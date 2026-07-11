"""Known-answer tests: arrival-process model, parameterized from real
workload manifests where possible."""

from pathlib import Path

import numpy as np
import pytest

from fleetlab.ingest import load_workload
from fleetlab.models.arrival import (
    ClosedLoopArrivalProcess,
    PhasedPoissonArrivalProcess,
    PoissonArrivalProcess,
    arrival_process_from_workload,
)

REAL_WORKLOADS = Path(__file__).resolve().parents[1] / "golden" / "fixtures" / "real" / "workloads"


def test_poisson_mean_interarrival_is_one_over_rate():
    proc = PoissonArrivalProcess(rate_rps=8.0)
    assert proc.mean_interarrival_seconds() == pytest.approx(0.125)


def test_poisson_interarrival_times_converge_to_the_declared_rate():
    proc = PoissonArrivalProcess(rate_rps=8.0)
    rng = np.random.default_rng(1003001)  # chat-short's own seed
    inter = proc.interarrival_times(rng, 200_000)
    assert inter.mean() == pytest.approx(1.0 / 8.0, rel=0.02)


def test_poisson_arrival_count_in_a_window_matches_rate_times_duration():
    proc = PoissonArrivalProcess(rate_rps=8.0)
    rng = np.random.default_rng(42)
    times = proc.arrival_times_until(rng, duration_seconds=10_000.0)
    expected = 8.0 * 10_000.0
    assert times.shape[0] == pytest.approx(expected, rel=0.03)
    assert np.all(np.diff(times) > 0)  # strictly increasing
    assert times.max() < 10_000.0


def test_poisson_same_seed_is_byte_identical():
    proc = PoissonArrivalProcess(rate_rps=5.0)
    a = proc.arrival_times(np.random.default_rng(7), 1000)
    b = proc.arrival_times(np.random.default_rng(7), 1000)
    assert np.array_equal(a, b)


def test_poisson_different_seeds_differ():
    proc = PoissonArrivalProcess(rate_rps=5.0)
    a = proc.arrival_times(np.random.default_rng(7), 1000)
    b = proc.arrival_times(np.random.default_rng(8), 1000)
    assert not np.array_equal(a, b)


def test_poisson_rejects_nonpositive_rate():
    with pytest.raises(ValueError):
        PoissonArrivalProcess(rate_rps=0.0)


def test_phased_poisson_respects_bursty_workloads_phase_schedule():
    # bursty.json: 2 rps base, 10x burst 15s, period 75s (docs/README.md, IB-T003)
    phases = ((60.0, 2.0), (15.0, 20.0))
    proc = PhasedPoissonArrivalProcess(phases=phases, repeat_phases=True)
    rng = np.random.default_rng(123)
    times = proc.arrival_times_until(rng, duration_seconds=750.0)  # 10 periods
    # expected count: 10 periods * (60*2 + 15*20) = 10 * (120+300) = 4200
    assert times.shape[0] == pytest.approx(4200, rel=0.05)


def test_phased_poisson_without_repeat_stops_when_schedule_exhausted():
    phases = ((10.0, 5.0),)
    proc = PhasedPoissonArrivalProcess(phases=phases, repeat_phases=False)
    rng = np.random.default_rng(5)
    times = proc.arrival_times_until(rng, duration_seconds=1000.0)
    assert times.max() < 10.0  # schedule exhausted after 10s even though duration=1000


def test_arrival_process_from_workload_single_rate():
    arrival = {"type": "open-loop-poisson", "rate_rps": 8.0}
    proc = arrival_process_from_workload(arrival)
    assert isinstance(proc, PoissonArrivalProcess)
    assert proc.rate_rps == 8.0


def test_arrival_process_from_workload_phases():
    arrival = {
        "type": "open-loop-poisson",
        "phases": [{"duration_seconds": 60.0, "rate_rps": 2.0}, {"duration_seconds": 15.0, "rate_rps": 20.0}],
        "repeat_phases": True,
    }
    proc = arrival_process_from_workload(arrival)
    assert isinstance(proc, PhasedPoissonArrivalProcess)
    assert proc.phases == ((60.0, 2.0), (15.0, 20.0))
    assert proc.repeat_phases is True


def test_arrival_process_from_workload_closed_loop():
    arrival = {"type": "closed-loop", "concurrency": 16, "think_time_seconds": 1.0, "closed_loop_disclosed": True}
    proc = arrival_process_from_workload(arrival)
    assert isinstance(proc, ClosedLoopArrivalProcess)
    assert proc.concurrency == 16


def test_arrival_process_from_workload_rejects_unknown_type():
    with pytest.raises(ValueError):
        arrival_process_from_workload({"type": "not-a-real-type"})


# ---------------------------------------------------------------------------
# against real, schema-validated workload manifests
# ---------------------------------------------------------------------------


def test_real_chat_short_workload_builds_a_poisson_process():
    w = load_workload(REAL_WORKLOADS / "chat-short.json")
    proc = arrival_process_from_workload(w.arrival_process)
    assert isinstance(proc, PoissonArrivalProcess)
    assert proc.rate_rps == 8.0


def test_real_bursty_workload_builds_a_phased_process():
    w = load_workload(REAL_WORKLOADS / "bursty.json")
    proc = arrival_process_from_workload(w.arrival_process)
    assert isinstance(proc, PhasedPoissonArrivalProcess)
    assert len(proc.phases) >= 1
