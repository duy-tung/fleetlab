"""Regenerates `reports/scenarios/placement.json` (FL-T007 deliverable):
runs the placement mechanism (`fleetlab.placement.model`) over (a) the one
measured hardware bucket this whole repo's evidence corpus covers, and (b)
one `serving-contracts` example GPU profile, per the reduced scope recorded
in `docs/risks.md` (kill rule 2) and `fleetlab/placement/model.py`'s module
docstring.

Run: `python3 -m fleetlab.placement.build_placement_report`

**Every recommendation-shaped output here that touches (b) is a mechanism
demonstration, never a placement recommendation** -- enforced structurally
via `PlacementVerdict` (a hardware candidate's `is_recommendation` field is
computed from its own `basis`, not set by this module), and stated in
`reports/placement.md`.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fleetlab.dynamics.cold_start import MEASURED_COLD_START
from fleetlab.ingest import load_cost_profile, load_hardware_profile, load_model_profile, load_workload
from fleetlab.models.length import mean_of_distribution
from fleetlab.placement.model import (
    HardwareCandidate,
    ModelCandidate,
    cold_start_penalty_factor,
    failover_headroom_for_candidate,
    filter_hardware_by_memory_fit,
    fragmentation,
    placement_verdict,
    rank_by_goodput_per_cost,
    workload_affinity,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "reports" / "scenarios"

FITTED_PROFILE_PATH = (
    REPO_ROOT
    / "profiles"
    / "fitted"
    / "mock-loopback-cpu-dev__mock-8b__gateway-mock-flags-v1-conncap2.json"
)
GPU_HARDWARE_PATH = REPO_ROOT / "profiles" / "examples" / "hardware-a10g-g5-xlarge.json"
GPU_MODEL_PATH = REPO_ROOT / "profiles" / "examples" / "model-llama31-8b.json"
GPU_COST_PATH = REPO_ROOT / "profiles" / "examples" / "cost-g5-xlarge-ondemand.json"
QWEN_MODEL_PATH = REPO_ROOT / "profiles" / "examples" / "model-qwen2.5-1.5b-instruct-gguf-q4km.json"
VENDOR_RESULT_EXAMPLE = REPO_ROOT / "vendor" / "serving-contracts-v0.2.0" / "examples" / "benchmark" / "result.json"

CHAT_SHORT_WORKLOAD = REPO_ROOT / "tests" / "golden" / "fixtures" / "real" / "workloads" / "chat-short.json"
BURSTY_WORKLOAD = REPO_ROOT / "tests" / "golden" / "fixtures" / "real" / "workloads" / "bursty.json"
RAG_LONG_IN_WORKLOAD = REPO_ROOT / "vendor" / "serving-contracts-v0.2.0" / "examples" / "workloads" / "rag-long-in.json"

AS_OF = "2026-07-11"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _workload_mean_context_tokens(path: Path) -> dict:
    workload = load_workload(path)
    mean_in = mean_of_distribution(workload.input_length_distribution)
    mean_out = mean_of_distribution(workload.output_length_distribution)
    return {
        "workload_name": workload.name,
        "path": str(path.relative_to(REPO_ROOT)),
        "sha256": _sha256_file(path),
        "mean_input_tokens": mean_in,
        "mean_output_tokens": mean_out,
        "mean_context_tokens": mean_in + mean_out,
    }


def _build_candidates():
    fitted = json.loads(FITTED_PROFILE_PATH.read_text())
    cpu_hw = HardwareCandidate(
        hardware_id=fitted["profile_id"],
        label=fitted["hardware"]["label"],
        basis="measured",
        memory_gb=None,  # never measured: local-dev-container RAM was not recorded anywhere in evidence
        capacity_rps=fitted["capacity_profile"]["capacity_rps"],
        capacity_rps_stderr=fitted["capacity_profile"]["capacity_rps_stderr"],
        capacity_basis="measured",
        usd_per_hour=None,  # no cloud billing exists for a local-dev-container; not fabricated as $0
        price_basis=None,
        cold_start_seconds=None,  # this engine's manifests all declare warm_up.policy="none"; never measured
        cold_start_basis=None,
    )

    gpu_hardware = load_hardware_profile(GPU_HARDWARE_PATH)
    gpu_cost = load_cost_profile(GPU_COST_PATH)
    on_demand = next(r for r in gpu_cost.rates if r.pricing_model == "on-demand")
    vendor_example = json.loads(VENDOR_RESULT_EXAMPLE.read_text())
    illustrative_capacity_rps = vendor_example["goodput"]["requests_per_second_meeting_slo"]

    gpu_hw = HardwareCandidate(
        hardware_id=gpu_hardware.profile_id,
        label=f"{gpu_hardware.gpu_model} ({gpu_hardware.node.get('instance_type')})",
        basis="source-reported",  # VRAM + price fields are source-reported; overall candidate is non-measured
        memory_gb=gpu_hardware.vram_gb.value,
        memory_kind="vram",
        memory_basis=gpu_hardware.vram_gb.provenance.basis,
        capacity_rps=illustrative_capacity_rps,
        capacity_rps_stderr=None,
        capacity_basis="assumed",  # borrowed from a vendor ILLUSTRATIVE fixture, not measured on this GPU
        usd_per_hour=on_demand.usd_per_hour.value,
        price_basis=on_demand.usd_per_hour.provenance.basis,
        cold_start_seconds=None,  # no GPU model-load timing exists anywhere in this program's evidence
        cold_start_basis=None,
        gpu_count_per_node=gpu_hardware.count_per_node,
    )
    return cpu_hw, gpu_hw, fitted, gpu_hardware, gpu_cost, on_demand, illustrative_capacity_rps


def _build_models():
    qwen = load_model_profile(QWEN_MODEL_PATH)
    qwen_model = ModelCandidate(
        model_id=qwen.profile_id,
        weights_size_gb=qwen.weights_size_gb.value,
        weights_basis=qwen.weights_size_gb.provenance.basis,
        kv_cache_bytes_per_token=qwen.kv_cache_bytes_per_token.value,
        kv_cache_basis=qwen.kv_cache_bytes_per_token.provenance.basis,
    )
    llama = load_model_profile(GPU_MODEL_PATH)
    llama_model = ModelCandidate(
        model_id=llama.profile_id,
        weights_size_gb=llama.weights_size_gb.value,
        weights_basis=llama.weights_size_gb.provenance.basis,
        kv_cache_bytes_per_token=llama.kv_cache_bytes_per_token.value,
        kv_cache_basis=llama.kv_cache_bytes_per_token.provenance.basis,
    )
    return qwen_model, llama_model


def build_report() -> dict:
    cpu_hw, gpu_hw, fitted, gpu_hardware, gpu_cost, on_demand, illustrative_capacity_rps = _build_candidates()
    qwen_model, llama_model = _build_models()

    verdicts = {hw.hardware_id: placement_verdict(hw).__dict__ for hw in (cpu_hw, gpu_hw)}

    # 1. memory fit -- measured CPU bucket paired with the real measured
    # (weights) model this program actually served on a CPU host (Qwen);
    # GPU demo bucket paired with the model it is already paired with
    # throughout this repo's other artifacts (Llama-3.1-8B).
    memory_fit_results = {}
    for label, model, hw in (
        ("measured_cpu_x_qwen", qwen_model, cpu_hw),
        ("gpu_demo_x_llama31_8b", llama_model, gpu_hw),
    ):
        fitting, rejected = filter_hardware_by_memory_fit(model, [hw])
        memory_fit_results[label] = {
            "model_id": model.model_id,
            "hardware_id": hw.hardware_id,
            "fits": [
                {"hardware_id": h.hardware_id, "required_gb": r.required_gb, "available_gb": r.available_gb,
                 "headroom_gb": r.headroom_gb, "utilization_fraction": r.utilization_fraction}
                for h, r in fitting
            ],
            "rejected": [
                {"hardware_id": r.hardware_id, "verdict": r.verdict, "detail": r.detail} for r in rejected
            ],
        }

    # 2. throughput/cost ranking across both candidates together
    ranked, insufficient_for_ranking = rank_by_goodput_per_cost([cpu_hw, gpu_hw])
    ranking = {
        "ranked": [r.__dict__ for r in ranked],
        "excluded_insufficient_data": insufficient_for_ranking,
        "note": (
            "the measured CPU bucket is excluded: it has a real measured "
            "capacity_rps but no usd_per_hour (a local-dev-container has no "
            "cloud billing) -- not fabricated as $0. With only one candidate "
            "carrying both figures, this mechanism has nothing real to rank "
            "against; this is itself the reduced-scope finding, not a bug."
        ),
    }

    # 3. cold-start weighting -- demonstrated on the measured CPU/llama.cpp
    # host FAMILY's own real warm-vs-cold reload regime (FL-T005), against
    # the real bursty workload's real burst-phase duration as the reaction
    # window. Not applied to either ranked candidate above (mock-loopback
    # never measured a cold start; no GPU cold-start timing exists anywhere
    # in this program) -- a separate, clearly-scoped exhibit, reusing real
    # numbers rather than inventing a reaction window or a cold-start figure.
    bursty = load_workload(BURSTY_WORKLOAD)
    burst_phase = next(p for p in bursty.arrival_process["phases"] if p["rate_rps"] == max(
        ph["rate_rps"] for ph in bursty.arrival_process["phases"]
    ))
    reaction_window_seconds = float(burst_phase["duration_seconds"])
    cold_start_demo = {
        "hardware_family": "measured CPU/llama.cpp host (inference-lab evidence/i3, same family as MEASURED_COLD_START)",
        "reaction_window_seconds": reaction_window_seconds,
        "reaction_window_source": f"{BURSTY_WORKLOAD.relative_to(REPO_ROOT)} burst-phase duration (real, IB-T003 canonical workload)",
        "warm_regime": {
            "cold_start_seconds": MEASURED_COLD_START.warm_load_seconds,
            "basis": MEASURED_COLD_START.basis,
            "penalty_factor": cold_start_penalty_factor(MEASURED_COLD_START.warm_load_seconds, reaction_window_seconds),
        },
        "cold_regime": {
            "cold_start_seconds": MEASURED_COLD_START.cold_load_seconds,
            "basis": MEASURED_COLD_START.basis,
            "penalty_factor": cold_start_penalty_factor(MEASURED_COLD_START.cold_load_seconds, reaction_window_seconds),
        },
        "source": MEASURED_COLD_START.source,
        "finding": (
            "warm reload (page cache hit) fits comfortably inside the "
            "15s burst-reaction window (penalty_factor=1.0); cold reload "
            "(page-cache-evicted) overruns it by ~6x, collapsing the "
            "mechanism's weight to ~0.16x -- the same warm/cold gap "
            "FL-T005's cold-start-headroom report found, now expressed as "
            "a placement-ranking penalty rather than a backlog figure."
        ),
    }

    # 4. failover headroom -- genuinely computed on the measured CPU bucket's
    # real fitted capacity (no GPU headroom: illustrative capacity is a
    # borrowed single figure, not a real per-replica number worth composing
    # into a failure scenario).
    replica_count = 2
    peak_rps = max(p["rate_rps"] for p in bursty.arrival_process["phases"])
    failure_report, deficit = failover_headroom_for_candidate(
        cpu_hw, replica_count=replica_count, peak_offered_rps=peak_rps
    )
    failover = {
        "hardware_id": cpu_hw.hardware_id,
        "per_replica_capacity_rps": failure_report.per_replica_capacity_rps,
        "replica_count": replica_count,
        "full_fleet_capacity_rps": failure_report.full_fleet_capacity_rps,
        "n_minus_1_capacity_rps": failure_report.n_minus_1_capacity_rps,
        "peak_offered_rps": peak_rps,
        "peak_offered_rps_source": f"{BURSTY_WORKLOAD.relative_to(REPO_ROOT)} (real, IB-T003 canonical bursty workload)",
        "deficit_rps": deficit,
        "headroom_deficit": deficit > 0,
    }

    # 5. fragmentation -- both candidates, where memory data allows
    fragmentation_results = {}
    for label, model, hw in (
        ("measured_cpu_x_qwen", qwen_model, cpu_hw),
        ("gpu_demo_x_llama31_8b", llama_model, gpu_hw),
    ):
        try:
            frag = fragmentation(model, hw, max_instances_per_node=hw.gpu_count_per_node)
            fragmentation_results[label] = {
                "instances_per_node": frag.instances_per_node,
                "used_gb": frag.used_gb,
                "wasted_gb": frag.wasted_gb,
                "waste_fraction": frag.waste_fraction,
            }
        except Exception as exc:  # MemoryCapacityUnknownError, recorded not swallowed
            fragmentation_results[label] = {"insufficient_data": str(exc)}

    # 6. workload affinity -- llama-3.1-8B on the GPU demo bucket, contrasted
    # across a short-chat workload (real, chat-short) and a long-context RAG
    # workload (vendored non-normative example fixture, rag-long-in) --
    # hypothesis 5.
    chat_short_tokens = _workload_mean_context_tokens(CHAT_SHORT_WORKLOAD)
    rag_long_in_tokens = _workload_mean_context_tokens(RAG_LONG_IN_WORKLOAD)
    affinity_results = {}
    for label, tokens in (("chat_short", chat_short_tokens), ("rag_long_in", rag_long_in_tokens)):
        result = workload_affinity(
            llama_model, gpu_hw, workload_name=tokens["workload_name"], mean_context_tokens=tokens["mean_context_tokens"]
        )
        affinity_results[label] = {
            **tokens,
            "required_kv_gb": result.required_kv_gb,
            "spare_after_weights_gb": result.spare_after_weights_gb,
            "fits_typical_request": result.fits_typical_request,
            "concurrent_requests_headroom": result.concurrent_requests_headroom,
        }

    return {
        "generated_by": "python3 -m fleetlab.placement.build_placement_report",
        "as_of": AS_OF,
        "basis": (
            "REDUCED SCOPE (docs/risks.md kill rule 2): the measured corpus "
            "covers exactly one hardware bucket. Candidate (a) below is that "
            "measured bucket; candidate (b) is a serving-contracts example "
            "GPU profile, a MECHANISM DEMONSTRATION only -- never a "
            "placement recommendation (see verdicts.*.is_recommendation, "
            "computed from each candidate's own basis field, not asserted "
            "here)."
        ),
        "candidates": {
            "measured_cpu": {
                "hardware_id": cpu_hw.hardware_id,
                "label": cpu_hw.label,
                "basis": cpu_hw.basis,
                "memory_gb": cpu_hw.memory_gb,
                "capacity_rps": cpu_hw.capacity_rps,
                "capacity_rps_stderr": cpu_hw.capacity_rps_stderr,
                "capacity_basis": cpu_hw.capacity_basis,
                "usd_per_hour": cpu_hw.usd_per_hour,
                "source_profile": str(FITTED_PROFILE_PATH.relative_to(REPO_ROOT)),
                "source_profile_sha256": _sha256_file(FITTED_PROFILE_PATH),
            },
            "gpu_demo": {
                "hardware_id": gpu_hw.hardware_id,
                "label": gpu_hw.label,
                "basis": gpu_hw.basis,
                "memory_gb": gpu_hw.memory_gb,
                "memory_basis": gpu_hw.memory_basis,
                "capacity_rps": gpu_hw.capacity_rps,
                "capacity_basis": gpu_hw.capacity_basis,
                "capacity_source": (
                    f"{VENDOR_RESULT_EXAMPLE.relative_to(REPO_ROOT)} goodput."
                    "requests_per_second_meeting_slo (vendor illustrative fixture, "
                    "'all values illustrative, no measurement claims')"
                ),
                "usd_per_hour": gpu_hw.usd_per_hour,
                "price_basis": gpu_hw.price_basis,
                "source_hardware_profile": str(GPU_HARDWARE_PATH.relative_to(REPO_ROOT)),
                "source_hardware_profile_sha256": _sha256_file(GPU_HARDWARE_PATH),
                "source_cost_profile": str(GPU_COST_PATH.relative_to(REPO_ROOT)),
                "source_cost_profile_sha256": _sha256_file(GPU_COST_PATH),
            },
        },
        "verdicts": verdicts,
        "memory_fit": memory_fit_results,
        "throughput_cost_ranking": ranking,
        "cold_start_weighting_demo": cold_start_demo,
        "failover_headroom": failover,
        "fragmentation": fragmentation_results,
        "workload_affinity": affinity_results,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report = build_report()
    out_path = OUT_DIR / "placement.json"
    out_path.write_text(json.dumps(report, indent=2) + "\n")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
