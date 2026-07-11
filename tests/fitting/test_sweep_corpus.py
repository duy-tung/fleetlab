"""ib-t008 sweep corpus tests (corrected corpus scope — the six-point rate
sweep with the knee at declared 21.12 rps lives in
`inferbench/docs/evidence/ib-t008/`, see docs/notes/fitting-method.md §2)."""

import json
from pathlib import Path

import pytest

from fleetlab.fitting import load_corpus_point_from_events
from tests.fitting.conftest import SWEEP_ENGINE_CONFIG_ID, SWEEP_FIXTURES


def test_sweep_has_six_points_with_monotone_offered_rates(sweep_points):
    assert len(sweep_points) == 6
    offered = [p.offered_rate_rps for p in sweep_points]
    assert offered == sorted(offered)
    assert all(p.engine_config_id == SWEEP_ENGINE_CONFIG_ID for p in sweep_points)
    assert all(p.total_requests == 450 for p in sweep_points)  # 3 reps x 150


def test_offered_rate_is_empirical_not_declared(sweep_points):
    """The seeded schedule ran a uniform ~7.46% faster than each point's
    declared rate (same seed => same draws, scaled per point). The corpus
    point records the EMPIRICAL scheduled rate, flagged via
    offered_rate_basis, so the fit doesn't inherit the schedule bias."""
    p3 = sweep_points[3]
    assert p3.offered_rate_basis == "empirical-scheduled-send-rate"
    declared = json.loads((SWEEP_FIXTURES / "point-3-workload.json").read_text())[
        "arrival_process"
    ]["rate_rps"]
    assert declared == pytest.approx(21.122027534283404)  # the brief's "21.12 rps"
    assert p3.offered_rate_rps == pytest.approx(22.698, abs=0.01)
    assert p3.offered_rate_rps / declared == pytest.approx(1.0746, abs=0.001)


def test_low_rate_points_are_unclamped_high_rate_points_are_clamped(sweep_points):
    # below the knee: achieved tracks offered within ~1%
    for p in sweep_points[:2]:
        assert p.achieved_rate_rps == pytest.approx(p.offered_rate_rps, rel=0.01)
    # the 1.2x point is clearly clamped (~28 rps plateau, ratio ~0.78)
    p5 = sweep_points[5]
    assert p5.achieved_rate_rps / p5.offered_rate_rps < 0.85
    assert p5.achieved_rate_rps == pytest.approx(28.05, abs=0.05)


def test_latency_grows_monotonically_toward_the_knee(sweep_points):
    e2e50 = [p.e2e_p50_seconds for p in sweep_points]
    assert e2e50 == sorted(e2e50)
    # p0 ~62ms -> p5 ~460ms
    assert e2e50[0] == pytest.approx(0.0622, abs=0.002)
    assert e2e50[5] == pytest.approx(0.4600, abs=0.005)


def test_refuses_mismatched_workload_manifest_pairing():
    with pytest.raises(ValueError, match="does not match"):
        load_corpus_point_from_events(
            run_id="bad-pairing",
            events_paths=[SWEEP_FIXTURES / "point-3" / "rep-1" / "events.jsonl"],
            manifest_paths=[SWEEP_FIXTURES / "point-3" / "rep-1" / "manifest.json"],
            workload_path=SWEEP_FIXTURES / "point-2-workload.json",  # wrong point
            hardware_id="mock-loopback-cpu-dev",
            model_id="mock-8b",
            engine_config_id=SWEEP_ENGINE_CONFIG_ID,
        )


def test_knee_result_file_matches_the_sweeps_p3_declared_rate():
    """Cross-check: inferbench's own knee detection (knee-result.json,
    confidence 0.8, ttft_seconds_p99 plateau-departure) places the knee at
    sweep point 3's declared rate — the '21.12 rps knee' of the corrected
    corpus brief."""
    knee = json.loads(
        (SWEEP_FIXTURES.parent / "knee-result.json").read_text()
    )
    assert knee["arrival_rate_rps"] == pytest.approx(21.122027534283404)
    assert knee["confidence"] == 0.8
    assert knee["bracketed"] is True
