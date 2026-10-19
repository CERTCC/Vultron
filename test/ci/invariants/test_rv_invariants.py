"""Case-ledger invariant tests for the rv (Reporter + Vendor) scenario.

Reads JSONL case-ledger replica files from ``devlogs/rv/`` and
asserts all universal invariants via the shared ``common`` library plus
rv-specific checks.

All tests are tagged ``@pytest.mark.case_ledger_invariants``.  They skip
automatically when ``devlogs/`` or ``devlogs/rv/`` is absent, so they
are safe to include in the regular unit-test collection.

Spec: CLP-07.
"""

from __future__ import annotations

import pytest

from test.ci.invariants.common import (
    check_late_joiner_has_full_history,
    load_devlogs,
)
from test.ci.invariants.universal_harness import make_universal_invariant_tests

_DEMO_NAME = "rv"

#: Expected protocol semanticTypes in a complete rv run.
_RV_EXPECTED_SEMANTIC_TYPES = [
    pytest.param("validate_report", id="validate_report"),
    pytest.param(
        "add_participant_status_to_participant",
        id="add_participant_status_to_participant",
    ),
    pytest.param("close_case", id="close_case"),
    pytest.param("add_note_to_case", id="add_note_to_case"),
    # DEMOMA-16-001: universal — the shared RM-triage helpers in
    # vultron/demo/helpers/workflow.py engage the case in every scenario.
    pytest.param("engage_case", id="engage_case"),
]

#: Actors with per-actor hash-chain / contiguity / completeness checks.
_CHAIN_ACTORS = [
    pytest.param("case-actor"),
    pytest.param("vendor"),
    pytest.param("reporter"),
]


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def rv_replicas() -> dict[str, list[dict]]:
    """Load rv scenario JSONL files grouped by actor name."""
    return load_devlogs(demo_name=_DEMO_NAME)


# ---------------------------------------------------------------------------
# Universal invariants (injected from universal_harness)
# ---------------------------------------------------------------------------

globals().update(
    make_universal_invariant_tests(
        replicas_fixture="rv_replicas",
        chain_actors=_CHAIN_ACTORS,
        expected_semantic_types=_RV_EXPECTED_SEMANTIC_TYPES,
        narrative_path="docs/topics/scenarios/rv.md",
    )
)


# ---------------------------------------------------------------------------
# rv-specific invariants
# ---------------------------------------------------------------------------
#
# The rv scenario has no scenario-specific ledger invariant beyond
# the universal set: the Reporter joins by submitting a report (which creates the
# case), never via an ``invite_actor_to_case`` activity, so no invite event is
# expected in this ledger.  Scenarios that invite a mid-case participant (RVV,
# RVCV-extension, RVCV-handoff) assert the invite event in their own files.


@pytest.mark.case_ledger_invariants
def test_invariant_8_late_joiner_has_full_history(
    rv_replicas: dict[str, list[dict]],
) -> None:
    """Reporter replica contains all logIndex values present in the vendor replica.

    The reporter joins after report-to-case promotion; pre-join entries must be
    backfilled.
    """
    if not rv_replicas.get("vendor") or not rv_replicas.get("reporter"):
        pytest.skip(
            "vendor or reporter replica absent; cannot check late-joiner invariant"
        )
    violations = check_late_joiner_has_full_history(
        rv_replicas, early_actor="vendor", late_actor="reporter"
    )
    assert not violations, "\n".join(violations)
