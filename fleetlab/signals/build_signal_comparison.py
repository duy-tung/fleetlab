"""Regenerates `reports/scenarios/autoscaling-signals.json` (FL-T006
deliverable): seeded G/G/c simulations of three workloads (`chat-short`,
`mixed`, `bursty`) plus one explicitly-labeled illustrative variant
(`bursty-illustrative-severe`), scored across all six candidate autoscaling
signals with one shared threshold-tuning/detection procedure
(`docs/adr/0003-signal-comparison-design.md`).

Run: `python3 -m fleetlab.signals.build_signal_comparison`

**Fairness protocol, applied identically to every signal in every
scenario** (the review focus `docs/tasks.md` FL-T006 names explicitly):
- same simulated system: `num_servers` and `mean_service_time_seconds`
  derived once from the FL-T004 fitted (G8-within-error) profile
  (`fleetlab.signals.ground_truth`), held fixed across all four scenarios;
- same sampling grid (`DT_SECONDS`) and windowed-rate length
  (`WINDOW_SECONDS`, shared by the two windowed signals);
- same threshold-tuning rule (`mean + k*std` over each scenario's own
  quiet calibration window, `THRESHOLD_K` identical for every signal);
- same debounce/hysteresis parameters (`DEBOUNCE_SECONDS`,
  `CLEAR_FRACTION`) for every signal's event detector;
- same scoring: detection lag against the *known* phase schedule (never
  against another signal), flapping count over the same quiet windows.

Only the threshold *value* and the resulting event timings differ per
signal -- exactly the comparison this task asks for.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import numpy as np

from fleetlab.dynamics import simulate_queue
from fleetlab.ingest import load_workload
from fleetlab.models.arrival import PhasedPoissonArrivalProcess, arrival_process_from_workload
from fleetlab.models.length import sample_distribution
from fleetlab.signals.detection import (
    count_events_in_window,
    detect_events,
    first_detection_lag_seconds,
    true_overload_windows,
    tune_threshold,
)
from fleetlab.signals.ground_truth import load_ground_truth_system
from fleetlab.signals.series import (
    in_flight_series,
    predicted_goodput_deficit_series,
    queue_depth_series,
    token_arrival_rate_series,
    utilization_series,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "reports" / "scenarios"
GOLDEN_WORKLOADS = REPO_ROOT / "tests" / "golden" / "fixtures" / "real" / "workloads"
VENDOR_WORKLOADS = (
    REPO_ROOT / "vendor" / "serving-contracts-v0.2.0" / "examples" / "workloads"
)

SEED = 20260711
DT_SECONDS = 1.0
WINDOW_SECONDS = 10.0
DEBOUNCE_SECONDS = 5.0
THRESHOLD_K = 3.0
CLEAR_FRACTION = 0.7
DETECTION_HORIZON_SECONDS = 30.0
ILLUSTRATIVE_BURST_MULTIPLIER = 1.6  # see bursty-illustrative-severe scenario docstring below

SIGNAL_NAMES = (
    "cpu_utilization",
    "gpu_utilization",
    "queue_depth",
    "in_flight_requests",
    "token_arrival_rate",
    "predicted_goodput_deficit",
)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class ScenarioSpec:
    name: str
    basis: str  # "measured" (real workload files) | "assumed" (illustrative burst amplification)
    arrival_process: object  # has .arrival_times_until(rng, duration_seconds)
    duration_seconds: float
    input_dist: dict
    output_dist: dict
    calibration_window: Tuple[float, float]
    phases: List[Tuple[float, float, float]]  # (start, end, declared_rate_rps), covers [0, duration)
    quiet_windows: List[Tuple[float, float]]
    source_workload_file: Optional[str]
    source_workload_sha256: Optional[str]
    note: str


def _expand_cycle(cycle: Sequence[Tuple[float, float]], duration_seconds: float) -> List[Tuple[float, float, float]]:
    """Repeat a `(phase_duration, rate_rps)` cycle to cover `[0,
    duration_seconds)`, returning `(start, end, rate)` triples."""
    phases: List[Tuple[float, float, float]] = []
    t = 0.0
    while t < duration_seconds:
        for phase_duration, rate in cycle:
            start = t
            end = min(t + phase_duration, duration_seconds)
            phases.append((start, end, rate))
            t = end
            if t >= duration_seconds:
                break
    return phases


def _load_workload_spec(path: Path, calibration_window: Tuple[float, float], quiet_windows, note: str) -> ScenarioSpec:
    workload = load_workload(path)
    proc = arrival_process_from_workload(workload.arrival_process)
    duration = float(workload.stop["duration_seconds"])
    arrival = workload.arrival_process
    if "phases" in arrival:
        cycle = [(p["duration_seconds"], p["rate_rps"]) for p in arrival["phases"]]
        phases = _expand_cycle(cycle, duration)
    else:
        phases = [(0.0, duration, float(arrival["rate_rps"]))]
    return ScenarioSpec(
        name=workload.name,
        basis="measured",
        arrival_process=proc,
        duration_seconds=duration,
        input_dist=workload.input_length_distribution,
        output_dist=workload.output_length_distribution,
        calibration_window=calibration_window,
        phases=phases,
        quiet_windows=quiet_windows,
        source_workload_file=str(path.relative_to(REPO_ROOT)) if REPO_ROOT in path.parents else str(path),
        source_workload_sha256=_sha256_file(path),
        note=note,
    )


def _build_chat_short_spec() -> ScenarioSpec:
    return _load_workload_spec(
        GOLDEN_WORKLOADS / "chat-short.json",
        calibration_window=(0.0, 200.0),
        quiet_windows=[(200.0, 600.0)],
        note="Steady 8 rps for the full 600s run -- the 'must stay quiet under sustained load' baseline.",
    )


def _build_mixed_spec() -> ScenarioSpec:
    return _load_workload_spec(
        VENDOR_WORKLOADS / "mixed.json",
        calibration_window=(0.0, 200.0),
        quiet_windows=[(200.0, 1200.0)],
        note=(
            "Steady 5 rps, mixture length distribution (70% chat-like / 30% "
            "RAG-like) -- a second 'must stay quiet' baseline with more "
            "per-request token heterogeneity than chat-short."
        ),
    )


def _bursty_quiet_windows(phases: Sequence[Tuple[float, float, float]], baseline_rate: float, exclude_before: float):
    return [(s, e) for s, e, r in phases if r == baseline_rate and s >= exclude_before]


def _build_bursty_real_spec() -> ScenarioSpec:
    workload = load_workload(GOLDEN_WORKLOADS / "bursty.json")
    proc = arrival_process_from_workload(workload.arrival_process)
    duration = float(workload.stop["duration_seconds"])
    cycle = [(p["duration_seconds"], p["rate_rps"]) for p in workload.arrival_process["phases"]]
    baseline_duration = cycle[0][0]  # first phase's duration -- the one full quiet phase before any burst
    phases = _expand_cycle(cycle, duration)
    quiet = _bursty_quiet_windows(phases, baseline_rate=2.0, exclude_before=baseline_duration)
    return ScenarioSpec(
        name="bursty",
        basis="measured",
        arrival_process=proc,
        duration_seconds=duration,
        input_dist=workload.input_length_distribution,
        output_dist=workload.output_length_distribution,
        calibration_window=(0.0, baseline_duration),
        phases=phases,
        quiet_windows=quiet,
        source_workload_file=str((GOLDEN_WORKLOADS / "bursty.json").relative_to(REPO_ROOT)),
        source_workload_sha256=_sha256_file(GOLDEN_WORKLOADS / "bursty.json"),
        note=(
            "Real workload file, unmodified (IB-T003 canonical bursty, "
            "60s@2rps + 15s@20rps repeating every 75s for 8 cycles over "
            "600s). The burst phase (20 rps) sits BELOW the fitted 2-slot "
            "ground-truth capacity (26.16 rps) -- 76.5% utilization, a "
            "near-saturation stress test rather than a hard capacity "
            "breach. See bursty-illustrative-severe for a genuine overload "
            "variant."
        ),
    )


def _build_bursty_illustrative_severe_spec(real_bursty: ScenarioSpec) -> ScenarioSpec:
    """NOT from the measured corpus -- an illustrative amplification of the
    real `bursty` workload's own cycle (60s@2rps + 15s@20rps, repeating):
    every phase whose rate exceeds the cycle's baseline rate is multiplied
    by `ILLUSTRATIVE_BURST_MULTIPLIER` (20 -> 32 rps); the baseline phase,
    every phase duration, and every length/cancellation/prefix parameter are
    the real workload's own, re-derived programmatically from the same file
    (not hand-copied), so this scenario cannot silently drift from the real
    cycle it is amplifying. Chosen so the burst phase clearly exceeds the
    fitted ground-truth capacity (26.16 rps) and a genuine hard-overload
    detection-lag comparison becomes possible. This mirrors the precedent
    already set by `fleetlab/dynamics/build_scenarios.py`'s illustrative
    capacity (15.0 rps, explicitly labeled ASSUMED) for the same reason: the
    real corpus alone does not contain a scenario where offered load exceeds
    fitted capacity under this system's concurrency, and demonstrating a
    signal's detection-lag behavior under true overload needs one.
    """
    real_workload = load_workload(GOLDEN_WORKLOADS / "bursty.json")
    raw_cycle = [
        (p["duration_seconds"], p["rate_rps"]) for p in real_workload.arrival_process["phases"]
    ]
    baseline_rate = min(rate for _duration, rate in raw_cycle)
    cycle = [
        (duration, rate if rate <= baseline_rate else rate * ILLUSTRATIVE_BURST_MULTIPLIER)
        for duration, rate in raw_cycle
    ]
    duration = real_bursty.duration_seconds
    phases = _expand_cycle(cycle, duration)
    quiet = _bursty_quiet_windows(phases, baseline_rate=baseline_rate, exclude_before=cycle[0][0])
    proc = PhasedPoissonArrivalProcess(
        phases=tuple((d, r) for d, r in cycle), repeat_phases=True
    )
    return ScenarioSpec(
        name="bursty-illustrative-severe",
        basis="assumed",
        arrival_process=proc,
        duration_seconds=duration,
        input_dist=real_bursty.input_dist,
        output_dist=real_bursty.output_dist,
        calibration_window=(0.0, cycle[0][0]),
        phases=phases,
        quiet_windows=quiet,
        source_workload_file=real_bursty.source_workload_file,
        source_workload_sha256=real_bursty.source_workload_sha256,
        note=(
            f"ASSUMED/illustrative: the burst phase amplified "
            f"{ILLUSTRATIVE_BURST_MULTIPLIER}x (20 -> "
            f"{20.0 * ILLUSTRATIVE_BURST_MULTIPLIER:.1f} rps) relative to the "
            "real bursty.json burst rate (20 rps) so it exceeds the fitted "
            "ground-truth capacity (26.16 rps) -- everything else (baseline "
            "rate, phase durations, length/cancellation distributions, seed) "
            "is the real workload's own, re-derived from the same file. NOT "
            "a measured scenario; demonstrates the detection-lag mechanism "
            "under genuine overload, which the real bursty workload does "
            "not reach at this system's fitted capacity."
        ),
    )


def _pooled_stats_by_rate(query_times: np.ndarray, values: np.ndarray, phases) -> dict:
    buckets = defaultdict(list)
    for start, end, rate in phases:
        mask = (query_times >= start) & (query_times < end)
        buckets[rate].extend(values[mask].tolist())
    out = {}
    for rate, vals in buckets.items():
        arr = np.asarray(vals)
        out[str(rate)] = {
            "n_samples": len(arr),
            "mean": float(arr.mean()),
            "p95": float(np.quantile(arr, 0.95)),
            "max": float(arr.max()),
        }
    return out


def run_scenario(spec: ScenarioSpec, num_servers: int, mean_service_time_seconds: float, capacity_rps: float) -> dict:
    rng = np.random.default_rng(SEED)  # single seeded RNG, fixed draw order (module docstring)
    arrivals = spec.arrival_process.arrival_times_until(rng, spec.duration_seconds)
    service_times = rng.exponential(scale=mean_service_time_seconds, size=len(arrivals))
    trace = simulate_queue(arrivals, service_times, num_servers=num_servers)

    order = np.argsort(arrivals, kind="stable")
    input_tokens = sample_distribution(spec.input_dist, rng, len(arrivals))
    output_tokens = sample_distribution(spec.output_dist, rng, len(arrivals))
    tokens_aligned = (input_tokens + output_tokens)[order]

    query_times = np.arange(0.0, spec.duration_seconds, DT_SECONDS)
    util = utilization_series(trace, num_servers, query_times)
    series = {
        "cpu_utilization": util,
        "gpu_utilization": util,  # identical proxy in this simulation; see module docstrings
        "queue_depth": queue_depth_series(trace, query_times),
        "in_flight_requests": in_flight_series(trace, query_times),
        "token_arrival_rate": token_arrival_rate_series(trace, tokens_aligned, query_times, WINDOW_SECONDS),
        "predicted_goodput_deficit": predicted_goodput_deficit_series(
            trace, capacity_rps, query_times, WINDOW_SECONDS
        ),
    }

    calib_lo, calib_hi = spec.calibration_window
    calib_mask = (query_times >= calib_lo) & (query_times < calib_hi)
    overload_windows = true_overload_windows(spec.phases, capacity_rps)

    signal_reports = {}
    for name, values in series.items():
        tuning = tune_threshold(values[calib_mask], k=THRESHOLD_K)
        events = detect_events(
            query_times, values, tuning.threshold, DT_SECONDS, DEBOUNCE_SECONDS, CLEAR_FRACTION
        )
        flapping = sum(count_events_in_window(events, s, e) for s, e in spec.quiet_windows)
        lags = [
            first_detection_lag_seconds(events, start, DETECTION_HORIZON_SECONDS)
            for start, _end in overload_windows
        ]
        signal_reports[name] = {
            "threshold_tuning": {
                "baseline_mean": tuning.baseline_mean,
                "baseline_std": tuning.baseline_std,
                "k": tuning.k,
                "threshold": tuning.threshold,
                "degenerate_baseline": tuning.degenerate_baseline,
            },
            "n_events": len(events),
            "events": [
                {"trigger_time": e.trigger_time, "clear_time": e.clear_time} for e in events
            ],
            "flapping_count_in_quiet_windows": flapping,
            "n_quiet_samples_seconds": sum(e - s for s, e in spec.quiet_windows),
            "true_overload_windows": [{"start": s, "end": e} for s, e in overload_windows],
            "detection_lags_seconds": lags,
            "detection_misses": sum(1 for lag in lags if lag is None),
            "stats_by_declared_rate": _pooled_stats_by_rate(query_times, values, spec.phases),
        }

    return {
        "scenario": spec.name,
        "basis": spec.basis,
        "note": spec.note,
        "seed": SEED,
        "n_requests": int(len(arrivals)),
        "duration_seconds": spec.duration_seconds,
        "calibration_window": list(spec.calibration_window),
        "source_workload_file": spec.source_workload_file,
        "source_workload_sha256": spec.source_workload_sha256,
        "signals": signal_reports,
    }


def build_report() -> dict:
    gt = load_ground_truth_system()

    chat_short = _build_chat_short_spec()
    mixed = _build_mixed_spec()
    bursty_real = _build_bursty_real_spec()
    bursty_severe = _build_bursty_illustrative_severe_spec(bursty_real)

    scenarios = [
        run_scenario(spec, gt.num_servers, gt.mean_service_time_seconds, gt.capacity_rps)
        for spec in (chat_short, mixed, bursty_real, bursty_severe)
    ]

    return {
        "generated_by": "python3 -m fleetlab.signals.build_signal_comparison",
        "fairness_protocol": {
            "dt_seconds": DT_SECONDS,
            "window_seconds": WINDOW_SECONDS,
            "debounce_seconds": DEBOUNCE_SECONDS,
            "threshold_k": THRESHOLD_K,
            "clear_fraction": CLEAR_FRACTION,
            "detection_horizon_seconds": DETECTION_HORIZON_SECONDS,
            "note": (
                "Every parameter above is identical across all six signals "
                "and all four scenarios; only the tuned threshold VALUE "
                "differs per signal, from that signal's own calibration-"
                "window statistics. See docs/adr/0003-signal-comparison-design.md."
            ),
        },
        "ground_truth_system": {
            "profile_id": gt.profile_id,
            "profile_path": str(gt.profile_path.relative_to(REPO_ROOT)),
            "profile_sha256": _sha256_file(gt.profile_path),
            "capacity_rps": gt.capacity_rps,
            "capacity_rps_stderr": gt.capacity_rps_stderr,
            "num_servers": gt.num_servers,
            "mean_service_time_seconds": gt.mean_service_time_seconds,
            "basis": gt.basis,
            "concurrency_cap_note": gt.concurrency_cap_note,
            "service_time_derivation": (
                "mean_service_time_seconds = num_servers / capacity_rps "
                "(the fitted throughput ceiling under the disclosed "
                "concurrency cap, NOT the fitted l0_seconds latency "
                "parameter -- see fleetlab/signals/ground_truth.py docstring)."
            ),
        },
        "scenarios": scenarios,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report = build_report()
    out_path = OUT_DIR / "autoscaling-signals.json"
    out_path.write_text(json.dumps(report, indent=2) + "\n")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
