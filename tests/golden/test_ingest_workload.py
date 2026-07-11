"""Golden-file tests: workload manifests (Contract 3)."""

from pathlib import Path

import pytest

from fleetlab.ingest import SchemaValidationError, UnsupportedFieldError, load_workload

FIXTURES = Path(__file__).parent / "fixtures"
VENDOR_EXAMPLES = Path(__file__).resolve().parents[2] / "vendor" / "serving-contracts-v0.2.0" / "examples"
DIR = FIXTURES / "workload"


def test_valid_ingests_cleanly():
    w = load_workload(DIR / "valid.json")
    assert w.name == "golden-valid"
    assert w.seed == 42
    assert w.arrival_process["rate_rps"] == 5


def test_invalid_refuses_with_typed_error():
    with pytest.raises(SchemaValidationError) as exc:
        load_workload(DIR / "invalid.json")
    err = exc.value
    assert "invalid.json" in err.file
    assert err.rule == "required"


def test_unsupported_field_is_rejected_not_ignored():
    with pytest.raises(UnsupportedFieldError) as exc:
        load_workload(DIR / "unsupported-field.json")
    assert exc.value.rule == "additionalProperties"


def test_vendored_invalid_examples_all_refuse():
    """Every fixture under serving-contracts' workloads/invalid/ must fail —
    this is the same rule the bundle's own selftest enforces (I1 obligation)."""
    invalid_dir = VENDOR_EXAMPLES / "workloads" / "invalid"
    files = sorted(invalid_dir.glob("*.json"))
    assert files, "expected vendored invalid workload fixtures"
    for f in files:
        with pytest.raises(SchemaValidationError):
            load_workload(f)


def test_vendored_positive_examples_all_ingest():
    examples_dir = VENDOR_EXAMPLES / "workloads"
    files = sorted(p for p in examples_dir.glob("*.json"))
    assert files
    for f in files:
        load_workload(f)  # must not raise
