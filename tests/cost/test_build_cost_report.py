"""Tests for `fleetlab.cost.build_cost_report` (FL-T008): determinism, the
recompute check against the one benchmark-result in this repo's evidence
with a non-null cost block, and the price-vs-SLO sensitivity finding."""

from __future__ import annotations

import json

import pytest

from fleetlab.cost.build_cost_report import build_report


def test_build_report_is_deterministic():
    a = json.dumps(build_report(), sort_keys=True)
    b = json.dumps(build_report(), sort_keys=True)
    assert a == b


def test_recompute_check_against_vendor_example_is_close():
    report = build_report()
    check = report["recompute_check_vs_vendor_example"]
    assert abs(check["rel_error"]) < 0.01  # within 1% of the stated figure


def test_cost_at_slo_has_both_pricing_models_with_provenance():
    report = build_report()
    on_demand = report["cost_at_slo"]["on_demand"]
    spot = report["cost_at_slo"]["spot"]
    assert on_demand["price_provenance_basis"] == "source-reported"
    assert spot["price_provenance_basis"] == "assumed"
    # spot is cheaper -> lower cost per token, same goodput (same SLO/profile)
    assert spot["cost_per_1e6_tokens_usd"] < on_demand["cost_per_1e6_tokens_usd"]
    assert spot["goodput_at_slo_rps"] == on_demand["goodput_at_slo_rps"]


def test_measured_tokens_per_request_is_positive_and_labeled_measured():
    report = build_report()
    tokens = report["measured_tokens_per_request"]
    assert tokens["mean_total_tokens"] > 0
    assert tokens["n_ok_events"] > 0
    assert "measured" in tokens["source"]


def test_sensitivity_slo_tightening_dominates_price_range():
    """The published finding (docs/experiments.md hypothesis 4): tightening
    SLO toward the fitted l0 raises cost per token by more than the full
    price sensitivity range (0.5x-2.0x, i.e. a 4x band) does."""
    report = build_report()
    points = report["sensitivity"]["points"]
    by_key = {
        (p["price_multiplier"], p["slo_latency_seconds"], p["load_fraction_of_slo_goodput"]): p
        for p in points
    }
    slo_grid = report["sensitivity"]["grid"]["slo_latency_seconds_grid"]
    loosest_slo, tightest_slo = slo_grid[0], slo_grid[-1]

    price_low = by_key[(0.5, loosest_slo, 1.0)]["cost_per_1e6_tokens_usd"]
    price_high = by_key[(2.0, loosest_slo, 1.0)]["cost_per_1e6_tokens_usd"]
    price_swing = price_high / price_low

    slo_loose = by_key[(1.0, loosest_slo, 1.0)]["cost_per_1e6_tokens_usd"]
    slo_tight = by_key[(1.0, tightest_slo, 1.0)]["cost_per_1e6_tokens_usd"]
    slo_swing = slo_tight / slo_loose

    assert price_swing == pytest.approx(4.0)
    assert slo_swing > price_swing
