# Experiments — serving-contracts

## Runtime experiments: N/A by design

This repo has no runtime, so there are no performance or behavior experiments to run here. The
single recorded performance hypothesis (validator kit adds negligible time to consumer CI) lives
in `docs/testing.md` and is measured once when the kit exists.

## What this file IS for: spec-ambiguity probes

While authoring contracts — especially the metrics/trace vocabulary (SC-T005) against the OTel
GenAI semantic conventions (status "Development" as of 2026-07 — re-verify at use time) — we
will hit real gaps and ambiguities in upstream specs. Each one is recorded here as a
**spec-ambiguity probe**: a dated note of the ambiguity, how it was observed, what interpretation
this repo pinned, and whether it is a candidate upstream clarification for the OSS track
(`docs/oss-opportunities.md`).

Probe entry format:

```markdown
### SAP-NNN — <short title> (YYYY-MM-DD)
- **Upstream spec + version:** e.g. OTel GenAI semconv <pinned version>
- **Ambiguity/gap:** what the upstream text leaves undefined or contradictory
- **Observed while:** which SC task / which contract section forced the question
- **Interpretation pinned here:** the normative choice this bundle makes, and where it is written
- **Candidate upstream contribution:** yes/no + one-line proposal
- **Status:** recorded | proposed upstream (after user review) | resolved upstream
```

Gating reminders (program rules): OSS progression is gated — target sign-off happens at
inference-lab task IL-T010, and every upstream submission gets user review before posting. OSS
work never sits on the critical path.

## Probes

_None recorded yet (as of SC-T001, 2026-07-10). Expect the first entries during SC-T005._
