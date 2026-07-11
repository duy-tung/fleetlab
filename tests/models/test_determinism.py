"""Determinism tests (docs/testing.md §5): same seed + same inputs => byte
identical results; no module-level or global RNG state anywhere in
`fleetlab.models`."""

import hashlib
import re
from pathlib import Path

import numpy as np

from fleetlab.ingest import load_workload
from fleetlab.models.arrival import arrival_process_from_workload
from fleetlab.models.length import LengthDistribution

REAL_WORKLOADS = Path(__file__).resolve().parents[1] / "golden" / "fixtures" / "real" / "workloads"
MODELS_SRC = Path(__file__).resolve().parents[2] / "fleetlab" / "models"


def _run_once(seed: int) -> bytes:
    w = load_workload(REAL_WORKLOADS / "chat-short.json")
    rng = np.random.default_rng(seed)
    proc = arrival_process_from_workload(w.arrival_process)
    arrivals = proc.arrival_times_until(rng, duration_seconds=120.0)
    in_len = LengthDistribution(w.input_length_distribution).sample(rng, len(arrivals))
    out_len = LengthDistribution(w.output_length_distribution, round_floor=1).sample(rng, len(arrivals))
    payload = arrivals.tobytes() + in_len.tobytes() + out_len.tobytes()
    return hashlib.sha256(payload).digest()


def test_same_seed_same_inputs_is_byte_identical():
    assert _run_once(20260711) == _run_once(20260711)


def test_different_seed_differs():
    assert _run_once(1) != _run_once(2)


def test_models_package_uses_no_module_level_or_global_rng_state():
    """Guard against `np.random.seed(...)`, bare `np.random.rand(...)`, or
    Python's global `random` module creeping into fleetlab.models — every
    sampling function in this package must take an explicit
    `numpy.random.Generator` argument (determinism rule 3)."""
    forbidden = re.compile(r"\bnp\.random\.(seed|rand|randn|randint|choice|uniform|normal|exponential|lognormal)\b|(?<!\w)random\.(seed|random|randint|choice|uniform)\(")
    offenders = []
    for path in sorted(MODELS_SRC.glob("*.py")):
        text = path.read_text()
        for lineno, line in enumerate(text.splitlines(), start=1):
            if forbidden.search(line):
                offenders.append(f"{path.name}:{lineno}: {line.strip()}")
    assert not offenders, "found forbidden global/module-level RNG usage:\n" + "\n".join(offenders)
