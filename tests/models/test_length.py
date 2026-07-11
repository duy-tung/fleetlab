"""Known-answer tests: length-distribution model (workload schema shapes)."""

import numpy as np
import pytest

from fleetlab.models.length import LengthDistribution, mean_of_distribution, sample_distribution


def test_constant_mean_and_samples():
    dist = {"type": "constant", "value": 42.0}
    assert mean_of_distribution(dist) == 42.0
    rng = np.random.default_rng(1)
    samples = sample_distribution(dist, rng, 100)
    assert np.all(samples == 42.0)


def test_uniform_mean_is_midpoint_and_samples_converge():
    dist = {"type": "uniform", "min": 10.0, "max": 30.0}
    assert mean_of_distribution(dist) == 20.0
    rng = np.random.default_rng(2)
    samples = sample_distribution(dist, rng, 200_000)
    assert samples.mean() == pytest.approx(20.0, abs=0.1)
    assert samples.min() >= 10.0
    assert samples.max() <= 30.0


def test_normal_samples_converge_to_mean_and_stddev_without_clamp():
    dist = {"type": "normal", "mean": 200.0, "stddev": 80.0}
    assert mean_of_distribution(dist) == 200.0
    rng = np.random.default_rng(3)
    samples = sample_distribution(dist, rng, 500_000)
    assert samples.mean() == pytest.approx(200.0, abs=1.0)
    assert samples.std() == pytest.approx(80.0, rel=0.02)


def test_normal_clamp_is_applied_after_sampling():
    dist = {"type": "normal", "mean": 200.0, "stddev": 80.0, "min": 16.0, "max": 1024.0}
    rng = np.random.default_rng(4)
    samples = sample_distribution(dist, rng, 50_000)
    assert samples.min() >= 16.0
    assert samples.max() <= 1024.0


def test_lognormal_mean_matches_exp_mu_plus_half_sigma_squared():
    # chat-short's own output-length distribution (inferbench/workloads/chat-short.json)
    dist = {"type": "lognormal", "mu": 4.8, "sigma": 0.6}
    expected = np.exp(4.8 + 0.6**2 / 2.0)
    assert mean_of_distribution(dist) == pytest.approx(expected)
    rng = np.random.default_rng(5)
    samples = sample_distribution(dist, rng, 500_000)
    assert samples.mean() == pytest.approx(expected, rel=0.02)


def test_lognormal_clamp_is_applied_after_sampling():
    dist = {"type": "lognormal", "mu": 4.8, "sigma": 0.6, "min": 8.0, "max": 384.0}
    rng = np.random.default_rng(6)
    samples = sample_distribution(dist, rng, 50_000)
    assert samples.min() >= 8.0
    assert samples.max() <= 384.0


def test_empirical_mean_and_sampling_replacement():
    dist = {"type": "empirical", "samples": [10.0, 20.0, 30.0]}
    assert mean_of_distribution(dist) == 20.0
    rng = np.random.default_rng(7)
    samples = sample_distribution(dist, rng, 1000)
    assert set(np.unique(samples)) <= {10.0, 20.0, 30.0}


def test_mixture_mean_is_weighted_average_of_components():
    dist = {
        "type": "mixture",
        "components": [
            {"weight": 1.0, "distribution": {"type": "constant", "value": 100.0}},
            {"weight": 1.0, "distribution": {"type": "constant", "value": 300.0}},
        ],
    }
    assert mean_of_distribution(dist) == pytest.approx(200.0)
    rng = np.random.default_rng(8)
    samples = sample_distribution(dist, rng, 100_000)
    assert samples.mean() == pytest.approx(200.0, abs=2.0)
    assert set(np.unique(samples)) == {100.0, 300.0}


def test_mixture_weights_need_not_be_pre_normalized():
    # 60/25/15 split, matching inferbench/workloads/mixed.json's declared blend
    dist = {
        "type": "mixture",
        "components": [
            {"weight": 60, "distribution": {"type": "constant", "value": 1.0}},
            {"weight": 25, "distribution": {"type": "constant", "value": 2.0}},
            {"weight": 15, "distribution": {"type": "constant", "value": 3.0}},
        ],
    }
    expected = 0.60 * 1.0 + 0.25 * 2.0 + 0.15 * 3.0
    assert mean_of_distribution(dist) == pytest.approx(expected)


def test_length_distribution_rounds_and_floors_at_one_by_default():
    ld = LengthDistribution({"type": "constant", "value": 0.2})
    rng = np.random.default_rng(9)
    samples = ld.sample(rng, 10)
    assert samples.dtype.kind == "i"
    assert np.all(samples == 1)  # round(0.2) = 0, floored to the >=1 rule


def test_length_distribution_cancellation_point_can_floor_at_zero():
    ld = LengthDistribution({"type": "constant", "value": 0.2}, round_floor=0)
    rng = np.random.default_rng(10)
    samples = ld.sample(rng, 10)
    assert np.all(samples == 0)


def test_length_distribution_raw_mode_skips_rounding():
    ld = LengthDistribution({"type": "uniform", "min": 0.1, "max": 0.9})
    rng = np.random.default_rng(11)
    samples = ld.sample(rng, 100, round_to_int=False)
    assert samples.dtype.kind == "f"
    assert samples.min() >= 0.1


def test_unknown_distribution_type_rejected():
    with pytest.raises(ValueError):
        sample_distribution({"type": "not-a-real-distribution"}, np.random.default_rng(0), 1)
