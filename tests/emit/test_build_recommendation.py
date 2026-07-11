"""Tests for `fleetlab.emit.build_recommendation` (FL-T009): the real E2
'5x overload' capacity-recommendation this task publishes. Determinism,
schema validity, and the headline numbers (replica count, uncertainty,
autoscaling thresholds) the task's own report must state."""

from __future__ import annotations

import json

import pytest

from fleetlab.emit.build_recommendation import build_recommendation
from fleetlab.emit.recommendation import validate_recommendation


def test_build_recommendation_is_deterministic():
    a = json.dumps(build_recommendation(), sort_keys=True)
    b = json.dumps(build_recommendation(), sort_keys=True)
    assert a == b


def test_build_recommendation_is_schema_valid():
    doc = build_recommendation()
    validate_recommendation(doc, "<test>")  # must not raise


def test_recommended_replica_count_is_six():
    doc = build_recommendation()
    groups = doc["recommended_topology"]["replica_groups"]
    assert len(groups) == 1
    assert groups[0]["replica_count"] == 6


def test_demand_is_the_real_e2_overload_workload_rate():
    doc = build_recommendation()
    assert doc["inputs"]["demand_forecast"]["peak_rps"] == pytest.approx(189.0362)
    assert doc["predictions"]["goodput"]["at_offered_rps"] == pytest.approx(189.0362)


def test_goodput_uncertainty_reflects_the_g8_holdout_error_not_just_fit_stderr():
    doc = build_recommendation()
    goodput = doc["predictions"]["goodput"]["requests_per_second_meeting_slo"]
    assert goodput["value"] == pytest.approx(189.0362)
    assert goodput["uncertainty"]["upper"] == pytest.approx(189.0362)
    # 12.6% G8 holdout error dominates the 3.3%-relative fit stderr
    assert goodput["uncertainty"]["lower"] == pytest.approx(165.279, abs=0.01)
    assert "G8 holdout" in goodput["uncertainty"]["method"]


def test_autoscaling_signal_is_contract_2_canonical_queue_depth():
    doc = build_recommendation()
    signal = doc["autoscaling"]["signal"]
    assert signal["source"] == "gateway"
    assert signal["metric"] == "inference_queue_depth"


def test_inputs_reference_the_real_benchmark_result_ids():
    doc = build_recommendation()
    assert set(doc["inputs"]["benchmark_result_ids"]) == {
        "ib-t010-e2-baseline-1x-sane",
        "ib-t010-e2-overload-5x-sane",
    }


def test_sensitivity_notes_disclose_the_n_minus_1_failover_deficit():
    doc = build_recommendation()
    joined = " ".join(doc["sensitivity_notes"])
    assert "N-1" in joined
    assert "deficit" in joined


def test_notes_field_names_the_dry_run_validation_script_and_rq14_status():
    doc = build_recommendation()
    assert "dry_run_validate" in doc["notes"]
    assert "RQ-14" in doc["notes"]


def test_re_measurement_success_criteria_reference_the_stated_bounds():
    doc = build_recommendation()
    re_measurement = doc["re_measurement"]
    lower = doc["predictions"]["goodput"]["requests_per_second_meeting_slo"]["uncertainty"]["lower"]
    assert any(f"{lower:.3f}" in c for c in re_measurement["success_criteria"])
