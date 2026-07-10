# ADR-0001 — Python stack and simulator style

- **Status:** Accepted (user review passed at the Wave-1 exit review, 2026-07-10)
- **Date:** 2026-07-10
- **Deciders:** fleetlab implementer + user (review)

## Context

fleetlab is a Python CLI + library (deliberate Python-deepening goal): reads schema-conformant files, runs deterministic seeded analysis, writes files. No daemon, server, database, GPU, or runtime network. The program directs a *minimal* numeric/statistical stack, justified here, and requires a decision on simulator style for `fleetlab/dynamics/` (discrete-event vs analytic). Hard requirements shaping the choice:

- Determinism: same seed + same inputs ⇒ byte-identical result tables.
- Every model needs a documented derivation and known-answer tests — opaque frameworks work against that.
- CI is GPU-free and should stay fast; the dependency surface is a supply-chain surface (`security.md`).
- Dynamics must reproduce known-answer limits exactly (λ<μ stable, λ>μ linear growth) and handle bursts, cold-start/warm-up delays, scaling lag, and N−1 failure analysis.

## Decision

### Stack (minimal, pinned via lockfile)

| Dependency | Role | Justification |
|---|---|---|
| `numpy` | arrays, seeded RNG (`numpy.random.Generator` / `SeedSequence`) | the determinism backbone; explicit generator objects, no global state |
| `scipy` | distribution fitting, optimization for profile fitting (FL-T004) | avoids hand-rolling well-known statistics; `stats`/`optimize` only |
| `pandas` | tabular results, JSONL raw-event handling, report tables | raw events are naturally tabular; pooled-percentile work is table work |
| `jsonschema` | validating all inputs/outputs against the pinned contract bundle | contracts are JSON Schema; validation is the core of FL-T002 |
| `PyYAML` (safe_load only) | YAML profiles | profile files are YAML per program plan; safe_load is a security rule |
| `pytest` (dev) | test runner | program floor: green pytest suite |

**Deliberately excluded:** simulation frameworks (SimPy — see below), plotting libraries (defer until a report actually needs a figure; then decide in a follow-up note), ML libraries (fitting is classical statistics, not learning), any HTTP client (no network at runtime).

### Simulator style: analytic-first, with a small owned discrete-event core for dynamics

- **Steady-state models (`fleetlab/models/`, placement, cost): closed-form analytic.** Little's law, KV-memory arithmetic, goodput-at-SLO interpolation over fitted profiles. Closed form gives exact known-answer tests and derivations a reviewer can check by hand.
- **Time-dependent behavior (`fleetlab/dynamics/`): a small discrete-event simulation written in-repo** (an event heap over request arrival/dispatch/completion/scale events), driven exclusively by a passed `numpy` Generator. Queue growth under bursts, cold-start/warm-up delays, scale-up/down lag, and N−1 failover are inherently transient; pure analytic treatment of all of them (time-varying fluid approximations) would be harder to explain and to test than a few hundred lines of event loop.
- **Not SimPy:** the event core fleetlab needs is small; owning it keeps determinism rules (seed flow, ordering ties broken deterministically) fully under our control, keeps the dependency surface minimal, and keeps every behavior derivable and testable. If the event core grows past its remit, that is the trigger to revisit this ADR — not to grow the core silently.
- **Discipline for the hybrid:** every discrete-event scenario must reproduce the corresponding analytic limit in known-answer tests (e.g. long-run simulated queue behavior matches Little's law within tolerance for λ<μ). Analytic results are the ground truth anchor; the simulator earns trust by converging to them.

## Consequences

- Positive: hand-checkable derivations; exact determinism control; minimal supply chain; fast GPU-free CI.
- Negative / accepted costs: we own the event-loop correctness (mitigated by known-answer-limit tests and the analytic anchors); no framework conveniences (process modeling DSLs) — acceptable at fleetlab's scenario complexity.
- Revisit triggers: the dynamics core exceeding its scenario remit; a fitting method that needs more than `scipy.optimize`/`scipy.stats` (that becomes ADR-0002, fitting method); report figures needing a plotting dependency.

## Planned follow-up ADRs

- ADR-0002 — fitting method (FL-T004): functional form of goodput/memory profiles, overfitting guard, error-bar method.
- ADR-0003 — signal-comparison design (FL-T006): fairness protocol, threshold-tuning budget, scoring.
