"""Known-answer-limit tests for `fleetlab.dynamics.simulator`
(docs/testing.md §2 + FL-T005 stop condition)."""

import math

import numpy as np
import pytest

from fleetlab.dynamics import simulate_queue
from fleetlab.models.arrival import PoissonArrivalProcess


def _erlang_c_wait_seconds(c: int, lam: float, mu: float) -> float:
    """Reference Erlang-C mean wait time, for cross-checking the simulator
    at low utilization. `a = lam/mu` (offered load, Erlangs); `rho = a/c`."""
    a = lam / mu
    rho = a / c
    assert rho < 1
    sum_terms = sum(a**k / math.factorial(k) for k in range(c))
    last_term = (a**c / math.factorial(c)) * (1.0 / (1 - rho))
    p_wait = last_term / (sum_terms + last_term)
    return p_wait / (c * mu - lam)


# ---------------------------------------------------------------------------
# Deterministic drain time (no RNG at all)
# ---------------------------------------------------------------------------


def test_deterministic_single_server_drain_time():
    """N jobs already queued at t=0 (no further arrivals), one server,
    fixed service time T each -> the last one completes at exactly N*T."""
    n = 25
    service_time = 0.4
    arrivals = np.zeros(n)
    service_times = np.full(n, service_time)
    trace = simulate_queue(arrivals, service_times, num_servers=1)
    last_completion = max(o.completion_time for o in trace.outcomes)
    assert last_completion == pytest.approx(n * service_time)
    # the i-th (0-indexed) job starts exactly at i*T and waits i*T seconds
    for i, outcome in enumerate(trace.outcomes):
        assert outcome.start_time == pytest.approx(i * service_time)
        assert outcome.wait_seconds == pytest.approx(i * service_time)


def test_deterministic_multiserver_drain_time():
    """N jobs at t=0, c identical servers, fixed service time T -> drains in
    exactly ceil(N/c) * T (round-robin across free servers)."""
    n, c, service_time = 20, 4, 1.5
    arrivals = np.zeros(n)
    service_times = np.full(n, service_time)
    trace = simulate_queue(arrivals, service_times, num_servers=c)
    last_completion = max(o.completion_time for o in trace.outcomes)
    expected = math.ceil(n / c) * service_time
    assert last_completion == pytest.approx(expected)


# ---------------------------------------------------------------------------
# lambda < mu: stable queue; matches M/M/1 mean-wait formula
# ---------------------------------------------------------------------------


def test_stable_queue_when_lambda_less_than_mu_matches_mm1_formula():
    rng = np.random.default_rng(20260711)
    lam, mu = 4.0, 5.0  # rho = 0.8
    n = 200_000
    arrival_proc = PoissonArrivalProcess(rate_rps=lam)
    arrivals = arrival_proc.arrival_times(rng, n)
    service_times = rng.exponential(scale=1.0 / mu, size=n)
    trace = simulate_queue(arrivals, service_times, num_servers=1)

    rho = lam / mu
    expected_wq = rho / (mu - lam)  # M/M/1 mean wait in queue
    assert trace.mean_wait_seconds() == pytest.approx(expected_wq, rel=0.05)


# ---------------------------------------------------------------------------
# lambda > mu: unbounded queue grows linearly at rate (lambda - mu)
# ---------------------------------------------------------------------------


def test_unstable_queue_grows_linearly_when_lambda_greater_than_mu():
    rng = np.random.default_rng(7)
    lam, mu = 10.0, 6.0
    n = 20_000
    arrival_proc = PoissonArrivalProcess(rate_rps=lam)
    arrivals = arrival_proc.arrival_times(rng, n)
    service_times = rng.exponential(scale=1.0 / mu, size=n)
    trace = simulate_queue(arrivals, service_times, num_servers=1)

    # Compare in-system count at two instants that both fall *while
    # arrivals are still flowing in* (arrivals.max() bounds that window --
    # after the last arrival the server keeps draining the backlog with no
    # new arrivals, which is a *different*, decreasing regime, not the
    # (lambda-mu) growth regime this test targets).
    arrival_span = arrivals.max()
    t1, t2 = 0.3 * arrival_span, 0.7 * arrival_span
    n1 = trace.in_system_at(t1)
    n2 = trace.in_system_at(t2)
    observed_slope = (n2 - n1) / (t2 - t1)
    assert observed_slope == pytest.approx(lam - mu, rel=0.1)


