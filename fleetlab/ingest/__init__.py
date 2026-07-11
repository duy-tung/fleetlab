"""fleetlab.ingest — schema validation + provenance enforcement (FL-T002).

Loads workload manifests, benchmark-run manifests, raw events, benchmark
results, backend-capability files, and hardware/model/SLO/cost profiles.
Validates everything against the pinned `serving-contracts` bundle
(``vendor/serving-contracts-v0.2.0``, tag v0.2.0 @ commit 484b449). Refuses —
never coerces or defaults — provenance-missing profiles, unsupported fields,
and any other schema violation, always naming the file, the field, and the
rule.
"""

from .bundle import BUNDLE_COMMIT, BUNDLE_VERSION, ContractBundle, default_bundle
from .errors import (
    IngestError,
    ProvenanceMissingError,
    RecordParseError,
    SchemaValidationError,
    UnsupportedFieldError,
)
from .loaders import (
    BackendCapability,
    BenchmarkResult,
    BenchmarkRunManifest,
    CostProfile,
    CostRate,
    HardwareProfile,
    ModelProfile,
    Provenance,
    ProvenancedValue,
    RawEvent,
    SloDefinition,
    SloObjective,
    Workload,
    load_backend_capability,
    load_benchmark_result,
    load_benchmark_run,
    load_cost_profile,
    load_hardware_profile,
    load_model_profile,
    load_raw_events,
    load_slo,
    load_workload,
)

__all__ = [
    "BUNDLE_COMMIT",
    "BUNDLE_VERSION",
    "ContractBundle",
    "default_bundle",
    "IngestError",
    "ProvenanceMissingError",
    "RecordParseError",
    "SchemaValidationError",
    "UnsupportedFieldError",
    "BackendCapability",
    "BenchmarkResult",
    "BenchmarkRunManifest",
    "CostProfile",
    "CostRate",
    "HardwareProfile",
    "ModelProfile",
    "Provenance",
    "ProvenancedValue",
    "RawEvent",
    "SloDefinition",
    "SloObjective",
    "Workload",
    "load_backend_capability",
    "load_benchmark_result",
    "load_benchmark_run",
    "load_cost_profile",
    "load_hardware_profile",
    "load_model_profile",
    "load_raw_events",
    "load_slo",
    "load_workload",
]
