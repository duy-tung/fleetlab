import pytest

from fleetlab.dynamics.headroom import (
    evaluate_cold_start_headroom,
    failure_capacity,
    required_headroom_rps,
)


def test_failure_capacity_arithmetic():
    report = failure_capacity(per_replica_capacity_rps=10.0, replica_count=3)
    assert report.full_fleet_capacity_rps == pytest.approx(30.0)
    assert report.n_minus_1_capacity_rps == pytest.approx(20.0)


def test_failure_capacity_single_replica_n_minus_1_is_zero():
    report = failure_capacity(per_replica_capacity_rps=10.0, replica_count=1)
    assert report.n_minus_1_capacity_rps == 0.0


def test_failure_capacity_rejects_bad_inputs():
    with pytest.raises(ValueError):
        failure_capacity(per_replica_capacity_rps=10.0, replica_count=0)
    with pytest.raises(ValueError):
        failure_capacity(per_replica_capacity_rps=0.0, replica_count=2)


def test_required_headroom_is_zero_when_n_minus_1_covers_peak():
    assert required_headroom_rps(peak_offered_rps=15.0, n_minus_1_capacity_rps=20.0) == 0.0


def test_required_headroom_is_the_positive_deficit():
    assert required_headroom_rps(peak_offered_rps=25.0, n_minus_1_capacity_rps=20.0) == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# Cold-start headroom scenario: backlog accrual + deterministic drain
# ---------------------------------------------------------------------------


def test_cold_start_headroom_no_deficit_means_no_backlog():
    scenario = evaluate_cold_start_headroom(
        peak_offered_rps=15.0,
        n_minus_1_capacity_rps=20.0,
        cold_start_seconds=90.0,
        recovered_capacity_rps=30.0,
        post_recovery_offered_rps=15.0,
    )
    assert scenario.deficit_rps == 0.0
    assert scenario.backlog_requests == 0.0
    assert scenario.drain_time_seconds == 0.0
    assert not scenario.drain_exceeds_available_time


def test_cold_start_headroom_backlog_and_drain_time_hand_computed():
    # deficit = 25 - 20 = 5 rps; over a 90s cold start -> 450-request backlog
    # drain rate once recovered = 30 - 15 = 15 rps -> drains in 30s
    scenario = evaluate_cold_start_headroom(
        peak_offered_rps=25.0,
        n_minus_1_capacity_rps=20.0,
        cold_start_seconds=90.0,
        recovered_capacity_rps=30.0,
        post_recovery_offered_rps=15.0,
    )
    assert scenario.deficit_rps == pytest.approx(5.0)
    assert scenario.backlog_requests == pytest.approx(450.0)
    assert scenario.drain_time_seconds == pytest.approx(30.0)
    assert not scenario.drain_exceeds_available_time


def test_cold_start_headroom_backlog_never_drains_if_post_recovery_still_saturated():
    scenario = evaluate_cold_start_headroom(
        peak_offered_rps=25.0,
        n_minus_1_capacity_rps=20.0,
        cold_start_seconds=90.0,
        recovered_capacity_rps=15.0,
        post_recovery_offered_rps=15.0,  # recovered capacity == ongoing offered rate
    )
    assert scenario.backlog_requests > 0
    assert scenario.drain_time_seconds is None
    assert scenario.drain_exceeds_available_time


def test_cold_start_headroom_scales_with_cold_start_duration():
    # doubling the cold-start window doubles the backlog (planning-prompt
    # hypothesis 3: headroom requirement is set by warm-up time x arrival
    # growth/deficit rate)
    short = evaluate_cold_start_headroom(
        peak_offered_rps=25.0, n_minus_1_capacity_rps=20.0,
        cold_start_seconds=2.0, recovered_capacity_rps=30.0,
        post_recovery_offered_rps=15.0,
    )
    long = evaluate_cold_start_headroom(
        peak_offered_rps=25.0, n_minus_1_capacity_rps=20.0,
        cold_start_seconds=88.0, recovered_capacity_rps=30.0,
        post_recovery_offered_rps=15.0,
    )
    assert long.backlog_requests == pytest.approx(44 * short.backlog_requests)
