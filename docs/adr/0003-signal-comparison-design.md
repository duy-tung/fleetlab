# ADR-0003 — Signal-comparison design (FL-T006)

- **Status:** Accepted
- **Date:** 2026-07-11
- **Deciders:** fleetlab implementer

## Context

FL-T006 compares six candidate autoscaling signals (`cpu_utilization`,
`gpu_utilization`, `queue_depth`, `in_flight_requests`, `token_arrival_rate`,
`predicted_goodput_deficit`) across workloads, with a mandatory "fairness of
comparison" review focus (`docs/tasks.md`): same workloads, same SLOs, same
tuning effort per signal. This ADR records the concrete design that makes
that fairness structural rather than a claim in prose, per ADR-0001's
planned follow-up.

Three decisions carried the most risk of quietly favoring one signal over
another, and are recorded here.

## Decision 1 — one shared ground-truth system, not per-signal assumptions

`fleetlab/signals/ground_truth.py` loads exactly one FL-T004 fitted profile
(`mock-loopback-cpu-dev__mock-8b__gateway-mock-flags-v1-conncap2`, the only
one of the three fitted profiles whose G8 outcome is **within stated error**
— the two `admission-sane-v1`/`v1b` profiles are a documented MISS and are
never used as ground truth here) and derives `num_servers` (from the
disclosed concurrency cap) and `mean_service_time_seconds` (`num_servers /
capacity_rps`) exactly once. Every scenario in this task uses this same
topology and service-time distribution; only the *arrival* process differs
per workload. `load_ground_truth_system` raises if pointed at a profile
whose G8 outcome is not the within-error one, or whose latency status is
not `FITTED` — a structural guard against silently downgrading the ground
truth in a future edit.

`mean_service_time_seconds` is deliberately derived from the fitted
`capacity_rps` (the G8-passing half of the profile), not from the fitted
`l0_seconds` latency parameter — `l0`'s own documented functional-form
misfit (`docs/notes/fitting-method.md` §4: the target latency is additive,
the one-parameter model is multiplicative) would otherwise be compounded
into a second task's ground truth.

## Decision 2 — one shared tuning/detection procedure, only the threshold value differs per signal

`fleetlab/signals/detection.py` applies exactly the same four parameters to
every signal in every scenario: `THRESHOLD_K=3.0` (threshold = baseline
mean + k·std over a scenario-specific quiet calibration window),
`DEBOUNCE_SECONDS=5.0` (a signal must sustain a crossing continuously for
5s to fire — guards against single-sample noise), `CLEAR_FRACTION=0.7`
(hysteresis band to clear), and `WINDOW_SECONDS=10.0` (the trailing-window
length shared by the two windowed signals, `token_arrival_rate` and
`predicted_goodput_deficit`). Nothing is hand-tuned per signal. Where this
rule produces a degenerate result — e.g. a threshold whose baseline
variance floors near zero (`queue_depth`, `predicted_goodput_deficit` are
both exactly 0 at every quiet baseline sample) or, more strikingly, a
threshold that exceeds the signal's own physical maximum
(`cpu_utilization`/`gpu_utilization`'s `mean + 3·std` exceeds 1.0 in three
of four scenarios, because a 2-server system's busy-fraction reading is
discretized to {0, 0.5, 1.0} rather than continuous, giving it
disproportionate variance for its mean) — that result is reported as a
genuine finding about the signal, not smoothed away by giving that one
signal a bespoke tuning rule. Fairness here means "same recipe," not "same
outcome."

Detection lag and flapping are scored against the **known phase schedule**
of each workload (exact, not estimated — the simulation's own construction
gives the true burst start/end times and the true declared rate), never
against another signal's reading. This avoids the circularity of scoring
one signal relative to another "reference" signal.

## Decision 3 — a real near-saturation scenario plus one explicitly-labeled illustrative hard-overload scenario

The real `bursty` workload (IB-T003 canonical fixture,
`tests/golden/fixtures/real/workloads/bursty.json`: 60s@2rps + 15s@20rps,
repeating) never exceeds the fitted ground-truth capacity (26.16 rps) even
at its 20 rps burst peak (76.5% utilization) — a near-saturation stress
test, not a hard capacity breach. Rather than force an artificial breach
into the real fixture (which would misrepresent measured data) or claim a
detection-lag result the real corpus cannot support, this task adds a
second, clearly-labeled scenario, `bursty-illustrative-severe`
(`basis="assumed"`): the real cycle's own phase durations, baseline rate,
and length/cancellation distributions are re-derived programmatically from
the same file, with only the burst phase's rate multiplied by a fixed,
disclosed `ILLUSTRATIVE_BURST_MULTIPLIER=1.6` (20 → 32 rps) so it clearly
exceeds capacity. This is the same pattern `fleetlab/dynamics/
build_scenarios.py` already established for FL-T005's cold-start-headroom
report (a real/measured scenario alongside one explicitly-labeled
illustrative scenario demonstrating the mechanism the real data cannot
reach) — reused here rather than inventing a new convention.

## Consequences

- Positive: the fairness claim is checked by code (`tests/signals/
  test_build_signal_comparison.py::
  test_cpu_and_gpu_utilization_are_the_identical_proxy_series` and the
  shared-constant design itself), not just asserted in the report prose;
  the ground-truth guard (Decision 1) prevents a future edit from silently
  swapping in a MISS profile.
- Negative / accepted costs: a single uniform tuning rule is not the best
  possible tuning for every signal (a signal-specific tuning heuristic could
  likely "fix" utilization's unreachable-threshold problem) — deliberately
  not done, because doing so would relitigate the fairness protocol per
  signal, defeating its purpose.
- The real corpus provides only one true-overload-free burst scenario;
  `bursty-illustrative-severe` is not a measured result and every report
  referencing it says so.

## Planned follow-up

None required by this task; a future revisit trigger would be a real
multi-replica autoscaling dataset from `inferops` IO-T009, which would let
detection-lag scoring use a measured scale-up delay instead of the FL-T005
assumed one.
