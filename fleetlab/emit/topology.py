"""Closed-form replica-count / goodput / uncertainty arithmetic (FL-T009).

Pure, hardware-agnostic functions (no RNG, consistent with
`fleetlab.cost.model`'s "closed form over optimizer" stance): every input is
caller-supplied (a fitted profile's own numbers), nothing here knows about
any specific engine-config. The one modeling choice baked in throughout is
the **linear replica-scaling assumption** (fleet capacity = replica_count x
per-replica capacity, no cross-replica routing-imbalance penalty) -- stated
explicitly wherever it is used, because this program's evidence corpus has
no multi-replica benchmark to validate it against (`docs/notes/
fitting-method.md`; `docs/risks.md` FL-L1/scale-up assumption).

The uncertainty helpers below are the mechanism behind FL-T009's
"structurally required uncertainty ... populate from the fitted profile's
real error bars": callers pass in a fitted profile's own `capacity_rps`,
`capacity_rps_stderr`, and (when available) a G8 holdout's own observed
relative extrapolation error -- never an invented margin.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


def recommend_replica_count(
    demand_rps: float,
    per_replica_capacity_rps: float,
    *,
    safety_margin_fraction: float = 0.0,
) -> int:
    """Smallest integer replica count whose linear-scaled fleet capacity
    meets `demand_rps`, after reserving `safety_margin_fraction` of each
    replica's capacity as headroom (0.0 = size exactly to demand)."""
    if demand_rps <= 0:
        raise ValueError(f"demand_rps must be > 0, got {demand_rps}")
    if per_replica_capacity_rps <= 0:
        raise ValueError(f"per_replica_capacity_rps must be > 0, got {per_replica_capacity_rps}")
    if not (0.0 <= safety_margin_fraction < 1.0):
        raise ValueError(f"safety_margin_fraction must be in [0, 1), got {safety_margin_fraction}")
    usable_capacity = per_replica_capacity_rps * (1.0 - safety_margin_fraction)
    return math.ceil(demand_rps / usable_capacity)


def fleet_capacity_rps(replica_count: int, per_replica_capacity_rps: float) -> float:
    """Linear-scaling fleet capacity -- the stated assumption every caller
    of this function must disclose (no imbalance/routing penalty modeled;
    this program has no multi-replica benchmark to fit one from)."""
    if replica_count < 1:
        raise ValueError(f"replica_count must be >= 1, got {replica_count}")
    if per_replica_capacity_rps <= 0:
        raise ValueError(f"per_replica_capacity_rps must be > 0, got {per_replica_capacity_rps}")
    return replica_count * per_replica_capacity_rps


def predicted_goodput_rps(demand_rps: float, fleet_capacity_rps_value: float) -> float:
    """Closed-form goodput: `min(demand, fleet_capacity)` -- the same
    capacity-clamp functional form `fleetlab.fitting.capacity` fits from
    real data, applied here at the fleet level."""
    if demand_rps <= 0:
        raise ValueError(f"demand_rps must be > 0, got {demand_rps}")
    if fleet_capacity_rps_value <= 0:
        raise ValueError(f"fleet_capacity_rps_value must be > 0, got {fleet_capacity_rps_value}")
    return min(demand_rps, fleet_capacity_rps_value)


@dataclass(frozen=True)
class GoodputUncertainty:
    value: float
    lower: float
    upper: float
    method: str


def goodput_uncertainty(
    *,
    demand_rps: float,
    replica_count: int,
    per_replica_capacity_rps: float,
    per_replica_capacity_stderr: Optional[float] = None,
    holdout_relative_error: Optional[float] = None,
) -> GoodputUncertainty:
    """Predicted goodput at the recommended topology, with an uncertainty
    interval grounded in the fitted profile's own real error bars:

    - `value` = `min(demand, replica_count x per_replica_capacity)` (the
      point estimate, linear-scaling assumption disclosed by the caller).
    - `upper` = `value` itself -- goodput cannot exceed offered demand in
      this closed-form model, so the point estimate is already the
      structural ceiling.
    - `lower` = `value` scaled down by the LARGER of (a) the per-replica
      capacity's own fit stderr (as a relative fraction) and (b) a supplied
      G8 holdout relative extrapolation error (`|rel_error|` from
      `reports/holdout-validation.md` for this exact profile/regime, when
      one exists) -- i.e. the most pessimistic *real, published* evidence
      about how wrong this profile's extrapolation has been shown to be,
      never an invented margin. At least one of the two must be supplied.
    """
    if per_replica_capacity_stderr is None and holdout_relative_error is None:
        raise ValueError(
            "at least one of per_replica_capacity_stderr or "
            "holdout_relative_error must be supplied -- an uncertainty "
            "interval with no real error-bar basis is not permitted"
        )
    capacity = fleet_capacity_rps(replica_count, per_replica_capacity_rps)
    value = predicted_goodput_rps(demand_rps, capacity)

    relative_terms = []
    if per_replica_capacity_stderr is not None:
        if per_replica_capacity_stderr < 0:
            raise ValueError("per_replica_capacity_stderr must be >= 0")
        relative_terms.append(per_replica_capacity_stderr / per_replica_capacity_rps)
    if holdout_relative_error is not None:
        relative_terms.append(abs(holdout_relative_error))
    dominant_relative_error = max(relative_terms)

    lower = max(0.0, value * (1.0 - dominant_relative_error))
    method = (
        f"point estimate = min(demand, replica_count x fitted capacity_rps), "
        f"linear-scaling assumption; lower bound applies this profile's own "
        f"largest documented relative error ({dominant_relative_error:.4f}) "
        f"to the per-replica capacity ("
        + (
            f"fit stderr={per_replica_capacity_stderr}"
            if per_replica_capacity_stderr is not None
            else ""
        )
        + (
            (", " if per_replica_capacity_stderr is not None else "")
            + f"G8 holdout |rel_error|={holdout_relative_error}"
            if holdout_relative_error is not None
            else ""
        )
        + "); upper bound is demand-capped since goodput cannot exceed offered load "
        "in this closed-form model."
    )
    return GoodputUncertainty(value=value, lower=lower, upper=value, method=method)
