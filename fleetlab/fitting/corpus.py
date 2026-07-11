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
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

import numpy as np

from fleetlab.ingest import (
    load_benchmark_result,
    load_benchmark_run,
    load_raw_events,
    load_workload,
)


@dataclass(frozen=True)
class CorpusPoint:
    """One measured (offered rate -> outcome) observation for a fitting
    bucket. `run_id` is the benchmark-result's `result_id` (or a caller-
    supplied point ID for raw-events-based points) — the identifier the
    holdout split (docs/testing.md §4) is keyed on.
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
    # how offered_rate_rps was determined: the workload file's declared
    # rate_rps, or the empirical scheduled-send rate measured from the raw
    # events themselves (see load_corpus_point_from_events for why the
    # empirical basis exists)
    offered_rate_basis: str = "workload-declared-rate_rps"

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


def _ts(value: str) -> float:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def load_corpus_point_from_events(
    *,
    run_id: str,
    events_paths: Sequence["str | Path"],
    manifest_paths: Sequence["str | Path"],
    workload_path: "str | Path",
    hardware_id: str,
    model_id: str,
    engine_config_id: str,
) -> CorpusPoint:
    """Build one `CorpusPoint` from raw events directly, for runs (like the
    ib-t008 sweep) that ship kit-valid raw events + manifests but no
    aggregated `benchmark-result.json`.

    `events_paths`/`manifest_paths` are the per-repetition file pairs of one
    sweep point (same workload, repeated); repetitions are pooled the way
    the program's percentile rule requires (pooled raw samples, never
    averaged percentiles). Every manifest's `workload_ref` must match the
    workload file (mismatched pairings refuse, as in `load_corpus_point`).

    **Offered rate is empirical, not declared.** The offered rate is
    computed from the events' own `scheduled_send_ts` schedule:
    `(n - 1) / (last_scheduled - first_scheduled)` per repetition, pooled.
    Rationale (measured, ib-t008): the sweep's seeded schedule happened to
    run a uniform 7.46% faster than each point's declared `rate_rps` (same
    seed at every point -> same exponential draws, scaled per point — a
    schedule-realization artifact, not noise). Fitting against the declared
    rate would bake that bias into every fitted parameter; the events record
    what was *actually* offered, so that is what the fit uses. The declared
    rate remains available via the workload file in `source_paths`, and
    `offered_rate_basis` on the returned point says which basis was used.

    Achieved rate = ok-event count / measured window (first scheduled send
    to last end), summed over repetitions — the same convention inferbench's
    own `requests_per_second` uses. Latency percentiles are pooled e2e
    durations on the `scheduled_send_ts` basis (Contract 2's coordinated-
    omission-safe measurement point, identical to `fleetlab.models.token_rate`).
    """
    if len(events_paths) != len(manifest_paths) or not events_paths:
        raise ValueError(
            "events_paths and manifest_paths must be non-empty and pairwise "
            "matched per repetition"
        )

    workload = load_workload(workload_path)
    arrival = workload.arrival_process
    if arrival.get("type") != "open-loop-poisson" or "rate_rps" not in arrival:
        raise ValueError(
            f"{workload_path}: only single-rate open-loop-poisson workloads "
            "are supported as fitting corpus points."
        )

    total_ok = 0
    total_events = 0
    achieved_window = 0.0
    sched_gap_count = 0
    sched_gap_seconds = 0.0
    e2e_pooled = []

    for events_path, manifest_path in zip(events_paths, manifest_paths):
        manifest = load_benchmark_run(manifest_path)
        ref = manifest.workload_ref
        if ref.get("name") != workload.name or ref.get("seed") != workload.seed:
            raise ValueError(
                f"{manifest_path}: workload_ref {ref} does not match the "
                f"paired workload file {workload_path} (name={workload.name!r}, "
                f"seed={workload.seed!r}) — refusing to build a corpus point "
                "from a mismatched pairing."
            )
        events = load_raw_events(events_path)
        if len(events) < 2:
            raise ValueError(f"{events_path}: need >= 2 events to measure a rate")
        scheduled = sorted(_ts(e.scheduled_send_ts) for e in events)
        ends = [_ts(e.end_ts) for e in events]
        sched_gap_count += len(events) - 1
        sched_gap_seconds += scheduled[-1] - scheduled[0]
        oks = [e for e in events if e.status == "ok"]
        total_ok += len(oks)
        total_events += len(events)
        achieved_window += max(ends) - scheduled[0]
        for e in oks:
            e2e_pooled.append(_ts(e.end_ts) - _ts(e.scheduled_send_ts))

    if not e2e_pooled:
        raise ValueError("no ok events across the supplied repetitions — nothing to fit")

    e2e = np.asarray(e2e_pooled)
    return CorpusPoint(
        run_id=run_id,
        hardware_id=hardware_id,
        model_id=model_id,
        engine_config_id=engine_config_id,
        offered_rate_rps=sched_gap_count / sched_gap_seconds,
        achieved_rate_rps=total_ok / achieved_window,
        total_requests=total_ok,
        e2e_p50_seconds=float(np.quantile(e2e, 0.50)),
        e2e_p95_seconds=float(np.quantile(e2e, 0.95)),
        source_paths=tuple(
            str(Path(p)) for p in (*events_paths, *manifest_paths, workload_path)
        ),
        offered_rate_basis="empirical-scheduled-send-rate",
    )
