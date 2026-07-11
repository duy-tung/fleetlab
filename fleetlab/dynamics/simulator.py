"""A small, in-repo discrete-event queue simulator (ADR-0001).

`simulate_queue` implements the standard FCFS `G/G/c` simulation algorithm
(e.g. Law & Kelton, *Simulation Modeling and Analysis*): a single FIFO queue
feeds `num_servers` identical servers; the i-th arrival (in arrival-time
order) begins service the moment the *earliest*-freeing server becomes
available (or immediately, if one is already idle) — correct for FCFS
because in a single shared queue, whichever server frees first always takes
the head of the line next. This is implemented with two small binary heaps
(server free-times; outstanding departure-times), not a hand-rolled clock
loop, but it is exactly the same model.

**Admission control / shedding.** `capacity`, if given, bounds the maximum
*total* number of requests in the system (waiting + in service) at the
instant of arrival; an arrival that would exceed it is shed (never enters
service). This is a total-occupancy cap, not a queue-only cap — documented
here because it is a modeling choice, not the only reasonable one (real
gateways sometimes cap queue depth only, leaving in-service concurrency
separately bounded by `max_num_seqs` — fleetlab's simulator folds both into
one number for simplicity; this is recorded, not hidden).

**Determinism.** This function takes no RNG and no wall-clock time — it is a
pure function of `arrivals` and `service_times` (both plain arrays the
caller supplies, typically built by `fleetlab.models.arrival` /  an
explicitly-seeded `numpy.random.Generator` upstream). Same inputs, same
output, always.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np


@dataclass(frozen=True)
class RequestOutcome:
    arrival_time: float
    service_time: float
    admitted: bool
    start_time: Optional[float]
    completion_time: Optional[float]

    @property
    def wait_seconds(self) -> Optional[float]:
        if not self.admitted:
            return None
        return self.start_time - self.arrival_time


@dataclass(frozen=True)
class QueueTrace:
    outcomes: Tuple[RequestOutcome, ...]
    num_servers: int
    capacity: Optional[int]

    @property
    def shed_count(self) -> int:
        return sum(1 for o in self.outcomes if not o.admitted)

    @property
    def shed_rate(self) -> float:
        if not self.outcomes:
            return 0.0
        return self.shed_count / len(self.outcomes)

    @property
    def admitted_outcomes(self) -> Tuple[RequestOutcome, ...]:
        return tuple(o for o in self.outcomes if o.admitted)

    def mean_wait_seconds(self) -> float:
        admitted = self.admitted_outcomes
        if not admitted:
            return 0.0
        return float(np.mean([o.wait_seconds for o in admitted]))

    def in_system_trace(self) -> Tuple[np.ndarray, np.ndarray]:
        """Step-function trace of the number of requests in the system
        (waiting + in service), as `(times, counts)` — `counts[i]` holds
        from `times[i]` (inclusive) until `times[i+1]`. Shed requests never
        contribute an event (they never entered the system)."""
        events: List[Tuple[float, int]] = []
        for o in self.admitted_outcomes:
            events.append((o.arrival_time, 1))
            events.append((o.completion_time, -1))
        if not events:
            return np.array([0.0]), np.array([0])
        # arrivals before departures at the same instant (a request that
        # arrives exactly as another departs briefly overlaps, matching the
        # "in service" semantics of a zero-length departure instant)
        events.sort(key=lambda e: (e[0], -e[1]))
        times = [events[0][0]]
        counts = [0]
        running = 0
        for t, delta in events:
            if t != times[-1]:
                times.append(t)
                counts.append(running)
            running += delta
            counts[-1] = running
        return np.asarray(times), np.asarray(counts)

    def max_in_system(self) -> int:
        _, counts = self.in_system_trace()
        return int(counts.max()) if counts.size else 0

    def in_system_at(self, t: float) -> int:
        times, counts = self.in_system_trace()
        idx = np.searchsorted(times, t, side="right") - 1
        if idx < 0:
            return 0
        return int(counts[idx])


def simulate_queue(
    arrivals: np.ndarray,
    service_times: np.ndarray,
    num_servers: int,
    capacity: Optional[int] = None,
) -> QueueTrace:
    """`service_times[i]` is paired with `arrivals[i]` (the i-th request's
    own service-time draw); both are re-sorted together by arrival time
    internally, so `QueueTrace.outcomes` is in arrival-time order, which may
    differ from the caller's original array order if `arrivals` was not
    already sorted."""
    if num_servers < 1:
        raise ValueError("num_servers must be >= 1")
    if len(arrivals) != len(service_times):
        raise ValueError("arrivals and service_times must be the same length")
    order = np.argsort(arrivals, kind="stable")
    arrivals = np.asarray(arrivals)[order]
    service_times = np.asarray(service_times)[order]

    server_free = [0.0] * num_servers
    heapq.heapify(server_free)
    departures: List[float] = []  # min-heap of outstanding completion times
    in_system = 0

    outcomes: List[RequestOutcome] = []
    for t, s in zip(arrivals, service_times):
        while departures and departures[0] <= t:
            heapq.heappop(departures)
            in_system -= 1

        if capacity is not None and in_system >= capacity:
            outcomes.append(
                RequestOutcome(
                    arrival_time=float(t),
                    service_time=float(s),
                    admitted=False,
                    start_time=None,
                    completion_time=None,
                )
            )
            continue

        earliest_free = heapq.heappop(server_free)
        start = max(float(t), earliest_free)
        completion = start + float(s)
        heapq.heappush(server_free, completion)
        heapq.heappush(departures, completion)
        in_system += 1
        outcomes.append(
            RequestOutcome(
                arrival_time=float(t),
                service_time=float(s),
                admitted=True,
                start_time=start,
                completion_time=completion,
            )
        )

    return QueueTrace(outcomes=tuple(outcomes), num_servers=num_servers, capacity=capacity)
