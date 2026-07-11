# Tasks — serving-contracts

Stable IDs SC-T001…SC-T010; use exactly these. All ten tasks are **Required** — nothing here is
stretch (the only flexible dimension is depth of *examples* beyond required coverage).
Execution order: SC-T001 first; then SC-T002/T003 (parallel), SC-T004–T007 (parallel after T001);
SC-T008 after T002/T003; SC-T009 (release, user review); SC-T010 when milestone-I5 experience
exists.

---

## SC-T001 — Bootstrap repo docs + versioning/compatibility policy

- **Goal / Repository:** create the full `docs/` set and the compatibility policy. serving-contracts.
- **Requirement:** contract inventory (all seven + fleet schemas), SemVer rules, breaking-change
  definition, deprecation rules, release process, consumer-test approach — per the plan's
  "Versioning and evolution policy".
- **Dependencies:** approved plan.
- **Expected files:** `docs/*` (all 15 + `adr/`), `compatibility/compatibility-policy.md`.
- **Complexity:** Small. **Critical path:** yes. **Parallel-safe:** no. **Required.**
- **Review focus:** policy soundness (breaking-change definition covers measurement-meaning
  changes, not just shape changes).
- **Verification:** docs complete per the plan's §6 checklist; policy internally consistent
  (pre-1.0 rule, deprecation window, I1 re-run triggers all stated).
- **Evidence:** committed policy + docs.
- **Integration impact:** unblocks all consumers and every other SC task.
- **Stop condition:** policy reviewed by the user.

## SC-T002 — Inference API contract

- **Goal / Repository:** author Contract 1 as OpenAPI + fixtures. serving-contracts.
- **Requirement:** OpenAPI subset (endpoints + the enumerated request-field subset,
  rejection-not-ignore rule), SSE semantics (`data:` framing, `[DONE]`, flush, ordering,
  usage-in-stream via `stream_options.include_usage`), error envelope + full taxonomy with
  retryability, request-ID contract, cancellation contract, examples — per Contract 1.
- **Dependencies:** SC-T001.
- **Expected files:** `openapi/inference-api.yaml`, `examples/api/*` (positive + negative fixtures).
- **Complexity:** Medium. **Critical path:** yes. **Parallel-safe:** no. **Required.**
- **Review focus:** subset completeness vs OpenAI shapes; the rejection-not-ignore rule;
  mid-stream-error-never-retried semantics.
- **Verification:** spec lints (OpenAPI linter); fixtures validate against the spec; negative
  fixtures (unsupported fields) exist for each rejection case.
- **Evidence:** spec + fixtures + lint output.
- **Integration impact:** gates IG-T002 (gateway skeleton) and IB-T002 (generator core).
- **Stop condition:** fixtures cover stream, non-stream, and all ten error classes.
- **Status:** done 2026-07-10 — spec + fixtures committed; lint/validation evidence in
  `docs/implementation-notes.md` (stop condition met: stream, non-stream, all ten error
  classes, and per-rejection-class negatives covered).

## SC-T003 — Benchmark data schemas

