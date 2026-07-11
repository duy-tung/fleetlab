"""fleetlab.placement -- heterogeneous placement (FL-T007), reduced scope.

See `model.py`'s module docstring for the full scope-reduction rationale
(`docs/risks.md` kill rule 2) and the mechanism list. `build_placement_report`
wires the mechanism over the one measured hardware bucket plus one
serving-contracts example GPU profile (mechanism demonstration only,
structurally distinguished via `PlacementVerdict`).
"""

from .model import (
    ColdStartWeightedScore,
    FragmentationResult,
    HardwareCandidate,
    MemoryCapacityUnknownError,
    MemoryFitOutcome,
    MemoryFitResult,
    ModelCandidate,
    PlacementVerdict,
    RankedCandidate,
    WorkloadAffinityResult,
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

__all__ = [
    "ColdStartWeightedScore",
    "FragmentationResult",
    "HardwareCandidate",
    "MemoryCapacityUnknownError",
    "MemoryFitOutcome",
    "MemoryFitResult",
    "ModelCandidate",
    "PlacementVerdict",
    "RankedCandidate",
    "WorkloadAffinityResult",
    "cold_start_penalty_factor",
    "cold_start_weight_candidates",
    "failover_headroom_for_candidate",
    "filter_hardware_by_memory_fit",
    "fragmentation",
    "memory_fit",
    "placement_verdict",
    "rank_by_goodput_per_cost",
    "workload_affinity",
]
