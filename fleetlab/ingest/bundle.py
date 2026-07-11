"""Access to the pinned `serving-contracts` bundle.

fleetlab pins one released bundle version and validates all inputs and outputs
against it (docs/interfaces.md). The bundle is vendored read-only under
`vendor/serving-contracts-v0.2.0/` via `git archive <tag-commit>` — never
fetched at runtime (determinism rule 5, docs/architecture.md).

Decision recorded here (see docs/implementation-notes.md FL-T002 entry): this
loader validates directly against `jsonschema` (already a pinned dependency
per ADR-0001) rather than shelling out to `serving-contracts/kit/
contracts-validate.py`. The kit remains the I1 CI mechanism (`make
contracts-verify` runs the kit's own `selftest`/`check` against the vendored
bundle); fleetlab's ingestion needs typed Python exceptions distinguishing
provenance-missing / unsupported-field / generic-schema refusals, which the
kit's CLI (text/JSON summary, process exit code) does not give us directly.
Both consume the exact same schema files, so there is no drift between what
CI checks and what the library enforces.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

from jsonschema import Draft202012Validator

BUNDLE_VERSION = "v0.2.0"
BUNDLE_COMMIT = "484b44904233da569d76bafe4a4acb8d71bbbe4d"  # tag v0.2.0, serving-contracts

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BUNDLE_ROOT = _REPO_ROOT / "vendor" / "serving-contracts-v0.2.0"
_SCHEMAS_DIR = _BUNDLE_ROOT / "schemas"


class ContractBundle:
    """Loads and caches schema documents + validators from the vendored bundle."""

    def __init__(self, root: Path = _BUNDLE_ROOT) -> None:
        self.root = root
        self.schemas_dir = root / "schemas"
        if not self.schemas_dir.is_dir():
            raise FileNotFoundError(
                f"vendored contract bundle not found at {self.schemas_dir}; "
                "expected a git-archive extraction of serving-contracts "
                f"@ {BUNDLE_COMMIT} ({BUNDLE_VERSION})"
            )
        self._docs: Dict[str, dict] = {}
        self._validators: Dict[str, Draft202012Validator] = {}

    def schema_doc(self, name: str) -> dict:
        if name not in self._docs:
            path = self.schemas_dir / f"{name}.schema.json"
            if not path.is_file():
                raise FileNotFoundError(
                    f"unknown contract schema '{name}' (looked for {path})"
                )
            self._docs[name] = json.loads(path.read_text())
        return self._docs[name]

    def defs(self, name: str) -> dict:
        """The schema's own $defs block (used to identify provenance-shaped
        sub-schemas structurally when classifying a validation failure)."""
        return self.schema_doc(name).get("$defs", {})

    def validator(self, name: str) -> Draft202012Validator:
        if name not in self._validators:
            doc = self.schema_doc(name)
            Draft202012Validator.check_schema(doc)
            self._validators[name] = Draft202012Validator(doc)
        return self._validators[name]


_default_bundle: "ContractBundle | None" = None


def default_bundle() -> ContractBundle:
    global _default_bundle
    if _default_bundle is None:
        _default_bundle = ContractBundle()
    return _default_bundle
