"""Typed corpus points for profile fitting, built from real benchmark files.

A `CorpusPoint` is one (offered rate, measured outcome) observation for a
named (hardware, model, engine-config) bucket. It is constructed from the
same `fleetlab.ingest` loaders FL-T002 built — this package never re-parses
or re-validates the underlying files itself, and never fabricates a rate: the
offered rate comes from the workload file actually used to drive the run
(`arrival_process.rate_rps`), not from the achieved throughput.

fleetlab never generates load and never re-derives what inferbench measured;
it only reads the files inferbench and inference-lab produced.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from fleetlab.ingest import load_benchmark_result, load_benchmark_run, load_workload


@dataclass(frozen=True)
class CorpusPoint:
    """One measured (offered rate -> outcome) observation for a fitting
    bucket. `run_id` is the benchmark-result's `result_id` — the identifier
    the holdout split (docs/testing.md §4) is keyed on.
    """

    run_id: str
    hardware_id: str
    model_id: str
    engine_config_id: str
    offered_rate_rps: float
    achieved_rate_rps: float
    total_requests: int
    e2e_p50_seconds: float
    e2e_p95_seconds: float
    source_paths: tuple  # provenance: exact files this point was built from

    @property
    def achieved_rate_stderr_rps(self) -> float:
        """Poisson-counting standard error on the achieved-rate estimate:
        achieved_rps = N / window, and for a Poisson-distributed count N over
        a fixed window, Var(N) = N, so SE(rate) = sqrt(N) / window =
        achieved_rps / sqrt(N). This is a measurement-noise floor, not the
        model's prediction error — the two are compared explicitly in
        `reports/holdout-validation.md`.
        """
        if self.total_requests <= 0:
            return float("nan")
        return self.achieved_rate_rps / math.sqrt(self.total_requests)


def load_corpus_point(
    *,
    result_path: "str | Path",
    workload_path: "str | Path",
    manifest_path: "str | Path",
    hardware_id: str,
    model_id: str,
    engine_config_id: str,
) -> CorpusPoint:
    """Build one `CorpusPoint`.

    `result_path` is a `benchmark-result.schema.json` file (measured
    outcome); `workload_path` is the `workload.schema.json` file that was
    actually used to drive the run (source of the offered rate —
    `arrival_process.rate_rps`; only the single-rate open-loop-poisson shape
    is supported here, since every real fittable engine-config in the corpus
    used it); `manifest_path` is the `benchmark-run.schema.json` manifest,
    read only to assert the workload_ref actually matches the workload file
    (refuses a mismatched pairing rather than silently trusting the caller).
    """
    result = load_benchmark_result(result_path)
    workload = load_workload(workload_path)
    manifest = load_benchmark_run(manifest_path)

    ref = manifest.workload_ref
    if ref.get("name") != workload.name or ref.get("seed") != workload.seed:
        raise ValueError(
            f"{manifest_path}: workload_ref {ref} does not match the paired "
            f"workload file {workload_path} (name={workload.name!r}, "
            f"seed={workload.seed!r}) — refusing to build a corpus point "
            "from a mismatched pairing."
        )

    arrival = workload.arrival_process
    if arrival.get("type") != "open-loop-poisson" or "rate_rps" not in arrival:
        raise ValueError(
            f"{workload_path}: only single-rate open-loop-poisson workloads "
            "are supported as fitting corpus points (got "
            f"{arrival.get('type')!r}); phased/closed-loop workloads have no "
            "single offered rate to fit against."
        )

    tables = result.pooled_percentiles.get("tables", {})
    e2e = tables.get("e2e_duration_seconds", {})

    return CorpusPoint(
        run_id=result.result_id,
        hardware_id=hardware_id,
        model_id=model_id,
        engine_config_id=engine_config_id,
        offered_rate_rps=float(arrival["rate_rps"]),
        achieved_rate_rps=float(result.throughput["requests_per_second"]),
        total_requests=int(result.throughput["total_requests"]),
        e2e_p50_seconds=float(e2e["p50"]),
        e2e_p95_seconds=float(e2e["p95"]),
        source_paths=(
            str(Path(result_path)),
            str(Path(workload_path)),
            str(Path(manifest_path)),
        ),
    )
