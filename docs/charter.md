# fleetlab — Charter

## Mission

fleetlab is an **explainable capacity, autoscaling, cost, configuration, and heterogeneous-placement simulation** for LLM inference fleets, written in Python. It answers capacity questions from measurement files alone: given schema-conformant benchmark results and hardware/model/SLO/cost profiles, it produces capacity, autoscaling-signal, cost, and placement analysis — with stated uncertainty on every prediction.

fleetlab is one of six repositories in the Composable AI Inference Systems portfolio (`serving-contracts`, `infergate`, `inferbench`, `fleetlab`, `inferops`, `inference-lab`). It is **not** a production scheduler, controller, or autoscaler. It is a CLI + library that reads files and writes files: no daemon, no server, no database, no GPU, no cluster, no gateway required.

## The simulation ≠ production pledge

This is a hard rule, restated everywhere fleetlab publishes anything:

> **Simulation is not production.** Every published fleetlab artifact states its uncertainty and its limitations. Prediction error against holdout measurements is a publishable *result*, not a failure to hide. No fleetlab output may claim, imply, or be phrased as if simulated numbers are production guarantees.

Concrete consequences of the pledge:

1. **Provenance is mandatory.** Every model parameter is either *fitted from measured benchmark data* (with the source run manifest referenced) or *explicitly assumed* (with a `provenance: assumed` flag and a date). There are no fabricated defaults; ingestion refuses profiles that lack provenance fields.
2. **Holdout validation is structural (gate G8).** Fit quality is only ever reported against benchmark runs *not used for fitting*. The fitting API takes an explicit train/holdout split and refuses to report fit quality on training data. A holdout miss is documented as a limitation and published.
3. **The simulation-limitations report is a required deliverable** (one of the five required reports), stating what is modeled, what is not, and the known error magnitudes from G8.
4. **Extrapolation is refused, not caveated.** Placement reasoning covers only hardware with measured profiles. fleetlab does not predict for GPUs nobody measured.

The portfolio's program-level honest-limitations statement includes: "simulation ≠ production — fleetlab predictions carry stated uncertainty." Nothing in this repository may contradict that sentence.

## Independent value

fleetlab is useful to any team that has measurement files and a capacity question, with zero dependency on the rest of the portfolio:

- Inputs: benchmark-result and raw-event files (Contract 3 shapes), workload manifests, and hardware/model/SLO/cost profiles — from *anyone*, as long as they conform to the pinned `serving-contracts` schema bundle and carry provenance.
- Outputs: machine-readable capacity recommendations (Contract 7) and human-readable reports (autoscaling policy comparison, cold-start headroom, heterogeneous placement, cost/capacity model, simulation limitations).
- Indicative command shape: `fleetlab recommend --results ... --slo ... --cost ...`.

Everything runs from files, deterministically, on a laptop: every simulation and fitting run is seeded, and outputs record the seed, input digests, and contract bundle version.

## Integration value: the I6 role

fleetlab closes the program's central story, milestone **I6 — Capacity feedback**:

1. `inferbench` produces benchmark results (files).
2. `fleetlab` produces a schema-valid capacity recommendation with stated uncertainty (Contract 7 file).
3. `inferops` applies the recommended change (replica counts / engine config).
4. `inferbench` re-measures.
5. **Predicted vs measured is compared and published — including where the prediction was wrong.**

The machine-readable Contract 7 recommendation file is what makes the loop checkable. If the prediction is badly off, that is a result: the error analysis is published and the profiles are refined (G8 discipline). The loop may shrink to mock/llama.cpp scale if the GPU budget is exhausted (recorded as a deviation), but it must close.

## Position and boundaries

- Consumes: pinned `serving-contracts` bundle (schemas); benchmark files emitted by `inferbench`. **Files only — never inferbench code.**
- Provides: Contract 7 recommendation files + reports, consumed by `inferops` (applies) and `inference-lab` (archives as Scenario E evidence).
- Owns as state: hardware/model/cost/SLO profile files, versioned, provenance-carrying.
- Never: generates load, deploys, proxies requests, imports another component's source, or is imported as a library by another repo.

See `scope.md` for the full ownership list and `non-goals.md` for what fleetlab must never grow into.

## Definition of done (summary)

fleetlab is done when, with evidence linked from `docs/`: (1) the G8 holdout gate has passed — prediction of an unfitted benchmark run within stated error bars, or the miss published with error analysis; (2) all five required reports are published; (3) a Contract-7 recommendation is schema-validated in CI, consumed by inferops in a dry run, and used in the real I6 loop at whatever scale the budget permitted, with deviations recorded. Details in `milestones.md`.
