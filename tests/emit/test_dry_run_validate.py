"""Tests for `fleetlab.emit.dry_run_validate` (FL-T009): the consumption-
side validation script, PENDING-on-RQ-14 for real inferops data (docs/
implementation-notes.md) but exercised here against a synthetic,
clearly-labeled post-change fixture so the mechanism itself is proven
correct and ready to run against a real one."""

from __future__ import annotations

import json

import pytest

from fleetlab.emit.build_recommendation import build_recommendation
from fleetlab.emit.dry_run_validate import (
    check_goodput_meets_lower_bound,
    check_latency_within_upper_bound,
    check_replica_count_applied,
    main,
    run_dry_run_validation,
)


def _synthetic_post_change_result(*, achieved_rps: float, e2e_p95: float) -> dict:
    """A SYNTHETIC post-change benchmark-result -- not real inferops data
    (PENDING-on-RQ-14) -- shaped exactly like a real one, used only to
    prove the checking mechanism itself works."""
    return {
        "result_id": "synthetic-post-change-001",
        "goodput": {"requests_per_second_meeting_slo": achieved_rps},
        "pooled_percentiles": {"tables": {"e2e_duration_seconds": {"p95": e2e_p95}}},
    }


def test_check_replica_count_applied_pass_and_fail():
    recommendation = build_recommendation()
    expected = recommendation["recommended_topology"]["replica_groups"][0]["replica_count"]
    matching = [{"replica_count": expected}]
    mismatched = [{"replica_count": expected - 1}]
    assert check_replica_count_applied(recommendation, matching).passed is True
    assert check_replica_count_applied(recommendation, mismatched).passed is False


def test_check_goodput_meets_lower_bound_pass_and_fail():
    recommendation = build_recommendation()
    lower = recommendation["predictions"]["goodput"]["requests_per_second_meeting_slo"]["uncertainty"]["lower"]
    passing = _synthetic_post_change_result(achieved_rps=lower + 1.0, e2e_p95=0.1)
    failing = _synthetic_post_change_result(achieved_rps=lower - 1.0, e2e_p95=0.1)
    assert check_goodput_meets_lower_bound(recommendation, passing).passed is True
    assert check_goodput_meets_lower_bound(recommendation, failing).passed is False


def test_check_latency_within_upper_bound_pass_and_fail():
    recommendation = build_recommendation()
    upper = recommendation["predictions"]["latency"]["e2e_duration_seconds_p95"]["uncertainty"]["upper"]
    passing = _synthetic_post_change_result(achieved_rps=1000.0, e2e_p95=upper - 0.01)
    failing = _synthetic_post_change_result(achieved_rps=1000.0, e2e_p95=upper + 0.01)
    assert check_latency_within_upper_bound(recommendation, passing).passed is True
    assert check_latency_within_upper_bound(recommendation, failing).passed is False


def test_run_dry_run_validation_all_pass():
    recommendation = build_recommendation()
    expected_replicas = recommendation["recommended_topology"]["replica_groups"][0]["replica_count"]
    lower = recommendation["predictions"]["goodput"]["requests_per_second_meeting_slo"]["uncertainty"]["lower"]
    upper = recommendation["predictions"]["latency"]["e2e_duration_seconds_p95"]["uncertainty"]["upper"]
    applied = [{"replica_count": expected_replicas}]
    post_change = _synthetic_post_change_result(achieved_rps=lower + 5.0, e2e_p95=upper - 0.01)
    results = run_dry_run_validation(recommendation, applied, post_change)
    assert all(r.passed for r in results)
    assert {r.name for r in results} == {
        "replica_count_applied",
        "goodput_meets_lower_bound",
        "latency_within_upper_bound",
    }


def test_run_dry_run_validation_surfaces_a_real_miss_honestly():
    """A miss here is exactly the 'predicted vs measured, including where
    the prediction was wrong' outcome the I6 loop is built to surface, not
    a bug in the script."""
    recommendation = build_recommendation()
    expected_replicas = recommendation["recommended_topology"]["replica_groups"][0]["replica_count"]
    lower = recommendation["predictions"]["goodput"]["requests_per_second_meeting_slo"]["uncertainty"]["lower"]
    applied = [{"replica_count": expected_replicas}]
    post_change = _synthetic_post_change_result(achieved_rps=lower - 10.0, e2e_p95=0.05)
    results = run_dry_run_validation(recommendation, applied, post_change)
    by_name = {r.name: r for r in results}
    assert by_name["goodput_meets_lower_bound"].passed is False


def test_cli_main_end_to_end(tmp_path):
    recommendation = build_recommendation()
    rec_path = tmp_path / "rec.json"
    rec_path.write_text(json.dumps(recommendation))

    expected_replicas = recommendation["recommended_topology"]["replica_groups"][0]["replica_count"]
    applied_path = tmp_path / "applied.json"
    applied_path.write_text(json.dumps({"replica_groups": [{"replica_count": expected_replicas}]}))

    lower = recommendation["predictions"]["goodput"]["requests_per_second_meeting_slo"]["uncertainty"]["lower"]
    upper = recommendation["predictions"]["latency"]["e2e_duration_seconds_p95"]["uncertainty"]["upper"]
    result_path = tmp_path / "post_change_result.json"
    result_path.write_text(json.dumps(_synthetic_post_change_result(achieved_rps=lower + 5.0, e2e_p95=upper - 0.01)))

    exit_code = main(
        [
            "--recommendation", str(rec_path),
            "--applied-topology", str(applied_path),
            "--post-change-result", str(result_path),
        ]
    )
    assert exit_code == 0


def test_cli_main_returns_nonzero_on_a_failing_check(tmp_path):
    recommendation = build_recommendation()
    rec_path = tmp_path / "rec.json"
    rec_path.write_text(json.dumps(recommendation))

    applied_path = tmp_path / "applied.json"
    applied_path.write_text(json.dumps({"replica_groups": [{"replica_count": 1}]}))  # wrong on purpose

    result_path = tmp_path / "post_change_result.json"
    result_path.write_text(json.dumps(_synthetic_post_change_result(achieved_rps=1.0, e2e_p95=99.0)))

    exit_code = main(
        [
            "--recommendation", str(rec_path),
            "--applied-topology", str(applied_path),
            "--post-change-result", str(result_path),
        ]
    )
    assert exit_code == 1
