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
- **Status (2026-07-11): DONE.** Contracts bundle pinned: `serving-contracts`
  tag `v0.2.0` @ commit `484b449` (git-archive-vendored, read-only, under
  `vendor/serving-contracts-v0.2.0/`; recorded in `docs/interfaces.md`).
  `fleetlab/ingest/*` validates directly against `jsonschema` (decision
  recorded in `fleetlab/ingest/bundle.py` docstring and
  `docs/implementation-notes.md`); the vendored `kit/contracts-validate.py`
  remains available for CI's `make contracts-verify`. 42 golden-file tests
  green (`tests/golden/`), covering valid / invalid / provenance-missing /
  unsupported-field for all eight input types. Real-file stop condition:
  the full `ib-t010`/`ib-t004`/`ib-t005`/`inference-lab evidence/i3` corpora
  (8 canonical workloads, 48 run manifests, 48 raw-event files ~13,433
  events, 10 benchmark results) ingest cleanly; the only two refusals are
  the two documented aborted-session truncated JSONL files under
  `evidence/i3/aborted/`, refused correctly (asserted explicitly in
  `tests/golden/test_real_inferbench_ingest.py`). One deviation recorded:
  `hardware-profile.schema.json` is GPU-centric and cannot represent the
  CPU-only hosts actually measured so far — see `profiles/examples/README.md`
  and `docs/implementation-notes.md`.

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
- **Status (2026-07-11): DONE, with one cross-check honestly PENDING.**
  `fleetlab/models/{arrival,length,token_rate,littles_law,kv_memory}.py`
  implemented; 61 model tests green (`tests/models/`). Cross-checks:
  Little's law holds exactly (sample-path identity) on two real raw-event
  traces; the token-rate model's `system_output_token_rate` reproduces a
  real benchmark-result's `output_tokens_per_second` to `rel=1e-6`; the
  KV-memory formula matches an independently-authored real fixture
  (`model-llama31-8b.json`, 131072 bytes/token) exactly. The KV-memory
  formula's cross-check against a *measured engine memory metric* for
  Qwen2.5-1.5B is recorded **PENDING** — no isolated KV-cache-memory
  measurement exists anywhere in the currently available evidence (see
  `docs/notes/model-validation.md` §5.2 for the full account of what was
  checked and what's missing). Architecture parameters (28 layers, 2 KV
  heads, 128 head_dim) were measured directly from the real GGUF checkpoint
  via `gguf_dump.py` this session.

  Stack note: FL-T003 needed only `numpy` (RNG, sampling, percentiles); no
  `scipy` dependency was added (ADR-0001 lists it as a FL-T004 candidate for
  profile fitting, not needed for this task's closed-form models).

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
- **Status (2026-07-11): DONE — G8 gate evaluated, outcome MISS documented
  as a limitation (publishable per the stop condition).**
  `fleetlab/fitting/{corpus,capacity,latency,holdout,build_profiles}.py`
  implemented; 24 tests green (`tests/fitting/`), full suite 127/127.
  Corpus reality: only two (hardware, model, engine-config) buckets in the
  entire available evidence have more than one offered-rate point (the
  mock backend under gateway configs `admission-sane-v1`/`admission-sane-
  v1b`, two points each, ~37.8/~189.0 rps) — every other bucket (both
  llama.cpp arms, all of `i3`, all of `ib-t005`) has exactly one point and
  is recorded insufficient, not fitted. The task brief's "knee at 21.12
  rps" was searched for exhaustively and not found in the corpus (recorded
  as a discrepancy, `docs/notes/fitting-method.md` §2); the actual measured
  probe-estimated capacities (~31–38 rps) are used throughout. Both
  fittable configs: one-free-parameter capacity-clamp model
  (`achieved_rps(offered)=min(offered,C)`), holdout-validated in both
  directions — **12.6%–20.4% relative prediction error, 4–9x the Poisson-
  counting measurement-noise floor** (a genuine model-specification
  limitation, not sampling noise; full numbers in `reports/holdout-
  validation.md`). Latency profile: **PENDING** for both configs — every
  real point already sits at/above its own single-point capacity estimate,
  so the queueing-blowup latency model has no training point where it is
  defined; the precise missing-data requirement is recorded, not forced.
  Memory profile: still **PENDING**, unchanged from FL-T003 (no isolated
  KV-cache measurement exists in the evidence). Holdout impossibility is
  structural: `evaluate_holdout` raises `TrainingDataLeakageError` against
  the profile's own recorded training-run-ID set regardless of caller
  claims, asserted by a dedicated test. No `scipy` added — one parameter,
  one training point is an algebraic solve, not an optimization
  (`docs/adr/0002-fitting-method.md`).
