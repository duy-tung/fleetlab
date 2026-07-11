# ADR-0003 — OpenAPI 3.1.x for the inference API spec

- **Status:** Accepted (re-confirm at SC-T002, before `openapi/inference-api.yaml` is authored)
- **Date:** 2026-07-10

## Context

Contract 1 (`openapi/inference-api.yaml`) needs an OpenAPI version. Candidates: 3.0.x (older,
widest legacy tooling) and 3.1.x (current; schema objects are full JSON Schema 2020-12).

Decisive factors:

- ADR-0002 pins JSON Schema 2020-12 for `schemas/`. OpenAPI 3.0's schema object is a
  *divergent subset* of JSON Schema; 3.1 uses 2020-12 natively, so API fixtures and standalone
  schemas validate under one dialect and error-envelope/chunk shapes can be shared by `$ref`
  without translation.
- The rejection-not-ignore rule needs precise `additionalProperties`/`unevaluatedProperties`
  semantics to make negative fixtures machine-checkable — cleaner in 3.1.
- Mainstream linters (e.g. Spectral, Redocly) and Go/Python tooling support 3.1 (as of 2026-07 —
  re-verify at use time when SC-T002 selects the linter).
- SSE streaming bodies are not fully modelable in any OpenAPI version; the streaming semantics
  are specified as normative prose + fixtures either way, so 3.0 offers no advantage there.

## Decision

`openapi/inference-api.yaml` declares `openapi: 3.1.x` (exact patch chosen at SC-T002). The
OpenAPI version is part of the contract surface; changing it follows the compatibility policy
(MAJOR if it changes validation outcomes for previously-valid artifacts).

## Consequences

- One schema dialect across the whole bundle (with ADR-0002).
- Consumers with 3.0-only tooling must upgrade their linters; SC-T008 wiring docs name tested
  tools.
- Recorded pre-spec so policy/testing docs reference a pinned choice; reversal is free until
  SC-T002 authors the file, where this ADR is re-confirmed or superseded.
