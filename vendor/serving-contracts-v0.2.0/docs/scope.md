# Scope — serving-contracts

This repo authors and stewards exactly the following contract surface. Everything here is a
public contract once released; changes are governed by `compatibility/compatibility-policy.md`.

## Contract 1 — Inference API (OpenAI-compatible subset)

**Consumers:** infergate (implements), inferbench (drives), inferops (smoke tests), inference-lab (demos).

- **Endpoints:** `POST /v1/chat/completions` (stream + non-stream), `GET /v1/models`,
  `GET /healthz`, `GET /readyz`, `GET /metrics`. infergate's admin surface (`/admin/v1/...`) is
  explicitly NOT part of this contract (single consumer — see `docs/non-goals.md`).
- **Supported request-field subset (exhaustive):** `model`, `messages`,
  `max_tokens`/`max_completion_tokens`, `temperature`, `top_p`, `stream`,
  `stream_options.include_usage`, `stop`, `seed`, `user`. All unsupported fields are **rejected
  with a typed error, never silently ignored**. Response objects mirror the OpenAI
  chat-completion and chunk shapes for the supported subset.
- **Streaming semantics:** SSE with `data: <json-chunk>` events; terminal `data: [DONE]`; every
  event flushed; usage in the final chunk when `stream_options.include_usage=true`; no
  interleaving across requests; monotonically increasing chunk indices per stream.
- **Error envelope:** `{"error": {"message", "type", "code", "param"}}` plus request ID. Error
  taxonomy with retryability: `invalid_request`, `authentication`, `permission`, `not_found`,
  `rate_limited` (429 + `Retry-After`), `overloaded` (503 + `Retry-After`), `upstream_error`,
  `upstream_timeout`, `canceled`, `internal`. Mid-stream failures are a standardized SSE error
  event followed by stream close — **never a retry** (post-first-token retry would duplicate
  sampled output and double-bill).
- **Request-ID contract:** `X-Request-Id` accepted or generated; echoed in responses, error
  bodies, traces, and usage records; the idempotency key for usage settlement.
- **Cancellation contract:** client disconnect or explicit connection close MUST propagate
  upstream (HTTP body close); observable effects (engine abort, resource release) are part of
  conformance; tokens emitted before cancellation are billable.

## Contract 2 — Metrics and trace vocabulary

**Consumers:** infergate (emits), inferops (dashboards/alerts), inferbench (client-side mirror
definitions), fleetlab (model inputs).

Canonical metric set (Prometheus naming; units in name; histograms with declared bucket
boundaries), to be fully specified in `metrics/metrics.md`:

| Metric | Type | Labels |
|---|---|---|
| `inference_requests_total` | counter | `model`, `backend`, `tenant_tier`, `status_class`, `error_class` |
| `inference_requests_in_flight` | gauge | `backend` |
| `inference_queue_depth` | gauge | `tenant_tier` |
| `inference_queue_wait_seconds` | histogram | `tenant_tier` |
| `inference_ttft_seconds` | histogram | `model`, `backend` |
| `inference_itl_seconds` | histogram | `model`, `backend` |
| `inference_e2e_duration_seconds` | histogram | `model`, `backend`, `status_class` |
| `inference_sheds_total` | counter | `reason` |
| `inference_retries_total` | counter | `stage` (always pre-first-token) |
| `inference_backend_healthy` | gauge | `backend` |
| `inference_usage_tokens_total` | counter | `direction` (input/output), `model`, `tenant_tier` |

- **Cardinality policy** (`metrics/cardinality-policy.md`): allowed labels are enumerable and
  low-cardinality; request IDs, raw tenant/user IDs, prompts, and arbitrary strings are forbidden
  as labels. Per-request detail belongs in traces; exemplars link histograms to traces.
- **Trace attributes:** OTel GenAI semantic conventions at a **pinned version** (status
  "Development" as of 2026-07 — re-verify at use time; the pin is mandatory), plus platform
  attributes `inference.config_version`, `inference.tenant_tier`, `inference.backend`,
  `inference.request_id`. Gateway span sequence:
  `recv → queue.wait → upstream.connect → ttft → stream.relay → settle`.
- **Measurement points (normative):** TTFT = first upstream body byte at the gateway (client-side
  TTFT measured by inferbench is a separate, named series); ITL = inter-chunk gap; queue wait =
  admission-enqueue to dispatch. These definitions make gateway, benchmark, and simulation
  numbers comparable.

## Contract 3 — Benchmark data

**Consumers:** inferbench (emits), fleetlab (consumes), inference-lab (reports).

- **`workload.schema.json`:** name, version, seed; arrival process (`open-loop-poisson` rate |
  `closed-loop` with mandatory disclosure flag); input/output-length distributions;
  prefix-sharing ratio; cancellation-rate profile; slow-client profile; duration or request
  count. The eight named workloads (`chat-short`, `rag-long-in`, `gen-long-out`, `shared-prefix`,
  `mixed`, `bursty`, `cancel-storm`, `slow-client`) ship here as **non-normative example
  fixtures**; the canonical versioned workload suite is authored and owned by `inferbench`
  (IB-T003), and `fleetlab` consumes inferbench's suite, not these fixtures.
