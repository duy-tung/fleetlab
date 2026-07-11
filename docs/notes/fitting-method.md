# Fitting method note (FL-T004)

This note records the corpus this task actually had to work with, why the
fitting method (`fleetlab/fitting/`) takes the shape it does, and the one
discrepancy between the task brief and the measured evidence that surfaced
during implementation.

## 1. Corpus inventory (what exists, exactly)

The full real corpus available at FL-T004 time — `inferbench/docs/evidence/`
`ib-t010`, `ib-t004`, `ib-t005`, and `inference-lab/evidence/i3` — contains
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

**Exactly two engine-configs have two offered-rate points each** — the only
data in the entire corpus a holdout split can be built from:

| Engine-config (gateway `config_version`) | Points | Offered rates |
|---|---|---|
| `admission-sane-v1` (`ib-t010` E2, queue cap 3) | 2 | 37.8072 rps ("1x", capacity-boundary probe), 189.0362 rps ("5x", deliberate overload) |
| `admission-sane-v1b` (`ib-t010` E2b, queue cap 1) | 2 | same two rates (E2b reuses E2's workload files verbatim) |

Both engine-configs run the **mock backend**, not llama.cpp — per this
task's instruction, this is profiled honestly as a "hardware/config" for
**loop-mechanics purposes**, explicitly labeled as such everywhere it
appears (`profiles/fitted/*.json`'s `hardware.label`, this note, the
holdout-validation report). It is not a claim about any real GPU or CPU
inference hardware.

## 2. The "21.12 rps knee" claim — not found; documented, not silently reconciled

The task brief describes "a sweep with knee at 21.12 rps." A full-corpus
grep (literal `21.12`, `knee`, `saturation`) across all four evidence
directories found **no such figure anywhere**. What does exist:

- `ib-t010`'s two probe-estimated capacities: **37.807 rps** (`e2-probe`,
  queue cap 3) and **36.879 rps** (`e2b-probe`, queue cap 1) —
  `e2-capacity-estimate-rps.txt` / `e2b-capacity-estimate-rps.txt`, computed
  as `ok_count / elapsed_seconds` at a single offered rate (200 rps) far
  above any plausible capacity (ADR-0003's "open-loop overload probe"
  method — a verification sweep, explicitly not a knee-fit).
- `ib-t005-smoke-A` (21.175 rps) and `ib-t005-stream-SA` (21.262 rps) —
  coincidentally close to "21.12", but both are **achieved throughput of an
  underloaded mock-loopback run** (`goodput.ratio: 1.0`, no shedding), not a
  saturation point of any kind.

Per program rule 6 (`docs/interfaces.md`/`docs/architecture.md`: every claim
carries provenance; a claim without a manifest/log is not published), this
note records the 21.12 figure as **not corroborated by the evidence
inspected this session** and uses the actual measured capacity estimates
(~33–38 rps, corroborated by the fitted `capacity_rps` values below, which
land in the same 31–38 rps range) throughout. No file/number matching
"21.12 rps" as a genuine saturation knee was found; if one exists elsewhere
it was not located in the four directories this task specifies.

## 3. Why every model here is exactly one free parameter

`docs/testing.md` §4.5 requires "model complexity justified against
training-set size." With a maximum of two data points per fittable
engine-config, **any model with two or more free parameters fit from one
training point is either underdetermined or a tautology** (a 2-parameter
line through 1 point has infinitely many solutions; a 2-parameter line
through both points has zero residual and zero holdout left over — no
report is a "fit" if there is nothing held out to check it against).
`fleetlab/fitting/capacity.py` and `latency.py` each expose exactly one free
parameter (`capacity_rps`, `l0_seconds`), each solved in closed form from a
single training point (`C = achieved`; `L0 = latency * (C - offered) / C`) —
never via an iterative optimizer. `scipy` (an ADR-0001 candidate for this
task) was not added: the actual data made an optimizer unnecessary, and
adding an unused dependency would only grow the supply-chain surface for no
benefit (ADR-0002 records this explicitly).

## 4. Why the latency (queueing-blowup) model is PENDING, not fit with a lower bar

Every one of the four real points across the two fittable configs has
`achieved < offered` — i.e., by the capacity model's own logic, **every
point already sits at or above its own implied capacity**. The queueing
model `latency(offered) = L0 * C / (C - offered)` is only defined and only
identifiable from a point with `offered < C` (a genuinely underloaded
calibration point). No such point exists for `admission-sane-v1` or
`admission-sane-v1b` anywhere in the evidence. This mirrors FL-T003's
KV-memory PENDING precedent exactly: the model is implemented and tested
(`tests/fitting/test_latency.py` exercises both the identifiable branch, on
a synthetic point, and the real refusal), and the gap is recorded with its
precise data requirement — **one calibration run per engine-config at an
offered rate clearly (>=20%) below the fitted `capacity_rps`** (e.g. ~15–25
rps for either config) — rather than silently fit from an inapplicable
point or from a different, unreviewed functional form.

## 5. Error bars: Poisson-counting standard error, not bootstrap

Per-repetition raw events were not needed to derive an error bar: each
`benchmark-result.json`'s `throughput.total_requests` (a count over a fixed
measurement window) gives a closed-form Poisson-counting standard error,
`SE(achieved_rps) = achieved_rps / sqrt(total_requests)`
(`CorpusPoint.achieved_rate_stderr_rps`). This is a measurement-noise floor,
used in `reports/holdout-validation.md` to show that the holdout prediction
errors (12.6%–20.4%) are **6–9x the measurement-noise floor** — i.e. the
miss is a genuine model-specification limitation, not sampling noise.

## 6. Memory profile: still PENDING (unchanged from FL-T003)

FL-T004's brief carries forward FL-T003's finding: no isolated
KV-cache-memory measurement exists anywhere in the currently available
evidence (`docs/notes/model-validation.md` §5.2). Nothing found during
FL-T004 changes that. The memory-profile side of this task's "goodput and
memory profiles" requirement is recorded PENDING here, in
`reports/holdout-validation.md`, and in `docs/tasks.md` — not silently
dropped, not re-litigated with fabricated data.
