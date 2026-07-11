import pytest

from fleetlab.fitting import fit_capacity, fit_latency, predict_latency
from fleetlab.fitting.latency import LatencyModelUndefined


def test_latency_undefined_when_no_training_point_is_below_fitted_capacity(
    e2_baseline, e2_overload
):
    # Both real points for this config have achieved < offered, i.e. both
    # sit at/above their own implied capacity -- exactly the documented
    # PENDING case (docs/notes/fitting-method.md).
    cap_from_baseline = fit_capacity([e2_baseline])
    with pytest.raises(LatencyModelUndefined):
        fit_latency([e2_baseline], cap_from_baseline)

    cap_from_overload = fit_capacity([e2_overload])
    with pytest.raises(LatencyModelUndefined):
        fit_latency([e2_overload], cap_from_overload)


def test_latency_fits_and_predicts_on_a_synthetic_underloaded_point(e2_baseline):
    # A synthetic point (NOT part of the real corpus, only used to exercise
    # the code path that the real data cannot reach) with offered clearly
    # below a capacity fit, to prove the identifiable branch works and its
    # predict function is the algebraic inverse of the fit.
    import dataclasses

    underloaded = dataclasses.replace(
        e2_baseline,
        run_id="synthetic-underloaded",
        offered_rate_rps=10.0,
        achieved_rate_rps=10.0,
        e2e_p50_seconds=0.05,
    )
    cap = fit_capacity([e2_baseline])  # capacity = 33.159 (real)
    fit = fit_latency([underloaded], cap)
    assert fit.l0_seconds > 0
    predicted = predict_latency(fit, 10.0)
    assert predicted == pytest.approx(0.05, rel=1e-9)


def test_predict_latency_at_or_above_capacity_raises():
    from fleetlab.fitting.capacity import CapacityFit
    from fleetlab.fitting.latency import LatencyFit

    cap = CapacityFit(
        capacity_rps=20.0,
        capacity_rps_stderr=1.0,
        train_run_ids=frozenset({"x"}),
        train_source_paths=(),
    )
    fit = LatencyFit(
        l0_seconds=0.1,
        l0_seconds_stderr=float("nan"),
        capacity_fit=cap,
        train_run_ids=frozenset({"x"}),
    )
    with pytest.raises(LatencyModelUndefined):
        predict_latency(fit, 20.0)
    with pytest.raises(LatencyModelUndefined):
        predict_latency(fit, 25.0)
