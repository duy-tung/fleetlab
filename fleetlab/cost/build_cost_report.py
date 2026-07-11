"""Regenerates `reports/scenarios/cost-model.json` (FL-T008 deliverable):
cost-per-1M-tokens-at-SLO, a cross-check against a real benchmark-result's
cost figures, and a price/load/SLO sensitivity sweep.

Run: `python3 -m fleetlab.cost.build_cost_report`

**MODEL DEMONSTRATION, not a real cost claim.** The only capacity/latency
profile in this repo with a G8-within-error outcome
(`mock-loopback-cpu-dev__mock-8b__gateway-mock-flags-v1-conncap2`) was
fitted on a **CPU-only mock backend**. This repo's evidence corpus has no
real hardware price at all -- there is no GPU, no billing record, nothing to
price honestly for that profile. This module therefore combines that fitted
profile's capacity/latency numbers with the `cost-g5-xlarge-ondemand`
example cost profile (`profiles/examples/cost-g5-xlarge-ondemand.json`,
vendored from `serving-contracts`'s reference examples, pricing a real
NVIDIA A10G GPU) purely to **demonstrate the cost-model mechanism** end to
end -- this is a hardware/config mismatch, stated explicitly in every
output artifact, never presented as "this mock backend costs $X on a G5."
"""

from __future__ import annotations

import hashlib
import json
import statistics
from pathlib import Path

from fleetlab.cost.model import (
    SloUnattainableError,
    compute_cost_at_slo,
    cost_per_1e6_tokens_usd,
    goodput_at_slo_rps,
    sensitivity_table,
)
from fleetlab.ingest import load_cost_profile, load_raw_events, load_slo

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "reports" / "scenarios"
FITTED_PROFILE = (
    REPO_ROOT
    / "profiles"
    / "fitted"
    / "mock-loopback-cpu-dev__mock-8b__gateway-mock-flags-v1-conncap2.json"
)
COST_PROFILE_PATH = REPO_ROOT / "profiles" / "examples" / "cost-g5-xlarge-ondemand.json"
SLO_PATH = REPO_ROOT / "profiles" / "examples" / "slo-chat-interactive.json"
SWEEP_EVENTS_DIR = REPO_ROOT / "tests" / "fitting" / "fixtures" / "real" / "ib-t008" / "sweep"
VENDOR_RESULT_EXAMPLE = (
    REPO_ROOT / "vendor" / "serving-contracts-v0.2.0" / "examples" / "benchmark" / "result.json"
)

AS_OF = "2026-07-11"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _measured_tokens_per_request() -> dict:
    """Mean input/output/total tokens per (ok) request, measured directly
    from the ib-t008 sweep's real raw events -- the same corpus FL-T004
    fitted the capacity/latency profile from, via `fleetlab.ingest`'s
    already-validated loader (not a re-parse). This is the one genuinely
    **measured** figure in this report; everything priced against a real
    GPU rate (the cost profile) is the demonstration path (module
    docstring)."""
    input_tokens = []
    output_tokens = []
    for point_dir in sorted(SWEEP_EVENTS_DIR.glob("point-*")):
        for rep_dir in sorted(point_dir.glob("rep-*")):
            events_path = rep_dir / "events.jsonl"
            if not events_path.exists():
                continue
            for event in load_raw_events(events_path):
                if event.status == "ok":
                    input_tokens.append(event.input_tokens)
                    output_tokens.append(event.output_tokens)
    if not input_tokens:
        raise ValueError(f"no ok events found under {SWEEP_EVENTS_DIR}")
    return {
        "n_ok_events": len(input_tokens),
        "mean_input_tokens": statistics.mean(input_tokens),
        "mean_output_tokens": statistics.mean(output_tokens),
        "mean_total_tokens": statistics.mean(input_tokens) + statistics.mean(output_tokens),
        "source": "tests/fitting/fixtures/real/ib-t008/sweep/point-*/rep-*/events.jsonl (measured)",
    }


