"""Regenerates `profiles/fitted/*.json` from the committed real-data fixtures
(FL-T004 deliverable). Deterministic: every number here is either read
verbatim from a real file or derived by the closed-form fits in this
package — there is no RNG, so there is nothing to seed.

Run: `python3 -m fleetlab.fitting.build_profiles`

The published profile per engine-config trains on the **baseline** (~1x the
probe-estimated capacity) point and holds out the **overload** (~5x) point —
"does a profile calibrated at normal load correctly predict the 5x-burst
case" is exactly the question `fleetlab/dynamics/` (FL-T005) needs answered.
Both directions are evaluated and recorded in `reports/holdout-validation.md`
for completeness; only the baseline-trained direction is persisted as the
config's canonical fitted profile.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from fleetlab.fitting import HoldoutSplit, evaluate_holdout, fit_profile
from fleetlab.fitting.corpus import load_corpus_point

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fitting" / "fixtures" / "real" / "ib-t010"
OUT_DIR = REPO_ROOT / "profiles" / "fitted"

# Canonical inferbench paths these fixtures are byte-identical copies of
# (provenance display — see tests/fitting/fixtures/real/README.md).
CANONICAL_PREFIX = "inferbench/docs/evidence/ib-t010/"

AS_OF = "2026-07-11"


def _canonical(path: Path) -> str:
    return CANONICAL_PREFIX + str(path.relative_to(FIXTURES))


def _load(result_name, workload_name, manifest_dir, engine_config_id):
    result_path = FIXTURES / "results" / result_name
    workload_path = FIXTURES / workload_name
    manifest_path = FIXTURES / manifest_dir / "manifest.json"
    point = load_corpus_point(
        result_path=result_path,
        workload_path=workload_path,
        manifest_path=manifest_path,
        hardware_id="mock-loopback-cpu-dev",
        model_id="mock-8b",
        engine_config_id=engine_config_id,
    )
    return point, [
        _canonical(result_path),
        _canonical(workload_path),
        _canonical(manifest_path),
    ]


def _build_one(name: str, engine_config_id: str, baseline_args, overload_args) -> dict:
    baseline, baseline_srcs = _load(*baseline_args, engine_config_id)
    overload, overload_srcs = _load(*overload_args, engine_config_id)

    split = HoldoutSplit(
        train_run_ids=frozenset({baseline.run_id}),
        holdout_run_ids=frozenset({overload.run_id}),
    )
    profile = fit_profile([baseline, overload], split)
    report = evaluate_holdout(profile, [overload])
    (holdout_result,) = report.points

    # reverse direction, for the robustness note only -- NOT persisted as
    # this config's canonical profile (see module docstring).
    reverse_split = HoldoutSplit(
        train_run_ids=frozenset({overload.run_id}),
        holdout_run_ids=frozenset({baseline.run_id}),
    )
    reverse_profile = fit_profile([baseline, overload], reverse_split)
    reverse_report = evaluate_holdout(reverse_profile, [baseline])
    (reverse_holdout_result,) = reverse_report.points

    return {
        "profile_id": name,
        "as_of": AS_OF,
        "basis": "measured",
        "hardware": {
            "id": profile.hardware_id,
            "label": (
                "mock backend (gateway-mediated loopback, local-dev-container, "
                "linux/amd64, 4 vCPU, CPU-only) -- NOT real hardware; profiled "
                "here for loop-mechanics purposes only, per FL-T004 scope "
                "decision. See docs/notes/fitting-method.md."
            ),
        },
        "model": {
            "id": profile.model_id,
            "label": "mock engine checkpoint 'mock-8b' (mockengine@6827d8c) -- simulated, not real weights",
        },
        "engine_config_id": profile.engine_config_id,
        "capacity_profile": {
            "capacity_rps": profile.capacity_fit.capacity_rps,
            "capacity_rps_stderr": profile.capacity_fit.capacity_rps_stderr,
            "model": "achieved_rps(offered) = min(offered, capacity_rps)",
            "fitted_parameters": 1,
            "training_points": 1,
            "basis": "measured",
        },
        "latency_profile": {
            "status": "PENDING",
            "reason": profile.latency_pending_reason,
            "data_requirement": (
                "one calibration run for this engine_config_id at an offered "
                "rate clearly (>=20%) below the fitted capacity_rps above -- "
                "see docs/notes/fitting-method.md"
            ),
        },
        "holdout_validation": {
            "train_run_id": baseline.run_id,
            "holdout_run_id": overload.run_id,
            "holdout_offered_rate_rps": holdout_result.offered_rate_rps,
            "holdout_actual_achieved_rps": holdout_result.actual_achieved_rps,
            "holdout_predicted_achieved_rps": holdout_result.predicted_achieved_rps,
            "abs_error_rps": holdout_result.abs_error_rps,
            "rel_error": holdout_result.rel_error,
            "measurement_stderr_rps": holdout_result.measurement_stderr_rps,
            "error_vs_measurement_noise_ratio": abs(holdout_result.abs_error_rps)
            / holdout_result.measurement_stderr_rps,
            "g8_outcome": (
                "MISS documented as a limitation, per FL-T004 stop condition "
                "(prediction error is a result, not a failure): the model "
                "mis-predicts achieved throughput at 5x offered load by "
                f"{abs(holdout_result.rel_error) * 100:.1f}% "
                f"({'under' if holdout_result.rel_error < 0 else 'over'}-predicting), "
                "several times the measurement-noise floor -- a genuine "
                "limitation of the single-parameter capacity-clamp model, "
                "not sampling noise. See reports/holdout-validation.md."
            ),
        },
        "reverse_direction_robustness_check": {
            "train_run_id": overload.run_id,
            "holdout_run_id": baseline.run_id,
            "rel_error": reverse_holdout_result.rel_error,
            "note": "NOT the canonical profile; recorded to show the miss is symmetric in scale regardless of fit direction.",
        },
        "provenance": {
            "source_run_manifests": [baseline_srcs[2], overload_srcs[2]],
            "source_benchmark_results": [baseline_srcs[0], overload_srcs[0]],
            "source_workloads": [baseline_srcs[1], overload_srcs[1]],
            "fixture_copies_committed_at": str(
                (FIXTURES).relative_to(REPO_ROOT)
            ),
        },
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    e2 = _build_one(
        "mock-loopback-cpu-dev__mock-8b__gateway-mock-admission-sane-v1",
        "gateway-mock-admission-sane-v1",
        ("ib-t010-e2-baseline-1x-sane.benchmark-result.json", "e2-baseline-workload.json", "e2-baseline"),
        ("ib-t010-e2-overload-5x-sane.benchmark-result.json", "e2-overload-workload.json", "e2-overload-compare/sane"),
    )
    e2b = _build_one(
        "mock-loopback-cpu-dev__mock-8b__gateway-mock-admission-sane-v1b",
        "gateway-mock-admission-sane-v1b",
        ("ib-t010-e2b-baseline-1x-sane.benchmark-result.json", "e2-baseline-workload.json", "e2b-baseline"),
        ("ib-t010-e2b-overload-5x-sane.benchmark-result.json", "e2-overload-workload.json", "e2b-overload"),
    )

    for profile in (e2, e2b):
        out_path = OUT_DIR / f"{profile['profile_id']}.json"
        out_path.write_text(json.dumps(profile, indent=2) + "\n")
        print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
