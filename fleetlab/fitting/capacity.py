"""Achieved-throughput capacity-clamp model: `achieved_rps(offered) = min(offered, C)`.

**Derivation.** Below a config's true saturation capacity `C`, the system
delivers what is offered (`achieved ~= offered`); once offered load exceeds
`C`, admission control sheds/stalls the excess and delivered throughput
plateaus at `C` — the standard "knee" shape of a saturation curve, in its
simplest (deterministic, one-parameter) form.

**Fitting.** One free parameter, `C`. Given one training point `(offered,
achieved)` with `achieved < offered` (i.e. the point is already at/above its
own apparent capacity), the model is exactly determined: `C = achieved` —
there is no residual to minimize, no optimizer, and nothing left over to
report as a "goodness of fit" on the training point itself (docs/testing.md
§4.2: fit quality is only ever computable on holdout). If `achieved ~=
offered` (an apparently underloaded point), `C` is only a *lower bound*, not
identified — `fit_capacity` refuses that case rather than silently reporting
a point estimate with no basis (`CapacityUnderdeterminedError`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from .corpus import CorpusPoint

# A point is only informative about capacity if achieved falls at least this
# fraction below offered — otherwise it is compatible with "no clamping
# happened here" and only bounds C from below. 1% guards against pure
# floating-point noise while still catching genuinely underloaded points
# (e.g. offered=6, achieved=5.99 would refuse; offered=6, achieved=5.81 in
# the real E1-mock arms would also refuse — that arm's single point is
# insufficient for a fit either way, see docs/notes/fitting-method.md).
_MIN_INFORMATIVE_GAP_FRACTION = 0.01


class CapacityUnderdeterminedError(ValueError):
    """Raised when every training point is compatible with 'no clamping
    happened' (achieved ~= offered): the capacity-clamp model's one
    parameter has no unique solution from such points, only a lower bound.
    """


@dataclass(frozen=True)
class CapacityFit:
    capacity_rps: float
    capacity_rps_stderr: float
    train_run_ids: frozenset
    train_source_paths: tuple
    basis: str = "measured"


def fit_capacity(train_points: Sequence[CorpusPoint]) -> CapacityFit:
    """Fit the one-parameter capacity clamp from training points only.

    With more than one training point, each point independently implies a
    capacity estimate (`C_i = achieved_i`, valid whenever `achieved_i` is
    informative per the gap test above); the fit combines them by inverse-
    variance weighting (weights from `CorpusPoint.achieved_rate_stderr_rps`,
    the Poisson-counting measurement error) — still closed-form, no
    optimizer. The overfitting guard is structural: one parameter can never
    exceed the training-point count as long as at least one point is
    supplied, so there is no configuration of this function call that
    overfits.
    """
    if not train_points:
        raise ValueError("fit_capacity requires at least one training point")

    informative = [
        p
        for p in train_points
        if p.achieved_rate_rps < p.offered_rate_rps * (1 - _MIN_INFORMATIVE_GAP_FRACTION)
    ]
    if not informative:
        raise CapacityUnderdeterminedError(
            "every training point has achieved ~= offered (no observed "
            "clamping) — this only lower-bounds capacity; refusing to "
            "report a point estimate with no basis. Supply a training point "
            "with offered load clearly above the true capacity."
        )

    weights = [1.0 / max(p.achieved_rate_stderr_rps, 1e-9) ** 2 for p in informative]
    estimates = [p.achieved_rate_rps for p in informative]
    total_weight = sum(weights)
    capacity = sum(w * c for w, c in zip(weights, estimates)) / total_weight
    # combined stderr of an inverse-variance-weighted mean
    stderr = math.sqrt(1.0 / total_weight)

    return CapacityFit(
        capacity_rps=capacity,
        capacity_rps_stderr=stderr,
        train_run_ids=frozenset(p.run_id for p in train_points),
        train_source_paths=tuple(sp for p in train_points for sp in p.source_paths),
    )


def predict_achieved_rps(fit: CapacityFit, offered_rate_rps: float) -> float:
    """`min(offered, C)` — the model's only prediction."""
    return min(offered_rate_rps, fit.capacity_rps)
