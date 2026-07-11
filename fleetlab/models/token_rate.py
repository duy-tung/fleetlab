"""Token-rate model, fitted from raw events (Contract 3).

Two views, matching docs/architecture.md component 2:

1. Per-request decode rate: output tokens per second *after* the first token
   (TTFT already accounts for the first token; the decode phase is
   `e2e_duration - ttft`, per Contract 2's exact measurement-point
   definitions — TTFT from `scheduled_send_ts`, ITL = inter-chunk gap).
2. System-level token throughput: `requests_per_second * mean_output_tokens`
   — a direct Little's-law-flavored identity (total tokens emitted per
   second = completion rate times mean tokens per completion), cross-checked
   against a real benchmark-result's own `throughput.output_tokens_per_second`
   field in `docs/notes/model-validation.md`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, List, Optional

import numpy as np


def _parse_ts(value: str) -> float:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def request_decode_tokens_per_second(event) -> Optional[float]:
    """Decode-phase throughput for one request, or None when it cannot be
    computed (not a completed request, fewer than 2 output tokens, or a
    non-positive decode interval)."""
    if event.status != "ok" or event.ttft_seconds is None:
        return None
    if event.output_tokens < 2:
        return None
    start = _parse_ts(event.scheduled_send_ts)
    end = _parse_ts(event.end_ts)
    e2e = end - start
    decode_seconds = e2e - event.ttft_seconds
    if decode_seconds <= 0:
        return None
    tokens_after_first = event.output_tokens - 1
    return tokens_after_first / decode_seconds


@dataclass(frozen=True)
class TokenRateSummary:
    n: int
    mean_tokens_per_second: float
    p50_tokens_per_second: float
    p95_tokens_per_second: float


def fit_token_rate(events: Iterable) -> TokenRateSummary:
    """Fit a decode-rate summary from a collection of
    `fleetlab.ingest.RawEvent`. Raises ValueError if no event yields a rate
    (fleetlab never reports a fit on zero data)."""
    rates: List[float] = []
    for e in events:
        r = request_decode_tokens_per_second(e)
        if r is not None:
            rates.append(r)
    if not rates:
        raise ValueError("no events yielded a computable decode rate")
    arr = np.asarray(rates)
    return TokenRateSummary(
        n=len(rates),
        mean_tokens_per_second=float(arr.mean()),
        p50_tokens_per_second=float(np.percentile(arr, 50)),
        p95_tokens_per_second=float(np.percentile(arr, 95)),
    )


def system_output_token_rate(requests_per_second: float, mean_output_tokens: float) -> float:
    """Predicted system-level output-token throughput: rps * mean tokens per
    request. A direct application of the same L=lambda*W family of
    identities (docs/architecture.md component 2): tokens/sec is completions/
    sec times tokens/completion, exactly analogous to L=lambda*W."""
    return requests_per_second * mean_output_tokens