def _recompute_check_against_vendor_example() -> dict:
    """Recompute `cost_per_1e6_tokens_usd` against the ONE example
    benchmark-result in this repo's evidence with a non-null `cost` block
    (`vendor/.../examples/benchmark/result.json` -- every real
    benchmark-result in the actual corpus carries `cost: null`, per
    `docs/notes/fitting-method.md`'s corpus inventory; this vendor example
    is itself illustrative, not a real measurement, per its own
    `comparability_note`). Checks the OUTPUT-token figure only
    (`per_million_output_tokens_usd`): the file's `throughput` block has
    `output_tokens_per_second` but no total (input+output) token rate, so
    `per_million_tokens_usd` (which needs the total) cannot be
    independently recomputed from this file's own fields -- a schema-
    coverage gap, recorded here rather than papered over with an assumed
    input-token rate."""
    example = json.loads(VENDOR_RESULT_EXAMPLE.read_text())
    cost_block = example["cost"]
    output_tokens_per_second = example["throughput"]["output_tokens_per_second"]
    usd_per_hour = 1.006  # cost-g5-xlarge-ondemand @ 0.1.0, on-demand, us-east-1 (same ref as cost_block)
    recomputed = cost_per_1e6_tokens_usd(usd_per_hour, output_tokens_per_second)
    stated = cost_block["per_million_output_tokens_usd"]
    return {
        "source_file": str(VENDOR_RESULT_EXAMPLE.relative_to(REPO_ROOT)),
        "note": (
            "This vendor example fixture is itself illustrative "
            "('Example fixture; all values illustrative, no measurement "
            "claims' per its own comparability_note) -- every REAL "
            "benchmark-result in this repo's corpus carries cost:null "
            "(checked: all 10 result files under tests/fitting/fixtures/"
            "real/ and tests/golden/fixtures/real/). This is the only "
            "recompute check the corpus supports."
        ),
        "cost_profile_ref": cost_block["cost_profile_ref"],
        "output_tokens_per_second": output_tokens_per_second,
        "usd_per_hour_used": usd_per_hour,
        "stated_per_million_output_tokens_usd": stated,
        "recomputed_per_million_output_tokens_usd": recomputed,
        "rel_error": (recomputed - stated) / stated,
        "per_million_tokens_usd_recompute": (
            "NOT independently recomputable from this file: "
            "benchmark-result.schema.json's throughput block has no "
            "total (input+output) token rate field, only "
            "output_tokens_per_second -- a schema-coverage gap, not an "
            "omission in this report."
        ),
        "stated_per_million_tokens_usd": cost_block["per_million_tokens_usd"],
    }


