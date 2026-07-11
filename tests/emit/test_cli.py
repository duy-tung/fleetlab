"""Tests for `fleetlab.cli` (FL-T009): `fleetlab recommend --results ...
--slo ... --cost ...` end-to-end, using real files from this repo's
evidence corpus (not synthetic fixtures) -- proving the CLI is a genuinely
reusable emitter, not hardcoded to the one E2 scenario
`fleetlab/emit/build_recommendation.py` publishes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fleetlab.cli import main
from fleetlab.emit.recommendation import validate_recommendation

REPO_ROOT = Path(__file__).resolve().parents[2]
FITTED_PROFILE = (
    REPO_ROOT / "profiles" / "fitted" / "mock-loopback-cpu-dev__mock-8b__gateway-mock-admission-sane-v1.json"
)
BASELINE_RESULT = (
    REPO_ROOT
    / "tests" / "fitting" / "fixtures" / "real" / "ib-t010" / "results" / "ib-t010-e2-baseline-1x-sane.benchmark-result.json"
)
OVERLOAD_RESULT = (
    REPO_ROOT
    / "tests" / "fitting" / "fixtures" / "real" / "ib-t010" / "results" / "ib-t010-e2-overload-5x-sane.benchmark-result.json"
)
WORKLOAD = REPO_ROOT / "tests" / "fitting" / "fixtures" / "real" / "ib-t010" / "e2-overload-workload.json"
SLO = REPO_ROOT / "profiles" / "examples" / "slo-chat-interactive.json"
COST_PROFILE = REPO_ROOT / "profiles" / "examples" / "cost-g5-xlarge-ondemand.json"


def _base_args(out_path: Path) -> list:
    return [
        "recommend",
        "--fitted-profile", str(FITTED_PROFILE),
        "--results", str(BASELINE_RESULT),
        "--results", str(OVERLOAD_RESULT),
        "--workload", str(WORKLOAD),
        "--slo", str(SLO),
        "--cost", str(COST_PROFILE),
        "--demand-rps", "189.0362",
        "--hardware-profile-id", "mock-loopback-cpu-dev",
        "--holdout-relative-error", "-0.1256752011727604",
        "--autoscaling-scale-out-value", "1",
        "--autoscaling-scale-in-value", "1",
        "--assumption", "test assumption one",
        "--sensitivity-note", "test sensitivity note one",
        "--out", str(out_path),
    ]


def test_cli_recommend_end_to_end_writes_a_schema_valid_file(tmp_path):
    out_path = tmp_path / "rec.capacity-recommendation.json"
    exit_code = main(_base_args(out_path))
    assert exit_code == 0
    assert out_path.exists()
    doc = json.loads(out_path.read_text())
    validate_recommendation(doc, out_path)  # must not raise
    assert doc["recommended_topology"]["replica_groups"][0]["replica_count"] == 6


def test_cli_recommend_requires_at_least_one_assumption(tmp_path):
    out_path = tmp_path / "rec.json"
    args = _base_args(out_path)
    # strip the --assumption pair
    idx = args.index("--assumption")
    del args[idx : idx + 2]
    with pytest.raises(SystemExit):
        main(args)


def test_cli_recommend_respects_replica_safety_margin(tmp_path):
    out_a = tmp_path / "rec_a.json"
    out_b = tmp_path / "rec_b.json"
    main(_base_args(out_a))
    args_b = _base_args(out_b) + ["--replica-safety-margin", "0.3"]
    main(args_b)
    doc_a = json.loads(out_a.read_text())
    doc_b = json.loads(out_b.read_text())
    replicas_a = doc_a["recommended_topology"]["replica_groups"][0]["replica_count"]
    replicas_b = doc_b["recommended_topology"]["replica_groups"][0]["replica_count"]
    assert replicas_b >= replicas_a
