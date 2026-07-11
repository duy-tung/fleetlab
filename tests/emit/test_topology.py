"""Known-answer tests for `fleetlab.emit.topology` (FL-T009)."""

from __future__ import annotations

import pytest

from fleetlab.emit.topology import (
    fleet_capacity_rps,
    goodput_uncertainty,
    predicted_goodput_rps,
    recommend_replica_count,
)


def test_recommend_replica_count_known_answer():
    # 100 rps demand / 33 rps per replica -> ceil(3.03) = 4
    assert recommend_replica_count(100.0, 33.0) == 4


def test_recommend_replica_count_exact_multiple():
    assert recommend_replica_count(99.0, 33.0) == 3


def test_recommend_replica_count_safety_margin_increases_count():
    no_margin = recommend_replica_count(100.0, 33.0)
    with_margin = recommend_replica_count(100.0, 33.0, safety_margin_fraction=0.2)
    assert with_margin >= no_margin


def test_recommend_replica_count_rejects_bad_inputs():
    with pytest.raises(ValueError):
        recommend_replica_count(0.0, 33.0)
    with pytest.raises(ValueError):
        recommend_replica_count(100.0, 0.0)
    with pytest.raises(ValueError):
        recommend_replica_count(100.0, 33.0, safety_margin_fraction=1.0)


def test_fleet_capacity_rps_known_answer():
    assert fleet_capacity_rps(6, 33.159) == pytest.approx(198.954)


def test_fleet_capacity_rps_rejects_bad_inputs():
    with pytest.raises(ValueError):
        fleet_capacity_rps(0, 33.0)
    with pytest.raises(ValueError):
        fleet_capacity_rps(3, 0.0)


def test_predicted_goodput_rps_is_demand_capped():
    assert predicted_goodput_rps(100.0, 200.0) == pytest.approx(100.0)
    assert predicted_goodput_rps(300.0, 200.0) == pytest.approx(200.0)


def test_goodput_uncertainty_requires_at_least_one_error_source():
    with pytest.raises(ValueError):
        goodput_uncertainty(demand_rps=100.0, replica_count=4, per_replica_capacity_rps=33.0)


def test_goodput_uncertainty_known_answer_with_stderr_only():
    result = goodput_uncertainty(
        demand_rps=100.0,
        replica_count=4,
        per_replica_capacity_rps=33.0,
        per_replica_capacity_stderr=3.3,  # 10% relative
    )
    assert result.value == pytest.approx(100.0)  # fleet capacity 132 > demand 100
    assert result.upper == pytest.approx(100.0)
    assert result.lower == pytest.approx(90.0)  # 100 * (1 - 0.10)


def test_goodput_uncertainty_picks_the_larger_relative_error():
    # stderr implies 5% relative error, holdout implies 20% -> lower bound
    # must reflect the larger (20%) figure.
    result = goodput_uncertainty(
        demand_rps=100.0,
        replica_count=4,
        per_replica_capacity_rps=33.0,
        per_replica_capacity_stderr=1.65,  # 5% relative
        holdout_relative_error=-0.20,
    )
    assert result.lower == pytest.approx(80.0)


def test_goodput_uncertainty_lower_never_negative():
    result = goodput_uncertainty(
        demand_rps=100.0,
        replica_count=1,
        per_replica_capacity_rps=33.0,
        holdout_relative_error=-1.5,  # absurdly large, exercises the floor
    )
    assert result.lower == 0.0


def test_goodput_uncertainty_matches_the_published_e2_recommendation_numbers():
    """Cross-check against the real E2 '5x overload' recommendation this
    task publishes (examples/recommendations/): capacity 33.15910399768093
    +/- 1.1053034665893644, 6 replicas, demand 189.0362, G8 holdout
    rel_error -0.1256752011727604."""
    result = goodput_uncertainty(
        demand_rps=189.0362,
        replica_count=6,
        per_replica_capacity_rps=33.15910399768093,
        per_replica_capacity_stderr=1.1053034665893644,
        holdout_relative_error=-0.1256752011727604,
    )
    assert result.value == pytest.approx(189.0362)
    assert result.upper == pytest.approx(189.0362)
    assert result.lower == pytest.approx(165.279, abs=0.01)
