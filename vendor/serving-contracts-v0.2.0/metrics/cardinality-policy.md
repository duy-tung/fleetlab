# Cardinality Policy (Contract 2)

**Status:** normative. Companion to [`metrics.md`](metrics.md). This policy
bounds the label space of every canonical metric and doubles as a **PII
guard** (see `docs/security.md`): the same rules that keep time-series
cardinality low keep personal data and prompt content out of the metrics
pipeline.

---

## 1. Principle

Every label value set MUST be **enumerable from configuration at any point in
time** and low-cardinality. If you cannot list a label's legal values by
reading the gateway config plus this contract, the label is illegal.
Per-request detail belongs in **traces**, reachable from histograms via
**exemplars** (metrics.md §7) — never in labels.

## 2. Allowed labels

The complete allowed label set across all eleven canonical metrics:

| Label | Source of the value set | Expected cardinality |
|---|---|---|
| `model` | configured model IDs + `unknown` | ~1–20 |
| `backend` | configured backend IDs | ~1–10 |
| `tenant_tier` | configured tier names | ~2–5 |
| `status_class` | fixed: `2xx`, `4xx`, `5xx` | 3 |
| `error_class` | Contract 1 taxonomy + `none` | 11 |
| `reason` | fixed shed-reason list (metrics.md §3) | 4 |
| `stage` | fixed: `pre_first_token` | 1 |
| `direction` | fixed: `input`, `output` | 2 |

Rules:

- No canonical metric may gain a label outside this table without a contract
  release (additive enumerable label = MINOR; anything else = MAJOR).
- **Normalization at the edge:** client-supplied strings MUST be normalized
  before labeling. A model string that does not match a configured model ID
  is labeled `unknown` (and rejected per Contract 1), never echoed into the
  label.
- **Unknown-value fallback:** any label whose value cannot be resolved to its
  configured set at emit time MUST be recorded as `unknown`, not dropped and
  not passed through raw.

## 3. Cardinality budget

- Worst-case series count per metric = product of its label-set sizes; with
  the table above the worst case (`inference_requests_total`) is
  `models × backends × tiers × 3 × 11` — with the expected sizes above this
  stays in the low thousands. Config changes that would push any single
  metric past **10,000 active series** MUST be treated as an operational
  defect (alerting on it is inferops' job; the bound itself is contractual).
- Dashboards and alerts (inferops) MUST key only on labels in §2, so config
  growth — not relabeling — is the only cardinality driver.

## 4. Forbidden as label values (MUST NOT, ever)

- **Request IDs** (`X-Request-Id`) — belong in traces/logs/usage records.
- **Raw tenant IDs or user IDs** (including the API `user` field) — only the
  configured `tenant_tier` is a label.
- **Prompts, completions, or any fragment of either** — content never enters
  the metrics pipeline in any form (also a security/PII rule).
- **Arbitrary or client-controlled strings** — anything not enumerable from
  config: free-form error messages, upstream addresses, header values, model
  strings that failed normalization, file paths, stack frames.
- **Unbounded numerics** as strings (token counts, offsets, timestamps).
- **API keys, tokens, secrets** in any label or metric name (absolute).

If a value is needed for debugging, it goes on the trace (platform
attributes, metrics.md §6) or in logs keyed by request ID — the request ID
label is allowed **in traces only**.

## 5. Enforcement and drift

- **Emit-time guard (infergate):** the metrics layer rejects (or normalizes
  to `unknown`) any label value outside the configured sets; `go test` level
  conformance tests assert the full emitted label surface equals §2.
- **CI fixture check:** consumer compatibility tests validate dashboard/alert
  fixtures (inferops) and mirror definitions (inferbench) against the §2
  table; an undeclared label anywhere is a contract violation, not a style
  issue.
- **Scrape-side watchdog (inferops):** alert when any canonical metric's
  active-series count approaches the §3 budget.
- Changes to this policy follow the compatibility policy: relaxing a
  forbidden rule is MAJOR; adding an enumerable value to an existing set is
  MINOR; clarifications are PATCH.
