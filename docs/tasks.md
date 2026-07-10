# fleetlab — Tasks

Stable IDs FL-T001…FL-T009 (use exactly these). Field key: **Goal/Repo · Requirement/Hypothesis · Deps/Expected files · Complexity · CP (critical path) · Par (parallel-safe) · Review focus · Verification · Evidence · Integration impact · Required/Stretch · Stop condition.**

Execution order: FL-T002 → FL-T003 → FL-T004 (G8 review) → {FL-T005, FL-T007, FL-T008 parallel-safe} → FL-T006 → FL-T009. Never start a task whose dependencies lack evidence.

---

## FL-T001 — Planning docs bootstrap
- **Goal/Repo:** create the full docs set (planning prompt §5) in fleetlab.
- **Requirement:** all 15 `docs/` files + the `adr/` directory, repo-specific, embedding the non-goals, the simulation-≠-production pledge, and the G8 holdout protocol.
- **Deps:** approved plan. **Expected files:** `docs/*`, `docs/adr/0001-stack-and-simulator-style.md`.
- **Complexity:** M. **CP:** no. **Par:** yes. **Required.**
- **Review focus:** scope/non-goals honesty; holdout protocol correctness; no boilerplate.
- **Verification:** checklist against the prompt's §5; user review of charter/scope/non-goals (mandatory review point).
- **Evidence:** committed docs.
- **Integration impact:** unblocks all fleetlab work; states the I6 role.
- **Stop condition:** 15+ docs exist and are reviewed.

## FL-T002 — Ingestion + validation
- **Goal/Repo:** load and validate all input file types in fleetlab.
- **Requirement:** ingest benchmark results, raw events, workload manifests, hardware/model/SLO/cost profiles; schema-conformant against the pinned contract bundle; **provenance required — refuse unproven data, no fabricated defaults**; typed, file-and-field-naming errors.
- **Deps:** SC-T007 (profile schemas released); sample data from inferbench. **Expected files:** `fleetlab/ingest/*`, `tests/golden/*` (valid + invalid fixtures incl. provenance-missing cases), `profiles/examples/*`.
- **Complexity:** M. **CP:** yes. **Par:** no. **Required.**
- **Review focus:** refusal paths (no silent coercion); provenance enforcement; contract-version pinning recorded in outputs.
- **Verification:** golden-file tests (pytest); contract-bundle fixture validation in CI.
- **Evidence:** green test run output; CI log validating against the pinned bundle tag.
- **Integration impact:** I6 entry; satisfies fleetlab's I1 consumer obligation.
- **Stop condition:** real inferbench files ingest cleanly.

## FL-T003 — Core models
- **Goal/Repo:** implement the analytic backbone in fleetlab.
- **Requirement:** arrival/length models parameterized from the workload schema; token-rate model; Little's-law relationships; KV-memory-per-token model (`2 × layers × kv_heads × head_dim × dtype_bytes × tokens`) validated against measured engine memory metrics. All model assumptions documented with provenance flags.
- **Deps:** FL-T002. **Expected files:** `fleetlab/models/*`, `tests/models/*`, `docs/notes/model-validation.md`, KV-memory worksheet + capacity-math worksheet (study track).
- **Complexity:** M. **CP:** yes. **Par:** no. **Required.**
- **Review focus:** model assumptions documented; derivations correct; measurement-point definitions (Contract 2) used exactly.
- **Verification:** unit tests with known-answer limits + cross-check vs measured llama.cpp/vLLM data where available.
- **Evidence:** model-validation note with cross-check numbers and error statements.
- **Integration impact:** everything downstream (fitting, dynamics, signals, placement, cost).
- **Stop condition:** cross-checks within stated error.

## FL-T004 — Goodput/memory profiles from measurements
- **Goal/Repo:** fit empirical profiles in fleetlab.
- **Requirement:** fit per-(hardware, model, engine-config) goodput and memory profiles from benchmark results; **holdout validation — predict a run not used for fitting**; overfitting guard; error bars on all fitted parameters.
- **Deps:** FL-T003; IB-T010 (CPU corpus) / IB-T011 (GPU corpus, if budget allowed) outputs. **Expected files:** `fleetlab/fitting/*`, `profiles/fitted/*` (provenance = the source run manifests), `reports/holdout-validation.md`.
- **Complexity:** M. **CP:** yes. **Par:** no. **Required.**
- **Review focus:** overfitting guard; error bars honest; train/holdout separation structural, not honor-system. **This is the G8 gate — mandatory human review.**
- **Verification:** holdout prediction within stated error (G8); seeded, reproducible fitting runs.
- **Evidence:** validation report (prediction vs holdout, error analysis).
- **Integration impact:** G8; the credibility basis for everything fleetlab publishes.
- **Stop condition:** stated error achieved **or documented as limitation** (prediction error is a result, not a failure).

