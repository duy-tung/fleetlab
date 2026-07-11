"""Arrival process models, parameterized from `workload.schema.json`.

fleetlab supports exactly the two arrival-process shapes the workload schema
defines (docs/architecture.md, component 2): open-loop Poisson (single-rate
or piecewise-constant "phases") and closed-loop (concurrency-driven).

Derivation (open-loop Poisson): inter-arrival times of a homogeneous Poisson
process of rate `lambda` are i.i.d. Exponential(lambda) — arrival epochs are
the cumulative sum. This is the standard result used throughout queueing
theory (e.g. Kleinrock); fleetlab does not re-derive it, only implements it
against an explicitly passed seeded `numpy.random.Generator`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, Union

import numpy as np


@dataclass(frozen=True)
class PoissonArrivalProcess:
    """Single-rate open-loop Poisson arrivals."""

    rate_rps: float

    def __post_init__(self) -> None:
        if self.rate_rps <= 0:
            raise ValueError("rate_rps must be > 0")

    def mean_interarrival_seconds(self) -> float:
        return 1.0 / self.rate_rps

    def interarrival_times(self, rng: np.random.Generator, n: int) -> np.ndarray:
        """n i.i.d. Exponential(rate_rps) inter-arrival times, in seconds."""
        return rng.exponential(scale=1.0 / self.rate_rps, size=n)

    def arrival_times(self, rng: np.random.Generator, n: int) -> np.ndarray:
        """n arrival epochs (seconds since t=0), strictly increasing."""
        return np.cumsum(self.interarrival_times(rng, n))

    def arrival_times_until(self, rng: np.random.Generator, duration_seconds: float) -> np.ndarray:
        """Arrival epochs within [0, duration_seconds). Batch-generates and
        grows until the window is covered — still exactly Exponential
        inter-arrivals per batch, just avoids guessing n up front."""
        expected_n = max(int(duration_seconds * self.rate_rps * 1.5) + 16, 16)
        times = self.arrival_times(rng, expected_n)
        while times[-1] < duration_seconds:
            more = self.interarrival_times(rng, expected_n)
            times = np.concatenate([times, times[-1] + np.cumsum(more)])
        return times[times < duration_seconds]


@dataclass(frozen=True)
class PhasedPoissonArrivalProcess:
    """Piecewise-constant-rate open-loop Poisson arrivals (e.g. `bursty`)."""

    phases: Tuple[Tuple[float, float], ...]  # ((duration_seconds, rate_rps), ...)
    repeat_phases: bool = False

    def arrival_times_until(self, rng: np.random.Generator, duration_seconds: float) -> np.ndarray:
        """Arrival epochs within [0, duration_seconds), phase rate applied
        piecewise. If `repeat_phases` is False, arrivals stop once the phase
        schedule is exhausted even if `duration_seconds` has not elapsed yet
        (matches the schema's `repeat_phases` semantics exactly)."""
        times: List[float] = []
        t0 = 0.0
        phase_iter = self._phase_cycle(duration_seconds)
        for phase_duration, rate_rps in phase_iter:
            if rate_rps > 0:
                proc = PoissonArrivalProcess(rate_rps)
                local = proc.arrival_times_until(rng, phase_duration)
                times.extend((t0 + local).tolist())
            t0 += phase_duration
            if t0 >= duration_seconds:
                break
        return np.asarray([t for t in times if t < duration_seconds])

    def _phase_cycle(self, duration_seconds: float):
        if not self.repeat_phases:
            yield from self.phases
            return
        elapsed = 0.0
        while elapsed < duration_seconds:
            for phase in self.phases:
                yield phase
                elapsed += phase[0]
                if elapsed >= duration_seconds:
                    return


@dataclass(frozen=True)
class ClosedLoopArrivalProcess:
    """Concurrency-driven arrivals: `concurrency` virtual clients, each
    issuing its next request `think_time_seconds` after the previous one
    completes.

    Deliberately data-only: unlike open-loop Poisson, closed-loop arrival
    timing depends on service latency, which this package does not model
    (that coupling belongs to `fleetlab/dynamics/`, FL-T005). fleetlab
    surfaces the disclosure flag the schema requires (closed-loop arrival
    hides queueing delay under saturation) but does not simulate it here.
    """

    concurrency: int
    think_time_seconds: float = 0.0


ArrivalProcess = Union[PoissonArrivalProcess, PhasedPoissonArrivalProcess, ClosedLoopArrivalProcess]


def arrival_process_from_workload(arrival_process: dict) -> ArrivalProcess:
    """Build the right arrival-process model from a validated
    `workload.arrival_process` sub-document."""
    kind = arrival_process["type"]
    if kind == "open-loop-poisson":
        if "phases" in arrival_process:
            phases = tuple(
                (p["duration_seconds"], p["rate_rps"]) for p in arrival_process["phases"]
            )
            return PhasedPoissonArrivalProcess(
                phases=phases,
                repeat_phases=bool(arrival_process.get("repeat_phases", False)),
            )
        return PoissonArrivalProcess(rate_rps=arrival_process["rate_rps"])
    if kind == "closed-loop":
        return ClosedLoopArrivalProcess(
            concurrency=arrival_process["concurrency"],
            think_time_seconds=arrival_process.get("think_time_seconds", 0.0),
        )
    raise ValueError(f"unknown arrival_process type '{kind}'")
