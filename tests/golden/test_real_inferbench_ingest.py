"""FL-T002 stop condition: real inferbench / inference-lab files ingest cleanly.

This module has two tiers:

1. A committed subset (`tests/golden/fixtures/real/`) — unmodified copies of
   real evidence, always present, always exercised. This is what keeps the
   suite green in a fleetlab-only checkout.
2. A full-corpus sweep of the sibling repos' evidence directories
   (`/home/user/inferbench`, `/home/user/inference-lab`), run only when those
   directories are present on disk (this program's repos share one host
   during development; a fleetlab-only checkout skips this tier rather than
   failing). This is the tier that produced the real counts recorded in
   `docs/implementation-notes.md` (FL-T002 evidence).

Two files under inference-lab's `evidence/i3/aborted/` are session-truncated
JSONL (the process was interrupted mid-write; `notes.md` documents both
aborted attempts as excluded from every acceptance number). fleetlab's
refusal of those two files is the CORRECT behavior — a truncated record must
never be silently skipped — and is asserted explicitly below, not treated as
a suite failure.
"""

from pathlib import Path

import pytest

from fleetlab.ingest import (
    IngestError,
    RecordParseError,
    load_benchmark_result,
    load_benchmark_run,
    load_raw_events,
    load_workload,
)

FIXTURES = Path(__file__).parent / "fixtures" / "real"

INFERBENCH = Path("/home/user/inferbench")
INFERENCE_LAB = Path("/home/user/inference-lab")

KNOWN_TRUNCATED = {
    # documented in inference-lab/evidence/i3/notes.md: aborted session, the
    # process was killed mid-write; excluded from every acceptance number.
    INFERENCE_LAB
    / "evidence/i3/aborted/attempt-2-interrupted-2026-07-11/shared-prefix-cpu-partial/events.jsonl",
    INFERENCE_LAB
    / "evidence/i3/aborted/attempt-1-2026-07-11/raw/runs/chat-short-cpu-direct/events.jsonl",
}


# ---------------------------------------------------------------------------
# tier 1: committed subset, always runs
# ---------------------------------------------------------------------------


def test_committed_real_workloads_ingest_cleanly():
    files = sorted((FIXTURES / "workloads").glob("*.json"))
    assert len(files) == 3
    for f in files:
        load_workload(f)


def test_committed_real_manifests_ingest_cleanly():
    files = sorted(FIXTURES.glob("runs/*/manifest.json"))
    assert len(files) == 2
    for f in files:
        load_benchmark_run(f)


def test_committed_real_events_ingest_cleanly():
    files = sorted(FIXTURES.glob("runs/*/events.jsonl"))
    assert len(files) == 2
    total = 0
    for f in files:
        events = load_raw_events(f)
        assert len(events) > 0
        total += len(events)
    assert total > 0


def test_committed_real_results_ingest_cleanly():
    files = sorted((FIXTURES / "results").glob("*.json"))
    assert len(files) == 2
    for f in files:
        load_benchmark_result(f)


# ---------------------------------------------------------------------------
# tier 2: full-corpus sweep, best-effort (skips if sibling repos are absent)
# ---------------------------------------------------------------------------


def _require_sibling_repos():
    if not (INFERBENCH.is_dir() and INFERENCE_LAB.is_dir()):
        pytest.skip(
            "sibling repos /home/user/inferbench and /home/user/inference-lab "
            "not present; full-corpus sweep skipped (committed subset above "
            "still covers the golden-file suite)"
        )


def test_full_corpus_canonical_workloads_ingest_cleanly():
    _require_sibling_repos()
    files = sorted((INFERBENCH / "workloads").glob("*.json"))
    assert len(files) == 8, "canonical suite is 8 named workloads (IB-T003)"
    for f in files:
        load_workload(f)


def test_full_corpus_manifests_ingest_cleanly():
    _require_sibling_repos()
    manifests = sorted(
        list((INFERBENCH / "docs/evidence").glob("**/manifest.json"))
        + list((INFERENCE_LAB / "evidence").glob("**/manifest.json"))
    )
    assert len(manifests) >= 40
    failures = []
    for f in manifests:
        try:
            load_benchmark_run(f)
        except IngestError as exc:
            failures.append((f, exc))
    assert not failures, f"unexpected manifest refusals: {failures}"


def test_full_corpus_events_ingest_cleanly_or_are_known_truncated():
    _require_sibling_repos()
    event_files = sorted(
        list((INFERBENCH / "docs/evidence").glob("**/events.jsonl"))
        + list((INFERENCE_LAB / "evidence").glob("**/events.jsonl"))
    )
    assert len(event_files) >= 40
    ok = 0
    known_bad = 0
    unexpected_failures = []
    total_events = 0
    for f in event_files:
        try:
            total_events += len(load_raw_events(f))
            ok += 1
        except RecordParseError:
            if f in KNOWN_TRUNCATED:
                known_bad += 1
            else:
                unexpected_failures.append(f)
        except IngestError as exc:
            unexpected_failures.append((f, exc))
    assert not unexpected_failures, f"unexpected event-file refusals: {unexpected_failures}"
    assert known_bad == len(KNOWN_TRUNCATED), (
        f"expected exactly the {len(KNOWN_TRUNCATED)} documented aborted-session "
        f"truncated files to refuse, saw {known_bad}"
    )
    assert ok >= 40
    assert total_events > 10_000


def test_full_corpus_results_ingest_cleanly():
    _require_sibling_repos()
    results = sorted(
        list((INFERBENCH / "docs/evidence/ib-t005/results").glob("*.json"))
        + list((INFERENCE_LAB / "evidence/i3/raw/results").glob("*.json"))
    )
    assert len(results) >= 8
    for f in results:
        load_benchmark_result(f)
