# Real fixtures (not synthetic)

Every file under this directory is an unmodified copy of real evidence produced
by `inferbench` / `inference-lab` — never hand-edited, never used to fit a
profile in these tests (that is `fitting`'s job, FL-T004). They exist so the
golden-file suite proves fleetlab's ingestion actually ingests real program
output, not only hand-crafted fixtures.

| File(s) | Copied from | What it is |
|---|---|---|
| `workloads/chat-short.json`, `bursty.json`, `shared-prefix.json` | `inferbench/workloads/*.json` (canonical suite v1, IB-T003) | Real named workload manifests. |
| `runs/calib-A-mock/{manifest.json,events.jsonl}` | `inferbench/docs/evidence/ib-t004/calib-A/` | Real benchmark-run manifest + raw events, mock engine, gateway-mock topology. |
| `runs/chat-short-cpu-direct-llamacpp/{manifest.json,events.jsonl}` | `inference-lab/evidence/i3/raw/runs/chat-short-cpu-direct/` | Real benchmark-run manifest + raw events, llama.cpp engine (Qwen2.5-1.5B-Instruct GGUF Q4_K_M), engine-direct topology, CPU. |
| `results/ib-t005-calib-A.benchmark-result.json` | `inferbench/docs/evidence/ib-t005/results/` | Real benchmark result aggregated from `calib-A`. |
| `results/i3-chat-short-cpu-direct.benchmark-result.json` | `inference-lab/evidence/i3/raw/results/` | Real benchmark result, llama.cpp CPU run. |
| `capabilities/llamacpp.backend-capability.json` | `inference-lab/evidence/i3/raw/` | Real Contract-4 descriptor, probed against llama-server commit 8f114a9. |
| `slo/scenario-b-llamacpp-cpu-shakedown.slo.json` | `inference-lab/evidence/i3/raw/slo/` | Real, measurement-derived SLO (model-serving scope; every objective's provenance.basis is "measured"). |

Copied 2026-07-11. See `tests/golden/test_real_inferbench_ingest.py` for the
full-corpus sweep this subset is drawn from (walks the sibling repos directly
when present; this committed subset keeps the suite green without them).
