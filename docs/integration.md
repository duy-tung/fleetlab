# fleetlab — Integration

fleetlab participates in two program integration milestones: **I1** (contract compatibility, as one of four consumers) and **I6** (capacity feedback — the program's central story and fleetlab's headline milestone). All integration is files-and-contracts only; see `interfaces.md` for the shapes and the forbidden edges.

## I1 — Contract compatibility (consumer-CI wiring)

**fleetlab's obligation:** `make contracts-verify` (or equivalent) green in CI against the pinned serving-contracts bundle tag.

What the CI job does (wired in FL-T002, milestone M2):

1. Validates the bundle's golden `examples/` fixtures through fleetlab ingestion — every accepted input type parses and validates.
2. Validates fleetlab's own emitted artifacts (Contract-7 recommendations, once the emitter exists) against `capacity-recommendation.schema.json` from the same bundle.
3. Covers unsupported-field rejection cases (unknown fields refused, not ignored).

**Acceptance (program-level):** all four consumers (infergate, inferbench, fleetlab, inferops) green against the same bundle version. Re-run on every contract release; **the v1.0.0 re-run is a prerequisite for I6** (v1.0.0 freezes Contract 1–3 shapes).

The pinned bundle version lives in `interfaces.md` and in every emitted artifact's run record. Contract ambiguities found during wiring are filed against serving-contracts, never patched locally.

## I6 — Capacity feedback (the central story)

**Owner:** inference-lab (loop), **fleetlab (recommendation)**.

### The loop

```text
inferbench results (files) ──► fleetlab recommend ──► Contract-7 recommendation (file)
        ▲                                                      │
        │                                                      ▼
  repeated benchmark ◄── inferops applies the change (replicas / engine config)
        │
        ▼
  predicted vs measured — compared and PUBLISHED, including where the prediction was wrong
```

### Prerequisites (pins recorded when the loop runs)

- I5 accepted (operational stack), FL-T009 (emitter + limitations report), IO-T009 (inferops autoscaling experiment), contracts v1.0.0 (SC-T010), benchmark corpus from IB-T010/T011 — plus a fleetlab release pin.

### fleetlab's acceptance criteria in I6

1. Given benchmark results, fleetlab produces a **schema-valid** capacity recommendation with **stated uncertainty** on every predicted number (goodput/latency/cost), an autoscaling signal + thresholds, and assumptions/sensitivity notes.
2. The recommendation is machine-consumable: inferops applies the recommended change from the file (dry-run consumption is already required earlier, at M8/FL-T009).
3. After the repeated benchmark, **predicted vs measured is compared and published — including where the prediction was wrong.** The comparison uses Contract 2 measurement-point definitions so the numbers are actually comparable.

### Indicative commands (future shape)

`fleetlab recommend --results ... --slo ... --cost ...` → inferops apply → `inferbench` re-run.

### Failure handling

- **Prediction badly off:** that is a *result*, not a failure — publish the error analysis and refine profiles (G8 discipline). The miss feeds `reports/simulation-limitations.md`.
- **Loop mechanics broken** (file doesn't validate, inferops can't consume it): fix Contract 7 plumbing; if the contract itself is ambiguous, file against serving-contracts.

### Scale fallback (pre-approved)

If the GPU budget is exhausted, the loop closes at **mock/llama.cpp scale** with a recorded deviation in `implementation-notes.md`. The loop may shrink; it must never vanish.

### Evidence

The loop report: recommendation file, applied manifests, before/after benchmark results, and the error analysis — archived by inference-lab as Scenario E evidence, with fleetlab's artifacts carrying their full run records (seed, digests, bundle version).
