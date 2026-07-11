from pathlib import Path

import pytest

from fleetlab.fitting import CorpusPoint, load_corpus_point

FIXTURES = Path(__file__).parent / "fixtures" / "real" / "ib-t010"


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
