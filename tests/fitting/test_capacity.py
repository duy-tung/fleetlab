import pytest

from fleetlab.fitting import fit_capacity, predict_achieved_rps
from fleetlab.fitting.capacity import CapacityUnderdeterminedError


def test_single_point_fit_is_exact_no_optimizer(e2_baseline):
    fit = fit_capacity([e2_baseline])
    assert fit.capacity_rps == pytest.approx(e2_baseline.achieved_rate_rps)
    assert fit.train_run_ids == frozenset({e2_baseline.run_id})


def test_predict_below_capacity_returns_offered(e2_baseline):
    fit = fit_capacity([e2_baseline])
    # offered well below fitted capacity -> model predicts "no clamping"
    assert predict_achieved_rps(fit, 1.0) == pytest.approx(1.0)


def test_predict_above_capacity_returns_capacity(e2_baseline):
    fit = fit_capacity([e2_baseline])
    assert predict_achieved_rps(fit, 10_000.0) == pytest.approx(fit.capacity_rps)


def test_underloaded_point_refuses_a_fit(e1_mock_direct):
    # Synthetic point (achieved == offered exactly): the cleanest possible
    # "no clamping observed" case -- the model must refuse rather than
    # pretend a capacity estimate exists. (The real e1_mock_direct point
    # has a small ~3% achieved/offered gap of its own -- technically over
    # this module's informative-gap threshold, but it is still a single
    # point with no second rate to holdout-validate against; that
    # insufficiency is documented in reports/holdout-validation.md, not
    # encoded as a refusal here.)
    import dataclasses

    exactly_at_offered = dataclasses.replace(
        e1_mock_direct, achieved_rate_rps=e1_mock_direct.offered_rate_rps
    )
    with pytest.raises(CapacityUnderdeterminedError):
        fit_capacity([exactly_at_offered])


def test_fit_capacity_requires_at_least_one_point():
    with pytest.raises(ValueError):
        fit_capacity([])


def test_two_training_points_combine_by_inverse_variance(e2_baseline, e2_overload):
    fit_both = fit_capacity([e2_baseline, e2_overload])
    fit_baseline_only = fit_capacity([e2_baseline])
    fit_overload_only = fit_capacity([e2_overload])
    # combined estimate lies strictly between the two single-point estimates
    lo, hi = sorted([fit_baseline_only.capacity_rps, fit_overload_only.capacity_rps])
    assert lo < fit_both.capacity_rps < hi
    # combining two points can only shrink (or hold) the standard error
    assert fit_both.capacity_rps_stderr <= min(
        fit_baseline_only.capacity_rps_stderr, fit_overload_only.capacity_rps_stderr
    )
