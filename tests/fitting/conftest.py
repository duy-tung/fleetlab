from pathlib import Path
from typing import List

import pytest

from fleetlab.fitting import CorpusPoint, load_corpus_point, load_corpus_point_from_events

FIXTURES = Path(__file__).parent / "fixtures" / "real" / "ib-t010"
SWEEP_FIXTURES = Path(__file__).parent / "fixtures" / "real" / "ib-t008" / "sweep"

# The ib-t008 sweep's engine-config identity: gateway config `flags-v1`
# (dev@74f2372), mock engine flags ttft=20ms/itl=5ms, and -- disclosed in
# sweep.json -- a client-transport concurrency cap of 2 held fixed across the
# probe and every point (models a capacity-limited target; the mock/gateway
# pair has no admission control of its own at that pinned build). The cap is
# part of the config identity: profiles fitted from this sweep describe THAT
# capacity-limited setup, not general mock behavior.
SWEEP_ENGINE_CONFIG_ID = "gateway-mock-flags-v1-conncap2"


def sweep_point(index: int) -> CorpusPoint:
    reps = [1, 2, 3]
    return load_corpus_point_from_events(
        run_id=f"ib-t008-sweep-p{index}",
        events_paths=[SWEEP_FIXTURES / f"point-{index}" / f"rep-{r}" / "events.jsonl" for r in reps],
        manifest_paths=[SWEEP_FIXTURES / f"point-{index}" / f"rep-{r}" / "manifest.json" for r in reps],
        workload_path=SWEEP_FIXTURES / f"point-{index}-workload.json",
        hardware_id="mock-loopback-cpu-dev",
        model_id="mock-8b",
        engine_config_id=SWEEP_ENGINE_CONFIG_ID,
    )


@pytest.fixture(scope="session")
def sweep_points() -> List[CorpusPoint]:
    return [sweep_point(i) for i in range(6)]


def _point(result_name: str, workload_name: str, manifest_dir: str, engine_config_id: str) -> CorpusPoint:
    return load_corpus_point(
        result_path=FIXTURES / "results" / result_name,
        workload_path=FIXTURES / workload_name,
        manifest_path=FIXTURES / manifest_dir / "manifest.json",
        hardware_id="mock-loopback-cpu-dev",
        model_id="mock-8b",
        engine_config_id=engine_config_id,
    )


@pytest.fixture
def e2_baseline() -> CorpusPoint:
    return _point(
        "ib-t010-e2-baseline-1x-sane.benchmark-result.json",
        "e2-baseline-workload.json",
        "e2-baseline",
        "gateway-mock-admission-sane-v1",
    )


@pytest.fixture
def e2_overload() -> CorpusPoint:
    return _point(
        "ib-t010-e2-overload-5x-sane.benchmark-result.json",
        "e2-overload-workload.json",
        "e2-overload-compare/sane",
        "gateway-mock-admission-sane-v1",
    )


@pytest.fixture
def e2b_baseline() -> CorpusPoint:
    return _point(
        "ib-t010-e2b-baseline-1x-sane.benchmark-result.json",
        "e2-baseline-workload.json",
        "e2b-baseline",
        "gateway-mock-admission-sane-v1b",
    )


@pytest.fixture
def e2b_overload() -> CorpusPoint:
    return _point(
        "ib-t010-e2b-overload-5x-sane.benchmark-result.json",
        "e2-overload-workload.json",
        "e2b-overload",
        "gateway-mock-admission-sane-v1b",
    )


@pytest.fixture
def e1_mock_direct() -> CorpusPoint:
    return _point(
        "ib-t010-e1-mock-direct.benchmark-result.json",
        "e1-mock-workload.json",
        "e1-mock-compare/direct",
        "direct-mock-default",
    )
