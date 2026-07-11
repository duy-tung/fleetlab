# Implementation notes — serving-contracts

Running log of notable decisions, ambiguities, classifications (MAJOR/MINOR/PATCH), review
outcomes, and recorded assumptions. Deviations from the approved plan go under **Deviations**
per the program deviation policy:

> When repository evidence forces a deviation from the approved plan, choose the conservative
> reversible option, record the evidence, decision, consequences, and follow-up under
> `Deviations`, and continue. Pause only when the deviation changes public contracts, repository
> ownership, security posture, or milestone scope.

Note: in this repo, almost every substantive file IS a public contract — expect the pause
condition to apply more often than elsewhere. Fixture additions, doc clarifications, and
PATCH-level fixes proceed under the policy; field/semantics changes pause for review.

## Running log

### 2026-07-10 — SC-T001 bootstrap

- Created the 15-doc set (`docs/`), the ADR seeds (`docs/adr/`), and
  `compatibility/compatibility-policy.md` on a fresh repo (no prior commits).
- **Recorded assumption (workload-fixture ownership):** the standalone repo prompt says the
  eight named workloads "ship as versioned examples", while the program contract document
  (04-shared-contracts §Contract 3) and the responsibility matrix state they ship here only as
  **non-normative example fixtures**, with the canonical versioned workload suite owned by
  `inferbench` (IB-T003) and consumed by `fleetlab` from inferbench. The docs here follow the
  program documents (non-normative fixtures). The two readings are compatible; no contract
  surface changes — logged as an assumption, not a deviation.
- **Recorded assumption (ADR pre-decisions):** ADR-0002 (JSON Schema draft 2020-12) and
  ADR-0003 (OpenAPI 3.1.x) are recorded now, before any schema exists, because the compatibility
  policy and testing doc need to reference pinned choices. Both are reversible at zero cost
  until the first schema file is authored in SC-T002/T003; they will be re-confirmed then.
- **Review status:** SC-T001 stop condition is "policy reviewed by the user" — user review of
  `compatibility/compatibility-policy.md` is **pending** as of this entry. No schema work
  (SC-T002+) starts before that review.

### 2026-07-10 — SC-T002 Inference API contract (Contract 1)

- Authored `openapi/inference-api.yaml` + golden fixtures `examples/api/**` (layout per
  ADR-0004: negatives in `invalid/` with `.reason.txt` notes).
- **Sequencing note:** the SC-T001 stop condition (user policy review) was still logged as
  pending; SC-T002 proceeded on explicit direction that SC-T001 had landed and SC-T002 should
  execute. If policy review later changes SC-T001 outputs, this contract re-syncs (pre-release,
  no tag yet — free to amend).
- **ADR re-confirmations:** ADR-0003 re-confirmed at authoring — exact patch `openapi: 3.1.0`.
  ADR-0002 re-confirmed — all schema objects are JSON Schema 2020-12 dialect (uses
  `dependentSchemas`, `not`, `const`, type arrays for nullability).
- **Authoring decisions (contract surface; all within the approved Contract 1 semantics):**
  - `error.request_id` is a **required** member of the error envelope — the plan requires the
    request ID in error bodies; this is an additive extension over the plain OpenAI envelope.
  - "Monotonically increasing chunk indices" is encoded checkably as a **required SSE `id:`
    field** per event (zero-based, +1 per event, including the error event and `[DONE]`).
    Standard SSE; OpenAI clients ignore it, so wire compatibility is preserved.
  - `canceled` carries `http_status: 499` in the taxonomy as a logging/metrics convention only —
    no HTTP response is delivered to a disconnected client; it is not an OpenAPI response entry.
  - `max_tokens`/`max_completion_tokens` are mutually exclusive (`conflicting_parameters`);
    `stream_options` requires explicit `stream: true` (encoded via `not` / `dependentSchemas`).
  - Message subset = `role` (`system|user|assistant`) + **string** `content`; the
    rejection-not-ignore rule applies at every nesting level (`additionalProperties: false`
    throughout; array-of-parts content is `unsupported_value`).
  - `n` unsupported ⇒ exactly one choice with `index: 0` (encoded `maxItems: 1`, `const: 0`);
    `finish_reason` ∈ {`stop`, `length`}.
  - Retryability vocabulary in `x-error-taxonomy`: `never` / `after_retry_after` /
    `pre_first_token_only`, plus the global never-retry-after-first-token rule.
  - The `text/event-stream` media-type schema is the **per-event payload** schema
    (`oneOf` chunk|error) — precedent: OpenAI's published spec; also documents the mid-stream
    error event shape machine-readably.
