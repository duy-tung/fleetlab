"""Tests for `fleetlab.signals.ground_truth` (FL-T006)."""

from __future__ import annotations

import json

import pytest

from fleetlab.signals.ground_truth import DEFAULT_PROFILE_PATH, load_ground_truth_system


def test_load_ground_truth_system_default_profile():
    gt = load_ground_truth_system()
    assert gt.profile_id == "mock-loopback-cpu-dev__mock-8b__gateway-mock-flags-v1-conncap2"
    assert gt.num_servers == 2
    assert gt.capacity_rps == pytest.approx(26.15722104139299)
    assert gt.mean_service_time_seconds == pytest.approx(gt.num_servers / gt.capacity_rps)
    assert gt.basis == "measured"


def test_load_ground_truth_system_refuses_a_g8_miss_profile(tmp_path):
    miss_profile = json.loads(DEFAULT_PROFILE_PATH.read_text())
    miss_profile["holdout_validation"]["g8_outcome"] = "MISS documented as a limitation"
    bad_path = tmp_path / "miss-profile.json"
    bad_path.write_text(json.dumps(miss_profile))
    with pytest.raises(ValueError, match="within-error"):
        load_ground_truth_system(bad_path)


def test_load_ground_truth_system_refuses_a_pending_latency_profile(tmp_path):
    pending_profile = json.loads(DEFAULT_PROFILE_PATH.read_text())
    pending_profile["latency_profile"]["status"] = "PENDING"
    bad_path = tmp_path / "pending-latency-profile.json"
    bad_path.write_text(json.dumps(pending_profile))
    with pytest.raises(ValueError, match="FITTED"):
        load_ground_truth_system(bad_path)


def test_load_ground_truth_system_refuses_zero_concurrency_cap(tmp_path):
    bad_profile = json.loads(DEFAULT_PROFILE_PATH.read_text())
    bad_profile["concurrency_cap_disclosure"]["concurrency_cap"] = 0
    bad_path = tmp_path / "zero-cap-profile.json"
    bad_path.write_text(json.dumps(bad_profile))
    with pytest.raises(ValueError, match="concurrency_cap"):
        load_ground_truth_system(bad_path)
