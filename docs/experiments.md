# fleetlab — Simulation Experiment Log

Every fleetlab experiment follows the discipline: **written hypothesis → seeded run(s) → result**, including holdout predictions. Entries are append-only; a wrong prediction is a result, recorded and published, never deleted. Numbers appear only with provenance (measured / source-reported / assumed + date) and each run entry links its run record (seed, input digests, bundle version — see `observability.md`).

## Entry template

```markdown
### EXP-NNN — <short title>
- **Date / fleetlab commit:**
- **Hypothesis:** <falsifiable statement, with source + as-of date if source-reported>
- **Inputs:** <files + SHA-256 digests; workload versions; profiles used>
- **Seeds:** <seed(s); rerun command>
- **Method:** <model/scenario config; train/holdout split if fitting>
- **Result:** <numbers with error bars; hypothesis supported / refuted / partially>
- **Where the prediction was wrong:** <mandatory section; "nothing observed" must be earned>
- **Artifacts:** <paths to committed outputs/reports>
```

## Seeded hypotheses (program-provided; each becomes an experiment when its dependencies land)

### EXP-001 (executed 2026-07-11, see Log) — GPU utilization as an overload signal *(→ FL-T006)*
- **Hypothesis:** GPU utilization is not a reliable overload signal for LLM inference (source-reported, as of 2026-07 — re-verify at use time). Predicted-goodput deficit and queue depth detect overload earlier and with fewer false positives on `bursty` and `gen-long-out` than GPU utilization.
- **Method sketch:** six-signal comparison across the named workloads; same SLOs and tuning effort per signal; report where each signal fails, not only which wins.
- **Depends on:** FL-T004 (fitted profiles), FL-T005 (dynamics).

### EXP-002 (planned) — KV-memory formula vs measured engine memory *(→ FL-T003)*
- **Hypothesis:** the KV-memory-per-token model (`2 × layers × kv_heads × head_dim × dtype_bytes × tokens`) predicts measured engine memory within stated error for llama.cpp (CPU) and vLLM profiles; disagreement localizes to allocator/fragmentation effects the formula ignores.
- **Method sketch:** cross-check against measured engine memory metrics from benchmark manifests/capability mappings; document the residual explicitly.
- **Depends on:** FL-T002/FL-T003; measured memory data from the inferbench corpus.

### EXP-003 (planned) — Cold-start delays dominate headroom on bursts *(→ FL-T005)*
- **Hypothesis:** on `bursty` workloads, required headroom is set by warm-up time × arrival growth rate, not by steady-state throughput.
- **Method sketch:** dynamics scenarios sweeping warm-up delay (measured or `assumed`-flagged) against burst profiles; known-answer limits as sanity anchors.
- **Depends on:** FL-T005; sourced warm-up delays (inferops/inferbench artifacts).

### EXP-004 (executed 2026-07-11, see Log) — Cost sensitivity concentrates at the saturation knee *(→ FL-T008)*
- **Hypothesis:** cost per 1M tokens at SLO is most sensitive to goodput near the saturation knee, not to raw GPU price; sensitivity analysis quantifies this.
- **Method sketch:** sensitivity sweep over price/load/SLO per configuration; dated, provenance-flagged prices.
- **Depends on:** FL-T004, FL-T008.

### EXP-005 (planned) — Workload affinity changes optimal placement *(→ FL-T007)*
- **Hypothesis:** on heterogeneous fleets, workload affinity (long-context vs short-chat) changes optimal placement even when per-GPU cost/throughput ratios are equal.
- **Method sketch:** placement runs over ≥2 measured hardware profiles with affinity on/off; invariants (VRAM fit, measured-hardware-only) enforced throughout.
- **Depends on:** FL-T004, FL-T007.

### EXP-006 (planned) — G8 holdout prediction *(→ FL-T004; gate evidence)*
- **Hypothesis:** fitted per-(hardware, model, engine-config) goodput/memory profiles predict a benchmark run **not used for fitting** within the stated error bars.
- **Method sketch:** structural train/holdout split; publish `reports/holdout-validation.md` either way — within-bounds prediction, or the miss with error analysis. Mandatory human review.
- **Depends on:** FL-T004; IB-T010 corpus (IB-T011 if GPU budget allowed).

---

## Log

*(EXP-002, EXP-003, EXP-005, EXP-006 remain planned/pending their dependent tasks; EXP-001 and EXP-004 executed below)*

