# Testing — serving-contracts

Everything here is GPU-free by construction. Test evidence rule: no "validates/lints/green"
claim without command output or an artifact to point at.

## What gets tested

1. **Schema lint / meta-validation.** Every `schemas/*.schema.json` is validated against the
   pinned JSON Schema draft (draft pinned in ADR-0002). `openapi/inference-api.yaml` passes an
   OpenAPI linter (OpenAPI version pinned in ADR-0003).
2. **Fixture validation — positive.** Every schema has at least one positive fixture under
   `examples/`; all positive fixtures validate against their schema on every commit.
3. **Fixture validation — negative.** Every schema has at least one negative fixture that MUST
   fail validation. Required negative coverage:
   - one negative API fixture per unsupported request-field class (rejection-not-ignore rule);
   - one fixture per error-taxonomy entry (all ten error classes);
   - a deliberately incomplete benchmark-run manifest (missing pins/flags/hardware/warm-up/hypothesis);
   - a provenance-less fleet-schema instance (hardware/model/SLO/cost);
   - a benchmark-result without its validity block.
4. **Kit self-test.** The validator kit (SC-T008) must demonstrably fail on a broken fixture —
   a validator that cannot fail is not evidence. The self-test runs both a green pass over all
   fixtures and a demonstrated-failure pass over the negative set, asserting the failure.
5. **Release check.** Tag content == committed content; the bundle artifact is reproducible from
   the tag (byte-comparable archive built twice from the same tag).

## CI matrix

| Job | Scope | Trigger |
|---|---|---|
| `schema-lint` | JSON Schema meta-validation of all schemas | every commit |
| `openapi-lint` | lint `openapi/inference-api.yaml` | every commit |
| `fixtures-positive` | validate all positive fixtures against schemas/spec | every commit |
| `fixtures-negative` | assert all negative fixtures FAIL validation | every commit |
| `kit-selftest` | kit green run + demonstrated-failure run | every commit (once kit exists) |
| `release-check` | tag == commit content; bundle reproducibility | on tag |

No job requires a GPU, a network service, or any consumer repo. Consumer-side compatibility runs
(the I1 mechanism) execute in each consumer's CI against the pinned bundle, not here.

## Rejection coverage rule

Contract 1's central promise is "unsupported fields are rejected with a typed error, never
silently ignored". CI enforces the promise's testability: one negative fixture per unsupported
API field class and one per error-taxonomy entry. Adding a field to the supported subset without
adjusting the negative set is a CI failure.

## Performance hypothesis (the only one)

The validator kit adds negligible time to consumer CI (target: seconds). To be measured once
when the kit exists (SC-T008) and recorded here with the date and command output.

- Status: **measured 2026-07-10** (SC-T008). `time python3 kit/contracts-validate.py selftest`
  over the full bundle (5 schemas meta-validated, 32 positive + 20 negative fixtures) →
  `real 0m0.285s` on the development container (Python 3.11.15, jsonschema 4.26.0). Hypothesis
  confirmed: well under the seconds target; fetch + `pip install` will dominate consumer CI cost.

## Tooling constraints

Validation tooling uses standard schema validators only (JSON Schema validators, OpenAPI
linters). No provider SDKs, no generated frameworks, no shared helpers for consumers. Keep the
tooling single-threaded and deterministic; `go test -race` discipline is N/A here by design.
