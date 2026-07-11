"""Known-answer tests for `fleetlab.cost.model` (FL-T008)."""

from __future__ import annotations

import pytest

from fleetlab.cost.model import (
    SloUnattainableError,
    compute_cost_at_slo,
    cost_per_1e6_tokens_usd,
    cost_per_request_usd,
    cost_per_second_usd,
    goodput_at_slo_rps,
    sensitivity_table,
)


def test_cost_per_second_usd():
    assert cost_per_second_usd(3600.0) == pytest.approx(1.0)
    assert cost_per_second_usd(0.0) == 0.0


def test_cost_per_second_usd_rejects_negative():
    with pytest.raises(ValueError):
        cost_per_second_usd(-1.0)


def test_cost_per_request_usd_known_answer():
    # $3600/hr = $1/s; at 10 rps, each request costs $0.10
    assert cost_per_request_usd(3600.0, achieved_rps=10.0) == pytest.approx(0.10)


def test_cost_per_request_usd_rejects_non_positive_rps():
    with pytest.raises(ValueError):
        cost_per_request_usd(1.0, achieved_rps=0.0)


def test_cost_per_1e6_tokens_usd_known_answer():
    # $3600/hr = $1/s; at 1000 tokens/s, 1e6 tokens take 1000s -> $1000
    assert cost_per_1e6_tokens_usd(3600.0, tokens_per_second=1000.0) == pytest.approx(1000.0)


def test_cost_per_1e6_tokens_usd_rejects_non_positive_throughput():
    with pytest.raises(ValueError):
        cost_per_1e6_tokens_usd(1.0, tokens_per_second=0.0)


def test_goodput_at_slo_rps_known_answer():
    # C=100, l0=1, slo=2 -> offered = 100*(1 - 1/2) = 50
    assert goodput_at_slo_rps(capacity_rps=100.0, l0_seconds=1.0, slo_latency_seconds=2.0) == pytest.approx(50.0)


def test_goodput_at_slo_rps_approaches_capacity_as_slo_loosens():
    tight = goodput_at_slo_rps(100.0, 1.0, slo_latency_seconds=2.0)
    loose = goodput_at_slo_rps(100.0, 1.0, slo_latency_seconds=1000.0)
    assert loose > tight
    assert loose < 100.0
    assert loose == pytest.approx(100.0, rel=0.01)


def test_goodput_at_slo_rps_raises_when_slo_at_or_below_l0():
    with pytest.raises(SloUnattainableError):
        goodput_at_slo_rps(100.0, l0_seconds=1.0, slo_latency_seconds=1.0)
    with pytest.raises(SloUnattainableError):
        goodput_at_slo_rps(100.0, l0_seconds=1.0, slo_latency_seconds=0.5)


def test_goodput_at_slo_rps_rejects_bad_inputs():
    with pytest.raises(ValueError):
        goodput_at_slo_rps(0.0, 1.0, 2.0)
    with pytest.raises(ValueError):
        goodput_at_slo_rps(100.0, 0.0, 2.0)


def test_compute_cost_at_slo_composes_goodput_and_cost():
    result = compute_cost_at_slo(
        capacity_rps=100.0,
        l0_seconds=1.0,
        slo_latency_seconds=2.0,
        usd_per_hour=3600.0,
        tokens_per_request=100.0,
    )
    assert result.goodput_at_slo_rps == pytest.approx(50.0)
    # tokens/s = 50*100=5000; $1/s / 5000 tokens/s * 1e6 = $200 / 1e6 tokens
    assert result.cost_per_1e6_tokens_usd == pytest.approx(200.0)
    assert result.cost_per_request_usd == pytest.approx(1.0 / 50.0)


def test_sensitivity_table_grid_size_and_monotonic_price_scaling():
    points = sensitivity_table(
        capacity_rps=100.0,
        l0_seconds=1.0,
        base_usd_per_hour=3600.0,
        tokens_per_request=10.0,
        price_multipliers=[1.0, 2.0],
        slo_latency_seconds_grid=[2.0, 10.0],
        load_fractions=[1.0],
    )
    assert len(points) == 2 * 2 * 1
    p1 = next(p for p in points if p.price_multiplier == 1.0 and p.slo_latency_seconds == 2.0)
    p2 = next(p for p in points if p.price_multiplier == 2.0 and p.slo_latency_seconds == 2.0)
    # doubling price at fixed goodput exactly doubles cost per token
    assert p2.cost_per_1e6_tokens_usd == pytest.approx(p1.cost_per_1e6_tokens_usd * 2.0)


def test_sensitivity_table_slo_tightening_raises_cost_more_than_price_range(
):
    """Ties to docs/experiments.md hypothesis 4: cost is most sensitive to
    goodput near the saturation knee, not to raw price."""
    points = sensitivity_table(
        capacity_rps=100.0,
        l0_seconds=1.0,
        base_usd_per_hour=3600.0,
        tokens_per_request=10.0,
        price_multipliers=[0.5, 2.0],
        slo_latency_seconds_grid=[100.0, 1.01],
        load_fractions=[1.0],
    )
    by_key = {(p.price_multiplier, p.slo_latency_seconds): p for p in points}
    price_swing = by_key[(2.0, 100.0)].cost_per_1e6_tokens_usd / by_key[(0.5, 100.0)].cost_per_1e6_tokens_usd
    slo_swing = by_key[(0.5, 1.01)].cost_per_1e6_tokens_usd / by_key[(0.5, 100.0)].cost_per_1e6_tokens_usd
    assert price_swing == pytest.approx(4.0)  # 2.0/0.5, purely linear in price
    assert slo_swing > price_swing  # goodput-near-the-knee dominates price
