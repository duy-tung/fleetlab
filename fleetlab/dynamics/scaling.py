"""Scale-up/down lag — **ASSUMED**, explicitly flagged, per FL-T005's review
focus ("delay parameters sourced ... not invented; assumed parameters
explicitly flagged").

A full-corpus search (`docs/notes/fitting-method.md`-style sweep, this
session) of `inferbench/docs/evidence/{ib-t010,ib-t004,ib-t005}` and
`inference-lab/evidence/i3` for `scale up`, `scale-up`, `replica`,
`cooldown`, `autoscal*` found **zero matches** — every run in the available
evidence is a single engine process behind at most one gateway instance;
there is no multi-replica or autoscaler-timing data anywhere in this
program's evidence yet (that is `inferops` IO-T009's job). `ScalingDelay`'s
numbers below are therefore `basis="assumed"`, not `"measured"`, and are
deliberately conservative, round, order-of-magnitude figures with a stated
rationale — never presented as measured.
"""

from __future__ import annotations

from dataclasses import dataclass

from .cold_start import MEASURED_COLD_START


@dataclass(frozen=True)
class ScalingDelay:
    scale_up_seconds: float
    scale_down_seconds: float
    basis: str
    rationale: str


# Composition (documented, not hidden): scale-up = [assumed] scheduler +
# image-already-present container start, PLUS [[measured]] model load. The
# scheduling constant is a commonly-cited Kubernetes pod-scheduling-to-
# running order of magnitude for an already-pulled image on a warm node
# (assumed here -- no inferops evidence exists yet to measure it in this
# program); the model-load term reuses MEASURED_COLD_START's warm-cache
# figure, since a newly scheduled replica on a node that has recently run
# the same model is the common case this simulator's burst scenarios use.
_ASSUMED_K8S_SCHEDULE_SECONDS = 10.0
_ASSUMED_DRAIN_GRACE_SECONDS = 30.0  # graceful in-flight drain + termination grace period

ASSUMED_SCALING_DELAY = ScalingDelay(
    scale_up_seconds=_ASSUMED_K8S_SCHEDULE_SECONDS + MEASURED_COLD_START.warm_load_seconds,
    scale_down_seconds=_ASSUMED_DRAIN_GRACE_SECONDS,
    basis="assumed",
    rationale=(
        "scale_up = assumed pod-scheduling overhead "
        f"({_ASSUMED_K8S_SCHEDULE_SECONDS}s, no measured basis in this "
        "program's evidence yet -- IO-T009 is the task that would measure "
        "it) + measured warm-cache model-load time "
        f"({MEASURED_COLD_START.warm_load_seconds:.2f}s, "
        f"{MEASURED_COLD_START.source}); scale_down = assumed graceful-"
        f"drain + termination-grace period ({_ASSUMED_DRAIN_GRACE_SECONDS}s, "
        "a common Kubernetes default, not measured in this program). "
        "Revisit when inferops IO-T009 produces real replica-scaling "
        "timing data."
    ),
)
