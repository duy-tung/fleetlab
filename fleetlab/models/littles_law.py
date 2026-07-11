"""Little's law: L = lambda * W.

Applied to in-flight requests, queue depth, and concurrency views of the
same trace (docs/architecture.md, component 2): L is the time-average number
of requests present in whichever subsystem is being measured (server,
queue, ...), lambda is the throughput of completions from that subsystem,
and W is the mean time a request spends in it. The identity is a standard
queueing-theory result (holds for any stationary, ergodic system without
further distributional assumptions) — fleetlab does not re-derive it here,
only applies it and checks the identity holds on real traces.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, List, Optional, Tuple


def concurrency(rate_rps: float, mean_latency_seconds: float) -> float:
    """L = lambda * W."""
    return rate_rps * mean_latency_seconds


def arrival_rate_rps(concurrency_l: float, mean_latency_seconds: float) -> float:
    """lambda = L / W."""
    if mean_latency_seconds <= 0:
        raise ValueError("mean_latency_seconds must be > 0")
    return concurrency_l / mean_latency_seconds


def latency_seconds(concurrency_l: float, rate_rps: float) -> float:
    """W = L / lambda."""
    if rate_rps <= 0:
        raise ValueError("rate_rps must be > 0")
    return concurrency_l / rate_rps


def _parse_ts(value: str) -> float:
    """Contract 3 timestamps are RFC 3339 ('...Z' suffix); Python 3.11's
    `datetime.fromisoformat` accepts the 'Z' form directly."""
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def empirical_time_average_concurrency(
    intervals: Iterable[Tuple[float, float]],
) -> float:
    """L measured directly from a trace: the time-average count of
    simultaneously in-flight requests over the observation window, computed
    by a sweep-line integral (each interval contributes its overlap with the
    window; the window is [min(start), max(end)] over all intervals).
    """
    intervals = list(intervals)
    if not intervals:
        raise ValueError("no intervals given")
    events: List[Tuple[float, int]] = []
    for start, end in intervals:
        if end < start:
            raise ValueError(f"interval end {end} precedes start {start}")
        events.append((start, 1))
        events.append((end, -1))
    events.sort(key=lambda e: (e[0], -e[1]))  # process +1 before -1 at ties

    window_start = min(s for s, _ in intervals)
    window_end = max(e for _, e in intervals)
    duration = window_end - window_start
    if duration <= 0:
        raise ValueError("observation window has zero duration")

    area = 0.0
    count = 0
    prev_t = window_start
    for t, delta in events:
        area += count * (t - prev_t)
        count += delta
        prev_t = t
    return area / duration


def empirical_throughput_rps(intervals: Iterable[Tuple[float, float]]) -> float:
    """lambda measured directly: completions per second over the same
    observation window used by `empirical_time_average_concurrency`."""
    intervals = list(intervals)
    if not intervals:
        raise ValueError("no intervals given")
    window_start = min(s for s, _ in intervals)
    window_end = max(e for _, e in intervals)
    duration = window_end - window_start
    if duration <= 0:
        raise ValueError("observation window has zero duration")
    return len(intervals) / duration


def empirical_mean_sojourn_seconds(intervals: Iterable[Tuple[float, float]]) -> float:
    """W measured directly: mean (end - start) across all intervals."""
    intervals = list(intervals)
    if not intervals:
        raise ValueError("no intervals given")
    return sum(end - start for start, end in intervals) / len(intervals)


@dataclass(frozen=True)
class LittlesLawCheck:
    l_measured: float
    lambda_measured: float
    w_measured: float
    l_predicted: float  # lambda_measured * w_measured
    relative_error: float
    within_tolerance: bool


def check_littles_law(
    intervals: Iterable[Tuple[float, float]], tolerance: float = 0.05
) -> LittlesLawCheck:
    """Compare the directly measured time-average concurrency L against the
    L predicted from the same trace's measured throughput and mean sojourn
    time (lambda * W) — Little's law applied to one trace three ways
    (in-flight count / throughput / latency), as docs/testing.md requires.
    """
    intervals = list(intervals)
    l_measured = empirical_time_average_concurrency(intervals)
    lam = empirical_throughput_rps(intervals)
    w = empirical_mean_sojourn_seconds(intervals)
    l_predicted = lam * w
    relative_error = abs(l_measured - l_predicted) / l_measured if l_measured else float("inf")
    return LittlesLawCheck(
        l_measured=l_measured,
        lambda_measured=lam,
        w_measured=w,
        l_predicted=l_predicted,
        relative_error=relative_error,
        within_tolerance=relative_error <= tolerance,
    )


def intervals_from_raw_events(
    events, start_field: str = "scheduled_send_ts", end_field: str = "end_ts"
) -> List[Tuple[float, float]]:
    """Build (start, end) second-epoch intervals from a list of
    `fleetlab.ingest.RawEvent`, for `check_littles_law`. Only events that
    actually occupied the system (not shed pre-admission) are included by
    default; callers wanting queue-depth-only or a different subsystem view
    should build their own interval list from the raw fields instead.
    """
    out = []
    for e in events:
        if e.shed:
            continue
        start = getattr(e, start_field)
        end = getattr(e, end_field)
        out.append((_parse_ts(start), _parse_ts(end)))
    return out
