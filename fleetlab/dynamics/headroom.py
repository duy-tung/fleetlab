"""Failover headroom / failure-capacity analysis (FL-T005).

Closed-form (ADR-0001: steady-state/capacity arithmetic stays analytic; the
discrete-event core in `simulator.py` is reserved for genuinely transient
behavior). Composes a fitted per-replica capacity (FL-T004,
`fleetlab.fitting`) with a replica count to answer:

1. **N-1 failure capacity:** what can the fleet still deliver with one fewer
   replica (a crashed pod, a drained node)?
2. **Cold-start headroom (planning-prompt hypothesis 3):** "required
   headroom is set by warm-up time x arrival growth rate, not steady-state
   throughput" — while a replacement replica cold-starts, the fleet runs at
   N-1 capacity; if the offered rate exceeds that, a backlog accumulates for
   the whole cold-start window and must be drained afterward. This module
   computes that backlog and its deterministic drain time (cross-checked
   against `simulator.simulate_queue` in `tests/dynamics/test_headroom.py`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class FailureCapacityReport:
    per_replica_capacity_rps: float
    replica_count: int
    full_fleet_capacity_rps: float
    n_minus_1_capacity_rps: float


def failure_capacity(per_replica_capacity_rps: float, replica_count: int) -> FailureCapacityReport:
    if replica_count < 1:
        raise ValueError("replica_count must be >= 1")
    if per_replica_capacity_rps <= 0:
        raise ValueError("per_replica_capacity_rps must be > 0")
    return FailureCapacityReport(
        per_replica_capacity_rps=per_replica_capacity_rps,
        replica_count=replica_count,
        full_fleet_capacity_rps=per_replica_capacity_rps * replica_count,
        n_minus_1_capacity_rps=per_replica_capacity_rps * max(replica_count - 1, 0),
    )


def required_headroom_rps(peak_offered_rps: float, n_minus_1_capacity_rps: float) -> float:
    """The deficit (>= 0) between peak offered load and what N-1 replicas
    can deliver. Zero means the fleet already tolerates losing one replica
    at this peak load with no cold-start exposure at all."""
    return max(0.0, peak_offered_rps - n_minus_1_capacity_rps)


@dataclass(frozen=True)
class HeadroomScenario:
    peak_offered_rps: float
    n_minus_1_capacity_rps: float
    cold_start_seconds: float
    deficit_rps: float
    backlog_requests: float
    recovered_capacity_rps: float
    drain_time_seconds: Optional[float]
    drain_exceeds_available_time: bool


def evaluate_cold_start_headroom(
    *,
    peak_offered_rps: float,
    n_minus_1_capacity_rps: float,
    cold_start_seconds: float,
    recovered_capacity_rps: float,
    post_recovery_offered_rps: float,
) -> HeadroomScenario:
    """Backlog accumulated while the fleet runs at N-1 capacity during a
    `cold_start_seconds`-long replacement, and the deterministic time to
    drain it once the replacement replica comes online (assuming
    `post_recovery_offered_rps` continues to arrive concurrently — the
    drain rate is `recovered_capacity_rps - post_recovery_offered_rps`,
    exactly the deterministic-single-server-drain arithmetic in
    `tests/dynamics/test_simulator.py`, generalized to a rate deficit).

    `drain_time_seconds` is `None` when `recovered_capacity_rps <=
    post_recovery_offered_rps`: the backlog never drains (an unbounded-queue
    limitation, not silently reported as a finite number).
    """
    deficit = required_headroom_rps(peak_offered_rps, n_minus_1_capacity_rps)
    backlog = deficit * cold_start_seconds

    drain_rate = recovered_capacity_rps - post_recovery_offered_rps
    if backlog <= 0:
        drain_time: Optional[float] = 0.0
        exceeds = False
    elif drain_rate <= 0:
        drain_time = None
        exceeds = True
    else:
        drain_time = backlog / drain_rate
        exceeds = False

    return HeadroomScenario(
        peak_offered_rps=peak_offered_rps,
        n_minus_1_capacity_rps=n_minus_1_capacity_rps,
        cold_start_seconds=cold_start_seconds,
        deficit_rps=deficit,
        backlog_requests=backlog,
        recovered_capacity_rps=recovered_capacity_rps,
        drain_time_seconds=drain_time,
        drain_exceeds_available_time=exceeds,
    )
