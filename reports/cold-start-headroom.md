# Cold-start headroom report (FL-T005)

Raw scenario outputs (seeded, with input digests):
`reports/scenarios/bursty-queue-growth.json`,
`reports/scenarios/cold-start-headroom.json`, regenerated deterministically
by `python3 -m fleetlab.dynamics.build_scenarios`. Simulator implementation
and known-answer tests: `fleetlab/dynamics/`, `tests/dynamics/`.

## 1. Queue growth under the `bursty` workload

Real canonical workload `bursty` (`tests/golden/fixtures/real/workloads/
bursty.json`, sha256 `378c3e82...`): 60s at 2 rps, then a 15s burst at 20
rps (10x amplitude), repeating for 600s. Long-run average offered rate:
**5.6 rps** (`(2*60 + 20*15) / 75`).

Two single-server scenarios (seed `20260711`), same arrivals, different
service rate:

| Scenario | Service rate | Stable overall? | Max in-system | Mean wait (admitted) |
|---|---|---|---|---|
| `provisioned_mu8` | 8 rps | **yes** (8 > 5.6 average) | 192 | 9.3 s |
| `underprovisioned_mu3` | 3 rps | **no** (3 < 5.6 average) | 1639 (still climbing) | 259.2 s |

**Finding:** provisioning for the *peak* burst rate is not the question —
provisioning for the *long-run average* (5.6 rps here) determines whether
the queue is stable at all. `provisioned_mu8` shows the queue spike sharply
during each burst and drain back down within the following 60s baseline
window (`tests/dynamics/test_simulator.py::
test_burst_decay_back_to_steady_state_after_the_burst_ends` asserts this
structurally: every pre-burst sample stays below half the run's peak
in-system count). `underprovisioned_mu3` — service rate below the long-run
average — never recovers: in-system count is still climbing at the end of
the 600s run (847 at t=300s, 1463 at t=590s), exactly the λ>μ linear-growth
limit (`tests/dynamics/test_simulator.py::
test_unstable_queue_grows_linearly_when_lambda_greater_than_mu`).

## 2. Cold-start delay: measured, not assumed

llama.cpp model-load timing, extracted directly from
`inference-lab/evidence/i3/logs/llama-server-*.log` (same checkpoint,
Qwen2.5-1.5B-Instruct GGUF Q4_K_M, same 4-vCPU CPU-only host throughout;
the log's own elapsed-time format, `MM.SS.mmm.uuu`, was reverse-engineered
this session and cross-checked against real wall-clock deltas in the paired
`events.jsonl` files — see `fleetlab/dynamics/cold_start.py`'s module
docstring for the full derivation):

| Regime | Mean elapsed (loading -> loaded) | Samples |
|---|---|---|
| **warm** (OS page cache holds the weights) | **1.94 s** | 6 real runs |
| **cold** (page cache evicted) | **91.34 s** | 2 real runs |

The ~47x gap is disk-read-bound page-cache eviction on this host, not
engine or GPU variance (`fleetlab/dynamics/cold_start.py` cites the exact
log lines). This is the one delay parameter in FL-T005 with a real,
measured basis; `MEASURED_COLD_START.basis == "measured"` is asserted by
`tests/dynamics/test_cold_start.py`.

**Scale-up/down lag: no measured basis exists in this program's evidence
yet** — a full-corpus search (`scale up`, `scale-up`, `replica`, `cooldown`,
`autoscal*`) across `ib-t010`/`ib-t004`/`ib-t005`/`i3` found zero matches;
every run in the available evidence is a single engine process, never a
multi-replica fleet. `ASSUMED_SCALING_DELAY` (`fleetlab/dynamics/
scaling.py`) is therefore explicitly `basis="assumed"`: scale-up = an
assumed 10s Kubernetes pod-scheduling constant + the measured warm-load
time (11.94s total); scale-down = an assumed 30s graceful-drain/termination
grace period. Both are flagged, never presented as measured
(`tests/dynamics/test_scaling.py` asserts the flag). This closes when
inferops IO-T009 produces real replica-scaling timing data.

## 3. N-1 failover headroom (planning-prompt hypothesis 3)

Combines FL-T004's fitted capacity with a replica count and the `bursty`
workload's peak offered rate (20 rps).

### 3a. Real measured capacity (mock backend, 2 replicas)

Per-replica capacity **33.16 rps** (`profiles/fitted/mock-loopback-cpu-dev__
mock-8b__gateway-mock-admission-sane-v1.json`, FL-T004's fitted, holdout-
validated profile). N-1 (1 surviving replica) capacity = 33.16 rps, still
comfortably above the bursty peak (20 rps). **Finding: no headroom deficit**
for this specific (measured mock capacity, this workload) pairing — losing
one of two replicas is not a cold-start risk here. This is a real, honest
negative result: the hypothesis that cold-start headroom dominates is not
automatically true, it depends on the actual capacity-vs-peak-load ratio,
which for this measured mock config is favorable.

### 3b. Illustrative scenario (assumed capacity, chosen to demonstrate the mechanism)

To show the mechanism actually binding, `per_replica_capacity_rps = 15`
(explicitly flagged `ASSUMED`, illustrative only — deliberately chosen
below the bursty peak, **not** a measured value for any real or mock
hardware). 2 replicas, N-1 capacity = 15 rps < peak (20 rps) -> deficit = 5
rps.

| Replacement | Cold-start window | Backlog accrued | Drain time |
|---|---|---|---|
| **warm** (page cache hit) | 11.94 s | 59.7 requests | 6.0 s |
| **cold** (page cache evicted) | 101.34 s | 506.7 requests | 50.7 s |

**Finding:** holding steady-state capacity and offered load completely
fixed, only the cold-start window changes (warm vs cold reload) — and the
resulting backlog and drain time scale by the *same* ~8.5x factor. This is
direct, mechanistic support for planning-prompt hypothesis 3: **required
headroom is set by warm-up time x deficit rate, not steady-state
throughput** — the steady-state capacity numbers here (15 rps per replica,
30 rps fleet) never change between the two rows; only the warm-vs-cold
model-load time does, and it alone drives an 8.5x difference in operational
consequence (a 6s hiccup vs a 51s backlog to drain).

## 4. What this report does not claim

- Section 3a's "no deficit" finding is specific to the **mock backend**
  capacity and the **bursty** workload's specific peak (20 rps) — it is not
  a general claim that cold-start headroom never matters. Section 3b shows
  the same mechanism producing a real, non-trivial deficit and drain time
  once capacity is lower relative to peak load.
- The illustrative 15 rps capacity in §3b is **not** measured — it is
  chosen specifically to be below the bursty peak so the mechanism is
  visible; do not read it as a claim about any real hardware.
- Scale-up/down lag figures are **assumed**, not measured (§2) — any
  recommendation downstream that depends on the exact 10s/30s constants
  should be revisited once inferops IO-T009 produces real data.
