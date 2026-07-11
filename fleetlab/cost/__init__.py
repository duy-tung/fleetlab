"""fleetlab.cost -- cost/capacity economics (FL-T008).

Cost per successful request and per 1M tokens at SLO attainment, built on
the FL-T004 fitted capacity/latency profile plus a `cost-profile.schema.json`
input (loaded via `fleetlab.ingest.load_cost_profile`, FL-T002 -- this
package never re-parses a cost-profile file itself). Every price carries the
mandatory schema provenance (`basis`, `as_of`, `source`); this package never
fabricates a rate.

fleetlab's own measured corpus has no GPU and no real hardware price (the
fitted profile is a CPU-only mock backend). This package therefore keeps two
separate things distinct, never conflated:

- `model.py`: closed-form, **parameterized** cost arithmetic (any
  `usd_per_hour` x any `goodput_rps` x any `tokens_per_request` -- no
  specific hardware or price baked in). Pure functions, no RNG (there is
  nothing to seed).
- `build_cost_report.py`: one concrete **demonstration** run, wiring the
  parameterized functions to the FL-T004 fitted profile (mock backend,
  measured) and the `cost-g5-xlarge-ondemand` example cost profile (a real
  GPU's on-demand/spot pricing, from `serving-contracts`'s reference
  examples) -- explicitly and repeatedly labeled "MODEL DEMONSTRATION, not a
  real cost claim" in every artifact it produces, because the priced
  hardware (A10G GPU) is not the hardware the capacity was actually measured
  on (CPU-only mock backend).
"""

from .model import (
    CostAtSloResult,
    SensitivityPoint,
    SloUnattainableError,
    compute_cost_at_slo,
    cost_per_1e6_tokens_usd,
    cost_per_request_usd,
    cost_per_second_usd,
    goodput_at_slo_rps,
    sensitivity_table,
)

__all__ = [
    "CostAtSloResult",
    "SensitivityPoint",
    "SloUnattainableError",
    "compute_cost_at_slo",
    "cost_per_1e6_tokens_usd",
    "cost_per_request_usd",
    "cost_per_second_usd",
    "goodput_at_slo_rps",
    "sensitivity_table",
]
