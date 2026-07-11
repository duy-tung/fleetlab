# Fitting method note (FL-T004)

This note records the corpus this task actually had to work with, why the
fitting method (`fleetlab/fitting/`) takes the shape it does, and the
corpus-scope discrepancy between the original task brief and the evidence —
including its same-day resolution (§2).

## 1. Corpus inventory (what exists, exactly)

**Corrected scope (same-day follow-up, 2026-07-11):** the corpus is
`inferbench/docs/evidence/{ib-t008, ib-t010, ib-t004, ib-t005}` and
`inference-lab/evidence/i3`. The original brief listed only the latter four
directories; `ib-t008` — which holds the program's one genuine multi-point
rate sweep — was missing from that list (an upstream brief-attribution
error, acknowledged by the orchestrator; the evidence itself was always
consistent). §1a covers the sweep; the rest of this section covers the
benchmark-result corpus of the original four directories.

### 1a. `ib-t008` — the six-point rate sweep (the richest fitting data)

`inferbench/docs/evidence/ib-t008/sweep/`: six offered rates at 10%–120% of
a probe-estimated capacity (27.79 rps), 3 repetitions each (150
requests/rep), all kit-valid raw events + run manifests (no aggregated
`benchmark-result.json` — points are computed from the raw events via
`load_corpus_point_from_events`, using the same FL-T002 ingest loaders).
Mock backend behind the gateway (`flags-v1`, dev@74f2372), with a
**disclosed client-side concurrency cap of 2** (`sweep.json`'s
`concurrency_cap_note`): the mock/gateway pair has no admission control of
its own at that build, so the cap models a capacity-limited target. The cap
is held fixed across the probe and every point and is carried into the
fitted profile's engine-config identity (`gateway-mock-flags-v1-conncap2`)
and its `concurrency_cap_disclosure` block — profiles fitted from this
sweep describe *that capacity-limited setup*, not general mock behavior.

Two measurement subtleties, both recorded in the corpus loader:

1. **Empirical vs declared offered rate.** The seeded schedule ran a
   uniform **7.46% faster** than every point's declared `rate_rps` (same
   seed at every point → same exponential draws, scaled per point — a
   schedule-realization artifact, not noise). Corpus points therefore use
   the empirical scheduled-send rate from the events themselves
   (`offered_rate_basis: "empirical-scheduled-send-rate"`), so the fit does
   not inherit the bias; the declared rate stays available via the workload
   files in provenance.
2. Achieved rate and e2e latency use the same conventions as the
   benchmark-result corpus (ok-count over the measured window; e2e on the
   `scheduled_send_ts` coordinated-omission-safe basis), pooled across
   repetitions per the program's pooled-percentile rule.

### 1b. The benchmark-result corpus (original four directories)

`ib-t010`, `ib-t004`, `ib-t005`, `inference-lab/evidence/i3` contain
**19 `benchmark-result.json` files** (9 in `ib-t010`, 7 in `ib-t005`, 3 in
`i3`; `ib-t004` itself holds only pre-Contract-3 calibration `stats.json`
files, explicitly superseded by the `ib-t005` re-processing per
`ib-t004/calibration.md`). Every one of them has `knee_estimate: null` and
every accompanying report states explicitly that no saturation/capacity
claim may be drawn without a rate sweep.

Grouped by (hardware, model, engine-config), almost every real
(hardware, model, engine-config) combination in this evidence has **exactly
one** offered-rate data point:

- `ib-t010` E1 arms (llama.cpp direct/gateway at 0.4 rps; mock direct/gateway
  at 6 rps): one point each.
- `i3` (`chat-short-cpu-direct`, `chat-short-cpu-gw`, `shared-prefix-cpu`,
  real llama.cpp on the real Qwen2.5-1.5B-Instruct GGUF, CPU): one point
  each, and all three reports self-label "methodology shakedown, not a
  performance claim" (`run_count=1`).
- `ib-t005` (`calib-A/B`, `slow-on/control`, `cancel-mid-stream`,
  `smoke-A`/`stream-SA`): one point each, all `run_count=1`.

In the original four directories, **exactly two engine-configs have two
offered-rate points each**:

