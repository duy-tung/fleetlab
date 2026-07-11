"""Determinism tests (docs/testing.md §5) for `fleetlab.dynamics`."""

import hashlib
import re
from pathlib import Path

import numpy as np

from fleetlab.dynamics import simulate_queue
from fleetlab.models.arrival import PhasedPoissonArrivalProcess

DYNAMICS_SRC = Path(__file__).resolve().parents[2] / "fleetlab" / "dynamics"


def _run_once(seed: int) -> bytes:
    rng = np.random.default_rng(seed)
    proc = PhasedPoissonArrivalProcess(phases=((60.0, 2.0), (15.0, 20.0)), repeat_phases=True)
    arrivals = proc.arrival_times_until(rng, 300.0)
    service_times = rng.exponential(scale=1.0 / 8.0, size=len(arrivals))
    trace = simulate_queue(arrivals, service_times, num_servers=1)
    payload = b"".join(
        f"{o.arrival_time:.9f},{o.service_time:.9f},{o.admitted},{o.start_time},{o.completion_time}".encode()
        for o in trace.outcomes
    )
    return hashlib.sha256(payload).digest()


def test_same_seed_same_inputs_is_byte_identical():
    assert _run_once(20260711) == _run_once(20260711)


def test_different_seed_differs():
    assert _run_once(1) != _run_once(2)


def test_simulate_queue_itself_takes_no_rng_and_is_a_pure_function():
    """`simulate_queue` accepts only plain arrays -- no `numpy.random.Generator`
    parameter at all -- so it cannot have hidden RNG state; same arrays in,
    same `QueueTrace` out, always."""
    arrivals = np.array([0.0, 1.0, 2.5, 2.6])
    service_times = np.array([0.9, 0.4, 0.2, 1.1])
    a = simulate_queue(arrivals, service_times, num_servers=2)
    b = simulate_queue(arrivals, service_times, num_servers=2)
    assert a == b


def test_dynamics_package_uses_no_module_level_or_global_rng_state():
    forbidden = re.compile(
        r"\bnp\.random\.(seed|rand|randn|randint|choice|uniform|normal|exponential|lognormal)\b"
        r"|(?<!\w)random\.(seed|random|randint|choice|uniform)\("
    )
    offenders = []
    for path in sorted(DYNAMICS_SRC.glob("*.py")):
        text = path.read_text()
        for lineno, line in enumerate(text.splitlines(), start=1):
            if forbidden.search(line):
                offenders.append(f"{path.name}:{lineno}: {line.strip()}")
    assert not offenders, "found forbidden global/module-level RNG usage:\n" + "\n".join(offenders)
