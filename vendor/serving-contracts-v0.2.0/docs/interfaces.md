# Interfaces — serving-contracts

## The one interface: the release bundle

The **released bundle** (annotated git tag `vX.Y.Z` + downloadable artifact containing the
OpenAPI spec, all JSON Schemas, the metrics documents, the compatibility policy, and the
`examples/` fixtures) is the **only** interface this repository exposes.

Rules:

- Consumers **fetch a pinned release** in CI. They never check out this repo's source in their
  build, never vendor its files ad hoc, and never link against anything here.
- Pins live in each consumer's CI config **and** in the `inference-lab` pins file. The
  supported-version matrix (which bundle versions each released component supports) is maintained
  in `inference-lab`.
- Tag content equals committed content; the bundle artifact is reproducible from the tag
  (verified as part of the release process — see `compatibility/compatibility-policy.md`).
- There is no other ingress or egress: no API, no network protocol, no shared library.

## Per-contract consumer table

| Contract | infergate | inferbench | fleetlab | inferops | inference-lab |
|---|---|---|---|---|---|
| 1 — Inference API | implements | drives | — | smoke tests | demos |
| 2 — Metrics/trace vocabulary | emits | client-side mirror definitions | model inputs | dashboards/alerts | evidence keys |
| 3 — Benchmark data | — | emits | consumes | — | reports |
| 4 — Backend capability | adapters declare + probe | feature-gates workloads | model constraints | probe configuration | — |
| 5 — Deployment | publishes descriptor per release | — | — | consumes | pins |
| 6 — Fault scenarios | semantics tests | client-impact measurement | — | injects | postmortems |
| 7 — Capacity recommendation | — | — | emits | applies as experiment | Scenario E evidence |
| Fleet schemas (hardware/model/SLO/cost) | — | — | emits/consumes | — | evidence |

Deliberate exclusion: **infergate's admin API (`/admin/v1/...`) is repo-private to infergate**,
not a shared contract (single consumer; program assumption A4).

## Fixture usage per consumer

`examples/` is the golden fixture set. The general pattern for every consumer is:
**fetch pinned bundle → validate own emitted artifacts against the schemas → validate own
accepted inputs against the fixtures** (the SC-T008 kit ships inside the bundle at `kit/`;
per-consumer wiring instructions in `kit/README.md`; indicative wrapper command:
`make contracts-verify` invoking `python3 kit/contracts-validate.py`).

| Consumer | Validates against fixtures |
|---|---|
| `infergate` | API request/response/SSE fixtures (including negative unsupported-field fixtures it must reject); error-envelope fixtures per taxonomy entry; capability descriptors its adapters must parse; fault-scenario expected-semantics entries its tests assert; deployment-contract examples it must be able to emit |
| `inferbench` | API fixtures it must be able to send/receive; workload example fixtures its generator must parse; benchmark-run/raw-event/benchmark-result fixtures its emitters must match (schema-affecting changes are released here first — never in inferbench) |
| `fleetlab` | benchmark-result and raw-event fixtures it ingests; hardware/model/SLO/cost-profile fixtures it accepts; capacity-recommendation fixtures it must emit conformantly |
| `inferops` | deployment-contract fixtures it consumes; fault-scenario fixtures it injects from; capability fixtures for probe configuration; metric names keyed from `metrics/metrics.md` for dashboards/alerts |
| `inference-lab` | the whole set — it runs the compatibility matrix and records I1 evidence |

## Change propagation (summary; normative text in the compatibility policy)

- **MINOR/additive:** consumers upgrade at their own pace; compatibility tests stay green on both
  old and new fixtures during the deprecation window.
- **MAJOR/breaking:** migration note in this repo, version bump in every consumer, and a re-run
  of milestone I1 before any cross-repo scenario is re-claimed.
- Any inferbench schema-affecting change is blocked unless contracts released it first — the
  schemas live here, not in inferbench.