### EXP-001 — GPU utilization as an overload signal
- **Date / fleetlab commit:** 2026-07-11 / FL-T006.
- **Hypothesis:** GPU utilization is not a reliable overload signal for LLM inference (source-reported, as of 2026-07 — re-verify at use time). Predicted-goodput deficit and queue depth detect overload earlier and with fewer false positives than GPU utilization.
- **Inputs:** `profiles/fitted/mock-loopback-cpu-dev__mock-8b__gateway-mock-flags-v1-conncap2.json` (sha256 `8a160961...`); workloads `tests/golden/fixtures/real/workloads/{chat-short,bursty}.json` and `vendor/serving-contracts-v0.2.0/examples/workloads/mixed.json` (all sha256-embedded in `reports/scenarios/autoscaling-signals.json`).
- **Seeds:** `20260711` (single seed, fixed RNG draw order per scenario). Rerun: `python3 -m fleetlab.signals.build_signal_comparison`.
- **Method:** six-signal comparison (`fleetlab/signals/`) across `chat-short`, `mixed`, `bursty` (real IB-T003 fixture) plus one explicitly-labeled illustrative severe-overload variant (`bursty-illustrative-severe`, `basis: assumed`); one shared threshold-tuning/detection procedure applied identically to every signal (`docs/adr/0003-signal-comparison-design.md`).
- **Result:** **supported**, with two concrete mechanisms rather than a restated assumption: (1) the shared uniform tuning rule produces an *unreachable* threshold (>1.0, the signal's own physical maximum) for cpu/gpu-utilization in 3 of 4 scenarios, because a 2-concurrency-slot system's busy-fraction reading is discretized ({0, 0.5, 1.0}) rather than continuous; (2) at 76.5%-of-capacity load with **zero true overload** (the real `bursty` scenario), utilization's burst-phase reading already hits p95=max=1.0, while `predicted_goodput_deficit` correctly stays exactly 0 throughout. `gen-long-out` was not exercised (out of this pass's three-workload scope — a stated scope limit, not a claimed result).
- **Where the prediction was wrong:** under genuine (illustrative) overload, `predicted_goodput_deficit` is not the *fastest* signal — it detects every occurrence (0 misses) but with systematically longer lag (12-13 s vs. the 5 s debounce floor for instantaneous signals), an exactly-attributable cost of its 10 s trailing-window smoothing. The hypothesis names `queue_depth` alongside `predicted_goodput_deficit` as an early-and-specific detector; this pass finds `queue_depth` fast (5-9s) but not perfectly specific (one flap traced to post-burst drain-down bleeding into a labeled-quiet window — a labeling artifact, not baseline noise, but worth noting the hypothesis's "fewer false positives" claim for queue depth was not as clean as for the deficit signal).
- **Artifacts:** `reports/autoscaling-signals.md`, `reports/scenarios/autoscaling-signals.json`, `docs/adr/0003-signal-comparison-design.md`, `tests/signals/` (29 tests).

### EXP-004 — Cost sensitivity concentrates at the saturation knee
- **Date / fleetlab commit:** 2026-07-11 / FL-T008.
- **Hypothesis:** cost per 1M tokens at SLO is most sensitive to goodput near the saturation knee, not to raw GPU price; sensitivity analysis quantifies this.
- **Inputs:** same fitted profile as EXP-001; `profiles/examples/cost-g5-xlarge-ondemand.json` (sha256 embedded in `reports/scenarios/cost-model.json`); `profiles/examples/slo-chat-interactive.json`; measured tokens-per-request from `tests/fitting/fixtures/real/ib-t008/sweep/*/rep-*/events.jsonl` (2,700 real `ok` events).
- **Seeds:** none — pure closed-form arithmetic (`fleetlab/cost/model.py`), deterministic by construction. Rerun: `python3 -m fleetlab.cost.build_cost_report`.
- **Method:** 60-point deterministic sweep over price multiplier (0.5x-2.0x), SLO latency threshold (10s down to just above the fitted `l0`), and load fraction of SLO-goodput (0.5/0.8/1.0).
- **Result:** **supported**. A 4x price range produces exactly a 4x cost-per-token range (linear, as expected). Tightening the SLO threshold from 10s (99.6% of capacity) to just above the fitted `l0` (4.8% of capacity) produces a **~21x** cost-per-token range — over 5x the full price-sensitivity band. Asserted as a test invariant (`tests/cost/test_build_cost_report.py::test_sensitivity_slo_tightening_dominates_price_range`), not just read off a table once.
- **Where the prediction was wrong:** nothing observed here — the hypothesis held cleanly in this simulation. The caveat is scope, not a miss: this is a MODEL DEMONSTRATION (a CPU-only mock backend's fitted capacity priced against a real GPU's example rate, a stated hardware/config mismatch — see `reports/cost-model.md`'s opening section) — the *shape* of the finding (SLO/load sensitivity dominating price sensitivity near a fitted queueing-blowup knee) is a property of the closed-form model itself and should generalize, but the specific 21x/4x magnitudes are specific to this system's fitted `l0`/`capacity_rps` and are not a claim about any real GPU deployment's numbers.
- **Artifacts:** `reports/cost-model.md`, `reports/scenarios/cost-model.json`, `tests/cost/` (18 tests).
