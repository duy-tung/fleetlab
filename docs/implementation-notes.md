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

### 2026-07-11 — FL-T002 ingestion + validation

- **Contract bundle pinned:** `serving-contracts` tag `v0.2.0` @ commit
  `484b449` (the tag exists now; `docs/interfaces.md` updated from "NOT YET
  PINNED"). Vendored read-only via `git archive 484b449 | tar -x` into
  `vendor/serving-contracts-v0.2.0/` — never fetched at runtime.
- **Validation mechanism decision (recorded per the task's "your call,
  record it"):** `fleetlab/ingest/*` validates directly against
  `jsonschema.Draft202012Validator` (already ADR-0001's pinned dependency)
  rather than shelling out to the bundle's own
  `kit/contracts-validate.py`. Reason: fleetlab's typed-refusal requirement
  (distinguish provenance-missing / unsupported-field / generic schema
  violations as Python exception types) needs programmatic access to
  `jsonschema`'s error objects that the kit's CLI (text/JSON summary +
  process exit code) does not expose. Both consume the identical vendored
  schema files, so there is no drift between what `make contracts-verify`
  (running the kit's `selftest` against the same vendored bundle) checks and
  what the library enforces. Full rationale in `fleetlab/ingest/bundle.py`.
- **Refusal classification heuristic:** a schema violation is classified
  `ProvenanceMissingError` when its JSON pointer passes through
  `provenance`/`basis`/`as_of`/`source`, OR when the failing sub-schema is
  structurally one of the three reusable provenance `$defs`
  (`provenance`, `provenancedNumber`, `provenancedInteger`) — this covers
  both "bare number where a `{value, provenance}` object was required" and
  "provenance object present but missing `basis`/`as_of`/`source`".
  `additionalProperties` violations are classified `UnsupportedFieldError`
  ahead of this check. Verified against every real `invalid/` fixture
  serving-contracts ships for the profile schemas
  (`hardware-missing-provenance.json`, `cost-reported-without-source.json`,
  `slo-declared-in-advance.json`) plus fleetlab's own synthetic
  unsupported-field fixtures.
- **42 golden-file tests green**, all four classes (valid / invalid /
  provenance-missing / unsupported-field) exercised for every input type
  named in `docs/testing.md` §1.
- **Real-file stop condition met:** the full available corpus —
  `inferbench/workloads/*` (8 canonical workloads), `inferbench/docs/
  evidence/{ib-t004,ib-t010}/**/manifest.json` + `inference-lab/evidence/
  i3/**/manifest.json` (48 manifests), the corresponding `events.jsonl`
  files (48 files, ~13,433 events), and `inferbench/docs/evidence/ib-t005/
  results/*` + `inference-lab/evidence/i3/raw/results/*` (10 benchmark
  results) — all ingest cleanly. Two files correctly **refuse**:
  `inference-lab/evidence/i3/aborted/{attempt-1,attempt-2}-.../events.jsonl`,
  both session-truncated JSONL from documented aborted sessions
  (`evidence/i3/notes.md`: "two aborted attempts...excluded from every
  acceptance number"). This refusal is the correct behavior (a truncated
  record must never be silently skipped) and is asserted explicitly as a
  passing test, not treated as noise.
- **Deviation — no hardware-profile example for the CPU-only measured
  host.** `hardware-profile.schema.json` requires a `gpu` block
  (`gpu.model`, `gpu.count_per_node >= 1`, `gpu.vram_gb`); it has no schema
  path to represent a CPU-only host without fabricating a placeholder GPU
  entry. fleetlab does not fabricate one. `profiles/examples/` therefore
  ships the GPU reference family (copied, attributed, from
  `serving-contracts examples/fleet/`) plus fleetlab-authored
  model/SLO profiles for the real CPU/llama.cpp/Qwen2.5-1.5B environment,
  but no `hardware-*.json` for that CPU host. Conservative/reversible per
  the deviation policy (§15): no public contract, ownership, or milestone
  scope changed. Filed here as a note for a future `serving-contracts`
  contract question, per `docs/interfaces.md`'s "never patched locally"
  rule — not raised as a live issue in this session.

### 2026-07-11 — FL-T003 core models

- `fleetlab/models/{arrival,length,token_rate,littles_law,kv_memory}.py`
  implemented; 61 tests green (`tests/models/`), including determinism
  tests (byte-identical output for the same seed; a static-analysis test
  that fails the suite if module-level/global RNG usage appears anywhere in
  `fleetlab.models`).
- **KV-memory cross-check against measured engine memory: recorded
  PENDING**, not fabricated. Full investigation in
  `docs/notes/model-validation.md` §5.2: checked llama.cpp's `/metrics`
  (11 series, none memory-related; `kv_cache_usage_ratio: null` in the real
  backend-capability descriptor), every captured server log (grepped
  case-insensitively for KV/MiB/GiB/buffer/graph — no memory figures at the
  captured verbosity), and `/slots` poll data (no memory field). The one
  memory figure in any available evidence (a tiny synthetic model's whole-
  process RSS, from the llama.cpp probe report) is for an unrelated model
  and is not KV-isolated; used only as an explicitly-labeled weak,
  non-tight sanity note, never as a passing cross-check. What would close
  this out: a llama.cpp build/run that logs its internal KV-buffer
  allocation at load time, an isolated before/after RSS delta varying only
  context size, or a vLLM run exposing `kv_cache_usage_ratio` (no vLLM run
  has produced data yet in this program).
- Formula known-answer validated exactly against an **independently
  authored** fixture: `serving-contracts examples/fleet/
  model-llama31-8b.json`'s documented `kv_cache_bytes_per_token: 131072`
  (computed there, in that repo, as "2 x 32 x 8 x 128 x 2") is reproduced
  exactly by `kv_cache_bytes_per_token(32, 8, 128, 2)`.
- Qwen2.5-1.5B-Instruct architecture parameters (layers=28, kv_heads=2,
  head_dim=128, context_length=32768) were **measured** directly from the
  real served GGUF checkpoint (`qwen2.5-1.5b-instruct-q4_k_m.gguf`, sha256
  `6a1a2eb6...`) via llama.cpp's own `gguf_dump.py`, this session — not
  looked up from a model card. `profiles/examples/
  model-qwen2.5-1.5b-instruct-gguf-q4km.json` records this provenance in
  full, including the explicit `assumed` (not `measured`) basis on the
  KV-cache-dtype-dependent final value, per the PENDING cross-check above.
- Little's law and the token-rate model both cross-check successfully
  against real data (Little's law: exact sample-path identity on two real
  raw-event traces; token-rate: `system_output_token_rate` reproduces a
  real benchmark-result's `output_tokens_per_second` to `rel=1e-6`) — see
  `docs/notes/model-validation.md` §3-4.
- No `scipy`/`pandas` dependency added: FL-T003's closed-form models needed
  only `numpy` (seeded RNG, sampling, percentiles). ADR-0001 already flags
  `scipy` as a FL-T004 (profile fitting) candidate, justified there when
  actually needed.

### 2026-07-11 — FL-T004 goodput profiles + G8 holdout

- **Corpus reality check first.** Swept the full evidence set named in the
  task (`inferbench/docs/evidence/{ib-t010,ib-t004,ib-t005}`,
  `inference-lab/evidence/i3`): 19 real `benchmark-result.json` files, every
  one with `knee_estimate: null`. Only **two** (hardware, model,
  engine-config) buckets have more than one offered-rate point — the mock
  backend under gateway configs `admission-sane-v1` (queue cap 3) and
  `admission-sane-v1b` (queue cap 1), each with exactly two points ("1x"
  ~37.8 rps, "5x" ~189.0 rps). Every other bucket (both llama.cpp arms in
  `ib-t010` E1, all three real llama.cpp runs in `i3`, all of `ib-t005`) has
  exactly one point — insufficient to fit or holdout-validate. Full
  inventory in `docs/notes/fitting-method.md` §1.
- **The task brief's "knee at 21.12 rps" was not found anywhere in the
  corpus** after a full-text grep (literal `21.12`, `knee`, `saturation`)
  across all four directories. The closest real numbers are the two
  probe-estimated capacities (37.807 rps / 36.879 rps,
  `e2-capacity-estimate-rps.txt` / `e2b-capacity-estimate-rps.txt`) and two
  coincidentally-similar-looking but unrelated achieved-throughput figures
  from unsaturated `ib-t005` runs (21.175 / 21.262 rps, `goodput.ratio:
  1.0`, no shedding — not a saturation point). Recorded as a discrepancy in
  `docs/notes/fitting-method.md` §2, not silently reconciled; the actual
  measured capacities (~31–38 rps) are used throughout instead.
- **Method: one free parameter, closed form, per `docs/adr/0002-fitting-
  method.md`.** `achieved_rps(offered) = min(offered, capacity_rps)` for
  throughput; a queueing-blowup model for latency, `l0 * C/(C-offered)`, is
  implemented but **PENDING** for both fittable configs — every real point
  in both already sits at/above its own single-point capacity estimate, so
  the model's parameter has no training point where it is even defined
  (`docs/notes/fitting-method.md` §4). No `scipy` added: with one parameter
  and one training point, fitting is an algebraic solve, not an
  optimization — a deviation from ADR-0001's speculative mention, made once
  the real (very sparse) data made the method clear.
- **G8 holdout result: MISS, documented as a limitation with full error
  analysis** (the stop condition's honest-miss branch, explicitly
  publishable per `docs/tasks.md`). Both configs, both directions:
  12.6%–20.4% relative prediction error, **4–9x the Poisson-counting
  measurement-noise floor** (`achieved_rps / sqrt(total_requests)`) — a
  genuine model-specification limitation (the true capacity is apparently
  offered-load-dependent in a way a 1-parameter clamp cannot capture), not
  sampling noise. Full numbers: `reports/holdout-validation.md`.
- **Holdout impossibility is structural**, not a convention:
  `fleetlab/fitting/holdout.py`'s `evaluate_holdout` raises
  `TrainingDataLeakageError` if asked to score a profile against any point
  that trained it, checked against the profile's own recorded training-run-
  ID set (not the caller's claim) — asserted directly by
  `tests/fitting/test_holdout.py::test_evaluate_holdout_on_a_training_point_raises`.
- **24 new tests green** (`tests/fitting/`), full suite 127/127 green.
  `profiles/fitted/*.json` (2 files) generated by
  `python3 -m fleetlab.fitting.build_profiles`, deterministic (no RNG).
- Memory profile: still PENDING, unchanged from FL-T003 (no isolated
  KV-cache measurement exists anywhere in the evidence; re-checked, nothing
  new surfaced this session).

### 2026-07-11 — FL-T005 dynamics: queue growth, cold start, scaling, headroom

- **Discrete-event core** (`fleetlab/dynamics/simulator.py`, ADR-0001's
  small in-repo FCFS `G/G/c` simulator) validated against five analytic
  limits: deterministic drain time (no RNG), M/M/1 mean-wait formula
  (λ<μ), λ>μ linear queue growth, M/M/c Erlang-C at low utilization, and
  burst decay back to baseline for a `bursty`-shaped provisioned scenario.
  32 tests green (`tests/dynamics/`), full suite 159/159.
- **Cold-start delay: measured, not assumed.** Extracted directly from
  `inference-lab/evidence/i3/logs/llama-server-*.log`'s own
  `load_model: loading model` / `llama_server: model loaded` timestamp
  pair, across all 8 real server-process logs in that evidence set: warm
  regime (OS page cache holds the weights) 1.94s mean of 6 runs; cold
  regime (page cache evicted) 91.34s mean of 2 runs — a ~47x gap,
  disk-read-bound, not engine/GPU variance. **The log's own elapsed-time
  format was undocumented** and had to be reverse-engineered this session:
  `MM.SS.mmm.uuu` (minutes uncapped rather than rolling to an hours field).
  Verified by an independent cross-check: the `chat-short-cpu-gw` run's
  real wall-clock span (its first and last `events.jsonl` timestamps, ~600-
  610s) against that same run's log's own final line (`10.09.254.080` =
  609.25s under this format) — matches. All 8 per-log deltas were then
  recomputed programmatically (not by eye) to confirm. Full derivation:
  `fleetlab/dynamics/cold_start.py`, `docs/notes/dynamics-method.md` §2.
- **Scale-up/down lag: no measured basis exists anywhere in the available
  evidence** — a full-corpus grep (`scale up`, `scale-up`, `replica`,
  `cooldown`, `autoscal*`) across `ib-t010`/`ib-t004`/`ib-t005`/`i3` found
  zero matches; every run in evidence is a single engine process, never a
  multi-replica fleet. `ASSUMED_SCALING_DELAY` (`fleetlab/dynamics/
  scaling.py`) is explicitly `basis="assumed"`: 10s assumed pod-scheduling
  constant + the measured warm-load time for scale-up (11.94s total); 30s
  assumed graceful-drain/termination-grace for scale-down. Flagged, not
  presented as measured; closes when inferops IO-T009 lands.
- **Failover headroom (N-1 failure capacity):** combined FL-T004's fitted
  mock-backend capacity (33.16 rps/replica) with 2 replicas against the real
  `bursty` workload's 20 rps peak — **no headroom deficit** (an honest
  negative result: the hypothesis that cold-start headroom dominates isn't
  automatically true; it depends on the actual capacity/peak-load ratio,
  favorable here). A second, explicitly `ASSUMED`/illustrative scenario
  (15 rps/replica, deliberately below the peak, clearly labeled as not a
  measured value) demonstrates the mechanism when it *does* bind: warm vs
  cold reload changes the cold-start window by 8.5x with steady-state
  capacity and offered load held completely fixed, and the resulting
  backlog/drain-time scale by the identical 8.5x — direct mechanistic
  support for planning-prompt hypothesis 3 ("required headroom is set by
  warm-up time x arrival growth rate, not steady-state throughput"). Full
  report: `reports/cold-start-headroom.md` (one of the five required
  reports); raw seeded outputs with input digests: `reports/scenarios/
  {bursty-queue-growth,cold-start-headroom}.json`.
- No `scipy`/`SimPy` added: the DES core needed only `numpy` (seeded
  exponential sampling) + Python's `heapq`, consistent with ADR-0001's
  "small owned discrete-event core, not a framework" decision.

### 2026-07-11 — FL-T004 follow-up: corrected corpus (ib-t008 sweep), re-fit, G8 improves

- **Corpus correction received:** the six-point rate sweep (knee at declared
  21.122 rps, confidence 0.8) lives in `inferbench/docs/evidence/ib-t008/`
  — missing from the original brief's corpus list (upstream attribution
  error, orchestrator-acknowledged). 6 offered rates at 10%–120% of the
  27.79 rps probe estimate, 3 reps x 150 requests each, kit-valid raw
  events + manifests (no aggregated benchmark-result files), mock backend
  behind gateway `flags-v1` (dev@74f2372) with a **disclosed client-side
  concurrency cap of 2** (sweep.json) — the cap is carried into the fitted
  profile's engine-config identity (`gateway-mock-flags-v1-conncap2`) and
  its `concurrency_cap_disclosure` block: it models a specific
  capacity-limited target, not general mock behavior.
- **New corpus path:** `load_corpus_point_from_events` builds points from
  raw events via the FL-T002 loaders. Offered rate is the **empirical
  scheduled-send rate** — the sweep's seeded schedule ran a uniform 7.46%
  faster than every point's declared rate_rps (same seed each point, scaled
  → same draws; verified identical ratio at all six points); fitting
  against declared rates would bake that bias into every parameter. Basis
  recorded per point (`offered_rate_basis`).
- **`fit_capacity` upgraded to exact weighted least squares** (still one
  parameter, still pure algebra, still no scipy — ADR-0002 addendum). For a
  single clamped training point it reduces to the old estimator exactly;
  the ib-t010 E2/E2b profiles regenerated **byte-identical** (verified via
  git diff), so nothing previously published changed.
- **G8 result on the sweep config — capacity WITHIN STATED ERROR, both
  directions:** train {p0,p1,p3,p4} → holdout p2 interior **+0.7%** / p5
  overload **−6.7%** (1.05x combined 1-sigma); reverse train {p1,p2,p3,p5}
  → holdout p0 **−0.4%** / p4 **+7.2%** (1.05x combined 1-sigma).
  Contrast: the two-point ib-t010 corpus still misses at 12.6–20.4%
  (4–9x noise floor) — unchanged, both outcomes published side by side.
- **Latency profile: FITTED for the sweep config** (the FL-T004 PENDING
  closes for it): `l0 = 38.7 ± 8.9 ms`. Interior interpolation +10.0%
  (within the stated l0 parameter error ~23%); extrapolation to the lowest
  rate −34.4% — a documented functional-form miss (implied l0 falls 55→18
  ms across training points: the target's latency is additive
  base-service + queueing delay, the model is multiplicative). The
  two-parameter additive form is deferred to a reviewed follow-up
  (ADR-0002 addendum item 3). Latency remains PENDING for E2/E2b (still no
  sub-capacity points there).
- `evaluate_holdout` now also scores latency predictions where the model is
  defined (below fitted C), records "no finite prediction" notes above C,
  and the leakage guard is unchanged (re-asserted on sweep data in
  `tests/fitting/test_sweep_holdout.py`).
- 9 new tests; full suite 168/168 green. Third fitted profile:
  `profiles/fitted/mock-loopback-cpu-dev__mock-8b__gateway-mock-flags-v1-conncap2.json`.

## Assumptions register

| # | Date | Assumption | Reversible? | Revisit when |
|---|---|---|---|---|
| A1 | 2026-07-10 | Contract bundle pin deferred to FL-T002 start (no serving-contracts release exists yet) | yes | first serving-contracts tag |
| A2 | 2026-07-10 | ADR-0001 recommendation (see file) pending human review | yes | FL-T001 review |
| A3 | 2026-07-11 | fleetlab validates directly against `jsonschema` rather than shelling out to the vendored `kit/contracts-validate.py`; the kit stays wired as the I1 CI mechanism | yes | if CI wiring reveals drift between the two paths |
| A4 | 2026-07-11 | KV-cache dtype for the Qwen2.5-1.5B profile is `assumed` (llama.cpp fp16 default), not measured — no run in evidence overrides `--cache-type-k/v` or logs the active KV dtype | yes | a run manifest/log that states the KV dtype explicitly, or a measured KV-memory metric |
| A5 | 2026-07-11 | Fitted capacity/latency profiles model the **mock backend** only (labeled honestly as loop-mechanics, not real hardware) — the only engine-configs in evidence with >1 offered-rate point are both mock-backend gateway configs | yes | a real multi-point rate sweep on llama.cpp or a GPU engine |
| A6 | 2026-07-11 | Published fitted profile per config trains on the "1x" baseline point and holds out the "5x" overload point (not the reverse) — the natural "does normal-load calibration predict a burst" direction; the reverse direction is computed and reported too, but not persisted as canonical | yes | if a 3rd data point ever justifies a different split policy |
| A7 | 2026-07-11 | Scale-up lag = assumed 10s Kubernetes pod-scheduling constant + measured warm model-load time; scale-down lag = assumed 30s graceful-drain/termination-grace constant — no measured basis for either assumed term exists in this program's evidence yet | yes | inferops IO-T009 real replica-scaling timing data |
| A8 | 2026-07-11 | `simulate_queue`'s `capacity` parameter bounds total in-system count (waiting + in service), not queue-only depth — a modeling simplification, documented in `fleetlab/dynamics/simulator.py`'s docstring rather than modeling real gateways' separate queue-depth-cap / concurrency-cap knobs | yes | if a scenario specifically needs the two caps to be independent |

## Deviations

- **2026-07-11 — no hardware-profile example for the CPU-only measured
  host.** Evidence: `hardware-profile.schema.json` requires `gpu.model`,
  `gpu.count_per_node >= 1`, `gpu.vram_gb` — structurally GPU-only; the
  CPU-only hosts actually measured in `ib-t010`/`i3` have no GPU to
  describe. Decision: do not fabricate a placeholder GPU entry (e.g.
  `model: "none"`); ship only the GPU reference family (attributed copies
  from `serving-contracts`) plus fleetlab-authored model/SLO profiles for
  the real CPU environment in `profiles/examples/`, and record the schema
  gap instead of a fake fixture. Consequences: `profiles/examples/` has no
  hardware profile paired with the Qwen2.5-1.5B model profile; FL-T004's
  fitting work (when it reaches CPU-measured data) will need either a
  schema change proposed to `serving-contracts` or a documented
  fitting-scope reduction. Conservative and reversible: no public contract,
  ownership, or milestone scope was changed by this session. Follow-up:
  raise a contract question with `serving-contracts` if/when FL-T004 needs
  a CPU hardware profile (per `docs/interfaces.md`: contract ambiguities
  are filed against `serving-contracts`, never patched locally).
- **2026-07-11 — KV-memory-per-token model cross-check against measured
  engine memory is recorded PENDING**, not fabricated as a pass. Evidence:
  no isolated KV-cache-memory measurement exists anywhere in the currently
  available evidence (checked llama.cpp's `/metrics`, every captured server
  log, and `/slots` poll data — see `docs/notes/model-validation.md` §5.2
  for the full account). Decision: ship the formula with full known-answer
  test coverage (including an exact match against an independently-authored
  real fixture) and record the measured-memory cross-check as an open item,
  per the task's explicit instruction to do so rather than fabricate.
  Consequences: FL-T003's stop condition ("cross-checks within stated error
  or honestly pending") is met via the "honestly pending" branch for this
  one cross-check; the other cross-checks in scope (Little's law,
  token-rate) passed exactly. Follow-up: closes when a measured,
  KV-isolated memory figure becomes available (see §5.2 for what that would
  take).
- **2026-07-11 — the task brief's "sweep with knee at 21.12 rps" does not
  match the evidence.** Evidence: a full-text grep (literal `21.12`, `knee`,
  `saturation`) across `ib-t010`/`ib-t004`/`ib-t005`/`inference-lab/evidence/
  i3` found no such figure; every real `knee_estimate` field in the corpus
  is `null`. Decision: used the actual measured probe-estimated capacities
  (37.807 / 36.879 rps) throughout instead of the brief's figure; recorded
  the discrepancy explicitly rather than silently substituting one number
  for another or fabricating a matching data point. Consequences: none to
  public contracts or scope — this only affects which real numbers appear
  in `reports/holdout-validation.md` and `profiles/fitted/*.json`, all of
  which are independently reproducible from the committed fixtures. No
  pause required (data-accuracy correction, not a scope/contract change).
  Full account: `docs/notes/fitting-method.md` §2.
  **RESOLVED same day (2026-07-11):** the orchestrator confirmed the
  discrepancy was an upstream brief-attribution error — the sweep exists at
  `inferbench/docs/evidence/ib-t008/` (a path absent from the brief's
  corpus list), with the knee at declared 21.122 rps in `knee-result.json`
  (confidence 0.8, ttft_p99 plateau-departure). The evidence itself was
  always consistent; the finding above (nothing in the four *listed*
  directories) remains accurate as stated. Follow-up work re-fit on the
  corrected corpus — see the "FL-T004 follow-up" log entry.
- **2026-07-11 — `scipy` not added despite ADR-0001 flagging it as a likely
  FL-T004 dependency.** Evidence: every fittable engine-config has at most
  two real data points, so every model in `fleetlab/fitting/` has exactly
  one free parameter, solved in closed form (`docs/adr/0002-fitting-
  method.md`) — there is no optimization problem for `scipy.optimize` to
  solve. Decision: keep the dependency set at `numpy`/`jsonschema`/`PyYAML`
  (unchanged since ADR-0001); do not add an unused ~35 MB dependency.
  Consequences: none — `docs/adr/0002-fitting-method.md` records this as
  the accepted decision, with a stated revisit trigger (a genuine
  multi-point rate sweep landing for any engine-config).
