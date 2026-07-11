"""Cold-start / model-load delay, sourced from measured llama-server logs.

**Measured, not assumed.** `inference-lab/evidence/i3/logs/llama-server-
*.log` records llama.cpp's own `load_model: loading model` and
`llama_server: model loaded` timestamps for every server process started in
that evidence set (same checkpoint every time: Qwen2.5-1.5B-Instruct GGUF
Q4_K_M, sha256 `6a1a2eb6...`, same 4-vCPU CPU-only host). Two regimes appear,
both real:

| Log file | Elapsed (loading -> loaded) | Regime |
|---|---|---|
| `llama-server-calib.log` | 2.00 s | warm (OS page cache holds the weights file) |
| `llama-server-direct.log` | 2.10 s | warm |
| `llama-server-gw.log` | 2.11 s | warm |
| `llama-server-failover-1.log` | 1.68 s | warm |
| `llama-server-failover-2.log` | 1.71 s | warm |
| `attempt1-cancel/llama-server-cancel.log` | 2.03 s | warm |
| `llama-server-cancel.log` (final) | 88.06 s | **cold** (page cache evicted) |
| `llama-server-sharedprefix.log` | 94.62 s | **cold** |

The ~45x gap between regimes is disk-read-bound page-cache eviction, not
engine/GPU variance — `chat-short-cpu-calib/workload.json`'s own description
states the calibration run's purpose is partly "the warm-up that pages the
model into the OS cache before the measured arms," i.e. the harness's design
assumes a preceding warm-up call; the two ~90s outliers are the cases where
that assumption did not hold (a fresh process started without one).

`MEASURED_COLD_START` below is the module-level constant built from exactly
these eight real numbers (mean of each regime) — every field carries
`basis="measured"` and the log line each number came from.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class ColdStartProfile:
    warm_load_seconds: float
    cold_load_seconds: float
    basis: str
    source: str
    warm_samples_seconds: Tuple[float, ...]
    cold_samples_seconds: Tuple[float, ...]


# Exact per-log elapsed times (loading -> loaded), computed from the
# `load_model: loading model` / `llama_server: model loaded` line pair in
# each file under inference-lab/evidence/i3/logs/ (this session, 2026-07-11).
#
# llama.cpp's log timestamp format (reverse-engineered this session by
# cross-checking against real wall-clock deltas in the paired events.jsonl
# files, since it is undocumented): `MM.SS.mmm.uuu` -- elapsed
# minutes.seconds.milliseconds.microseconds since process start, where MM is
# NOT capped at 59 (it keeps counting up rather than rolling into an hours
# field: the gw run's final log line, `10.09.254.080`, is 10 min 9.254080 s
# = 609.25 s elapsed, matching that run's real ~600-610 s wall-clock
# duration from its events.jsonl timestamps). elapsed_seconds = MM*60 + SS +
# mmm/1000 + uuu/1e6.
_WARM_SAMPLES = (
    2.000140,  # llama-server-calib.log:      0.00.005.145 -> 0.02.005.285
    2.097744,  # llama-server-direct.log:     0.00.005.731 -> 0.02.103.475
    2.112835,  # llama-server-gw.log:         0.00.005.020 -> 0.02.117.855
    1.678534,  # llama-server-failover-1.log: 0.00.004.882 -> 0.01.683.416
    1.705316,  # llama-server-failover-2.log: 0.00.004.482 -> 0.01.709.798
    2.029209,  # attempt1-cancel/llama-server-cancel.log: 0.00.005.051 -> 0.02.034.260
)
_COLD_SAMPLES = (
    88.057178,  # llama-server-cancel.log (final):  0.00.005.505 -> 1.28.062.683
    94.624432,  # llama-server-sharedprefix.log:    0.00.016.356 -> 1.34.640.788
)

MEASURED_COLD_START = ColdStartProfile(
    warm_load_seconds=sum(_WARM_SAMPLES) / len(_WARM_SAMPLES),
    cold_load_seconds=sum(_COLD_SAMPLES) / len(_COLD_SAMPLES),
    basis="measured",
    source=(
        "inference-lab/evidence/i3/logs/llama-server-{calib,direct,gw,"
        "failover-1,failover-2}.log + attempt1-cancel/llama-server-cancel.log "
        "(warm regime, OS page cache holds the weights); "
        "inference-lab/evidence/i3/logs/llama-server-cancel.log (final) + "
        "llama-server-sharedprefix.log (cold regime, page cache evicted); "
        "llama.cpp commit 8f114a9, qwen2.5-1.5b-instruct-q4_k_m.gguf, "
        "same 4-vCPU CPU-only host throughout"
    ),
    warm_samples_seconds=_WARM_SAMPLES,
    cold_samples_seconds=_COLD_SAMPLES,
)
