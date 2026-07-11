"""Reproducibility + sanity checks for the committed FL-T005 scenario
outputs (`reports/scenarios/*.json`, docs/testing.md §5: seeded runs must be
reproducible)."""

import json

from fleetlab.dynamics.build_scenarios import (
    build_cold_start_headroom_scenario,
    build_queue_growth_scenario,
)


def test_queue_growth_scenario_is_reproducible():
    a = build_queue_growth_scenario()
    b = build_queue_growth_scenario()
    assert a == b


def test_queue_growth_scenario_matches_committed_report_numbers():
    result = build_queue_growth_scenario()
    assert result["long_run_average_offered_rps"] == 5.6
    assert result["scenarios"]["provisioned_mu8"]["stable"] is True
    assert result["scenarios"]["underprovisioned_mu3"]["stable"] is False
    # the underprovisioned run never recovers -- late in-system count is
    # far above the provisioned run's
    assert (
        result["scenarios"]["underprovisioned_mu3"]["in_system_at_t590s"]
        > result["scenarios"]["provisioned_mu8"]["in_system_at_t590s"]
    )


def test_cold_start_headroom_scenario_is_reproducible():
    a = build_cold_start_headroom_scenario()
    b = build_cold_start_headroom_scenario()
    assert a == b


def test_cold_start_headroom_real_capacity_has_no_deficit():
    result = build_cold_start_headroom_scenario()
    assert result["real_measured_capacity_scenario"]["deficit_rps"] == 0.0


def test_cold_start_headroom_illustrative_scenario_shows_the_mechanism():
    result = build_cold_start_headroom_scenario()
    illus = result["illustrative_assumed_capacity_scenario"]
    assert illus["warm_replacement"]["deficit_rps"] == 5.0
    assert illus["cold_replacement"]["deficit_rps"] == 5.0
    # same deficit rate, but the cold replacement's cold-start window is
    # ~8.5x longer -- backlog and drain time scale by the same factor
    ratio = (
        illus["cold_replacement"]["cold_start_seconds"]
        / illus["warm_replacement"]["cold_start_seconds"]
    )
    assert 8.0 < ratio < 9.0
    backlog_ratio = (
        illus["cold_replacement"]["backlog_requests"]
        / illus["warm_replacement"]["backlog_requests"]
    )
    assert backlog_ratio == ratio
