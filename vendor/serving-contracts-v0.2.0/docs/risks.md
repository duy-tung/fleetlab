# Risks — serving-contracts

Program risks that land in this repo, with triggers and the mitigations this repo executes.
Likelihood/impact ratings are the program's (as of 2026-07).

## R8 — Contract churn destabilizing consumers (M/M)

- **Trigger:** more than 1 breaking change per program wave after v0.2.
- **Mitigation (ours to execute):** pre-1.0 rules honestly applied — during v0.x, MINOR may break
  **with an explicit migration note**; consumer compatibility kits catch breaks at I1; the
  v1.0.0 freeze (SC-T010) happens before milestone I6 so the capacity-feedback loop runs on
  frozen contracts. Every change is classified MAJOR/MINOR/PATCH and logged in
  `docs/implementation-notes.md`, so the trigger is measurable.

## R3 — Ecosystem drift: vLLM metric names, OTel GenAI semconv changes (H/M)

- **Trigger:** conformance or mapping tests fail on a new pin.
- **Mitigation:** pin everything (semconv version pin is mandatory in Contract 2); backend
  capability uses metric-name **mapping** instead of hardcoding engine metric names; every
  ecosystem fact in a spec carries a dated provenance flag ("as of 2026-07 — re-verify at use
  time"). Drift-check procedure is documented in `docs/observability.md`.

## R1 — Multi-repo overhead: release/pin churn eats building time (M/H)

- **Trigger:** pin/release bookkeeping dominates work, or lockstep changes across repos twice in
  a row.
- **Mitigation:** contract-first discipline. **If a change here forces same-day source changes in
  another repo twice in a row, that is a contract gap — fix the contract, not the boundary.**
  Keep the bundle small and the release process cheap (single tag, reproducible artifact).

## Pre-1.0 churn (repo-local expression of R8)

- **Trigger:** consumers repeatedly broken by v0.x MINOR releases without warning.
- **Mitigation:** the pre-1.0 rule is explicit and documented honestly in the compatibility
  policy: v0.x MINOR may break **only** with a migration note; I1 re-runs on every release make
  breakage visible immediately instead of at integration time; ≤1 breaking change per wave after
  v0.2 is the hard ceiling (R8 trigger).

## Speculative-surface guard (single-consumer contracts)

- **Trigger:** a schema exists here with only one real consumer.
- **Mitigation:** do not ship it. infergate's admin API is deliberately NOT a shared contract
  (program assumption A4); the same test applies to every new schema proposal at review time.
  Promotion requires a demonstrated second consumer, not an anticipated one.

## Guardrails that bound all risk responses

- **Never-cut list:** contract validation is on the program's never-cut list. Fixtures and the
  compatibility kit are not reducible, whatever the schedule pressure.
- **Consolidation trigger (user decision, never autonomous):** if this repo demonstrably lacks
  independent value at two consecutive wave exits, the pre-analyzed candidate is folding
  `serving-contracts` into `inference-lab`. Present evidence to the user; never decide alone.
- **Deviation policy:** almost every substantive file here IS a public contract, so the pause
  condition of the deviation policy applies more often than elsewhere — field/semantics changes
  pause for review; fixture additions, doc clarifications, and PATCH fixes proceed with a log
  entry (see `docs/implementation-notes.md`).
