# Compatibility Policy — serving-contracts bundle

**Status:** normative. This document governs how every contract in this repository is versioned,
changed, deprecated, released, and verified against consumers. Statements with MUST/MUST NOT are
binding; everything else is explanatory.

---

## 1. Contract inventory

The bundle comprises exactly the following contract surface. Every file listed is a public
contract once released; the docs under `docs/` and this policy's explanatory text are not
contracts, but this policy's normative rules are.

| # | Contract | Files | Consumers |
|---|---|---|---|
| 1 | Inference API (OpenAI-compatible subset) | `openapi/inference-api.yaml`, `examples/api/**` | infergate (implements), inferbench (drives), inferops (smoke tests), inference-lab (demos) |
| 2 | Metrics + trace vocabulary | `metrics/metrics.md`, `metrics/cardinality-policy.md` | infergate (emits), inferops (dashboards/alerts), inferbench (client-side mirrors), fleetlab (model inputs) |
| 3 | Benchmark data | `schemas/workload.schema.json`, `schemas/benchmark-run.schema.json`, `schemas/raw-event.schema.json`, `schemas/benchmark-result.schema.json`, `examples/workloads/**`, `examples/benchmark/**` | inferbench (emits), fleetlab (consumes), inference-lab (reports) |
| 4 | Backend capability | `schemas/backend-capability.schema.json`, `examples/capabilities/**` | infergate (declares+probes), inferbench (feature-gates), fleetlab (constraints), inferops (probe config) |
| 5 | Deployment | `schemas/deployment-contract.schema.json`, `examples/deployment/**` | infergate (publishes per release), inferops (consumes), inference-lab (pins) |
| 6 | Fault scenarios | `schemas/fault-scenario.schema.json`, `examples/faults/**` (12 scenarios) | inferops (injects), infergate (semantics tests), inferbench (client impact), inference-lab (postmortems) |
| 7 | Capacity recommendation | `schemas/capacity-recommendation.schema.json`, `examples/capacity/**` | fleetlab (emits), inferops (applies), inference-lab (Scenario E evidence) |
| — | Fleet schemas (Contract 3/7 inputs) | `schemas/hardware-profile.schema.json`, `schemas/model-profile.schema.json`, `schemas/slo.schema.json`, `schemas/cost-profile.schema.json`, `examples/fleet/**` | fleetlab primarily; inference-lab evidence |
| — | This policy | `compatibility/compatibility-policy.md` | all |

Deliberate exclusion: infergate's admin API (`/admin/v1/...`) is repo-private to infergate and
MUST NOT be added to this inventory unless a second real consumer appears (program assumption
A4). The same single-consumer test applies to any proposed new schema.

## 2. SemVer rules for the bundle

The entire contract set is versioned **together as one bundle** (ADR-0001). Releases are
annotated git tags `vMAJOR.MINOR.PATCH` with a downloadable artifact. A release's classification
is the most severe change it contains.

- **MAJOR** — any breaking change (per §3). Examples: removed or renamed field; semantics
  change of an existing field or rule; metric rename; histogram bucket-boundary change; error
  taxonomy entry removed or its retryability changed; a previously-optional field made required;
  a previously-accepted request field removed from the supported subset.
- **MINOR** — additive, backward-compatible change. Examples: new optional fields; new schemas;
  new examples/fixtures; new metric or new allowed label value (enumerable, low-cardinality);
  new error-taxonomy entry; deprecation markers (§4).
- **PATCH** — clarifications and fixture fixes that change no validation outcome and no
  measurement meaning. Examples: description text, typo fixes, corrected fixture that was wrong
  against an unchanged schema, doc-only changes.

Rules:

- Every change MUST be classified MAJOR/MINOR/PATCH at review time and the classification logged
  in `docs/implementation-notes.md`.
- If classification is uncertain, the change MUST be treated as the more severe class.
- Consumers pin the bundle by tag; there are no per-file versions.

## 3. Breaking-change definition

A change is **breaking** if it can:

1. make a **previously-valid consumer artifact invalid** — any request, response, emitted file,
   descriptor, or fixture that validated against bundle version N fails against N+1; **or**
2. **change the meaning of a previously-recorded measurement** — numbers recorded under version
   N can no longer be compared with numbers recorded under N+1 as if they measured the same
   thing.

Clause 2 is deliberate and equal in force to clause 1. Shape-compatible edits are still MAJOR if
they move meaning. Non-exhaustive examples of clause-2 breaks:

