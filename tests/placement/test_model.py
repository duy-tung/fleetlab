"""Known-answer + sanity-invariant tests for `fleetlab.placement.model`
(FL-T007). The two sanity invariants named in `docs/tasks.md` --
"never place a model that doesn't fit VRAM" and "never recommend unmeasured
hardware" -- are asserted directly against the code's behavior, not read off
a report."""

from __future__ import annotations

import pytest

from fleetlab.placement.model import (
    ColdStartWeightedScore,
    HardwareCandidate,
    MemoryCapacityUnknownError,
    ModelCandidate,
    PlacementVerdict,
    RankedCandidate,
    cold_start_penalty_factor,
    cold_start_weight_candidates,
    failover_headroom_for_candidate,
    filter_hardware_by_memory_fit,
    fragmentation,
    memory_fit,
    placement_verdict,
    rank_by_goodput_per_cost,
    workload_affinity,
)


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


def gpu_24gb():
    return HardwareCandidate(
        hardware_id="hw-gpu-24gb",
        label="24 GB GPU",
        basis="source-reported",
        memory_gb=24.0,
        memory_kind="vram",
        memory_basis="source-reported",
        capacity_rps=10.0,
        capacity_basis="assumed",
        usd_per_hour=1.0,
        price_basis="source-reported",
        cold_start_seconds=60.0,
        cold_start_basis="assumed",
    )


def cpu_no_memory_data():
    return HardwareCandidate(
        hardware_id="hw-cpu-measured",
        label="measured CPU host",
        basis="measured",
        memory_gb=None,
        capacity_rps=26.157,
        capacity_basis="measured",
        usd_per_hour=None,
    )


def model_16gb():
    return ModelCandidate(
        model_id="model-16gb",
        weights_size_gb=16.1,
        weights_basis="source-reported",
        kv_cache_bytes_per_token=131072,
        kv_cache_basis="source-reported",
    )


def model_no_weights():
    return ModelCandidate(model_id="model-unknown")


# ---------------------------------------------------------------------------
# 1. memory_fit / invariant "never place a model that doesn't fit"
# ---------------------------------------------------------------------------


def test_memory_fit_known_answer():
    result = memory_fit(model_16gb(), gpu_24gb())
    assert result.fits is True
    assert result.required_gb == pytest.approx(16.1)
    assert result.headroom_gb == pytest.approx(24.0 - 16.1)
    assert result.utilization_fraction == pytest.approx(16.1 / 24.0)


def test_memory_fit_rejects_when_too_large():
    huge = ModelCandidate(model_id="huge", weights_size_gb=40.0)
    result = memory_fit(huge, gpu_24gb())
    assert result.fits is False
    assert result.headroom_gb < 0


def test_memory_fit_safety_margin_can_flip_a_marginal_fit():
    # 20 GB model on 24 GB hardware fits with no margin...
    marginal = ModelCandidate(model_id="marginal", weights_size_gb=20.0)
    assert memory_fit(marginal, gpu_24gb()).fits is True
    # ...but not with a 25% safety margin (20 * 1.25 = 25 > 24).
    assert memory_fit(marginal, gpu_24gb(), safety_margin_fraction=0.25).fits is False


def test_memory_fit_raises_when_hardware_memory_unknown():
    """The sanity invariant, as an exception: a hardware candidate with no
    recorded memory capacity can never produce a `fits=True` result --
    the function refuses to evaluate at all."""
    with pytest.raises(MemoryCapacityUnknownError):
        memory_fit(model_16gb(), cpu_no_memory_data())


def test_memory_fit_raises_when_model_weights_unknown():
    with pytest.raises(MemoryCapacityUnknownError):
        memory_fit(model_no_weights(), gpu_24gb())


def test_filter_hardware_by_memory_fit_partitions_correctly():
    huge = ModelCandidate(model_id="huge", weights_size_gb=40.0)
    fitting, rejected = filter_hardware_by_memory_fit(
        model_16gb(), [gpu_24gb(), cpu_no_memory_data()]
    )
    assert [hw.hardware_id for hw, _ in fitting] == ["hw-gpu-24gb"]
    assert [r.hardware_id for r in rejected] == ["hw-cpu-measured"]
    assert rejected[0].verdict == "insufficient-data"

    fitting2, rejected2 = filter_hardware_by_memory_fit(huge, [gpu_24gb()])
    assert fitting2 == []
    assert rejected2[0].verdict == "does-not-fit"


def test_hardware_candidate_rejects_non_positive_optional_fields():
    with pytest.raises(ValueError):
        HardwareCandidate(hardware_id="bad", label="x", basis="measured", memory_gb=0.0)
    with pytest.raises(ValueError):
        HardwareCandidate(hardware_id="bad", label="x", basis="measured", capacity_rps=-1.0)


def test_hardware_candidate_rejects_unknown_basis():
    with pytest.raises(ValueError):
        HardwareCandidate(hardware_id="bad", label="x", basis="vibes")


