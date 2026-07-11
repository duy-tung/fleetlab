from pathlib import Path

import pytest

from fleetlab.fitting import load_corpus_point

FIXTURES = Path(__file__).parent / "fixtures" / "real" / "ib-t010"


def test_e2_baseline_point_matches_real_benchmark_result(e2_baseline):
    # cross-checked directly against
    # ib-t010-e2-baseline-1x-sane.benchmark-result.json
    assert e2_baseline.run_id == "ib-t010-e2-baseline-1x-sane"
    assert e2_baseline.offered_rate_rps == pytest.approx(37.8072)
    assert e2_baseline.achieved_rate_rps == pytest.approx(33.15910399768093)
    assert e2_baseline.total_requests == 900
    assert e2_baseline.e2e_p50_seconds == pytest.approx(0.16838788986206055)


def test_achieved_rate_stderr_is_poisson_counting_error(e2_baseline):
    # SE(rate) = rate / sqrt(N) for a Poisson count over a fixed window
    expected = 33.15910399768093 / (900**0.5)
    assert e2_baseline.achieved_rate_stderr_rps == pytest.approx(expected)


def test_refuses_mismatched_workload_manifest_pairing():
    with pytest.raises(ValueError, match="does not match"):
        load_corpus_point(
            result_path=FIXTURES / "results" / "ib-t010-e2-baseline-1x-sane.benchmark-result.json",
            workload_path=FIXTURES / "e2-overload-workload.json",  # wrong pairing
            manifest_path=FIXTURES / "e2-baseline" / "manifest.json",
            hardware_id="mock-loopback-cpu-dev",
            model_id="mock-8b",
            engine_config_id="gateway-mock-admission-sane-v1",
        )


def test_e1_mock_direct_point_is_underloaded_relative_to_offered(e1_mock_direct):
    # offered=6, achieved close to but below 6 -- real data, not fabricated
    assert e1_mock_direct.offered_rate_rps == pytest.approx(6.0)
    assert e1_mock_direct.achieved_rate_rps < e1_mock_direct.offered_rate_rps
    assert e1_mock_direct.achieved_rate_rps == pytest.approx(5.809063599452249)
