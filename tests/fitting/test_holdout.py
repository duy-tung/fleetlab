import pytest

from fleetlab.fitting import (
    HoldoutSplit,
    TrainingDataLeakageError,
    evaluate_holdout,
    fit_profile,
)


# ---------------------------------------------------------------------------
# HoldoutSplit structural validation
# ---------------------------------------------------------------------------


def test_holdout_split_requires_nonempty_train_and_holdout():
    with pytest.raises(ValueError):
        HoldoutSplit(train_run_ids=frozenset(), holdout_run_ids=frozenset({"a"}))
    with pytest.raises(ValueError):
        HoldoutSplit(train_run_ids=frozenset({"a"}), holdout_run_ids=frozenset())


def test_holdout_split_requires_disjoint_sets():
    with pytest.raises(ValueError, match="disjoint"):
        HoldoutSplit(train_run_ids=frozenset({"a", "b"}), holdout_run_ids=frozenset({"b", "c"}))


# ---------------------------------------------------------------------------
# The G8 impossibility test: fit quality on training data has NO code path.
# ---------------------------------------------------------------------------


def test_evaluate_holdout_on_a_training_point_raises(e2_baseline, e2_overload):
    """Structural proof (docs/testing.md §4.2): asking to score a profile
    against the very data that trained it raises, unconditionally — this is
    not a convention the caller could get around by mislabeling a split."""
    split = HoldoutSplit(
        train_run_ids=frozenset({e2_baseline.run_id}),
        holdout_run_ids=frozenset({e2_overload.run_id}),
    )
    profile = fit_profile([e2_baseline, e2_overload], split)

    with pytest.raises(TrainingDataLeakageError):
        evaluate_holdout(profile, [e2_baseline])  # the training point itself

    with pytest.raises(TrainingDataLeakageError):
        # even mixed in with a genuine holdout point, ANY training point
        # present in the call is refused -- no silent filtering.
        evaluate_holdout(profile, [e2_baseline, e2_overload])


def test_evaluate_holdout_on_undeclared_point_raises(e2_baseline, e2_overload, e2b_baseline):
    split = HoldoutSplit(
        train_run_ids=frozenset({e2_baseline.run_id}),
        holdout_run_ids=frozenset({e2_overload.run_id}),
    )
    profile = fit_profile([e2_baseline, e2_overload], split)
    with pytest.raises(ValueError, match="neither this profile's training nor holdout"):
        evaluate_holdout(profile, [e2b_baseline])


def test_evaluate_holdout_requires_at_least_one_point(e2_baseline, e2_overload):
    split = HoldoutSplit(
        train_run_ids=frozenset({e2_baseline.run_id}),
        holdout_run_ids=frozenset({e2_overload.run_id}),
    )
    profile = fit_profile([e2_baseline, e2_overload], split)
    with pytest.raises(ValueError):
        evaluate_holdout(profile, [])


# ---------------------------------------------------------------------------
# fit_profile: per-config isolation
# ---------------------------------------------------------------------------


def test_fit_profile_refuses_points_spanning_two_engine_configs(e2_baseline, e2b_baseline):
    split = HoldoutSplit(
        train_run_ids=frozenset({e2_baseline.run_id, e2b_baseline.run_id}),
        holdout_run_ids=frozenset({"placeholder-not-used"}),
    )
    with pytest.raises(ValueError, match="more than one"):
        fit_profile([e2_baseline, e2b_baseline], split)


def test_fit_profile_rejects_unknown_run_ids(e2_baseline):
    split = HoldoutSplit(
        train_run_ids=frozenset({e2_baseline.run_id}),
        holdout_run_ids=frozenset({"does-not-exist"}),
    )
    with pytest.raises(ValueError, match="not found"):
        fit_profile([e2_baseline], split)


# ---------------------------------------------------------------------------
# The real G8 result: both directions, both configs (see
# reports/holdout-validation.md for the full write-up and error analysis).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "train_fixture,holdout_fixture,expected_rel_error",
    [
        ("e2_baseline", "e2_overload", -0.126),
        ("e2_overload", "e2_baseline", 0.140),
        ("e2b_baseline", "e2b_overload", -0.170),
        ("e2b_overload", "e2b_baseline", 0.204),
    ],
)
def test_g8_holdout_prediction_error_matches_the_reviewed_figures(
    request, train_fixture, holdout_fixture, expected_rel_error
):
    train_point = request.getfixturevalue(train_fixture)
    holdout_point = request.getfixturevalue(holdout_fixture)
    split = HoldoutSplit(
        train_run_ids=frozenset({train_point.run_id}),
        holdout_run_ids=frozenset({holdout_point.run_id}),
    )
    profile = fit_profile([train_point, holdout_point], split)
    report = evaluate_holdout(profile, [holdout_point])
    (point,) = report.points
    assert point.rel_error == pytest.approx(expected_rel_error, abs=0.01)
    # the miss is several times larger than the measurement-noise floor --
    # a genuine model-specification limitation, not sampling noise.
    assert abs(point.abs_error_rps) > 3 * point.measurement_stderr_rps
