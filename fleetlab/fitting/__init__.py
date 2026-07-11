"""fleetlab.fitting — goodput/latency profiles from measured benchmark results
(FL-T004), with a structural train/holdout split (G8).

Scope decision, recorded here and in `docs/adr/0002-fitting-method.md`: the
real corpus available at FL-T004 time (`inferbench/docs/evidence/ib-t010`,
`ib-t004`, `ib-t005`, `inference-lab/evidence/i3`) has, per
(hardware, model, engine-config), at most **two** distinct offered-rate data
points — never a multi-point sweep. A model with more free parameters than
training points is not a fit, it is an equation with a unique solution and
zero evidence of generalization. Every model in this package is therefore
deliberately **one free parameter**, closed-form (solved algebraically, not
via an iterative optimizer — `scipy` is not needed and is not a dependency),
so that a single training point exactly determines it and the *entire*
evidentiary burden falls on the holdout prediction, exactly as G8 intends.

Modules:
- `corpus`: typed real-data points, built from `fleetlab.ingest` loaders.
- `capacity`: the achieved-throughput capacity-clamp model.
- `latency`: the queueing-blowup latency model (PENDING for the only two
  fittable engine-configs in the corpus — see `docs/notes/fitting-method.md`
  for why, and `reports/holdout-validation.md` for the full account).
- `holdout`: the structural train/holdout split and the impossibility guard.
"""

from .corpus import CorpusPoint, load_corpus_point
from .capacity import CapacityFit, fit_capacity, predict_achieved_rps
from .latency import LatencyFit, LatencyModelUndefined, fit_latency, predict_latency
from .holdout import (
    FittedGoodputProfile,
    HoldoutReport,
    HoldoutSplit,
    TrainingDataLeakageError,
    evaluate_holdout,
    fit_profile,
)

__all__ = [
    "CorpusPoint",
    "load_corpus_point",
    "CapacityFit",
    "fit_capacity",
    "predict_achieved_rps",
    "LatencyFit",
    "LatencyModelUndefined",
    "fit_latency",
    "predict_latency",
    "FittedGoodputProfile",
    "HoldoutReport",
    "HoldoutSplit",
    "TrainingDataLeakageError",
    "evaluate_holdout",
    "fit_profile",
]
