# Releases — serving-contracts

Release notes live here, newest first. Each entry follows the release process in
`compatibility/compatibility-policy.md` §5: version + class, per-contract change list,
migration note (when applicable), deprecations, and — while in v0.x — the pre-1.0 rule
statement. Consumers pin releases by annotated git tag (`vMAJOR.MINOR.PATCH`, ADR-0001).

---

## v0.2.0 — deployment, fault-scenario, and fleet contracts (SC-T006/SC-T007) + raw-event coordinated-omission fix

- **Status:** released 2026-07-11 — user review passed (I2/Wave-2 review batch), annotated
  tag `v0.2.0` cut. Consumers pin this tag. (Remote note: the session git proxy drops tag
  pushes — `release/v0.2.0` branch is the pinnable remote ref until direct hosting; the
  annotated tag is authoritative in history.)
- **Class: MINOR — additive + ONE breaking change to `raw-event`, with explicit migration
  note (pre-1.0 rule, policy §8).** Seven new schemas and four new fixture areas are strictly
  additive. One pre-existing schema changed breakingly: `schemas/raw-event.schema.json` gains
  the REQUIRED field `scheduled_send_ts` (coordinated-omission fix from the program's
  CO-safety review of the inferbench generator — see migration note below). Everything else
  valid against v0.1.0 remains valid against v0.2.0. The pre-1.0 rule is exercised honestly:
  this is documented as breaking, never disguised as additive.

### Per-contract change list (all new surface)

| Contract | Files added | Notes |
|---|---|---|
| 3 — Benchmark data (**breaking**) | `schemas/raw-event.schema.json` (amended), `examples/benchmark/raw-events.jsonl` (updated), `examples/benchmark/invalid/raw-event-missing-scheduled-send.jsonl` (new negative) | **Breaking:** new REQUIRED field `scheduled_send_ts` (schedule-plan send time) + normative measurement rule: client-side TTFT and end-to-end latency are measured from `scheduled_send_ts`, not `send_ts`, so dispatch/connect/write queueing under saturation is never excluded (coordinated-omission safety); `send_ts` stays as the actual wire-write time for diagnostics. Additive alongside it: OPTIONAL `send_slip_seconds` (>= 0) = `send_ts` − `scheduled_send_ts`, recorded for observability. |
| 5 — Deployment | `schemas/deployment-contract.schema.json`, `examples/deployment/**` (infergate + vllm-backend descriptors; 2 negatives) | image pinned by digest; API+metrics ports; env/config mounts; startup/readiness/liveness with **warm-up-aware readiness** (required `warm_up` gate: readiness false during model load/warm-up); model mount (null only for model-less components); resources incl. GPU count (0 for the GPU-free gateway); graceful termination with required preStop drain hook and the **termination-grace > max-stream-duration rule** encoded as a required const-true attestation (JSON Schema cannot compare sibling numerics; numeric comparison is a documented SHOULD for richer validators); secret expectations (names/purposes only — values not expressible). |
| 6 — Fault scenarios | `schemas/fault-scenario.schema.json`, `examples/faults/**` (12 scenarios fs-01…fs-12; 2 negatives) | each scenario: ID, injection, expected gateway semantics, expected client-visible behavior, **metrics that must move** (source-qualified: gateway/client = Contract 2 vocabulary, engine = capability name-mapping canonical keys, platform), optional must-NOT-move list, abort condition. All 12 catalog items encoded exactly once (`contract_item` 1–12). |
| 7 — Capacity recommendation | `schemas/capacity-recommendation.schema.json`, `examples/capacity/**` (Scenario E fixture; 1 negative) | required input references (benchmark-result IDs, workload version, SLO, cost profile, hardware profiles); recommended topology (replica counts per hardware type + engine config in benchmark-run flag vocabulary); predicted goodput/latency/cost with **structurally required uncertainty** (interval + method); autoscaling signal + thresholds; required assumptions + sensitivity notes; optional `re_measurement` block closing the I6 loop. |
| Fleet schemas | `schemas/{hardware-profile,model-profile,slo,cost-profile}.schema.json`, `examples/fleet/**` (5 profiles; 3 negatives incl. the provenance-missing one) | **provenance mandatory and structural**: every quantitative value is a `{value, provenance}` object (basis measured/source-reported/assumed + date; source required unless assumed) — bare numbers and fabricated defaults are not schema-valid. SLO schema expresses the program's source-verified gateway targets and enforces that **model-serving SLOs are measurement-derived only** (scope conditional). |
| Kit | `kit/validation-map.json` (comment + one fixture rule) | the fixture rules pre-seeded at SC-T008 activated **unchanged** for the new areas; comment updated (rules no longer described as inert; fleet filename-ordering note added); one rule added for the new `benchmark/invalid/raw-event-*.jsonl` negative. No kit code change — schema auto-discovery worked as designed. |