- **Goal / Repository:** author Contract 3. serving-contracts.
- **Requirement:** workload / benchmark-run / raw-event / benchmark-result schemas with every
  field listed in Contract 3, plus the 8 named workload examples (non-normative fixtures; the
  canonical suite is inferbench's).
- **Dependencies:** SC-T001.
- **Expected files:** `schemas/{workload,benchmark-run,raw-event,benchmark-result}.schema.json`,
  `examples/workloads/*`.
- **Complexity:** Medium. **Critical path:** yes. **Parallel-safe:** yes. **Required.**
- **Review focus:** manifest completeness (pins, engine flags, hardware, warm-up policy,
  hypothesis); pooled-percentile + shed-adjacent-goodput + validity-block rules encoded in
  structure, not just prose.
- **Verification:** JSON Schema validation of all examples; a deliberately incomplete manifest
  fixture fails validation.
- **Evidence:** schemas + examples + validator output.
- **Integration impact:** gates IB-T002 and FL-T002.
- **Stop condition:** all 8 workloads expressible (including prefix-sharing ratio,
  cancellation-rate and slow-client profiles, closed-loop disclosure flag).

## SC-T004 — Backend-capability schema

- **Goal / Repository:** author Contract 4. serving-contracts.
- **Requirement:** capability fields per Contract 4, including metric-name mapping (engine metric
  names vary by version — mapped, never hardcoded; as of 2026-07, re-verify) and
  cancellation-release observability.
- **Dependencies:** SC-T001.
- **Expected files:** `schemas/backend-capability.schema.json`,
  `examples/capabilities/{mock,llamacpp,vllm}.json`.
- **Complexity:** Small. **Critical path:** no. **Parallel-safe:** yes. **Required.**
- **Review focus:** no engine internals leak into gateway responsibilities (capability describes
  what the engine exposes, not how the gateway should schedule).
- **Verification:** three example descriptors validate.
- **Evidence:** schema + examples.
- **Integration impact:** infergate adapters (IG-T005/T012/T014), inferbench feature-gating.
- **Stop condition:** mock, llama.cpp, and vLLM example descriptors validate.

## SC-T005 — Metrics vocabulary + cardinality policy

- **Goal / Repository:** author Contract 2. serving-contracts.
- **Requirement:** the canonical metric table (all 11 metrics with types, labels, units-in-name,
  declared histogram bucket boundaries), forbidden-label list, trace attributes with the OTel
  GenAI semconv version pin (status "Development" as of 2026-07 — pin mandatory, re-verify at
  use time), platform attributes, span sequence, and the normative TTFT/ITL/queue-wait
  measurement-point definitions.
- **Dependencies:** SC-T001.
- **Expected files:** `metrics/metrics.md`, `metrics/cardinality-policy.md`.
- **Complexity:** Small. **Critical path:** yes. **Parallel-safe:** yes. **Required.**
- **Review focus:** TTFT/ITL/queue-wait definitions unambiguous (gateway-side vs client-side
  series explicitly separated).
- **Verification:** doc review; cross-check that every metric named anywhere in the program
  roadmap appears here; fixture dashboard names (inferops) can be keyed to it.
- **Evidence:** committed vocabulary.
- **Integration impact:** IG-T006 (gateway observability), IO-T003 (dashboards), IB-T005
  (analysis), FL-T003 (models). Ambiguities discovered while writing this are candidate OSS
  contributions (see `docs/oss-opportunities.md`).
- **Stop condition:** every roadmap metric named here.

## SC-T006 — Deployment + fault-scenario contracts

- **Goal / Repository:** author Contracts 5 and 6. serving-contracts.
- **Requirement:** deployment descriptor schema (all Contract 5 fields, including warm-up-aware
  readiness and termination-grace > max-stream-duration); fault-scenario schema + all 12
  scenarios encoded with ID, injection, expected gateway semantics, expected client-visible
  behavior, metrics that must move, abort condition.
- **Dependencies:** SC-T001.
- **Expected files:** `schemas/{deployment-contract,fault-scenario}.schema.json`, `examples/faults/*`.
- **Complexity:** Medium. **Critical path:** no. **Parallel-safe:** yes. **Required.**
- **Review focus:** termination-grace > max-stream rule; scenario semantics match Contract 6 exactly.
- **Verification:** examples validate; 12 scenario files present and schema-valid.
- **Evidence:** schemas + examples.
- **Integration impact:** IO-T002 (cluster baseline), IO-T006/T007 (fault campaigns), IG-T016
  (release descriptor).
- **Stop condition:** 12 scenarios encoded.
- **Status:** done 2026-07-10 — `schemas/{deployment-contract,fault-scenario}.schema.json` +
  `examples/deployment/**` (2 descriptors, 2 negatives) and `examples/faults/**` (fs-01…fs-12,
  all 12 catalog items encoded exactly once, 2 negatives). Termination-grace > max-stream rule
  encoded as a required const-true attestation (JSON Schema cannot compare sibling numerics) +
  documented arithmetic SHOULD; warm-up-aware readiness is a required `warm_up` gate. Selftest
  green (see `docs/implementation-notes.md`); ships in v0.2.0 (prepared, tag pending review).

## SC-T007 — Fleet schemas

- **Goal / Repository:** author hardware/model/SLO/cost/capacity-recommendation schemas
  (Contract 7 + inputs). serving-contracts.
- **Requirement:** five schemas with mandatory provenance fields (measured / source-reported /
  assumed + date); capacity-recommendation fields per Contract 7 including stated uncertainty;
  SLO schema expresses the gateway targets and supports measurement-derived model-level SLOs.
- **Dependencies:** SC-T001.
- **Expected files:**
  `schemas/{hardware-profile,model-profile,slo,cost-profile,capacity-recommendation}.schema.json`,
  examples.
- **Complexity:** Medium. **Critical path:** no. **Parallel-safe:** yes. **Required.**
- **Review focus:** provenance mandatory (validation fails without it); no fabricated defaults.
- **Verification:** examples validate; a provenance-less example fails.
- **Evidence:** schemas + examples.
- **Integration impact:** FL-T002 (ingestion), IL-T006 (Scenario E / milestone I6).
- **Stop condition:** Scenario E (benchmark results → recommendation → deployment change →
  re-measurement) is expressible end-to-end in fixtures.
- **Status:** done 2026-07-10 — five fleet schemas with structural provenance (every
  quantitative value is a `{value, provenance}` object; basis measured/source-reported/assumed
  + date; source required unless assumed); `examples/fleet/**` (5 profiles incl. the gateway-
  targets SLO and the measured chat-interactive SLO; 3 negatives incl. the provenance-missing
  one) + `examples/capacity/**` (Scenario E recommendation + missing-uncertainty negative).
  Stop condition met: Scenario E chain is expressible end-to-end in shipped fixtures
  (benchmark result → recommendation → 1→3-replica topology change → re-measurement plan);
  evidence in `RELEASES.md` v0.2.0 entry and `docs/implementation-notes.md`. Ships in v0.2.0
  (prepared, tag pending review).

## SC-T008 — Consumer compatibility test kit

- **Goal / Repository:** golden fixtures + validation tooling consumable in each consumer repo's
  CI. serving-contracts.
- **Requirement:** `examples/**` organized as the golden fixture set (positive + negative); a
  minimal validator CLI/config wrapping standard schema validators; documented wiring
  instructions per consumer (fetch pinned release → validate own emitted artifacts against
  schemas → validate accepted inputs against fixtures).
- **Dependencies:** SC-T002, SC-T003.
- **Expected files:** `examples/**`, minimal validator CLI/config, usage docs.
- **Complexity:** Medium. **Critical path:** yes. **Parallel-safe:** no. **Required.**
- **Review focus:** kit stays validation-only (no framework, no shared-library creep).
- **Verification:** kit runs green locally against all fixtures; deliberately broken fixture fails.
- **Evidence:** kit output (both green and demonstrated-failure runs).
- **Integration impact:** this is the I1 mechanism.
- **Stop condition:** four consumer repos can wire it (documented usage, no source checkout of
  this repo needed).
- **Status:** done 2026-07-10 — kit at `kit/` (`contracts-validate.py` + `validation-map.json`
  config + `requirements.txt` + `README.md` with per-consumer wiring for all four consumers);
  self-test green (32 positives pass, 20 negatives fail as required, 5 schemas meta-validated),
  demonstrated-failure and consumer-flow (inferbench `check`) evidence in
  `docs/implementation-notes.md`.

## SC-T009 — Release v0.1.0

- **Goal / Repository:** first tagged bundle. serving-contracts.
- **Requirement:** tagged bundle + release notes + migration policy stated (pre-1.0 rules explicit).
- **Dependencies:** SC-T002–T005, SC-T008.
- **Expected files:** tag `v0.1.0`, release notes, downloadable bundle artifact.
- **Complexity:** Small. **Critical path:** yes. **Parallel-safe:** no. **Required.**
- **Review focus:** release notes (mandatory user review — contract releases are a program review
  point).
- **Verification:** tag exists; bundle artifact downloadable; consumers pin it.
- **Evidence:** the release.
- **Integration impact:** opens program Waves 2+ for all consumers.
- **Stop condition:** milestone I1 green on v0.1.0.
- **Status:** done 2026-07-10 — user review passed at the Wave-1 exit review (release
  approved, Apache-2.0 license, `$id` → `https://github.com/duy-tung/serving-contracts/schemas/…`);
  post-review validation green; tag `v0.1.0` cut. Evidence in `RELEASES.md` and
  `docs/implementation-notes.md`. I1 re-runs per consumer as each wires the kit.

## SC-T010 — v1.0.0 freeze

- **Goal / Repository:** freeze Contracts 1–3 shapes before milestone I6. serving-contracts.
- **Requirement:** breaking-change audit of everything accumulated during v0.x; migration notes
  for all accumulated changes; freeze Contract 1 (API), Contract 2 (metrics — via I1 fixtures),
  Contract 3 (benchmark data).
- **Dependencies:** operational experience from milestone I5.
- **Expected files:** tag `v1.0.0`, migration notes, audit record.
- **Complexity:** Small. **Critical path:** no. **Parallel-safe:** yes. **Required.**
- **Review focus:** breaking-change audit (mandatory user review).
- **Verification:** consumer kits green on v1.0.0; I1 re-run green across all four consumers.
- **Evidence:** the release + I1 re-run CI links.
- **Integration impact:** **prerequisite for milestone I6** (the capacity-feedback loop must run
  on frozen contracts).
- **Stop condition:** I1 re-run green.
