from fleetlab.dynamics.cold_start import MEASURED_COLD_START
from fleetlab.dynamics.scaling import ASSUMED_SCALING_DELAY


def test_scaling_delay_basis_is_assumed_not_measured():
    # FL-T005 review focus: assumed parameters must be explicitly flagged,
    # never presented as measured.
    assert ASSUMED_SCALING_DELAY.basis == "assumed"
    assert "assumed" in ASSUMED_SCALING_DELAY.rationale.lower()


def test_scale_up_seconds_composes_assumed_and_measured_parts():
    # scale_up = assumed scheduling overhead (10s) + measured warm load time
    assert ASSUMED_SCALING_DELAY.scale_up_seconds > MEASURED_COLD_START.warm_load_seconds
    assert (
        ASSUMED_SCALING_DELAY.scale_up_seconds - MEASURED_COLD_START.warm_load_seconds
    ) == 10.0


def test_scale_down_seconds_is_positive_and_documented():
    assert ASSUMED_SCALING_DELAY.scale_down_seconds > 0
    assert "drain" in ASSUMED_SCALING_DELAY.rationale.lower()