# ---------------------------------------------------------------------------
# M/M/c at low utilization matches the closed-form Erlang-C mean wait
# ---------------------------------------------------------------------------


def test_mmc_low_utilization_matches_erlang_c():
    rng = np.random.default_rng(99)
    c = 3
    mu = 2.0
    lam = 1.8  # a = 0.9 Erlangs, rho = 0.3 -- low utilization
    n = 150_000
    arrival_proc = PoissonArrivalProcess(rate_rps=lam)
    arrivals = arrival_proc.arrival_times(rng, n)
    service_times = rng.exponential(scale=1.0 / mu, size=n)
    trace = simulate_queue(arrivals, service_times, num_servers=c)

    expected_wq = _erlang_c_wait_seconds(c, lam, mu)
    assert trace.mean_wait_seconds() == pytest.approx(expected_wq, rel=0.1)


# ---------------------------------------------------------------------------
# Admission control / shedding
# ---------------------------------------------------------------------------


def test_capacity_cap_sheds_excess_and_never_exceeds_capacity():
    rng = np.random.default_rng(3)
    lam, mu = 10.0, 5.0
    n = 5_000
    arrival_proc = PoissonArrivalProcess(rate_rps=lam)
    arrivals = arrival_proc.arrival_times(rng, n)
    service_times = rng.exponential(scale=1.0 / mu, size=n)
    cap = 5
    trace = simulate_queue(arrivals, service_times, num_servers=1, capacity=cap)

    assert trace.shed_count > 0
    _, counts = trace.in_system_trace()
    assert counts.max() <= cap


def test_zero_capacity_sheds_everything():
    arrivals = np.array([0.0, 1.0, 2.0])
    service_times = np.array([0.5, 0.5, 0.5])
    trace = simulate_queue(arrivals, service_times, num_servers=1, capacity=0)
    assert trace.shed_count == 3
    assert trace.shed_rate == 1.0


# ---------------------------------------------------------------------------
# Burst decay: queue depth returns toward baseline after a burst ends
# ---------------------------------------------------------------------------


def test_burst_decay_back_to_steady_state_after_the_burst_ends():
    """Bursty-workload-shaped scenario (docs/testing.md §2's 'burst decay'
    limit): baseline rate comfortably below capacity, a short burst above
    capacity, then back to baseline -- in-system count must fall back close
    to the pre-burst level well before the next burst, not ratchet upward
    forever."""
    from fleetlab.models.arrival import PhasedPoissonArrivalProcess

    rng = np.random.default_rng(2026)
    # mu must exceed both the long-run average offered rate
    # ((60*2 + 15*20)/75 = 5.6 rps) -- otherwise the system is unstable
    # overall and never drains regardless of bursts -- and, ideally, drain
    # the per-burst backlog within the 60s baseline window that follows.
    mu = 8.0
    proc = PhasedPoissonArrivalProcess(
        phases=((60.0, 2.0), (15.0, 20.0)), repeat_phases=True
    )
    duration = 75.0 * 6  # six full cycles
    arrivals = proc.arrival_times_until(rng, duration)
    service_times = rng.exponential(scale=1.0 / mu, size=len(arrivals))
    trace = simulate_queue(arrivals, service_times, num_servers=1)

    # sample in-system count near the end of each 60s baseline phase
    # (i.e. just before each burst starts) across the six cycles
    pre_burst_counts = [trace.in_system_at(cycle * 75.0 + 58.0) for cycle in range(1, 6)]
    # none of the pre-burst samples should be anywhere near the peak
    # in-system count reached during a burst (proof the queue drains
    # between bursts rather than accumulating cycle over cycle)
    peak = trace.max_in_system()
    assert max(pre_burst_counts) < 0.5 * peak
