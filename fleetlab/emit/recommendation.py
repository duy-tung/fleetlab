"""Contract-7 (capacity-recommendation) builder + validator (FL-T009).

Assembles the machine-checkable recommendation the I6 loop applies:
input references, recommended topology, predictions with **structurally
required uncertainty** on every quantity, an autoscaling signal +
thresholds, assumptions, sensitivity notes, and an optional
`re_measurement` plan. Every predicted quantity is built through
`predicted_quantity()` below, which refuses a degenerate/inverted interval
before this module ever hands the document to the schema validator.

Validation reuses `fleetlab.ingest`'s already-pinned bundle machinery
(`fleetlab.ingest.validate.validate_instance`) against the
`capacity-recommendation` schema -- the identical vendored schema file the
bundle's own kit CLI (`vendor/serving-contracts-v0.2.0/kit/
contracts-validate.py`) validates against, so there is no drift between
what this module enforces and what CI's `make contracts-verify` / a
consumer's own kit run would find.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from fleetlab.ingest.bundle import ContractBundle, default_bundle
from fleetlab.ingest.validate import validate_instance


def predicted_quantity(
    *,
    value: float,
    unit: str,
    lower: float,
    upper: float,
    method: str,
    confidence: Optional[float] = None,
) -> Dict[str, Any]:
    """Builds one `$defs/predictedQuantity` object. Refuses an inverted or
    missing-method interval before it ever reaches schema validation --
    Contract 7's whole point is that "a point prediction without an
    interval is not expressible"; this is that rule enforced on the
    producer side too, not just the consumer side."""
    if lower > upper:
        raise ValueError(f"lower ({lower}) must be <= upper ({upper})")
    if not method.strip():
        raise ValueError("method must be a non-empty description of how the interval was obtained")
    uncertainty: Dict[str, Any] = {"lower": lower, "upper": upper, "method": method}
    if confidence is not None:
        if not (0.0 < confidence <= 1.0):
            raise ValueError(f"confidence must be in (0, 1], got {confidence}")
        uncertainty["confidence"] = confidence
    return {"value": value, "unit": unit, "uncertainty": uncertainty}


def latency_bracket_from_benchmark_results(
    benchmark_results: Sequence[dict],
    *,
    signal: str = "e2e_duration_seconds",
) -> Dict[str, float]:
    """A generic, measured-data latency bracket for engine-configs with no
    fitted latency model (`latency_profile.status == "PENDING"`, e.g. every
    ib-t010 E2/E2b config -- `docs/notes/fitting-method.md` §4): given one
    or more real `benchmark-result` documents, `value` is the mean of their
    own pooled p95 for `signal`, `lower` is the smallest p50 among them,
    `upper` is the largest p95. This is a **measured-data approximation**,
    not a fitted-model-based prediction -- callers must state that in the
    recommendation's `assumptions`.
    """
    if not benchmark_results:
        raise ValueError("at least one benchmark_result is required")
    p50s = []
    p95s = []
    for result in benchmark_results:
        table = result["pooled_percentiles"]["tables"][signal]
        p50s.append(table["p50"])
        p95s.append(table["p95"])
    return {
        "value": sum(p95s) / len(p95s),
        "lower": min(p50s),
        "upper": max(p95s),
    }


def build_capacity_recommendation(
    *,
    recommendation_id: str,
    created_at: str,
    producer_version: str,
    benchmark_result_ids: Sequence[str],
    workload_ref: Dict[str, str],
    slo_ref: Dict[str, Any],
    cost_profile_ref: Dict[str, Any],
    hardware_profile_refs: Sequence[Dict[str, Any]],
    model_profile_ref: Optional[Dict[str, Any]],
    demand_forecast: Dict[str, Any],
    baseline: Optional[str],
    change_summary: str,
    replica_groups: Sequence[Dict[str, Any]],
    goodput: Dict[str, Any],
    goodput_at_offered_rps: float,
    latency: Dict[str, Dict[str, Any]],
    cost: Dict[str, Dict[str, Any]],
    autoscaling_signal: Dict[str, Any],
    autoscaling_thresholds: Dict[str, Any],
    autoscaling_bounds: Optional[Dict[str, int]],
    autoscaling_notes: Optional[str],
    assumptions: Sequence[str],
    sensitivity_notes: Sequence[str],
    re_measurement: Optional[Dict[str, Any]] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Assembles one Contract-7 document. Fails fast on the schema's own
    non-empty-array requirements (`minItems`/`required`) before ever
    invoking the schema validator, so a caller gets a specific Python
    exception rather than an opaque jsonschema error for the common
    mistakes."""
    if not benchmark_result_ids:
        raise ValueError("benchmark_result_ids must be non-empty")
    if not hardware_profile_refs:
        raise ValueError("hardware_profile_refs must be non-empty")
    if not replica_groups:
        raise ValueError("replica_groups must be non-empty")
    if not assumptions:
        raise ValueError("assumptions must be non-empty -- an unstated-assumptions model is a fabricated default")
    if not sensitivity_notes:
        raise ValueError("sensitivity_notes must be non-empty")

    doc: Dict[str, Any] = {
        "recommendation_id": recommendation_id,
        "created_at": created_at,
        "producer": {"tool": "fleetlab", "version": producer_version},
        "inputs": {
            "benchmark_result_ids": list(benchmark_result_ids),
            "workload_ref": workload_ref,
            "slo_ref": slo_ref,
            "cost_profile_ref": cost_profile_ref,
            "hardware_profile_refs": list(hardware_profile_refs),
            "demand_forecast": demand_forecast,
        },
        "recommended_topology": {
            "replica_groups": list(replica_groups),
            "change_summary": change_summary,
        },
        "predictions": {
            "goodput": {"requests_per_second_meeting_slo": goodput, "at_offered_rps": goodput_at_offered_rps},
            "latency": latency,
            "cost": cost,
        },
        "autoscaling": {
            "signal": autoscaling_signal,
            "thresholds": autoscaling_thresholds,
        },
        "assumptions": list(assumptions),
        "sensitivity_notes": list(sensitivity_notes),
    }
    if model_profile_ref is not None:
        doc["inputs"]["model_profile_ref"] = model_profile_ref
    if baseline is not None:
        doc["recommended_topology"]["baseline"] = baseline
    if autoscaling_bounds is not None:
        doc["autoscaling"]["bounds"] = autoscaling_bounds
    if autoscaling_notes is not None:
        doc["autoscaling"]["notes"] = autoscaling_notes
    if re_measurement is not None:
        doc["re_measurement"] = re_measurement
    if notes is not None:
        doc["notes"] = notes
    return doc


def validate_recommendation(
    doc: dict, source: "str | Path" = "<in-memory recommendation>", bundle: Optional[ContractBundle] = None
) -> None:
    """Validates `doc` against the pinned `capacity-recommendation` schema.
    Raises one of `fleetlab.ingest`'s typed refusal errors on failure;
    returns None (silently) when valid."""
    validate_instance("capacity-recommendation", doc, source, bundle or default_bundle())


def write_recommendation(doc: dict, out_path: "str | Path") -> Path:
    """Validates, then writes `doc` as pretty-printed JSON to `out_path`.
    Never writes a schema-invalid recommendation to disk."""
    out_path = Path(out_path)
    validate_recommendation(doc, out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=2) + "\n")
    return out_path