- **Validation evidence (commands run 2026-07-10):**
  - `npx -y @redocly/cli@latest lint openapi/inference-api.yaml` → “Your API description is
    valid.” **0 errors, 4 warnings, exit code 0.** Accepted warnings, each deliberate:
    `info-license` ×1 (repo has no license yet — license choice is a user decision, latest at
    SC-T009 release review); `operation-4xx-response` ×3 (`/healthz`, `/readyz`, `/metrics` are
    unauthenticated, parameterless probe/scrape endpoints with genuinely no 4xx surface —
    fabricating one would distort the contract). Revisit via lint config at SC-T008.
  - `python3 -m openapi_spec_validator openapi/inference-api.yaml` → `OK`, exit code 0.
  - Throwaway fixture-consistency script (scratchpad; permanent kit is SC-T008), Python
    `jsonschema` Draft 2020-12: **81/81 checks PASS** — positives validate (3 requests,
    response, model list, 10 error envelopes = full taxonomy exactly once); all 14 negatives
    fail their schema (spot-checked failure *reasons*: `not`, `dependentSchemas`, nested
    `additionalProperties` each trip on the intended fixture); SSE transcripts checked for
    framing, strictly monotonic `id:` from 0, chunk validity, constant `id`/`created`,
    exactly-one `finish_reason`, usage-only final chunk iff `include_usage`, terminal `[DONE]`
    on success, error-event-then-close (no `[DONE]`, no retry) on the error transcript.
  - Redocly quirk recorded: its example validator applies `dependentSchemas` subschemas in
    isolation with injected strictness, falsely flagging valid inline streaming examples; the
    inline streaming request example was dropped in favor of the golden fixtures (which are
    canonical anyway). Python jsonschema validates the same instances correctly.
- **Classification:** pre-release contract authoring (no tag exists); ships in v0.1.0. No
  SemVer bump applicable yet.

### 2026-07-10 — SC-T003 benchmark data schemas (Contract 3)

- Authored `schemas/{workload,benchmark-run,raw-event,benchmark-result}.schema.json`
  (JSON Schema **2020-12** per ADR-0002 — re-confirmed here at first-standalone-schema time as
  the ADR requires) plus fixtures: the 8 named workloads under `examples/workloads/`
  (non-normative; README states inferbench owns the canonical suite), a run manifest /
  raw-events JSONL / result under `examples/benchmark/`, and negatives under `invalid/` per
  ADR-0004 (incl. the required deliberately-incomplete manifest).
- **Structural encodings of prose rules:** closed-loop arrival requires
  `closed_loop_disclosed: const true`; prefix ratio > 0 requires a prefix length; cancellation
  rate > 0 requires a cancellation point; slow-client fraction > 0 requires a read throttle;
  `via-gateway`/`gateway-mock` manifests require the gateway block and `engine-direct` forbids
  it; `pooled_percentiles.method` admits only `"pooled-raw-events"` (averaging per-run
  percentiles is inexpressible); `shed_rate` and `stall_rate` are required siblings inside the
  `goodput` block and `goodput.slo_ref` is required; the `validity` block is required.
- **Recorded interpretations (reversible; pre-release so no deviation pause):**
  (a) the manifest gained required `workload_ref{name,version,seed}` — not in the Contract 3
  field list verbatim but required by the §7 comparability rule (keys on workload
  version+seed); (b) `knee_estimate` and `cost` are required-but-nullable, with normative
  descriptions forcing a `validity.threats_to_validity` note when null (mock runs have no cost
  profile; single-rate sets have no knee); (c) raw-event latencies are defined as client-side
  (the `client_*` mirror series of metrics.md), seconds + RFC3339 timestamps; (d) `$id` uses
  the placeholder namespace `https://serving-contracts.inference-systems.dev/schemas/…` — an
  identifier, not a location; revisit before the v0.1.0 tag if a real URL exists.
