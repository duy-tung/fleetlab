"""Heterogeneous-placement mechanism (FL-T007), reduced scope.

**Scope decision, recorded per `docs/risks.md`'s pre-decided kill rule 2**
("FL-T007 heterogeneous-placement depth is reducible to two hardware
profiles"): this repo's entire measured evidence corpus covers exactly
**one** hardware bucket -- the CPU-only mock/llama.cpp loopback family used
throughout FL-T004/FL-T005/FL-T006/FL-T008. There is no second measured
hardware bucket to place across (the GPU corpus never materialized, per
`docs/risks.md` FL-L2). Per the provenance mandate ("placement reasoning is
restricted to hardware actually covered by measured profiles -- no
extrapolation to unmeasured GPUs", `docs/non-goals.md`), this module
implements the full placement MECHANISM -- tested, working code -- and
`build_placement_report.py` runs it over (a) the one measured hardware
bucket and (b) the `serving-contracts` example GPU profile
(`hardware-a10g-g5-xlarge`), clearly labeled `basis: source-reported` (its
own VRAM/price figures) or `basis: assumed`/illustrative (its capacity
figure, borrowed from a vendor illustrative fixture) throughout. (b) is a
MECHANISM DEMONSTRATION, never a placement recommendation -- enforced
structurally below (`PlacementVerdict.is_recommendation`), not just stated
in prose.

Six mechanisms, all pure/closed-form, no RNG:

1. `memory_fit` -- does a model's weights fit a hardware candidate's memory
   (VRAM for a GPU, RAM for a CPU-only host)? **Fails closed**: raises
   `MemoryCapacityUnknownError` rather than assuming a fit when the
   hardware's memory capacity was never measured/recorded (this repo's
   ingestion-refusal philosophy, `docs/architecture.md`, applied here).
2. `rank_by_goodput_per_cost` -- throughput/cost ranking (goodput per
   dollar-hour).
3. `cold_start_penalty_factor` / `cold_start_weight_candidates` -- weights a
   candidate's rank down when its cold-start delay exceeds the reaction
   window a workload's burst dynamics allow (FL-T005's measured cold-start
   figures feed this).
4. `failover_headroom_for_candidate` -- thin wrapper composing
   `fleetlab.dynamics.headroom` (reused, not reimplemented) with a placement
   candidate's fitted per-replica capacity.
5. `fragmentation` -- how many model instances pack onto one hardware node's
   memory, and how much is wasted.
6. `workload_affinity` -- does a hardware candidate's spare memory (after
   model weights) cover a given workload's typical per-request KV-cache
   footprint (reusing the model profile's `kv_cache_bytes_per_token`, itself
   the FL-T003 KV-memory-model's output)? Different workloads (short chat vs
   long-context RAG) can flip which hardware candidate is the better fit
   even when the raw goodput/cost ranking is unchanged -- planning-prompt
   hypothesis 5.

Every dataclass here carries its own `basis` (measured / source-reported /
assumed) so the report layer can label every number without re-deriving
provenance.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from fleetlab.dynamics.headroom import (
    FailureCapacityReport,
    failure_capacity,
    required_headroom_rps,
)

VALID_BASES = ("measured", "source-reported", "assumed")


class MemoryCapacityUnknownError(ValueError):
    """Raised when a hardware candidate's memory capacity (VRAM or RAM) or
    a model candidate's weight size was never measured/recorded. This
    module never assumes a fit when the denominator is missing -- the
    caller must supply the number or receive an explicit refusal, never a
    fabricated default."""


@dataclass(frozen=True)
class HardwareCandidate:
    """A placement target. `memory_gb=None` / `capacity_rps=None` /
    `usd_per_hour=None` mean "not measured/recorded", not zero -- every
    mechanism below refuses to treat a missing value as a passing check."""

    hardware_id: str
    label: str
    basis: str  # measured | source-reported | assumed
    memory_gb: Optional[float] = None
    memory_kind: Optional[str] = None  # "vram" | "ram"
    memory_basis: Optional[str] = None
    capacity_rps: Optional[float] = None
    capacity_rps_stderr: Optional[float] = None
    capacity_basis: Optional[str] = None
    usd_per_hour: Optional[float] = None
    price_basis: Optional[str] = None
    cold_start_seconds: Optional[float] = None
    cold_start_basis: Optional[str] = None
    gpu_count_per_node: Optional[int] = None

    def __post_init__(self) -> None:
        if self.basis not in VALID_BASES:
            raise ValueError(f"basis must be one of {VALID_BASES}, got {self.basis!r}")
        if self.memory_gb is not None and self.memory_gb <= 0:
            raise ValueError(f"memory_gb must be > 0 if given, got {self.memory_gb}")
        if self.capacity_rps is not None and self.capacity_rps <= 0:
            raise ValueError(f"capacity_rps must be > 0 if given, got {self.capacity_rps}")
        if self.usd_per_hour is not None and self.usd_per_hour <= 0:
            raise ValueError(f"usd_per_hour must be > 0 if given, got {self.usd_per_hour}")


@dataclass(frozen=True)
class ModelCandidate:
    model_id: str
    weights_size_gb: Optional[float] = None
    weights_basis: Optional[str] = None
    kv_cache_bytes_per_token: Optional[float] = None
    kv_cache_basis: Optional[str] = None

    def __post_init__(self) -> None:
        if self.weights_size_gb is not None and self.weights_size_gb <= 0:
            raise ValueError(f"weights_size_gb must be > 0 if given, got {self.weights_size_gb}")


# ---------------------------------------------------------------------------
# 1. model-fits-memory (generalizes "model fits VRAM" to VRAM-or-RAM)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MemoryFitResult:
    fits: bool
    required_gb: float
    available_gb: float
    headroom_gb: float
    utilization_fraction: float
    safety_margin_fraction: float


def memory_fit(
    model: ModelCandidate,
    hardware: HardwareCandidate,
    *,
    safety_margin_fraction: float = 0.0,
) -> MemoryFitResult:
    """Does `model`'s weights fit in `hardware`'s memory capacity?

    Raises `MemoryCapacityUnknownError` if either the hardware's memory
    capacity or the model's weight size was never recorded -- this is the
    sanity invariant "never place a model that doesn't fit VRAM" enforced
    as code: a caller cannot get a `fits=True` result out of missing data.
    """
    if hardware.memory_gb is None:
        raise MemoryCapacityUnknownError(
            f"hardware '{hardware.hardware_id}' has no recorded memory "
            f"capacity (basis={hardware.basis}) -- cannot evaluate whether "
            f"'{model.model_id}' fits; refusing to assume a fit."
        )
    if model.weights_size_gb is None:
        raise MemoryCapacityUnknownError(
            f"model '{model.model_id}' has no recorded weights_size_gb -- "
            "cannot evaluate memory fit; refusing to assume a fit."
        )
    if safety_margin_fraction < 0:
        raise ValueError(f"safety_margin_fraction must be >= 0, got {safety_margin_fraction}")
    required = model.weights_size_gb * (1.0 + safety_margin_fraction)
    headroom = hardware.memory_gb - required
    return MemoryFitResult(
        fits=headroom >= 0.0,
        required_gb=required,
        available_gb=hardware.memory_gb,
        headroom_gb=headroom,
        utilization_fraction=required / hardware.memory_gb,
        safety_margin_fraction=safety_margin_fraction,
    )


@dataclass(frozen=True)
class MemoryFitOutcome:
    hardware_id: str
    verdict: str  # "fits" | "does-not-fit" | "insufficient-data"
    detail: str
    result: Optional[MemoryFitResult] = None


def filter_hardware_by_memory_fit(
    model: ModelCandidate,
    hardware_candidates: Sequence[HardwareCandidate],
    *,
    safety_margin_fraction: float = 0.0,
) -> Tuple[List[Tuple[HardwareCandidate, MemoryFitResult]], List[MemoryFitOutcome]]:
    """Partitions candidates into those the model fits (with their
    `MemoryFitResult`) and everything else (rejected, with a typed reason --
    `"does-not-fit"` or `"insufficient-data"`, never silently dropped)."""
    fitting: List[Tuple[HardwareCandidate, MemoryFitResult]] = []
    rejected: List[MemoryFitOutcome] = []
    for hw in hardware_candidates:
        try:
            result = memory_fit(model, hw, safety_margin_fraction=safety_margin_fraction)
        except MemoryCapacityUnknownError as exc:
            rejected.append(MemoryFitOutcome(hw.hardware_id, "insufficient-data", str(exc)))
            continue
        if result.fits:
            fitting.append((hw, result))
        else:
            rejected.append(
                MemoryFitOutcome(
                    hw.hardware_id,
                    "does-not-fit",
                    f"requires {result.required_gb:.3f} GB > {result.available_gb:.3f} GB available",
                    result,
                )
            )
    return fitting, rejected


# ---------------------------------------------------------------------------
# 2. throughput/cost ranking
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RankedCandidate:
    hardware_id: str
    capacity_rps: float
    capacity_basis: str
    usd_per_hour: float
    price_basis: str
    goodput_per_dollar_hour: float


def rank_by_goodput_per_cost(
    hardware_candidates: Sequence[HardwareCandidate],
) -> Tuple[List[RankedCandidate], List[str]]:
    """Ranks candidates by goodput-rps-per-dollar-hour, descending.
    Candidates missing `capacity_rps` or `usd_per_hour` are excluded (their
    ids returned separately) rather than silently defaulted to zero/inf."""
    ranked: List[RankedCandidate] = []
    insufficient: List[str] = []
    for hw in hardware_candidates:
        if hw.capacity_rps is None or hw.usd_per_hour is None:
            insufficient.append(hw.hardware_id)
            continue
        ranked.append(
            RankedCandidate(
                hardware_id=hw.hardware_id,
                capacity_rps=hw.capacity_rps,
                capacity_basis=hw.capacity_basis or "unknown",
                usd_per_hour=hw.usd_per_hour,
                price_basis=hw.price_basis or "unknown",
                goodput_per_dollar_hour=hw.capacity_rps / hw.usd_per_hour,
            )
        )
    ranked.sort(key=lambda r: r.goodput_per_dollar_hour, reverse=True)
    return ranked, insufficient


# ---------------------------------------------------------------------------
# 3. cold-start weighting
# ---------------------------------------------------------------------------


def cold_start_penalty_factor(cold_start_seconds: float, reaction_window_seconds: float) -> float:
    """Fraction (<=1.0) of a workload's `reaction_window_seconds` (e.g. the
    burst-phase duration a bursty workload gives an autoscaler to react
    before backlog forms, FL-T005/FL-T006) that a `cold_start_seconds`
    replacement/scale-out delay actually fits within. `1.0` means the cold
    start comfortably fits inside the reaction window (no penalty); values
    below 1.0 scale down a candidate's rank in proportion to how far its
    cold start overruns that window -- monotonic and bounded, not a
    tuned/arbitrary curve."""
    if cold_start_seconds <= 0:
        raise ValueError(f"cold_start_seconds must be > 0, got {cold_start_seconds}")
    if reaction_window_seconds <= 0:
        raise ValueError(f"reaction_window_seconds must be > 0, got {reaction_window_seconds}")
    return min(1.0, reaction_window_seconds / cold_start_seconds)


@dataclass(frozen=True)
class ColdStartWeightedScore:
    hardware_id: str
    base_score: float
    cold_start_seconds: float
    cold_start_basis: str
    reaction_window_seconds: float
    penalty_factor: float
    weighted_score: float


def cold_start_weight_candidates(
    ranked: Sequence[RankedCandidate],
    hardware_by_id: Dict[str, HardwareCandidate],
    *,
    reaction_window_seconds: float,
) -> Tuple[List[ColdStartWeightedScore], List[str]]:
    """Re-scores `rank_by_goodput_per_cost`'s output by
    `cold_start_penalty_factor`. Candidates with no recorded cold-start
    figure are excluded (ids returned separately), never assumed to have
    zero cold-start delay."""
    weighted: List[ColdStartWeightedScore] = []
    insufficient: List[str] = []
    for r in ranked:
        hw = hardware_by_id[r.hardware_id]
        if hw.cold_start_seconds is None:
            insufficient.append(hw.hardware_id)
            continue
        penalty = cold_start_penalty_factor(hw.cold_start_seconds, reaction_window_seconds)
        weighted.append(
            ColdStartWeightedScore(
                hardware_id=r.hardware_id,
                base_score=r.goodput_per_dollar_hour,
                cold_start_seconds=hw.cold_start_seconds,
                cold_start_basis=hw.cold_start_basis or "unknown",
                reaction_window_seconds=reaction_window_seconds,
                penalty_factor=penalty,
                weighted_score=r.goodput_per_dollar_hour * penalty,
            )
        )
    weighted.sort(key=lambda w: w.weighted_score, reverse=True)
    return weighted, insufficient


# ---------------------------------------------------------------------------
# 4. failover headroom (reuses fleetlab.dynamics.headroom, not reimplemented)
# ---------------------------------------------------------------------------


def failover_headroom_for_candidate(
    hardware: HardwareCandidate, *, replica_count: int, peak_offered_rps: float
) -> Tuple[FailureCapacityReport, float]:
    """Thin composition of a placement candidate's fitted per-replica
    capacity with `fleetlab.dynamics.headroom`'s existing N-1
    failure-capacity arithmetic (FL-T005) -- no placement-specific
    reimplementation. Returns `(FailureCapacityReport, deficit_rps)`."""
    if hardware.capacity_rps is None:
        raise MemoryCapacityUnknownError(
            f"hardware '{hardware.hardware_id}' has no recorded capacity_rps "
            "-- cannot evaluate failover headroom."
        )
    report = failure_capacity(hardware.capacity_rps, replica_count)
    deficit = required_headroom_rps(peak_offered_rps, report.n_minus_1_capacity_rps)
    return report, deficit


# ---------------------------------------------------------------------------
# 5. fragmentation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FragmentationResult:
    instances_per_node: int
    used_gb: float
    wasted_gb: float
    waste_fraction: float


def fragmentation(
    model: ModelCandidate,
    hardware: HardwareCandidate,
    *,
    max_instances_per_node: Optional[int] = None,
    safety_margin_fraction: float = 0.0,
) -> FragmentationResult:
    """How many copies of `model` pack onto one `hardware` node's memory,
    and how much of that memory is left unusable. Raises
    `MemoryCapacityUnknownError` via `memory_fit` if either input is
    missing (same fail-closed rule)."""
    fit = memory_fit(model, hardware, safety_margin_fraction=safety_margin_fraction)
    instances = math.floor(hardware.memory_gb / fit.required_gb) if fit.required_gb > 0 else 0
    if max_instances_per_node is not None:
        if max_instances_per_node < 0:
            raise ValueError("max_instances_per_node must be >= 0")
        instances = min(instances, max_instances_per_node)
    used = instances * fit.required_gb
    wasted = hardware.memory_gb - used
    return FragmentationResult(
        instances_per_node=instances,
        used_gb=used,
        wasted_gb=wasted,
        waste_fraction=wasted / hardware.memory_gb,
    )


# ---------------------------------------------------------------------------
# 6. workload affinity
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WorkloadAffinityResult:
    workload_name: str
    mean_context_tokens: float
    required_kv_gb: float
    spare_after_weights_gb: float
    fits_typical_request: bool
    concurrent_requests_headroom: float


def workload_affinity(
    model: ModelCandidate,
    hardware: HardwareCandidate,
    *,
    workload_name: str,
    mean_context_tokens: float,
    safety_margin_fraction: float = 0.0,
) -> WorkloadAffinityResult:
    """Does `hardware`'s spare memory (after `model`'s weights) cover one
    typical `workload_name` request's KV-cache footprint at
    `mean_context_tokens` tokens of context? Reuses the model profile's own
    `kv_cache_bytes_per_token` (the FL-T003 KV-memory model's output),
    never re-derives it from architecture parameters here. This is the
    mechanism behind planning-prompt hypothesis 5: two workloads against
    the *same* hardware+model pairing (equal throughput/cost ranking) can
    still have different placement affinity once their context-length
    profile is accounted for."""
    if model.kv_cache_bytes_per_token is None:
        raise MemoryCapacityUnknownError(
            f"model '{model.model_id}' has no recorded kv_cache_bytes_per_token "
            "-- cannot evaluate workload affinity."
        )
    if mean_context_tokens <= 0:
        raise ValueError(f"mean_context_tokens must be > 0, got {mean_context_tokens}")
    fit = memory_fit(model, hardware, safety_margin_fraction=safety_margin_fraction)
    required_kv_gb = (model.kv_cache_bytes_per_token * mean_context_tokens) / 1e9
    spare = fit.headroom_gb
    concurrency_headroom = spare / required_kv_gb if required_kv_gb > 0 else float("inf")
    return WorkloadAffinityResult(
        workload_name=workload_name,
        mean_context_tokens=mean_context_tokens,
        required_kv_gb=required_kv_gb,
        spare_after_weights_gb=spare,
        fits_typical_request=spare >= required_kv_gb,
        concurrent_requests_headroom=concurrency_headroom,
    )


# ---------------------------------------------------------------------------
# Structural invariant: never recommend unmeasured hardware
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlacementVerdict:
    """`is_recommendation` is `True` **if and only if** the hardware
    candidate's own `basis` is `"measured"` -- this is the second sanity
    invariant ("never recommend unmeasured hardware") enforced as a field
    computed from data, not a caller-supplied flag that could be set wrong.
    Every non-measured hardware candidate is structurally a
    `demonstration_only` output."""

    hardware_id: str
    hardware_basis: str
    is_recommendation: bool
    demonstration_only: bool

    def __post_init__(self) -> None:
        expected = self.hardware_basis == "measured"
        if self.is_recommendation != expected or self.demonstration_only == expected:
            raise ValueError(
                "PlacementVerdict invariant violated: is_recommendation must "
                "equal (hardware_basis == 'measured') and demonstration_only "
                "must be its negation -- got "
                f"basis={self.hardware_basis!r}, is_recommendation="
                f"{self.is_recommendation}, demonstration_only={self.demonstration_only}"
            )


def placement_verdict(hardware: HardwareCandidate) -> PlacementVerdict:
    is_recommendation = hardware.basis == "measured"
    return PlacementVerdict(
        hardware_id=hardware.hardware_id,
        hardware_basis=hardware.basis,
        is_recommendation=is_recommendation,
        demonstration_only=not is_recommendation,
    )
