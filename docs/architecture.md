# fleetlab — Architecture

fleetlab is a single-process Python CLI + library. Files in → models → files out. No daemon, no server, no database, no network at runtime, no GPU. This document describes the components, the data flow, and the determinism rules that every component obeys.

## Data flow

```text
                    INPUTS (read-only, validated against pinned contract bundle)
  workload manifests (Contract 3)        benchmark-run manifests (Contract 3)
  raw-event JSONL (Contract 3)           benchmark-result JSON (Contract 3)
  backend-capability files (Contract 4)  hardware/model/SLO/cost profiles (SC-T007 schemas)
        │
        ▼
  fleetlab/ingest/      schema validation + provenance enforcement (refuse, never coerce)
        │
        ▼
  fleetlab/models/      arrival, length, token-rate, Little's-law, KV-memory models
        │
        ├──────────────► fleetlab/fitting/    goodput/memory profiles fitted from
        │                                     measurements; structural train/holdout split
        ▼
  fleetlab/dynamics/    queue growth, cold start, scaling lag, failover headroom
        │
        ├──► fleetlab/signals/    autoscaling-signal comparison (6 candidates)
        ├──► fleetlab/placement/  heterogeneous placement (measured hardware only)
        └──► fleetlab/cost/       cost per 1M tokens at SLO; sensitivity analysis
                  │
                  ▼
  fleetlab/emit/ + fleetlab/reports/
        │
        ▼
                    OUTPUTS (every artifact carries seed, input digests, bundle version, provenance)
  capacity-recommendation JSON (Contract 7, schema-validated in CI)
  human reports: autoscaling comparison, cold-start headroom, placement, cost/capacity,
                 simulation limitations
```

## Components

Suggested layout; deviations require an ADR.

1. **Ingestion & validation — `fleetlab/ingest/`.** Loads workload manifests, benchmark results, raw events, backend-capability files, and hardware/model/SLO/cost profiles. Validates everything against the pinned contract bundle. **Rejects any profile without provenance fields and any fabricated default.** Failure semantics: fail fast and loudly with typed errors naming the file, the field, and the rule violated; never silently coerce or default. Ingestion is read-only — fleetlab never mutates its inputs. Golden-file tests (valid, invalid, provenance-missing, unsupported-field cases).

2. **Core analytic models — `fleetlab/models/`.** Arrival and length models parameterized directly from workload manifests (the same versioned files inferbench generates load from, so simulation and measurement describe the same workload by construction). Token-rate model fitted from raw events. Little's-law relationships (L = λW applied to in-flight requests, queue depth, concurrency). KV-memory-per-token model: `2 × layers × kv_heads × head_dim × dtype_bytes × tokens`, cross-checked against measured engine memory metrics. Every closed-form model gets a documented derivation and known-answer tests.

3. **Profile fitting — `fleetlab/fitting/`.** Fits per-(hardware, model, engine-config) goodput and memory profiles from benchmark-result + raw-event files. Overfitting guard; error bars on every fitted parameter. **Holdout validation is structural:** the fitting API takes an explicit train/holdout split and refuses to report fit quality on training data (a test proves this is impossible, not merely discouraged). Fitted profiles carry provenance = the source run manifests.

4. **Dynamics simulator — `fleetlab/dynamics/`.** Simulation of queue growth under bursts; cold-start/warm-up delays; scale-up/down lag; failover headroom; failure-capacity analysis ("N−1 replicas at peak: what breaks?"). Delay parameters must be sourced from measured warm-up artifacts (inferops/inferbench); assumed values carry an explicit `provenance: assumed` flag. Discrete-event vs analytic style is decided in ADR-0001.

5. **Autoscaling-signal comparison — `fleetlab/signals/`.** Evaluates six candidate scaling signals against simulated workloads: CPU utilization, GPU utilization, queue depth, in-flight requests, token-arrival rate, predicted-goodput deficit. Signal candidates map to the Contract 2 metric names (`inference_queue_depth`, `inference_requests_in_flight`, `inference_usage_tokens_total`, …) so the comparison is stated in the vocabulary inferops will actually scale on.

6. **Placement engine — `fleetlab/placement/`.** Heterogeneous placement over **measured hardware profiles only**: model fit vs VRAM, throughput/cost differences, cold starts, failover headroom, fragmentation, workload affinity. Invariants enforced in code, not prose: never place a model that doesn't fit VRAM; never recommend unmeasured hardware.

7. **Cost model — `fleetlab/cost/`.** Cost per 1M tokens at SLO per configuration; sensitivity analysis over price/load/SLO. All prices dated and provenance-flagged (GPU pricing is the most volatile input this repo touches — every price carries its as-of date; re-verify at use time).

8. **Recommendation emitter + report generator — `fleetlab/emit/`, `fleetlab/reports/`.** Emits Contract-7 capacity-recommendation files, schema-validated against the pinned bundle in CI, plus the human-readable reports. Every predicted number carries a stated uncertainty.

## Measurement-point discipline

fleetlab's simulated quantities use the **exact** Contract 2 measurement-point definitions — TTFT = first upstream body byte at the gateway (client-side TTFT is a separate named series); ITL = inter-chunk gap; queue wait = admission-enqueue to dispatch — so simulation, gateway, and benchmark numbers are comparable. Any ambiguity in a metric definition is filed against `serving-contracts`, never patched locally.

Contract 4 backend-capability files bound what a simulated backend may do: context limits, max concurrency hints, prefix-cache support, quantization. Engine metric names (e.g. vLLM waiting/KV-usage gauges) come from the capability file's name mapping, never hardcoded (names vary by version; as of 2026-07, re-verify at use time).

## Determinism rules

Concurrency model: effectively none — single-process, deterministic.

1. **Every simulation and fitting run is seeded.** Same seed + same inputs ⇒ byte-identical result tables (enforced by determinism tests).
2. Every output artifact records: contract bundle version, input file digests (SHA-256), seed, fleetlab version/commit, timestamp, and per-parameter provenance flags.
3. All randomness flows from an explicitly passed seeded RNG (`numpy.random.Generator`); no module-level or global RNG state, no wall-clock-derived seeds.
4. Parallelism, if ever needed for parameter sweeps, must not break determinism per seed (e.g. per-task derived seeds via `SeedSequence.spawn`, order-independent reduction). Until a sweep actually needs it, there is no parallelism.
5. No network at runtime: contract bundles are vendored/pinned, not fetched.

## Failure semantics

fleetlab is offline, so its failure semantics are input-validation semantics: fail fast on schema violations, missing provenance, version-pin mismatches, or metric-definition ambiguity. A failed ingest names the file, the field, and the rule violated, with a typed error class.

Modeling of *platform* failure behavior (retries pre-first-token only, shed-with-429, mid-stream errors never retried) follows Contract 1/2 semantics **as measured by inferbench** — fleetlab models what was measured, not what the spec hopes.

## Stack

Python; minimal numeric/statistical stack (pandas/numpy/scipy candidates). The precise dependency set and the simulator style (discrete-event vs analytic) are decided and justified in `adr/0001-stack-and-simulator-style.md`. Future ADRs cover the fitting method and the signal-comparison design.
