"""Achieved-throughput capacity-clamp model: `achieved_rps(offered) = min(offered, C)`.

**Derivation.** Below a config's true saturation capacity `C`, the system
delivers what is offered (`achieved ~= offered`); once offered load exceeds
`C`, admission control sheds (or queueing stalls) the excess and delivered
throughput plateaus at `C` — the standard "knee" shape of a saturation
curve, in its simplest (deterministic, one-parameter) form.

**Fitting.** One free parameter, `C`, solved by **exact weighted least
squares** (weights = inverse Poisson-counting variance per point, from
`CorpusPoint.achieved_rate_stderr_rps`). The clamp model's SSE is piecewise
quadratic in `C` with breakpoints at the training points' offered rates: for
`C` inside a segment, points with `offered <= C` predict `offered` (a
`C`-independent residual) while points with `offered > C` predict `C`, so
each segment's optimum is the weighted mean of the *clamped* points'
achieved rates. Enumerating the (at most n) segments and taking the global
minimum is exact algebra — no iterative optimizer, no `scipy` (ADR-0002;
upgraded from a single-estimate inverse-variance combination when the
ib-t008 six-point sweep landed, see the ADR's addendum — for a single
clamped training point the two methods coincide exactly, so the E2/E2b
fitted profiles are unchanged by the upgrade).

With one clamped training point the model is exactly determined
(`C = achieved` of that point): there is no residual to minimize and nothing
left over to report as a "goodness of fit" on the training data
(docs/testing.md §4.2: fit quality is only ever computable on holdout). If
*every* training point has `achieved ~= offered` (apparently underloaded),
`C` is only a *lower bound*, not identified — `fit_capacity` refuses that
case rather than silently reporting a point estimate with no basis
(`CapacityUnderdeterminedError`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Sequence, Tuple

from .corpus import CorpusPoint

# A point is only informative about capacity if achieved falls at least this
# fraction below offered — otherwise it is compatible with "no clamping
# happened here" and only bounds C from below. 1% guards against pure
# floating-point/window-convention noise while still catching genuinely
# underloaded points (e.g. offered=6, achieved=5.99 would refuse; offered=6,
# achieved=5.81 in the real E1-mock arms would also refuse — that arm's
# single point is insufficient for a fit either way, see
# docs/notes/fitting-method.md).
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


def _weighted_sse(points: Sequence[CorpusPoint], weights: Sequence[float], C: float) -> float:
    return sum(
        w * (min(p.offered_rate_rps, C) - p.achieved_rate_rps) ** 2
        for p, w in zip(points, weights)
    )


def fit_capacity(train_points: Sequence[CorpusPoint]) -> CapacityFit:
    """Fit the one-parameter capacity clamp from training points only, by
    exact weighted least squares (module docstring). The overfitting guard
    is structural: one parameter can never exceed the training-point count
    as long as at least one point is supplied, so there is no configuration
    of this function call that overfits.
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

    pts = sorted(train_points, key=lambda p: p.offered_rate_rps)
    weights = [1.0 / max(p.achieved_rate_stderr_rps, 1e-9) ** 2 for p in pts]
    offered = [p.offered_rate_rps for p in pts]
    n = len(pts)

    # Enumerate segments: for C in (offered[k-1], offered[k]], the clamped
    # set is exactly pts[k:] (offered > C). Per-segment optimum = weighted
    # mean of clamped achieved; keep it only if it falls inside its own
    # segment (self-consistency), plus the segment's boundary points as
    # fallback candidates so the global piecewise-quadratic minimum is
    # always among the candidates.
    candidates: List[Tuple[float, frozenset]] = []
    for k in range(n):  # clamped suffix pts[k:]
        suffix = pts[k:]
        wsuf = weights[k:]
        total_w = sum(wsuf)
        c_opt = sum(w * p.achieved_rate_rps for p, w in zip(suffix, wsuf)) / total_w
        lo = offered[k - 1] if k > 0 else float("-inf")
        hi = offered[k]
        clamped_ids = frozenset(p.run_id for p in suffix)
        if lo < c_opt <= hi:
            candidates.append((c_opt, clamped_ids))
        # segment boundaries (evaluated under the same clamped set; at
        # C == offered[k] the k-th point's prediction min(offered,C) is
        # continuous, so SSE is continuous across the breakpoint)
        candidates.append((hi, clamped_ids))

    best_c, best_ids = min(
        candidates, key=lambda cand: (_weighted_sse(pts, weights, cand[0]), cand[0])
    )

    # stderr: measurement error of the weighted mean over the points that
    # actually determine C at the optimum (the clamped set); for a single
    # clamped point this is exactly that point's Poisson stderr.
    clamped_weights = [
        w for p, w in zip(pts, weights) if p.run_id in best_ids and p.offered_rate_rps >= best_c
    ]
    stderr = math.sqrt(1.0 / sum(clamped_weights)) if clamped_weights else float("nan")

    return CapacityFit(
        capacity_rps=best_c,
        capacity_rps_stderr=stderr,
        train_run_ids=frozenset(p.run_id for p in train_points),
        train_source_paths=tuple(sp for p in train_points for sp in p.source_paths),
    )


def predict_achieved_rps(fit: CapacityFit, offered_rate_rps: float) -> float:
    """`min(offered, C)` — the model's only prediction."""
    return min(offered_rate_rps, fit.capacity_rps)
