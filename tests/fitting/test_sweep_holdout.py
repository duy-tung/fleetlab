"""G8 holdout on the ib-t008 six-point sweep (corrected corpus scope).

The reviewed figures below are the ones published in
`reports/holdout-validation.md` §2b and `profiles/fitted/
mock-loopback-cpu-dev__mock-8b__gateway-mock-flags-v1-conncap2.json`.
"""

import math

import pytest

from fleetlab.fitting import (
    HoldoutSplit,
    TrainingDataLeakageError,
    evaluate_holdout,
    fit_profile,
)


def _split(train_idx, holdout_idx):
    return HoldoutSplit(
        train_run_ids=frozenset(f"ib-t008-sweep-p{i}" for i in train_idx),
        holdout_run_ids=frozenset(f"ib-t008-sweep-p{i}" for i in holdout_idx),
    )


def _by_id(points):
    return {p.run_id: p for p in points}


# ---------------------------------------------------------------------------
# Direction A (published): train {p0,p1,p3,p4}, holdout {p2 interior,
# p5 overload extrapolation}
# ---------------------------------------------------------------------------


def test_direction_a_capacity_and_latency(sweep_points):
    ids = _by_id(sweep_points)
    profile = fit_profile(sweep_points, _split([0, 1, 3, 4], [2, 5]))

    # capacity: weighted-LSQ optimum clamps only p4 -> C = p4's achieved
    assert profile.capacity_fit.capacity_rps == pytest.approx(26.157, abs=0.01)
    assert profile.capacity_fit.capacity_rps_stderr == pytest.approx(1.233, abs=0.01)

    # latency model is now FITTED (sub-capacity training points exist:
    # p0, p1, p3 are below C) -- the FL-T004 PENDING is closed for this config
    assert profile.latency_fit is not None
    assert profile.latency_pending_reason is None

    report = evaluate_holdout(profile, [ids["ib-t008-sweep-p2"], ids["ib-t008-sweep-p5"]])
    by_run = {r.run_id: r for r in report.points}

    # interior interpolation point p2: capacity nearly exact, latency +10%
    p2 = by_run["ib-t008-sweep-p2"]
    assert p2.rel_error == pytest.approx(0.007, abs=0.005)
    assert p2.latency_rel_error == pytest.approx(0.100, abs=0.01)

    # overload extrapolation point p5: capacity -6.7%, ~1.05x the COMBINED
    # 1-sigma error (fit stderr + measurement stderr in quadrature) -- the
    # G8 within-stated-error outcome for this config
    p5 = by_run["ib-t008-sweep-p5"]
    assert p5.rel_error == pytest.approx(-0.067, abs=0.005)
    combined = math.hypot(profile.capacity_fit.capacity_rps_stderr, p5.measurement_stderr_rps)
    assert abs(p5.abs_error_rps) / combined == pytest.approx(1.05, abs=0.05)
    # latency has no finite prediction at/above C -- recorded, not clipped
    assert p5.predicted_e2e_p50_seconds is None
    assert p5.latency_note is not None


# ---------------------------------------------------------------------------
# Direction B (reverse): train {p1,p2,p3,p5}, holdout {p0 low-rate, p4}
# ---------------------------------------------------------------------------


def test_direction_b_capacity_and_latency(sweep_points):
    ids = _by_id(sweep_points)
    profile = fit_profile(sweep_points, _split([1, 2, 3, 5], [0, 4]))

    assert profile.capacity_fit.capacity_rps == pytest.approx(28.050, abs=0.01)
    assert profile.latency_fit is not None

    report = evaluate_holdout(profile, [ids["ib-t008-sweep-p0"], ids["ib-t008-sweep-p4"]])
    by_run = {r.run_id: r for r in report.points}

    # p0 (lowest rate): capacity nearly exact; latency extrapolation to the
    # near-empty system UNDER-predicts by 34% -- the documented functional-
    # form limitation (multiplicative L0*C/(C-offered) vs the target's
    # additive base-service-time + queueing-delay shape)
    p0 = by_run["ib-t008-sweep-p0"]
    assert p0.rel_error == pytest.approx(-0.004, abs=0.005)
    assert p0.latency_rel_error == pytest.approx(-0.344, abs=0.01)

    # p4 (0.98x capacity point): capacity +7.2%, ~1.05x combined 1-sigma
    p4 = by_run["ib-t008-sweep-p4"]
    assert p4.rel_error == pytest.approx(0.072, abs=0.005)
    combined = math.hypot(profile.capacity_fit.capacity_rps_stderr, p4.measurement_stderr_rps)
    assert abs(p4.abs_error_rps) / combined == pytest.approx(1.05, abs=0.05)
    # p4's offered (29.27) sits above C (28.05): no finite latency prediction
    assert p4.predicted_e2e_p50_seconds is None


# ---------------------------------------------------------------------------
# The leakage guard is unchanged by the richer corpus
# ---------------------------------------------------------------------------


def test_leakage_guard_still_raises_on_sweep_training_points(sweep_points):
    ids = _by_id(sweep_points)
    profile = fit_profile(sweep_points, _split([0, 1, 3, 4], [2, 5]))
    with pytest.raises(TrainingDataLeakageError):
        evaluate_holdout(profile, [ids["ib-t008-sweep-p3"]])
    with pytest.raises(TrainingDataLeakageError):
        # a training point hidden among genuine holdout points still refuses
        evaluate_holdout(
            profile, [ids["ib-t008-sweep-p2"], ids["ib-t008-sweep-p0"]]
        )
