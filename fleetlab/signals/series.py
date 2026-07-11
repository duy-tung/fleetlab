"""Time-sampled signal series computed from a `fleetlab.dynamics.QueueTrace`
(FL-T006). Six candidate autoscaling signals, each a pure function of a
completed simulation trace plus the ground-truth system parameters:

- `cpu_utilization` / `gpu_utilization` -- **the same proxy in this
  simulation** (fraction of concurrency slots busy at time t): fleetlab's
  corpus is CPU-only (mock backend, no real GPU) and carries no separate
  CPU-vs-GPU occupancy telemetry, so there is no mechanistic way to make
  these two signals differ here. That absence of differentiation is itself
  recorded honestly in `reports/autoscaling-signals.md`, not papered over by
  inventing two different formulas.
- `queue_depth` -- requests admitted but not yet in service (waiting only).
- `in_flight_requests` -- requests admitted and not yet complete (waiting +
  in service) -- Contract 2's `inference_requests_in_flight`, distinct from
  `queue_depth` (`inference_queue_depth`) by definition.
- `token_arrival_rate` -- trailing-window arrival-side token rate (weighted
  by each request's input+output token count), independent of admission.
- `predicted_goodput_deficit` -- trailing-window offered-request-rate
  estimate minus the FL-T004 fitted `capacity_rps` (ground truth), clamped
  at zero.

All windowed computations (`token_arrival_rate`, `predicted_goodput_deficit`)
use the *same* trailing-window length, passed explicitly -- part of the
fairness protocol (`docs/adr/0003-signal-comparison-design.md`): the window
is a shared simulation parameter, not tuned per signal.
"""

from __future__ import annotations

from typing import List, Sequence, Tuple

import numpy as np

from fleetlab.dynamics import QueueTrace


def _step_series(events: List[Tuple[float, int]]) -> Tuple[np.ndarray, np.ndarray]:
    """Build a step function from `(time, delta)` events -- identical
    convention to `QueueTrace.in_system_trace` (arrivals/starts before
    departures/completions at a tied instant, via the `(t, -delta)` sort
    key), generalized to arbitrary event streams (queue-only, service-only).
    """
    if not events:
        return np.array([0.0]), np.array([0.0])
    events = sorted(events, key=lambda e: (e[0], -e[1]))
    times = [events[0][0]]
    counts = [0.0]
    running = 0.0
    for t, delta in events:
        if t != times[-1]:
            times.append(t)
            counts.append(running)
        running += delta
        counts[-1] = running
    return np.asarray(times), np.asarray(counts)


def _sample_step_at(times: np.ndarray, counts: np.ndarray, query_times: np.ndarray) -> np.ndarray:
    idx = np.searchsorted(times, query_times, side="right") - 1
    out = np.zeros(len(query_times))
    valid = idx >= 0
    out[valid] = counts[idx[valid]]
    return out


def in_service_count_series(trace: QueueTrace, query_times: np.ndarray) -> np.ndarray:
    """Number of requests actively occupying a concurrency slot at each of
    `query_times` (started, not yet completed)."""
    events: List[Tuple[float, int]] = []
    for o in trace.admitted_outcomes:
        events.append((o.start_time, 1))
        events.append((o.completion_time, -1))
    times, counts = _step_series(events)
    return _sample_step_at(times, counts, query_times)


def queue_depth_series(trace: QueueTrace, query_times: np.ndarray) -> np.ndarray:
    """Number of requests admitted but still waiting (not yet in service) at
    each of `query_times` -- Contract 2's `inference_queue_depth`."""
    events: List[Tuple[float, int]] = []
    for o in trace.admitted_outcomes:
        events.append((o.arrival_time, 1))
        events.append((o.start_time, -1))
    times, counts = _step_series(events)
    return _sample_step_at(times, counts, query_times)


def in_flight_series(trace: QueueTrace, query_times: np.ndarray) -> np.ndarray:
    """Number of requests admitted and not yet complete (waiting + in
    service) at each of `query_times` -- Contract 2's
    `inference_requests_in_flight`."""
    times, counts = trace.in_system_trace()
    return _sample_step_at(times, counts.astype(float), query_times)


def utilization_series(trace: QueueTrace, num_servers: int, query_times: np.ndarray) -> np.ndarray:
    """The shared cpu/gpu-utilization proxy: fraction of concurrency slots
    busy (`in_service_count / num_servers`), clamped to [0, 1]."""
    busy = in_service_count_series(trace, query_times)
    return np.clip(busy / num_servers, 0.0, 1.0)


def _windowed_rate_series(
    event_times: np.ndarray,
    weights: "np.ndarray | None",
    query_times: np.ndarray,
    window_seconds: float,
) -> np.ndarray:
    if len(event_times) == 0:
        return np.zeros(len(query_times))
    order = np.argsort(event_times)
    times_sorted = np.asarray(event_times)[order]
    w = np.ones(len(times_sorted)) if weights is None else np.asarray(weights)[order]
    cumsum = np.concatenate([[0.0], np.cumsum(w)])
    hi = np.searchsorted(times_sorted, query_times, side="right")
    lo = np.searchsorted(times_sorted, query_times - window_seconds, side="right")
    return (cumsum[hi] - cumsum[lo]) / window_seconds


def offered_request_rate_series(
    trace: QueueTrace, query_times: np.ndarray, window_seconds: float
) -> np.ndarray:
    """Trailing-window arrival-side request rate (rps) -- ALL arrivals,
    admitted or not (nothing is shed in this task's scenarios, since none
    pass `capacity=` to `simulate_queue`, but the definition is arrival-side
    by design, matching what a gateway would see before any admission
    decision)."""
    arrival_times = np.array([o.arrival_time for o in trace.outcomes])
    return _windowed_rate_series(arrival_times, None, query_times, window_seconds)


def token_arrival_rate_series(
    trace: QueueTrace,
    tokens_per_request: Sequence[float],
    query_times: np.ndarray,
    window_seconds: float,
) -> np.ndarray:
    """Trailing-window token arrival rate (tokens/s), weighting each arrival
    by `tokens_per_request[i]` (must be aligned 1:1 with `trace.outcomes`,
    i.e. in arrival-time order -- see `fleetlab/signals/build_signal_
    comparison.py` for how the caller keeps this alignment)."""
    if len(tokens_per_request) != len(trace.outcomes):
        raise ValueError(
            f"tokens_per_request has {len(tokens_per_request)} entries but "
            f"the trace has {len(trace.outcomes)} outcomes -- must be "
            "aligned 1:1 in arrival-time order"
        )
    arrival_times = np.array([o.arrival_time for o in trace.outcomes])
    return _windowed_rate_series(arrival_times, np.asarray(tokens_per_request), query_times, window_seconds)


def predicted_goodput_deficit_series(
    trace: QueueTrace,
    capacity_rps: float,
    query_times: np.ndarray,
    window_seconds: float,
) -> np.ndarray:
    """`max(0, offered_rate_hat(t) - capacity_rps)` -- the FL-T004 fitted
    capacity is used as ground truth (not re-estimated), exactly the way a
    real deployment would consult a previously-fitted capacity profile."""
    offered = offered_request_rate_series(trace, query_times, window_seconds)
    return np.maximum(0.0, offered - capacity_rps)