- **Verification (commands run 2026-07-10):** `pip install jsonschema` (4.26.0, Python
  3.11.15); throwaway script `validate.py` (session scratchpad; permanent kit is SC-T008) →
  **RESULT: ALL CHECKS GREEN** on first run: 5 schemas meta-validate against draft 2020-12;
  exactly the 8 named workloads present and valid; manifest + 5 JSONL events + result valid;
  all 6 negative fixtures fail for the intended reason (failure messages inspected); in-memory
  checks (closed-loop with/without disclosure flag, gateway-block conditionality both ways,
  goodput sibling/slo_ref removal) behave as specified.
- **Classification:** pre-release contract authoring (no tag exists); ships in v0.1.0.

### 2026-07-10 — SC-T004 backend-capability schema (Contract 4)

- Authored `schemas/backend-capability.schema.json` +
  `examples/capabilities/{mock,llamacpp,vllm}.json` + one negative
  (`invalid/missing-release-observability.json`).
- Metric names are **mapped, never hardcoded**: `metrics.name_mapping` requires an `as_of`
  date + `verified_against_version` + canonical-key→engine-name entries (null = no engine
  equivalent). The canonical keys (`queue_waiting_requests`, `running_requests`,
  `kv_cache_usage_ratio`, `prefix_cache_hit_rate`, `generation_tokens_total`,
  `prompt_tokens_total`) are stable contract surface; engine-native names are per-descriptor
  data.
- **Boundary rule** stated normatively in the schema description: the descriptor declares what
  the engine exposes; it MUST NOT carry gateway scheduling directives (`concurrency_hints` is
  explicitly hints-only; batching/KV/prefix internals appear only as observability facts).
- **Volatile-fact flags preserved (risk R3):** llamacpp/vllm descriptors carry
  `provenance.method: "source-reported"` and "as of 2026-07 — re-verify at use time" flags on
  metric names, cancellation behavior, and usage-in-stream; engine versions/commits/model IDs
  are illustrative. vLLM names (`vllm:num_requests_waiting`, `vllm:gpu_cache_usage_perc`, …)
  and llama.cpp names (`llamacpp:requests_processing`, …) were written from training-time
  knowledge, not probed in this offline session — they MUST be re-verified at adapter-probe
  time (IG-T005/T012/T014); the schema's dated-mapping design exists precisely so this is a
  data update, not a schema change.
- **Verification:** same `validate.py` run (green above): schema meta-validates; the 3
  descriptors validate; the negative fails; `release_observability.observable=true` with empty
  `signals` is rejected (structural check).
- **Classification:** pre-release contract authoring; ships in v0.1.0.

### 2026-07-10 — SC-T005 metrics vocabulary + cardinality policy (Contract 2)

- Authored `metrics/metrics.md` — exhaustive 11-metric canonical table, declared histogram
  bucket boundaries for all 4 histograms, label value semantics, normative measurement points
  (gateway TTFT = first upstream body byte at the gateway; client-side TTFT/ITL/e2e as
  separately named `client_*` series; ITL = inter-chunk gap between content-bearing chunks;
  stall = max gap vs SLO threshold; queue wait = admission-enqueue → dispatch), gateway span
  sequence `recv → queue.wait → upstream.connect → ttft → stream.relay → settle`, OTel GenAI
  semconv pin + platform attributes, exemplar rule — and `metrics/cardinality-policy.md`
  (allowed-label table with value-set sources, 10k active-series budget, forbidden-label list
  doubling as the PII guard, enforcement/drift hooks).
- **Prose-encoded structural rules:** `stage` has exactly one legal value `pre_first_token` —
  no label value exists for a post-first-token retry (mirrors Contract 1 never-retry rule);
  client and gateway latency series are separately named and MUST NOT be merged.
- **OTel GenAI semconv pin:** pinned to **OpenTelemetry Semantic Conventions v1.34.0**, `gen_ai.*`
  namespace, status **"Development" as of 2026-07 — re-verify at use time** (first emit
  wiring, IG-T006) and re-date. The pin version was chosen conservatively from
  known-published releases; the latest semconv release could not be verified from this
  offline session — flagged in the doc itself and here. Ambiguities found while applying the
  conventions go to `docs/experiments.md` (OSS track).
- **First-authored numbers:** histogram bucket boundaries did not pre-exist anywhere in the
  plan; they are authored here (rationale in metrics.md §2) and become breaking-change surface
  at v0.1.0 per the compatibility policy.
