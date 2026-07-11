"""Typed loaders for every fleetlab input file type.

Each loader: (1) parses the file, refusing unparsable content with a typed
error naming the file; (2) validates the parsed instance against the pinned
contract bundle, refusing schema violations (see `validate.py` for the
refusal taxonomy); (3) returns a lightweight, read-only view over the
validated data. Ingestion never mutates its inputs and never fills a default
for a value the file did not provide.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from .bundle import ContractBundle, default_bundle
from .errors import RecordParseError
from .validate import validate_instance


# ---------------------------------------------------------------------------
# file reading (typed parse failures)
# ---------------------------------------------------------------------------


def _read_json(path: Path) -> Any:
    text = path.read_text()
    try:
        return json.loads(text)
    except ValueError as exc:
        raise RecordParseError(path, "", "not-valid-json", str(exc)) from exc


def _read_jsonl(path: Path) -> Iterator[tuple[int, Any]]:
    text = path.read_text()
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            yield lineno, json.loads(line)
        except ValueError as exc:
            raise RecordParseError(
                path, f"line {lineno}", "not-valid-json", str(exc)
            ) from exc


# ---------------------------------------------------------------------------
# provenance value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Provenance:
    basis: str  # "measured" | "source-reported" | "assumed"
    as_of: str
    source: Optional[str] = None
    notes: Optional[str] = None


@dataclass(frozen=True)
class ProvenancedValue:
    value: float
    provenance: Provenance


def _provenance(d: dict) -> Provenance:
    return Provenance(
        basis=d["basis"],
        as_of=d["as_of"],
        source=d.get("source"),
        notes=d.get("notes"),
    )


def _pv(d: dict) -> ProvenancedValue:
    return ProvenancedValue(value=d["value"], provenance=_provenance(d["provenance"]))


def _pv_opt(d: Optional[dict]) -> Optional[ProvenancedValue]:
    return _pv(d) if d is not None else None


# ---------------------------------------------------------------------------
# Contract 3 — workload
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Workload:
    name: str
    version: str
    seed: int
    arrival_process: dict
    input_length_distribution: dict
    output_length_distribution: dict
    prefix_sharing: dict
    cancellation: dict
    slow_client: dict
    stop: dict
    description: Optional[str]
    tags: List[str]
    source_path: Path
    raw: dict


def load_workload(path: "str | Path", bundle: Optional[ContractBundle] = None) -> Workload:
    path = Path(path)
    doc = _read_json(path)
    validate_instance("workload", doc, path, bundle)
    return Workload(
        name=doc["name"],
        version=doc["version"],
        seed=doc["seed"],
        arrival_process=doc["arrival_process"],
        input_length_distribution=doc["input_length_distribution"],
        output_length_distribution=doc["output_length_distribution"],
        prefix_sharing=doc["prefix_sharing"],
        cancellation=doc["cancellation"],
        slow_client=doc["slow_client"],
        stop=doc["stop"],
        description=doc.get("description"),
        tags=doc.get("tags", []),
        source_path=path,
        raw=doc,
    )


# ---------------------------------------------------------------------------
# Contract 3 — benchmark-run manifest
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BenchmarkRunManifest:
    run_id: str
    target_topology: str
    workload_ref: dict
    engine: dict
    model: dict
    hardware: dict
    warm_up: dict
    repetitions: int
    hypothesis: str
    gateway: Optional[dict]
    source_path: Path
    raw: dict


def load_benchmark_run(
    path: "str | Path", bundle: Optional[ContractBundle] = None
) -> BenchmarkRunManifest:
    path = Path(path)
    doc = _read_json(path)
    validate_instance("benchmark-run", doc, path, bundle)
    return BenchmarkRunManifest(
        run_id=doc["run_id"],
        target_topology=doc["target_topology"],
        workload_ref=doc["workload_ref"],
        engine=doc["engine"],
        model=doc["model"],
        hardware=doc["hardware"],
        warm_up=doc["warm_up"],
        repetitions=doc["repetitions"],
        hypothesis=doc["hypothesis"],
        gateway=doc.get("gateway"),
        source_path=path,
        raw=doc,
    )


# ---------------------------------------------------------------------------
# Contract 3 — raw events (JSONL, one record per request)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RawEvent:
    run_id: str
    request_id: str
    status: str
    error_class: Optional[str]
    ttft_seconds: Optional[float]
    itl: Optional[dict]
    input_tokens: int
    output_tokens: int
    shed: bool
    retries: int
    cancellation_point: Optional[dict]
    scheduled_send_ts: str
    send_ts: str
    end_ts: str
    raw: dict


def load_raw_events(
    path: "str | Path", bundle: Optional[ContractBundle] = None
) -> List[RawEvent]:
    """Load and validate every record of a raw-event JSONL file.

    Every line is validated independently; the first schema violation raises
    a typed error naming the file and the line. A file with zero parseable
    lines is not refused by this loader (an empty raw-event file is a shape
    fleetlab has no opinion about); callers that require at least one event
    check `len(...)` themselves.
    """
    path = Path(path)
    events: List[RawEvent] = []
    for lineno, record in _read_jsonl(path):
        validate_instance("raw-event", record, f"{path}:{lineno}", bundle)
        events.append(
            RawEvent(
                run_id=record["run_id"],
                request_id=record["request_id"],
                status=record["status"],
                error_class=record.get("error_class"),
                ttft_seconds=record.get("ttft_seconds"),
                itl=record.get("itl"),
                input_tokens=record["input_tokens"],
                output_tokens=record["output_tokens"],
                shed=record["shed"],
                retries=record["retries"],
                cancellation_point=record.get("cancellation_point"),
                scheduled_send_ts=record["scheduled_send_ts"],
                send_ts=record["send_ts"],
                end_ts=record["end_ts"],
                raw=record,
            )
        )
    return events


# ---------------------------------------------------------------------------
# Contract 3 — benchmark result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BenchmarkResult:
    result_id: str
    links: dict
    throughput: dict
    pooled_percentiles: dict
    goodput: dict
    knee_estimate: Optional[dict]
    cost: Optional[dict]
    validity: dict
    source_path: Path
    raw: dict


def load_benchmark_result(
    path: "str | Path", bundle: Optional[ContractBundle] = None
) -> BenchmarkResult:
    path = Path(path)
    doc = _read_json(path)
    validate_instance("benchmark-result", doc, path, bundle)
    return BenchmarkResult(
        result_id=doc["result_id"],
        links=doc["links"],
        throughput=doc["throughput"],
        pooled_percentiles=doc["pooled_percentiles"],
        goodput=doc["goodput"],
        knee_estimate=doc.get("knee_estimate"),
        cost=doc.get("cost"),
        validity=doc["validity"],
        source_path=path,
        raw=doc,
    )


# ---------------------------------------------------------------------------
# Contract 4 — backend capability
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BackendCapability:
    engine: dict
    streaming: dict
    context_limit_tokens: int
    concurrency_hints: dict
    prefix_cache: dict
    quantization: dict
    metrics: dict
    source_path: Path
    raw: dict


def load_backend_capability(
    path: "str | Path", bundle: Optional[ContractBundle] = None
) -> BackendCapability:
    path = Path(path)
    doc = _read_json(path)
    validate_instance("backend-capability", doc, path, bundle)
    return BackendCapability(
        engine=doc["engine"],
        streaming=doc["streaming"],
        context_limit_tokens=doc["context_limit_tokens"],
        concurrency_hints=doc["concurrency_hints"],
        prefix_cache=doc["prefix_cache"],
        quantization=doc["quantization"],
        metrics=doc["metrics"],
        source_path=path,
        raw=doc,
    )


# ---------------------------------------------------------------------------
# SC-T007 fleet profiles — provenance mandatory and structural
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HardwareProfile:
    profile_id: str
    version: Optional[str]
    gpu_model: str
    count_per_node: int
    vram_gb: ProvenancedValue
    memory_bandwidth_gbps: Optional[ProvenancedValue]
    fp16_tflops: Optional[ProvenancedValue]
    node: dict
    source_path: Path
    raw: dict


def load_hardware_profile(
    path: "str | Path", bundle: Optional[ContractBundle] = None
) -> HardwareProfile:
    path = Path(path)
    doc = _read_json(path)
    validate_instance("hardware-profile", doc, path, bundle)
    gpu = doc["gpu"]
    return HardwareProfile(
        profile_id=doc["profile_id"],
        version=doc.get("version"),
        gpu_model=gpu["model"],
        count_per_node=gpu["count_per_node"],
        vram_gb=_pv(gpu["vram_gb"]),
        memory_bandwidth_gbps=_pv_opt(gpu.get("memory_bandwidth_gbps")),
        fp16_tflops=_pv_opt(gpu.get("fp16_tflops")),
        node=doc.get("node", {}),
        source_path=path,
        raw=doc,
    )


@dataclass(frozen=True)
class ModelProfile:
    profile_id: str
    version: Optional[str]
    checkpoint_id: str
    checkpoint_revision: str
    tokenizer_id: str
    parameters_billion: ProvenancedValue
    weights_size_gb: ProvenancedValue
    context_limit_tokens: ProvenancedValue
    kv_cache_bytes_per_token: Optional[ProvenancedValue]
    quantization: dict
    source_path: Path
    raw: dict


def load_model_profile(
    path: "str | Path", bundle: Optional[ContractBundle] = None
) -> ModelProfile:
    path = Path(path)
    doc = _read_json(path)
    validate_instance("model-profile", doc, path, bundle)
    return ModelProfile(
        profile_id=doc["profile_id"],
        version=doc.get("version"),
        checkpoint_id=doc["checkpoint"]["id"],
        checkpoint_revision=doc["checkpoint"]["revision"],
        tokenizer_id=doc["tokenizer"]["id"],
        parameters_billion=_pv(doc["parameters_billion"]),
        weights_size_gb=_pv(doc["weights_size_gb"]),
        context_limit_tokens=_pv(doc["context_limit_tokens"]),
        kv_cache_bytes_per_token=_pv_opt(doc.get("kv_cache_bytes_per_token")),
        quantization=doc.get("quantization", {"active": None}),
        source_path=path,
        raw=doc,
    )


@dataclass(frozen=True)
class SloObjective:
    signal: str
    statistic: str
    comparator: str
    threshold: float
    unit: str
    provenance: Provenance
    notes: Optional[str]


@dataclass(frozen=True)
class SloDefinition:
    slo_id: str
    version: str
    scope: str
    objectives: List[SloObjective]
    source_path: Path
    raw: dict


def load_slo(path: "str | Path", bundle: Optional[ContractBundle] = None) -> SloDefinition:
    path = Path(path)
    doc = _read_json(path)
    validate_instance("slo", doc, path, bundle)
    objectives = [
        SloObjective(
            signal=o["signal"],
            statistic=o["statistic"],
            comparator=o["comparator"],
            threshold=o["threshold"],
            unit=o["unit"],
            provenance=_provenance(o["provenance"]),
            notes=o.get("notes"),
        )
        for o in doc["objectives"]
    ]
    return SloDefinition(
        slo_id=doc["slo_id"],
        version=doc["version"],
        scope=doc["scope"],
        objectives=objectives,
        source_path=path,
        raw=doc,
    )


@dataclass(frozen=True)
class CostRate:
    hardware_profile_id: str
    hardware_profile_version: Optional[str]
    pricing_model: str
    region: Optional[str]
    usd_per_hour: ProvenancedValue
    notes: Optional[str]


@dataclass(frozen=True)
class CostProfile:
    profile_id: str
    version: str
    currency: str
    rates: List[CostRate]
    source_path: Path
    raw: dict


def load_cost_profile(
    path: "str | Path", bundle: Optional[ContractBundle] = None
) -> CostProfile:
    path = Path(path)
    doc = _read_json(path)
    validate_instance("cost-profile", doc, path, bundle)
    rates = [
        CostRate(
            hardware_profile_id=r["hardware_profile_ref"]["id"],
            hardware_profile_version=r["hardware_profile_ref"].get("version"),
            pricing_model=r["pricing_model"],
            region=r.get("region"),
            usd_per_hour=_pv(r["usd_per_hour"]),
            notes=r.get("notes"),
        )
        for r in doc["rates"]
    ]
    return CostProfile(
        profile_id=doc["profile_id"],
        version=doc["version"],
        currency=doc["currency"],
        rates=rates,
        source_path=path,
        raw=doc,
    )
