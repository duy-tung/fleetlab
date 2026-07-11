"""Known-answer + real-data cross-check tests: token-rate model."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pytest

from fleetlab.ingest import load_benchmark_result, load_raw_events
from fleetlab.models.token_rate import (
    fit_token_rate,
    request_decode_tokens_per_second,
    system_output_token_rate,
)

REAL_RUNS = Path(__file__).resolve().parents[1] / "golden" / "fixtures" / "real" / "runs"
REAL_RESULTS = Path(__file__).resolve().parents[1] / "golden" / "fixtures" / "real" / "results"


@dataclass
class _FakeEvent:
    status: str
    ttft_seconds: Optional[float]
    output_tokens: int
    scheduled_send_ts: str
    end_ts: str


def test_hand_computed_decode_rate():
    """ttft=0.1s, output_tokens=50, e2e=1.0s -> decode phase = 0.9s over
    49 tokens (the first token is already inside TTFT) = 49/0.9 tokens/s."""
    event = _FakeEvent(
        status="ok",
        ttft_seconds=0.1,
        output_tokens=50,
        scheduled_send_ts="2026-01-01T00:00:00.000000Z",
        end_ts="2026-01-01T00:00:01.000000Z",
    )
    rate = request_decode_tokens_per_second(event)
    assert rate == pytest.approx(49.0 / 0.9)


def test_decode_rate_is_none_for_non_ok_or_single_token_events():
    assert request_decode_tokens_per_second(
        _FakeEvent("error", 0.1, 5, "2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z")
    ) is None
    assert request_decode_tokens_per_second(
        _FakeEvent("ok", 0.1, 1, "2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z")
    ) is None
    assert request_decode_tokens_per_second(
        _FakeEvent("ok", None, 5, "2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z")
    ) is None


def test_system_output_token_rate_is_rps_times_mean_tokens():
    assert system_output_token_rate(requests_per_second=2.0, mean_output_tokens=50.0) == pytest.approx(100.0)


def test_fit_token_rate_rejects_empty_input():
    with pytest.raises(ValueError):
        fit_token_rate([])


def test_fit_token_rate_on_real_events():
    events = load_raw_events(REAL_RUNS / "calib-A-mock" / "events.jsonl")
    summary = fit_token_rate(events)
    assert summary.n > 0
    assert summary.mean_tokens_per_second > 0
    assert summary.p50_tokens_per_second > 0


# ---------------------------------------------------------------------------
# cross-check against a real benchmark-result's own throughput block
# ---------------------------------------------------------------------------


def test_system_output_token_rate_matches_real_benchmark_result_throughput():
    """ib-t005-calib-A.benchmark-result.json: total_requests=120,
    total_output_tokens=7650, requests_per_second=3.1175309264829445,
    output_tokens_per_second=198.74259656328772. fleetlab's
    system_output_token_rate(rps, mean_tokens) is the same arithmetic
    identity inferbench used to compute output_tokens_per_second from the
    same pooled window; this reproduces the reported figure to floating
    point (an exact-formula cross-check, not a statistical one)."""
    result = load_benchmark_result(REAL_RESULTS / "ib-t005-calib-A.benchmark-result.json")
    mean_output_tokens = (
        result.throughput["total_output_tokens"] / result.throughput["total_requests"]
    )
    predicted = system_output_token_rate(
        requests_per_second=result.throughput["requests_per_second"],
        mean_output_tokens=mean_output_tokens,
    )
    measured = result.throughput["output_tokens_per_second"]
    assert predicted == pytest.approx(measured, rel=1e-6)
