"""Emits the REAL FL-T009 capacity-recommendation (FL-T009 deliverable):
the ib-t010 E2 "5x overload" scale-out case.

The E2/E2b overload evidence (FL-T004; `reports/holdout-validation.md` §2a)
shows the single mock-backend replica saturating well below the "5x"
offered-rate stress-test point (189.0362 rps): its own G8 holdout result
under-predicted the achieved throughput at that point by 12.6%. This module
recommends the replica count the fitted `admission-sane-v1` capacity model
(33.159 rps/replica) implies for that 189.0362 rps demand, with honest
uncertainty populated from this profile's own real error bars (fit stderr
AND the published G8 holdout relative error) -- this is the recommendation
the I6 loop would actually apply and re-measure.

Run: `python3 -m fleetlab.emit.build_recommendation`
"""

from __future__ import annotations

import json
from pathlib import Path

from fleetlab.cost.model import cost_per_1e6_tokens_usd, cost_per_request_usd
from fleetlab.emit.recommendation import (
    build_capacity_recommendation,
    latency_bracket_from_benchmark_results,
    predicted_quantity,
    write_recommendation,
)
from fleetlab.emit.topology import fleet_capacity_rps, goodput_uncertainty, recommend_replica_count
from fleetlab.ingest import load_cost_profile, load_workload

REPO_ROOT = Path(__file__).resolve().parents[2]
FITTED_PROFILE_PATH = REPO_ROOT / "profiles" / "fitted" / "mock-loopback-cpu-dev__mock-8b__gateway-mock-admission-sane-v1.json"
BASELINE_RESULT_PATH = REPO_ROOT / "tests" / "fitting" / "fixtures" / "real" / "ib-t010" / "results" / "ib-t010-e2-baseline-1x-sane.benchmark-result.json"
OVERLOAD_RESULT_PATH = REPO_ROOT / "tests" / "fitting" / "fixtures" / "real" / "ib-t010" / "results" / "ib-t010-e2-overload-5x-sane.benchmark-result.json"
OVERLOAD_WORKLOAD_PATH = REPO_ROOT / "tests" / "fitting" / "fixtures" / "real" / "ib-t010" / "e2-overload-workload.json"
BASELINE_WORKLOAD_PATH = REPO_ROOT / "tests" / "fitting" / "fixtures" / "real" / "ib-t010" / "e2-baseline-workload.json"
COST_PROFILE_PATH = REPO_ROOT / "profiles" / "examples" / "cost-g5-xlarge-ondemand.json"
OUT_PATH = REPO_ROOT / "examples" / "recommendations" / "e2-admission-sane-v1-5x-scaleout.capacity-recommendation.json"

RECOMMENDATION_ID = "rec-2026-07-11-e2-admission-sane-v1-5x-scaleout-001"
CREATED_AT = "2026-07-11T00:00:00Z"
REPLICA_SAFETY_MARGIN = 0.0  # this recommendation sizes exactly to the stated demand; see sensitivity_notes for the N-1 caveat


