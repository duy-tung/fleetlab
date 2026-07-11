"""Golden-file tests: raw events (Contract 3, JSONL)."""

from pathlib import Path

import pytest

from fleetlab.ingest import SchemaValidationError, UnsupportedFieldError, load_raw_events

FIXTURES = Path(__file__).parent / "fixtures"
DIR = FIXTURES / "raw-event"


def test_valid_ingests_cleanly():
    events = load_raw_events(DIR / "valid.jsonl")
    assert len(events) == 1
    assert events[0].status == "ok"
    assert events[0].error_class is None


def test_invalid_refuses_ok_status_with_nonnull_error_class():
    with pytest.raises(SchemaValidationError) as exc:
        load_raw_events(DIR / "invalid.jsonl")
    assert exc.value.file.endswith("invalid.jsonl:1")
    assert exc.value.pointer == "error_class"


def test_unsupported_field_is_rejected_not_ignored():
    with pytest.raises(UnsupportedFieldError) as exc:
        load_raw_events(DIR / "unsupported-field.jsonl")
    assert exc.value.rule == "additionalProperties"
