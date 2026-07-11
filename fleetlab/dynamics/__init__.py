"""fleetlab.dynamics — time-dependent behavior (FL-T005).

Per ADR-0001 ("analytic-first, with a small owned discrete-event core for
dynamics"): steady-state models (`fleetlab/models/`, fitting) are closed
form; genuinely transient behavior — queue growth under bursts, cold-start
delay, scale-up/down lag, N-1 failover headroom — is simulated here with a
small, in-repo, seed-driven event core. Every discrete-event scenario is
required to reproduce its analytic limit in a known-answer test (`tests/
dynamics/`): the analytic results are ground truth; the simulator earns
trust by converging to them.

Determinism: `simulate_queue` itself takes no RNG — it is a pure function of
its `arrivals`/`service_times` arrays, so it is trivially deterministic.
Anywhere a stochastic input array is generated (e.g. exponential service
times for an M/M/c scenario), that sampling takes an explicit
`numpy.random.Generator`, exactly like `fleetlab.models` (determinism rule
3, docs/architecture.md) — no module-level or global RNG state anywhere in
this package (`tests/dynamics/test_determinism.py` guards this).
"""

from .simulator import QueueTrace, RequestOutcome, simulate_queue
from .cold_start import ColdStartProfile, MEASURED_COLD_START
from .scaling import ScalingDelay, ASSUMED_SCALING_DELAY
from .headroom import (
    FailureCapacityReport,
    HeadroomScenario,
    failure_capacity,
    required_headroom_rps,
)

__all__ = [
    "QueueTrace",
    "RequestOutcome",
    "simulate_queue",
    "ColdStartProfile",
    "MEASURED_COLD_START",
    "ScalingDelay",
    "ASSUMED_SCALING_DELAY",
    "FailureCapacityReport",
    "HeadroomScenario",
    "failure_capacity",
    "required_headroom_rps",
]
