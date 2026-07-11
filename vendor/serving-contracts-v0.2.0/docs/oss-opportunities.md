# OSS opportunities — serving-contracts

## Primary track: OpenTelemetry GenAI semantic conventions

**Why this track:** it is spec/docs work (no GPU, no runtime), it overlaps directly with this
repo's Contract 2 (metrics + trace vocabulary), and the conventions are still moving — status
"Development" as of 2026-07 (re-verify at use time) — so real gaps and ambiguities exist to be
found by anyone applying them rigorously.

**How contributions arise here:** while authoring SC-T005, every attribute we pin, every
measurement point we make normative (gateway TTFT vs client TTFT, ITL as inter-chunk gap, queue
wait as admission-enqueue→dispatch), and every place the upstream conventions are silent or
ambiguous gets recorded as a spec-ambiguity probe in `docs/experiments.md`. Probes marked
"candidate upstream contribution" are the OSS pipeline.

**Expected contribution shapes:**

- clarification PRs/issues on ambiguous attribute definitions (e.g. what counts as "time to
  first token" at a proxy vs at a client);
- gap reports where gateway/proxy-level GenAI serving concepts (queueing, shedding, retries,
  usage settlement) have no conventional attributes;
- feedback on streaming-related span/event modeling from the SSE semantics this repo specifies.

## Gating rules (program-level, non-negotiable)

- **Secondary target.** OSS runs cheaply in parallel; it is **never on the critical path**. The
  program's contingency rules for slow upstream review apply — no SC task blocks on an upstream
  response.
- **Target sign-off** happens at inference-lab task IL-T010, not here.
- **Every upstream submission gets user review before posting.** Nothing is filed upstream
  autonomously; probes stay in `docs/experiments.md` until reviewed.
- **Pin discipline:** the semconv version pin in Contract 2 stays mandatory regardless of
  upstream progress; contributions never justify tracking upstream HEAD.

## Study-track artifacts that touch this repo

- The **DistServe** paper's goodput@SLO definition is encoded in the metric vocabulary and the
  benchmark-result schema (SC-T003/SC-T005).
- The **goodput-critique rule** ("stall rate reported beside goodput") is enforced structurally
  by the benchmark-result schema, not just by prose.

## Log

_No upstream contributions proposed yet (as of SC-T001, 2026-07-10). Candidates accumulate in
`docs/experiments.md` first._
