"""Ground-truth system parameters for the signal comparison (FL-T006),
derived from the FL-T004 fitted, **G8-within-error** profile.

Why this specific profile. Three profiles exist under `profiles/fitted/`:
the two `admission-sane-v1`/`v1b` (ib-t010) configs, whose G8 outcome is a
documented **MISS** (12.6-20.4% capacity error, latency PENDING), and the
`gateway-mock-flags-v1-conncap2` (ib-t008 sweep) config, whose G8 outcome is
**WITHIN STATED ERROR** for capacity and has a FITTED latency profile. Using
a MISS profile as "ground truth" for a signal-comparison simulation would
silently launder a documented modeling limitation into this task's results;
the sweep profile is the only one honest to use as the simulation's known
capacity/latency law. See `docs/notes/fitting-method.md` and
`reports/holdout-validation.md` §2b.

Deriving a per-server service-time distribution from the fitted capacity.
The capacity-clamp model (`fleetlab.fitting.capacity`) fits a throughput
ceiling `capacity_rps` for a specific disclosed client-side concurrency cap
(`concurrency_cap_disclosure.concurrency_cap`, held fixed across the whole
sweep) -- structurally the same role `num_servers` plays in
`fleetlab.dynamics.simulate_queue`'s G/G/c model (a bounded number of
concurrent in-flight slots). Treating the concurrency cap as `num_servers`
and solving `capacity_rps = num_servers / mean_service_time_seconds` for the
per-request mean service time (the standard `c` identical-server throughput
identity at saturation) gives a G/G/c-compatible service-time distribution
consistent with the fitted throughput ceiling.

This deliberately does NOT use the fitted `l0_seconds` latency parameter as
the service time: `l0` is a *multiplicative*-model artifact whose own
functional-form misfit is already documented (`docs/notes/fitting-method.md`
§4 -- the implied `l0` falls from 55ms to 18ms across training points because
the real target latency is additive, not multiplicative). Reusing it here
would compound a known limitation into a second task. The
`num_servers / capacity_rps` derivation uses only the capacity fit (the
G8-passing half of the profile), which is the more conservative choice.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROFILE_PATH = (
    REPO_ROOT
    / "profiles"
    / "fitted"
    / "mock-loopback-cpu-dev__mock-8b__gateway-mock-flags-v1-conncap2.json"
)


@dataclass(frozen=True)
class GroundTruthSystem:
    profile_id: str
    profile_path: Path
    capacity_rps: float
    capacity_rps_stderr: float
    num_servers: int
    mean_service_time_seconds: float
    l0_seconds: float
    l0_seconds_stderr: float
    basis: str
    concurrency_cap_note: str


def load_ground_truth_system(path: Optional[Path] = None) -> GroundTruthSystem:
    """Load the fitted sweep profile and derive the G/G/c parameters used as
    ground truth throughout `fleetlab/signals/`. Raises if the profile's own
    G8 outcome is not the within-error one (a hard guard against silently
    swapping in a MISS profile as ground truth in some future edit)."""
    path = Path(path) if path is not None else DEFAULT_PROFILE_PATH
    profile = json.loads(path.read_text())

    g8 = profile["holdout_validation"]["g8_outcome"]
    if "WITHIN STATED ERROR" not in g8:
        raise ValueError(
            f"{path}: profile's own g8_outcome does not read as a within-"
            "error pass -- refusing to use it as ground truth for the "
            f"signal comparison (g8_outcome={g8!r})"
        )
    if profile["latency_profile"]["status"] != "FITTED":
        raise ValueError(
            f"{path}: latency_profile.status is "
            f"{profile['latency_profile']['status']!r}, not FITTED -- this "
            "profile cannot supply the l0 parameter this module records "
            "(informational only; not used to derive service time, see "
            "module docstring)"
        )

    capacity_rps = float(profile["capacity_profile"]["capacity_rps"])
    num_servers = int(profile["concurrency_cap_disclosure"]["concurrency_cap"])
    if num_servers < 1:
        raise ValueError(f"{path}: concurrency_cap must be >= 1, got {num_servers}")

    return GroundTruthSystem(
        profile_id=profile["profile_id"],
        profile_path=path,
        capacity_rps=capacity_rps,
        capacity_rps_stderr=float(profile["capacity_profile"]["capacity_rps_stderr"]),
        num_servers=num_servers,
        mean_service_time_seconds=num_servers / capacity_rps,
        l0_seconds=float(profile["latency_profile"]["l0_seconds"]),
        l0_seconds_stderr=float(profile["latency_profile"]["l0_seconds_stderr"]),
        basis=profile["basis"],
        concurrency_cap_note=profile["concurrency_cap_disclosure"]["note"],
    )