- changing a normative measurement point (e.g. TTFT from "first upstream body byte at the
  gateway" to anything else; ITL or queue-wait redefinition);
- changing histogram bucket boundaries (recorded distributions are no longer comparable);
- renaming a metric or label, or changing a label's allowed value set semantics;
- changing the goodput/SLO-attainment definition or the pooled-percentile rule in
  benchmark-result;
- changing what counts as billable tokens under cancellation;
- changing retryability of an existing error class (alters recorded retry/shed counts' meaning);
- changing the benchmark comparability rule (§7).

Anything matching either clause MUST ship as MAJOR (or under the pre-1.0 rule, §8, as MINOR with
an explicit migration note).

## 4. Deprecation rules

- Deprecated fields MUST carry `deprecated: true` plus a **removal version** in the schema (and
  the equivalent marker in OpenAPI/metrics docs).
- At least **one MINOR release** MUST separate deprecation from removal: a field deprecated in
  `X.Y.Z` may be removed no earlier than `X.(Y+2).0` (equivalently: never in the release that
  introduces the deprecation, and only after a MINOR in which it was visible as deprecated).
- During the deprecation window, consumer compatibility tests MUST stay green on both old and
  new fixtures: fixtures exercising the deprecated field remain in `examples/` until the removal
  release.
- Removal is a breaking change → MAJOR (or pre-1.0 MINOR + migration note, §8).
- **Migration notes are mandatory for every MAJOR release**: what changed, why, per-consumer
  impact, and mechanical upgrade steps. They ship in the release notes and are kept in the repo.

## 5. Release process

1. **Classify.** Aggregate the changes since the last tag; the release class is the most severe
   change included (§2). Verify the classification log in `docs/implementation-notes.md` is
   complete.
2. **Re-verify volatile pins.** Any "as of 2026-07 — re-verify at use time" fact touched by the
   release (engine metric names, OTel GenAI semconv pin) MUST be re-verified and re-dated.
3. **Validate.** Full CI green: schema meta-validation (pinned draft, ADR-0002), OpenAPI lint,
   all positive fixtures validate, all negative fixtures fail, kit self-test passes.
4. **Write release notes.** Contents: version + class; per-contract change list; migration note
   (mandatory for MAJOR and for any pre-1.0 breaking MINOR); deprecations introduced with their
   removal versions; the pre-1.0 rule statement while in v0.x.
5. **User review.** Contract releases are a program review point: release notes get user review
   before tagging. (The v1.0.0 breaking-change audit additionally gets user review, SC-T010.)
6. **Tag + artifact.** Annotated tag `vX.Y.Z`; build the downloadable bundle artifact from the
   tag. Release check: tag content == committed content; artifact reproducible from the tag.
7. **Re-run I1.** Milestone I1 re-runs on **every release** (§6). For MAJOR: migration note
   published, every consumer bumps its pin, and I1 MUST be green before any cross-repo scenario
   is re-claimed.
8. **Record.** Link the release and the I1 evidence in `docs/implementation-notes.md`; the
   supported-version matrix in `inference-lab` is updated by that repo.

## 6. Consumer compatibility tests (the I1 mechanism)

- `examples/` golden fixtures are consumed by every consumer repo's CI: each consumer validates
  **its own emitted artifacts against the bundle schemas** and **its accepted inputs against the
  fixtures** (including negative fixtures it must reject — e.g. unsupported API fields).
- Consumers fetch a **pinned release artifact**; they MUST NOT check out this repo's source in
  their builds, and this repo MUST NOT provide generated code or shared libraries to them.
- **Milestone I1** = all four consumers (infergate, inferbench, fleetlab, inferops) green
  against the **same** bundle tag, evidence linked in the inference-lab pins file. I1 is
  re-entrant and re-runs on every release.
- Failure handling: fixture mismatch → fix the consumer or file a contract defect; contract
  defect → PATCH release here, then re-run I1.
- Change propagation: MINOR → consumers upgrade at their own pace (old and new fixtures both
  green during any deprecation window). MAJOR → migration note + consumer version bumps + green
  I1 re-run before re-claiming cross-repo scenarios. Any inferbench schema-affecting change is
  blocked unless released here first — the schemas live here, not in inferbench.

## 7. Pinning and comparability

- Consumers pin the bundle by SemVer tag in CI config **and** in the inference-lab pins file.
  The supported-version matrix (which bundle versions each released component supports) is
  maintained in `inference-lab`.
- **Benchmark comparability rule (normative; printed in every benchmark report):** results are
  comparable only when model revision, quantization, tokenizer, engine version+flags, hardware,
  driver/CUDA, workload version+seed, and warm-up policy all match, **or** the difference is the
  single declared experimental variable.
- Ecosystem pins inside contracts (OTel GenAI semconv version — status "Development" as of
  2026-07, re-verify at use time; engine metric-name mappings) are mandatory and dated; drift
  handling per `docs/observability.md`.

## 8. Pre-1.0 rule

- During `v0.x`, a MINOR release MAY contain breaking changes **only with an explicit migration
  note** (documented honestly — never disguised as additive). PATCH must never break, at any
  version.
- Ceiling: no more than **one breaking change per program wave after v0.2** (risk R8 trigger —
  exceeding it forces a stewardship review).
- **`v1.0.0` freezes the shapes of Contracts 1–3** (API, metrics via I1 fixtures, benchmark
  data) and requires a breaking-change audit with migration notes for everything accumulated
  during v0.x, plus a green I1 re-run. v1.0.0 is a **prerequisite for milestone I6**: the
  capacity-feedback loop MUST NOT be claimed on a pre-1.0 bundle.
- After v1.0.0, full SemVer discipline applies with no pre-1.0 exception: any break to
  Contracts 1–3 is MAJOR with migration notes, consumer bumps, and an I1 re-run.
