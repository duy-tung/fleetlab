# fleetlab — Implementation Notes

Running log of notable events: surprises, assumption changes, reduced scope, prediction misses, upstream waits. Deviations from the approved plan go under **Deviations** per the program deviation policy:

> When repository evidence forces a deviation from the approved plan, choose the conservative reversible option, record the evidence, decision, consequences, and follow-up under `Deviations`, and continue. Pause only when the deviation changes public contracts, repository ownership, security posture, or milestone scope.

## Log

### 2026-07-10 — FL-T001 docs bootstrap
- Created the full 15-file `docs/` set + `docs/adr/0001-stack-and-simulator-style.md` per the approved plan (planning prompt §5). Docs only; no implementation code yet.
- Repo state at start: empty repository (unborn `main`), no code, no CI.
- **Assumption (reversible):** `serving-contracts` has no released bundle tag as of 2026-07-10 (its repo has no commits yet), so no bundle version could be pinned. `docs/interfaces.md` records the pin as **NOT YET PINNED**; the pin is set at the start of FL-T002 (which depends on SC-T007 anyway) and recorded in `interfaces.md`, CI, and every emitted artifact. No architecture or contract shape was invented to compensate — all contract descriptions in the docs restate the program planning documents.
- **Assumption (reversible):** ADR-0001 (stack + simulator style) is drafted with a recommendation but marked **Proposed** — every ADR is a mandatory human review point; it is not treated as accepted until reviewed.
- Mandatory review point now open: user review of the docs set (charter/scope/non-goals in particular) before FL-T002 begins.

### 2026-07-11 — FL-T002 ingestion + validation

