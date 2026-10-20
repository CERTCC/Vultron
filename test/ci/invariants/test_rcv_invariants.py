"""Case-ledger invariant tests for the RCV three-actor scenario.

Reads JSONL case-ledger replica files from ``devlogs/rcv/`` and
asserts universal invariants (via the shared ``common`` library) plus
RCV-specific checks.

Actor set: ``reporter``, ``coordinator``, ``vendor``, ``case-actor``.

RCV-specific invariants (DEMOMA-12-008/009):
- ``validate_report`` semantic type is present (Coordinator validates Reporter's report).
- ``invite_actor_to_case`` appears exactly once (the Vendor's invitation; the
  Reporter is seated at case creation, CM-22-002, and is never invited).
- ``close_case`` semantic type is present.
- CS transition VFd observed in Vendor's add_participant_status entries
  (the Vendor stops at VFd, CSB-15-002).
- P-transition observed in Coordinator's add_participant_status entries.
- Vendor is a late joiner — replica holds the complete log from genesis.

All tests are tagged ``@pytest.mark.case_ledger_invariants``.  They skip
automatically when ``devlogs/rcv/`` is absent.

Spec: DEMOMA-12, CLP-07.
"""

from __future__ import annotations

import pytest

from test.ci.invariants.common import (
    check_late_joiner_has_full_history,
    check_semantic_type_count,
    check_semantic_type_present,
    cs_observations_from_snap,
    load_devlogs,
    payload,
    semantic_type,
)
from test.ci.invariants.universal_harness import make_universal_invariant_tests

_DEMO_NAME = "rcv"

#: Expected protocol semanticTypes in a complete RCV run.
_RCV_EXPECTED_SEMANTIC_TYPES = [
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
    # DEMOMA-16-007: the Coordinator invites the Vendor, who accepts.  The
    # Reporter is seated at case creation (CM-22-002) — no Invite.
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
    pytest.param("reporter"),
]


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def rcv_replicas() -> dict[str, list[dict]]:
    """Load RCV scenario JSONL files grouped by actor name."""
    return load_devlogs(demo_name=_DEMO_NAME)


# ---------------------------------------------------------------------------
# Universal invariants (injected from universal_harness)
# ---------------------------------------------------------------------------

globals().update(
    make_universal_invariant_tests(
        replicas_fixture="rcv_replicas",
        chain_actors=_CHAIN_ACTORS,
        expected_semantic_types=_RCV_EXPECTED_SEMANTIC_TYPES,
        narrative_path="docs/topics/scenarios/rcv.md",
        joined_invitees=1,
    )
)


# ---------------------------------------------------------------------------
# RCV-specific invariants (DEMOMA-12-008/009)
# ---------------------------------------------------------------------------


@pytest.mark.case_ledger_invariants
def test_rcv_validate_report_present(
    rcv_replicas: dict[str, list[dict]],
) -> None:
    """``validate_report`` semantic type is present in the log.

    Spec: DEMOMA-12-002 (Coordinator validates Reporter's report).
    """
    violations = check_semantic_type_present(rcv_replicas, "validate_report")
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_rcv_invite_actor_to_case_exactly_once(
    rcv_replicas: dict[str, list[dict]],
) -> None:
    """``invite_actor_to_case`` appears exactly once (the Vendor's invitation).

    The Reporter submitted the report, so the CASE_MANAGER seats it as a signatory
    participant (an ``AGREED`` consent row) when it creates the case (CM-22-002,
    CM-14-005); RCV never invites it.  The one Invite is the Vendor's.  The upper bound
    matters: a
    floor alone cannot tell the scenario's one send from a second Invite, such
    as a Reporter invite reintroduced with its own activity id (CLP-07-002).

    Spec: DEMOMA-12-003 (Reporter seated, not invited), DEMOMA-12-004
    (Coordinator invites Vendor directly), DEMOMA-12-009(2).
    """
    violations = check_semantic_type_count(
        rcv_replicas, "invite_actor_to_case", min_count=1, max_count=1
    )
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_rcv_close_case_present(
    rcv_replicas: dict[str, list[dict]],
) -> None:
    """``close_case`` semantic type is present in the log.

    Spec: DEMOMA-12-005 (case reaches terminal RM.CLOSED).
    """
    violations = check_semantic_type_present(rcv_replicas, "close_case")
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_rcv_vendor_late_joiner_has_full_history(
    rcv_replicas: dict[str, list[dict]],
) -> None:
    """Vendor replica contains all logIndex values present in coordinator replica.

    Vendor is a late joiner (invited after case creation) and must receive the
    full ledger backfill.  Spec: DEMOMA-12-004 (LedgerFanout convergence).
    """
    if not rcv_replicas.get("coordinator") or not rcv_replicas.get("vendor"):
        pytest.skip(
            "coordinator or vendor replica absent; cannot check late-joiner invariant"
        )
    violations = check_late_joiner_has_full_history(
        rcv_replicas, early_actor="coordinator", late_actor="vendor"
    )
    assert not violations, "\n".join(violations)


@pytest.mark.case_ledger_invariants
def test_rcv_vendor_vfd_transition_observed(
    rcv_replicas: dict[str, list[dict]],
) -> None:
    """VFd transition observed in Vendor's add_participant_status entries.

    Vendor holds CVDRole.VENDOR (not CVDRole.DEPLOYER), so the fix lifecycle
    stops at VFd per CSB-15-002.  Spec: DEMOMA-12-009(4).
    """
    vendor_entries = rcv_replicas.get("vendor")
    if not vendor_entries:
        pytest.skip(
            "vendor replica absent; cannot check Vendor VFd transition"
        )

    status_entries = [
        e
        for e in vendor_entries
        if semantic_type(e) == "add_participant_status_to_participant"
    ]
    if not status_entries:
        pytest.skip(
            "No add_participant_status_to_participant entries in vendor log"
        )

    saw_fix_ready = False
    for e in status_entries:
        fix_ready, _, _ = cs_observations_from_snap(payload(e))
        saw_fix_ready |= fix_ready

    assert saw_fix_ready, (
        "Vendor: vfd_state == 'VFd' (fix_ready) never observed"
    )


@pytest.mark.case_ledger_invariants
def test_rcv_coordinator_p_transition_observed(
    rcv_replicas: dict[str, list[dict]],
) -> None:
    """P-transition observed in Coordinator's add_participant_status entries.

    The Coordinator as CASE_OWNER triggers CS.P (DEMOMA-07-003(4)).
    Spec: DEMOMA-12-009(4).
    """
    coordinator_entries = rcv_replicas.get("coordinator")
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
