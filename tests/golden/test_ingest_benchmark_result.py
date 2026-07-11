"""Golden-file tests: benchmark results (Contract 3)."""

from pathlib import Path

import pytest

from fleetlab.ingest import SchemaValidationError, UnsupportedFieldError, load_benchmark_result

FIXTURES = Path(__file__).parent / "fixtures"
DIR = FIXTURES / "benchmark-result"


def test_valid_ingests_cleanly():
    res = load_benchmark_result(DIR / "valid.json")
    assert res.result_id == "golden-valid-result"
    assert res.goodput["shed_rate"] == 0.0
    assert res.cost is None


def test_invalid_refuses_averaged_percentiles_method():
    """pooled_percentiles.method is a const 'pooled-raw-events' — averaging
    per-run percentiles is not schema-valid (benchmark-result normative rule)."""
    with pytest.raises(SchemaValidationError):
        load_benchmark_result(DIR / "invalid.json")


def test_unsupported_field_is_rejected_not_ignored():
    with pytest.raises(UnsupportedFieldError) as exc:
        load_benchmark_result(DIR / "unsupported-field.json")
    assert exc.value.rule == "additionalProperties"
