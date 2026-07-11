"""Closed-form cost/capacity arithmetic (FL-T008).

Every function here is parameterized and hardware-agnostic: none of them
know about any specific GPU, mock backend, or price. `usd_per_hour` is
whatever a caller-supplied, provenance-carrying cost-profile rate says;
`goodput_rps` and `tokens_per_request` are whatever a caller-supplied fitted
profile (or measured corpus figure) says. Pure algebra, no RNG, no
iterative solve -- consistent with `fleetlab.fitting`'s "closed form over
optimizer" stance (ADR-0002) and with this repo's minimal-dependency stance
(ADR-0001): no new dependency was needed for this task either.

**"At SLO" here means the fitted queueing-blowup latency model**
(`fleetlab.fitting.latency`: `e2e_p50(offered) = l0 * C / (C - offered)`)
**inverted for offered rate at a given latency threshold** -- i.e. it
predicts e2e **p50**, not the p95/p99 a real SLO objective typically names
(`slo.schema.json`'s objectives are usually p95/p99 -- see
`profiles/examples/slo-chat-interactive.json`). Treating a p50-only model's
inversion as "goodput at SLO" for a p95-defined SLO threshold is a stated
approximation, not a rigorous claim; `build_cost_report.py` states this
explicitly wherever it uses `goodput_at_slo_rps`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence


def cost_per_second_usd(usd_per_hour: float) -> float:
    if usd_per_hour < 0:
        raise ValueError(f"usd_per_hour must be >= 0, got {usd_per_hour}")
    return usd_per_hour / 3600.0


def cost_per_request_usd(usd_per_hour: float, achieved_rps: float) -> float:
    """Cost of one successful request, assuming the hardware is dedicated
    (not shared across other workloads) and running continuously at
    `achieved_rps` -- the same assumption `benchmark-result.schema.json`'s
    `cost.per_successful_request_usd` field makes (Contract 3)."""
    if achieved_rps <= 0:
        raise ValueError(f"achieved_rps must be > 0, got {achieved_rps}")
    return cost_per_second_usd(usd_per_hour) / achieved_rps


def cost_per_1e6_tokens_usd(usd_per_hour: float, tokens_per_second: float) -> float:
    """Cost per 1,000,000 tokens processed, at a given aggregate token
    throughput. `tokens_per_second` may be output-tokens-only or
    input+output total -- the caller states which (this function is
    agnostic, matching `benchmark-result.schema.json`'s split between
    `per_million_tokens_usd` (total) and `per_million_output_tokens_usd`
    (output-only), both computed by this same formula against different
    `tokens_per_second` inputs)."""
    if tokens_per_second <= 0:
        raise ValueError(f"tokens_per_second must be > 0, got {tokens_per_second}")
    return cost_per_second_usd(usd_per_hour) / tokens_per_second * 1e6


class SloUnattainableError(ValueError):
    """Raised when a requested SLO latency threshold is at or below the
    fitted model's near-empty-system latency (`l0_seconds`) -- the queueing-
    blowup model has no offered rate (not even 0) that meets it."""


def goodput_at_slo_rps(capacity_rps: float, l0_seconds: float, slo_latency_seconds: float) -> float:
    """Max offered rate such that the fitted latency model's prediction
    stays at or below `slo_latency_seconds`, inverting
    `e2e_p50(offered) = l0 * C / (C - offered)`:

        offered = C * (1 - l0 / slo_latency_seconds)

    Raises `SloUnattainableError` if `slo_latency_seconds <= l0_seconds`
    (the model predicts latency >= l0 at ANY offered rate, including 0 --
    no achievable rate meets a threshold at or below the near-empty-system
    latency itself).
    """
    if capacity_rps <= 0:
        raise ValueError(f"capacity_rps must be > 0, got {capacity_rps}")
    if l0_seconds <= 0:
        raise ValueError(f"l0_seconds must be > 0, got {l0_seconds}")
    if slo_latency_seconds <= l0_seconds:
        raise SloUnattainableError(
            f"slo_latency_seconds={slo_latency_seconds} <= l0_seconds={l0_seconds} "
            "-- the fitted queueing-blowup model predicts latency >= l0 at "
            "every offered rate (including near-zero load), so no rate "
            "meets a threshold at or below l0 itself"
        )
    return capacity_rps * (1.0 - l0_seconds / slo_latency_seconds)


@dataclass(frozen=True)
class CostAtSloResult:
    capacity_rps: float
    l0_seconds: float
    slo_latency_seconds: float
    goodput_at_slo_rps: float
    usd_per_hour: float
    tokens_per_request: float
    cost_per_request_usd: float
    cost_per_1e6_tokens_usd: float
    pricing_model: Optional[str] = None
    price_provenance_basis: Optional[str] = None
    price_as_of: Optional[str] = None


def compute_cost_at_slo(
    *,
    capacity_rps: float,
    l0_seconds: float,
    slo_latency_seconds: float,
    usd_per_hour: float,
    tokens_per_request: float,
    pricing_model: Optional[str] = None,
    price_provenance_basis: Optional[str] = None,
    price_as_of: Optional[str] = None,
) -> CostAtSloResult:
    goodput = goodput_at_slo_rps(capacity_rps, l0_seconds, slo_latency_seconds)
    tokens_per_second = goodput * tokens_per_request
    return CostAtSloResult(
        capacity_rps=capacity_rps,
        l0_seconds=l0_seconds,
        slo_latency_seconds=slo_latency_seconds,
        goodput_at_slo_rps=goodput,
        usd_per_hour=usd_per_hour,
        tokens_per_request=tokens_per_request,
        cost_per_request_usd=cost_per_request_usd(usd_per_hour, goodput),
        cost_per_1e6_tokens_usd=cost_per_1e6_tokens_usd(usd_per_hour, tokens_per_second),
        pricing_model=pricing_model,
        price_provenance_basis=price_provenance_basis,
        price_as_of=price_as_of,
    )


@dataclass(frozen=True)
class SensitivityPoint:
    price_multiplier: float
    usd_per_hour: float
    slo_latency_seconds: float
    load_fraction_of_slo_goodput: float
    achieved_rps: float
    cost_per_1e6_tokens_usd: float
    cost_per_request_usd: float


def sensitivity_table(
    *,
    capacity_rps: float,
    l0_seconds: float,
    base_usd_per_hour: float,
    tokens_per_request: float,
    price_multipliers: Sequence[float],
    slo_latency_seconds_grid: Sequence[float],
    load_fractions: Sequence[float],
) -> List[SensitivityPoint]:
    """Deterministic closed-form sweep over price x SLO x load -- every
    combination of `price_multipliers` (applied to `base_usd_per_hour`),
    `slo_latency_seconds_grid` (each solved for its own goodput-at-SLO via
    `goodput_at_slo_rps`), and `load_fractions` (the achieved rate as a
    fraction of that SLO's goodput ceiling -- 1.0 means running exactly at
    the SLO boundary, < 1.0 means running with headroom, which lowers
    achieved throughput and therefore raises cost per token). No RNG: pure
    arithmetic, so there is nothing to seed and reproduction is exact by
    construction.
    """
    points: List[SensitivityPoint] = []
    for mult in price_multipliers:
        usd_per_hour = base_usd_per_hour * mult
        for slo in slo_latency_seconds_grid:
            goodput = goodput_at_slo_rps(capacity_rps, l0_seconds, slo)
            for frac in load_fractions:
                achieved = goodput * frac
                if achieved <= 0:
                    continue
                points.append(
                    SensitivityPoint(
                        price_multiplier=mult,
                        usd_per_hour=usd_per_hour,
                        slo_latency_seconds=slo,
                        load_fraction_of_slo_goodput=frac,
                        achieved_rps=achieved,
                        cost_per_1e6_tokens_usd=cost_per_1e6_tokens_usd(
                            usd_per_hour, achieved * tokens_per_request
                        ),
                        cost_per_request_usd=cost_per_request_usd(usd_per_hour, achieved),
                    )
                )
    return points
