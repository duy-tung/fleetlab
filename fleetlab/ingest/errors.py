"""Typed refusal errors for fleetlab ingestion.

fleetlab's failure semantics are input-validation semantics (docs/architecture.md
"Failure semantics"): fail fast and loudly, name the file, the field (JSON
pointer), and the rule violated. Never silently coerce or default.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional


class IngestError(Exception):
    """Base class for every fleetlab ingestion refusal.

    Attributes:
        file: path of the file that was rejected.
        pointer: JSON-pointer-style location of the violation within the file
            (e.g. "gpu/vram_gb", "objectives/0/provenance/basis"). Empty string
            when the violation applies to the whole document.
        rule: short machine-readable rule name (e.g. "additionalProperties",
            "required", "type", "provenance-missing").
        detail: human-readable explanation from the underlying validator.
    """

    def __init__(
        self,
        file: "str | Path",
        pointer: str,
        rule: str,
        detail: str,
    ) -> None:
        self.file = str(file)
        self.pointer = pointer
        self.rule = rule
        self.detail = detail
        message = f"{self.file}: at '{pointer or '<root>'}': [{rule}] {detail}"
        super().__init__(message)


class SchemaValidationError(IngestError):
    """A file fails schema validation for a reason unrelated to provenance or
    unsupported fields (wrong type, missing required field, pattern mismatch,
    conditional-schema violation, etc.)."""


class ProvenanceMissingError(IngestError):
    """A quantitative value lacks the mandatory {value, provenance{basis,
    as_of}} shape, or its provenance object is missing basis/as_of/source.

    This is refused structurally — fleetlab never fills a default in place of
    a missing provenance record (docs/architecture.md, program hard rule 8).
    """


class UnsupportedFieldError(IngestError):
    """A file carries a field the schema does not recognize.

    Unknown fields are rejected, not ignored (program-wide unsupported-field
    rejection posture, docs/testing.md).
    """


class RecordParseError(IngestError):
    """A record (a JSON document, or one line of a JSONL file) could not even
    be parsed. A file that is not parseable must fail, not be skipped."""
