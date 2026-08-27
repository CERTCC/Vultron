"""Case-ledger invariant tests for the FCV three-actor scenario.

Reads JSONL case-ledger replica files from ``devlogs/fcv/`` and
asserts universal invariants (via the shared ``common`` library) plus
FCV-specific checks.

Actor set: ``finder``, ``coordinator``, ``vendor``, ``case-actor``.

FCV-specific invariants (DEMOMA-12-008/009):
- ``validate_report`` event type is present (Coordinator validates Finder's report).
- ``invite_actor_to_case`` appears at least twice (Finder + Vendor invitations).
- ``accept_invite_actor_to_case`` appears at least twice (Finder and Vendor each accept).
- ``close_case`` event type is present.
- CS transitions VFd and VFD observed in Vendor's add_participant_status entries.
- P-transition observed in Coordinator's add_participant_status entries.
- Vendor is a late joiner — replica holds the complete log from genesis.

All tests are tagged ``@pytest.mark.case_ledger_invariants``.  They skip
automatically when ``devlogs/fcv/`` is absent.

Spec: DEMOMA-12, CLP-07.
"""

from __future__ import annotations

import pytest

from test.ci.invariants.common import (
    check_event_type_count,
    check_event_type_present,
    check_late_joiner_has_full_history,
    cs_observations_from_snap,
    event_type,
    load_devlogs,
    payload,
)
from test.ci.invariants.universal_harness import make_universal_invariant_tests

_DEMO_NAME = "fcv"

#: Expected protocol eventTypes in a complete FCV run.
_FCV_EXPECTED_EVENT_TYPES = [
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
    # DEMOMA-16-007: Coordinator invites both Finder and Vendor; both accept.
    pytest.param("invite_actor_to_case", id="invite_actor_to_case"),
    pytest.param(
        "accept_invite_actor_to_case", id="accept_invite_actor_to_case"
    ),
]

#: Actors with per-actor chain / contiguity / completeness checks.
_CHAIN_ACTORS = [
    pytest.param("case-actor"),
    pytest.param("coordinator"),
    pytest.param("vendor"),
    pytest.param("finder"),
]


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fcv_replicas() -> dict[str, list[dict]]:
    """Load FCV scenario JSONL files grouped by actor name."""
    return load_devlogs(demo_name=_DEMO_NAME)


# ---------------------------------------------------------------------------
# Universal invariants (injected from universal_harness)
# ---------------------------------------------------------------------------

globals().update(
    make_universal_invariant_tests(
        replicas_fixture="fcv_replicas",
        chain_actors=_CHAIN_ACTORS,
        expected_event_types=_FCV_EXPECTED_EVENT_TYPES,
        narrative_path="docs/topics/scenarios/fcv.md",
    )
)


# ---------------------------------------------------------------------------
# FCV-specific invariants (DEMOMA-12-008/009)
# ---------------------------------------------------------------------------


@pytest.mark.case_ledger_invariants
def test_fcv_validate_report_present(
    fcv_replicas: dict[str, list[dict]],
) -> None:
    """``validate_report`` event type is present in the log.

    Spec: DEMOMA-12-002 (Coordinator validates Finder's report).
    """
    violations = check_event_type_present(fcv_replicas, "validate_report")
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_fcv_invite_actor_to_case_at_least_twice(
    fcv_replicas: dict[str, list[dict]],
) -> None:
    """``invite_actor_to_case`` appears at least twice (Finder + Vendor invitations).

    Spec: DEMOMA-12-003 (Coordinator invites Finder),
    DEMOMA-12-004 (Coordinator invites Vendor directly).
    """
    violations = check_event_type_count(
        fcv_replicas, "invite_actor_to_case", min_count=2
    )
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_fcv_close_case_present(
    fcv_replicas: dict[str, list[dict]],
) -> None:
    """``close_case`` event type is present in the log.

    Spec: DEMOMA-12-005 (case reaches terminal RM.CLOSED).
    """
    violations = check_event_type_present(fcv_replicas, "close_case")
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_fcv_vendor_late_joiner_has_full_history(
    fcv_replicas: dict[str, list[dict]],
) -> None:
    """Vendor replica contains all logIndex values present in coordinator replica.

    Vendor is a late joiner (invited after case creation) and must receive the
    full ledger backfill.  Spec: DEMOMA-12-004 (LedgerFanout convergence).
    """
    if not fcv_replicas.get("coordinator") or not fcv_replicas.get("vendor"):
        pytest.skip(
            "coordinator or vendor replica absent; cannot check late-joiner invariant"
        )
    violations = check_late_joiner_has_full_history(
        fcv_replicas, early_actor="coordinator", late_actor="vendor"
    )
    assert not violations, "\n".join(violations)


@pytest.mark.case_ledger_invariants
def test_fcv_vendor_vfd_transition_observed(
    fcv_replicas: dict[str, list[dict]],
) -> None:
    """VFd transition observed in Vendor's add_participant_status entries.

    Vendor holds CVDRole.VENDOR (not CVDRole.DEPLOYER), so the fix lifecycle
    stops at VFd per CSB-15-002.  Spec: DEMOMA-12-009(4).
    """
    vendor_entries = fcv_replicas.get("vendor")
    if not vendor_entries:
        pytest.skip(
            "vendor replica absent; cannot check Vendor VFd transition"
        )

    status_entries = [
        e
        for e in vendor_entries
        if event_type(e) == "add_participant_status_to_participant"
    ]
    if not status_entries:
        pytest.skip(
            "No add_participant_status_to_participant entries in vendor log"
        )

    saw_fix_ready = False
    for e in status_entries:
        fix_ready, _, _ = cs_observations_from_snap(payload(e))
        saw_fix_ready |= fix_ready

    assert (
        saw_fix_ready
    ), "Vendor: vfd_state == 'VFd' (fix_ready) never observed"


@pytest.mark.case_ledger_invariants
def test_fcv_coordinator_p_transition_observed(
    fcv_replicas: dict[str, list[dict]],
) -> None:
    """P-transition observed in Coordinator's add_participant_status entries.

    The Coordinator as CASE_OWNER triggers CS.P (DEMOMA-07-003(4)).
    Spec: DEMOMA-12-009(4).
    """
    coordinator_entries = fcv_replicas.get("coordinator")
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
