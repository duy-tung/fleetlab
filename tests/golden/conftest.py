from pathlib import Path

import pytest

from fleetlab.ingest import ContractBundle

FIXTURES = Path(__file__).parent / "fixtures"
VENDOR_EXAMPLES = (
    Path(__file__).resolve().parents[2] / "vendor" / "serving-contracts-v0.2.0" / "examples"
)


@pytest.fixture(scope="session")
def bundle() -> ContractBundle:
    return ContractBundle()
