# Consumer compatibility kit (SC-T008)

This directory ships **inside the released contract bundle**. It is the mechanism behind
milestone I1: every consumer repo (`infergate`, `inferbench`, `fleetlab`, `inferops`) runs it in
CI against a **pinned release** of the bundle — never against a source checkout of
`serving-contracts`.

The kit is **validation-only**: one CLI (`contracts-validate.py`) wrapping the standard
python-jsonschema validator (JSON Schema 2020-12, ADR-0002), plus one configuration file
(`validation-map.json`) carrying the fixture-path→schema mapping (ADR-0004). No client library,
no code generation, no shared helpers — the moment those appear, the ownership matrix is
violated.

## Requirements

- Python ≥ 3.9
- `pip install -r kit/requirements.txt` (`jsonschema>=4.18`, `PyYAML>=6` — PyYAML is only
  exercised when validating against `api.*` schemas, which are sourced from
  `openapi/inference-api.yaml`)

## Commands

```text
python3 kit/contracts-validate.py [--bundle DIR] [--json] <command>

  list-schemas                      list schema names available in this bundle
  validate --schema NAME FILE...    validate files against one named schema
  selftest [--verbose]              golden-fixture sweep: every positive fixture MUST
                                    validate, every fixture under invalid/ MUST fail
  check DIR [--schema NAME]         validate a directory of consumer-emitted artifacts
        [--ignore-unmatched]        (schema auto-detected from the artifact name)
```

- `--bundle DIR` points at the bundle root; the default is the bundle this kit ships in, so
  inside an unpacked release no flag is needed.
- Artifact kinds: `.json` (one instance), `.jsonl` (one instance per line), `.sse`
  (SSE transcript — see below).

### Schema names

File schemas are auto-discovered from `schemas/*.schema.json` (name = filename stem, e.g.
`workload`, `benchmark-run`, `raw-event`, `benchmark-result`, `backend-capability`). API shapes
are exposed as `api.*` names resolved into `openapi/inference-api.yaml` components
(`api.chat-completion-request`, `api.chat-completion-response`, `api.chat-completion-chunk`,
`api.error-response`, `api.models-response`, `api.stream-event`). Run `list-schemas` — never
hardcode the list: **the schema set grows across releases** (deployment + fault-scenario schemas
land at SC-T006; hardware/model/SLO/cost + capacity-recommendation at SC-T007) and new schemas
appear automatically with no kit change.

### Artifact naming convention (`check` auto-detection)

Name emitted artifacts `<anything>.<schema>.json` or `<anything>.<schema>.jsonl`, e.g.
`run-20260710-a.benchmark-run.json`, `run-20260710-a.raw-event.jsonl`,
`nightly.benchmark-result.json`, `a100.hardware-profile.json`. Files whose schema cannot be
detected make `check` exit 2 (pass `--schema` to force one schema for the whole directory, or
`--ignore-unmatched` to skip them). `.sse` files map to `api.stream-event` by convention.

### Exit codes (stable; CI gates on them)

| Code | Meaning |
|---|---|
| 0 | everything validated as required (selftest: positives green AND negatives failed) |
| 1 | validation failure — a positive/artifact failed, or an `invalid/` fixture passed |
| 2 | usage/config/environment error (unknown schema, missing bundle, missing dependency) |

### Machine-readable output

`--json` emits a single JSON summary object on stdout (human progress moves to stderr):

```json
{
  "kit": "serving-contracts-compatibility-kit",
  "summary_format": 1,
  "command": "selftest",
  "bundle": "/path/to/bundle",
  "ok": true,
  "exit_code": 0,
  "counts": { "positives_total": 32, "positives_passed": 32,
              "negatives_total": 20, "negatives_failed_as_required": 20,
              "schemas_meta_validated": 5 },
  "failures": []
}
```

`summary_format` changes only per the compatibility policy (a bump is breaking for CI parsers).

### SSE transcripts (`.sse`) — kit scope decision

