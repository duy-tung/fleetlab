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

### EXP-001 (planned) — GPU utilization as an overload signal *(→ FL-T006)*
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

### EXP-004 (planned) — Cost sensitivity concentrates at the saturation knee *(→ FL-T008)*
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

*(no completed experiments yet — entries land here as EXP-001…EXP-006 execute, plus any new hypotheses that emerge, each added above with a written hypothesis before its first run)*