- **Verification (field-by-field cross-check script, run 2026-07-10):** metrics.md table ==
  Contract 2 table (04-shared-contracts.md) for all 11 metrics — names, types, and label sets
  exact; grep sweep of `/home/user/ai-infra/portfolio-planning/` found exactly 11
  `inference_*` roadmap metric names, all present in metrics.md (SC-T005 stop condition);
  span-sequence string, semconv pin + Development flag, all 4 platform attributes,
  measurement-point phrases, 4 bucket declarations, and forbidden-label mentions verified →
  **ALL CROSS-CHECKS GREEN** on first run.
- **Classification:** pre-release contract authoring; ships in v0.1.0.

### 2026-07-10 — SC-T008 consumer compatibility test kit

- Shipped `kit/` **inside the bundle**: `contracts-validate.py` (single-file CLI; Python stdlib
  + `jsonschema>=4.18` + `PyYAML>=6` only — standard validators per the architecture
  constraints, no SDKs/frameworks/consumer helpers), `validation-map.json` (fixture-path→schema
  mapping as configuration per ADR-0004, plus `api.*`→OpenAPI-component mapping),
  `requirements.txt`, `README.md` (usage + per-consumer wiring for infergate, inferbench,
  fleetlab, inferops — the SC-T008 stop condition).
- **Commands:** `list-schemas`; `validate --schema NAME FILE...`; `selftest` (positives MUST
  pass, `invalid/` MUST fail, schemas meta-validated, `.reason.txt` presence enforced per
  ADR-0004); `check DIR` (consumer-emitted artifacts; schema auto-detected from the
  `<name>.<schema>.json|jsonl` naming convention or forced via `--schema`). Exit codes 0/1/2
  (green / validation failure / usage-config error); `--json` emits a machine summary
  (`summary_format: 1` — bumping it is contract surface).
- **Schema-set growth (fleetlab/inferops note):** file schemas are auto-discovered from
  `schemas/*.schema.json`; rules for the upcoming ADR-0004 areas (`deployment/`, `faults/`,
  `capacity/`, `fleet/`) are pre-seeded and inert until SC-T006/T007 fixtures land. Verified by
  dropping a dummy `deployment-contract.schema.json` + fixtures into a bundle copy → selftest
  went 6 schemas / 33 positives / 21 negatives GREEN with zero kit changes.
- **Recorded choice (SSE scope):** the kit validates `.sse` transcripts **lightweight only** —
  SSE framing + every embedded `data:` JSON payload against `api.stream-event`
  (oneOf chunk|error), `[DONE]` as terminal sentinel. Ordering/monotonic-`id`/flush/
  usage-in-final-chunk/cancellation semantics are gateway-conformance testing owned by
  infergate's suite, out of kit scope (documented in `kit/README.md`). The deeper transcript
  checks run during SC-T002 remain recorded above as authoring-time evidence.
- **Verification (commands run 2026-07-10, from repo root):**
  - `python3 kit/contracts-validate.py selftest` → `positives 32/32 passed`,
    `negatives 20/20 failed-as-required`, `5 schemas meta-validated`, `selftest: GREEN`,
    exit 0.
  - Demonstrated failure (bundle copy with `seed` removed from `chat-short.json` and a valid
    descriptor planted under `capabilities/invalid/`) → both caught
    (`positive-failed` + `negative fixture PASSED validation`), `selftest: RED (2 problem(s))`,
    exit 1 — the validator can fail in both directions.
  - Consumer flow as inferbench: staged `examples/benchmark/*` + a workload under
    convention names (`run-20260710-a.benchmark-run.json`, `.raw-event.jsonl`,
    `.benchmark-result.json`, `chat-short.workload.json`) → `check` = 4/4 PASS exit 0; adding
    the incomplete manifest as an emitted artifact → exit 1 with
    `'hardware' is a required property` in the `--json` summary.
  - Exit-code spot checks: unknown schema → exit 2; mixed valid+invalid `validate` → exit 1;
    `.sse` via `validate --schema api.stream-event` → PASS.
  - Performance hypothesis measured: selftest `real 0m0.285s` (recorded in `docs/testing.md`).
- **Kit-carried contract surface** (changes follow the compatibility policy once released):
  exit codes, artifact naming convention, `summary_format`, `validation-map.json` rule set.
