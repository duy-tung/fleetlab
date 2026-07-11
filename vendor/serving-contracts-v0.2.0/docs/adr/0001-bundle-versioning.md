# ADR-0001 — Bundle versioning, not per-schema versioning

- **Status:** Accepted (design fixed in the approved program plan)
- **Date:** 2026-07-10

## Context

The repo publishes one OpenAPI spec, 13 JSON Schemas, two normative metrics documents, a
compatibility policy, and a fixture set. Two versioning models were available:

1. **Per-schema versions** — each schema evolves independently with its own SemVer; consumers
   pin a matrix of versions.
2. **One bundle version** — all contract files are versioned and released together under a
   single SemVer tag; consumers pin exactly one version.

The contracts are strongly cross-referential: benchmark results reference SLOs and cost
profiles; capacity recommendations reference benchmark results, workloads, and hardware
profiles; fault scenarios reference API error semantics and metric names; the API error taxonomy
appears in metrics labels (`error_class`). Per-schema versioning would force a compatibility
matrix *inside* the contract set itself, and milestone I1 ("all four consumers green against the
same version") would lose its single reference point.

## Decision

**One bundle, one SemVer version.** Every release tags the entire contract set together
(`vX.Y.Z` annotated tag + reproducible downloadable artifact). A change to any file yields a new
bundle version classified by the most severe change in the release. Consumers pin the bundle
tag, never individual files.

## Consequences

- I1 evidence is four green consumer CI runs referencing **one** tag — simple and auditable.
- A breaking change in one schema forces a MAJOR bump on the whole bundle. Accepted cost: the
  migration note states which files actually changed, so untouched-contract consumers can
  upgrade trivially — but they still bump the pin (keeps the supported-version matrix in
  inference-lab one-dimensional).
- Release cadence is shared; a PATCH fix cannot ship for one schema "on its own version". This
  is deliberate: it keeps pin bookkeeping (program risk R1) linear in the number of consumers,
  not schemas × consumers.