- **`benchmark-run.schema.json` (manifest):** run ID; target topology (`engine-direct` |
  `via-gateway` | `gateway-mock`); engine name/version/commit + all runtime flags
  (`max_num_seqs`, `max_num_batched_tokens`, `gpu_memory_utilization`, prefix caching, chunked
  prefill, quantization, KV dtype, speculative decoding config); model checkpoint + revision +
  tokenizer; hardware (GPU model, VRAM, driver, CUDA version, instance type); gateway version +
  config version; client location/RTT; warm-up policy; repetition count; hypothesis statement.
- **`raw-event.schema.json`:** one JSONL record per request: request ID, workload item, send
  timestamp, TTFT, ITL series or summary + max stall, end timestamp, status, error class,
  input/output token counts, shed/retry flags, cancellation point.
- **`benchmark-result.schema.json`:** aggregates per run set: pooled-percentile tables
  (percentiles computed on pooled raw data — never averaged across runs), throughput, goodput
  with explicit SLO reference, shed rate (always adjacent to goodput), stall rate,
  saturation-knee estimate, cost per successful request and per 1M tokens (with cost-profile
  reference), validity block (warm-up handling, run count, threats to validity, unexplained
  anomalies), links to raw events and manifest.

## Contract 4 — Backend capability

**Consumers:** infergate (adapters declare + probe), inferbench (feature-gates workloads),
fleetlab (model constraints), inferops (probe configuration).

Fields: engine name + version/commit; streaming support; usage-in-stream support; cancellation
mechanism (HTTP-close semantics) and expected release observability; metrics endpoint + name
mapping (e.g. vLLM waiting/KV-usage gauges — names vary by version and must be **mapped, not
hardcoded**; as of 2026-07 — re-verify at use time); tokenizer identity; context limit; max
concurrency hints; prefix-cache support + observability; quantization; priority support.
Capability descriptors for the mock backend, llama.cpp, and vLLM ship as examples.

## Contract 5 — Deployment

**Consumers:** infergate (publishes descriptor per release), inferops (consumes), inference-lab (pins).

Fields: image + digest; ports (API, metrics); environment variables and config mounts;
startup/readiness/liveness semantics including warm-up-aware readiness (readiness false during
model load/warm-up); model mount path and expected volume; resource requests/limits including GPU
count; graceful termination (`preStop` drain hook, termination grace period > max stream
duration); secret expectations (names only, never values).

## Contract 6 — Fault scenarios (shared vocabulary for milestone I7)

**Consumers:** inferops (injects), infergate (semantics tests), inferbench (client-impact
measurement), inference-lab (postmortems).

Twelve required scenarios, each encoded with: ID, injection description, expected gateway
semantics, expected client-visible behavior, metrics that must move, and abort condition:

1. backend killed before first token → pre-first-token retry within budget or typed 5xx
2. backend killed after first token → SSE error event, no retry, partial usage settled
3. slow backend → pressure-aware routing shifts; timeouts typed
4. slow client → bounded write buffer + write deadline; stream closed, engine released
5. gateway termination during streaming → drain semantics; accepted streams complete
6. queue saturation → sheds with 429 + `Retry-After`; accepted-request latency protected
7. retry storm → retry budget caps amplification
8. config reload during traffic → snapshot swap, zero dropped streams
9. usage database failure → requests unaffected; settlement backlog drains idempotently
10. one unhealthy backend → routing shifts within bounded interval; circuit opens on error rate
11. readiness during model warm-up → no traffic before warm; no restart loops
12. rolling update with active requests → zero client-visible errors

## Contract 7 — Capacity recommendation (fleetlab → inferops)

**Consumers:** fleetlab (emits), inferops (applies as experiment), inference-lab (Scenario E
evidence).

Fields: input references (benchmark-result IDs, workload version, SLO, cost profile, hardware
profiles); recommended topology (replica counts per hardware type, engine config); predicted
goodput/latency/cost with stated uncertainty; autoscaling signal + thresholds recommendation;
assumptions and sensitivity notes. Closes the I6 feedback loop in a machine-checkable form.

## Fleet schemas (feed Contracts 3 and 7)

`hardware-profile`, `model-profile`, `slo`, `cost-profile` schemas all carry **mandatory
provenance fields** (measured / source-reported / assumed + date) — no fabricated defaults. The
SLO schema must be able to express the program's source-verified gateway targets (as of 2026-07,
re-baseline from measurement if infeasible): non-queue gateway overhead p95 <10ms / p99 <20ms;
cancellation propagation p95 <250ms (gateway+mock path); usage settle variance <1%; key
revocation ≤5s; config publish ≤5s. Model-level TTFT/ITL/goodput SLOs are declared only from
measurement, never in advance.

## Compatibility policy

`compatibility/compatibility-policy.md` is itself part of the contract surface: SemVer rules on
the bundle, the breaking-change definition, deprecation rules, the release process, and the
consumer compatibility-test approach. See that file for the normative text.