- **Classification:** pre-release; ships in v0.1.0. Redocly lint-config revisit flagged at
  SC-T002 was considered: the kit intentionally does not wrap the OpenAPI linter (lint runs in
  this repo's CI, not in consumer CI — consumers validate instances, not the spec itself).

### 2026-07-10 — SC-T009 release v0.1.0 (preparation; tag pending user review)

- Prepared the release **up to but excluding tagging** — the tag is created only after the
  mandatory user review of the release notes (policy §5 step 5; program review point at the
  Wave-1 exit review). **No tag exists yet.**
- **Files:** `RELEASES.md` (v0.1.0 release notes: bundle contents, known-open items, pre-1.0
  rule statement, migration policy, checklist results) and top-level `README.md` (bundle
  overview, pinning rules, kit pointer) added; SC-T009 status updated in `docs/tasks.md`.
- **Release-process checklist (policy §5), run 2026-07-10 from repo root:**
  1. *Classify* — initial release; all prior entries in this log are classified
     "pre-release contract authoring; ships in v0.1.0". Log complete.
  2. *Re-verify volatile pins* — session is offline; the OTel semconv pin (v1.34.0,
     "Development") and llama.cpp/vLLM metric-name mappings stay dated 2026-07 with their
     re-verify-at-use-time flags. Recorded in the release notes' known-open items rather than
     silently skipped; first live re-verification lands with IG-T005/T006.
  3. *Validate* — all green: `python3 kit/contracts-validate.py selftest` → 5 schemas
     meta-validated, positives 32/32, negatives 20/20 failed-as-required, GREEN, exit 0;
     `python3 -m openapi_spec_validator openapi/inference-api.yaml` → OK, exit 0;
     `npx -y @redocly/cli@latest lint openapi/inference-api.yaml` → valid, 0 errors, the same
     4 accepted warnings recorded at SC-T002 (`info-license` ×1, `operation-4xx-response` ×3),
     exit 0. Fixture completeness sweep: 10/10 error classes, 8/8 workloads, 3/3 capability
     descriptors, 3 SSE transcripts, benchmark manifest/raw-events/result, and every
     `invalid/` fixture paired with its `.reason.txt` (ADR-0004).
  4. *Release notes* — written (`RELEASES.md`).
  5. *User review* — **pending**; steps 6–8 (tag + artifact, I1 re-run, recording links)
     deferred until after it.
- **Decisions queued for the review:** (a) license (repo-wide + `info.license` in the OpenAPI
  spec — clears the accepted `info-license` lint warning); (b) real `$id` namespace vs the
  `https://serving-contracts.inference-systems.dev/schemas/…` placeholder (cheapest to change
  now, before any consumer dereferences it); (c) sign-off on shipping v0.1.0 without
  Contracts 5/6 + fleet schemas (SC-T006/T007 → later MINOR, additive).
- **Classification:** doc-only preparation (release notes, README, status updates); no
  contract surface changed. Ships in v0.1.0.

### 2026-07-10 — SC-T006 deployment + fault-scenario contracts (Contracts 5 and 6)

- **Files:** `schemas/deployment-contract.schema.json`, `schemas/fault-scenario.schema.json`,
  `examples/deployment/` (infergate.json, vllm-backend.json + `invalid/` grace-not-exceeding-
  max-stream, image-without-digest), `examples/faults/` (fs-01 … fs-12, one file per Contract 6
  catalog item + `invalid/` scenario-missing-abort-condition, metric-expectation-without-source).
- **Deployment contract choices:**
  - Image pinned by **digest** (required, `sha256:` pattern); tag informative only. A tag-only
    descriptor is the second negative.
  - **Warm-up-aware readiness encoded structurally:** the readiness probe requires a `warm_up`
    object with `ready_only_after_warm_up: const true` + a concrete `warm_signal` string —
    a descriptor that does not gate readiness on warm-up is not schema-valid (fs-11).
  - **Termination-grace > max-stream-duration:** JSON Schema 2020-12 cannot compare two sibling
    numeric fields, so the rule is encoded as a required const-true attestation field
    (`grace_period_exceeds_max_stream_duration`) whose description states the arithmetic MUST
    hold and that richer validators SHOULD check it; the negative fixture reports `false`
    honestly and fails the const. Recorded as the structural-encoding pattern for cross-field
    numeric constraints (same spirit as the benchmark-result pooled-percentile const).
  - `model_mount` is `null | object` — null permitted only for model-less components (gateway);
    `resources.gpu.count` has minimum 0 (the gateway is GPU-free by construction).
  - Secrets are **expectations only** (name/purpose/delivery/required); `additionalProperties:
    false` leaves no field where a value could go (security policy).
- **Fault-scenario choices:** every scenario carries `contract_item` (1–12, audited exactly-once
  across fixtures), source-qualified metric expectations (`gateway`/`client` = Contract 2
  vocabulary; `engine` = canonical keys via the capability `name_mapping`, never engine-native
  names — the second negative hardcodes `vllm:num_requests_waiting` to show why; `platform` =
  orchestration metrics), an optional `metrics_that_must_not_move` list (used for the
  no-post-first-token-retry and zero-5xx assertions in fs-01/02/05/08/09/11/12), and a required
  `abort_condition` (missing one is the first negative). Scenario semantics transcribe the
  Contract 6 catalog exactly (arrow semantics → expected_gateway_semantics statements).
- **Classification:** MINOR (new schemas + fixtures, additive); ships in v0.2.0.

### 2026-07-10 — SC-T007 fleet schemas (Contract 7 + inputs)

- **Files:** `schemas/{hardware-profile,model-profile,slo,cost-profile,capacity-recommendation}
  .schema.json`; `examples/fleet/` (hardware-a10g-g5-xlarge, model-llama31-8b,
  slo-gateway-targets, slo-chat-interactive, cost-g5-xlarge-ondemand + `invalid/`
  hardware-missing-provenance, slo-declared-in-advance, cost-reported-without-source);
  `examples/capacity/` (recommendation-chat-short-scaleout + `invalid/`
  recommendation-missing-uncertainty).
- **Provenance made structural, not advisory:** every quantitative fact in a profile is a
  `{value, provenance}` object; provenance requires `basis` (measured / source-reported /
  assumed) + `as_of` date, and `source` is conditionally required for measured/source-reported
  (a value that claims to come from somewhere must say where). Bare numbers are not schema-valid
  — the provenance-missing negative demonstrates it. `basis: assumed` is legal but must be
  explicit (the spot-price rate in the cost example is the worked assumed-value case). Identity
  fields (ids, model strings, checkpoint revisions) are identities, not measurements, and carry
  no provenance — the line is documented in each schema description.
- **SLO schema:** expresses all five program gateway targets (overhead p95/p99, cancellation
  propagation p95 gateway+mock, usage settle variance, key revocation, config publish) in
  `slo-gateway-targets.json` as source-reported objectives, and enforces the "model-level SLOs
  declared only from measurement" rule structurally: `scope: model-serving` conditionally forces
  every objective's `provenance.basis` to `measured` (the declared-in-advance negative fails on
  it). `slo-chat-interactive@0.1.0` and `cost-g5-xlarge-ondemand@0.1.0` deliberately carry the
  exact ids/versions the v0.1.0 benchmark-result example references — the dangling refs in that
  fixture now resolve within the bundle.
