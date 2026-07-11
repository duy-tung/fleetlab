# profiles/examples — fleetlab's example fleet profiles

Per `docs/architecture.md`, fleetlab owns its hardware/model/SLO/cost profiles
as versioned files with mandatory provenance. This directory holds the
bootstrap example set, two families:

## 1. GPU reference family (copied, attributed)

`hardware-a10g-g5-xlarge.json`, `model-llama31-8b.json`,
`slo-chat-interactive.json`, `cost-g5-xlarge-ondemand.json` are copied
verbatim from `serving-contracts examples/fleet/` (SC-T007) — they are
mutually cross-referencing (the cost rate and the SLO both reference the
hardware/model profile ids), source-reported/measured provenance, and are the
program's standard illustrative baseline (an A10G/g5.xlarge GPU node running
Llama-3.1-8B). Copied unmodified 2026-07-11 from bundle v0.2.0 (commit
484b449). They are non-normative fixtures owned by serving-contracts;
fleetlab treats them as read-only reference examples, not as fleetlab's own
measured facts.

## 2. Real, measured CPU/llama.cpp family (fleetlab-authored)

`model-qwen2.5-1.5b-instruct-gguf-q4km.json` and
`slo-scenario-b-llamacpp-cpu-shakedown.json` describe the model and SLO
actually behind `inference-lab/evidence/i3` (Scenario B): Qwen2.5-1.5B-Instruct,
GGUF Q4_K_M, served by llama.cpp (commit 8f114a9) on a 4-vCPU CPU-only host.
The model profile's architecture fields (layers, kv heads, head dim, context
length) were measured directly from the pinned GGUF's own metadata this
session (`gguf_dump.py` against the checkpoint sha256 recorded in the
profile). The SLO is a copy of the real measurement-derived SLO from that
evidence set (every objective's `provenance.basis` is `measured`).

### Known limitation: no hardware profile for the CPU-only host (recorded, not patched locally)

`hardware-profile.schema.json` requires a `gpu` block (`gpu.model`,
`gpu.count_per_node` >= 1, `gpu.vram_gb`) — it has no way to represent a
CPU-only host without fabricating a placeholder GPU entry. fleetlab does not
fabricate one: there is deliberately no `hardware-*.json` example for the
CPU-only host measured in `ib-t010`/`i3`. Per `docs/interfaces.md`, contract
ambiguities are filed against `serving-contracts`, never patched locally in
fleetlab. This is recorded as a deviation in `docs/implementation-notes.md`.
