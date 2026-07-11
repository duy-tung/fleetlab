"""Regenerates `reports/scenarios/*.json` (FL-T005 deliverable): seeded queue-
growth and cold-start-headroom scenario outputs, each embedding its seed and
input-file digest (docs/observability.md's run-record discipline).

Run: `python3 -m fleetlab.dynamics.build_scenarios`
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from fleetlab.dynamics import simulate_queue
from fleetlab.dynamics.cold_start import MEASURED_COLD_START
from fleetlab.dynamics.headroom import evaluate_cold_start_headroom, failure_capacity
from fleetlab.dynamics.scaling import ASSUMED_SCALING_DELAY
from fleetlab.ingest import load_workload
from fleetlab.models.arrival import arrival_process_from_workload

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "reports" / "scenarios"
BURSTY_WORKLOAD = (
    REPO_ROOT / "tests" / "golden" / "fixtures" / "real" / "workloads" / "bursty.json"
)
FITTED_PROFILE = (
    REPO_ROOT
    / "profiles"
    / "fitted"
    / "mock-loopback-cpu-dev__mock-8b__gateway-mock-admission-sane-v1.json"
)

SEED = 20260711


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_queue_growth_scenario() -> dict:
    workload = load_workload(BURSTY_WORKLOAD)
    proc = arrival_process_from_workload(workload.arrival_process)

    scenarios = {}
    for label, mu in (("provisioned_mu8", 8.0), ("underprovisioned_mu3", 3.0)):
        rng = np.random.default_rng(SEED)
        arrivals = proc.arrival_times_until(rng, duration_seconds=600.0)  # workload's own stop.duration_seconds
        service_times = rng.exponential(scale=1.0 / mu, size=len(arrivals))
        trace = simulate_queue(arrivals, service_times, num_servers=1)
        times, counts = trace.in_system_trace()
        scenarios[label] = {
            "service_rate_rps": mu,
            "n_requests": len(arrivals),
            "max_in_system": trace.max_in_system(),
            "mean_wait_seconds_admitted": trace.mean_wait_seconds(),
            "in_system_at_t300s": trace.in_system_at(300.0),
            "in_system_at_t590s": trace.in_system_at(590.0),
            "stable": mu > (workload.arrival_process["phases"][0]["rate_rps"] * 60
                            + workload.arrival_process["phases"][1]["rate_rps"] * 15) / 75.0,
        }

    return {
        "scenario": "bursty-queue-growth",
        "seed": SEED,
        "input_workload_file": "tests/golden/fixtures/real/workloads/bursty.json",
        "input_workload_sha256": _sha256_file(BURSTY_WORKLOAD),
        "workload_description": workload.description,
        "long_run_average_offered_rps": (
            workload.arrival_process["phases"][0]["rate_rps"] * 60
            + workload.arrival_process["phases"][1]["rate_rps"] * 15
        ) / 75.0,
        "scenarios": scenarios,
        "note": (
            "provisioned_mu8: long-run average offered rate (5.6 rps) < service "
            "rate (8 rps) -- system is stable overall; the burst phase alone "
            "briefly exceeds capacity but the queue drains within each 60s "
            "baseline window (see tests/dynamics/test_simulator.py::"
            "test_burst_decay_back_to_steady_state_after_the_burst_ends). "
            "underprovisioned_mu3: service rate (3 rps) below the long-run "
            "average offered rate (5.6 rps) -- unstable, in-system count "
            "ratchets upward cycle over cycle with no recovery."
        ),
    }


def build_cold_start_headroom_scenario() -> dict:
    fitted = json.loads(FITTED_PROFILE.read_text())
    real_capacity_rps = fitted["capacity_profile"]["capacity_rps"]

    workload = load_workload(BURSTY_WORKLOAD)
    peak_rps = workload.arrival_process["phases"][1]["rate_rps"]  # 20 rps burst

    # (a) real: FL-T004's measured (mock, honestly labeled) capacity, 2 replicas
    real_failure = failure_capacity(real_capacity_rps, replica_count=2)
    real_scenario_warm = evaluate_cold_start_headroom(
        peak_offered_rps=peak_rps,
        n_minus_1_capacity_rps=real_failure.n_minus_1_capacity_rps,
        cold_start_seconds=ASSUMED_SCALING_DELAY.scale_up_seconds,
        recovered_capacity_rps=real_failure.full_fleet_capacity_rps,
        post_recovery_offered_rps=peak_rps,
    )

    # (b) illustrative (assumed per-replica capacity, NOT measured -- chosen
    # below the bursty peak specifically to demonstrate the mechanism):
    illustrative_capacity_rps = 15.0
    illus_failure = failure_capacity(illustrative_capacity_rps, replica_count=2)
    warm_delay = ASSUMED_SCALING_DELAY.scale_up_seconds  # assumed sched + measured warm load
    cold_delay = 10.0 + MEASURED_COLD_START.cold_load_seconds  # assumed sched + measured cold load
    illus_warm = evaluate_cold_start_headroom(
        peak_offered_rps=peak_rps,
        n_minus_1_capacity_rps=illus_failure.n_minus_1_capacity_rps,
        cold_start_seconds=warm_delay,
        recovered_capacity_rps=illus_failure.full_fleet_capacity_rps,
        post_recovery_offered_rps=peak_rps,
    )
    illus_cold = evaluate_cold_start_headroom(
        peak_offered_rps=peak_rps,
        n_minus_1_capacity_rps=illus_failure.n_minus_1_capacity_rps,
        cold_start_seconds=cold_delay,
        recovered_capacity_rps=illus_failure.full_fleet_capacity_rps,
        post_recovery_offered_rps=peak_rps,
    )

    return {
        "scenario": "cold-start-headroom",
        "seed": None,  # closed-form arithmetic, no RNG
        "input_workload_file": "tests/golden/fixtures/real/workloads/bursty.json",
        "input_workload_sha256": _sha256_file(BURSTY_WORKLOAD),
        "input_fitted_profile_file": str(FITTED_PROFILE.relative_to(REPO_ROOT)),
        "input_fitted_profile_sha256": _sha256_file(FITTED_PROFILE),
        "measured_cold_start": {
            "warm_load_seconds": MEASURED_COLD_START.warm_load_seconds,
            "cold_load_seconds": MEASURED_COLD_START.cold_load_seconds,
            "basis": MEASURED_COLD_START.basis,
            "source": MEASURED_COLD_START.source,
        },
        "assumed_scaling_delay": {
            "scale_up_seconds": ASSUMED_SCALING_DELAY.scale_up_seconds,
            "scale_down_seconds": ASSUMED_SCALING_DELAY.scale_down_seconds,
            "basis": ASSUMED_SCALING_DELAY.basis,
        },
        "real_measured_capacity_scenario": {
            "basis": "measured (mock backend, loop-mechanics labeling per FL-T004)",
            "per_replica_capacity_rps": real_capacity_rps,
            "replica_count": 2,
            "n_minus_1_capacity_rps": real_failure.n_minus_1_capacity_rps,
            "bursty_peak_offered_rps": peak_rps,
            "deficit_rps": real_scenario_warm.deficit_rps,
            "finding": (
                "no headroom deficit: N-1 capacity "
                f"({real_failure.n_minus_1_capacity_rps:.2f} rps) already "
                f"exceeds the bursty workload's peak ({peak_rps} rps) -- "
                "losing one of two replicas is not a cold-start risk for "
                "this specific (measured mock capacity, this workload) pairing."
            ),
        },
        "illustrative_assumed_capacity_scenario": {
            "basis": "ASSUMED (illustrative only, chosen below the bursty peak to demonstrate the mechanism -- NOT a measured capacity)",
            "per_replica_capacity_rps": illustrative_capacity_rps,
            "replica_count": 2,
            "n_minus_1_capacity_rps": illus_failure.n_minus_1_capacity_rps,
            "bursty_peak_offered_rps": peak_rps,
            "warm_replacement": {
                "cold_start_seconds": warm_delay,
                "deficit_rps": illus_warm.deficit_rps,
                "backlog_requests": illus_warm.backlog_requests,
                "drain_time_seconds": illus_warm.drain_time_seconds,
            },
            "cold_replacement": {
                "cold_start_seconds": cold_delay,
                "deficit_rps": illus_cold.deficit_rps,
                "backlog_requests": illus_cold.backlog_requests,
                "drain_time_seconds": illus_cold.drain_time_seconds,
            },
            "finding": (
                f"warm vs cold replacement changes the cold-start window by "
                f"{cold_delay / warm_delay:.1f}x ({warm_delay:.1f}s vs "
                f"{cold_delay:.1f}s) with steady-state capacity and offered "
                f"load held fixed -- the resulting backlog and drain time "
                f"scale by the same {cold_delay / warm_delay:.1f}x "
                f"({illus_warm.backlog_requests:.1f} vs "
                f"{illus_cold.backlog_requests:.1f} requests; "
                f"{illus_warm.drain_time_seconds:.1f}s vs "
                f"{illus_cold.drain_time_seconds:.1f}s to drain) -- direct "
                "support for planning-prompt hypothesis 3: cold-start "
                "headroom is set by warm-up time x deficit rate, not "
                "steady-state throughput."
            ),
        },
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, builder in (
        ("bursty-queue-growth", build_queue_growth_scenario),
        ("cold-start-headroom", build_cold_start_headroom_scenario),
    ):
        out_path = OUT_DIR / f"{name}.json"
        out_path.write_text(json.dumps(builder(), indent=2) + "\n")
        print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