### Scenario E (benchmark → recommendation → topology change → re-measurement)

Expressible end-to-end in shipped fixtures: `examples/benchmark/result.json`
(`res-2026-07-10-chatshort-vllm-a10g-001`, referencing `slo-chat-interactive@0.1.0` and
`cost-g5-xlarge-ondemand@0.1.0`) → `examples/capacity/recommendation-chat-short-scaleout.json`
(references that result ID, workload `chat-short@0.1.0`, those SLO/cost profiles, and
`hardware-a10g-g5-xlarge@0.1.0`; recommends 1→3 replicas with the measured engine config) →
deployment shape per `examples/deployment/vllm-backend.json` → `re_measurement` plan with the
replica count as the single declared comparability variable and goodput/TTFT/shed-rate success
criteria.

### Migration note — raw-event `scheduled_send_ts` (mandatory; pre-1.0 breaking MINOR)

- **What changed and why.** `raw-event` gains a REQUIRED `scheduled_send_ts` (same timestamp
  format as `send_ts`): the schedule-plan send time from the workload's arrival process. The
  program's CO-safety review of the inferbench generator found that latency was measured from
  the actual wire-write (`send_ts`) instead of the scheduled send, which hides connect/dispatch
  queueing under saturation (classic coordinated omission — exactly when latency matters most,
  the delayed sends made results look better). The normative rule now in the schema: client-side
  TTFT and end-to-end latency are measured from `scheduled_send_ts`; `send_ts` remains recorded
  for diagnostic comparison, and optional `send_slip_seconds` (= `send_ts` − `scheduled_send_ts`)
  captures the slip for observability.
- **Who is affected.** Only inferbench and its emitted artifacts. The sole existing raw-event
  corpus is IB-T002's evidence artifacts, which will be regenerated; no published benchmark
  results are invalidated (none exist outside fixtures). fleetlab consumes results, not raw
  events, and is untouched; infergate/inferops do not touch this schema.
- **What to do (mechanical).** In the generator: (1) record the schedule-plan send time per
  request and emit it as `scheduled_send_ts`; (2) re-base client-side TTFT and end-to-end
  measurements on it (`send_ts` stays as the wire-write timestamp); (3) optionally emit
  `send_slip_seconds`; (4) regenerate any raw-event artifacts kept as evidence and re-run
  `kit/contracts-validate.py check` — v0.1.0-shaped events now fail validation (by design;
  see the new negative fixture).
- **Measurement-meaning consequence (stated per policy §3).** TTFT/e2e values recorded under
  v0.1.0 semantics are NOT comparable to values recorded under v0.2.0 semantics; any
  cross-version comparison must re-measure, not re-label.

### Release-checklist results (policy §5, run 2026-07-10, steps 1–4; tag blocked on step 5)

1. **Classify** — MINOR under the pre-1.0 rule: additive (new schemas + fixtures) plus one
   breaking change to `raw-event` carried with the mandatory migration note above (policy §8:
   v0.x MINOR may break WITH an explicit migration note; this is the first exercised breaking
   change, within the ≤1-per-wave ceiling). Classification logged in
   `docs/implementation-notes.md`.
2. **Re-verify volatile pins** — session offline; new volatile facts (A10G/g5.xlarge specs,
   g5.xlarge on-demand price, Llama-3.1-8B sizes, vLLM image/version in examples) are dated
   2026-07-10 with "as of 2026-07 — re-verify at use time" flags in the fixtures themselves;
   the spot rate is explicitly `basis: assumed`. No v0.1.0 pin touched.
3. **Validate** — `python3 kit/contracts-validate.py selftest` → **12 schemas meta-validated
   (2020-12), positives 52/52 passed, negatives 29/29 failed-as-required, GREEN, exit 0**
   (v0.1.0 baseline re-confirmed this session: 5 schemas, 32/32, 20/20). Coverage sweep:
   12/12 fault scenarios (`contract_item` 1–12 each exactly once), 2 deployment descriptors,
   5 fleet profiles, 1 capacity recommendation; every new `invalid/` fixture fails on its
   intended rule and carries its `.reason.txt` (ADR-0004). OpenAPI untouched (no re-lint
   needed; spec byte-identical to v0.1.0).
