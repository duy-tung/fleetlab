"""Golden-file tests: benchmark-run manifests (Contract 3)."""

from pathlib import Path

import pytest

from fleetlab.ingest import SchemaValidationError, UnsupportedFieldError, load_benchmark_run

FIXTURES = Path(__file__).parent / "fixtures"
DIR = FIXTURES / "benchmark-run"


def test_valid_ingests_cleanly():
    run = load_benchmark_run(DIR / "valid.json")
    assert run.run_id == "golden-valid-run"
    assert run.target_topology == "engine-direct"
    assert run.gateway is None


def test_invalid_refuses_engine_direct_with_gateway_block():
    with pytest.raises(SchemaValidationError):
        load_benchmark_run(DIR / "invalid.json")


def test_unsupported_field_is_rejected_not_ignored():
    with pytest.raises(UnsupportedFieldError) as exc:
        load_benchmark_run(DIR / "unsupported-field.json")
    assert exc.value.rule == "additionalProperties"
