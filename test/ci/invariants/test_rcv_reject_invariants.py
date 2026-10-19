"""Case-ledger invariant tests for the RCV-Reject three-actor scenario.

Reads JSONL case-ledger replica files from ``devlogs/rcv-reject/`` and
asserts universal invariants (via the shared ``common`` library) plus
RCV-Reject-specific checks.

Actor set: ``reporter``, ``coordinator``, ``case-actor``.
Vendor is intentionally absent: it rejected the invitation and was never
added as a case participant, so it has no case ledger replica.

RCV-Reject-specific invariants (issue #2047):
- ``validate_report`` semantic type is present (Coordinator validates Reporter's report).
- ``invite_actor_to_case`` appears at least once (Coordinator invites Vendor).
- ``reject_invite_actor_to_case`` appears at least once (Vendor's rejection recorded).
- ``accept_invite_actor_to_case`` is absent (Vendor rejected, never accepted).
- ``close_case`` semantic type is present.
- P-transition observed in Coordinator's add_participant_status entries.
- Vendor replica is absent from devlogs (Vendor was never a participant).

All tests are tagged ``@pytest.mark.case_ledger_invariants``.  They skip
automatically when ``devlogs/rcv-reject/`` is absent.

Spec: GitHub issue #2047, CLP-07.
"""

from __future__ import annotations

import pytest

from test.ci.invariants.common import (
    check_semantic_type_present,
    cs_observations_from_snap,
    load_devlogs,
    log_index,
    payload,
    semantic_type,
)
from test.ci.invariants.universal_harness import make_universal_invariant_tests

_DEMO_NAME = "rcv-reject"

#: Expected protocol semanticTypes in a complete RCV-Reject run.
_RCV_REJECT_EXPECTED_SEMANTIC_TYPES = [
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
    pytest.param("invite_actor_to_case", id="invite_actor_to_case"),
    pytest.param(
        "reject_invite_actor_to_case", id="reject_invite_actor_to_case"
    ),
]

#: Actors that have ledger replicas in the RCV-Reject scenario.
#: Vendor is absent — it rejected the invitation and was never a participant.
_CHAIN_ACTORS = [
    pytest.param("case-actor"),
    pytest.param("coordinator"),
    pytest.param("reporter"),
]


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def rcv_reject_replicas() -> dict[str, list[dict]]:
    """Load RCV-Reject scenario JSONL files grouped by actor name."""
    return load_devlogs(demo_name=_DEMO_NAME)


# ---------------------------------------------------------------------------
# Universal invariants (injected from universal_harness)
# ---------------------------------------------------------------------------

globals().update(
    make_universal_invariant_tests(
        replicas_fixture="rcv_reject_replicas",
        chain_actors=_CHAIN_ACTORS,
        expected_semantic_types=_RCV_REJECT_EXPECTED_SEMANTIC_TYPES,
        check_fix_ready=False,
        narrative_path="docs/topics/scenarios/rcv-reject.md",
    )
)


# ---------------------------------------------------------------------------
# RCV-Reject-specific invariants (issue #2047)
# ---------------------------------------------------------------------------


@pytest.mark.case_ledger_invariants
def test_rcv_reject_validate_report_present(
    rcv_reject_replicas: dict[str, list[dict]],
) -> None:
    """``validate_report`` semantic type is present in the log.

    Spec: Coordinator validates Reporter's report (Phase 1).
    """
    violations = check_semantic_type_present(
        rcv_reject_replicas, "validate_report"
    )
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_rcv_reject_invite_actor_to_case_present(
    rcv_reject_replicas: dict[str, list[dict]],
) -> None:
    """``invite_actor_to_case`` appears at least once (Coordinator invited Vendor).

    Spec: issue #2047 — Coordinator invites Vendor via invite-actor-to-case.
    """
    violations = check_semantic_type_present(
        rcv_reject_replicas, "invite_actor_to_case"
    )
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_rcv_reject_reject_invite_actor_to_case_present(
    rcv_reject_replicas: dict[str, list[dict]],
) -> None:
    """``reject_invite_actor_to_case`` appears at least once (Vendor's rejection).

    Spec: issue #2047 AC-1 — Vendor sends RI (RM.INVALID) then RC (RM.CLOSED);
    the CaseActor records a reject_invite_actor_to_case ledger entry.
    """
    violations = check_semantic_type_present(
        rcv_reject_replicas, "reject_invite_actor_to_case"
    )
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_rcv_reject_accept_invite_absent(
    rcv_reject_replicas: dict[str, list[dict]],
) -> None:
    """``accept_invite_actor_to_case`` is absent (Vendor rejected, never accepted).

    Spec: issue #2047 AC-2 — Vendor does NOT appear in the final participant list.
    If this event appears, it means the rejection path incorrectly also accepted.
    """
    all_entries = [
        e for entries in rcv_reject_replicas.values() for e in entries
    ]
    bad = [
        e
        for e in all_entries
        if semantic_type(e) == "accept_invite_actor_to_case"
    ]
    assert not bad, (
        f"Found {len(bad)} unexpected accept_invite_actor_to_case entries "
        f"(Vendor should have rejected, not accepted): "
        + str([log_index(e) for e in bad])
    )


@pytest.mark.case_ledger_invariants
def test_rcv_reject_vendor_has_no_replica(
    rcv_reject_replicas: dict[str, list[dict]],
) -> None:
    """Vendor has no case ledger replica (was never added as a participant).

    Spec: issue #2047 AC-2 — Vendor is not in the final participant list.
    """
    assert "vendor" not in rcv_reject_replicas, (
        "Vendor has a case ledger replica but should not: "
        "Vendor rejected the invitation and was never a case participant."
    )


@pytest.mark.case_ledger_invariants
def test_rcv_reject_close_case_present(
    rcv_reject_replicas: dict[str, list[dict]],
) -> None:
    """``close_case`` semantic type is present in the log.

    Spec: issue #2047 AC-1 — case reaches terminal RM.CLOSED.
    """
    violations = check_semantic_type_present(rcv_reject_replicas, "close_case")
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_rcv_reject_coordinator_p_transition_observed(
    rcv_reject_replicas: dict[str, list[dict]],
) -> None:
    """P-transition observed in Coordinator's add_participant_status entries.

    The Coordinator as CASE_OWNER triggers CS.P.
    """
    coordinator_entries = rcv_reject_replicas.get("coordinator")
    if not coordinator_entries:
        pytest.skip(
            "coordinator replica absent; cannot check Coordinator P-transition"
        )

    status_entries = [
        e
        for e in coordinator_entries
        if semantic_type(e) == "add_participant_status_to_participant"
    ]
    if not status_entries:
        pytest.skip(
            "No add_participant_status_to_participant entries in coordinator log"
        )

    saw_published = any(
        cs_observations_from_snap(payload(e))[2] for e in status_entries
    )
    assert saw_published, (
        "Coordinator: pxa_state starting with 'P' (public-aware) never observed "
        "in add_participant_status_to_participant entries"
    )
