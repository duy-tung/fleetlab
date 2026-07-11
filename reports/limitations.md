# Simulation limitations (FL-T009)

**The mandatory honesty artifact.** Simulation ≠ production. Every number
fleetlab has ever published carries a `basis` (measured / source-reported /
assumed) and, where predicted, a stated uncertainty. This report collects,
in one place, everything that is modeled, everything that is not, and every
PENDING/assumed item accumulated across FL-T001–T009 — the "known error
magnitudes from G8" this task requires, plus the full accumulated list, not
a curated subset.

## 1. Simulation ≠ production (the program-wide pledge, restated concretely)

fleetlab has never run against a real GPU, a real multi-tenant gateway, or
real production traffic. Every fitted profile, every dynamics scenario,
every signal comparison, every cost figure, every placement candidate, and
the one real capacity recommendation this task emits are downstream of one
of exactly two evidence sources:

1. A **CPU-only mock backend** (`mock-loopback-cpu-dev`, gateway-mediated
   loopback in a local-dev-container) — the only hardware bucket with more
   than one offered-rate data point anywhere in this program's evidence
   (`docs/notes/fitting-method.md` §1).
2. A **real CPU/llama.cpp deployment** serving Qwen2.5-1.5B-Instruct
   (`inference-lab/evidence/i3`) — real, but exactly one offered-rate point
   per scenario (insufficient to fit or holdout-validate a goodput/latency
   model at all).

No number in this repo describes GPU behavior, multi-tenant contention,
network-attached storage, real client geography, or any production
workload mixture. Every placement/cost artifact that touches a GPU
(`reports/placement.md`, `reports/cost-model.md`) explicitly borrows a
`source-reported`/`assumed` GPU profile for **mechanism demonstration
only**, never as a claim about real GPU behavior.

## 2. Single-hardware-bucket corpus

The GPU corpus never materialized (`docs/risks.md` FL-L2 — program GPU
budget ~$150–250 total, as of 2026-07). Consequences, concretely:

- FL-T007 (heterogeneous placement) reduced to the pre-decided fallback:
  one measured hardware bucket + one `serving-contracts` example GPU
  profile as a mechanism demonstration, structurally barred from being
  emitted as a recommendation (`PlacementVerdict.is_recommendation`,
  `reports/placement.md`).
- FL-T008 (cost model) prices the measured CPU/mock capacity/latency
  profile against a real A10G GPU's example rate card purely to exercise
  the cost-model mechanism — stated as a hardware/config mismatch in every
  artifact (`reports/cost-model.md`).