The kit performs **lightweight** validation of SSE fixtures: framing (only
`id:`/`data:`/`event:`/`retry:`/comment/blank lines) and every embedded `data:` JSON payload
validated against `api.stream-event` (oneOf chunk | error envelope), with `data: [DONE]`
accepted as the terminal sentinel. Ordering, monotonic `id` sequencing, flush behaviour,
usage-in-final-chunk, termination and cancellation semantics are **gateway-conformance testing**
(infergate's own test suite drives the transcripts through a live gateway) — deliberately out of
kit scope. The transcripts remain contract fixtures either way.

## Wiring the kit into a consumer repo (all four follow the same shape)

1. **Pin** the bundle tag (e.g. `v0.1.0`) in CI config, and record the pin in the
   `inference-lab` pins file.
2. **Fetch** the pinned release at CI time — never a source checkout, e.g.:
   ```sh
   curl -fsSL -o bundle.tar.gz \
     https://github.com/<org>/serving-contracts/archive/refs/tags/${CONTRACTS_VERSION}.tar.gz
   tar xzf bundle.tar.gz && mv serving-contracts-* contracts-bundle
   pip install -r contracts-bundle/kit/requirements.txt
   ```
3. **Self-test the bundle** (proves the fetched fixture set is intact and the validator can
   fail): `python3 contracts-bundle/kit/contracts-validate.py selftest`
4. **Validate emitted artifacts**: `check` on the directory your build/tests emit into.
5. **Validate accepted inputs**: your test suite feeds the golden fixtures under
   `contracts-bundle/examples/` to your own code — positives must be accepted, `invalid/`
   fixtures must be rejected. (The kit ships the fixtures; asserting your code's accept/reject
   behaviour is your test suite's job.)
6. **Report** the bundle tag in CI output (I1 evidence references one tag across all four
   consumers). Indicative wrapper target: `make contracts-verify`.

### infergate

Validates **API conformance inputs** and, later, its **emitted deployment descriptor**.

```sh
python3 contracts-bundle/kit/contracts-validate.py selftest
# gateway conformance tests (infergate's own suite):
#   - send examples/api/chat-completion-request*.json → must be accepted
#   - send examples/api/invalid/request-*.json → must be rejected with the typed error
#     (error envelopes assertable against schema api.error-response)
#   - emitted/relayed responses, chunks and error envelopes dumped by tests:
python3 contracts-bundle/kit/contracts-validate.py check test-output/ --ignore-unmatched
# capability descriptors its adapters declare/parse:
python3 contracts-bundle/kit/contracts-validate.py validate --schema backend-capability \
  adapters/testdata/*.json
# from SC-T006 (deployment-contract schema in the bundle): the per-release descriptor it publishes
python3 contracts-bundle/kit/contracts-validate.py validate --schema deployment-contract \
  release/infergate.deployment-contract.json
```

SSE ordering/flush/cancellation semantics: infergate's conformance suite, not the kit (above).

### inferbench

Validates everything it **emits** (schema-affecting changes are released here first — never in
inferbench) and the workload fixtures it must parse.

```sh
python3 contracts-bundle/kit/contracts-validate.py selftest
# generator must parse the 8 named workload fixtures: examples/workloads/*.json
# every emitted artifact, named per the convention:
#   out/run-<id>.benchmark-run.json, out/run-<id>.raw-event.jsonl,
#   out/run-<id>.benchmark-result.json, out/<name>.workload.json
python3 contracts-bundle/kit/contracts-validate.py --json check out/
```

### fleetlab

Validates **consumed profiles** and **emitted recommendations**. The hardware/model/SLO/cost
and capacity-recommendation schemas arrive at SC-T006/T007; the kit discovers them automatically
once the pinned bundle contains them — wire the commands now, they start covering the new
schemas on the first bundle bump that ships them.

```sh
python3 contracts-bundle/kit/contracts-validate.py selftest
# inputs it accepts (benchmark results / raw events produced elsewhere):
python3 contracts-bundle/kit/contracts-validate.py check input-artifacts/
# profiles it maintains (once SC-T007 schemas are in the pinned bundle):
#   profiles/a100.hardware-profile.json, profiles/llama70b.model-profile.json,
#   profiles/gw.slo.json, profiles/aws.cost-profile.json
python3 contracts-bundle/kit/contracts-validate.py check profiles/
# recommendations it emits (Contract 7):
python3 contracts-bundle/kit/contracts-validate.py validate --schema capacity-recommendation \
  out/*.capacity-recommendation.json
```

### inferops

Deployment and fault-scenario contracts land at SC-T006; until then inferops wires the
self-test plus the capability fixtures it uses for probe configuration. Metric/dashboard names
are keyed from `metrics/metrics.md` (a document, not a schema — no kit validation).

```sh
python3 contracts-bundle/kit/contracts-validate.py selftest
# probe configuration source (capability descriptors):
python3 contracts-bundle/kit/contracts-validate.py validate --schema backend-capability \
  contracts-bundle/examples/capabilities/*.json
# from SC-T006 in the pinned bundle:
#   deployment descriptors it consumes and fault scenarios it injects from
python3 contracts-bundle/kit/contracts-validate.py check deploy-inputs/   # *.deployment-contract.json
python3 contracts-bundle/kit/contracts-validate.py check fault-catalog/   # *.fault-scenario.json
```

## Maintaining the kit (this repo only)

- New schema file in `schemas/` → auto-discovered; add fixture rules to `validation-map.json`
  when its `examples/` area lands (rules for the ADR-0004 areas `deployment/`, `faults/`,
  `capacity/`, `fleet/` are pre-seeded and inert until fixtures exist — adjust at SC-T006/T007).
- `selftest` fails on any fixture not matched by a rule, any positive that fails, any
  `invalid/` fixture that passes, and any negative missing its `.reason.txt` (ADR-0004).
- Exit codes, the artifact naming convention, and `summary_format` are contract surface once
  released: changes follow `compatibility/compatibility-policy.md`.
