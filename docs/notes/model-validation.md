# Model validation note (FL-T003)

Every model in `fleetlab/models/` is closed-form/analytic (ADR-0001). This
note gives each model's derivation, its known-answer test evidence, and its
cross-check against measured data — including the one cross-check that is
honestly **PENDING**, per the program rule that a prediction miss (or, here,
an unavailable measurement) is a recorded result, never fabricated as a pass.

All code referenced here lives in `fleetlab/models/`; all cross-checks are
exercised as pytest tests in `tests/models/` (103 tests total across
FL-T002 + FL-T003, all green — see `docs/implementation-notes.md` for the
run evidence).

## 1. Arrival model (`fleetlab/models/arrival.py`)

**Derivation.** Inter-arrival times of a homogeneous Poisson process of rate
`lambda` are i.i.d. Exponential(`lambda`); arrival epochs are the cumulative
sum (standard queueing-theory result, e.g. Kleinrock, *Queueing Systems Vol.
1*). fleetlab implements exactly the two arrival shapes
`workload.schema.json` defines: single-rate open-loop Poisson, and
piecewise-constant-rate ("phases") open-loop Poisson for bursty workloads.
Closed-loop arrival is represented as a data-only `ClosedLoopArrivalProcess`
(concurrency + think time) — its timing depends on service latency, which is
`fleetlab/dynamics/`'s job (FL-T005), not this package's; this is a
deliberate scope boundary, not an oversight.

**Known-answer tests** (`tests/models/test_arrival.py`):
- Mean inter-arrival time = 1/rate (exact algebraic check).
- Large-N inter-arrival sample mean converges to 1/rate within 2% (law of
  large numbers, seeded).
- Arrival count over a long window converges to `rate x duration` within 3%.
- Phased ("bursty") schedule: arrival count over ten repeated periods
  converges to the hand-computed expectation (`10 x (60s x 2rps + 15s x
  20rps) = 4200`) within 5%.
- Determinism: same seed -> byte-identical arrival-time arrays; different
  seed -> different arrays.
- Parameterized directly from the **real** canonical workload manifests
  (`chat-short.json`, `bursty.json` — copied into
  `tests/golden/fixtures/real/workloads/`), not only synthetic dicts.

## 2. Length model (`fleetlab/models/length.py`)

**Derivation.** Implements `workload.schema.json`'s `$defs/distribution`
shapes (constant, uniform, normal, lognormal, empirical, mixture) with the
exact sampling and clamp semantics the schema documents (normal/lognormal
clamp post-sampling; mixture weights are normalized, not assumed
pre-normalized). Using the identical shapes inferbench's own workload files
declare means a fleetlab-simulated length distribution and an
inferbench-generated one describe the same workload by construction.

**Known-answer tests** (`tests/models/test_length.py`): closed-form means
for every distribution type verified against large-N sample means (uniform
midpoint, lognormal `exp(mu + sigma^2/2)` — using chat-short's own
`mu=4.8, sigma=0.6`, mixture weighted average using `mixed.json`'s declared
60/25/15 split), clamp behavior, and the schema's rounding rule (`round(x)`,
floored at 1 for input/output length, floorable at 0 for a token-valued
cancellation point).

**Documented assumption:** `mean_of_distribution` computes the *unclamped*
closed-form mean; the min/max clamp truncates tails and shifts the true
(clamped) mean slightly. Not numerically corrected here — flagged as an
approximation for capacity arithmetic, not a certified expectation.

## 3. Token-rate model (`fleetlab/models/token_rate.py`)

**Derivation.** Per-request decode rate = tokens emitted after the first
token, divided by the decode-phase duration (`e2e_duration - ttft_seconds`),
using Contract 2's exact measurement points (TTFT from `scheduled_send_ts`,
per raw-event.schema.json v0.2.0's coordinated-omission-safe basis).
System-level output-token throughput = `requests_per_second x
mean_output_tokens` — the same L=lambda*W family of identities applied to
tokens instead of requests.