# ---------------------------------------------------------------------------
# 2. throughput/cost ranking
# ---------------------------------------------------------------------------


def test_rank_by_goodput_per_cost_known_answer():
    cheap_fast = HardwareCandidate(
        hardware_id="a", label="a", basis="measured", capacity_rps=20.0, usd_per_hour=1.0
    )
    pricey_faster = HardwareCandidate(
        hardware_id="b", label="b", basis="measured", capacity_rps=30.0, usd_per_hour=3.0
    )
    ranked, insufficient = rank_by_goodput_per_cost([cheap_fast, pricey_faster])
    assert insufficient == []
    # a: 20 rps/$ , b: 10 rps/$ -> a ranks first
    assert [r.hardware_id for r in ranked] == ["a", "b"]
    assert ranked[0].goodput_per_dollar_hour == pytest.approx(20.0)
    assert ranked[1].goodput_per_dollar_hour == pytest.approx(10.0)


def test_rank_by_goodput_per_cost_excludes_incomplete_candidates():
    complete = HardwareCandidate(
        hardware_id="a", label="a", basis="measured", capacity_rps=20.0, usd_per_hour=1.0
    )
    no_price = HardwareCandidate(hardware_id="b", label="b", basis="measured", capacity_rps=30.0)
    ranked, insufficient = rank_by_goodput_per_cost([complete, no_price])
    assert [r.hardware_id for r in ranked] == ["a"]
    assert insufficient == ["b"]


# ---------------------------------------------------------------------------
# 3. cold-start weighting
# ---------------------------------------------------------------------------


def test_cold_start_penalty_factor_known_answer():
    # cold start fits well within the reaction window -> no penalty
    assert cold_start_penalty_factor(cold_start_seconds=5.0, reaction_window_seconds=60.0) == 1.0
    # cold start is exactly double the reaction window -> half-strength
    assert cold_start_penalty_factor(cold_start_seconds=120.0, reaction_window_seconds=60.0) == pytest.approx(0.5)


def test_cold_start_penalty_factor_rejects_non_positive_inputs():
    with pytest.raises(ValueError):
        cold_start_penalty_factor(0.0, 60.0)
    with pytest.raises(ValueError):
        cold_start_penalty_factor(5.0, 0.0)


def test_cold_start_weight_candidates_reorders_when_penalty_dominates():
    fast_slow_start = HardwareCandidate(
        hardware_id="fast-cold",
        label="fast-cold",
        basis="measured",
        capacity_rps=100.0,
        usd_per_hour=1.0,
        cold_start_seconds=300.0,  # far exceeds the 15s reaction window
        cold_start_basis="measured",
    )
    slower_but_warm = HardwareCandidate(
        hardware_id="slow-fast-start",
        label="slow-fast-start",
        basis="measured",
        capacity_rps=50.0,
        usd_per_hour=1.0,
        cold_start_seconds=2.0,
        cold_start_basis="measured",
    )
    ranked, _ = rank_by_goodput_per_cost([fast_slow_start, slower_but_warm])
    assert ranked[0].hardware_id == "fast-cold"  # base ranking: 100 > 50 rps/$

    by_id = {"fast-cold": fast_slow_start, "slow-fast-start": slower_but_warm}
    weighted, insufficient = cold_start_weight_candidates(ranked, by_id, reaction_window_seconds=15.0)
    assert insufficient == []
    # fast-cold's penalty (15/300=0.05) flips the ranking below slow-fast-start's (1.0)
    assert weighted[0].hardware_id == "slow-fast-start"
    assert isinstance(weighted[0], ColdStartWeightedScore)


def test_cold_start_weight_candidates_excludes_unknown_cold_start():
    ranked = [
        RankedCandidate(
            hardware_id="no-cold-start-data",
            capacity_rps=10.0,
            capacity_basis="measured",
            usd_per_hour=1.0,
            price_basis="measured",
            goodput_per_dollar_hour=10.0,
        )
    ]
    hw = HardwareCandidate(hardware_id="no-cold-start-data", label="x", basis="measured", capacity_rps=10.0, usd_per_hour=1.0)
    weighted, insufficient = cold_start_weight_candidates(ranked, {"no-cold-start-data": hw}, reaction_window_seconds=15.0)
    assert weighted == []
    assert insufficient == ["no-cold-start-data"]


# ---------------------------------------------------------------------------
# 4. failover headroom (composition with fleetlab.dynamics.headroom)
# ---------------------------------------------------------------------------


def test_failover_headroom_for_candidate_composes_dynamics_headroom():
    hw = HardwareCandidate(hardware_id="a", label="a", basis="measured", capacity_rps=10.0)
    report, deficit = failover_headroom_for_candidate(hw, replica_count=3, peak_offered_rps=25.0)
    assert report.full_fleet_capacity_rps == pytest.approx(30.0)
    assert report.n_minus_1_capacity_rps == pytest.approx(20.0)
    assert deficit == pytest.approx(5.0)  # 25 - 20


