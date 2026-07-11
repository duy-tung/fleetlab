"""Known-answer + real-trace tests: Little's law (L = lambda * W)."""

from pathlib import Path

import pytest

from fleetlab.ingest import load_raw_events
from fleetlab.models.littles_law import (
    arrival_rate_rps,
    check_littles_law,
    concurrency,
    empirical_mean_sojourn_seconds,
    empirical_throughput_rps,
    empirical_time_average_concurrency,
    intervals_from_raw_events,
    latency_seconds,
)

REAL_RUNS = Path(__file__).resolve().parents[1] / "golden" / "fixtures" / "real" / "runs"


def test_concurrency_arrival_rate_latency_are_algebraically_consistent():
    l = concurrency(rate_rps=10.0, mean_latency_seconds=0.5)
    assert l == pytest.approx(5.0)
    assert arrival_rate_rps(l, 0.5) == pytest.approx(10.0)
    assert latency_seconds(l, 10.0) == pytest.approx(0.5)


def test_concurrency_rejects_nonpositive_inputs():
    with pytest.raises(ValueError):
        arrival_rate_rps(1.0, mean_latency_seconds=0.0)
    with pytest.raises(ValueError):
        latency_seconds(1.0, rate_rps=0.0)


def test_hand_computed_three_request_trace():
    """Three overlapping requests, worked by hand:

        request A: [0, 10]   request B: [2, 8]   request C: [5, 15]

    Segment-by-segment in-flight count: [0,2)=1, [2,5)=2, [5,8)=3, [8,10)=2,
    [10,15)=1. Area = 2*1 + 3*2 + 3*3 + 2*2 + 5*1 = 2+6+9+4+5 = 26.
    Window duration = 15 - 0 = 15, so L = 26/15.
    lambda = 3 requests / 15 s = 0.2 rps.
    W = mean(10, 6, 10) = 26/3 s.
    lambda * W = 0.2 * 26/3 = 26/15 -- matches L exactly (see docstring in
    fleetlab.models.littles_law: this identity holds algebraically for any
    finite trace over its own bounding window, not merely approximately).
    """
    intervals = [(0.0, 10.0), (2.0, 8.0), (5.0, 15.0)]
    l = empirical_time_average_concurrency(intervals)
    assert l == pytest.approx(26.0 / 15.0)
    lam = empirical_throughput_rps(intervals)
    assert lam == pytest.approx(0.2)
    w = empirical_mean_sojourn_seconds(intervals)
    assert w == pytest.approx(26.0 / 3.0)
    assert lam * w == pytest.approx(l)

    check = check_littles_law(intervals, tolerance=1e-9)
    assert check.within_tolerance
    assert check.relative_error < 1e-9


def test_check_littles_law_rejects_empty_trace():
    with pytest.raises(ValueError):
        check_littles_law([])


@pytest.mark.parametrize(
    "run_dir",
    ["calib-A-mock", "chat-short-cpu-direct-llamacpp"],
)
def test_littles_law_holds_on_real_traces(run_dir):
    """The identity holds exactly (to floating point) on the real,
    unmodified raw-event traces too — it is a sample-path algebraic
    identity, not a statistical property that needs a large-N argument."""
    events = load_raw_events(REAL_RUNS / run_dir / "events.jsonl")
    intervals = intervals_from_raw_events(events)
    assert len(intervals) > 0
    check = check_littles_law(intervals, tolerance=1e-6)
    assert check.within_tolerance, check
    assert check.l_measured > 0