def build_report() -> dict:
    fitted = json.loads(FITTED_PROFILE.read_text())
    capacity_rps = fitted["capacity_profile"]["capacity_rps"]
    l0_seconds = fitted["latency_profile"]["l0_seconds"]

    cost_profile = load_cost_profile(COST_PROFILE_PATH)
    rates = {r.pricing_model: r for r in cost_profile.rates}
    on_demand = rates["on-demand"]
    spot = rates["spot"]

    slo = load_slo(SLO_PATH)
    (e2e_objective,) = [o for o in slo.objectives if o.signal == "e2e_duration_seconds"]

    tokens = _measured_tokens_per_request()

    results = {}
    for label, rate in (("on_demand", on_demand), ("spot", spot)):
        result = compute_cost_at_slo(
            capacity_rps=capacity_rps,
            l0_seconds=l0_seconds,
            slo_latency_seconds=e2e_objective.threshold,
            usd_per_hour=rate.usd_per_hour.value,
            tokens_per_request=tokens["mean_total_tokens"],
            pricing_model=rate.pricing_model,
            price_provenance_basis=rate.usd_per_hour.provenance.basis,
            price_as_of=rate.usd_per_hour.provenance.as_of,
        )
        results[label] = {
            "usd_per_hour": result.usd_per_hour,
            "pricing_model": result.pricing_model,
            "price_provenance_basis": result.price_provenance_basis,
            "price_as_of": result.price_as_of,
            "slo_latency_seconds": result.slo_latency_seconds,
            "slo_signal": f"{e2e_objective.signal}_{e2e_objective.statistic}",
            "slo_note": (
                "the fitted latency model predicts e2e p50, not the SLO "
                "objective's own p95 statistic -- inverting a p50 model "
                "against a p95 threshold is a stated approximation, not a "
                "rigorous claim (see fleetlab/cost/model.py module docstring)"
            ),
            "goodput_at_slo_rps": result.goodput_at_slo_rps,
            "fraction_of_capacity": result.goodput_at_slo_rps / capacity_rps,
            "cost_per_request_usd": result.cost_per_request_usd,
            "cost_per_1e6_tokens_usd": result.cost_per_1e6_tokens_usd,
        }

    # sensitivity: price x SLO x load, deterministic closed-form sweep
    slo_grid = [10.0, 1.0, 0.2, 0.1, l0_seconds * 1.05]
    price_multipliers = [0.5, 1.0, 1.5, 2.0]
    load_fractions = [0.5, 0.8, 1.0]
    sensitivity = []
    for point in sensitivity_table(
        capacity_rps=capacity_rps,
        l0_seconds=l0_seconds,
        base_usd_per_hour=on_demand.usd_per_hour.value,
        tokens_per_request=tokens["mean_total_tokens"],
        price_multipliers=price_multipliers,
        slo_latency_seconds_grid=slo_grid,
        load_fractions=load_fractions,
    ):
        sensitivity.append(
            {
                "price_multiplier": point.price_multiplier,
                "usd_per_hour": point.usd_per_hour,
                "slo_latency_seconds": point.slo_latency_seconds,
                "load_fraction_of_slo_goodput": point.load_fraction_of_slo_goodput,
                "achieved_rps": point.achieved_rps,
                "cost_per_1e6_tokens_usd": point.cost_per_1e6_tokens_usd,
                "cost_per_request_usd": point.cost_per_request_usd,
            }
        )

    return {
        "generated_by": "python3 -m fleetlab.cost.build_cost_report",
        "as_of": AS_OF,
        "basis": "MODEL DEMONSTRATION -- see module docstring: fitted capacity/latency from a measured CPU-only mock backend, priced against a real GPU's example cost profile. NOT a real cost claim for any actual hardware.",
        "fitted_profile": {
            "profile_id": fitted["profile_id"],
            "profile_path": str(FITTED_PROFILE.relative_to(REPO_ROOT)),
            "profile_sha256": _sha256_file(FITTED_PROFILE),
            "capacity_rps": capacity_rps,
            "capacity_rps_stderr": fitted["capacity_profile"]["capacity_rps_stderr"],
            "l0_seconds": l0_seconds,
            "l0_seconds_stderr": fitted["latency_profile"]["l0_seconds_stderr"],
            "hardware_label": fitted["hardware"]["label"],
        },
        "cost_profile": {
            "profile_id": cost_profile.profile_id,
            "version": cost_profile.version,
            "path": str(COST_PROFILE_PATH.relative_to(REPO_ROOT)),
            "sha256": _sha256_file(COST_PROFILE_PATH),
            "hardware_priced": "hardware-a10g-g5-xlarge (a real NVIDIA A10G GPU -- NOT the hardware capacity_rps/l0_seconds above were measured on)",
        },
        "slo_profile": {
            "slo_id": slo.slo_id,
            "path": str(SLO_PATH.relative_to(REPO_ROOT)),
            "sha256": _sha256_file(SLO_PATH),
            "objective_used": f"{e2e_objective.signal} {e2e_objective.statistic} {e2e_objective.comparator} {e2e_objective.threshold}",
        },
        "measured_tokens_per_request": tokens,
        "cost_at_slo": results,
        "recompute_check_vs_vendor_example": _recompute_check_against_vendor_example(),
        "sensitivity": {
            "grid": {
                "price_multipliers": price_multipliers,
                "slo_latency_seconds_grid": slo_grid,
                "load_fractions": load_fractions,
            },
            "note": (
                "Pure closed-form arithmetic (goodput_at_slo_rps + "
                "cost_per_1e6_tokens_usd), no RNG -- deterministic by "
                "construction, nothing to seed."
            ),
            "points": sensitivity,
        },
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report = build_report()
    out_path = OUT_DIR / "cost-model.json"
    out_path.write_text(json.dumps(report, indent=2) + "\n")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
