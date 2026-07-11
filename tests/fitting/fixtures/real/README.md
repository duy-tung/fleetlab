# Real fixtures for FL-T004 (fitting)

Every file under `ib-t010/` is an unmodified copy of real evidence produced by
`inferbench` (IB-T010: sweep design + saturation-boundary probes, gateway
config `admission-sane-v1` / `admission-sane-v1b`). They are the entire real
corpus this repo's holdout validation is fit and scored against — see
`reports/holdout-validation.md` for the full account, and
`docs/notes/fitting-method.md` for why this is the whole usable corpus (no
other engine-config in the available evidence has more than one offered-rate
data point).

| File(s) | Copied from | What it is |
|---|---|---|
| `e2-baseline-workload.json` | `inferbench/docs/evidence/ib-t010/e2-baseline-workload.json` | The workload actually used to drive both `e2-baseline` and `e2b-baseline` (offered rate 37.8072 rps, ~1x the probe-estimated capacity). |
| `e2-overload-workload.json` | `inferbench/docs/evidence/ib-t010/e2-overload-workload.json` | The workload driving both `e2-overload` and `e2b-overload` (189.0362 rps, 5x). |
| `e1-mock-workload.json`, `e1-llamacpp-workload.json` | same dir | Single-rate workloads for the E1 overhead arms (6 rps mock, 0.4 rps llama.cpp) — each engine-config has only this one rate point, insufficient to fit or holdout-validate a profile; kept here only so the coverage/insufficient-data story in the report is checkable against real files. |
| `results/ib-t010-e2-baseline-1x-sane.benchmark-result.json`, `...-e2-overload-5x-sane...`, `...-e2b-baseline-1x-sane...`, `...-e2b-overload-5x-sane...` | `inferbench/docs/evidence/ib-t010/results/` | The four real benchmark results FL-T004's fitted profiles and holdout validation are built from. |
| `results/ib-t010-e1-{mock,llamacpp}-{direct,gateway}.benchmark-result.json` | same dir | The four single-point E1 overhead-arm results (documented as insufficient data, not fitted). |
| `e2-baseline/manifest.json`, `e2-overload-compare/sane/manifest.json`, `e2b-baseline/manifest.json`, `e2b-overload/manifest.json` | `inferbench/docs/evidence/ib-t010/{e2-baseline,e2-overload-compare/sane,e2b-baseline,e2b-overload}/rep-1/manifest.json` | One representative repetition's run manifest per config (repetitions share engine/gateway/hardware identity; only `rep-1` is needed to establish engine-config identity and cross-check the `workload_ref`). |
| `e1-mock-compare/{direct,gateway}/manifest.json`, `e1-llamacpp-compare/{direct,gateway}/manifest.json` | same pattern | Manifests for the four insufficient-data E1 points. |

Copied 2026-07-11. Per-repetition raw event files are **not** copied here —
`fleetlab.fitting.corpus.CorpusPoint.achieved_rate_stderr_rps` derives a
measurement-error bar from the pooled `benchmark-result.json`'s own
`total_requests` (Poisson-counting statistic), so no raw per-request data is
needed to reproduce the error bars in `reports/holdout-validation.md`.
