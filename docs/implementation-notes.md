# fleetlab — Implementation Notes

Running log of notable events: surprises, assumption changes, reduced scope, prediction misses, upstream waits. Deviations from the approved plan go under **Deviations** per the program deviation policy:

> When repository evidence forces a deviation from the approved plan, choose the conservative reversible option, record the evidence, decision, consequences, and follow-up under `Deviations`, and continue. Pause only when the deviation changes public contracts, repository ownership, security posture, or milestone scope.

## Log

### 2026-07-10 — FL-T001 docs bootstrap
- Created the full 15-file `docs/` set + `docs/adr/0001-stack-and-simulator-style.md` per the approved plan (planning prompt §5). Docs only; no implementation code yet.
- Repo state at start: empty repository (unborn `main`), no code, no CI.
- **Assumption (reversible):** `serving-contracts` has no released bundle tag as of 2026-07-10 (its repo has no commits yet), so no bundle version could be pinned. `docs/interfaces.md` records the pin as **NOT YET PINNED**; the pin is set at the start of FL-T002 (which depends on SC-T007 anyway) and recorded in `interfaces.md`, CI, and every emitted artifact. No architecture or contract shape was invented to compensate — all contract descriptions in the docs restate the program planning documents.
- **Assumption (reversible):** ADR-0001 (stack + simulator style) is drafted with a recommendation but marked **Proposed** — every ADR is a mandatory human review point; it is not treated as accepted until reviewed.
- Mandatory review point now open: user review of the docs set (charter/scope/non-goals in particular) before FL-T002 begins.

## Assumptions register

| # | Date | Assumption | Reversible? | Revisit when |
|---|---|---|---|---|
| A1 | 2026-07-10 | Contract bundle pin deferred to FL-T002 start (no serving-contracts release exists yet) | yes | first serving-contracts tag |
| A2 | 2026-07-10 | ADR-0001 recommendation (see file) pending human review | yes | FL-T001 review |

## Deviations

*(none recorded)*
