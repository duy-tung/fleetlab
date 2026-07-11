# Charter — serving-contracts

## Mission

`serving-contracts` is the root of the `inference-systems` portfolio dependency graph. It holds the
versioned specifications and schemas for the whole program: the OpenAI-compatible API subset, the
streaming/error/cancellation semantics, the metric and trace vocabulary, and every cross-repo data
schema. It contains **no runtime business logic** — schema-validation tooling is the only permitted
code.

All contracts are versioned together as one bundle under SemVer and released as git tags with
downloadable artifacts. Consumers pin a bundle version; the release tag is the unit of truth.

## Independent value

Any OpenAI-compatible serving project — inside or outside this portfolio — can adopt, standalone:

- the **API subset definition** (which request fields are supported, which are rejected with a
  typed error, and the exact SSE streaming semantics);
- the **metric vocabulary** with normative measurement points (TTFT, ITL, queue wait) so gateway,
  benchmark, and simulation numbers are comparable;
- the **benchmark-data schemas** (workload, run manifest, raw events, results with mandatory
  validity blocks);
- the **fault-scenario catalog** (12 encoded scenarios with expected semantics and abort
  conditions).

The repo is useful alone as a rigorously specified, fixture-backed contract set.

## Integration value

All five other portfolio repositories consume the pinned released bundle:

| Consumer | Role |
|---|---|
| `infergate` | implements Contract 1, emits Contract 2, declares/probes Contract 4, publishes Contract 5 descriptors, tests Contract 6 semantics |
| `inferbench` | drives Contract 1, mirrors Contract 2 client-side, emits Contract 3, feature-gates on Contract 4, measures Contract 6 client impact |
| `fleetlab` | models on Contract 2, consumes Contract 3, respects Contract 4 constraints, emits Contract 7, uses the fleet schemas |
| `inferops` | dashboards/alerts on Contract 2, probes via Contract 4, consumes Contract 5, injects Contract 6, applies Contract 7 as experiments |
| `inference-lab` | maintains the compatibility matrix + pins file; uses all contracts for demos, postmortems, and Scenario E evidence |

No cross-repo interaction is legal except through these contracts, released artifacts, files, or
documented network protocols. Milestone **I1 (contract compatibility)** is owned here.

## Ownership boundary — specs only

This repo owns shared API/schema/metric-vocabulary/compatibility-policy definitions and nothing
else (single-owner matrix, `02-repository-responsibilities`). Hard boundary rules:

- **Depends on nothing.** No provider SDKs, no generated service frameworks, no other portfolio
  repo. Validation tooling may use standard schema validators only (JSON Schema validators,
  OpenAPI linters).
- **Never imports, vendors, or generates code for consumers.** Consumers validate against
  fixtures; they do not link against this repo. No shared application library, ever.
- **No engine-scheduling concepts smuggled into gateway responsibilities.** Contracts describe
  what engines expose and what the gateway must guarantee, never how the gateway should schedule
  or how engines batch internally.
- **No speculative contract surface.** A schema with only one real consumer does not ship here.
  infergate's admin API (`/admin/v1/...`) is deliberately repo-private to infergate (program
  assumption A4); it is promoted only if a second consumer appears.

## Definition of Done (repo-level)

The repo is accepted when: v1.0.0 is released; milestone I1 is green across all four consumers on
that version; and the compatibility policy has been exercised at least once — one deprecation or
one migration executed cleanly through the documented process.
