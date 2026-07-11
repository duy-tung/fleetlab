"""Schema validation + refusal classification.

Wraps `jsonschema` (Draft 2020-12, matching the bundle's `$schema`) and turns
its generic `ValidationError`s into the three typed refusal categories
fleetlab's docs commit to (docs/testing.md §1): unsupported-field,
provenance-missing, and generic schema violations. Never coerces, never fills
a default.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

from jsonschema.exceptions import ValidationError, best_match

from .bundle import ContractBundle, default_bundle
from .errors import (
    ProvenanceMissingError,
    SchemaValidationError,
    UnsupportedFieldError,
)

# The three reusable provenance-carrying $defs used across the profile
# schemas (hardware/model/slo/cost-profile). A validation failure whose
# resolved sub-schema is structurally one of these — rather than merely
# mentioning "provenance" in a message — is classified as provenance-missing
# regardless of which schema file it came from.
_PROVENANCE_DEF_NAMES = ("provenance", "provenancedNumber", "provenancedInteger")

# Path components that only ever appear inside a provenance record. A
# violation whose JSON pointer passes through one of these is provenance
# work, not a generic shape violation (e.g. "usd_per_hour/provenance" missing
# 'source', or "objectives/0/provenance/basis" failing the measured-only
# const rule for model-serving SLOs).
_PROVENANCE_PATH_TOKENS = {"provenance", "basis", "as_of", "source"}


def _pointer(error: ValidationError) -> str:
    return "/".join(str(p) for p in error.absolute_path)


def _is_provenance_shaped(error: ValidationError, defs: dict) -> bool:
    schema = error.schema
    if not isinstance(schema, dict):
        return False
    for name in _PROVENANCE_DEF_NAMES:
        ref_schema = defs.get(name)
        if ref_schema is not None and schema == ref_schema:
            return True
    return False


def _touches_provenance_path(error: ValidationError) -> bool:
    return any(str(p) in _PROVENANCE_PATH_TOKENS for p in error.absolute_path)


def validate_instance(
    schema_name: str,
    instance,
    source: "str | Path",
    bundle: Optional[ContractBundle] = None,
) -> None:
    """Validate `instance` against the named contract schema.

    Raises on the first significant refusal category found:
      1. UnsupportedFieldError  — an `additionalProperties` violation.
      2. ProvenanceMissingError — a quantitative value or provenance record
         missing/malformed per the mandatory {value, provenance{basis,
         as_of}} shape.
      3. SchemaValidationError  — any other schema violation.

    Returns None (silently) when the instance is schema-valid. Never mutates
    `instance` and never substitutes a default for a missing value.
    """
    bundle = bundle or default_bundle()
    validator = bundle.validator(schema_name)
    errors: List[ValidationError] = list(validator.iter_errors(instance))
    if not errors:
        return

    unsupported = [e for e in errors if e.validator == "additionalProperties"]
    if unsupported:
        e = unsupported[0]
        raise UnsupportedFieldError(
            source, _pointer(e), "additionalProperties", e.message
        )

    defs = bundle.defs(schema_name)
    provenance_errors = [
        e for e in errors if _touches_provenance_path(e) or _is_provenance_shaped(e, defs)
    ]
    if provenance_errors:
        e = provenance_errors[0]
        raise ProvenanceMissingError(source, _pointer(e), "provenance-missing", e.message)

    e = best_match(errors)
    raise SchemaValidationError(source, _pointer(e), e.validator, e.message)