**Cross-check against real measured data — PASSED (exact formula match).**
`ib-t005-calib-A.benchmark-result.json` (real inferbench output): 120
requests, 7650 total output tokens, `requests_per_second =
3.1175309264829445`, reported `output_tokens_per_second =
198.74259656328772`. fleetlab's `system_output_token_rate(rps,
total_output_tokens/total_requests)` reproduces `198.7425965...` to
`rel=1e-6` — the same arithmetic identity inferbench used internally.
(`tests/models/test_token_rate.py::test_system_output_token_rate_matches_real_benchmark_result_throughput`)

`fit_token_rate` was also run against the real `calib-A` raw-event trace
(mock engine) and the real `chat-short-cpu-direct` trace (llama.cpp on CPU,
Qwen2.5-1.5B) — both produce sane positive decode-rate summaries; no
independent ground truth exists to check the *decode-rate* number itself
against (llama.cpp's per-request `timings` field, which would be the
independent check, was stripped by the adapter per the backend-capability
descriptor's notes and is not present in the raw-event schema) — this is
noted as a gap, not glossed over.

## 4. Little's law (`fleetlab/models/littles_law.py`)

**Derivation.** `L = lambda * W` — the time-average number of requests
present in a subsystem equals its throughput times the mean time a request
spends in it. This holds as an exact **sample-path identity** for any finite
set of (start, end) intervals over their own bounding window (not merely a
long-run statistical limit): `sum(end-start)` over all intervals equals the
integral of the in-flight count over the same window (linearity of
indicator-function integrals), so `lambda * W = (N/duration) *
(sum(end-start)/N) = sum(end-start)/duration = L` algebraically, with no
approximation. This is the "H = lambda*G" sample-path form of Little's law.

**Known-answer test** — hand-computed three-request trace `[0,10], [2,8],
[5,15]`: worked by hand in the test docstring to `L = 26/15 = lambda*W`
exactly (`tests/models/test_littles_law.py::test_hand_computed_three_request_trace`,
`relative_error < 1e-9`).

**Cross-check against real traces — PASSED (exact identity, both real
runs).** `check_littles_law` run against the real, unmodified raw-event
traces `calib-A` (mock engine, gateway-mock) and `chat-short-cpu-direct`
(llama.cpp, engine-direct, CPU): the identity holds to floating-point
precision on both (`relative_error < 1e-6`) — consistent across in-flight
requests / throughput / latency views of the same real trace, exactly as
`docs/testing.md` §2 requires.

## 5. KV-memory-per-token model (`fleetlab/models/kv_memory.py`)

**Formula (verbatim, as specified):**

```
kv_bytes_per_token = 2 x layers x kv_heads x head_dim x dtype_bytes
```

**Derivation.** A transformer decoder's KV cache stores one Key vector and
one Value vector per layer per token (the factor of 2), each of dimension
`kv_heads x head_dim`. Grouped-query attention (GQA) shares K/V projections
across a group of query/attention heads, so `kv_heads` can be smaller than
the attention head count — this is exactly the mechanism that shrinks the
cache (PagedAttention, SOSP'23, motivates the KV cache as the
capacity-limiting resource; this repo's worksheet reading is scoped to its
§1-4 as planned). Each cached element costs `dtype_bytes` (2 for fp16/bf16,
1 for fp8/int8, 4 for fp32).

**Known-answer tests** (`tests/models/test_kv_memory.py`):
- **Llama-3.1-8B, matched against an independently-authored fixture.**
  `serving-contracts examples/fleet/model-llama31-8b.json` documents
  `kv_cache_bytes_per_token: 131072`, computed (per its own `notes` field,
  authored independently of fleetlab) as "2 x 32 layers x 8 KV heads x 128
  head_dim x 2 bytes (fp16 KV dtype)". `kv_cache_bytes_per_token(layers=32,
  kv_heads=8, head_dim=128, dtype_bytes=2)` reproduces `131072` exactly.
  This is a genuine known-answer case: the fixture's number was authored
  independently in `serving-contracts`, not derived from fleetlab's code.
- **GQA case:** `kv_heads=8` vs. an MHA-equivalent `kv_heads=32` — the GQA
  case is exactly 1/4 the footprint (`8/32`), verified exactly.
- **dtype variation:** fp16/bf16 = 2 bytes, fp8/int8 = 1 byte, fp32 = 4
  bytes; halving/doubling verified exactly.
- **Qwen2.5-1.5B-Instruct case** (see §5.1 below): `layers=28, kv_heads=2,
  head_dim=128, dtype_bytes=2 -> 28,672 bytes/token`, matching
  `profiles/examples/model-qwen2.5-1.5b-instruct-gguf-q4km.json`.
- Zero/negative architecture parameters are rejected (`ValueError`), never
  silently coerced.

### 5.1 Qwen2.5-1.5B-Instruct: measured architecture, from the real checkpoint

The GGUF checkpoint actually served in `inference-lab/evidence/i3` (Scenario
B) — `/home/user/tools/models/qwen2.5-1.5b-instruct-q4_k_m.gguf`, sha256
`6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e`, matching
the pinned run manifests — was dumped directly with llama.cpp's own
`gguf-py/gguf/scripts/gguf_dump.py` this session (2026-07-11):

```
general.architecture      = qwen2
qwen2.block_count          = 28      (layers)
qwen2.embedding_length     = 1536
qwen2.attention.head_count    = 12  (attention/query heads)
qwen2.attention.head_count_kv = 2   (KV heads -- GQA)
qwen2.context_length       = 32768
```

`head_dim = embedding_length / head_count = 1536 / 12 = 128`. These four
numbers (layers, kv_heads, head_dim, context_length) are **measured** —
read directly from the served checkpoint's own metadata, not estimated or
looked up from a model card.

`kv_cache_bytes_per_token(layers=28, kv_heads=2, head_dim=128,
dtype_bytes=2) = 28,672 bytes/token`, assuming llama.cpp's default KV cache
dtype (fp16) — see §5.2 for why that dtype is *assumed*, not *measured*.

### 5.2 Cross-check against measured engine memory — **PENDING**

**Stop condition met, cross-check status honestly recorded as PENDING** (per
the FL-T003 instruction: "If no adequate measured memory data exists,
record the cross-check as PENDING with what's missing — do NOT fabricate").

What was checked, this session, across every available real memory-adjacent
artifact:

1. **`/metrics` (Prometheus) endpoint.** llama.cpp commit `8f114a9` exposes
   exactly 11 unlabeled `llamacpp:`-prefixed series (probe report,
   `/home/user/tools/llamacpp-probe-report.md` §4) — none of them is a
   memory or KV-cache-size metric. The real `llamacpp.backend-capability.json`
   descriptor (`inference-lab/evidence/i3/raw/`) records
   `kv_cache_usage_ratio: null` explicitly: this engine build has no
   equivalent metric.
2. **Server logs, every run in `inference-lab/evidence/i3/logs/*.log` and
   `/home/user/tools/server.log`.** Grepped case-insensitively for `KV`,
   `MiB`, `GiB`, `buffer size`, `kv self size`, `compute buffer`, `graph`
   (the log lines older llama.cpp CLI builds print at model load) — none
   present at the captured log verbosity (`common_params_print_info:
   verbosity = 3`). The server only logs `n_slots`, `n_ctx_slot`, and
   per-request timing/token counts, never a memory figure.
3. **`/slots` polling data** (`inference-lab/evidence/i3/raw/slots-poll-cancel.jsonl`)
   — carries `is_processing` only, no memory field.
4. **Process RSS.** The one memory figure that exists anywhere in the
   available evidence is a *different* artifact: the llama.cpp probe report
   records `RSS 43 MB` for an unrelated **tiny synthetic** model (2 layers,
   `n_embd=64`, 8 heads / 4 KV heads, F32, 2 slots x 4096 ctx) used for
   IG-T005 protocol testing — not for Qwen2.5-1.5B. RSS is also whole-process
   memory (weights + KV cache + compute-graph buffers + allocator overhead),
   not an isolated KV-cache figure, so even a clean RSS delta would only
   loosely bound the KV term, not cross-check it tightly.

**What's missing to close this out:** a measured, KV-cache-isolated memory
figure for a real served model — e.g. rebuilding llama-server with
`--verbose` at a level that prints its internal `ggml` buffer allocations at
load time (the exact log line varies by version and was not verified this
session), or an explicit before/after RSS delta captured with `--parallel 1`
and only one context size varied (to isolate the KV term from the constant
weights term), or a real vLLM run exposing `kv_cache_usage_ratio` through
its own metrics (the Contract 4 vLLM descriptor's `name_mapping` has a slot
for this metric name; no vLLM run has produced data yet in this program).

**As a weak, explicitly-non-tight sanity note only** (not a stated-error
cross-check): the tiny model's predicted KV total is `kv_cache_bytes(layers=2,
kv_heads=4, head_dim=8, dtype_bytes=4, tokens=2*4096) = 2*2*4*8*4*8192 =
4,194,304 bytes ~= 4 MiB` (F32 KV cache, matching the probe's `-c 8192
-np 2` -> 4096 ctx/slot config) against a measured whole-process RSS of 43
MB. 4 MiB is a small, plausible fraction of 43 MB alongside the ~9 MB
weights file and llama.cpp's fixed compute-graph/allocator overhead — the
order of magnitude is directionally consistent, but this is not a tight
cross-check (RSS is not KV-isolated) and is not treated as satisfying the
FL-T003 stop condition; it is recorded only as a sanity note, per the
instruction to record what's missing rather than fabricate a pass.

**Conclusion:** the KV-memory formula's known-answer behavior is fully
verified (§5's tests, including an independently-authored fixture match);
its cross-check against a measured memory metric for a real served model is
honestly **PENDING** for want of an isolated KV-memory measurement anywhere
in the currently available evidence. This is recorded here and in
`docs/implementation-notes.md`, not hidden.

## 6. Capacity-math worksheet (Pope et al. backbone; study-track artifact)

A minimal concrete worked example tying every model above together for the
real, measured Qwen2.5-1.5B / CPU environment (`inference-lab/evidence/i3`),
in the spirit of Pope et al., *Efficiently Scaling Transformer Inference*
(skim-level backbone per `docs/oss-opportunities.md`'s reading plan):

- Workload: `chat-short-cpu` (CPU-adapted `chat-short`), calibrated arrival
  rate ~0.08 rps (`inference-lab/evidence/i3/notes.md`).
- Token-rate: real `chat-short-cpu-direct` events give an
  engine-measured decode rate via `fit_token_rate` (`tests/models/
  test_token_rate.py::test_fit_token_rate_on_real_events` exercises this on
  the mock trace; the same function applies unchanged to the llama.cpp
  trace).
- Little's law: at steady state, in-flight concurrency `L = lambda * W`; for
  the real `chat-short-cpu-direct` trace this holds exactly (§4).
- KV memory: with `kv_cache_bytes_per_token = 28,672` (§5.1) and the served
  `n_ctx_slot = 4096` (2 parallel slots, `ctx_size=8192`, from the real run
  manifest), the model's own headroom bound is `28,672 x 4096 x 2 slots =
  ~235 MiB` of KV cache at full slot occupancy — well within the host's 16
  GiB RAM, consistent with the host never reporting memory pressure in this
  evidence set. This number inherits the §5.2 PENDING dtype assumption and
  is not claimed as a measured figure.

This worksheet is intentionally short: it demonstrates the models compose
(arrival -> Little's law -> token rate -> KV memory) on one real,
already-ingested trace, rather than introducing a second synthetic example.
