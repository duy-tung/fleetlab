# fleetlab — Interfaces

All integration is via versioned contracts and files. The contracts are owned by `serving-contracts`, versioned together as one SemVer bundle, and released as git tags with artifacts. fleetlab pins one bundle version and validates **all** inputs and outputs against it.

## Pinned contract bundle

| Item | Value |
|---|---|
| Bundle version pinned | **NOT YET PINNED** — as of 2026-07-10 `serving-contracts` has no released tag. The pin is set at the start of FL-T002 and recorded here, in CI, and in every emitted artifact. |
| Pinning mechanism | vendored/pinned bundle at a released tag; never fetched at runtime |
| Pre-1.0 caveat | during v0.x, MINOR may break with a migration note; **contracts v1.0.0 (freezing Contract 1–3 shapes) is a prerequisite for I6** |
| Re-validation | consumer fixture validation re-runs in CI on every contract release (I1 obligation); the v1.0.0 re-run is a prerequisite for I6 |

Contract questions or ambiguities discovered during ingestion are filed against `serving-contracts`, never patched locally.

## Consumed interfaces

### Contract 3 — Benchmark data (primary input; emitted by inferbench, arrives as files)

| Schema | fleetlab's use |
|---|---|
| `workload.schema.json` | Parameterizes arrival and length models: arrival process (`open-loop-poisson` rate \| `closed-loop` with mandatory disclosure flag), input/output-length distributions, prefix-sharing ratio, cancellation-rate profile, slow-client profile, seed, duration/request count. The canonical versioned workload suite (`chat-short`, `rag-long-in`, `gen-long-out`, `shared-prefix`, `mixed`, `bursty`, `cancel-storm`, `slow-client`) is authored by **inferbench**; the fixtures in serving-contracts are non-normative examples. fleetlab consumes inferbench's suite — the same files inferbench generates load from, so simulation and measurement describe the same workload by construction. |
| `benchmark-run.schema.json` | The provenance record for every fitted profile: run ID; topology (`engine-direct` \| `via-gateway` \| `gateway-mock`); engine name/version/commit + all runtime flags (`max_num_seqs`, `max_num_batched_tokens`, `gpu_memory_utilization`, prefix caching, chunked prefill, quantization, KV dtype, speculative decoding); model checkpoint/revision/tokenizer; hardware (GPU model, VRAM, driver, CUDA, instance type); gateway version/config; client RTT; warm-up policy; repetition count; hypothesis. |
| `raw-event.schema.json` | One JSONL record per request (request ID, TTFT, ITL series/summary + max stall, timestamps, status, error class, token counts, shed/retry flags, cancellation point). fleetlab fits token-rate and length models from these. |
| `benchmark-result.schema.json` | Fitting input and cross-check target: pooled-percentile tables (pooled raw data, never averaged across runs), throughput, goodput with explicit SLO reference, shed rate (adjacent to goodput), stall rate, saturation-knee estimate, cost per successful request / per 1M tokens (with cost-profile reference), validity block, links to raw events and manifest. |

### Contract 2 — Metrics and trace vocabulary (model-input definitions)

fleetlab's simulated quantities use the canonical metric definitions exactly, so simulation, gateway, and benchmark numbers are comparable:

- Metric names the signal comparison maps to: `inference_requests_total`, `inference_requests_in_flight`, `inference_queue_depth`, `inference_queue_wait_seconds`, `inference_ttft_seconds`, `inference_itl_seconds`, `inference_e2e_duration_seconds`, `inference_sheds_total`, `inference_usage_tokens_total`.
- Normative measurement points: **TTFT** = first upstream body byte at the gateway (client-side TTFT is a separate named series); **ITL** = inter-chunk gap; **queue wait** = admission-enqueue to dispatch.

### Contract 4 — Backend capability (model constraints)

Bounds what a simulated backend can do: context limit, max concurrency hints, prefix-cache support, quantization, streaming/cancellation capabilities, tokenizer identity. Engine metrics-endpoint name mapping (e.g. vLLM waiting/KV-usage gauge names vary by version — as of 2026-07, re-verify) is taken from the capability file, never hardcoded.

### Profile schemas (SC-T007) — fleetlab's own input files conform to these

`hardware-profile.schema.json`, `model-profile.schema.json`, `slo.schema.json`, `cost-profile.schema.json` — all with **mandatory provenance fields**. If a profile lacks provenance, fleetlab refuses to ingest it. No fabricated defaults. Cost-profile prices are the most volatile input this repo touches: every price carries its as-of date.

## Emitted interfaces

### Contract 7 — Capacity recommendation (`capacity-recommendation.schema.json`)

Machine-readable file emitted by `fleetlab/emit/`, applied by `inferops`, archived by `inference-lab` as Scenario E evidence. Fields:

- **Input references:** benchmark-result IDs, workload version, SLO, cost profile, hardware profiles.
- **Recommended topology:** replica counts per hardware type, engine config.
- **Predicted goodput/latency/cost — with stated uncertainty** on every number.
- **Autoscaling signal + thresholds recommendation.**
- **Assumptions and sensitivity notes.**

fleetlab's emitter validates its own output against the pinned bundle in CI. Every emitted file also embeds the run record (seed, input digests, bundle version, fleetlab version/commit, timestamp) per `observability.md`.

### Human-readable reports (formats owned by fleetlab)

Markdown reports under `reports/`, each embedding the same run record and per-number provenance:

1. `reports/autoscaling-signal-comparison.md` — six-signal comparison + when-each-signal-fails.
2. Cold-start headroom report (from dynamics scenarios, `reports/scenarios/`).
3. `reports/heterogeneous-placement.md` — measured hardware only.
4. `reports/cost-capacity-model.md` — with sensitivity analysis, dated prices.
5. `reports/simulation-limitations.md` — the mandatory honesty artifact: what is modeled, what is not, known error magnitudes from G8.
6. `reports/holdout-validation.md` — G8 evidence (prediction vs holdout, error analysis).

## Dependency edges (and forbidden edges)

| Edge | Mechanism |
|---|---|
| fleetlab → serving-contracts | pinned released spec bundle; validate everything |
| inferbench → fleetlab | benchmark files (JSONL/JSON) only |
| fleetlab → inferops | Contract 7 files + reports (I6 experiment input) |

**Forbidden, checked at every review gate:** fleetlab → inferbench *code* (files only; no shared statistics library); fleetlab → infergate/inferops/engine *source* (never checked out, imported, or linked); any repo importing fleetlab as a library (consumers read emitted files).
