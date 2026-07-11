"""Threshold tuning + event detection, applied **identically** to every
signal (FL-T006's fairness requirement -- `docs/adr/0003-signal-comparison-
design.md`): the same tuning rule, the same debounce/hysteresis parameters,
the same scoring procedure, run once per signal per scenario. Only the
threshold *value* differs per signal (it is fit from that signal's own
baseline-window statistics); the *procedure* and its parameters (`k`,
`debounce_seconds`, `clear_fraction`) are shared constants applied to all
six signals in every scenario.

Detection lag and flapping are scored against **ground truth defined
independently of any signal**: the known phase schedule of the workload
(exact burst start/end times, exact declared rate per phase) is the
literal construction of the simulation, not an estimate -- so scoring one
signal's trigger time against it is not circular.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import numpy as np


@dataclass(frozen=True)
class ThresholdTuning:
    baseline_mean: float
    baseline_std: float
    k: float
    threshold: float
    degenerate_baseline: bool  # True if baseline_std was floored (near-zero variance)


def tune_threshold(baseline_values: np.ndarray, k: float = 3.0, min_std: float = 1e-9) -> ThresholdTuning:
    """`threshold = mean + k * std` over a caller-supplied baseline segment.

    If the baseline has (near-)zero variance -- e.g. `queue_depth` reads
    exactly 0 throughout an uncongested baseline -- `std` is floored at
    `min_std` rather than left at 0 (a 0 threshold would fire on the very
    first nonzero reading, which is not a meaningful "3-sigma" test); the
    floor is recorded via `degenerate_baseline=True` rather than hidden.
    """
    mean = float(np.mean(baseline_values))
    std = float(np.std(baseline_values, ddof=0))
    degenerate = std < min_std
    if degenerate:
        std = min_std
    return ThresholdTuning(
        baseline_mean=mean, baseline_std=std, k=k, threshold=mean + k * std, degenerate_baseline=degenerate
    )


@dataclass(frozen=True)
class TriggerEvent:
    trigger_time: float
    clear_time: Optional[float]  # None if still triggered at the end of the series


def detect_events(
    query_times: np.ndarray,
    values: np.ndarray,
    threshold: float,
    dt: float,
    debounce_seconds: float,
    clear_fraction: float = 0.7,
) -> List[TriggerEvent]:
    """Debounced, hysteresis-banded threshold crossing detector.

    A signal must read `>= threshold` for `debounce_seconds` continuously
    to fire (guards against single-sample noise spikes counting as a
    detection); once fired, it must read `<= threshold * clear_fraction`
    for `debounce_seconds` continuously to clear (the hysteresis band
    stops a signal oscillating right at `threshold` from flapping). Both
    parameters are identical across every signal and scenario in this task.

    `trigger_time`/`clear_time` are the instant the debounce condition is
    **confirmed** (i.e. the `debounce_samples`-th continuously-qualifying
    sample), not the back-dated onset of the qualifying run -- this is the
    realistic decision instant (an autoscaler cannot know a run will last
    `debounce_seconds` until it has actually lasted that long), so the
    reported detection lag legitimately includes the debounce delay itself,
    applied identically to every signal.
    """
    if len(query_times) != len(values):
        raise ValueError("query_times and values must be the same length")
    debounce_samples = max(1, round(debounce_seconds / dt))

    events: List[TriggerEvent] = []
    triggered = False
    run_len = 0
    trigger_idx: Optional[int] = None

    for i, v in enumerate(values):
        if not triggered:
            run_len = run_len + 1 if v >= threshold else 0
            if run_len >= debounce_samples:
                trigger_idx = i
                triggered = True
                run_len = 0
        else:
            run_len = run_len + 1 if v <= threshold * clear_fraction else 0
            if run_len >= debounce_samples:
                clear_idx = i
                events.append(
                    TriggerEvent(
                        trigger_time=float(query_times[trigger_idx]),
                        clear_time=float(query_times[clear_idx]),
                    )
                )
                triggered = False
                run_len = 0
                trigger_idx = None

    if triggered and trigger_idx is not None:
        events.append(TriggerEvent(trigger_time=float(query_times[trigger_idx]), clear_time=None))
    return events


def true_overload_windows(
    phases: Sequence[Tuple[float, float, float]], capacity_rps: float
) -> List[Tuple[float, float]]:
    """`phases` is `(start_time, end_time, declared_rate_rps)` triples
    covering the whole scenario (the known, exact phase schedule -- ground
    truth, not an estimate). Returns the `(start, end)` sub-intervals whose
    declared rate exceeds the ground-truth `capacity_rps` -- i.e. where the
    system is *actually*, not just approximately, overloaded."""
    return [(start, end) for start, end, rate in phases if rate > capacity_rps]


def first_detection_lag_seconds(
    events: Sequence[TriggerEvent], true_onset_seconds: float, horizon_seconds: float
) -> Optional[float]:
    """Time from `true_onset_seconds` to the first trigger at or after it,
    within `horizon_seconds`. `None` means the signal never fired within the
    horizon -- a **missed detection**, reported as such, never silently
    treated as "detected at infinity"."""
    candidates = [
        e.trigger_time - true_onset_seconds
        for e in events
        if 0 <= e.trigger_time - true_onset_seconds <= horizon_seconds
    ]
    return min(candidates) if candidates else None


def count_events_in_window(events: Sequence[TriggerEvent], start: float, end: float) -> int:
    """Number of triggers whose `trigger_time` falls in `[start, end)` --
    used to count false-positive/flapping triggers during a designated
    quiet window."""
    return sum(1 for e in events if start <= e.trigger_time < end)