def build_recommendation() -> dict:
    fitted = json.loads(FITTED_PROFILE_PATH.read_text())
    baseline_result = json.loads(BASELINE_RESULT_PATH.read_text())
    overload_result = json.loads(OVERLOAD_RESULT_PATH.read_text())
    overload_workload = load_workload(OVERLOAD_WORKLOAD_PATH)
    baseline_workload = load_workload(BASELINE_WORKLOAD_PATH)
    cost_profile = load_cost_profile(COST_PROFILE_PATH)
    on_demand = next(r for r in cost_profile.rates if r.pricing_model == "on-demand")

    capacity_rps = fitted["capacity_profile"]["capacity_rps"]
    capacity_stderr = fitted["capacity_profile"]["capacity_rps_stderr"]
    holdout_rel_error = fitted["holdout_validation"]["rel_error"]

    # The workload's declared OFFERED rate (189.0362 rps) is the demand this
    # recommendation is sized for. The result's own ACHIEVED rate at that
    # point (37.925 rps, overload_result["throughput"]["requests_per_second"])
    # is a different, much smaller number -- the whole point of this
    # recommendation is that 1 replica cannot serve 189.0362 rps of demand at
    # all; it saturates near ~33-38 rps regardless of how much is offered.
    demand_rps = overload_workload.arrival_process["rate_rps"]

    replica_count = recommend_replica_count(
        demand_rps, capacity_rps, safety_margin_fraction=REPLICA_SAFETY_MARGIN
    )
    goodput = goodput_uncertainty(
        demand_rps=demand_rps,
        replica_count=replica_count,
        per_replica_capacity_rps=capacity_rps,
        per_replica_capacity_stderr=capacity_stderr,
        holdout_relative_error=holdout_rel_error,
    )

    # N-1 failover check (reuses fleetlab.dynamics.headroom's own arithmetic
    # inline here, since this recommendation's honest sensitivity note --
    # not its point recommendation -- is what surfaces it): with the
    # recommended replica_count sized exactly to demand, is there any
    # single-replica-failure headroom at all?
    n_minus_1_capacity = fleet_capacity_rps(replica_count - 1, capacity_rps) if replica_count > 1 else 0.0
    n_minus_1_deficit = max(0.0, demand_rps - n_minus_1_capacity)

    bracket = latency_bracket_from_benchmark_results([baseline_result, overload_result])
    latency = {
        "e2e_duration_seconds_p95": predicted_quantity(
            value=bracket["value"],
            unit="seconds",
            lower=bracket["lower"],
            upper=bracket["upper"],
            method=(
                "measured-data bracket, NOT a fitted-model prediction: this "
                "engine-config's latency_profile.status is PENDING (no "
                "training point below its own fitted capacity exists, "
                "reports/holdout-validation.md §3) -- value = mean p95 "
                "across the baseline (ib-t010-e2-baseline-1x-sane) and "
                "overload (ib-t010-e2-overload-5x-sane) benchmark-results' "
                "own real pooled e2e_duration_seconds tables; lower = "
                "baseline's p50 (0.168s); upper = overload's p95 (0.309s)"
            ),
        )
    }

    usd_per_hour = replica_count * on_demand.usd_per_hour.value
    baseline_mean_output_tokens_per_request = (
        baseline_result["throughput"]["total_output_tokens"] / baseline_result["throughput"]["total_requests"]
    )
    cost = {
        "usd_per_hour": predicted_quantity(
            value=usd_per_hour,
            unit="usd_per_hour",
            lower=usd_per_hour,
            upper=usd_per_hour,
            confidence=0.95,
            method=(
                f"deterministic: {replica_count} x on-demand rate from "
                f"{cost_profile.profile_id}@{cost_profile.version} "
                f"({on_demand.usd_per_hour.provenance.basis}, as of "
                f"{on_demand.usd_per_hour.provenance.as_of}) -- ILLUSTRATIVE "
                "ONLY: the measured hardware this recommendation is actually "
                "sized from (mock-loopback-cpu-dev, a local-dev-container) "
                "has no real cloud billing; this reuses a real GPU's "
                "example on-demand rate purely to satisfy Contract 7's "
                "required cost field, same convention as reports/cost-model.md (FL-T008)."
            ),
        ),
        "usd_per_successful_request": predicted_quantity(
            value=cost_per_request_usd(usd_per_hour, goodput.value),
            unit="usd_per_successful_request",
            lower=cost_per_request_usd(usd_per_hour, goodput.upper),
            upper=cost_per_request_usd(usd_per_hour, max(goodput.lower, 1e-9)),
            method="usd_per_hour divided by the predicted goodput interval, converted to requests/hour",
        ),
        "usd_per_million_tokens": predicted_quantity(
            value=cost_per_1e6_tokens_usd(usd_per_hour, goodput.value * baseline_mean_output_tokens_per_request),
            unit="usd_per_million_tokens",
            lower=cost_per_1e6_tokens_usd(usd_per_hour, goodput.upper * baseline_mean_output_tokens_per_request),
            upper=cost_per_1e6_tokens_usd(usd_per_hour, max(goodput.lower, 1e-9) * baseline_mean_output_tokens_per_request),
            method=(
                "usd_per_hour divided by predicted output-token throughput "
                "(goodput x mean output tokens/request); OUTPUT-TOKEN BASIS "
                "ONLY -- benchmark-result.schema.json's throughput block has "
                "no total (input+output) token-rate field, a schema-"
                "coverage gap already recorded in reports/cost-model.md "
                "(FL-T008); tokens/request measured from "
                "ib-t010-e2-baseline-1x-sane's own throughput block "
                f"({baseline_mean_output_tokens_per_request:.4f} output tokens/request)"
            ),
        ),
    }

    doc = build_capacity_recommendation(
        recommendation_id=RECOMMENDATION_ID,
        created_at=CREATED_AT,
        producer_version="0.1.0",
        benchmark_result_ids=[baseline_result["result_id"], overload_result["result_id"]],
        workload_ref={"name": overload_workload.name, "version": overload_workload.version},
        slo_ref=baseline_result["goodput"]["slo_ref"],  # reuses the real ref already carried by the baseline result
        cost_profile_ref={"id": cost_profile.profile_id, "version": cost_profile.version},
        hardware_profile_refs=[{"id": fitted["hardware"]["id"]}],
        model_profile_ref={"id": fitted["model"]["id"]},
        demand_forecast={
            "peak_rps": demand_rps,
            "basis": (
                "measured: the real declared offered rate of the ib-t010 E2 "
                "'5x' overload stress-test workload (not a live production "
                "forecast) -- used here as the demand this recommendation "
                "is sized for, per this task's explicit instruction"
            ),
        },
        baseline=(
            f"1 replica of {fitted['engine_config_id']} ({fitted['hardware']['label']}), measured achieving "
            f"{baseline_result['throughput']['requests_per_second']:.3f} rps at "
            f"{baseline_workload.arrival_process['rate_rps']:.4f} rps offered "
            f"(goodput ratio {baseline_result['goodput']['ratio']:.3f}, shed_rate {baseline_result['goodput']['shed_rate']:.3f}) "
            f"-- {baseline_result['result_id']}"
        ),
        change_summary=(
            f"scale out 1 -> {replica_count} replicas of {fitted['engine_config_id']} to serve the "
            f"{demand_rps} rps '5x' overload stress-test rate within this profile's fitted capacity"
        ),
        replica_groups=[
            {
                "hardware_profile_ref": {"id": fitted["hardware"]["id"]},
                "replica_count": replica_count,
                "engine_config": {"engine": {"name": "mock", "version": "dev"}, "flags": {}},
            }
        ],
        goodput=predicted_quantity(
            value=goodput.value,
            unit="requests_per_second",
            lower=goodput.lower,
            upper=goodput.upper,
            method=goodput.method,
        ),
        goodput_at_offered_rps=demand_rps,
        latency=latency,
        cost=cost,
        autoscaling_signal={"source": "gateway", "metric": "inference_queue_depth"},
        autoscaling_thresholds={
            "scale_out": {"comparator": ">", "value": 1, "for_seconds": 60},
            "scale_in": {"comparator": "<", "value": 1, "for_seconds": 300},
        },
        autoscaling_bounds={"min_replicas": 1, "max_replicas": 8},
        autoscaling_notes=(
            "FL-T006 (reports/autoscaling-signals.md) recommends "
            "predicted_goodput_deficit as primary (paired with queue_depth/"
            "in_flight_requests as a fitted-profile-independent fallback), "
            "but predicted_goodput_deficit is fleetlab's own derived "
            "simulation signal, not a metric the gateway emits -- Contract "
            "7 requires a canonical gateway/engine metric name (Contract 2 "
            "vocabulary), so this field names inference_queue_depth "
            "(Contract 2 canonical), FL-T006's recommended fallback. "
            "Thresholds (queue_depth > 1 to scale out, < 1 to scale in) are "
            "a stated, disclosed choice (basis: assumed) reserving 2 of "
            "this gateway config's 3-deep admission queue as headroom "
            "before scaling, not a fitted or measured figure -- no "
            "queue-depth telemetry exists in this program's evidence for "
            "this engine-config. FL-T006's own caveat carries over "
            "unchanged: queue_depth under-reads true overload once "
            "admission control starts shedding rather than queuing, which "
            "this gateway config (admission-sane-v1, queue cap 3) does at "
            "sustained overload."
        ),
        assumptions=[
            "goodput scales linearly with replica count behind even routing -- no cross-replica imbalance penalty is modeled (unlike the serving-contracts example recommendation's assumed 3% penalty): no multi-replica benchmark exists anywhere in this program's evidence to measure or even assume an imbalance figure from (docs/risks.md FL-L1; docs/implementation-notes.md A7)",
            "engine config (gateway-mock-admission-sane-v1, queue cap 3), model (mock-8b), and hardware (mock-loopback-cpu-dev) are held exactly at the pins of ib-t010-e2-baseline-1x-sane and ib-t010-e2-overload-5x-sane -- this is the CPU-only mock backend profiled for loop-mechanics purposes only (FL-T004 scope decision), NOT a claim about any real GPU or CPU serving stack",
            "the 189.0362 rps demand is the E2 '5x' overload workload's own declared offered rate (a stress-test rate), not a measured or forecast production traffic figure",
            "cost figures reuse cost-g5-xlarge-ondemand's real GPU on-demand rate purely to populate Contract 7's required cost field -- the actual measured hardware (a local-dev-container) has no real cloud billing; NOT a real cost claim (same convention as reports/cost-model.md, FL-T008)",
            "the latency prediction is a measured-data bracket (baseline/overload benchmark-results' own pooled percentiles), not a fitted-model-based prediction -- this engine-config's queueing-blowup latency model has status PENDING (no training point below its own fitted capacity exists anywhere in evidence)",
            f"the recommended replica count ({replica_count}) sizes exactly to the stated demand with no N-1 failover margin: at {replica_count} replicas, losing one leaves {n_minus_1_capacity:.3f} rps of capacity against the {demand_rps} rps demand -- a {n_minus_1_deficit:.3f} rps deficit (see sensitivity_notes)",
        ],
        sensitivity_notes=[
            (
                f"the recommended {replica_count}-replica fleet capacity "
                f"({fleet_capacity_rps(replica_count, capacity_rps):.3f} rps, point estimate) "
                f"exceeds the {demand_rps} rps demand by only "
                f"{(fleet_capacity_rps(replica_count, capacity_rps) / demand_rps - 1) * 100:.1f}% -- "
                "this is an exactly-sized recommendation, not a comfortably "
                "provisioned one; a small negative surprise in per-replica "
                "capacity would leave the fleet short"
            ),
            (
                f"N-1 failover: with {replica_count} replicas, a single replica "
                f"failure leaves only {n_minus_1_capacity:.3f} rps against the "
                f"{demand_rps} rps demand -- a {n_minus_1_deficit:.3f} rps deficit "
                f"(headroom_deficit=True per fleetlab.dynamics.headroom's own "
                "arithmetic). If N-1 failover margin at this demand is "
                f"required, provision {replica_count + 1} replicas instead; "
                "this recommendation sizes only to the stated demand, per "
                "this task's explicit instruction"
            ),
            (
                "this profile's own G8 holdout result (reports/holdout-"
                "validation.md §2a) is the dominant source of uncertainty "
                "here (12.6% relative error at this exact operating regime "
                "-- an offered rate far past the single training point), "
                "several times larger than the fit's own statistical stderr "
                "(3.3% relative) -- the re_measurement plan below exists "
                "specifically to resolve which of this profile's two single-"
                "point capacity estimates (33.159 rps baseline-fit vs 37.925 "
                "rps overload-empirical) better predicts real multi-replica behavior"
            ),
            (
                "queue_depth (the chosen autoscaling signal) under-reads true "
                "overload once this gateway config's admission control starts "
                "shedding instead of queuing (FL-T006 caveat, reports/"
                "autoscaling-signals.md §7) -- the baseline run's own 10.1% "
                "shed_rate at 'normal' load shows this config sheds well "
                "before queue_depth would saturate"
            ),
        ],
        re_measurement={
            "workload_ref": {"name": overload_workload.name, "version": overload_workload.version, "seed": overload_workload.seed},
            "single_declared_variable": (
                f"replica_count 1 -> {replica_count} (engine config gateway-mock-admission-sane-v1, "
                "model mock-8b, hardware mock-loopback-cpu-dev, and workload version+seed held at "
                "ib-t010-e2-overload-5x-sane's own pins, per the benchmark comparability rule)"
            ),
            "success_criteria": [
                f"pooled achieved_rps >= {goodput.lower:.3f} (this recommendation's stated goodput lower bound) at {demand_rps} rps offered, evaluated across all {replica_count} replicas",
                "shed_rate at the recommended topology is materially lower than the single-replica baseline's own shed_rate (10.1%, ib-t010-e2-baseline-1x-sane) -- goodput gained is not bought by shedding alone",
                f"e2e_duration_seconds p95 <= {bracket['upper']:.4f}s (this recommendation's stated latency upper bound)",
                (
                    f"if measured achieved_rps at {replica_count} replicas lands nearer "
                    f"{fleet_capacity_rps(replica_count, capacity_rps):.1f} rps (linear-scaling "
                    "prediction from the baseline-fit capacity) or nearer "
                    f"{fleet_capacity_rps(replica_count, 37.92538429901373):.1f} rps (linear-scaling "
                    "from the overload-empirical capacity), this directly answers which of this "
                    "profile's two single-point capacity estimates better predicts multi-replica "
                    "behavior -- closing the open root-cause question in docs/notes/fitting-method.md"
                ),
            ],
        },
        notes=(
            "Consumption-side dry-run validation: fleetlab/emit/dry_run_validate.py "
            "(run as `python3 -m fleetlab.emit.dry_run_validate --recommendation "
            "<this file> --applied-topology <applied.json> --post-change-result "
            "<benchmark-result.json>`) checks replica_count applied, goodput vs "
            "this recommendation's lower bound, and latency vs its upper bound. "
            "STATUS: PENDING-on-RQ-14 -- inferops' runtime environment decision is "
            "not yet made, so no real post-change benchmark-result exists yet to "
            "run this against; recorded as an honest deferral in "
            "docs/implementation-notes.md, not skipped silently. The script is "
            "written and tested now (tests/emit/test_dry_run_validate.py) so it "
            "is ready to run the moment a real one lands."
        ),
    )
    return doc


def main() -> None:
    doc = build_recommendation()
    path = write_recommendation(doc, OUT_PATH)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
