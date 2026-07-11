# Milestones — serving-contracts

Dependency-ordered; no calendar durations. Acceptance criteria are the review-gate checklist for
each milestone. At each gate, a fresh-context verification pass checks the work against the plan
before the milestone is claimed.

| # | Milestone | Depends on | Acceptance criteria |
|---|---|---|---|
| M1 | Docs + versioning/compatibility policy committed | plan approval | All 15 docs exist with content; `compatibility/compatibility-policy.md` states SemVer rules, breaking-change definition, deprecation rules, release process; **policy reviewed by the user** |
| M2 | Core contracts drafted (API + benchmark data) | M1 | `openapi/inference-api.yaml` lints; 4 benchmark schemas valid; fixtures cover stream, non-stream, every error class, and all 8 named workloads |
| M3 | Full schema set | M1 (parallel with M2 tail) | Capability schema (3 example descriptors), metrics vocabulary + cardinality policy, deployment schema, fault-scenario schema (12 encoded), 5 fleet schemas — all examples validate |
| M4 | Consumer compatibility kit | M2 | Kit runs green locally; documented usage shows all four consumer repos can wire it into CI without checking out this repo's source |
| M5 | **v0.1.0 release** → I1 | M2, M3 (Contracts 1–3 + capability + metrics), M4 | Tag exists with release notes + migration policy; all four consumers pin it and are green (**I1 accepted**) |
| M6 | Evolution stewardship through v0.x | M5 | Every change classified (MAJOR/MINOR/PATCH); ≤1 breaking change per program wave after v0.2 (R8 trigger); at least one deprecation or migration executed cleanly through the policy |
| M7 | **v1.0.0 freeze** | M6 + operational experience from milestone I5 | Breaking-change audit done; migration notes for accumulated changes; consumer kits green on v1.0.0; I1 re-run green — prerequisite for milestone I6 |

## Milestone-to-task mapping

- **M1:** SC-T001.
- **M2:** SC-T002 (Inference API), SC-T003 (benchmark data schemas) — parallel after SC-T001.
- **M3:** SC-T004 (capability), SC-T005 (metrics vocabulary), SC-T006 (deployment + faults),
  SC-T007 (fleet schemas) — parallel after SC-T001.
- **M4:** SC-T008 (compatibility kit) — after SC-T002 and SC-T003.
- **M5:** SC-T009 (v0.1.0 release; user review of release notes is mandatory).
- **M6:** ongoing stewardship — no single task; every post-v0.1.0 change is classified and logged
  in `docs/implementation-notes.md`.
- **M7:** SC-T010 (v1.0.0 freeze; breaking-change audit gets user review).

## Program milestones this repo gates

- **I1 — Contract compatibility (owned here):** all four consumers validate the golden fixtures
  and their own emitted artifacts against the same bundle tag in CI. Re-run trigger: **every
  contract release** (I1 is re-entrant). See `docs/integration.md`.
- **I2–I8 (indirect):** every integration milestone runs against pinned bundle versions; I7
  executes the 12 fault scenarios encoded in Contract 6; I6 requires the v1.0.0 freeze (M7).