4. **Release notes** — this entry.
5. **User review** — **pending**; steps 6–8 (tag + artifact, I1 re-run, recording) deferred
   until after it.

### Deprecations introduced

None.

### Pre-1.0 rule (normative while in v0.x)

Restated per policy §5: during `v0.x`, a MINOR release MAY contain breaking changes only with
an explicit migration note. **This release contains exactly one** (raw-event
`scheduled_send_ts`, migration note above) — documented honestly, not disguised as additive.
Ceiling check: first breaking change of the wave (limit: no more than one per program wave
after v0.2 — risk R8 trigger). PATCH must never break, at any version.

---

## v0.1.0 — initial contract bundle

- **Status:** released 2026-07-10 — user review passed (Wave-1 exit review), annotated tag
  `v0.1.0` cut. Consumers pin this tag.
- **Class:** initial release (no prior tag; SemVer classification of changes starts with the
  next release). All contract surface below is new.

### Contents of the bundle

| Contract | Files | State in v0.1.0 |
|---|---|---|
| 1 — Inference API (OpenAI-compatible subset) | `openapi/inference-api.yaml`, `examples/api/**` | Complete: endpoints + supported request-field subset with the rejection-not-ignore rule, SSE streaming semantics (framing, monotonic `id:`, `[DONE]`, usage-in-stream via `stream_options.include_usage`, mid-stream error event), error envelope + full 10-class taxonomy with retryability, request-ID and cancellation contracts. Fixtures: positive (requests, response, model list, 3 SSE transcripts, all 10 error envelopes) + 14 negatives (one per rejection case). |
| 2 — Metrics + trace vocabulary | `metrics/metrics.md`, `metrics/cardinality-policy.md` | Complete: canonical 11-metric table (types, labels, units-in-name, declared histogram bucket boundaries), normative TTFT/ITL/queue-wait measurement points with gateway-side vs client-side (`client_*`) series separated, gateway span sequence, OTel GenAI semconv pin (v1.34.0, status "Development" as of 2026-07 — re-verify at use time), allowed-label table + forbidden-label list + 10k active-series budget. |
| 3 — Benchmark data | `schemas/{workload,benchmark-run,raw-event,benchmark-result}.schema.json`, `examples/workloads/**`, `examples/benchmark/**` | Complete: all four schemas with the pooled-percentile, shed-adjacent-goodput and validity-block rules encoded structurally; the 8 named workloads as **non-normative** example fixtures (canonical suite is inferbench's); run-manifest / raw-events / result fixtures + negatives (incl. the deliberately-incomplete manifest). |
| 4 — Backend capability | `schemas/backend-capability.schema.json`, `examples/capabilities/**` | Complete: capability descriptor with dated engine metric-name **mapping** (never hardcoded; "as of 2026-07 — re-verify at use time"), cancellation-release observability; mock / llama.cpp / vLLM example descriptors + negative. |
| Compatibility policy | `compatibility/compatibility-policy.md` | Normative: SemVer rules for the bundle, breaking-change definition (shape **and** measurement-meaning), deprecation rules, release process, consumer-test (I1) mechanism, pinning + benchmark comparability rule, pre-1.0 rule. |
| Consumer compatibility kit | `kit/` (`contracts-validate.py`, `validation-map.json`, `requirements.txt`, `README.md`) | Validation-only CLI shipping inside the bundle; `selftest` / `validate` / `check` commands; per-consumer wiring docs for infergate, inferbench, fleetlab, inferops. Kit-carried contract surface: exit codes (0/1/2), artifact naming convention, `--json` `summary_format: 1`, `validation-map.json` rule set. |

Also in the bundle: `docs/` (program documentation, ADRs — explanatory, not contract surface
except where the policy says otherwise) and this file.

### Known-open items (deliberately not in v0.1.0)

- **Contracts 5 and 6 (deployment descriptor, fault scenarios) and the fleet schemas
  (hardware/model/SLO/cost/capacity-recommendation)** — SC-T006/SC-T007 — are **not** in this
  release. They arrive in a later **MINOR** (additive: new schemas + fixtures). The kit already
  auto-discovers new `schemas/*.schema.json` and has inert fixture rules pre-seeded for
  `deployment/`, `faults/`, `capacity/`, `fleet/`, so their arrival requires no kit change.
- **Schema `$id` namespace** — RESOLVED at the Wave-1 exit review (2026-07-10): user selected
  `https://github.com/duy-tung/serving-contracts/schemas/…` (stable identifier tied to the
  repo's home; not required to be resolvable). Applied to all five schemas before tagging.
- **License** — RESOLVED at the Wave-1 exit review (2026-07-10): user selected **Apache-2.0**
  for all six portfolio repositories. `LICENSE` added and `info.license` set in the OpenAPI
  document before tagging; the Redocly `info-license` warning is cleared.
- **Volatile pins carried, not re-verified online:** the OTel GenAI semconv pin (v1.34.0,
  "Development") and the llama.cpp/vLLM engine metric names in the capability examples were
  authored offline from training-time knowledge and are flagged "as of 2026-07 — re-verify at
  use time" in the files themselves. First re-verification happens at first emit/probe wiring
  (IG-T005/T006); descriptor updates are data changes, not schema changes, by design.

### Pre-1.0 rule (normative while in v0.x)

Per `compatibility/compatibility-policy.md` §8: during `v0.x`, a **MINOR release MAY contain
breaking changes only with an explicit migration note** — documented honestly, never disguised
as additive. **PATCH must never break, at any version.** Ceiling: no more than one breaking
change per program wave after v0.2 (risk R8 trigger). `v1.0.0` freezes the shapes of
Contracts 1–3 and requires a breaking-change audit (SC-T010).

### Migration policy

- There is nothing to migrate **to** v0.1.0 (first release). Consumers adopt it by pinning the
  tag in CI config and in the inference-lab pins file, then wiring the kit per `kit/README.md`.
- **From v0.1.0 onward**, migrations follow the compatibility policy: every MAJOR release —
  and every pre-1.0 breaking MINOR — ships a **mandatory migration note** in these release
  notes (what changed, why, per-consumer impact, mechanical upgrade steps). Deprecations carry
  `deprecated: true` + a removal version; at least one MINOR separates deprecation from
  removal, and fixtures exercising deprecated fields stay in `examples/` until the removal
  release. Milestone I1 re-runs on **every** release; a MAJOR is not "done" until every
  consumer has bumped its pin and I1 is green.

### Deprecations introduced

None.

### Release-checklist results (policy §5, run 2026-07-10, steps 1–4; tag blocked on step 5)

1. **Classify** — initial release; per-change classification log in
   `docs/implementation-notes.md` is complete (all entries "pre-release contract authoring;
   ships in v0.1.0").
2. **Re-verify volatile pins** — attempted; this session is offline, so the semconv pin and
   engine metric names remain dated 2026-07 with re-verify-at-use-time flags (see known-open
   items). Recorded, not silently skipped.
3. **Validate** — all green:
   - `python3 kit/contracts-validate.py selftest` → 5 schemas meta-validated (2020-12),
     positives 32/32 passed, negatives 20/20 failed-as-required, **GREEN**, exit 0.
   - `python3 -m openapi_spec_validator openapi/inference-api.yaml` → `OK`, exit 0.
   - `npx -y @redocly/cli@latest lint openapi/inference-api.yaml` → valid, **0 errors**,
     4 accepted warnings (1× `info-license` — license pending; 3× `operation-4xx-response` on
     the probe/scrape endpoints, deliberate), exit 0.
   - Fixture completeness sweep: 10/10 error-class envelopes, 8/8 named workloads, 3/3
     capability descriptors, 3 SSE transcripts (success, with-usage, mid-stream error),
     benchmark manifest + raw events + result present; every `invalid/` fixture has its
     `.reason.txt` (ADR-0004).
4. **Release notes** — this entry.
5. **User review** — passed 2026-07-10 (Wave-1 exit review): release approved; license
   Apache-2.0; `$id` namespace `github.com/duy-tung` path. Post-review re-validation run
   green (lint 0 errors 0 warnings-accepted-remaining except probe-4xx; selftest 32/32 + 20/20).
6. **Tag** — `v0.1.0` created 2026-07-10. 7. I1 re-run: tracked per consumer as each wires
   the kit (infergate green at IG-T002 pin re-check). 8. Recorded in inference-lab pins.
