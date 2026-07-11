# ADR-0002 — JSON Schema draft pinned to 2020-12

- **Status:** Accepted (re-confirm at SC-T002/T003, before the first schema file is authored)
- **Date:** 2026-07-10

## Context

The program plan requires declaring and pinning the JSON Schema draft in an ADR (testing
section: JSON Schema meta-validation against a pinned draft). Realistic candidates: draft-07
(broadest legacy validator support) and draft 2020-12 (current stable draft; the dialect OpenAPI
3.1 uses natively).

Constraints that matter here:

- ADR-0003 selects OpenAPI 3.1.x, whose schema objects are JSON Schema 2020-12 dialect —
  a single dialect across `openapi/` and `schemas/` avoids subtle keyword-behavior differences
  (e.g. `items`/`prefixItems`, `$defs`).
- Consumers span Go and Python; mainstream validators in both ecosystems support 2020-12
  (as of 2026-07 — re-verify at use time when the kit selects concrete validators in SC-T008).
- The schemas need `unevaluatedProperties`/conditional composition for rules like
  "closed-loop arrival requires the disclosure flag" and mandatory provenance blocks; 2020-12
  semantics for these are cleaner than draft-07 workarounds.

## Decision

All `schemas/*.schema.json` declare `"$schema": "https://json-schema.org/draft/2020-12/schema"`.
CI meta-validates every schema against that draft. The draft is part of the contract surface:
changing it is at minimum a MINOR bump, and MAJOR if it changes validation outcomes for
previously-valid artifacts.

## Consequences

- One dialect everywhere; OpenAPI and standalone schemas can share definitions by reference
  without dialect translation.
- Consumers must use 2020-12-capable validators; the SC-T008 wiring docs will name tested ones
  per ecosystem.
- Recorded pre-schema (SC-T001) so the compatibility policy and testing docs can reference a
  pinned choice; cost of reversal is zero until SC-T002/T003 write the first schema, where this
  ADR is re-confirmed or superseded.
