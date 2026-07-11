"""Known-answer tests for `fleetlab.signals.series` (FL-T006, docs/testing.md
§2 style): a small hand-traced G/G/2 scenario, queried at non-boundary
instants to avoid exercising the tie-break convention already covered by
`tests/dynamics/test_simulator.py`.

Scenario: three simultaneous arrivals at t=0 (service time 5 each) into a
2-server system, plus a fourth arrival at t=10 (service time 5). By hand:
req1, req2 start immediately at t=0 (servers both free), completing at t=5;
req3 waits (no free server) until t=5, completing at t=10; req4 arrives
after everything has drained and starts immediately at t=10, completing at
t=15. Verified independently against `simulate_queue`'s own outcomes before
being fixed as the expected values below.
"""

from __future__ import annotations

import numpy as np
import pytest

from fleetlab.dynamics import simulate_queue
from fleetlab.signals.series import (
    in_flight_series,
    in_service_count_series,
    offered_request_rate_series,
    predicted_goodput_deficit_series,
    queue_depth_series,
    token_arrival_rate_series,
    utilization_series,
)


@pytest.fixture
def hand_traced_trace():
    arrivals = np.array([0.0, 0.0, 0.0, 10.0])
    service_times = np.array([5.0, 5.0, 5.0, 5.0])
    return simulate_queue(arrivals, service_times, num_servers=2)


QUERY_TIMES = np.array([2.0, 7.0, 12.0, 17.0])


def test_in_service_count_series_matches_hand_trace(hand_traced_trace):
    # req1,req2 in service on [0,5); req3 on [5,10); req4 on [10,15)
    assert in_service_count_series(hand_traced_trace, QUERY_TIMES).tolist() == [2.0, 1.0, 1.0, 0.0]


def test_queue_depth_series_matches_hand_trace(hand_traced_trace):
    # req3 arrives at 0 but does not start until 5 -> waiting on [0,5) only
    assert queue_depth_series(hand_traced_trace, QUERY_TIMES).tolist() == [1.0, 0.0, 0.0, 0.0]


def test_in_flight_series_is_in_service_plus_queue_depth(hand_traced_trace):
    in_service = in_service_count_series(hand_traced_trace, QUERY_TIMES)
    queue = queue_depth_series(hand_traced_trace, QUERY_TIMES)
    in_flight = in_flight_series(hand_traced_trace, QUERY_TIMES)
    assert in_flight.tolist() == (in_service + queue).tolist()
    assert in_flight.tolist() == [3.0, 1.0, 1.0, 0.0]


def test_utilization_series_is_in_service_over_num_servers(hand_traced_trace):
    util = utilization_series(hand_traced_trace, num_servers=2, query_times=QUERY_TIMES)
    assert util.tolist() == pytest.approx([1.0, 0.5, 0.5, 0.0])


def test_utilization_series_never_exceeds_one_even_with_one_server():
    """A pathological single-server case where three requests queue up:
    in_service can never exceed 1, so utilization must stay in [0, 1] even
    though queue depth (a different signal) grows unbounded."""
    arrivals = np.array([0.0, 0.0, 0.0])
    service_times = np.array([100.0, 100.0, 100.0])
    trace = simulate_queue(arrivals, service_times, num_servers=1)
    qt = np.array([50.0, 150.0, 250.0])
    util = utilization_series(trace, num_servers=1, query_times=qt)
    assert np.all(util >= 0.0) and np.all(util <= 1.0)


def test_offered_request_rate_series_counts_all_arrivals_including_shed():
    """A capacity cap sheds the third arrival, but the offered-rate signal
    is arrival-side (what was offered), so it must still count it."""
    arrivals = np.array([0.0, 0.0, 0.0])
    service_times = np.array([10.0, 10.0, 10.0])
    trace = simulate_queue(arrivals, service_times, num_servers=2, capacity=2)
    assert trace.shed_count == 1
    qt = np.array([0.5])
    rate = offered_request_rate_series(trace, qt, window_seconds=1.0)
    assert rate.tolist() == pytest.approx([3.0])  # 3 arrivals / 1s window


def test_token_arrival_rate_series_requires_alignment():
    arrivals = np.array([0.0, 1.0])
    service_times = np.array([1.0, 1.0])
    trace = simulate_queue(arrivals, service_times, num_servers=1)
    with pytest.raises(ValueError, match="aligned 1:1"):
        token_arrival_rate_series(trace, tokens_per_request=[10.0], query_times=np.array([1.0]), window_seconds=5.0)


def test_token_arrival_rate_series_known_answer():
    # two requests, one at t=0 (100 tokens), one at t=2 (50 tokens);
    # 5s trailing window at t=3 covers both -> (100+50)/5 = 30 tokens/s
    arrivals = np.array([0.0, 2.0])
    service_times = np.array([1.0, 1.0])
    trace = simulate_queue(arrivals, service_times, num_servers=2)
    rate = token_arrival_rate_series(trace, tokens_per_request=[100.0, 50.0], query_times=np.array([3.0]), window_seconds=5.0)
    assert rate.tolist() == pytest.approx([30.0])


def test_predicted_goodput_deficit_is_zero_below_capacity():
    arrivals = np.array([0.0, 1.0, 2.0])
    service_times = np.array([0.1, 0.1, 0.1])
    trace = simulate_queue(arrivals, service_times, num_servers=2)
    deficit = predicted_goodput_deficit_series(trace, capacity_rps=100.0, query_times=np.array([2.5]), window_seconds=10.0)
    assert deficit.tolist() == [0.0]


def test_predicted_goodput_deficit_is_positive_above_capacity():
    # 10 arrivals in a 1s window -> offered ~10 rps, well above capacity=1
    arrivals = np.arange(10) * 0.1
    service_times = np.full(10, 0.05)
    trace = simulate_queue(arrivals, service_times, num_servers=2)
    deficit = predicted_goodput_deficit_series(trace, capacity_rps=1.0, query_times=np.array([0.9]), window_seconds=1.0)
    assert deficit[0] > 0.0
