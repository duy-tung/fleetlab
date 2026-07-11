# ADR-0002 — Fitting method (FL-T004)

- **Status:** Proposed — pending G8 human review (see `reports/holdout-validation.md`; this is the mandatory human-review gate, not yet exercised by a human reviewer as of this commit)
- **Date:** 2026-07-11
- **Deciders:** fleetlab implementer + user (G8 review)

## Context

ADR-0001 listed `scipy` as a likely FL-T004 dependency for "distribution
fitting, optimization for profile fitting" and asked this task to choose a
functional form, an overfitting guard, and an error-bar method once the real
corpus was in hand.

The real corpus (`docs/notes/fitting-method.md` §1) turned out to have, per
(hardware, model, engine-config), **at most two** offered-rate data points —
never a multi-point sweep, and only for two engine-configs (`admission-sane-
v1`, `admission-sane-v1b`, both on the mock backend). This is a much sparser
corpus than ADR-0001 anticipated, and it directly determines the method.

## Decision

**Functional form:** one free parameter per model, solved in closed form.

- Throughput/goodput: `achieved_rps(offered) = min(offered, capacity_rps)`
  — the standard saturation-clamp shape, `capacity_rps` solved exactly as
  `achieved_rps` of a training point whose `achieved < offered` (i.e. a
  point already showing observed clamping).
- Latency: `latency(offered) = l0_seconds * capacity_rps / (capacity_rps -
  offered)` — the standard `M/M/1`-flavored queueing-blowup shape, `l0`
  solved exactly from a training point with `offered < capacity_rps`.
  **Not fit for the two real configs** — no training point in the corpus
  has `offered < capacity_rps` (`docs/notes/fitting-method.md` §4);
  recorded PENDING, not forced.

**No `scipy`.** With one free parameter and one training point, the "fit" is
an exact algebraic solve (`C = achieved`; `L0 = latency * (C - offered) /
C`) — there is nothing for an iterative optimizer to do. Adding `scipy` (a
~35 MB wheel, per this session's `pip download` check) for code paths that
would never call `scipy.optimize.curve_fit` etc. would only grow the
supply-chain surface (`docs/security.md`) for zero benefit. `numpy` remains
sufficient. This is a deviation from ADR-0001's *speculative* mention, made
once the real data made the actual method clear — not a rejection of
ADR-0001's stack table, which correctly flagged this as an open question at
the time.

**Overfitting guard: structural, not a review checklist item.** Every
fitting function in `fleetlab/fitting/` takes exactly the training points
passed to it; `fleetlab/fitting/holdout.py`'s `HoldoutSplit` enforces a
non-empty, disjoint train/holdout partition, and `FittedGoodputProfile`
remembers which run IDs trained it so `evaluate_holdout` can refuse (raise
`TrainingDataLeakageError`) any attempt to score a profile against its own
training data — this is asserted directly by a test
(`tests/fitting/test_holdout.py::test_evaluate_holdout_on_a_training_point_raises`),
per `docs/testing.md` §4.2's "prove the impossibility" requirement.

**Error-bar method: closed-form Poisson-counting standard error.**
`achieved_rps = total_requests / window`; for a Poisson-distributed count
over a fixed window, `SE(rate) = rate / sqrt(total_requests)`. This needs
only the pooled `benchmark-result.json`'s own `total_requests` field — no
raw per-repetition event data, no bootstrap. It is used in
`reports/holdout-validation.md` as the measurement-noise floor the holdout
prediction errors are compared against (4–9x the floor — a genuine
model-specification limitation, not noise).

**Per-config isolation is structural.** `fit_profile` raises if the supplied
training points span more than one (hardware, model, engine-config) bucket
— fleetlab never pools across engine-configs to manufacture more "data",
even though doing so would make a richer model temptingly easier to fit.

## Consequences

- Positive: every number in `profiles/fitted/*.json` is either read
  verbatim from a real file or an exact algebraic solve from real training
  points — nothing is a black-box optimizer result a reviewer cannot
  re-derive by hand. Minimal dependency surface unchanged from ADR-0001
  (still just `numpy`, `jsonschema`, `PyYAML`, `pytest`).
- Negative / accepted costs: the fitted capacity profiles carry
  12.6%–20.4% documented holdout error (§`reports/holdout-validation.md`) —
  a real, non-trivial limitation, published rather than hidden. The latency
  side of FL-T004 is PENDING, not delivered, for both fittable configs.
- Revisit trigger: if a genuine multi-point rate sweep ever lands for any
  engine-config (3+ offered rates), a richer model becomes fittable with a
  real holdout set left over — that is the point to revisit this ADR and
  reconsider `scipy.optimize` for a nonlinear multi-parameter fit.

## Addendum (2026-07-11, same day): the ib-t008 sweep corpus and the weighted-LSQ upgrade

Shortly after this ADR was written, the corpus scope was corrected upstream:
the six-point rate sweep this repo's original brief alluded to ("knee at
21.12 rps") exists in `inferbench/docs/evidence/ib-t008/` — a path missing
from the brief's corpus list (orchestrator-acknowledged attribution error).
Three decisions follow, all consistent with this ADR's principles:

1. **`fit_capacity` upgraded from single-estimate inverse-variance
   combination to exact weighted least squares** over all training points.
   The clamp model's SSE is piecewise quadratic in `C` (breakpoints at the
   training offered rates; each segment's optimum is the weighted mean of
   the clamped points' achieved rates), so the global optimum is found by
   enumerating at most n segments — still pure algebra, still no `scipy`,
   still one free parameter. For a single clamped training point the two
   methods coincide exactly; the ib-t010 E2/E2b fitted profiles were
   regenerated and are **byte-identical** before and after the upgrade.
   Rationale for the change: with 4 training points, "average the achieved
   rates of every point showing any clamping" (the old combination) lets a
   barely-degraded near-knee point drag `C` far below the plateau; the LSQ
   fit correctly attributes near-knee points to the `offered <= C` branch.
2. **Raw-events corpus path** (`load_corpus_point_from_events`): the sweep
   ships kit-valid raw events + manifests but no aggregated
   `benchmark-result.json`; points are computed via the FL-T002 ingest
   loaders using the same conventions (ok-count over measured window;
   pooled percentiles on the `scheduled_send_ts` basis). Offered rate uses
   the **empirical scheduled-send rate**, not the declared `rate_rps` — the
   sweep's seeded schedule ran a uniform 7.46% fast (same seed every point),
   and fitting against the declared rate would bake that bias into every
   parameter. The basis is recorded on every corpus point
   (`offered_rate_basis`).
3. **One-parameter forms retained** even though 4+ training points could
   now support richer models. The holdout results characterize the
   one-parameter forms' misfit precisely (capacity within ~1.05x combined
   1-sigma; latency multiplicative-form limitation quantified at −34% low-
   rate extrapolation); moving to a two-parameter additive latency model is
   a *reviewed follow-up*, not a silent mid-task upgrade. That follow-up is
   this addendum's revisit trigger, now concretely reachable.

The sweep-fitted profile carries the sweep's disclosed client-transport
concurrency cap (2) in its engine-config identity and its
`concurrency_cap_disclosure` block — it models that specific
capacity-limited target, never general mock behavior.

## Planned follow-up

- ADR-0003 — signal-comparison design (FL-T006), unchanged from ADR-0001's
  forward pointer.
- Two-parameter additive latency form (`base_service + queue_term`) for the
  ib-t008 sweep config — now validatable with holdout left over (see
  Addendum item 3).
