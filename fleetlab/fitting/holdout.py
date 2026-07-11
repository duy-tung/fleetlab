"""The G8 holdout mechanism (docs/testing.md §4): structural, not honor-system.

`HoldoutSplit` requires an explicit, disjoint, non-empty train/holdout
partition by run ID. `fit_profile` fits the capacity model (and the latency
model, when the data supports it) from the training points only, and the
returned `FittedGoodputProfile` remembers exactly which run IDs trained it.
`evaluate_holdout` computes prediction error **only** against points whose
run ID is in the profile's own recorded holdout set; it raises
`TrainingDataLeakageError` if asked to evaluate against any point whose run
ID trained the profile — there is no argument or call sequence that reports
fit quality on training data (`tests/fitting/test_holdout.py::
test_evaluate_holdout_on_a_training_point_raises` asserts this directly).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, Optional, Sequence

from .capacity import CapacityFit, fit_capacity, predict_achieved_rps
from .corpus import CorpusPoint
from .latency import LatencyFit, LatencyModelUndefined, fit_latency, predict_latency


class TrainingDataLeakageError(ValueError):
    """Raised when `evaluate_holdout` is asked to score a point whose run ID
    trained the profile being evaluated. This is the structural proof that
    fit-quality-on-training-data has no code path (docs/testing.md §4.2)."""


@dataclass(frozen=True)
class HoldoutSplit:
    train_run_ids: FrozenSet[str]
    holdout_run_ids: FrozenSet[str]

    def __post_init__(self) -> None:
        train = frozenset(self.train_run_ids)
        holdout = frozenset(self.holdout_run_ids)
        object.__setattr__(self, "train_run_ids", train)
        object.__setattr__(self, "holdout_run_ids", holdout)
        if not train:
            raise ValueError("HoldoutSplit requires at least one training run ID")
        if not holdout:
            raise ValueError(
                "HoldoutSplit requires a non-empty holdout set — G8 has no "
                "concept of a fit with nothing held out"
            )
        overlap = train & holdout
        if overlap:
            raise ValueError(
                f"train and holdout run-ID sets must be disjoint; overlap: {sorted(overlap)}"
            )


@dataclass(frozen=True)
class FittedGoodputProfile:
    hardware_id: str
    model_id: str
    engine_config_id: str
    capacity_fit: CapacityFit
    latency_fit: Optional[LatencyFit]
    latency_pending_reason: Optional[str]
    train_run_ids: FrozenSet[str]
    holdout_run_ids: FrozenSet[str]


def fit_profile(
    points: Sequence[CorpusPoint], split: HoldoutSplit
) -> FittedGoodputProfile:
    """Fit capacity (always) and latency (when identifiable) from exactly
    the points named in `split.train_run_ids`. Points not named in either
    side of the split are simply not used — they are neither training nor
    holdout for this call, e.g. the single-point insufficient-data configs
    documented in `reports/holdout-validation.md`.
    """
    by_id: Dict[str, CorpusPoint] = {p.run_id: p for p in points}
    missing = split.train_run_ids - by_id.keys()
    if missing:
        raise ValueError(f"train run IDs not found in supplied points: {sorted(missing)}")

    train_points = [by_id[rid] for rid in split.train_run_ids]
    hw = {p.hardware_id for p in train_points}
    model = {p.model_id for p in train_points}
    cfg = {p.engine_config_id for p in train_points}
    if len(hw) > 1 or len(model) > 1 or len(cfg) > 1:
        raise ValueError(
            "training points span more than one (hardware, model, "
            f"engine-config) bucket: hardware={hw}, model={model}, "
            f"engine_config={cfg} — fleetlab fits per-config profiles only, "
            "never pooled across configs"
        )

    missing_holdout = split.holdout_run_ids - by_id.keys()
    if missing_holdout:
        raise ValueError(
            f"holdout run IDs not found in supplied points: {sorted(missing_holdout)}"
        )

    capacity_fit = fit_capacity(train_points)
    latency_fit: Optional[LatencyFit] = None
    latency_pending_reason: Optional[str] = None
    try:
        latency_fit = fit_latency(train_points, capacity_fit)
    except LatencyModelUndefined as exc:
        latency_pending_reason = str(exc)

    return FittedGoodputProfile(
        hardware_id=next(iter(hw)),
        model_id=next(iter(model)),
        engine_config_id=next(iter(cfg)),
        capacity_fit=capacity_fit,
        latency_fit=latency_fit,
        latency_pending_reason=latency_pending_reason,
        train_run_ids=split.train_run_ids,
        holdout_run_ids=split.holdout_run_ids,
    )


@dataclass(frozen=True)
class HoldoutPointReport:
    run_id: str
    offered_rate_rps: float
    actual_achieved_rps: float
    predicted_achieved_rps: float
    abs_error_rps: float
    rel_error: float
    measurement_stderr_rps: float
    # latency-model scoring — populated only when the profile has a fitted
    # latency model AND the holdout point's offered rate is below the fitted
    # capacity (the model has no finite prediction at/above C; that case is
    # recorded in latency_note, never silently clipped to a number).
    actual_e2e_p50_seconds: Optional[float] = None
    predicted_e2e_p50_seconds: Optional[float] = None
    latency_rel_error: Optional[float] = None
    latency_note: Optional[str] = None


@dataclass(frozen=True)
class HoldoutReport:
    points: tuple  # tuple[HoldoutPointReport, ...]


def evaluate_holdout(
    profile: FittedGoodputProfile, points: Sequence[CorpusPoint]
) -> HoldoutReport:
    """Score `profile` against `points`. Every point's `run_id` MUST be in
    `profile.holdout_run_ids`; any point whose `run_id` is in
    `profile.train_run_ids` raises `TrainingDataLeakageError` immediately —
    this is checked before anything else, and checked against the *profile's
    own record* of what trained it, not against whatever the caller claims,
    so it cannot be worked around by constructing a new, differently-labeled
    split.
    """
    leaked = [p.run_id for p in points if p.run_id in profile.train_run_ids]
    if leaked:
        raise TrainingDataLeakageError(
            f"refusing to compute fit quality: run ID(s) {leaked} trained "
            "this profile (docs/testing.md §4.2 — fit quality is only ever "
            "computable on holdout data, structurally, not by convention)"
        )
    unknown = [p.run_id for p in points if p.run_id not in profile.holdout_run_ids]
    if unknown:
        raise ValueError(
            f"run ID(s) {unknown} are neither this profile's training nor "
            "holdout set — cannot evaluate a fit against undeclared data"
        )
    if not points:
        raise ValueError("evaluate_holdout requires at least one holdout point")

    reports = []
    for p in points:
        predicted = predict_achieved_rps(profile.capacity_fit, p.offered_rate_rps)
        abs_err = predicted - p.achieved_rate_rps
        rel_err = abs_err / p.achieved_rate_rps

        actual_lat: Optional[float] = None
        predicted_lat: Optional[float] = None
        lat_rel: Optional[float] = None
        lat_note: Optional[str] = None
        if profile.latency_fit is not None:
            actual_lat = p.e2e_p50_seconds
            try:
                predicted_lat = predict_latency(profile.latency_fit, p.offered_rate_rps)
                lat_rel = (predicted_lat - actual_lat) / actual_lat
            except LatencyModelUndefined as exc:
                lat_note = str(exc)
        elif profile.latency_pending_reason is not None:
            lat_note = f"latency model not fitted: {profile.latency_pending_reason}"

        reports.append(
            HoldoutPointReport(
                run_id=p.run_id,
                offered_rate_rps=p.offered_rate_rps,
                actual_achieved_rps=p.achieved_rate_rps,
                predicted_achieved_rps=predicted,
                abs_error_rps=abs_err,
                rel_error=rel_err,
                measurement_stderr_rps=p.achieved_rate_stderr_rps,
                actual_e2e_p50_seconds=actual_lat,
                predicted_e2e_p50_seconds=predicted_lat,
                latency_rel_error=lat_rel,
                latency_note=lat_note,
            )
        )
    return HoldoutReport(points=tuple(reports))
