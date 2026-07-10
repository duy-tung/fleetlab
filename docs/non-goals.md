# fleetlab — Non-Goals

This file is a first-class portfolio artifact, not filler. It is checked at every review gate. fleetlab does NOT own the following, and must never grow them. If work in this repo starts drifting toward any item below, stop and treat it as a scope deviation (see `implementation-notes.md` deviation policy).

## Never in this repository

1. **Provisioning.** fleetlab does not create, resize, or manage machines, clusters, or cloud resources.
2. **Kubernetes controllers.** No operators, no CRDs, no reconciliation loops. `inferops` owns everything Kubernetes.
3. **A global scheduler.** fleetlab *simulates* placement and scaling; it never schedules real workloads onto real hardware.
4. **Multi-region consensus.** No distributed coordination of any kind — fleetlab is a single-process offline tool.
5. **Live migration.** Not modeled as an owned capability, never implemented.
6. **Universal hardware abstraction.** No attempt at a general GPU/accelerator abstraction layer. Hardware exists in fleetlab only as measured profiles.
7. **Benchmark implementation or importing benchmark code.** `inferbench` is the program's only load-generation and benchmark-analysis system. fleetlab consumes its *files*, never its code. No shared statistics library: shared metric definitions live in the `serving-contracts` metric vocabulary.
8. **Load generation.** fleetlab never sends a request to anything. It has no network at runtime.
9. **Deployment.** fleetlab never deploys, applies manifests, or touches a cluster. Its recommendations are applied by `inferops`, as inferops's experiment.
10. **Any claim that simulation equals production.** The hard rule. Every artifact states uncertainty and limitations; prediction error is published, not hidden.

## Scope restrictions (owned, but deliberately bounded)

- **Placement reasoning is restricted to hardware actually covered by measured profiles.** No extrapolation to unmeasured GPUs — not with caveats, not with scaling heuristics. Unmeasured hardware is refused, and the refusal is enforced by a code invariant and a test (FL-T007), not by prose.
- **Autoscaling experiments (HPA, justified KEDA) belong to inferops; capacity logic stays here.** fleetlab recommends signals and thresholds; inferops runs the cluster experiment (IO-T009) and compares cluster behavior against fleetlab's predictions.
- **Engine internals are modeled from measurements, never implemented or controlled.** Continuous batching, per-token scheduling, KV-cache internals, prefix-cache internals, and GPU placement are engine-owned. fleetlab may fit their externally observable behavior from benchmark data; it contains no engine logic.
- **No brokers anywhere.** fleetlab is not on the synchronous inference request path at all, and must never be put there.

## Why this list exists

The portfolio's credibility rests on honest boundaries: one gateway, one load generator, one deployment stack, one simulator. The most likely failure mode for a simulation repo is scope creep toward "production-ish" behavior (a daemon that watches metrics, a controller that applies its own recommendations) — every item above exists to make that creep impossible to do silently. The companion risk, models drifting from measurements into fantasy, is risk **R9** in `risks.md`, guarded by the G8 holdout gate and provenance-mandatory profiles.
