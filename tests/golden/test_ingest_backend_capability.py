"""Golden-file tests: backend-capability descriptors (Contract 4)."""

from pathlib import Path

import pytest

from fleetlab.ingest import SchemaValidationError, UnsupportedFieldError, load_backend_capability

FIXTURES = Path(__file__).parent / "fixtures"
VENDOR_EXAMPLES = Path(__file__).resolve().parents[2] / "vendor" / "serving-contracts-v0.2.0" / "examples"
DIR = FIXTURES / "backend-capability"


def test_valid_ingests_cleanly():
    cap = load_backend_capability(VENDOR_EXAMPLES / "capabilities" / "mock.json")
    assert cap.engine["name"] == "mock"


def test_invalid_missing_release_observability_refuses():
    with pytest.raises(SchemaValidationError):
        load_backend_capability(
            VENDOR_EXAMPLES / "capabilities" / "invalid" / "missing-release-observability.json"
        )


def test_unsupported_field_is_rejected_not_ignored():
    with pytest.raises(UnsupportedFieldError) as exc:
        load_backend_capability(DIR / "unsupported-field.json")
    assert exc.value.rule == "additionalProperties"


def test_real_llamacpp_capability_descriptor_ingests_cleanly():
    """The real, probed Contract 4 descriptor from inference-lab evidence/i3."""
    real = FIXTURES / "real" / "capabilities" / "llamacpp.backend-capability.json"
    cap = load_backend_capability(real)
    assert cap.engine["name"] == "llamacpp"
    assert cap.context_limit_tokens == 4096