- This task's own real recommendation (`examples/recommendations/
  e2-admission-sane-v1-5x-scaleout.capacity-recommendation.json`) sizes a
  real, measured mock-backend engine-config for a real stress-test demand
  — but its cost predictions reuse the same borrowed GPU rate card, for the
  same reason (Contract 7 requires a populated cost field; this program has
  no real cloud billing for a local-dev-container).
- `hardware-profile.schema.json` structurally cannot represent the CPU-only
  hosts this program actually measured (`gpu.model`/`gpu.count_per_node`/
  `gpu.vram_gb` are required) — recorded as a contract-question deviation
  since FL-T002, never patched locally (`profiles/examples/README.md`,
  `docs/implementation-notes.md`). This resurfaced directly in FL-T007's
  placement mechanism: the measured hardware bucket's own memory capacity
  could not be evaluated at all (`MemoryCapacityUnknownError`, `reports/
  placement.md` §2).

## 3. G8 error magnitudes (the fitted profiles' real error bars)

| Config | Points | G8 outcome | Error |
|---|---|---|---|
| `gateway-mock-flags-v1-conncap2` (ib-t008 sweep, 6 points) | 6 | **WITHIN STATED ERROR** (capacity, both directions) | ±0.4–7.2%, ≈1.05x combined 1σ at the extrapolation points |
| `gateway-mock-flags-v1-conncap2` latency | 3 sub-capacity points | FITTED, interior within error | +10.0% interior; **−34.4% extrapolation** (documented functional-form miss: additive true latency vs multiplicative model) |
| `admission-sane-v1` (E2, queue cap 3) | 2 | **MISS, documented** | **−12.6% / +14.0%** (direction-dependent), **6.3–4.2x** the measurement-noise floor |
| `admission-sane-v1b` (E2b, queue cap 1) | 2 | **MISS, documented** | **−17.0% / +20.4%**, **8.6–6.1x** the measurement-noise floor |

Root cause for the two-point MISS configs (`docs/notes/fitting-method.md`
§4, `reports/holdout-validation.md` §3): a one-parameter capacity-clamp
model assumes fixed capacity independent of offered load; these configs'
own two single-point capacity estimates differ by exactly the reported
error, showing the real admission-controlled queue's capacity genuinely
depends on offered load itself — a model-specification limitation, not
sampling noise, and not fixable with a second parameter this corpus has no
holdout data left to validate.

**This task's real recommendation inherits the E2 MISS directly**: its
predicted-goodput lower bound (165.279 rps) is built by applying this exact
−12.6% figure to the fitted per-replica capacity, not a generic margin
(`fleetlab/emit/topology.py::goodput_uncertainty`,
`examples/recommendations/e2-admission-sane-v1-5x-scaleout.capacity-recommendation.json`).

## 4. p50-inversion approximation

The fitted queueing-blowup latency model (`e2e_p50 = l0 · C/(C−offered)`)
predicts the **p50** of end-to-end duration. Every SLO objective this
program's schema examples define is on **p95** (`slo.schema.json`
examples; `slo-chat-interactive.json`). FL-T008's cost report inverts the
p50 model against a p95 threshold to compute "goodput at SLO" — a stated
approximation, immaterial at a loose SLO threshold (10s vs a ~39ms
near-empty latency) but not validated at a tight one (`reports/
cost-model.md` §1, §3). This task's own recommendation avoids the same
trap differently: the `admission-sane-v1` engine-config has **no fitted
latency model at all** (PENDING, §5 below), so its latency prediction uses
a measured-data bracket instead of an inverted fitted model — a different
approximation, disclosed explicitly in `assumptions`
(`fleetlab/emit/build_recommendation.py`).

## 5. Unmeasured scale-lag and the linear-replica-scaling assumption

- **Scale-up/down lag is `assumed`, not measured** (FL-T005): a full-corpus
  grep for `scale up`/`scale-up`/`replica`/`cooldown`/`autoscal*` across
  every evidence directory found zero matches — every run in evidence is a
  single engine process, never a multi-replica fleet
  (`fleetlab/dynamics/scaling.py`, `docs/implementation-notes.md` A7).
- **The linear-replica-scaling assumption itself is untested.** This task's
  real recommendation (6 replicas) assumes fleet capacity scales exactly
  linearly with replica count (no cross-replica routing-imbalance penalty)
  — because no multi-replica benchmark exists anywhere in this program's
  evidence to fit or even bound an imbalance figure from (unlike the
  `serving-contracts` example recommendation, which assumes an explicit 3%
  penalty). This is the single largest unvalidated assumption the emitted
  recommendation rests on, and is exactly what its `re_measurement` plan is
  built to test.
- **No N-1 failover margin at the recommended topology.** Sized exactly to
  the 189.0362 rps demand, this recommendation's own 6-replica fleet has a
  23.24 rps deficit if any one replica fails
  (`examples/recommendations/e2-admission-sane-v1-5x-scaleout.capacity-recommendation.json`
  `sensitivity_notes`) — disclosed, not hidden, since the task instructed
  sizing to the stated demand specifically.

## 6. Everything else accumulated as PENDING or `assumed` (full list)

| Item | Status | Where |
|---|---|---|
| KV-memory-per-token formula cross-check against a *measured* engine memory metric | **PENDING** — no isolated KV-cache-memory measurement exists anywhere in evidence (checked `/metrics`, every server log, `/slots` poll data) | `docs/notes/model-validation.md` §5.2 |
| Fitted memory profile (goodput+memory profiles, FL-T004) | **PENDING**, unchanged since FL-T003 | `reports/holdout-validation.md` §2a/§3 |
| E2/E2b latency (fitted-model form) | **PENDING** — every real point sits at/above its own single-point capacity estimate, so the model has no training point where it's defined | `reports/holdout-validation.md` §3 |
| Qwen2.5-1.5B KV-cache dtype (fp16) | `assumed` (llama.cpp build default), not confirmed by a measured metric | `profiles/examples/model-qwen2.5-1.5b-instruct-gguf-q4km.json` |
| CPU-only hardware profile (no `hardware-profile.schema.json` instance) | Deviation, not fabricated | `profiles/examples/README.md` |
| `cpu_utilization` / `gpu_utilization` are the identical simulated proxy | Corpus has no separate CPU/GPU occupancy telemetry — no evidence here distinguishes real GPU utilization's failure modes from this proxy's | `reports/autoscaling-signals.md` §2 |
| `bursty-illustrative-severe` scenario | `basis: assumed` — a 1.6x amplification of the real `bursty` fixture, since the real corpus never breaches this system's fitted capacity | `reports/autoscaling-signals.md` |
| Autoscaling debounce/threshold parameters (k=3σ, 5s debounce, 0.7 clear fraction) | One reasonable, uniformly-applied choice, not swept | `reports/autoscaling-signals.md` §10 |
| This recommendation's own `queue_depth` autoscaling thresholds (>1 scale-out, <1 scale-in) | `assumed` — no queue-depth telemetry exists in evidence for `admission-sane-v1`; a disclosed operational judgment call, not fitted | `examples/recommendations/e2-admission-sane-v1-5x-scaleout.capacity-recommendation.json` `autoscaling.notes` |
| Cost-model hardware/config mismatch (CPU capacity priced with GPU rates) | Explicit "MODEL DEMONSTRATION" label throughout | `reports/cost-model.md` |
| Spot GPU pricing (~40% of on-demand) | `assumed` planning figure, not a quoted price; preemption risk unpriced | `profiles/examples/cost-g5-xlarge-ondemand.json` |
| Placement demo GPU capacity figure (7.41 rps) | `assumed` — borrowed from a vendor illustrative fixture, not measured on any real A10G | `reports/placement.md` §3 |
| Placement cold-start-weighting demo | Borrows FL-T005's llama.cpp/Qwen cold-start measurement across engines as a standalone exhibit, not attributed to either ranked placement candidate | `reports/placement.md` §4 |
| `benchmark-result.schema.json`'s `throughput` block has no total (input+output) token-rate field | Schema-coverage gap — `per_million_tokens_usd`/total-token cost figures are not independently recomputable from any real result file; this task's cost prediction states its output-token-only basis explicitly | `reports/cost-model.md` §4; `examples/recommendations/e2-admission-sane-v1-5x-scaleout.capacity-recommendation.json` cost method strings |
| Tokens-per-request figures throughout (7.06–59.21 depending on config) | **measured**, but from a mock backend's synthetic generator or a tiny methodology-shakedown run — not representative of any real chat/RAG workload's token distribution | `reports/cost-model.md` §5; this recommendation's cost `method` strings |
| Contracts bundle pinned at v0.2.0 | **v1.0.0 (freezing Contract 1-3 shapes) is a stated prerequisite for I6** and has not been released yet — this repo's I1 obligation (`make contracts-verify`) is green against v0.2.0 only | `docs/interfaces.md` |
| **Inferops dry-run consumption** | **PENDING-on-RQ-14** — inferops' runtime environment decision is not made; this task's own stop condition cannot execute for real yet | §7 below, `docs/implementation-notes.md` |

## 7. The I6 loop's last mile: PENDING-on-RQ-14

FL-T009's stop condition ("recommendation consumed by inferops in a dry
run") **cannot run yet**: inferops' runtime environment decision (RQ-14) is
unresolved, so no inferops deployment exists to apply this recommendation's
topology change or to produce a real post-change `benchmark-result`. This
is an honest deferral, not a skipped step:

- The consumption-side validation script inferops will run once RQ-14
  resolves is written and tested **now**:
  `fleetlab/emit/dry_run_validate.py` (`tests/emit/test_dry_run_validate.py`,
  10 tests, exercised against a synthetic-but-clearly-labeled post-change
  fixture — never presented as real data). It checks: the applied replica
  count matches the recommendation, the re-measured goodput meets the
  recommendation's own stated lower bound, and the re-measured latency
  stays within its stated upper bound.
- The real recommendation this task emits names this script and its
  PENDING status explicitly in its own `notes` field, so a reader of the
  Contract-7 file itself — not just this report — sees the deferral.
- Recorded in `docs/implementation-notes.md` under FL-T009's log entry and
  its `Deviations` section.

## 8. What this report is not

This report does not claim fleetlab's models are wrong, or that the I6 loop
is broken. Per the program's own failure-handling rule (`docs/tasks.md`):
a prediction miss is a **result**, to be published with its error analysis,
not a failure to hide. Every limitation above is either (a) a genuine data
gap this program's evidence has not yet closed, with a stated closing
condition, or (b) a disclosed modeling approximation with a stated
direction and magnitude of its own error. Nothing here is silently
papered over, and nothing in `examples/recommendations/` or any other
fleetlab artifact contradicts the portfolio's I8 pledge: **"simulation ≠
production — fleetlab predictions carry stated uncertainty."**

## 9. Reproduction

```
pytest tests/ -q                                       # 301+ tests green
python3 -m fleetlab.emit.build_recommendation           # regenerates the real recommendation
python3 vendor/serving-contracts-v0.2.0/kit/contracts-validate.py \
    --bundle vendor/serving-contracts-v0.2.0 check examples/recommendations/
```
