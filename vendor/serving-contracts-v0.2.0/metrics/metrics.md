# Metrics and Trace Vocabulary (Contract 2)

**Status:** normative. Statements with MUST/MUST NOT are binding; everything
else is explanatory. Consumers: infergate (emits), inferops
(dashboards/alerts), inferbench (client-side mirror definitions), fleetlab
(model inputs). Renaming a metric or label, or changing a histogram's bucket
boundaries, is a **breaking change** under the compatibility policy
(clause 2: it changes the meaning of previously-recorded measurements).

---

## 1. Canonical metric set

Prometheus naming; units in the name; histograms use the declared bucket
boundaries in §2. This table is exhaustive: the gateway MUST emit exactly
these eleven `inference_*` metrics with exactly these labels (additional
non-`inference_*` process/runtime metrics are out of scope of this contract).

| # | Metric | Type | Labels |
|---|---|---|---|
| 1 | `inference_requests_total` | counter | `model`, `backend`, `tenant_tier`, `status_class`, `error_class` |
| 2 | `inference_requests_in_flight` | gauge | `backend` |
| 3 | `inference_queue_depth` | gauge | `tenant_tier` |
| 4 | `inference_queue_wait_seconds` | histogram | `tenant_tier` |
| 5 | `inference_ttft_seconds` | histogram | `model`, `backend` |
| 6 | `inference_itl_seconds` | histogram | `model`, `backend` |
| 7 | `inference_e2e_duration_seconds` | histogram | `model`, `backend`, `status_class` |
| 8 | `inference_sheds_total` | counter | `reason` |
| 9 | `inference_retries_total` | counter | `stage` |
| 10 | `inference_backend_healthy` | gauge | `backend` |
| 11 | `inference_usage_tokens_total` | counter | `direction`, `model`, `tenant_tier` |

Semantics notes:

- **`inference_requests_total`** increments once per request at settle time
  (terminal outcome known). `error_class="none"` for successes.
- **`inference_sheds_total`** counts admission rejections (429/503 +
  `Retry-After`); a shed request also appears in `inference_requests_total`
  with the corresponding `status_class`/`error_class`.
- **`inference_retries_total`** — `stage` has exactly one allowed value,
  `pre_first_token`. This encodes the Contract 1 rule that mid-stream
  failures are never retried: there is no legal label value for a
  post-first-token retry.
- **`inference_backend_healthy`** is 1/0 per configured backend, as judged by
  the gateway's health checking.
- **`inference_usage_tokens_total`** counts settled, billable tokens (tokens
  emitted before cancellation are billable, per Contract 1).

## 2. Histogram bucket boundaries (declared, normative)

Bucket boundaries are contract surface. Changing them is a breaking change
(recorded distributions stop being comparable). Upper bounds in seconds; each
histogram also has the implicit `+Inf` bucket.

| Histogram | Buckets (seconds) |
|---|---|
| `inference_queue_wait_seconds` | `0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30` |
| `inference_ttft_seconds` | `0.025, 0.05, 0.1, 0.2, 0.4, 0.8, 1.5, 3, 6, 12, 30, 60` |
| `inference_itl_seconds` | `0.005, 0.01, 0.02, 0.04, 0.08, 0.15, 0.3, 0.6, 1, 2, 5` |
| `inference_e2e_duration_seconds` | `0.25, 0.5, 1, 2, 4, 8, 15, 30, 60, 120, 300, 600` |

Rationale (explanatory): queue-wait buckets extend down to 1 ms so the
sub-10 ms non-queue gateway-overhead targets remain resolvable; ITL buckets
straddle typical decode cadence (tens of ms) and the stall region (≥ 0.3 s);
TTFT and e2e buckets are roughly geometric across interactive-to-batch use.

## 3. Label value semantics

Cardinality rules, forbidden labels, and enforcement live in
[`cardinality-policy.md`](cardinality-policy.md) (same contract). Value sets:

| Label | Values |
|---|---|
| `model` | configured model IDs (gateway config), plus `unknown` for rejected/unroutable model strings — never the raw client string |
| `backend` | configured backend IDs |
| `tenant_tier` | configured tier names (e.g. `free`, `standard`, `premium`) — never raw tenant IDs |
| `status_class` | `2xx`, `4xx`, `5xx` |
| `error_class` | the Contract 1 taxonomy: `invalid_request`, `authentication`, `permission`, `not_found`, `rate_limited`, `overloaded`, `upstream_error`, `upstream_timeout`, `canceled`, `internal`, plus `none` |
| `reason` (sheds) | `queue_full`, `tenant_rate_limit`, `global_overload`, `backend_unavailable` |
| `stage` (retries) | `pre_first_token` (only value; see §1) |
| `direction` | `input`, `output` |

New values for `reason` may be added in a MINOR release; all other value sets
change only with their source contract.

## 4. Normative measurement-point definitions

These definitions exist so gateway, benchmark, and simulation numbers are
comparable. Changing any of them is a breaking change (clause 2).

