"""Golden-file tests: hardware/model/SLO/cost fleet profiles (SC-T007).

PROVENANCE IS MANDATORY AND STRUCTURAL for these four schemas: every
quantitative value is a {value, provenance{basis, as_of}} object. This module
exercises all four "provenance-missing" fixtures explicitly — the rule fleetlab
commits to (docs/testing.md §1) as a test, not a convention.
"""

from pathlib import Path

import pytest

from fleetlab.ingest import (
    ProvenanceMissingError,
    SchemaValidationError,
    UnsupportedFieldError,
    load_cost_profile,
    load_hardware_profile,
    load_model_profile,
    load_slo,
)

FIXTURES = Path(__file__).parent / "fixtures"
VENDOR_EXAMPLES = Path(__file__).resolve().parents[2] / "vendor" / "serving-contracts-v0.2.0" / "examples" / "fleet"


# ---------------------------------------------------------------------------
# hardware-profile
# ---------------------------------------------------------------------------


def test_hardware_profile_valid_ingests_cleanly():
    hp = load_hardware_profile(VENDOR_EXAMPLES / "hardware-a10g-g5-xlarge.json")
    assert hp.gpu_model == "NVIDIA A10G"
    assert hp.vram_gb.value == 24
    assert hp.vram_gb.provenance.basis == "source-reported"


def test_hardware_profile_provenance_missing_refuses():
    with pytest.raises(ProvenanceMissingError) as exc:
        load_hardware_profile(VENDOR_EXAMPLES / "invalid" / "hardware-missing-provenance.json")
    assert exc.value.rule == "provenance-missing"


def test_hardware_profile_unsupported_field_is_rejected():
    with pytest.raises(UnsupportedFieldError):
        load_hardware_profile(FIXTURES / "hardware-profile" / "unsupported-field.json")


# ---------------------------------------------------------------------------
# model-profile
# ---------------------------------------------------------------------------


def test_model_profile_valid_ingests_cleanly():
    mp = load_model_profile(VENDOR_EXAMPLES / "model-llama31-8b.json")
    assert mp.checkpoint_id == "meta-llama/Llama-3.1-8B-Instruct"
    assert mp.parameters_billion.value == pytest.approx(8.03)
    assert mp.kv_cache_bytes_per_token.provenance.basis == "source-reported"


def test_model_profile_unsupported_field_is_rejected():
    with pytest.raises(UnsupportedFieldError):
        load_model_profile(FIXTURES / "model-profile" / "unsupported-field.json")


# ---------------------------------------------------------------------------
# slo
# ---------------------------------------------------------------------------


def test_slo_valid_ingests_cleanly():
    slo = load_slo(VENDOR_EXAMPLES / "slo-chat-interactive.json")
    assert slo.scope == "model-serving"
    assert all(o.provenance.basis == "measured" for o in slo.objectives)


def test_slo_declared_in_advance_refuses_as_provenance_missing():
    """Model-serving SLOs are declared only from measurement; an 'assumed'
    basis on a model-serving objective is the provenance-missing rule, not a
    generic schema error — the SLO schema encodes this structurally."""
    with pytest.raises(ProvenanceMissingError):
        load_slo(VENDOR_EXAMPLES / "invalid" / "slo-declared-in-advance.json")


def test_slo_unsupported_field_is_rejected():
    with pytest.raises(UnsupportedFieldError):
        load_slo(FIXTURES / "slo" / "unsupported-field.json")


def test_real_measured_slo_ingests_cleanly():
    """The real, measurement-derived SLO from inference-lab evidence/i3."""
    real = FIXTURES / "real" / "slo" / "scenario-b-llamacpp-cpu-shakedown.slo.json"
    slo = load_slo(real)
    assert slo.slo_id == "scenario-b-llamacpp-cpu-shakedown"
    assert all(o.provenance.basis == "measured" for o in slo.objectives)


# ---------------------------------------------------------------------------
# cost-profile
# ---------------------------------------------------------------------------


def test_cost_profile_valid_ingests_cleanly():
    cp = load_cost_profile(VENDOR_EXAMPLES / "cost-g5-xlarge-ondemand.json")
    assert cp.currency == "USD"
    assert cp.rates[0].usd_per_hour.provenance.basis == "source-reported"


def test_cost_profile_reported_without_source_refuses_as_provenance_missing():
    with pytest.raises(ProvenanceMissingError):
        load_cost_profile(VENDOR_EXAMPLES / "invalid" / "cost-reported-without-source.json")


def test_cost_profile_unsupported_field_is_rejected():
    with pytest.raises(UnsupportedFieldError):
        load_cost_profile(FIXTURES / "cost-profile" / "unsupported-field.json")


# ---------------------------------------------------------------------------
# fleetlab's own profiles/examples/ must ingest cleanly: the GPU-reference
# family copied (attributed) from serving-contracts, plus fleetlab-authored
# profiles for the real, measured CPU/llama.cpp/Qwen2.5-1.5B environment.
# ---------------------------------------------------------------------------

PROFILES_EXAMPLES = Path(__file__).resolve().parents[2] / "profiles" / "examples"


def test_fleetlab_hardware_profile_example_ingests_cleanly():
    hp = load_hardware_profile(PROFILES_EXAMPLES / "hardware-a10g-g5-xlarge.json")
    assert hp.gpu_model == "NVIDIA A10G"


def test_fleetlab_model_profile_examples_ingest_cleanly():
    mp = load_model_profile(PROFILES_EXAMPLES / "model-llama31-8b.json")
    assert "Llama-3.1" in mp.checkpoint_id

    qwen = load_model_profile(PROFILES_EXAMPLES / "model-qwen2.5-1.5b-instruct-gguf-q4km.json")
    assert "Qwen" in qwen.checkpoint_id
    assert qwen.kv_cache_bytes_per_token is not None


def test_fleetlab_cost_profile_example_ingests_cleanly():
    cp = load_cost_profile(PROFILES_EXAMPLES / "cost-g5-xlarge-ondemand.json")
    assert cp.currency == "USD"


def test_fleetlab_slo_profile_examples_ingest_cleanly():
    slo = load_slo(PROFILES_EXAMPLES / "slo-chat-interactive.json")
    assert slo.scope == "model-serving"

    real = load_slo(PROFILES_EXAMPLES / "slo-scenario-b-llamacpp-cpu-shakedown.json")
    assert real.slo_id == "scenario-b-llamacpp-cpu-shakedown"