- **Capacity recommendation (Contract 7):** inputs are required references (benchmark-result
  IDs, workload name+version, SLO, cost profile, hardware profiles); predictions require
  goodput + latency + cost, and every predicted quantity structurally requires an
  `uncertainty` object with `lower`/`upper`/`method` (the capacity negative omits it);
  autoscaling signal is source-qualified like fault-scenario metrics; `assumptions` and
  `sensitivity_notes` are required non-empty; optional `re_measurement` block (workload ref,
  single declared comparability variable, success criteria) added beyond the Contract 7 field
  list to make the I6 loop closure machine-checkable — additive, justified by Contract 7's
  "closes the I6 feedback loop in a machine-checkable form" sentence.
- **Scenario E expressibility (stop condition):** end-to-end chain in shipped fixtures:
  `examples/benchmark/result.json` (res-2026-07-10-chatshort-vllm-a10g-001) →
  `examples/capacity/recommendation-chat-short-scaleout.json` (references that result id,
  chat-short@0.1.0, slo-chat-interactive@0.1.0, cost-g5-xlarge-ondemand@0.1.0,
  hardware-a10g-g5-xlarge@0.1.0; recommends 1→3 replicas at the measured engine flags; cost
  arithmetic consistent with the result's 0.000037 USD/success at 1.006 USD/h) → deployment
  shape `examples/deployment/vllm-backend.json` (same model revision pin) → `re_measurement`
  plan with replica count as the single declared variable.
- **Classification:** MINOR (new schemas + fixtures, additive); ships in v0.2.0.

### 2026-07-10 — v0.2.0 release preparation (tag pending user review)

- **Kit impact: zero code changes.** The fixture rules pre-seeded in `kit/validation-map.json`
  at SC-T008 (deployment/, faults/, capacity/, fleet/) activated unchanged when the fixtures
  landed; schema auto-discovery picked up all seven new schemas. Only the map's `$comment` was
  updated (rules no longer described as inert; fleet filename-ordering note added: the four
  fleet rules match hardware-/model-/slo-/cost- prefixes in order, so fleet fixture filenames
  must not contain an earlier prefix as a substring — checked for all shipped names).
- **Verification (commands run 2026-07-10, from repo root):**
  - Baseline before the change: `python3 kit/contracts-validate.py selftest` → 5 schemas,
    positives 32/32, negatives 20/20, GREEN, exit 0.
  - After: `python3 kit/contracts-validate.py selftest` → **12 schemas meta-validated,
    positives 52/52 passed, negatives 28/28 failed-as-required, GREEN, exit 0** (+7 schemas,
    +20 positives, +8 negatives).
  - `selftest --verbose` inspection: all 8 new negatives fail on their **intended** rule
    (uncertainty required; grace attestation const; digest required; metric source required;
    abort_condition required; provenance-source conditional; bare-number-vs-provenanced-object;
    model-serving measured-basis const) — none fail incidentally.
  - Coverage audit: 12/12 fault files, `contract_item` = {1…12} exactly once, scenario_ids
    unique (scripted check).
- **RELEASES.md:** v0.2.0 entry written (class MINOR, additive; per-contract change list;
  Scenario E evidence; checklist steps 1–4 recorded, step 2 noted offline — new volatile facts
  are dated + flagged in the fixtures themselves). **Status: prepared, tag pending review** —
  per policy §5 step 5 the tag is a user-review point; steps 6–8 deferred. `README.md` bundle
  table extended (and the stale pre-v0.1.0 license line corrected to Apache-2.0 — doc-only).
- **Classification:** the release itself is MINOR; README/notes edits are doc-only.

### 2026-07-10 — raw-event coordinated-omission fix (breaking; rides the untagged v0.2.0)

- **Trigger:** the program's CO-safety review of the inferbench generator found latency was
  measured from actual wire-write (`send_ts`) instead of the scheduled send time, hiding
  connect/dispatch queueing under saturation (coordinated omission).
- **Change:** `schemas/raw-event.schema.json` — new REQUIRED `scheduled_send_ts` (date-time;
  schedule-plan send time) with the normative rule in its description: client-side TTFT and
  end-to-end latency are measured from `scheduled_send_ts`, not `send_ts`; `send_ts` kept as
  the actual wire-write time for diagnostics (description updated, as was `ttft_seconds`'s and
  the schema preamble); new OPTIONAL `send_slip_seconds` (number ≥ 0) = send_ts −
  scheduled_send_ts for observability.
- **Fixtures:** `examples/benchmark/raw-events.jsonl` updated (all 5 records carry
  `scheduled_send_ts`; 4 carry `send_slip_seconds`, one omits it to exercise optionality; the
  shed record carries the largest slip, 0.06 s, as the saturation illustration). New negative
  `examples/benchmark/invalid/raw-event-missing-scheduled-send.jsonl` (+ reason note): a
  v0.1.0-shaped event, failing on the new required field. One fixture rule added to
  `kit/validation-map.json` (`benchmark/invalid/raw-event-*.jsonl` → raw-event) — the
  pre-existing `benchmark/invalid/` rules were name-specific, so the new negative needed one.
- **Classification: BREAKING, carried in v0.2.0 as a pre-1.0 breaking MINOR** (policy §8) —
  legitimate only because v0.2.0 is still untagged; had v0.2.0 been tagged, this would have
  forced v0.3.0 (or a MAJOR post-1.0). Mandatory migration note written in the RELEASES.md
  v0.2.0 entry (affected: only inferbench IB-T002 evidence artifacts, to be regenerated;
  measurement-meaning consequence stated: v0.1.0-basis TTFT/e2e values are not comparable to
  v0.2.0-basis values). First exercised breaking change of the wave (R8 ceiling: ≤1).
- **Verification:** `python3 kit/contracts-validate.py selftest` → 12 schemas meta-validated,
  positives 52/52 passed, **negatives 29/29 failed-as-required** (was 28), GREEN, exit 0;
  `--verbose` confirms the new negative fails on `'scheduled_send_ts' is a required property`.

## Deviations
