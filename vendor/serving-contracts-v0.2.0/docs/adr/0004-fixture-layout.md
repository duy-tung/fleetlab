# ADR-0004 — Fixture layout under `examples/`

- **Status:** Accepted
- **Date:** 2026-07-10

## Context

`examples/` is the golden fixture set consumed by all four consumer CIs (the I1 mechanism). It
must make three things mechanical: (a) which schema/spec a fixture validates against, (b)
whether a fixture is positive (must validate) or negative (must fail), and (c) coverage
auditing (one negative fixture per unsupported API field class and per error-taxonomy entry;
incomplete-manifest and provenance-less negatives; 8 workloads; 3 capability descriptors; 12
fault scenarios).

## Decision

Fixtures are grouped by contract area, with negative fixtures in an `invalid/` subdirectory of
the area they violate:

```text
examples/
├── api/                      # Contract 1: requests, responses, SSE transcripts (streams as .sse text)
│   └── invalid/              # unsupported-field requests, malformed envelopes — one per rejection class
├── workloads/                # Contract 3: the 8 named workloads (non-normative examples)
│   └── invalid/
├── benchmark/                # Contract 3: run manifests, raw events (.jsonl), results
│   └── invalid/              # incl. the deliberately incomplete manifest, result w/o validity block
├── capabilities/             # Contract 4: mock.json, llamacpp.json, vllm.json
│   └── invalid/
├── deployment/               # Contract 5: descriptors
│   └── invalid/
├── faults/                   # Contract 6: the 12 scenarios, one file each (fs-01 … fs-12)
│   └── invalid/
├── fleet/                    # hardware/model/SLO/cost profiles
│   └── invalid/              # incl. provenance-less instances
└── capacity/                 # Contract 7: recommendations (+ Scenario E end-to-end chain)
    └── invalid/
```

Conventions:

- **Validation target is derivable from the path** (directory → schema/spec); the validator kit
  carries this mapping as configuration, not code heuristics.
- **`invalid/` fixtures MUST fail validation**; each carries a `// why-invalid` note in an
  adjacent `<name>.reason.txt` (JSON has no comments) naming the violated rule.
- File naming: `<short-purpose>.<ext>` with stable names (fixtures are contract surface —
  renames are at least MINOR per the compatibility policy); multi-record raw events use
  `.jsonl`; SSE transcripts use `.sse`.
- Directory names are part of the bundle interface once released (consumer CI paths depend on
  them); layout changes after v0.1.0 follow the compatibility policy.

## Consequences

- Coverage audits are directory listings (12 fault files, 8 workload files, 3 capability files,
  invalid/ per area) — checkable in CI without bespoke logic.
- The kit's green run = all non-`invalid/` fixtures pass; its demonstrated-failure run = all
  `invalid/` fixtures fail. A fixture in the wrong directory is caught automatically.
- Slightly deeper paths than a flat layout; accepted for mechanical positive/negative
  separation.