## FL-T005 — Dynamics: queue growth, cold start, scaling delays, headroom
- **Goal/Repo:** simulate time-dependent behavior in fleetlab.
- **Requirement:** simulate queue growth under bursts; cold-start/warm-up delays; scale-up/down lag; failover headroom; failure-capacity analysis (capacity with N−1 replicas, degraded hardware).
- **Deps:** FL-T003. **Expected files:** `fleetlab/dynamics/*`, `tests/dynamics/*` (known-answer limits: λ<μ stable queue, λ>μ linear growth), `reports/scenarios/*`.
- **Complexity:** M. **CP:** no. **Par:** yes. **Required.**
- **Review focus:** delay parameters sourced (measured warm-up from inferops/inferbench artifacts, not invented); assumed parameters explicitly flagged.
- **Verification:** scenario tests with known-answer limits; seeded runs.
- **Evidence:** scenario outputs committed with seeds and input digests.
- **Integration impact:** feeds the autoscaling comparison (FL-T006) and cold-start-headroom report.
- **Stop condition:** scenarios reviewed.

## FL-T006 — Autoscaling signal comparison
- **Goal/Repo:** compare scaling signals in fleetlab simulation.
- **Requirement:** compare **CPU utilization, GPU utilization, queue depth, in-flight requests, token-arrival rate, predicted-goodput deficit** as scaling signals across the named workloads; report with recommendation + **when-each-signal-fails analysis**. Hypothesis to test (source-reported, as of 2026-07 — source research warns GPU utilization is NOT a reliable overload signal for LLM inference): does GPU utilization mislead the autoscaler in simulation, and under which workloads?
- **Deps:** FL-T004, FL-T005. **Expected files:** `fleetlab/signals/*`, `reports/autoscaling-signal-comparison.md`, seeded run configs.
- **Complexity:** M. **CP:** yes. **Par:** no. **Required.**
- **Review focus:** fairness of comparison (same workloads, same SLOs, same tuning effort per signal).
- **Verification:** reproducible simulation runs (seeded); rerun reproduces the tables.
- **Evidence:** autoscaling policy report (one of the five required reports).
- **Integration impact:** informs inferops IO-T009 (HPA experiment compares cluster behavior against these predictions); I6.
- **Stop condition:** report published.

## FL-T007 — Heterogeneous placement
- **Goal/Repo:** placement recommendations across GPU types in fleetlab.
- **Requirement:** model fit vs VRAM; throughput/cost differences; cold starts; failover headroom; fragmentation; workload affinity; placement recommendations — **restricted to hardware actually covered by measured profiles**.
- **Deps:** FL-T004. **Expected files:** `fleetlab/placement/*`, `tests/placement/*` (sanity invariants: never place a model that doesn't fit VRAM; never recommend unmeasured hardware), `reports/heterogeneous-placement.md`.
- **Complexity:** L. **CP:** no. **Par:** yes. **Required (depth reducible — see `risks.md`).**
- **Review focus:** honesty about profile coverage (only measured hardware); invariants enforced in code, not prose.
- **Verification:** seeded runs; sanity-invariant tests.
- **Evidence:** placement report (one of the five required reports).
- **Integration impact:** portfolio depth (capacity reasoning breadth).
- **Stop condition:** report published, or reduced-scope note (two hardware profiles) recorded as a deviation.

## FL-T008 — Cost model + sensitivity
- **Goal/Repo:** cost/capacity economics in fleetlab.
- **Requirement:** cost per 1M tokens at SLO per configuration; sensitivity analysis over price/load/SLO; all prices carry provenance and dates (volatile — re-verify at use time).
- **Deps:** FL-T004. **Expected files:** `fleetlab/cost/*`, `profiles/cost/*` (dated), `reports/cost-capacity-model.md`.
- **Complexity:** M. **CP:** no. **Par:** yes. **Required.**
- **Review focus:** provenance of prices (dated, source-flagged); sensitivity ranges honest.
- **Verification:** recompute vs the cost figures in inferbench benchmark reports (which reference the same cost profiles) — must agree.
- **Evidence:** cost report (one of the five required reports).
- **Integration impact:** I6 recommendation quality (cost is a recommendation field).
- **Stop condition:** report published.

## FL-T009 — Recommendation emitter + limitations report
- **Goal/Repo:** close the loop artifact in fleetlab.
- **Requirement:** emit capacity-recommendation files (Contract 7: input references, recommended topology with replica counts per hardware type + engine config, predicted goodput/latency/cost with stated uncertainty, autoscaling signal + thresholds, assumptions and sensitivity notes); publish the **"simulation limitations" report** stating explicitly that simulation ≠ production, what is modeled, what is not, and known error magnitudes from G8.
- **Deps:** FL-T006, FL-T008. **Expected files:** `fleetlab/emit/*`, `examples/recommendations/*.json`, `reports/simulation-limitations.md`, CLI entry (`fleetlab recommend --results ... --slo ... --cost ...`).
- **Complexity:** M. **CP:** yes. **Par:** no. **Required.**
- **Review focus:** uncertainty statements on every predicted number; limitations report is candid (mandatory honesty artifact, part of G8 review).
- **Verification:** schema-valid output against the pinned bundle in CI; **recommendation consumed by inferops in a dry run**.
- **Evidence:** recommendation file + limitations report + inferops dry-run log.
- **Integration impact:** I6 loop (the central story).
- **Stop condition:** inferops dry-run consumes it.
