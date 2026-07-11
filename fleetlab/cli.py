"""fleetlab CLI entry point (FL-T009): `fleetlab recommend --results ... --slo ... --cost ...`.

A thin argparse wrapper over `fleetlab.emit`: loads a fitted capacity
profile, one or more benchmark-result files, a workload, an SLO, and a cost
profile, then emits a schema-valid Contract-7 capacity-recommendation file
sized for a caller-specified demand. Generic over any (hardware, model,
engine-config) fitted profile this repo (or a future one) produces --
not hardcoded to any one scenario. `fleetlab/emit/build_recommendation.py`
is the wiring script that calls this same machinery with this repo's real
E2 "5x overload" numbers to produce the actual published recommendation.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import List, Optional

from fleetlab.cost.model import cost_per_1e6_tokens_usd, cost_per_request_usd
from fleetlab.emit.recommendation import (
    build_capacity_recommendation,
    latency_bracket_from_benchmark_results,
    predicted_quantity,
    write_recommendation,
)
from fleetlab.emit.topology import goodput_uncertainty, recommend_replica_count
from fleetlab.ingest import load_cost_profile, load_slo, load_workload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fleetlab")
    sub = parser.add_subparsers(dest="command", required=True)

    rec = sub.add_parser("recommend", help="emit a Contract-7 capacity-recommendation file")
    rec.add_argument("--fitted-profile", required=True, type=Path, help="fitted capacity profile JSON (profiles/fitted/*.json)")
    rec.add_argument("--results", dest="benchmark_results", action="append", required=True, type=Path, help="benchmark-result.json (repeatable)")
    rec.add_argument("--workload", required=True, type=Path)
    rec.add_argument("--slo", required=True, type=Path)
    rec.add_argument("--cost", dest="cost_profile", required=True, type=Path)
    rec.add_argument("--pricing-model", default="on-demand")
    rec.add_argument("--demand-rps", required=True, type=float)
    rec.add_argument("--hardware-profile-id", required=True)
    rec.add_argument("--hardware-profile-version", default=None)
    rec.add_argument("--replica-safety-margin", type=float, default=0.0)
    rec.add_argument("--holdout-relative-error", type=float, default=None)
    rec.add_argument("--tokens-per-request", type=float, default=None, help="mean tokens/request for cost-per-1M-tokens; omitted if not given")
    rec.add_argument("--autoscaling-source", choices=["gateway", "engine"], default="gateway")
    rec.add_argument("--autoscaling-metric", default="inference_queue_depth")
    rec.add_argument("--autoscaling-scale-out-value", type=float, required=True)
    rec.add_argument("--autoscaling-scale-in-value", type=float, required=True)
    rec.add_argument("--autoscaling-scale-out-for-seconds", type=int, default=None)
    rec.add_argument("--autoscaling-scale-in-for-seconds", type=int, default=None)
    rec.add_argument("--autoscaling-notes", default=None)
    rec.add_argument("--assumption", dest="assumptions", action="append", required=True)
    rec.add_argument("--sensitivity-note", dest="sensitivity_notes", action="append", required=True)
    rec.add_argument("--notes", default=None)
    rec.add_argument("--recommendation-id", default=None)
    rec.add_argument("--engine-name", default=None)
    rec.add_argument("--engine-version", default=None)
    rec.add_argument("--out", required=True, type=Path)

    return parser


def _cmd_recommend(args: argparse.Namespace) -> int:
    fitted = json.loads(args.fitted_profile.read_text())
    benchmark_results = [json.loads(p.read_text()) for p in args.benchmark_results]
    workload = load_workload(args.workload)
    slo = load_slo(args.slo)
    cost_profile = load_cost_profile(args.cost_profile)
    rate = next(r for r in cost_profile.rates if r.pricing_model == args.pricing_model)

    capacity_rps = fitted["capacity_profile"]["capacity_rps"]
    capacity_stderr = fitted["capacity_profile"].get("capacity_rps_stderr")

    replica_count = recommend_replica_count(
        args.demand_rps, capacity_rps, safety_margin_fraction=args.replica_safety_margin
    )
    goodput = goodput_uncertainty(
        demand_rps=args.demand_rps,
        replica_count=replica_count,
        per_replica_capacity_rps=capacity_rps,
        per_replica_capacity_stderr=capacity_stderr,
        holdout_relative_error=args.holdout_relative_error,
    )

    bracket = latency_bracket_from_benchmark_results(benchmark_results)
    latency = {
        "e2e_duration_seconds_p95": predicted_quantity(
            value=bracket["value"],
            unit="seconds",
            lower=bracket["lower"],
            upper=bracket["upper"],
            method=(
                "measured-data bracket (no fitted latency model for this "
                "engine-config): value = mean p95 across the supplied "
                "benchmark-result inputs, lower = min p50, upper = max p95"
            ),
        )
    }

    usd_per_hour = replica_count * rate.usd_per_hour.value
    cost: dict = {
        "usd_per_hour": predicted_quantity(
            value=usd_per_hour,
            unit="usd_per_hour",
            lower=usd_per_hour,
            upper=usd_per_hour,
            confidence=0.95,
            method=f"deterministic: {replica_count} x {rate.pricing_model} rate from {cost_profile.profile_id}@{cost_profile.version}",
        ),
        "usd_per_successful_request": predicted_quantity(
            value=cost_per_request_usd(usd_per_hour, goodput.value),
            unit="usd_per_successful_request",
            lower=cost_per_request_usd(usd_per_hour, goodput.upper),
            upper=cost_per_request_usd(usd_per_hour, max(goodput.lower, 1e-9)),
            method="usd_per_hour divided by predicted goodput interval, converted to requests/hour",
        ),
    }
    if args.tokens_per_request is not None:
        cost["usd_per_million_tokens"] = predicted_quantity(
            value=cost_per_1e6_tokens_usd(usd_per_hour, goodput.value * args.tokens_per_request),
            unit="usd_per_million_tokens",
            lower=cost_per_1e6_tokens_usd(usd_per_hour, goodput.upper * args.tokens_per_request),
            upper=cost_per_1e6_tokens_usd(usd_per_hour, max(goodput.lower, 1e-9) * args.tokens_per_request),
            method="usd_per_hour divided by predicted token throughput (goodput x tokens_per_request)",
        )

    engine_config = {"flags": {}}
    if args.engine_name is not None:
        engine_config["engine"] = {"name": args.engine_name, "version": args.engine_version or "unknown"}
    else:
        engine_config["engine"] = {"name": fitted["model"]["id"], "version": fitted.get("engine_config_id", "unknown")}

    autoscaling_thresholds = {
        "scale_out": {"comparator": ">", "value": args.autoscaling_scale_out_value, **(
            {"for_seconds": args.autoscaling_scale_out_for_seconds} if args.autoscaling_scale_out_for_seconds is not None else {}
        )},
        "scale_in": {"comparator": "<", "value": args.autoscaling_scale_in_value, **(
            {"for_seconds": args.autoscaling_scale_in_for_seconds} if args.autoscaling_scale_in_for_seconds is not None else {}
        )},
    }

    recommendation_id = args.recommendation_id or f"rec-{_dt.datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    created_at = _dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    doc = build_capacity_recommendation(
        recommendation_id=recommendation_id,
        created_at=created_at,
        producer_version="0.1.0",
        benchmark_result_ids=[r["result_id"] for r in benchmark_results],
        workload_ref={"name": workload.name, "version": workload.version},
        slo_ref={"id": slo.slo_id, "version": slo.version},
        cost_profile_ref={"id": cost_profile.profile_id, "version": cost_profile.version},
        hardware_profile_refs=[{"id": args.hardware_profile_id, **({"version": args.hardware_profile_version} if args.hardware_profile_version else {})}],
        model_profile_ref=None,
        demand_forecast={"peak_rps": args.demand_rps, "basis": "CLI-supplied demand-rps argument"},
        baseline=None,
        change_summary=f"scale to {replica_count} replica(s) of {fitted.get('engine_config_id', fitted.get('profile_id'))} to serve {args.demand_rps} rps",
        replica_groups=[{"hardware_profile_ref": {"id": args.hardware_profile_id}, "replica_count": replica_count, "engine_config": engine_config}],
        goodput=predicted_quantity(
            value=goodput.value, unit="requests_per_second", lower=goodput.lower, upper=goodput.upper, method=goodput.method
        ),
        goodput_at_offered_rps=args.demand_rps,
        latency=latency,
        cost=cost,
        autoscaling_signal={"source": args.autoscaling_source, "metric": args.autoscaling_metric},
        autoscaling_thresholds=autoscaling_thresholds,
        autoscaling_bounds=None,
        autoscaling_notes=args.autoscaling_notes,
        assumptions=args.assumptions,
        sensitivity_notes=args.sensitivity_notes,
        notes=args.notes,
    )
    write_recommendation(doc, args.out)
    print(f"wrote {args.out} (recommendation_id={recommendation_id}, replica_count={replica_count})")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "recommend":
        return _cmd_recommend(args)
    parser.error(f"unknown command {args.command!r}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