- **Status update (2026-07-11, same day — corrected corpus):** the "knee at
  21.12 rps" sweep exists at `inferbench/docs/evidence/ib-t008/` (missing
  from the original brief's corpus list; upstream attribution error,
  orchestrator-acknowledged). Re-fit on the corrected corpus: 6 offered-rate
  points for engine-config `gateway-mock-flags-v1-conncap2` (client-side
  concurrency cap 2, disclosed and carried into the profile identity).
  **G8 on this config: capacity WITHIN STATED ERROR both directions**
  (interior +0.7%/−0.4%; at/beyond-capacity extrapolation −6.7%/+7.2% ≈
  1.05x the combined 1-sigma error), and the **latency profile is now
  FITTED** (interior interpolation +10.0%, within the stated l0 parameter
  error; low-rate extrapolation −34.4%, a documented functional-form miss —
  additive target vs multiplicative model, reviewed two-parameter follow-up
  recorded in ADR-0002's addendum). The ib-t010 E2/E2b MISS (12.6–20.4%)
  stands unchanged alongside; E2/E2b latency still PENDING; memory profile
  still PENDING. `fit_capacity` upgraded to exact weighted least squares
  (E2/E2b profiles byte-identical before/after). 33 fitting tests, full
  suite 168/168 green. Evidence: `reports/holdout-validation.md` §2b,
  `profiles/fitted/mock-loopback-cpu-dev__mock-8b__gateway-mock-flags-v1-conncap2.json`.

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
- **Status (2026-07-11): DONE.** `fleetlab/dynamics/{simulator,cold_start,
  scaling,headroom,build_scenarios}.py` implemented; 32 tests green
  (`tests/dynamics/`), full suite 159/159. Discrete-event core (ADR-0001)
  validated against five independent analytic limits (deterministic drain
  time, M/M/1 mean-wait formula, λ>μ linear growth, M/M/c Erlang-C at low
  utilization, burst decay back to baseline) — see `docs/notes/dynamics-
  method.md` §1. Cold-start delay is **measured**: llama.cpp model-load
  timing extracted directly from `inference-lab/evidence/i3/logs/llama-
  server-*.log` (warm regime 1.94s mean of 6 runs; cold/page-cache-evicted
  regime 91.34s mean of 2 runs — the log's undocumented `MM.SS.mmm.uuu`
  timestamp format was reverse-engineered and independently cross-checked
  this session, `docs/notes/dynamics-method.md` §2). Scale-up/down lag is
  **assumed**, explicitly flagged (`basis="assumed"`) — a full-corpus search
  found zero scale-up/replica/autoscaling data anywhere in the available
  evidence; closes when inferops IO-T009 produces real data. Failover
  headroom / N-1 failure-capacity analysis (`fleetlab/dynamics/headroom.py`)
  combines FL-T004's fitted capacity with replica counts: the real measured
  (mock-backend) capacity shows **no headroom deficit** against the
  `bursty` workload's peak rate (an honest negative result); an explicitly-
  labeled illustrative/assumed lower capacity demonstrates the mechanism
  binding, showing an 8.5x warm-vs-cold reload difference in cold-start
  window produces the same 8.5x difference in accrued backlog and drain
  time — direct support for planning-prompt hypothesis 3. Full report:
  `reports/cold-start-headroom.md`; seeded scenario outputs with input
  digests: `reports/scenarios/{bursty-queue-growth,cold-start-headroom}.json`.

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
- **Status (2026-07-11): DONE.** `fleetlab/signals/{ground_truth,series,
  detection,build_signal_comparison}.py` implemented; 29 tests green
  (`tests/signals/`), full suite 215/215. Ground truth: the FL-T004 fitted
  profile whose G8 outcome is within stated error
  (`gateway-mock-flags-v1-conncap2`, capacity 26.157 rps, 2 concurrency
  slots) — `load_ground_truth_system` structurally refuses a MISS or
  latency-PENDING profile. Four seeded scenarios: `chat-short`, `mixed`
  (real workloads, steady load — zero flapping across all six signals in
  both), `bursty` (real IB-T003 fixture — burst peak 76.5% of capacity, no
  true overload), `bursty-illustrative-severe` (**basis: assumed** — the
  real cycle's own phases re-derived programmatically with only the burst
  rate amplified 1.6x to exceed capacity, since the real corpus has no
  scenario that breaches this system's fitted capacity). Findings: (1)
  applying the required uniform 3-sigma tuning rule to
  cpu/gpu-utilization produces an **unreachable threshold (>1.0)** in 3 of
  4 scenarios, because a 2-slot system's busy-fraction reading is
  discretized rather than continuous; (2) utilization's burst-phase
  reading already hits p95=max=1.0 at 76.5%-of-capacity load (zero true
  overload), while `predicted_goodput_deficit` correctly stays exactly
  zero throughout; (3) under genuine overload every signal detects every
  occurrence (0 misses), but `predicted_goodput_deficit` is
  systematically slower (12-13s vs the 5s debounce floor for the
  instantaneous signals) — an exactly-attributable cost of its windowed,
  capacity-anchored specificity. Recommendation: `predicted_goodput_deficit`
  primary (paired with `queue_depth`/`in_flight_requests` as a
  fitted-profile-independent fallback), utilization secondary/diagnostic
  only. Full report: `reports/autoscaling-signals.md`; design rationale:
  `docs/adr/0003-signal-comparison-design.md`; seeded scenario JSON:
  `reports/scenarios/autoscaling-signals.json`. **Filename deviation**:
  published as `reports/autoscaling-signals.md` (not this task's original
  `reports/autoscaling-signal-comparison.md`) per the dispatching session's
  explicit instruction — recorded in `docs/implementation-notes.md`.

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
- **Status (2026-07-11): DONE — reduced scope invoked per the pre-decided
  kill rule (`docs/risks.md` rule 2), recorded as a deviation, not cut
  silently.** `fleetlab/placement/{model,build_placement_report}.py`
  implemented (six mechanisms: memory fit, throughput/cost ranking,
  cold-start weighting, failover headroom, fragmentation, workload
  affinity — all pure/closed-form, no RNG); 36 tests green
  (`tests/placement/`), full suite 251/251. The measured evidence corpus
  covers exactly one hardware bucket (the CPU-only mock/llama.cpp loopback
  family); the mechanism ran over that bucket (measured,
  `mock-loopback-cpu-dev__mock-8b__gateway-mock-flags-v1-conncap2`, G8-
  within-error fitted capacity 26.157 ± 1.233 rps) plus one
  `serving-contracts` example GPU profile (`hardware-a10g-g5-xlarge`,
  `basis: source-reported` for VRAM/price, `basis: assumed` for its
  capacity figure, borrowed from a vendor illustrative fixture) as a
  **mechanism demonstration only** — enforced in code via
  `PlacementVerdict.is_recommendation` (computed from a candidate's own
  `basis`, not caller-asserted; a dedicated test proves it cannot be
  constructed to claim otherwise). Both sanity invariants from this task's
  own spec hold structurally: `memory_fit()` raises
  `MemoryCapacityUnknownError` rather than assuming a fit whenever memory
  capacity is unknown (the measured CPU bucket's own host RAM was never
  recorded anywhere in this program's evidence — an honest PENDING, not a
  fabricated pass); `PlacementVerdict` cannot claim `is_recommendation=True`
  for non-measured hardware. Headline finding: workload affinity
  (planning-prompt hypothesis 5) — the same hardware+model pairing's
  concurrency headroom collapses ~24x (174.5 → 7.3 concurrent requests)
  between a short-chat and a long-context workload, with throughput/cost
  ranking held completely fixed. Full report: `reports/placement.md`; raw
  output: `reports/scenarios/placement.json`.

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
- **Status (2026-07-11): DONE — MODEL DEMONSTRATION, explicitly labeled.**
  `fleetlab/cost/{model,build_cost_report}.py` implemented; 18 tests green
  (`tests/cost/`), full suite 215/215. `model.py` is parameterized and
  hardware-agnostic (no specific price or hardware baked in); the demo
  wiring combines the FL-T004 fitted, G8-within-error capacity/latency
  profile (a measured CPU-only mock backend) with
  `profiles/examples/cost-g5-xlarge-ondemand.json` (a real A10G GPU's
  example pricing) purely to demonstrate the mechanism — every artifact
  states this is a hardware/config mismatch, not a real cost claim.
  Tokens-per-request (59.21, 48.57 in + 10.63 out) is **measured** from the
  same ib-t008 sweep corpus the capacity profile was fitted from. Recompute
  check: every real benchmark-result in this repo's corpus carries
  `cost: null` (checked, all 10 result files); the one file with a
  populated cost block is a vendor illustrative example
  (`vendor/.../examples/benchmark/result.json`) — recomputed
  `per_million_output_tokens_usd` against it within -0.33%;
  `per_million_tokens_usd` (total-token basis) is not independently
  recomputable from that file (a schema-coverage gap: no total-token-rate
  field in `benchmark-result.schema.json`'s throughput block), recorded
  rather than backed into. Sensitivity (60-point deterministic sweep,
  price x SLO x load): a 4x price range produces exactly a 4x cost range;
  tightening the SLO toward the fitted `l0` produces a ~21x cost range —
  direct, quantified support for `docs/experiments.md` hypothesis 4 (cost
  is most sensitive to goodput near the saturation knee, not to raw
  price), asserted as a test invariant, not just read off a table. No new
  dependency added (pure closed-form arithmetic). Full report:
  `reports/cost-model.md`; seeded (parameterless — no RNG) output:
  `reports/scenarios/cost-model.json`. **Filename/path deviations**:
  published as `reports/cost-model.md` (not this task's original
  `reports/cost-capacity-model.md`), and `profiles/cost/` holds a
  pointer README rather than a duplicate cost-profile file (reuses
  `profiles/examples/cost-g5-xlarge-ondemand.json` in place) — both per
  the dispatching session's explicit instruction/decision, recorded in
  `docs/implementation-notes.md`.

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
- **Status (2026-07-11): DONE for everything within fleetlab's control;
  the inferops dry-run half of the stop condition is honestly
  PENDING-on-RQ-14 (recorded, not skipped).** `fleetlab/emit/{topology,
  recommendation,build_recommendation,dry_run_validate}.py` +
  `fleetlab/cli.py` (`fleetlab recommend --results ... --slo ... --cost
  ...`, registered via `pyproject.toml` `[project.scripts]`) implemented;
  50 tests green (`tests/emit/`), full suite 301/301.
  **The real recommendation** (FL-T004's E2/E2b overload evidence — the
  single mock-backend replica saturates well below the "5x" 189.0362 rps
  offered-rate stress-test point): recommends **6 replicas** of
  `gateway-mock-admission-sane-v1` (fitted per-replica capacity 33.159 ±
  1.105 rps), predicted goodput 189.036 rps with uncertainty **[165.279,
  189.036]** — the lower bound applies this profile's own published **G8
  holdout relative error (−12.6%, `reports/holdout-validation.md` §2a)**,
  which dominates the fit's own 3.3%-relative stderr; autoscaling signal
  `inference_queue_depth` (gateway, Contract 2 canonical — FL-T006's
  `predicted_goodput_deficit` primary recommendation is fleetlab's own
  derived simulation signal, not a metric the gateway emits, so the
  Contract-2-vocabulary fallback is named instead, with FL-T006's own
  caveats carried into `autoscaling.notes`), thresholds `queue_depth > 1`
  (scale out, 60s) / `< 1` (scale in, 300s), `assumed`, disclosed. Honestly
  discloses **no N-1 failover margin** at this exact demand (a 23.24 rps
  deficit) and that **linear replica-scaling is itself untested** (no
  multi-replica benchmark exists anywhere in this program's evidence) — the
  `re_measurement` plan is built specifically to resolve both the
  scaling-model question and which of E2's two single-point capacity
  estimates (33.159 baseline-fit vs 37.925 overload-empirical) is closer to
  true multi-replica behavior. Emitted:
  `examples/recommendations/e2-admission-sane-v1-5x-scaleout.capacity-recommendation.json`.
  **Kit-validated**: `python3 vendor/serving-contracts-v0.2.0/kit/
  contracts-validate.py --bundle vendor/serving-contracts-v0.2.0 check
  examples/recommendations/` → `PASS ... [capacity-recommendation]`,
  `check: 1/1 artifact(s) valid`. Limitations report (the mandatory honesty
  artifact): `reports/limitations.md`. **Deviation**: the inferops dry-run
  stop-condition item cannot run — inferops' runtime environment decision
  (RQ-14) is unresolved — so the consumption-side validation script
  (`fleetlab/emit/dry_run_validate.py`, tested against a synthetic,
  clearly-labeled post-change fixture) is written and named in the
  recommendation's own top-level `notes` field (Contract 7's
  `re_measurement` block has no free-form notes property;
  `additionalProperties: false`), and the PENDING-on-RQ-14 status is
  recorded in `docs/implementation-notes.md`, not silently skipped.
