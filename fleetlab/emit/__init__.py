"""fleetlab.emit -- Contract-7 (capacity-recommendation) emitter (FL-T009).

`topology.py`: closed-form replica-count/goodput/uncertainty arithmetic.
`recommendation.py`: assembles + validates + writes a Contract-7 document.
`build_recommendation.py`: wires the two together into the real recommendation
this repo's evidence supports (the ib-t010 E2 "5x overload" scale-out case).
`dry_run_validate.py`: the consumption-side validation script inferops will
run once its runtime environment decision (RQ-14) unblocks -- see
`docs/implementation-notes.md`.
"""

from .recommendation import (
    build_capacity_recommendation,
    latency_bracket_from_benchmark_results,
    predicted_quantity,
    validate_recommendation,
    write_recommendation,
)
from .topology import (
    GoodputUncertainty,
    fleet_capacity_rps,
    goodput_uncertainty,
    predicted_goodput_rps,
    recommend_replica_count,
)

__all__ = [
    "build_capacity_recommendation",
    "latency_bracket_from_benchmark_results",
    "predicted_quantity",
    "validate_recommendation",
    "write_recommendation",
    "GoodputUncertainty",
    "fleet_capacity_rps",
    "goodput_uncertainty",
    "predicted_goodput_rps",
    "recommend_replica_count",
]
