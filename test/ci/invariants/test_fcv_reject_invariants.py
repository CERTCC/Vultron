"""Case-ledger invariant tests for the FCV-Reject three-actor scenario.

Reads JSONL case-ledger replica files from ``devlogs/fcv-reject/`` and
asserts universal invariants (via the shared ``common`` library) plus
FCV-Reject-specific checks.

Actor set: ``finder``, ``coordinator``, ``case-actor``.
Vendor is intentionally absent: it rejected the invitation and was never
added as a case participant, so it has no case ledger replica.

FCV-Reject-specific invariants (issue #2047):
- ``validate_report`` event type is present (Coordinator validates Finder's report).
- ``invite_actor_to_case`` appears at least once (Coordinator invites Vendor).
- ``reject_invite_actor_to_case`` appears at least once (Vendor's rejection recorded).
- ``accept_invite_actor_to_case`` is absent (Vendor rejected, never accepted).
- ``close_case`` event type is present.
- P-transition observed in Coordinator's add_participant_status entries.
- Vendor replica is absent from devlogs (Vendor was never a participant).

All tests are tagged ``@pytest.mark.case_ledger_invariants``.  They skip
automatically when ``devlogs/fcv-reject/`` is absent.

Spec: GitHub issue #2047, CLP-07.
"""

from __future__ import annotations

import pytest

from test.ci.invariants.common import (
    check_event_type_present,
    cs_observations_from_snap,
    event_type,
    load_devlogs,
    payload,
)
from test.ci.invariants.universal_harness import make_universal_invariant_tests

_DEMO_NAME = "fcv-reject"

#: Expected protocol eventTypes in a complete FCV-Reject run.
_FCV_REJECT_EXPECTED_EVENT_TYPES = [
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

#: Actors that have ledger replicas in the FCV-Reject scenario.
#: Vendor is absent — it rejected the invitation and was never a participant.
_CHAIN_ACTORS = [
    pytest.param("case-actor"),
    pytest.param("coordinator"),
    pytest.param("finder"),
]


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fcv_reject_replicas() -> dict[str, list[dict]]:
    """Load FCV-Reject scenario JSONL files grouped by actor name."""
    return load_devlogs(demo_name=_DEMO_NAME)


# ---------------------------------------------------------------------------
# Universal invariants (injected from universal_harness)
# ---------------------------------------------------------------------------

globals().update(
    make_universal_invariant_tests(
        replicas_fixture="fcv_reject_replicas",
        chain_actors=_CHAIN_ACTORS,
        expected_event_types=_FCV_REJECT_EXPECTED_EVENT_TYPES,
        check_fix_ready=False,
    )
)


# ---------------------------------------------------------------------------
# FCV-Reject-specific invariants (issue #2047)
# ---------------------------------------------------------------------------


@pytest.mark.case_ledger_invariants
def test_fcv_reject_validate_report_present(
    fcv_reject_replicas: dict[str, list[dict]],
) -> None:
    """``validate_report`` event type is present in the log.

    Spec: Coordinator validates Finder's report (Phase 1).
    """
    violations = check_event_type_present(
        fcv_reject_replicas, "validate_report"
    )
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_fcv_reject_invite_actor_to_case_present(
    fcv_reject_replicas: dict[str, list[dict]],
) -> None:
    """``invite_actor_to_case`` appears at least once (Coordinator invited Vendor).

    Spec: issue #2047 — Coordinator invites Vendor via invite-actor-to-case.
    """
    violations = check_event_type_present(
        fcv_reject_replicas, "invite_actor_to_case"
    )
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_fcv_reject_reject_invite_actor_to_case_present(
    fcv_reject_replicas: dict[str, list[dict]],
) -> None:
    """``reject_invite_actor_to_case`` appears at least once (Vendor's rejection).

    Spec: issue #2047 AC-1 — Vendor sends RI (RM.INVALID) then RC (RM.CLOSED);
    the CaseActor records a reject_invite_actor_to_case ledger entry.
    """
    violations = check_event_type_present(
        fcv_reject_replicas, "reject_invite_actor_to_case"
    )
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_fcv_reject_accept_invite_absent(
    fcv_reject_replicas: dict[str, list[dict]],
) -> None:
    """``accept_invite_actor_to_case`` is absent (Vendor rejected, never accepted).

    Spec: issue #2047 AC-2 — Vendor does NOT appear in the final participant list.
    If this event appears, it means the rejection path incorrectly also accepted.
    """
    all_entries = [
        e for entries in fcv_reject_replicas.values() for e in entries
    ]
    bad = [
        e
        for e in all_entries
        if event_type(e) == "accept_invite_actor_to_case"
    ]
    assert not bad, (
        f"Found {len(bad)} unexpected accept_invite_actor_to_case entries "
        f"(Vendor should have rejected, not accepted): "
        + str([e.get("log_index") for e in bad])
    )


@pytest.mark.case_ledger_invariants
def test_fcv_reject_vendor_has_no_replica(
    fcv_reject_replicas: dict[str, list[dict]],
) -> None:
    """Vendor has no case ledger replica (was never added as a participant).

    Spec: issue #2047 AC-2 — Vendor is not in the final participant list.
    """
    assert "vendor" not in fcv_reject_replicas, (
        "Vendor has a case ledger replica but should not: "
        "Vendor rejected the invitation and was never a case participant."
    )


@pytest.mark.case_ledger_invariants
def test_fcv_reject_close_case_present(
    fcv_reject_replicas: dict[str, list[dict]],
) -> None:
    """``close_case`` event type is present in the log.

    Spec: issue #2047 AC-1 — case reaches terminal RM.CLOSED.
    """
    violations = check_event_type_present(fcv_reject_replicas, "close_case")
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_fcv_reject_coordinator_p_transition_observed(
    fcv_reject_replicas: dict[str, list[dict]],
) -> None:
    """P-transition observed in Coordinator's add_participant_status entries.

    The Coordinator as CASE_OWNER triggers CS.P.
    """
    coordinator_entries = fcv_reject_replicas.get("coordinator")
    if not coordinator_entries:
        pytest.skip(
            "coordinator replica absent; cannot check Coordinator P-transition"
        )

    status_entries = [
        e
        for e in coordinator_entries
        if event_type(e) == "add_participant_status_to_participant"
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
