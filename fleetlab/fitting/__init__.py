"""fleetlab.fitting — goodput/latency profiles from measured benchmark results
(FL-T004), with a structural train/holdout split (G8).

Scope decision, recorded here and in `docs/adr/0002-fitting-method.md` (and
its same-day addendum): the real corpus is `inferbench/docs/evidence/
{ib-t008, ib-t010, ib-t004, ib-t005}` + `inference-lab/evidence/i3`. The
ib-t008 six-point rate sweep (added in a same-day corpus-scope correction —
it was missing from the original brief's directory list) is the only
multi-point data; every other engine-config has one or two offered-rate
points. Every model in this package is deliberately **one free parameter**,
closed-form (exact algebra, not an iterative optimizer — `scipy` is not
needed and is not a dependency): for the two-point ib-t010 configs a richer
model would leave no holdout, and for the ib-t008 sweep the one-parameter
forms are retained so the holdout results characterize their misfit
precisely before any reviewed follow-up upgrades them (ADR-0002 addendum).

Modules:
- `corpus`: typed real-data points, built from `fleetlab.ingest` loaders
  (from aggregated benchmark-result files, or directly from raw events for
  sweep runs that ship no aggregate).
- `capacity`: the achieved-throughput capacity-clamp model (exact weighted
  least squares).
- `latency`: the queueing-blowup latency model (FITTED for the ib-t008
  sweep config; PENDING for the ib-t010 configs, which have no sub-capacity
  points — see `docs/notes/fitting-method.md` §4 and
  `reports/holdout-validation.md`).
- `holdout`: the structural train/holdout split and the impossibility guard.
"""

from .corpus import CorpusPoint, load_corpus_point, load_corpus_point_from_events
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
    "load_corpus_point_from_events",
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
