"""fleetlab.signals -- autoscaling-signal comparison (FL-T006).

Evaluates six candidate scaling signals -- `cpu_utilization`,
`gpu_utilization`, `queue_depth`, `in_flight_requests`, `token_arrival_rate`,
`predicted_goodput_deficit` -- against seeded `fleetlab.dynamics` G/G/c
simulations of three workloads (`chat-short`, `mixed`, `bursty`), using the
FL-T004 fitted (G8-within-error) capacity/latency profile as ground truth
for the simulated system's own capacity. See `docs/adr/0003-signal-
comparison-design.md` for the fairness protocol and
`reports/autoscaling-signals.md` for the published comparison.

Modules:
- `ground_truth`: loads the fitted profile and derives G/G/c parameters.
- `series`: per-signal time series from a completed `QueueTrace`.
- `detection`: threshold tuning (identical procedure for every signal) +
  debounced/hysteresis-banded event detection, scored against ground-truth
  phase schedules (never against another signal).
- `build_signal_comparison`: orchestrates the seeded scenario runs and
  writes `reports/scenarios/autoscaling-signals.json`.
"""

from .ground_truth import GroundTruthSystem, load_ground_truth_system
from .series import (
    in_flight_series,
    in_service_count_series,
    offered_request_rate_series,
    predicted_goodput_deficit_series,
    queue_depth_series,
    token_arrival_rate_series,
    utilization_series,
)
from .detection import (
    ThresholdTuning,
    TriggerEvent,
    count_events_in_window,
    detect_events,
    first_detection_lag_seconds,
    true_overload_windows,
    tune_threshold,
)

__all__ = [
    "GroundTruthSystem",
    "load_ground_truth_system",
    "in_flight_series",
    "in_service_count_series",
    "offered_request_rate_series",
    "predicted_goodput_deficit_series",
    "queue_depth_series",
    "token_arrival_rate_series",
    "utilization_series",
    "ThresholdTuning",
    "TriggerEvent",
    "count_events_in_window",
    "detect_events",
    "first_detection_lag_seconds",
    "true_overload_windows",
    "tune_threshold",
]
