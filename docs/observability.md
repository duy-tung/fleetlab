# fleetlab — Observability

fleetlab is an offline, single-process tool: it emits no Prometheus metrics and no traces about itself. Its observability is **run-record discipline** — every run must be reconstructible and auditable from its outputs alone.

## The run record (embedded in every output artifact)

Every artifact fleetlab writes — fitted profiles, scenario outputs, report tables, Contract-7 recommendation files — embeds:

| Field | Content | Why |
|---|---|---|
| `contract_bundle_version` | the pinned serving-contracts bundle tag | comparability + I1 audit |
| `input_digests` | SHA-256 per input file (workloads, results, raw events, profiles) | exact-input reconstruction; detects silent input drift |
| `seed` | the run's RNG seed | determinism: same seed + same digests ⇒ byte-identical tables |
| `fleetlab_version` | version + git commit of fleetlab itself | which model code produced the number |
| `timestamp` | run wall-clock time (UTC) | dating for volatile inputs (prices, ecosystem facts) |
| `provenance` | per-parameter flags: `measured` (with source run-manifest reference) / `source-reported` (with source + date) / `assumed` (with rationale + date) | no number without a pedigree |
| `train/holdout split` | run IDs on each side (fitted profiles and validation reports only) | G8 auditability |

A test asserts the run record is present and complete in every emitted artifact (see `testing.md` §5).

## Logging

- **Rejected inputs are always named:** every ingest refusal logs (and raises with) the file path, the field, and the rule violated — e.g. `hardware-profile gpu-a10g.yaml: field 'provenance' missing: profiles without provenance are refused`. No aggregate "N files failed" without the list.
- Structured, human-readable logs to stderr; results to declared output files only. No log-scraping needed to find a result — everything a consumer needs is in the artifact.
- Warnings are reserved for provenance-flagged assumptions in use (`provenance: assumed` parameters are echoed at run start so a reader can't miss what was assumed), never for recoverable schema problems — those are hard errors.

## Reproducibility as the audit path

The reproducibility story replaces dashboards: any published number can be traced to (artifact → run record → input digests + seed → rerun ⇒ identical output). The program's I8 reproducibility audit removes any claim that fails this trace, so the run record is treated as part of the deliverable, not metadata garnish.

## What fleetlab does NOT observe

- No metrics/traces about fleetlab's own execution performance (it is a batch tool; pytest keeps it fast enough).
- No runtime telemetry collection from live systems — Contract 2 metric *definitions* enter fleetlab as model-input vocabulary via files, never via a live Prometheus connection. fleetlab has no network at runtime (`security.md`).
