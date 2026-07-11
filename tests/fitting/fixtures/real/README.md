# Real fixtures for FL-T004 (fitting)

Two corpora, both unmodified copies of real inferbench evidence — see
`reports/holdout-validation.md` for the full account and
`docs/notes/fitting-method.md` for the corpus inventory (including the
corrected scope: `ib-t008/` was missing from the original task brief's
corpus list and was added in a same-day follow-up).

## `ib-t008/` — the six-point rate sweep (IB-T008)

The sweep the corrected brief describes: 6 offered rates at 10%–120% of a
probe-estimated capacity (27.79 rps), 3 repetitions each (150 requests/rep),
mock backend behind the gateway (`flags-v1`, dev@74f2372) with a **disclosed
client-transport concurrency cap of 2** (see `sweep/sweep.json`'s
`concurrency_cap_note` — the cap models a capacity-limited target and is part
of the fitted profile's engine-config identity, `gateway-mock-flags-v1-
conncap2`). `knee-result.json` is inferbench's own knee detection: knee at
sweep point 3's declared rate (21.122 rps), confidence 0.8, `ttft_seconds_p99`
plateau-departure signal.

| File(s) | Copied from | What it is |
|---|---|---|
| `sweep/sweep.json` | `inferbench/docs/evidence/ib-t008/sweep/sweep.json` | Sweep manifest: probe result, per-point rates/run dirs, the concurrency-cap disclosure. |
| `knee-result.json`, `sweep-base.json` | `inferbench/docs/evidence/ib-t008/` | Knee-detection output; the base workload the per-point workloads are derived from. |
| `sweep/point-{0..5}-workload.json` | same dir | Per-point workloads (declared `rate_rps` per point; the events' empirical scheduled rate runs a uniform 7.46% above it — see `fleetlab/fitting/corpus.py::load_corpus_point_from_events`). |
| `sweep/point-{0..5}/rep-{1..3}/{events.jsonl,manifest.json}` | same dirs | The 18 kit-valid raw-event files + run manifests the corpus points are computed from. `reference.json`/`run.log` files are not copied (not consumed by fitting). |

The probe run's raw events are also not copied — `sweep.json` records the
probe's method and result, which is all the fitted profile cites.

## `ib-t010/` — the two-point capacity-boundary arms (IB-T010)

Gateway configs `admission-sane-v1` / `admission-sane-v1b`, two offered-rate
points each ("1x" / "5x") — the corpus FL-T004's original G8 evaluation used
before the sweep's location was corrected.

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
