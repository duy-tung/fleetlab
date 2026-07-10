# fleetlab — Milestones

Dependency-ordered; no calendar durations. Each milestone gate requires the listed acceptance criteria with evidence (command output or committed artifacts), reviewed against this document. Program wave context (ordering only): FL-T001–T005 run in Wave 5; FL-T006–T009 in Wave 6 feeding I6. Program critical path through this repo: `FL-T002 → FL-T003 → FL-T004 → FL-T006 → FL-T009 → I6`. The program's stated risk concentration for this repo: **FL-T004 → I6 — the models must fit real data.**

| # | Milestone | Depends on | Acceptance criteria |
|---|---|---|---|
| M1 | Docs bootstrap | approved plan | All 15 `docs/` files + the `adr/` directory exist and are repo-specific (no boilerplate); reviewed by the user (mandatory review point for the docs-set plan). |
| M2 | Contract-conformant ingestion | M1; contracts bundle pinned; sample data from inferbench | Golden-file tests green; real inferbench files ingest cleanly; provenance-less profiles and fabricated defaults rejected with typed errors naming file/field/rule; consumer fixture validation wired into CI against the pinned bundle tag (I1 obligation). |
| M3 | Core models validated | M2 | Arrival/length/token-rate/Little's-law/KV-memory models unit-tested with known-answer limits; KV formula cross-checked against measured llama.cpp/vLLM engine memory where available, within stated error; model-validation note published with all assumptions provenance-flagged. |
| M4 | Fitted profiles + G8 holdout | M3; benchmark corpus (IB-T010 CPU; IB-T011 GPU if budget allowed) | Per-(hardware, model, engine-config) goodput/memory profiles fitted with error bars; **G8 gate: prediction of a holdout benchmark run (not used for fitting) within stated error bars, or the miss documented as a limitation — either outcome is publishable**; validation report reviewed (**mandatory human review point**). |
| M5 | Dynamics scenarios | M3 | Queue growth, cold start/warm-up, scaling delay, failover headroom, and failure-capacity scenarios pass known-answer-limit tests (e.g. λ<μ stable queue, λ>μ linear growth); all delay parameters sourced from measurements or explicitly flagged `assumed`; scenario outputs reviewed. |
| M6 | Autoscaling-signal report | M4, M5 | Six-signal comparison across the named workloads published with a recommendation and when-each-signal-fails analysis; seeded, reproducible runs (rerun reproduces the tables). |
| M7 | Placement + cost reports | M4 | Heterogeneous-placement report (measured hardware only; VRAM-fit and no-unmeasured-hardware invariants tested in code) and cost/capacity report with sensitivity analysis published; all prices dated and provenance-flagged. |
| M8 | Recommendation emitter + limitations report | M6, M7 | Contract-7 files schema-valid in CI; **inferops consumes a recommendation in a dry run** (evidence: dry-run log); simulation-limitations report published (mandatory honesty artifact); ready for I6. |

## Gate discipline

- **G8 (program gate, lands at M4 and is restated at M8):** fit quality is only ever reported against holdout runs; the holdout protocol is structural in the fitting API (see `testing.md`). A holdout miss is published with error analysis — prediction error is a result, not a failure.
- **Mandatory human review points:** the M1 docs-set plan; G8 evidence (M4 validation report and the M8 limitations report); every ADR; any OSS submission before posting.
- **Verification at each gate uses a fresh-context verifier** (subagent or reviewer) checking against the planning prompt's acceptance criteria — self-review alone is not acceptance evidence.
- **Milestone → task mapping:** M1 = FL-T001; M2 = FL-T002; M3 = FL-T003; M4 = FL-T004; M5 = FL-T005; M6 = FL-T006; M7 = FL-T007 + FL-T008; M8 = FL-T009. See `tasks.md`.
- **External dependencies to watch:** M2 needs a released serving-contracts bundle (SC-T007 profile schemas) and sample inferbench files; M4 needs the IB-T010 CPU corpus (GPU corpus optional); I6 additionally needs contracts v1.0.0 and IO-T009. If an upstream input is late, parallel-safe tasks (FL-T005 after M3; FL-T007/T008 after M4) proceed first and the wait is recorded in `implementation-notes.md`.