- **Contract bundle pinned:** `serving-contracts` tag `v0.2.0` @ commit
  `484b449` (the tag exists now; `docs/interfaces.md` updated from "NOT YET
  PINNED"). Vendored read-only via `git archive 484b449 | tar -x` into
  `vendor/serving-contracts-v0.2.0/` — never fetched at runtime.
- **Validation mechanism decision (recorded per the task's "your call,
  record it"):** `fleetlab/ingest/*` validates directly against
  `jsonschema.Draft202012Validator` (already ADR-0001's pinned dependency)
  rather than shelling out to the bundle's own
  `kit/contracts-validate.py`. Reason: fleetlab's typed-refusal requirement
  (distinguish provenance-missing / unsupported-field / generic schema
  violations as Python exception types) needs programmatic access to
  `jsonschema`'s error objects that the kit's CLI (text/JSON summary +
  process exit code) does not expose. Both consume the identical vendored
  schema files, so there is no drift between what `make contracts-verify`
  (running the kit's `selftest` against the same vendored bundle) checks and
  what the library enforces. Full rationale in `fleetlab/ingest/bundle.py`.
- **Refusal classification heuristic:** a schema violation is classified
  `ProvenanceMissingError` when its JSON pointer passes through
  `provenance`/`basis`/`as_of`/`source`, OR when the failing sub-schema is
  structurally one of the three reusable provenance `$defs`
  (`provenance`, `provenancedNumber`, `provenancedInteger`) — this covers
  both "bare number where a `{value, provenance}` object was required" and
  "provenance object present but missing `basis`/`as_of`/`source`".
  `additionalProperties` violations are classified `UnsupportedFieldError`
  ahead of this check. Verified against every real `invalid/` fixture
  serving-contracts ships for the profile schemas
  (`hardware-missing-provenance.json`, `cost-reported-without-source.json`,
  `slo-declared-in-advance.json`) plus fleetlab's own synthetic
  unsupported-field fixtures.
- **42 golden-file tests green**, all four classes (valid / invalid /
  provenance-missing / unsupported-field) exercised for every input type
  named in `docs/testing.md` §1.
- **Real-file stop condition met:** the full available corpus —
  `inferbench/workloads/*` (8 canonical workloads), `inferbench/docs/
  evidence/{ib-t004,ib-t010}/**/manifest.json` + `inference-lab/evidence/
  i3/**/manifest.json` (48 manifests), the corresponding `events.jsonl`
  files (48 files, ~13,433 events), and `inferbench/docs/evidence/ib-t005/
  results/*` + `inference-lab/evidence/i3/raw/results/*` (10 benchmark
  results) — all ingest cleanly. Two files correctly **refuse**:
  `inference-lab/evidence/i3/aborted/{attempt-1,attempt-2}-.../events.jsonl`,
  both session-truncated JSONL from documented aborted sessions
  (`evidence/i3/notes.md`: "two aborted attempts...excluded from every
  acceptance number"). This refusal is the correct behavior (a truncated
  record must never be silently skipped) and is asserted explicitly as a
  passing test, not treated as noise.
- **Deviation — no hardware-profile example for the CPU-only measured
  host.** `hardware-profile.schema.json` requires a `gpu` block
  (`gpu.model`, `gpu.count_per_node >= 1`, `gpu.vram_gb`); it has no schema
  path to represent a CPU-only host without fabricating a placeholder GPU
  entry. fleetlab does not fabricate one. `profiles/examples/` therefore
  ships the GPU reference family (copied, attributed, from
  `serving-contracts examples/fleet/`) plus fleetlab-authored
  model/SLO profiles for the real CPU/llama.cpp/Qwen2.5-1.5B environment,
  but no `hardware-*.json` for that CPU host. Conservative/reversible per
  the deviation policy (§15): no public contract, ownership, or milestone
  scope changed. Filed here as a note for a future `serving-contracts`
  contract question, per `docs/interfaces.md`'s "never patched locally"
  rule — not raised as a live issue in this session.

### 2026-07-11 — FL-T003 core models

- `fleetlab/models/{arrival,length,token_rate,littles_law,kv_memory}.py`
  implemented; 61 tests green (`tests/models/`), including determinism
  tests (byte-identical output for the same seed; a static-analysis test
  that fails the suite if module-level/global RNG usage appears anywhere in
  `fleetlab.models`).
- **KV-memory cross-check against measured engine memory: recorded
  PENDING**, not fabricated. Full investigation in
  `docs/notes/model-validation.md` §5.2: checked llama.cpp's `/metrics`
  (11 series, none memory-related; `kv_cache_usage_ratio: null` in the real
  backend-capability descriptor), every captured server log (grepped
  case-insensitively for KV/MiB/GiB/buffer/graph — no memory figures at the
  captured verbosity), and `/slots` poll data (no memory field). The one
  memory figure in any available evidence (a tiny synthetic model's whole-
  process RSS, from the llama.cpp probe report) is for an unrelated model
  and is not KV-isolated; used only as an explicitly-labeled weak,
  non-tight sanity note, never as a passing cross-check. What would close
  this out: a llama.cpp build/run that logs its internal KV-buffer
  allocation at load time, an isolated before/after RSS delta varying only
  context size, or a vLLM run exposing `kv_cache_usage_ratio` (no vLLM run
  has produced data yet in this program).
- Formula known-answer validated exactly against an **independently
  authored** fixture: `serving-contracts examples/fleet/
  model-llama31-8b.json`'s documented `kv_cache_bytes_per_token: 131072`
  (computed there, in that repo, as "2 x 32 x 8 x 128 x 2") is reproduced
  exactly by `kv_cache_bytes_per_token(32, 8, 128, 2)`.
- Qwen2.5-1.5B-Instruct architecture parameters (layers=28, kv_heads=2,
  head_dim=128, context_length=32768) were **measured** directly from the
  real served GGUF checkpoint (`qwen2.5-1.5b-instruct-q4_k_m.gguf`, sha256
  `6a1a2eb6...`) via llama.cpp's own `gguf_dump.py`, this session — not
  looked up from a model card. `profiles/examples/
  model-qwen2.5-1.5b-instruct-gguf-q4km.json` records this provenance in
  full, including the explicit `assumed` (not `measured`) basis on the
  KV-cache-dtype-dependent final value, per the PENDING cross-check above.
- Little's law and the token-rate model both cross-check successfully
  against real data (Little's law: exact sample-path identity on two real
  raw-event traces; token-rate: `system_output_token_rate` reproduces a
  real benchmark-result's `output_tokens_per_second` to `rel=1e-6`) — see
  `docs/notes/model-validation.md` §3-4.
- No `scipy`/`pandas` dependency added: FL-T003's closed-form models needed
  only `numpy` (seeded RNG, sampling, percentiles). ADR-0001 already flags
  `scipy` as a FL-T004 (profile fitting) candidate, justified there when
  actually needed.

## Assumptions register

| # | Date | Assumption | Reversible? | Revisit when |
|---|---|---|---|---|
| A1 | 2026-07-10 | Contract bundle pin deferred to FL-T002 start (no serving-contracts release exists yet) | yes | first serving-contracts tag |
| A2 | 2026-07-10 | ADR-0001 recommendation (see file) pending human review | yes | FL-T001 review |
| A3 | 2026-07-11 | fleetlab validates directly against `jsonschema` rather than shelling out to the vendored `kit/contracts-validate.py`; the kit stays wired as the I1 CI mechanism | yes | if CI wiring reveals drift between the two paths |
| A4 | 2026-07-11 | KV-cache dtype for the Qwen2.5-1.5B profile is `assumed` (llama.cpp fp16 default), not measured — no run in evidence overrides `--cache-type-k/v` or logs the active KV dtype | yes | a run manifest/log that states the KV dtype explicitly, or a measured KV-memory metric |

## Deviations

- **2026-07-11 — no hardware-profile example for the CPU-only measured
  host.** Evidence: `hardware-profile.schema.json` requires `gpu.model`,
  `gpu.count_per_node >= 1`, `gpu.vram_gb` — structurally GPU-only; the
  CPU-only hosts actually measured in `ib-t010`/`i3` have no GPU to
  describe. Decision: do not fabricate a placeholder GPU entry (e.g.
  `model: "none"`); ship only the GPU reference family (attributed copies
  from `serving-contracts`) plus fleetlab-authored model/SLO profiles for
  the real CPU environment in `profiles/examples/`, and record the schema
  gap instead of a fake fixture. Consequences: `profiles/examples/` has no
  hardware profile paired with the Qwen2.5-1.5B model profile; FL-T004's
  fitting work (when it reaches CPU-measured data) will need either a
  schema change proposed to `serving-contracts` or a documented
  fitting-scope reduction. Conservative and reversible: no public contract,
  ownership, or milestone scope was changed by this session. Follow-up:
  raise a contract question with `serving-contracts` if/when FL-T004 needs
  a CPU hardware profile (per `docs/interfaces.md`: contract ambiguities
  are filed against `serving-contracts`, never patched locally).
- **2026-07-11 — KV-memory-per-token model cross-check against measured
  engine memory is recorded PENDING**, not fabricated as a pass. Evidence:
  no isolated KV-cache-memory measurement exists anywhere in the currently
  available evidence (checked llama.cpp's `/metrics`, every captured server
  log, and `/slots` poll data — see `docs/notes/model-validation.md` §5.2
  for the full account). Decision: ship the formula with full known-answer
  test coverage (including an exact match against an independently-authored
  real fixture) and record the measured-memory cross-check as an open item,
  per the task's explicit instruction to do so rather than fabricate.
  Consequences: FL-T003's stop condition ("cross-checks within stated error
  or honestly pending") is met via the "honestly pending" branch for this
  one cross-check; the other cross-checks in scope (Little's law,
  token-rate) passed exactly. Follow-up: closes when a measured,
  KV-isolated memory figure becomes available (see §5.2 for what that would
  take).
