"""Case-ledger invariant tests for the three-actor RVV scenario.

Reads JSONL case-ledger replica files from ``devlogs/rvv/`` and asserts
universal invariants (via the shared ``common`` library) plus RVV-specific
checks.

Actor set: ``reporter``, ``vendor``, ``vendor2``, ``case-actor``.

Universal invariants (1–15) are applied via ``common.py``.

RVV-specific invariants:
- ``invite_actor_to_case`` appears at least once (Vendor1 invites Vendor2).
- ``accept_invite_actor_to_case`` appears at least once (Vendor2 accepts).
- Vendor2 replica holds the complete log from genesis (late-joiner backfill).
- Reporter replica holds the complete log from genesis (late-joiner backfill).

All tests are tagged ``@pytest.mark.case_ledger_invariants``.  They skip
automatically when ``devlogs/rvv/`` is absent.

Spec: DEMOMA-09, CLP-07.
"""

from __future__ import annotations

import pytest

from test.ci.invariants.common import (
    check_late_joiner_has_full_history,
    check_semantic_type_count,
    load_devlogs,
)
from test.ci.invariants.universal_harness import make_universal_invariant_tests

_DEMO_NAME = "rvv"

#: Expected protocol semanticTypes in a complete RVV run.
_RVV_EXPECTED_SEMANTIC_TYPES = [
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
    # DEMOMA-16-003: Vendor1 invites Vendor2; Vendor2 accepts.
    pytest.param("invite_actor_to_case", id="invite_actor_to_case"),
    pytest.param(
        "accept_invite_actor_to_case", id="accept_invite_actor_to_case"
    ),
]

#: Actors with per-actor chain / contiguity / completeness checks.
_CHAIN_ACTORS = [
    pytest.param("case-actor"),
    pytest.param("vendor"),
    pytest.param("vendor2"),
    pytest.param("reporter"),
]


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def rvv_replicas() -> dict[str, list[dict]]:
    """Load RVV scenario JSONL files grouped by actor name."""
    return load_devlogs(demo_name=_DEMO_NAME)


# ---------------------------------------------------------------------------
# Universal invariants (injected from universal_harness)
# ---------------------------------------------------------------------------

globals().update(
    make_universal_invariant_tests(
        replicas_fixture="rvv_replicas",
        chain_actors=_CHAIN_ACTORS,
        expected_semantic_types=_RVV_EXPECTED_SEMANTIC_TYPES,
        narrative_path="docs/topics/scenarios/rvv.md",
        joined_invitees=1,
    )
)


# ---------------------------------------------------------------------------
# RVV-specific invariants
# ---------------------------------------------------------------------------


@pytest.mark.case_ledger_invariants
def test_rvv_invite_actor_to_case_present(
    rvv_replicas: dict[str, list[dict]],
) -> None:
    """``invite_actor_to_case`` appears at least once (Vendor1 invites Vendor2).

    Spec: DEMOMA-09-002.
    """
    violations = check_semantic_type_count(
        rvv_replicas, "invite_actor_to_case", min_count=1
    )
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_rvv_vendor2_late_joiner_has_full_history(
    rvv_replicas: dict[str, list[dict]],
) -> None:
    """Vendor2 replica contains all logIndex values present in vendor replica.

    Vendor2 is a late joiner and must receive the full ledger backfill.
    Spec: DEMOMA-09-004 (LedgerFanout convergence).
    """
    if not rvv_replicas.get("vendor") or not rvv_replicas.get("vendor2"):
        pytest.skip(
            "vendor or vendor2 replica absent; cannot check late-joiner invariant"
        )
    violations = check_late_joiner_has_full_history(
        rvv_replicas, early_actor="vendor", late_actor="vendor2"
    )
    assert not violations, "\n".join(violations)


@pytest.mark.case_ledger_invariants
def test_rvv_reporter_late_joiner_has_full_history(
    rvv_replicas: dict[str, list[dict]],
) -> None:
    """Reporter replica contains all logIndex values present in vendor replica.

    Reporter is seeded by the CaseActor's trust-bootstrap Announce after
    Vendor1 validates the report; the CaseActor must backfill all prior
    entries to Reporter.
    Spec: DEMOMA-09-004 (LedgerFanout convergence).
    """
    if not rvv_replicas.get("vendor") or not rvv_replicas.get("reporter"):
        pytest.skip(
            "vendor or reporter replica absent; cannot check late-joiner invariant"
        )
    violations = check_late_joiner_has_full_history(
        rvv_replicas, early_actor="vendor", late_actor="reporter"
    )
    assert not violations, "\n".join(violations)
