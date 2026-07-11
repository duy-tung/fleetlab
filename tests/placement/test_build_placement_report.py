"""Tests for `fleetlab.placement.build_placement_report` (FL-T007):
determinism, the two sanity invariants surfacing correctly in the wired
report, and the headline findings (hypothesis 5 workload affinity, the
measured-CPU-bucket memory-fit PENDING, the cold-start weighting demo)."""

from __future__ import annotations

import json

from fleetlab.placement.build_placement_report import build_report


def test_build_report_is_deterministic():
    a = json.dumps(build_report(), sort_keys=True)
    b = json.dumps(build_report(), sort_keys=True)
    assert a == b


def test_measured_hardware_is_a_recommendation_and_gpu_demo_is_not():
    report = build_report()
    verdicts = report["verdicts"]
    measured_id = report["candidates"]["measured_cpu"]["hardware_id"]
    gpu_id = report["candidates"]["gpu_demo"]["hardware_id"]
    assert verdicts[measured_id]["is_recommendation"] is True
    assert verdicts[gpu_id]["is_recommendation"] is False
    assert verdicts[gpu_id]["demonstration_only"] is True


def test_measured_cpu_bucket_memory_fit_is_honest_pending_not_fabricated():
    """The sole measured hardware bucket has no recorded RAM figure
    anywhere in this program's evidence -- the memory-fit mechanism must
    report this as insufficient data, never silently assume a fit."""
    report = build_report()
    result = report["memory_fit"]["measured_cpu_x_qwen"]
    assert result["fits"] == []
    assert result["rejected"][0]["verdict"] == "insufficient-data"


def test_gpu_demo_model_fits_with_positive_headroom():
    report = build_report()
    result = report["memory_fit"]["gpu_demo_x_llama31_8b"]
    assert result["rejected"] == []
    fit = result["fits"][0]
    assert fit["headroom_gb"] > 0
    assert fit["required_gb"] < fit["available_gb"]


def test_throughput_cost_ranking_excludes_the_measured_bucket_for_lack_of_price():
    report = build_report()
    ranking = report["throughput_cost_ranking"]
    measured_id = report["candidates"]["measured_cpu"]["hardware_id"]
    assert measured_id in ranking["excluded_insufficient_data"]
    assert len(ranking["ranked"]) == 1


def test_cold_start_weighting_demo_shows_cold_regime_penalized_far_below_warm():
    report = build_report()
    demo = report["cold_start_weighting_demo"]
    assert demo["warm_regime"]["penalty_factor"] == 1.0
    assert 0 < demo["cold_regime"]["penalty_factor"] < demo["warm_regime"]["penalty_factor"]


def test_failover_headroom_matches_fl_t005s_published_no_deficit_finding():
    """Cross-check against `reports/cold-start-headroom.md`'s published
    finding: the real bursty workload's 20 rps peak does not exceed this
    fitted profile's N-1 (single-replica) capacity."""
    report = build_report()
    failover = report["failover_headroom"]
    assert failover["peak_offered_rps"] == 20.0
    assert failover["headroom_deficit"] is False
    assert failover["deficit_rps"] == 0.0


def test_workload_affinity_long_context_has_far_less_concurrency_headroom():
    """Hypothesis 5: the same hardware+model pairing has very different
    placement affinity once a workload's context length is accounted for."""
    report = build_report()
    affinity = report["workload_affinity"]
    chat = affinity["chat_short"]
    rag = affinity["rag_long_in"]
    assert rag["required_kv_gb"] > chat["required_kv_gb"]
    assert rag["concurrent_requests_headroom"] < chat["concurrent_requests_headroom"]
    assert chat["fits_typical_request"] is True
    assert rag["fits_typical_request"] is True


def test_report_states_its_own_reduced_scope():
    report = build_report()
    assert "REDUCED SCOPE" in report["basis"]
    assert "MECHANISM DEMONSTRATION" in report["basis"]
