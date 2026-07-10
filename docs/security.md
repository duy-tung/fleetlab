# fleetlab — Security

fleetlab's attack surface is small by construction — an offline CLI that reads declared files and writes declared files — and the security posture is to keep it that way.

## Input-file trust model

**All input files are untrusted data**, even when they come from sibling portfolio repos. Consequences:

1. **Schema validation before use.** Every input is validated against the pinned contract bundle before any model code touches it. Validation failures are typed, terminal errors (file/field/rule) — never warnings, never best-effort parses.
2. **No code execution from inputs.**
   - No `pickle` / `dill` / `shelve` anywhere — not for inputs, not for caches, not for outputs.
   - No `eval` / `exec` on any input-derived string.
   - YAML is loaded with `yaml.safe_load` only; JSON with the standard parser. No custom constructors/tags.
   - Profiles and manifests are pure data; nothing in an input can name a Python object, class, or import path that fleetlab will instantiate.
3. **Path handling confined to declared directories.** Input paths come from CLI arguments; any path *referenced inside* an input file (e.g. a result file linking its raw events) is resolved relative to its declaring file and must stay within the declared input roots — path traversal out of them is a refusal. Outputs go only to the declared output directory. No writes anywhere else, no input mutation ever (ingestion is read-only).
4. **Resource sanity on untrusted files.** Raw-event JSONL is processed as line-delimited records (bounded memory per record); absurd sizes or malformed lines fail with a named error rather than exhausting memory silently.

## No secrets

- fleetlab needs no credentials: no API keys, no tokens, no cloud access. There is nothing to configure and nothing to leak.
- Input files must not contain secrets; cost profiles carry *list prices with dates and sources*, not billing-account data. If a secret-looking field ever appears in a proposed schema, that is a contract question for serving-contracts.
- No secret material in logs, run records, or committed fixtures (nothing sensitive should exist to redact — the guard is review of fixtures before commit).

## No network at runtime

- fleetlab makes **zero network calls at runtime**. Contract bundles are vendored/pinned at a released tag, not fetched; inputs arrive as local files; outputs are local files.
- Dependency acquisition happens at development/CI install time only, with pinned versions (lockfile), never during a run.
- This is testable: a run under a no-network sandbox behaves identically, and any future change introducing runtime network use is a security-posture change that triggers the deviation-policy pause (user review required).

## Supply chain

- Minimal dependency set (ADR-0001), version-pinned with a lockfile; CI installs from the lockfile.
- CI needs no GPU and no privileged access; it runs pytest + `contracts-verify` against vendored fixtures.

## Threats explicitly out of scope

- Multi-user isolation, sandboxing of hostile operators: fleetlab runs with the invoking user's privileges on their own files; it is a local analysis tool, not a service.
- Confidentiality of results: outputs are meant to be published (with provenance); there is no sensitive-data handling path by design.
