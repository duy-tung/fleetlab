# Security — serving-contracts

A spec repository's security posture is about what its published artifacts may contain and what
its specs force consumers to (not) expose.

## No secrets or PII in fixtures — ever

- No secrets, API keys, tokens, or credentials in any fixture, example, schema default, or doc.
- No real user or tenant identifiers. Fixture identity values are obviously synthetic
  (e.g. `tenant_tier: "gold"`, `user: "fixture-user-01"`, request IDs like
  `req_fixture_0001`).
- No real prompts or model outputs containing personal data; fixture message content is
  synthetic and minimal.
- Release bundles are public artifacts; anything committed here must be publishable as-is.
  Review-gate check: scan fixtures for secret-shaped strings before every release.

## Cardinality policy doubles as a PII guard

`metrics/cardinality-policy.md` (Contract 2) forbids as metric labels: request IDs, raw
tenant/user IDs, prompts, and arbitrary strings. This is simultaneously a cardinality rule and a
PII rule — it structurally prevents personal data from entering the metrics pipeline, where
retention and access are broad. Per-request detail belongs in traces (access-controlled), linked
via exemplars.

## Error-envelope leak rules (normative for Contract 1)

The error-envelope spec MUST state, and fixtures MUST demonstrate, that error `message` values
never leak:

- internal addresses, hostnames, ports, or topology;
- stack traces or internal file paths;
- upstream credentials, auth headers, or connection strings;
- raw upstream error bodies (they are classified into the typed taxonomy —
  `upstream_error` / `upstream_timeout` — not passed through verbatim).

The request ID (`X-Request-Id`) is the correlation handle: enough for an operator to find full
detail in traces/logs, without the client-visible envelope carrying any of it.

## Deployment-contract secret expectations

Contract 5 descriptors name **what** secrets a deployment expects (name, mount/env location,
purpose) — never values, and never value formats that invite embedding real material in
examples. Example descriptors use placeholder secret names only.

## Repo hygiene

- No dependency surface: the repo depends on nothing beyond standard schema validators, which
  minimizes supply-chain exposure by construction.
- CI requires no privileged credentials (no GPU, no cloud); release publishing is the only
  credentialed operation.
- The validator kit must not read anything outside the files it is pointed at, and must not
  make network calls.
