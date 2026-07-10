# fleetlab — Risks and Kill Criteria

## Risk register

| ID | Owner | Likelihood / Impact | Risk | Trigger (observable) | Mitigation |
|---|---|---|---|---|---|
| **R9** | fleetlab | L:M, I:H | **fleetlab drifts into fantasy — models unmoored from measurements.** The defining risk of a simulation repo: plausible-looking numbers with no measured basis. | Holdout validation error exceeds stated bounds; profiles cover hardware never measured; a published number lacks a manifest reference. | **G8 holdout gate** (structural train/holdout split; fit quality never reported on training data); **provenance-mandatory profiles** (ingestion refuses provenance-less data and fabricated defaults); **the simulation-limitations report is a required artifact**, and prediction misses are published with error analysis. |
| R3 | shared (program) | — | Ecosystem drift: engine metric names change under a new pin (e.g. vLLM waiting/KV-usage gauge names vary by version; as of 2026-07, re-verify). | Mapping/conformance failures on new pins. | Capability-file metric-name mapping (Contract 4), never hardcoding; dated provenance on all ecosystem facts. |
| R12 | program | — | Overclaiming — numbers without provenance. | Any claim lacking a manifest/log to point at. | Evidence rules (every number is measured / source-reported / assumed + date); reproducibility audit at I8 removes unreproducible claims. |

Local secondary risks worth watching (not program-registered, tracked here):

| ID | Risk | Trigger | Handling |
|---|---|---|---|
| FL-L1 | Upstream input starvation: serving-contracts bundle (SC-T007) or inferbench corpus (IB-T010/T011) late, blocking FL-T002/FL-T004. | Dependency lacks a released artifact when the task is ready to start. | Proceed on parallel-safe work; record the wait in `implementation-notes.md`; never substitute invented sample data for measured corpus in fitted profiles (synthetic fixtures are fine for *golden tests*, clearly labeled, never for fitted profiles). |
| FL-L2 | GPU corpus never materializes (program GPU budget ~$150–250 total, as of 2026-07). | IB-T011 not run. | Pre-approved: fit and validate on the CPU (llama.cpp) corpus; I6 closes at mock/llama.cpp scale with a recorded deviation. The loop shrinks; it never vanishes. |
| FL-L3 | Comparison unfairness in FL-T006 (a favored signal gets more tuning effort). | Review finds asymmetric tuning or workload selection. | Same workloads, same SLOs, same tuning budget per signal; fairness is an explicit review-focus item. |

## Kill / reduction rules (pre-decided; never cut ad hoc under pressure)

These are the pre-approved fallbacks. Anything else that blocks the critical path is handled by the generic drop rule, with a deviation record.

1. **Program kill-order item:** KEDA/autoscaling breadth is cut before fleetlab work — the cut keeps **one HPA experiment (inferops) + the fleetlab simulation**.
2. **FL-T007 heterogeneous-placement depth is reducible to two hardware profiles** — recorded as a deviation in `implementation-notes.md`, never silently.
3. **Never-cut: the I6 feedback loop.** It may shrink to mock/llama.cpp scale if the GPU budget is gone, but it must close.
4. **Generic drop rule:** drop anything that (a) blocks the critical path without new evidence, (b) duplicates a capability owned elsewhere, (c) lacks a measurable artifact, or (d) creates tight source coupling (e.g. importing inferbench code — the fix for that urge is a contract clarification, never a code dependency).

## Standing guards

- Critical path through this repo: `FL-T002 → FL-T003 → FL-T004 → FL-T006 → FL-T009 → I6`; the program's stated risk concentration is **FL-T004 → I6: the models must fit real data**.
- Every review gate re-checks the forbidden edges (`interfaces.md`) and the non-goals list (`non-goals.md`).
- Volatile facts (GPU prices, engine metric names, upstream layouts) carry "as of <date> — re-verify at use time" flags; GPU pricing is the most volatile input this repo touches and every price is dated.
