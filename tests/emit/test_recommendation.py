"""Tests for `fleetlab.emit.recommendation` (FL-T009): the predictedQuantity
builder's own refusal, the latency-bracket helper, schema validation against
the real serving-contracts vendored bundle (both the vendor's own valid
example and its invalid/missing-uncertainty negative fixture -- "a validator
that cannot fail is not evidence"), and `build_capacity_recommendation`'s
required-non-empty-array guards."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fleetlab.ingest.errors import IngestError
from fleetlab.emit.recommendation import (
    build_capacity_recommendation,
    latency_bracket_from_benchmark_results,
    predicted_quantity,
    validate_recommendation,
    write_recommendation,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
VENDOR_VALID_EXAMPLE = (
    REPO_ROOT / "vendor" / "serving-contracts-v0.2.0" / "examples" / "capacity" / "recommendation-chat-short-scaleout.json"
)
VENDOR_INVALID_EXAMPLE = (
    REPO_ROOT
    / "vendor"
    / "serving-contracts-v0.2.0"
    / "examples"
    / "capacity"
    / "invalid"
    / "recommendation-missing-uncertainty.json"
)


def test_predicted_quantity_known_shape():
    pq = predicted_quantity(value=10.0, unit="requests_per_second", lower=9.0, upper=11.0, method="test method")
    assert pq == {
        "value": 10.0,
        "unit": "requests_per_second",
        "uncertainty": {"lower": 9.0, "upper": 11.0, "method": "test method"},
    }


def test_predicted_quantity_with_confidence():
    pq = predicted_quantity(value=10.0, unit="seconds", lower=9.0, upper=11.0, method="m", confidence=0.8)
    assert pq["uncertainty"]["confidence"] == 0.8


def test_predicted_quantity_rejects_inverted_interval():
    with pytest.raises(ValueError):
        predicted_quantity(value=10.0, unit="seconds", lower=11.0, upper=9.0, method="m")


def test_predicted_quantity_rejects_empty_method():
    with pytest.raises(ValueError):
        predicted_quantity(value=10.0, unit="seconds", lower=9.0, upper=11.0, method="  ")


def test_predicted_quantity_rejects_bad_confidence():
    with pytest.raises(ValueError):
        predicted_quantity(value=10.0, unit="seconds", lower=9.0, upper=11.0, method="m", confidence=1.5)


def test_latency_bracket_known_answer():
    result_a = {"pooled_percentiles": {"tables": {"e2e_duration_seconds": {"p50": 0.1, "p95": 0.2}}}}
    result_b = {"pooled_percentiles": {"tables": {"e2e_duration_seconds": {"p50": 0.15, "p95": 0.4}}}}
    bracket = latency_bracket_from_benchmark_results([result_a, result_b])
    assert bracket["value"] == pytest.approx((0.2 + 0.4) / 2)
    assert bracket["lower"] == pytest.approx(0.1)
    assert bracket["upper"] == pytest.approx(0.4)


def test_latency_bracket_rejects_empty_input():
    with pytest.raises(ValueError):
        latency_bracket_from_benchmark_results([])


def test_validate_recommendation_accepts_the_vendor_valid_example():
    doc = json.loads(VENDOR_VALID_EXAMPLE.read_text())
    validate_recommendation(doc, VENDOR_VALID_EXAMPLE)  # must not raise


def test_validate_recommendation_refuses_the_vendor_missing_uncertainty_example():
    """The bundle's own negative fixture: a bare point value with no
    uncertainty object. If this ever validated cleanly, our validator
    would not be evidence of anything."""
    doc = json.loads(VENDOR_INVALID_EXAMPLE.read_text())
    with pytest.raises(IngestError):
        validate_recommendation(doc, VENDOR_INVALID_EXAMPLE)


def _minimal_kwargs(**overrides):
    base = dict(
        recommendation_id="rec-test-001",
        created_at="2026-07-11T00:00:00Z",
        producer_version="0.1.0",
        benchmark_result_ids=["res-1"],
        workload_ref={"name": "chat-short", "version": "1.0.0"},
        slo_ref={"id": "slo-1", "version": "1.0.0"},
        cost_profile_ref={"id": "cost-1", "version": "1.0.0"},
        hardware_profile_refs=[{"id": "hw-1"}],
        model_profile_ref=None,
        demand_forecast={"peak_rps": 10.0, "basis": "test"},
        baseline=None,
        change_summary="test change",
        replica_groups=[
            {
                "hardware_profile_ref": {"id": "hw-1"},
                "replica_count": 2,
                "engine_config": {"engine": {"name": "mock", "version": "dev"}, "flags": {}},
            }
        ],
        goodput=predicted_quantity(value=10.0, unit="requests_per_second", lower=9.0, upper=10.0, method="m"),
        goodput_at_offered_rps=10.0,
        latency={"e2e_duration_seconds_p95": predicted_quantity(value=0.1, unit="seconds", lower=0.05, upper=0.15, method="m")},
        cost={"usd_per_hour": predicted_quantity(value=1.0, unit="usd_per_hour", lower=1.0, upper=1.0, method="m")},
        autoscaling_signal={"source": "gateway", "metric": "inference_queue_depth"},
        autoscaling_thresholds={
            "scale_out": {"comparator": ">", "value": 1},
            "scale_in": {"comparator": "<", "value": 1},
        },
        autoscaling_bounds=None,
        autoscaling_notes=None,
        assumptions=["an assumption"],
        sensitivity_notes=["a sensitivity note"],
    )
    base.update(overrides)
    return base


def test_build_capacity_recommendation_minimal_document_is_schema_valid():
    doc = build_capacity_recommendation(**_minimal_kwargs())
    validate_recommendation(doc, "<test>")  # must not raise


def test_build_capacity_recommendation_rejects_empty_benchmark_result_ids():
    with pytest.raises(ValueError):
        build_capacity_recommendation(**_minimal_kwargs(benchmark_result_ids=[]))


def test_build_capacity_recommendation_rejects_empty_hardware_profile_refs():
    with pytest.raises(ValueError):
        build_capacity_recommendation(**_minimal_kwargs(hardware_profile_refs=[]))


def test_build_capacity_recommendation_rejects_empty_replica_groups():
    with pytest.raises(ValueError):
        build_capacity_recommendation(**_minimal_kwargs(replica_groups=[]))


def test_build_capacity_recommendation_rejects_empty_assumptions():
    with pytest.raises(ValueError):
        build_capacity_recommendation(**_minimal_kwargs(assumptions=[]))


def test_build_capacity_recommendation_rejects_empty_sensitivity_notes():
    with pytest.raises(ValueError):
        build_capacity_recommendation(**_minimal_kwargs(sensitivity_notes=[]))


def test_build_capacity_recommendation_with_re_measurement_is_schema_valid():
    doc = build_capacity_recommendation(
        **_minimal_kwargs(
            re_measurement={
                "workload_ref": {"name": "chat-short", "version": "1.0.0", "seed": 1},
                "single_declared_variable": "replica_count 1 -> 2",
                "success_criteria": ["achieved_rps >= 9.0"],
            }
        )
    )
    validate_recommendation(doc, "<test>")


def test_write_recommendation_refuses_to_write_a_schema_invalid_document(tmp_path):
    bad_doc = {"recommendation_id": "x"}  # missing everything else
    with pytest.raises(IngestError):
        write_recommendation(bad_doc, tmp_path / "bad.json")
    assert not (tmp_path / "bad.json").exists()


def test_write_recommendation_writes_a_valid_document(tmp_path):
    doc = build_capacity_recommendation(**_minimal_kwargs())
    out = write_recommendation(doc, tmp_path / "rec.capacity-recommendation.json")
    assert out.exists()
    assert json.loads(out.read_text()) == doc