**TTFT (`inference_ttft_seconds`)** — measured at the gateway.
- **Start:** the gateway has read the complete client request (headers +
  body) and assigned/echoed the request ID.
- **End:** the **first upstream response body byte** arrives at the gateway.
- Includes queue wait, upstream connect, and engine prefill. It does NOT
  include client network time.

**Client-side TTFT** — a **separate, named series**, never merged with the
gateway series: `client_ttft_seconds` (recorded per request in
`raw-event.ttft_seconds` by inferbench; reported as the
`client_ttft_seconds` pooled-percentile table in benchmark results).
- **Start:** client completes writing the request body.
- **End:** first response body byte arrives at the client.
- `client_ttft_seconds − inference_ttft_seconds ≈` network + client stack
  time; the two series MUST always be labeled distinctly in every report.
  The same client/gateway split applies to `client_itl_seconds` and
  `client_e2e_duration_seconds`.

**ITL (`inference_itl_seconds`)** — the **inter-chunk gap**: elapsed time
between arrivals of consecutive **content-bearing** stream chunks (chunks
carrying at least one output-token delta) for one stream, measured at the
gateway on upstream reads. Role-only chunks, usage-only chunks, and the
terminal `[DONE]` sentinel do not define gaps. A stream with n content chunks
contributes n−1 observations.

**Stall** — the maximum single inter-chunk gap within a stream
(`raw-event.itl.max_stall_seconds`). A stream stalls when that maximum
exceeds the SLO's stall threshold; **stall rate** is the fraction of
streaming requests that stall, and is always reported adjacent to goodput
(enforced structurally by `benchmark-result.schema.json`).

**Queue wait (`inference_queue_wait_seconds`)** —
- **Start:** admission control accepts the request and enqueues it
  (admission-enqueue).
- **End:** the request is dispatched (dequeued and handed to upstream
  connection establishment).
- Shed requests never enter the queue and contribute no observation.

**E2E duration (`inference_e2e_duration_seconds`)** — start of TTFT window to
terminal outcome at the gateway (last byte relayed and stream settled, or
terminal error), per request.

## 5. Gateway span sequence

One trace per request; the request ID joins traces to logs, usage records,
and benchmark raw events. Gateway spans, in order:

```text
recv → queue.wait → upstream.connect → ttft → stream.relay → settle
```

| Span | Start | End |
|---|---|---|
| `recv` | first byte of client request | request fully read + admission decision |
| `queue.wait` | admission-enqueue | dispatch (== the queue-wait metric window) |
| `upstream.connect` | dispatch | upstream connection established / request written |
| `ttft` | upstream request written | first upstream body byte (end of the gateway TTFT window) |
| `stream.relay` | first upstream body byte | last byte relayed to client (or terminal stream error) |
| `settle` | stream close | usage settled + terminal metrics recorded |

Shed requests produce `recv` only (with the shed outcome recorded on it).
Pre-first-token retries repeat `upstream.connect`/`ttft` as new child spans
under the same request trace.

## 6. Trace attributes

**OTel GenAI semantic conventions — pinned version (mandatory):**
`gen_ai.*` attributes follow **OpenTelemetry Semantic Conventions v1.34.0**.
The GenAI conventions have status **"Development" as of 2026-07 — re-verify
the pin at use time** (first emit wiring, IG-T006) and re-date it; attribute
names there may still change between semconv releases, which is exactly why
the pin is mandatory and unpinned emission is non-conformant. Drift handling
per `docs/observability.md`; gaps/ambiguities found while applying the
conventions are recorded in `docs/experiments.md` as candidate upstream
contributions.

Minimum `gen_ai.*` set on the request's server span (names per the pinned
semconv version):

- `gen_ai.operation.name` (= `chat`)
- `gen_ai.request.model`, `gen_ai.response.model`
- `gen_ai.request.max_tokens`, `gen_ai.request.temperature`, `gen_ai.request.top_p`
- `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`
- `gen_ai.response.finish_reasons`

Prompt/completion **content** is never attached to spans (see
cardinality-policy §4; the same PII rule applies to trace payloads).

**Platform attributes (this contract's namespace, stable):**

| Attribute | Meaning |
|---|---|
| `inference.config_version` | gateway config snapshot version serving the request |
| `inference.tenant_tier` | tier (never the raw tenant ID) |
| `inference.backend` | backend ID chosen by routing |
| `inference.request_id` | the `X-Request-Id` (allowed in traces; forbidden as a metric label) |

## 7. Exemplars

Histograms (`inference_ttft_seconds`, `inference_itl_seconds`,
`inference_queue_wait_seconds`, `inference_e2e_duration_seconds`) SHOULD
carry OpenMetrics exemplars referencing the trace ID, so per-request detail
is reachable from any latency panel without high-cardinality labels.

## 8. Client-side mirror series (inferbench)

inferbench measures the client-visible counterparts with the same
definitions shifted to the client boundary and MUST name them distinctly:
`client_ttft_seconds`, `client_itl_seconds`, `client_e2e_duration_seconds`
(§4). Benchmark reports MUST state which side each number was measured on.
fleetlab model inputs consume both series under these names.
