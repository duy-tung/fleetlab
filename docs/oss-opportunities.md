# fleetlab — OSS Opportunities

Modest, deliberately narrow for this repo. Every item follows the program's OSS rules: grounded in measured evidence with full manifests, scoped to docs/metrics/tests, and **any submission requires user review before posting**.

## 1. Published methodology artifacts (primary track)

The program's OSS track accepts a "public benchmark or design artifact." fleetlab's qualifying candidates:

- **The holdout-validation report** (`reports/holdout-validation.md`, G8 evidence): a worked example of structurally enforced train/holdout separation for capacity-model fitting — including the honest publication of prediction misses.
- **The autoscaling-signal-comparison methodology** (`reports/autoscaling-signal-comparison.md`): six candidate signals, same workloads/SLOs/tuning effort, with a when-each-signal-fails analysis rather than a single winner claim.
- **The KV-memory worksheet** (study-track artifact feeding FL-T003): the `2 × layers × kv_heads × head_dim × dtype_bytes × tokens` derivation cross-checked against measured engine memory, with the residual (allocator/fragmentation effects) documented.

These are published as part of the repo/reports; "OSS" here means public, reusable, and citable — no upstream PR required.

## 2. Possible upstream feedback to vLLM docs (fallback target)

vLLM is the program's OSS fallback target, **docs/metrics/tests scope only**. fleetlab's ingestion and profile fitting exercise vLLM's exposed metrics (e.g. waiting-queue and KV-usage gauges, whose names vary by version and are mapped via Contract 4 capability files). Plausible contributions if evidence emerges:

- Documentation drift or ambiguity in the waiting/KV-usage gauge definitions discovered while building the metric-name mapping.
- Clarifications to metric semantics that made profile fitting ambiguous (with the measured manifests demonstrating the ambiguity).

Constraints: grounded in measured evidence with full manifests; user review before posting; maintainer responsiveness is unverified as of 2026-07 — re-verify live before investing effort.

## 3. Never

- Scheduler rewrites or architecture proposals to any engine project.
- Unverified performance claims, anywhere.
- Any contribution that would require fleetlab to import or couple to upstream source (files and docs only — the same boundary discipline as inside the program).

## Tracking

OSS activity is logged by `inference-lab` (program OSS log). This file only identifies the opportunities; anything actually submitted gets an entry in `implementation-notes.md` plus the inference-lab log, with links to the evidence used.