| Engine-config (gateway `config_version`) | Points | Offered rates |
|---|---|---|
| `admission-sane-v1` (`ib-t010` E2, queue cap 3) | 2 | 37.8072 rps ("1x", capacity-boundary probe), 189.0362 rps ("5x", deliberate overload) |
| `admission-sane-v1b` (`ib-t010` E2b, queue cap 1) | 2 | same two rates (E2b reuses E2's workload files verbatim) |

All fittable engine-configs (both above, plus the §1a sweep config) run the
**mock backend**, not llama.cpp — per this task's instruction, this is
profiled honestly as a "hardware/config" for **loop-mechanics purposes**,
explicitly labeled as such everywhere it appears (`profiles/fitted/*.json`'s
`hardware.label`, this note, the holdout-validation report). It is not a
claim about any real GPU or CPU inference hardware.

## 2. The "21.12 rps knee" — initially not found; located same-day in `ib-t008`

The original task brief described "a sweep with knee at 21.12 rps" and
listed the corpus as `ib-t010`/`ib-t004`/`ib-t005`/`i3`. A full-text grep
(literal `21.12`, `knee`, `saturation`) across those four directories found
no such figure — every `knee_estimate` there is `null` — and the initial
FL-T004 pass recorded that as an uncorroborated claim rather than silently
substituting a different number (the conservative reading under program
rule 6: every claim carries provenance).

**Resolution (same day):** the orchestrator confirmed the discrepancy was an
upstream brief-attribution error — the sweep exists, in
`inferbench/docs/evidence/ib-t008/`, a path absent from the brief's corpus
list. `ib-t008/knee-result.json` records exactly the described knee:
`arrival_rate_rps: 21.122027534283404` (sweep point 3's declared rate),
`confidence: 0.8`, signal `ttft_seconds_p99` plateau-departure, `bracketed:
true`. Two provenance notes on that figure:

- 21.122 rps is the **declared** rate of the knee point; the events'
  empirical scheduled rate at that point is 22.698 rps (the uniform +7.46%
  schedule-realization offset, §1a). fleetlab's fitted values use the
  empirical basis.
- The knee is a **latency-departure** point (`ttft_p99` leaves its low-rate
  plateau), not the throughput plateau: fleetlab's fitted capacity for the
  same config (26.16–28.05 rps depending on fit direction) and the sweep's
  own probe estimate (27.79 rps) both sit *above* the knee, exactly as a
  throughput plateau should relative to a latency knee. The two numbers
  measure different things and are mutually consistent.

The original ib-t010-only findings in this note (probe capacities 37.807 /
36.879 rps for the E2/E2b configs; the two coincidental `ib-t005` ~21.2 rps
throughput figures being unrelated to any knee) remain correct as stated.

## 3. Why every model here is exactly one free parameter

`docs/testing.md` §4.5 requires "model complexity justified against
training-set size." For the two-point ib-t010 configs, **any model with two
or more free parameters fit from one training point is either
underdetermined or a tautology** (a 2-parameter line through 1 point has
infinitely many solutions; a 2-parameter line through both points has zero
residual and zero holdout left over — no report is a "fit" if there is
nothing held out to check it against). With the ib-t008 sweep (6 points, 4
in a training split) richer models become *fittable*, but the one-parameter
forms are retained deliberately for this pass: they are the forms whose
misfit the holdout results now precisely characterize (§4), and swapping in
a richer functional form belongs to a reviewed follow-up, not a silent
mid-task upgrade.

`fleetlab/fitting/capacity.py` and `latency.py` each expose exactly one
free parameter (`capacity_rps`, `l0_seconds`), each solved in closed form —
never via an iterative optimizer. When the sweep landed, `fit_capacity` was
upgraded from a single-estimate inverse-variance combination to an **exact
weighted least-squares** solve over all training points (the clamp model's
SSE is piecewise quadratic in `C`; enumerating segments and taking each
segment's weighted-mean optimum is still pure algebra — ADR-0002 addendum).
For a single clamped training point the two methods coincide exactly, so
the ib-t010 E2/E2b fitted profiles are byte-identical before and after the
upgrade (verified: regenerating produced no diff). `scipy` remains
unnecessary and excluded.

## 4. Latency (queueing-blowup) model: PENDING for E2/E2b; FITTED on the ib-t008 sweep, with a characterized misfit

For `admission-sane-v1`/`admission-sane-v1b` (ib-t010), every real point
has `achieved < offered` — every point already sits at or above its own
implied capacity, so `latency(offered) = L0 * C / (C - offered)` has no
training point where it is even defined. Still **PENDING** for those two
configs, with the same data requirement as before (one calibration run
clearly below capacity).

For the sweep config (`gateway-mock-flags-v1-conncap2`) the sub-capacity
points exist and the model is now **FITTED** — with its accuracy honestly
characterized by holdout (full numbers in `reports/holdout-validation.md`
§2b):

- **Interior interpolation** (holdout p2, 16.1 rps, between training
  points): predicted e2e p50 +10.0% vs actual — within the stated `l0`
  parameter error (~23%, from the spread of implied `l0` across training
  points).
- **Extrapolation to the lowest rate** (holdout p0, 3.0 rps): −34.4% —
  a real miss, documented, not clipped.
- **Root cause (functional form, not noise):** the implied `l0` falls
  monotonically across training points (55 ms at the lowest rate → 18 ms
  near the knee). The target's real latency is *additive* (a fixed base
  service time ≈60 ms plus queueing delay that grows with load), while the
  one-parameter model is *multiplicative* (`L0/(1-ρ)` shape forces latency
  → `l0` as load → 0, under-predicting the empty-system latency). A
  two-parameter additive form (`base + queue_term`) is the obvious
  candidate fix — deferred to a reviewed follow-up per §3, now that the
  sweep makes it validatable with holdout left over.

## 5. Error bars: Poisson-counting standard error, not bootstrap

Per-repetition raw events were not needed to derive an error bar: each
point's ok-request count over its measured window gives a closed-form
Poisson-counting standard error, `SE(achieved_rps) = achieved_rps /
sqrt(total_requests)` (`CorpusPoint.achieved_rate_stderr_rps`). This is a
measurement-noise floor, used in `reports/holdout-validation.md` to show:

- ib-t010 E2/E2b holdout errors (12.6%–20.4%) are **6–9x** the floor — a
  genuine model-specification limitation of the two-point corpus.
- ib-t008 sweep holdout errors (±6.7–7.2% at the extrapolation points) are
  **~1.05x the combined 1-sigma error** (fit stderr + measurement stderr in
  quadrature) — within stated error, the G8 within-bounds outcome.

## 6. Memory profile: still PENDING (unchanged from FL-T003)

FL-T004's brief carries forward FL-T003's finding: no isolated
KV-cache-memory measurement exists anywhere in the currently available
evidence (`docs/notes/model-validation.md` §5.2). Nothing found during
FL-T004 changes that. The memory-profile side of this task's "goodput and
memory profiles" requirement is recorded PENDING here, in
`reports/holdout-validation.md`, and in `docs/tasks.md` — not silently
dropped, not re-litigated with fabricated data.
