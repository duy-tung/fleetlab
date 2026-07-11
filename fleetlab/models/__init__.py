"""fleetlab.models — the analytic backbone (FL-T003).

Arrival and length models parameterized directly from workload manifests;
a token-rate model fitted from raw events; Little's-law relationships; and
the KV-memory-per-token model. Every model here is closed-form / analytic
per ADR-0001 ("Steady-state models: closed-form analytic"); time-dependent
behavior (queue growth, cold start, scaling lag) is FL-T005's
`fleetlab/dynamics/`, not this package.

Determinism: every sampling function takes an explicit
`numpy.random.Generator` — no module-level or global RNG state (determinism
rule 3, docs/architecture.md).
"""

from .arrival import (
    ClosedLoopArrivalProcess,
    PhasedPoissonArrivalProcess,
    PoissonArrivalProcess,
    arrival_process_from_workload,
)
from .kv_memory import DTYPE_BYTES, dtype_bytes_for, kv_cache_bytes, kv_cache_bytes_per_token
from .length import LengthDistribution, mean_of_distribution, sample_distribution
from .littles_law import (
    LittlesLawCheck,
    check_littles_law,
    concurrency,
    empirical_mean_sojourn_seconds,
    empirical_throughput_rps,
    empirical_time_average_concurrency,
    latency_seconds,
    arrival_rate_rps,
)
from .token_rate import TokenRateSummary, fit_token_rate, request_decode_tokens_per_second

__all__ = [
    "ClosedLoopArrivalProcess",
    "PhasedPoissonArrivalProcess",
    "PoissonArrivalProcess",
    "arrival_process_from_workload",
    "DTYPE_BYTES",
    "dtype_bytes_for",
    "kv_cache_bytes",
    "kv_cache_bytes_per_token",
    "LengthDistribution",
    "mean_of_distribution",
    "sample_distribution",
    "LittlesLawCheck",
    "check_littles_law",
    "concurrency",
    "empirical_mean_sojourn_seconds",
    "empirical_throughput_rps",
    "empirical_time_average_concurrency",
    "latency_seconds",
    "arrival_rate_rps",
    "TokenRateSummary",
    "fit_token_rate",
    "request_decode_tokens_per_second",
]
