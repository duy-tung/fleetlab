# Architecture — serving-contracts

A spec repository's "architecture" is its artifact layout, its release mechanics, its validator
kit, and its normativity rules. There is no runtime, no state outside git, and no concurrency.

## Artifact layout

```text
openapi/inference-api.yaml                      # Contract 1 — OpenAI-compatible API subset
schemas/backend-capability.schema.json          # Contract 4
schemas/workload.schema.json                    # Contract 3
schemas/benchmark-run.schema.json               # Contract 3 (manifest)
schemas/raw-event.schema.json                   # Contract 3 (JSONL per-request records)
schemas/benchmark-result.schema.json            # Contract 3 (aggregates + validity block)
schemas/hardware-profile.schema.json            # fleet schema (provenance mandatory)
schemas/model-profile.schema.json               # fleet schema (provenance mandatory)
schemas/slo.schema.json                         # fleet schema (provenance mandatory)
schemas/cost-profile.schema.json                # fleet schema (provenance mandatory)
schemas/deployment-contract.schema.json         # Contract 5
schemas/fault-scenario.schema.json              # Contract 6 (12 scenarios as examples)
schemas/capacity-recommendation.schema.json     # Contract 7
metrics/metrics.md                              # Contract 2 — canonical metric + trace vocabulary
metrics/cardinality-policy.md                   # Contract 2 — label rules / PII guard
compatibility/compatibility-policy.md           # versioning, breaking changes, releases
examples/                                       # golden fixtures (positive AND negative)
docs/                                           # this documentation set
```

Schema and spec files are created by tasks SC-T002…SC-T007; as of SC-T001 only `docs/` and
`compatibility/` exist. The layout above is the approved design and changes to it are
contract-affecting (deviation policy applies).

## Bundle and release mechanics

- **One bundle, one version.** Every contract file is versioned together under a single SemVer
  version. There is no per-schema versioning (see ADR-0001).
- **Release = git tag + downloadable artifact.** A release is an annotated tag `vX.Y.Z` plus a
  downloadable archive of the contract files (OpenAPI, schemas, metrics docs, compatibility
  policy, examples). Tag content must equal committed content; the bundle artifact must be
  reproducible from the tag.
- **The release bundle is the only interface.** Consumers fetch a pinned release in CI; they never
  check out this repo's source in their build.
- **Release process** is defined normatively in `compatibility/compatibility-policy.md` and is a
  program review point (release notes get user review).

## Validator-kit design (SC-T008; constraints stated here)

One minimal validator kit (CLI or config) is the only code in this repo. Design constraints:

- Wraps **standard** schema validators (JSON Schema validator, OpenAPI linter) — no custom
  validation engine, no provider SDKs.
- **Validation-only.** The moment it grows request handling, code generation, or shared helpers
  for consumers, the ownership matrix is violated. That is a review-gate check, not a preference.
- Single-threaded, deterministic, no state. Target runtime: seconds inside consumer CI (the one
  performance hypothesis this repo records; measured once and dated in `docs/testing.md`).
- Consumers invoke it against a fetched pinned bundle: validate their own emitted artifacts
  against the schemas, and validate their accepted inputs against the golden fixtures.
- Must demonstrably **fail** on a broken fixture — a validator that cannot fail is not evidence.

## Fixtures

`examples/` holds the golden fixture set consumed by every consumer's CI:

- **Positive fixtures:** valid instances of every schema; API request/response/SSE examples
  covering stream, non-stream, and every error class; the 8 named workloads (non-normative
  examples — the canonical versioned workload suite is owned by `inferbench`); 3 capability
  descriptors (mock, llama.cpp, vLLM); 12 fault scenarios; end-to-end Scenario E fixtures.
- **Negative fixtures:** inputs that MUST be rejected — e.g. API requests carrying unsupported
  fields (one per unsupported field class), a deliberately incomplete benchmark-run manifest, a
  provenance-less fleet-schema instance, one fixture per error-taxonomy entry.

Fixture layout conventions are recorded in ADR-0004.

## Normativity rules

Every spec statement in this repo is either **normative** (MUST/MUST NOT, machine-checkable where
possible) or **explanatory** — never ambiguous prose in between.

Where a rule cannot be schema-encoded, it is encoded structurally **plus** stated as a normative
sentence in the schema `description`. Canonical examples:

- "Percentiles are computed on pooled raw data, never averaged across runs" → the
  `benchmark-result` schema requires pooled-percentile tables and carries the rule in its
  description.
- "Shed rate is always reported adjacent to goodput" → the result schema places the shed-rate
  field structurally next to goodput and requires both.
- "Results need a validity block" → the validity block is a required object, not a convention.

## Volatility discipline

Ecosystem facts embedded in contracts (engine metric names, OTel GenAI semconv status, upstream
layouts) are volatile. Every such fact carries an explicit "as of 2026-07 — re-verify at use time"
flag inside the spec text, and pins are mandatory where a version exists (e.g. the OTel GenAI
semconv pin in Contract 2). See `docs/observability.md` for the drift-check procedure.