def test_failover_headroom_raises_when_capacity_unknown():
    hw = HardwareCandidate(hardware_id="a", label="a", basis="measured")
    with pytest.raises(MemoryCapacityUnknownError):
        failover_headroom_for_candidate(hw, replica_count=2, peak_offered_rps=10.0)


# ---------------------------------------------------------------------------
# 5. fragmentation
# ---------------------------------------------------------------------------


def test_fragmentation_known_answer():
    # 24 GB / 16.1 GB -> floor(1.49) = 1 instance, 7.9 GB wasted
    result = fragmentation(model_16gb(), gpu_24gb())
    assert result.instances_per_node == 1
    assert result.used_gb == pytest.approx(16.1)
    assert result.wasted_gb == pytest.approx(24.0 - 16.1)
    assert result.waste_fraction == pytest.approx((24.0 - 16.1) / 24.0)


def test_fragmentation_multiple_instances_pack_tightly():
    small_model = ModelCandidate(model_id="small", weights_size_gb=6.0)
    result = fragmentation(small_model, gpu_24gb())
    assert result.instances_per_node == 4
    assert result.wasted_gb == pytest.approx(0.0, abs=1e-9)


def test_fragmentation_respects_max_instances_per_node_cap():
    small_model = ModelCandidate(model_id="small", weights_size_gb=6.0)
    result = fragmentation(small_model, gpu_24gb(), max_instances_per_node=1)
    assert result.instances_per_node == 1
    assert result.wasted_gb == pytest.approx(18.0)


def test_fragmentation_propagates_memory_capacity_unknown():
    with pytest.raises(MemoryCapacityUnknownError):
        fragmentation(model_16gb(), cpu_no_memory_data())


# ---------------------------------------------------------------------------
# 6. workload affinity (hypothesis 5)
# ---------------------------------------------------------------------------


def test_workload_affinity_short_chat_fits_comfortably():
    result = workload_affinity(
        model_16gb(), gpu_24gb(), workload_name="chat-short", mean_context_tokens=320.0
    )
    # required_kv_gb = 131072 bytes/token * 320 tokens / 1e9 = 0.0419 GB
    assert result.required_kv_gb == pytest.approx(131072 * 320 / 1e9)
    assert result.fits_typical_request is True
    assert result.concurrent_requests_headroom > 100  # tons of headroom at this context length


def test_workload_affinity_long_context_can_flip_the_verdict():
    """Same hardware+model pairing (equal throughput/cost ranking); a
    long-context workload (rag-long-in-style, ~12000 tokens) leaves far
    less concurrency headroom than chat-short at ~320 tokens -- the
    mechanism behind planning-prompt hypothesis 5."""
    short = workload_affinity(model_16gb(), gpu_24gb(), workload_name="chat-short", mean_context_tokens=320.0)
    long = workload_affinity(model_16gb(), gpu_24gb(), workload_name="rag-long-in", mean_context_tokens=12000.0)
    assert long.required_kv_gb > short.required_kv_gb
    assert long.concurrent_requests_headroom < short.concurrent_requests_headroom
    assert long.fits_typical_request is True  # still fits one request, just far less concurrency room


def test_workload_affinity_raises_when_kv_cache_bytes_unknown():
    no_kv = ModelCandidate(model_id="no-kv", weights_size_gb=1.0)
    with pytest.raises(MemoryCapacityUnknownError):
        workload_affinity(no_kv, gpu_24gb(), workload_name="chat-short", mean_context_tokens=320.0)


def test_workload_affinity_rejects_non_positive_context():
    with pytest.raises(ValueError):
        workload_affinity(model_16gb(), gpu_24gb(), workload_name="chat-short", mean_context_tokens=0.0)


# ---------------------------------------------------------------------------
# structural invariant: never recommend unmeasured hardware
# ---------------------------------------------------------------------------


def test_placement_verdict_measured_hardware_is_a_recommendation():
    verdict = placement_verdict(cpu_no_memory_data())
    assert verdict.is_recommendation is True
    assert verdict.demonstration_only is False


def test_placement_verdict_unmeasured_hardware_is_never_a_recommendation():
    for basis in ("source-reported", "assumed"):
        hw = HardwareCandidate(hardware_id="x", label="x", basis=basis)
        verdict = placement_verdict(hw)
        assert verdict.is_recommendation is False
        assert verdict.demonstration_only is True


def test_placement_verdict_construction_enforces_its_own_invariant():
    """Even a hand-constructed `PlacementVerdict` (bypassing
    `placement_verdict()`) cannot claim a recommendation for unmeasured
    hardware -- the invariant lives in `__post_init__`, not just in the one
    helper function."""
    with pytest.raises(ValueError):
        PlacementVerdict(
            hardware_id="x",
            hardware_basis="assumed",
            is_recommendation=True,
            demonstration_only=False,
        )
    with pytest.raises(ValueError):
        PlacementVerdict(
            hardware_id="x",
            hardware_basis="measured",
            is_recommendation=False,
            demonstration_only=True,
        )
