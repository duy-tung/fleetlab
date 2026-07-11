"""Consumption-side dry-run validation script (FL-T009).

Once inferops applies a capacity-recommendation's topology change and
re-measures the referenced workload, THIS is what checks the outcome
against the recommendation's own stated bounds -- the machine-checkable
half of the I6 loop's "predicted vs measured, published, including where
the prediction was wrong" acceptance criterion.

**Status: PENDING-on-RQ-14.** inferops' runtime environment decision (which
Kubernetes/observability stack to run against) is not yet made, so this
task's own stop condition ("recommendation consumed by inferops in a dry
run") cannot execute for real yet -- recorded honestly in
`docs/implementation-notes.md`, not skipped silently. This script is
written and tested NOW (`tests/emit/test_dry_run_validate.py`, against a
synthetic-but-clearly-labeled post-change fixture) so it is ready to run
the moment a real post-change benchmark-result exists; the real
recommendation this repo emits (`examples/recommendations/`) names this
script in its top-level `notes` field for exactly that purpose.

Usage:
    python3 -m fleetlab.emit.dry_run_validate \\
        --recommendation examples/recommendations/<file>.json \\
        --applied-topology applied-topology.json \\
        --post-change-result post-change-result.benchmark-result.json

`applied-topology.json` shape: `{"replica_groups": [{"replica_count": N, ...}, ...]}`
(the same shape `recommended_topology.replica_groups` uses, describing what
inferops actually deployed -- may differ from what was recommended, which
is itself worth checking).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    detail: str


def check_replica_count_applied(recommendation: dict, applied_replica_groups: List[dict]) -> CheckResult:
    """Did inferops actually deploy the recommended total replica count?
    (A dry run can apply something other than what was recommended --
    this check makes that visible rather than assuming compliance.)"""
    expected = sum(g["replica_count"] for g in recommendation["recommended_topology"]["replica_groups"])
    actual = sum(g["replica_count"] for g in applied_replica_groups)
    return CheckResult(
        "replica_count_applied",
        actual == expected,
        f"expected total replica_count={expected}, applied={actual}",
    )


def check_goodput_meets_lower_bound(recommendation: dict, post_change_result: dict) -> CheckResult:
    """Does the re-measured goodput meet the recommendation's own stated
    uncertainty lower bound? A miss here is exactly the honest "predicted
    vs measured, including where the prediction was wrong" result the I6
    loop is built to surface -- not a script failure."""
    predicted = recommendation["predictions"]["goodput"]["requests_per_second_meeting_slo"]
    lower = predicted["uncertainty"]["lower"]
    actual = post_change_result["goodput"]["requests_per_second_meeting_slo"]
    return CheckResult(
        "goodput_meets_lower_bound",
        actual >= lower,
        f"predicted lower bound={lower}, measured={actual}",
    )


def check_latency_within_upper_bound(
    recommendation: dict, post_change_result: dict, *, signal: str = "e2e_duration_seconds_p95"
) -> CheckResult:
    """Does the re-measured latency statistic (Contract-2-named,
    `<signal>_<statistic>` per Contract 7's `predictions.latency` key
    pattern) stay within the recommendation's stated upper bound?"""
    predicted = recommendation["predictions"]["latency"][signal]
    upper = predicted["uncertainty"]["upper"]
    base_signal, _, statistic = signal.rpartition("_")
    actual = post_change_result["pooled_percentiles"]["tables"][base_signal][statistic]
    return CheckResult(
        "latency_within_upper_bound",
        actual <= upper,
        f"predicted upper bound={upper}, measured {signal}={actual}",
    )


def run_dry_run_validation(
    recommendation: dict, applied_replica_groups: List[dict], post_change_result: dict
) -> List[CheckResult]:
    return [
        check_replica_count_applied(recommendation, applied_replica_groups),
        check_goodput_meets_lower_bound(recommendation, post_change_result),
        check_latency_within_upper_bound(recommendation, post_change_result),
    ]


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Consumption-side dry-run validation for a fleetlab capacity-recommendation (PENDING-on-RQ-14; see module docstring)."
    )
    parser.add_argument("--recommendation", required=True, type=Path)
    parser.add_argument(
        "--applied-topology",
        required=True,
        type=Path,
        help='JSON file: {"replica_groups": [{"replica_count": N, ...}, ...]} -- what inferops actually deployed',
    )
    parser.add_argument(
        "--post-change-result",
        required=True,
        type=Path,
        help="benchmark-result.json measured after applying the recommendation",
    )
    args = parser.parse_args(argv)

    recommendation = json.loads(args.recommendation.read_text())
    applied = json.loads(args.applied_topology.read_text())["replica_groups"]
    post_change_result = json.loads(args.post_change_result.read_text())

    results = run_dry_run_validation(recommendation, applied, post_change_result)
    all_passed = True
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"{status}  {r.name}: {r.detail}")
        all_passed = all_passed and r.passed
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
