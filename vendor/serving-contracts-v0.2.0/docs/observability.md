# Observability — serving-contracts

## This repo DEFINES the vocabulary; it does not emit it

Contract 2 (`metrics/metrics.md` + `metrics/cardinality-policy.md`, authored in SC-T005) is the
program's single observability vocabulary: 11 canonical metrics (Prometheus naming, units in
name, declared histogram buckets), the allowed/forbidden label sets, the trace-attribute set
with a pinned OTel GenAI semconv version, the gateway span sequence
(`recv → queue.wait → upstream.connect → ttft → stream.relay → settle`), and the normative
TTFT/ITL/queue-wait measurement points.

The repo itself has no runtime, so its own observability is exactly:

- **CI logs** (schema lint, fixture validation, kit self-test) — the evidence trail for every
  "validates/green" claim;
- **release artifacts** (tags, bundle archives, release notes) — the evidence trail for what
  consumers actually pinned.

## Stewardship duties

As vocabulary owner, this repo must:

1. **Keep definitions unambiguous.** Gateway-side vs client-side series are explicitly separated
   (e.g. gateway TTFT vs inferbench's client-measured TTFT are distinct, named series).
   Measurement-point definitions are normative so gateway, benchmark, and simulation numbers are
   comparable.
2. **Guarantee roadmap coverage.** Every metric named anywhere in the program roadmap must appear
   in `metrics/metrics.md` (SC-T005 stop condition). Dashboards and alerts in inferops key off
   the vocabulary, never off ad-hoc names.
3. **Classify every vocabulary change.** A metric rename or histogram-bucket change is MAJOR
   (it changes the meaning of previously-recorded measurements — see the breaking-change
   definition in the compatibility policy). New metrics or labels with enumerable values are
   MINOR.

## Drift-check procedure (volatile ecosystem facts — program risk R3)

Engine metric names and the OTel GenAI semantic conventions are volatile (semconv status
"Development" as of 2026-07 — re-verify at use time).

- **Pins:** the semconv version pin in Contract 2 is mandatory; backend-capability descriptors
  carry a metric-name **mapping** per engine version instead of hardcoded names.
- **Trigger:** a consumer reports a conformance failure, a mapping test fails on a new engine
  version, or a semconv pin bump is proposed.
- **Procedure:**
  1. Re-verify the upstream fact at its source (engine release notes / semconv changelog) and
     date the finding.
  2. Classify the required contract change (mapping update in an example descriptor = PATCH/MINOR;
     attribute rename following a semconv bump = MAJOR).
  3. Record the finding and classification in `docs/implementation-notes.md`; semconv gaps or
     ambiguities also go to `docs/experiments.md` as candidate OSS clarifications.
  4. Release per the compatibility policy; I1 re-runs on every release, which is what makes
     drift visible program-wide.
- **Cadence:** no fixed timer; drift checks are event-driven (consumer failure or pin bump), plus
  a mandatory re-verification of all "as of 2026-07" flags at each release that touches them.
