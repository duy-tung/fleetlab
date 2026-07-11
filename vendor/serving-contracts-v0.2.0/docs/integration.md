# Integration — serving-contracts

## I1 — Contract compatibility (THIS REPO OWNS IT)

**Definition:** all four consumers (`infergate`, `inferbench`, `fleetlab`, `inferops`) validate
the golden fixtures **and** their own emitted artifacts against the same bundle version in CI,
including the unsupported-field rejection cases.

- **Prerequisites:** SC-T009 (bundle v0.1.0) released; consumer CI wiring present in all four
  consumer repos. Pins: contracts v0.1.0.
- **Mechanism:** the SC-T008 compatibility kit. Indicative consumer command:
  `make contracts-verify` — fetch pinned release → validate own emitted artifacts against the
  schemas → validate accepted inputs against the fixtures. No consumer checks out this repo's
  source.
- **Evidence:** four green CI runs referencing the same bundle tag, linked in the inference-lab
  pins file.
- **Failure handling:** fixture mismatch → fix the consumer or file a contract defect; contract
  defect → PATCH release here, then re-run I1.

## I1 re-run triggers

I1 is **re-entrant**. It re-runs on:

1. **Every contract release** (PATCH, MINOR, or MAJOR — no exceptions).
2. **Every MAJOR release**, additionally: migration note published here, version bump in every
   consumer, and the I1 re-run must be green **before any cross-repo scenario is re-claimed**.
3. **The v1.0.0 freeze (SC-T010):** the v1.0.0 I1 re-run is a hard prerequisite for milestone
   I6 (the capacity-feedback loop — the program's central story — runs on frozen contracts).

## The v1.0.0-before-I6 rule

`v1.0.0` freezes the shapes of Contract 1 (API), Contract 2 (metrics, via I1 fixtures), and
Contract 3 (benchmark data). Milestone I6 MUST NOT be claimed on any pre-1.0 bundle. Rationale:
I6 chains measurements across repos (benchmark → recommendation → deployment change →
re-measurement); a contract change mid-loop would silently change the meaning of the numbers
being compared.

## How this repo gates the other milestones

Every integration milestone (I2–I8) runs against pinned bundle versions; I7 executes the 12
fault scenarios encoded in Contract 6. This repo never participates in those runs directly — it
gates them through releases and the kit.

## Consumer wiring guide (summary; full instructions ship with SC-T008)

Per consumer, the wiring is identical in shape:

1. **Pin** the bundle by SemVer tag in CI config (and record the pin in the inference-lab pins
   file).
2. **Fetch** the release artifact for the pinned tag at CI time (never a source checkout of this
   repo).
3. **Validate emitted artifacts:** everything the consumer produces that has a schema here
   (benchmark files for inferbench, recommendations for fleetlab, deployment descriptors for
   infergate, etc.) is validated against the bundle's schemas.
4. **Validate accepted inputs:** everything the consumer accepts that has fixtures here (API
   requests for infergate including negative unsupported-field fixtures it must reject, workload
   files for inferbench, result files for fleetlab, scenario/deployment files for inferops) is
   exercised against the golden fixtures.
5. **Report** the bundle tag in CI output so I1 evidence can reference one tag across all four
   consumers.

## Change-propagation rules (normative text in the compatibility policy)

- MINOR/additive → consumers upgrade at their own pace; compatibility tests stay green on both
  old and new fixtures during the deprecation window.
- MAJOR/breaking → migration note + consumer bumps + I1 re-run before re-claiming scenarios.
- inferbench schema-affecting changes are blocked unless released here first — schemas live
  here, not in inferbench.
- Supported-version matrix lives in `inference-lab`.
