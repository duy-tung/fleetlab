"""Queueing-blowup latency model: `latency(offered) = L0 * C / (C - offered)`.

**Derivation.** Standard single-server queueing-delay shape: latency grows
without bound as offered load `offered` approaches the system's capacity `C`
from below (`M/M/1`-flavored; `docs/notes/model-validation.md` and
`fleetlab/dynamics/` use the same family for the known-answer queue-growth
limits). `L0` is a one-parameter scale (roughly, the near-empty-system
latency), fit from **one** training point whose `offered < C` (the model is
only defined there — the system has not yet saturated).

**Why this is PENDING for the two real fittable engine-configs in this
corpus (`admission-sane-v1`, `admission-sane-v1b`), not silently applied.**
Both configs' only two measured points (`1x` and `5x` the probe-estimated
capacity) each have `achieved < offered` — i.e. by the capacity model's own
fit (`fleetlab.fitting.capacity`), *both* points already sit at or above
their fitted `C`. There is no point in the corpus with `offered` measurably
below the fitted `C` for either config, so `L0` has no valid training point
to be fit from — not "insufficient precision", genuinely undefined for this
model on this data. `fit_latency` raises `LatencyModelUndefined` rather than
silently extrapolating or picking a different, unreviewed functional form.
See `reports/holdout-validation.md` for the full account and the precise
data (`docs/notes/fitting-method.md`) that would close this out: one
calibration run per engine-config at an offered rate clearly (>=20%) below
the fitted capacity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .capacity import CapacityFit
from .corpus import CorpusPoint


class LatencyModelUndefined(ValueError):
    """No training point has `offered < C`: the queueing-blowup model's
    scale parameter cannot be identified from this data."""


@dataclass(frozen=True)
class LatencyFit:
    l0_seconds: float
    l0_seconds_stderr: float
    capacity_fit: CapacityFit
    train_run_ids: frozenset
    basis: str = "measured"


def fit_latency(
    train_points: Sequence[CorpusPoint], capacity_fit: CapacityFit
) -> LatencyFit:
    """Fit `L0` from training points strictly below the given capacity fit.

    Reuses `capacity_fit` rather than re-deriving capacity from the same
    points (that would let the two "parameters" secretly share the one
    degree of freedom the corpus actually provides — the overfitting guard
    this package commits to). Raises `LatencyModelUndefined` if no training
    point qualifies.
    """
    if not train_points:
        raise ValueError("fit_latency requires at least one training point")

    C = capacity_fit.capacity_rps
    below = [p for p in train_points if p.offered_rate_rps < C]
    if not below:
        raise LatencyModelUndefined(
            f"no training point has offered_rate_rps < fitted capacity "
            f"({C:.3f} rps) — the queueing-blowup latency model is not "
            "identifiable from this data; see docs/notes/fitting-method.md "
            "for the calibration run this needs."
        )

    # one point is enough to solve L0 exactly (no residual on training data,
    # per docs/testing.md's holdout-only fit-quality rule); with more than
    # one qualifying point, average the implied L0s (still closed-form).
    l0s = [p.e2e_p50_seconds * (C - p.offered_rate_rps) / C for p in below]
    l0 = sum(l0s) / len(l0s)
    if len(l0s) > 1:
        mean = l0
        variance = sum((x - mean) ** 2 for x in l0s) / len(l0s)
        stderr = variance**0.5 / (len(l0s) ** 0.5)
    else:
        stderr = float("nan")  # single point: no internal dispersion estimate

    return LatencyFit(
        l0_seconds=l0,
        l0_seconds_stderr=stderr,
        capacity_fit=capacity_fit,
        train_run_ids=frozenset(p.run_id for p in train_points),
    )


def predict_latency(fit: LatencyFit, offered_rate_rps: float) -> float:
    """`L0 * C / (C - offered)`. Raises if `offered >= C`: the model has no
    finite prediction beyond its own fitted capacity — this is the
    documented failure mode (docs/tasks.md FL-T004 stop condition: a miss is
    a result, not something to paper over with a clipped value)."""
    C = fit.capacity_fit.capacity_rps
    if offered_rate_rps >= C:
        raise LatencyModelUndefined(
            f"offered_rate_rps={offered_rate_rps} >= fitted capacity "
            f"{C:.3f} rps — the queueing-blowup model predicts unbounded "
            "latency (division by <= 0); no finite prediction exists."
        )
    return fit.l0_seconds * C / (C - offered_rate_rps)
