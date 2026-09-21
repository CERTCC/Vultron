#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""Regression tests for accept-invite BT nodes (ADR-0048, CM-10-001, CM-17-003).

AC-4: The invitee MUST reach PEC.SIGNATORY after signing embargo consent.
CM-17-003: Roles MUST be read from the Accept's embedded Invite, not DataLayer.
"""

import logging
import types
from unittest.mock import patch

import py_trees
import pytest
from py_trees.common import Status

from vultron.core.behaviors.case.nodes import (
    CreateInviteeParticipantNode,
)
from vultron.core.behaviors.case.nodes.invite_embargo_consent import (
    _SignEmbargoConsentLeafNode,
)
from vultron.core.models.activity import VultronActivity
from vultron.core.models.base import VultronObject
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.events.actor import (
    AcceptInviteActorToCaseReceivedEvent,
)
from vultron.core.states.participant_embargo_consent import PEC
from vultron.enums.roles import CVDRole
from test.core.behaviors.bt_harness import BTTestScenario

_ACTOR_ID = "https://example.org/actors/invitee"
_EMBARGO_ID = "https://example.org/embargoes/embargo-001"


def _run_sign_node(
    bt_scenario: BTTestScenario,
    starting_pec: PEC,
) -> tuple[Status, CaseParticipant]:
    """Create a CaseParticipant at ``starting_pec``, run the sign node, return result."""
    participant = CaseParticipant(
        id_=_ACTOR_ID,
        attributed_to=_ACTOR_ID,
        embargo_consent_state=starting_pec,
    )

    node = _SignEmbargoConsentLeafNode(invitee_id=_ACTOR_ID)

    result = bt_scenario.run(
        node,
        actor_id=_ACTOR_ID,
        new_invite_participant=participant,
        active_embargo_id=_EMBARGO_ID,
    )
    return result.status, participant


@pytest.mark.spec("CM-10-001")
class TestSignEmbargoConsentLeafNode:
    """_SignEmbargoConsentLeafNode must set invitee to SIGNATORY (CM-10-001)."""

    def test_invitee_reaches_signatory_from_no_embargo(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """Regression: invitee starting at UNBOUND must reach SIGNATORY.

        Before the ADR-0048 fix the consent write was fail-open, returning
        UNBOUND unchanged while the node logged success — CM-10-001
        violated.
        """
        status, participant = _run_sign_node(
            bt_scenario, starting_pec=PEC.UNBOUND
        )
        assert status == Status.SUCCESS
        assert participant.embargo_consent_state == PEC.SIGNATORY

    def test_invitee_reaches_signatory_from_invited(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """Invitee who was formally INVITED also reaches SIGNATORY."""
        status, participant = _run_sign_node(
            bt_scenario, starting_pec=PEC.INVITED
        )
        assert status == Status.SUCCESS
        assert participant.embargo_consent_state == PEC.SIGNATORY

    def test_invitee_reaches_signatory_from_lapsed(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """Invitee who LAPSED (embargo revised) can re-consent without a new invite."""
        status, participant = _run_sign_node(
            bt_scenario, starting_pec=PEC.LAPSED
        )
        assert status == Status.SUCCESS
        assert participant.embargo_consent_state == PEC.SIGNATORY

    def test_already_signatory_is_idempotent(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """SIGNATORY: ACCEPT is skipped, node succeeds, no duplicate embargo ID.

        ADR-0093 introduced SIGNATORY → DECLINED, making DECLINED a reachable
        terminal state.  A SIGNATORY re-accepting is a no-op: the guard skips
        the invalid ACCEPT trigger, and the dedup check prevents appending a
        duplicate embargo ID (CM-18-005).
        """
        node = _SignEmbargoConsentLeafNode(invitee_id=_ACTOR_ID)
        participant = CaseParticipant(
            id_=_ACTOR_ID,
            attributed_to=_ACTOR_ID,
            embargo_consent_state=PEC.SIGNATORY,
            accepted_embargo_ids=[_EMBARGO_ID],
        )
        result = bt_scenario.run(
            node,
            actor_id=_ACTOR_ID,
            new_invite_participant=participant,
            active_embargo_id=_EMBARGO_ID,
        )
        assert result.status == Status.SUCCESS
        assert participant.embargo_consent_state == PEC.SIGNATORY
        assert participant.accepted_embargo_ids.count(_EMBARGO_ID) == 1

    def test_declined_participant_accept_is_skipped(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """DECLINED: ACCEPT is skipped (ACCEPT from DECLINED is invalid), SUCCESS.

        Mirrors the service-layer guard in _record_actor_pec_acceptance.
        A DECLINED participant reaching this node (e.g., out-of-order EA
        without prior EP re-invite) must not crash.
        """
        node = _SignEmbargoConsentLeafNode(invitee_id=_ACTOR_ID)
        participant = CaseParticipant(
            id_=_ACTOR_ID,
            attributed_to=_ACTOR_ID,
            embargo_consent_state=PEC.DECLINED,
        )
        result = bt_scenario.run(
            node,
            actor_id=_ACTOR_ID,
            new_invite_participant=participant,
            active_embargo_id=_EMBARGO_ID,
        )
        assert result.status == Status.SUCCESS
        assert participant.embargo_consent_state == PEC.DECLINED

    def test_embargo_id_recorded_on_participant(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """The active embargo ID is appended to accepted_embargo_ids."""
        _, participant = _run_sign_node(bt_scenario, starting_pec=PEC.UNBOUND)
        assert _EMBARGO_ID in participant.accepted_embargo_ids

    def test_snapshot_em_consent_state_agrees_with_scalar(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """AC-7: ledger snapshot emConsentState agrees with embargo_consent_state.

        After the sign node runs, participant_status.consent.state MUST equal
        embargo_consent_state — the snapshot must not be stale (CM-18-006).
        """
        _, participant = _run_sign_node(bt_scenario, starting_pec=PEC.UNBOUND)
        assert participant.embargo_consent_state == PEC.SIGNATORY
        status = participant.participant_status
        assert status is not None
        assert status.consent is not None
        assert status.consent.state == PEC.SIGNATORY

    def test_failure_when_participant_missing(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """FAILURE returned when new_invite_participant is absent."""
        node = _SignEmbargoConsentLeafNode(invitee_id=_ACTOR_ID)
        result = bt_scenario.run(
            node,
            actor_id=_ACTOR_ID,
            active_embargo_id=_EMBARGO_ID,
        )
        assert result.status == Status.FAILURE

    def test_failure_when_embargo_id_missing(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """FAILURE returned when active_embargo_id is absent."""
        participant = CaseParticipant(
            id_=_ACTOR_ID,
            attributed_to=_ACTOR_ID,
            embargo_consent_state=PEC.UNBOUND,
        )
        node = _SignEmbargoConsentLeafNode(invitee_id=_ACTOR_ID)
        result = bt_scenario.run(
            node,
            actor_id=_ACTOR_ID,
            new_invite_participant=participant,
        )
        assert result.status == Status.FAILURE


_CM17_CASE_ID = "https://example.org/cases/case-cm17"
_CM17_INVITEE_ID = "https://example.org/actors/vendor-invitee"
_CM17_CASE_ACTOR_ID = "https://example.org/actors/case-actor"
_CM17_INVITE_ID = "https://example.org/activities/invite-cm17"


@pytest.mark.spec("CM-17-003")
def test_create_invitee_participant_reads_roles_from_accept_activity_when_invite_absent_from_datalayer(
    bt_scenario: BTTestScenario,
) -> None:
    """CM-17-003: roles come from event.activity.object_.roles, not DataLayer.

    Reproduces the race condition where the Invite has not yet been stored in
    the CaseActor's DataLayer when the Accept arrives (ISSUE-2719 Bug 1).
    Before fix: _read_invite_roles() returned [] because datalayer.read()
    returned None; the participant was persisted with case_roles=[].
    After fix: roles are read from event.activity.object_.roles (the Invite
    embedded in the Accept message), so DataLayer absence does not matter.
    """
    case = VulnerabilityCase(
        id_=_CM17_CASE_ID, attributed_to=_CM17_CASE_ACTOR_ID
    )
    bt_scenario.seed(case)

    # Build an Accept event whose activity.object_ carries roles.
    # The Invite is intentionally NOT stored in the DataLayer to simulate
    # the race condition (cc self-delivery not yet processed).
    invite_wire = types.SimpleNamespace(roles=["vendor"])
    accept_activity = VultronActivity(
        id_="https://example.org/activities/accept-cm17",
        type_="Accept",
        actor=_CM17_INVITEE_ID,
        object_=invite_wire,
    )
    event = AcceptInviteActorToCaseReceivedEvent(
        activity_id="https://example.org/activities/accept-cm17",
        actor_id=_CM17_INVITEE_ID,
        object_=VultronObject(id_=_CM17_INVITE_ID, type_="Invite"),
        activity=accept_activity,
    )

    node = CreateInviteeParticipantNode(
        case_id=_CM17_CASE_ID,
        invitee_id=_CM17_INVITEE_ID,
    )

    result = bt_scenario.run(
        node,
        actor_id=_CM17_CASE_ACTOR_ID,
        activity=event,
        invitee_case=case,
        invitee_already_participant=False,
    )

    assert result.status == Status.SUCCESS
    participant = py_trees.blackboard.Blackboard.storage.get(
        "/new_invite_participant"
    )
    assert participant is not None
    assert CVDRole.VENDOR in participant.case_roles


@pytest.mark.spec("CM-17-003")
def test_read_invite_roles_warns_when_invite_object_missing(
    bt_scenario: BTTestScenario,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """#2802: WARNING emitted when activity.object_ is None — protocol violation.

    A missing embedded Invite object in the Accept activity is a protocol
    violation (per datalayer-fallback-is-a-smell learning).  The node MUST
    log a WARNING so operators can distinguish silent absence from graceful
    empty-roles.
    """
    case = VulnerabilityCase(
        id_=_CM17_CASE_ID, attributed_to=_CM17_CASE_ACTOR_ID
    )
    bt_scenario.seed(case)

    accept_activity = VultronActivity(
        id_="https://example.org/activities/accept-no-obj",
        type_="Accept",
        actor=_CM17_INVITEE_ID,
        object_=None,
    )
    event = AcceptInviteActorToCaseReceivedEvent(
        activity_id="https://example.org/activities/accept-no-obj",
        actor_id=_CM17_INVITEE_ID,
        object_=VultronObject(id_=_CM17_INVITE_ID, type_="Invite"),
        activity=accept_activity,
    )
    node = CreateInviteeParticipantNode(
        case_id=_CM17_CASE_ID,
        invitee_id=_CM17_INVITEE_ID,
    )

    with caplog.at_level(logging.WARNING):
        result = bt_scenario.run(
            node,
            actor_id=_CM17_CASE_ACTOR_ID,
            activity=event,
            invitee_case=case,
            invitee_already_participant=False,
        )

    assert result.status == Status.SUCCESS
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any(
        "object_" in r.message and "protocol violation" in r.message
        for r in warnings
    ), f"Expected WARNING about missing object_ / protocol violation, got: {[r.message for r in warnings]}"


@pytest.mark.spec("CM-17-003")
def test_read_invite_roles_warns_when_roles_field_absent(
    bt_scenario: BTTestScenario,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """#2802: WARNING emitted when invite object_ is present but has no roles field.

    A missing roles field on the embedded Invite is a protocol violation.
    The node MUST log a WARNING rather than silently returning an empty list.
    """
    case = VulnerabilityCase(
        id_=_CM17_CASE_ID, attributed_to=_CM17_CASE_ACTOR_ID
    )
    bt_scenario.seed(case)

    invite_without_roles = types.SimpleNamespace()  # no .roles attribute
    accept_activity = VultronActivity(
        id_="https://example.org/activities/accept-no-roles",
        type_="Accept",
        actor=_CM17_INVITEE_ID,
        object_=invite_without_roles,
    )
    event = AcceptInviteActorToCaseReceivedEvent(
        activity_id="https://example.org/activities/accept-no-roles",
        actor_id=_CM17_INVITEE_ID,
        object_=VultronObject(id_=_CM17_INVITE_ID, type_="Invite"),
        activity=accept_activity,
    )
    node = CreateInviteeParticipantNode(
        case_id=_CM17_CASE_ID,
        invitee_id=_CM17_INVITEE_ID,
    )

    with caplog.at_level(logging.WARNING):
        result = bt_scenario.run(
            node,
            actor_id=_CM17_CASE_ACTOR_ID,
            activity=event,
            invitee_case=case,
            invitee_already_participant=False,
        )

    assert result.status == Status.SUCCESS
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any(
        "roles" in r.message and "protocol violation" in r.message
        for r in warnings
    ), f"Expected WARNING about missing roles / protocol violation, got: {[r.message for r in warnings]}"


@pytest.mark.spec("CM-17-003")
def test_read_invite_roles_warns_and_recovers_on_typeerror(
    bt_scenario: BTTestScenario,
) -> None:
    """#2802: TypeError from validate_roles is caught; node returns SUCCESS.

    If validate_roles raises TypeError (truthy but non-iterable roles payload),
    the except clause in _read_invite_roles() MUST catch it rather than
    propagating out of update() and aborting the BT sequence.
    """
    case = VulnerabilityCase(
        id_=_CM17_CASE_ID, attributed_to=_CM17_CASE_ACTOR_ID
    )
    bt_scenario.seed(case)

    invite_with_integer_roles = types.SimpleNamespace(roles=42)
    accept_activity = VultronActivity(
        id_="https://example.org/activities/accept-typeerror",
        type_="Accept",
        actor=_CM17_INVITEE_ID,
        object_=invite_with_integer_roles,
    )
    event = AcceptInviteActorToCaseReceivedEvent(
        activity_id="https://example.org/activities/accept-typeerror",
        actor_id=_CM17_INVITEE_ID,
        object_=VultronObject(id_=_CM17_INVITE_ID, type_="Invite"),
        activity=accept_activity,
    )
    node = CreateInviteeParticipantNode(
        case_id=_CM17_CASE_ID,
        invitee_id=_CM17_INVITEE_ID,
    )

    with patch(
        "vultron.core.behaviors.case.nodes.invite_participant.validate_roles",
        side_effect=TypeError("not iterable"),
    ):
        result = bt_scenario.run(
            node,
            actor_id=_CM17_CASE_ACTOR_ID,
            activity=event,
            invitee_case=case,
            invitee_already_participant=False,
        )

    assert result.status == Status.SUCCESS


@pytest.mark.spec("CM-11-001")
def test_invitee_birth_is_construct_attach_then_advance(
    bt_scenario: BTTestScenario,
) -> None:
    """AC-4 (#3207): birth is construct → attach → advance-through-the-writer.

    Between attach and advance the invitee participant reads ``RM.START``; only
    the writer moves it to ``RM.RECEIVED``.  Pinning the intermediate state
    guards against re-fusing the two halves of the transition — the #2548
    family of bug that a detached, already-advanced participant reintroduced.
    """
    from vultron.core.behaviors.case.nodes import (
        AdvanceInviteeToReceivedNode,
        PersistInviteeParticipantNode,
    )
    from vultron.core.models.participant_status import (
        participant_status_rm_state,
    )
    from vultron.core.states.rm import RM

    # The CaseActor runs this tree in its own store, so make it the harness's
    # own actor — otherwise the write lands in a different per-actor store
    # (ADR-0073) than the one this test reads from.
    case_actor_id = bt_scenario.actor_id
    invitee_id = "https://example.org/actors/invitee-birth"
    case = VulnerabilityCase(
        id_=f"{case_actor_id}/cases/birth-order",
        attributed_to=case_actor_id,
    )
    bt_scenario.seed(case)

    # Steps 1 (construct at RM.START) + 2 (attach and save).
    create_then_persist = py_trees.composites.Sequence(
        name="CreateThenPersist",
        memory=True,
        children=[
            CreateInviteeParticipantNode(
                case_id=case.id_, invitee_id=invitee_id
            ),
            PersistInviteeParticipantNode(
                case_id=case.id_, invitee_id=invitee_id
            ),
        ],
    )
    result = bt_scenario.run(
        create_then_persist,
        actor_id=case_actor_id,
        invitee_case=case,
        invitee_already_participant=False,
    )
    assert result.status == Status.SUCCESS

    participant_id = f"{case.id_}/participants/{invitee_id.split('/')[-1]}"
    attached = bt_scenario.dl.read(participant_id)
    assert isinstance(attached, CaseParticipant)
    # AC-4: attached, but not yet advanced.
    assert participant_status_rm_state(attached.participant_status) == RM.START

    # Step 3 (advance): the writer moves it to RM.RECEIVED.
    advance_result = bt_scenario.run(
        AdvanceInviteeToReceivedNode(case_id=case.id_, invitee_id=invitee_id),
        actor_id=case_actor_id,
        invitee_already_participant=False,
    )
    assert advance_result.status == Status.SUCCESS

    advanced = bt_scenario.dl.read(participant_id)
    assert isinstance(advanced, CaseParticipant)
    assert (
        participant_status_rm_state(advanced.participant_status) == RM.RECEIVED
    )


def _seed_case_with_persisted_invitee(
    bt_scenario: BTTestScenario, invitee_id: str
) -> tuple[VulnerabilityCase, str]:
    """Construct + persist an invitee (steps 1–2), leaving it at RM.START.

    Returns the case and the persisted participant id.  Mirrors the interrupted
    birth: the participant is durable at RM.START but not yet advanced.
    """
    case_actor_id = bt_scenario.actor_id
    case = VulnerabilityCase(
        id_=f"{case_actor_id}/cases/birth-resume",
        attributed_to=case_actor_id,
    )
    bt_scenario.seed(case)
    from vultron.core.behaviors.case.nodes import (
        CreateInviteeParticipantNode,
        PersistInviteeParticipantNode,
    )

    result = bt_scenario.run(
        py_trees.composites.Sequence(
            name="CreateThenPersist",
            memory=True,
            children=[
                CreateInviteeParticipantNode(
                    case_id=case.id_, invitee_id=invitee_id
                ),
                PersistInviteeParticipantNode(
                    case_id=case.id_, invitee_id=invitee_id
                ),
            ],
        ),
        actor_id=case_actor_id,
        invitee_case=case,
        invitee_already_participant=False,
    )
    assert result.status == Status.SUCCESS
    participant_id = f"{case.id_}/participants/{invitee_id.split('/')[-1]}"
    return case, participant_id


def test_advance_invitee_retry_after_failure_completes_from_rm_start(
    bt_scenario: BTTestScenario,
) -> None:
    """Issue #3283: retry advances a participant stranded at RM.START.

    Birth commits in three steps.  If a prior run persisted the participant
    (step 2) but its advance (step 3) failed, the retry sees
    ``invitee_already_participant=True``.  A blanket skip would strand it at
    RM.START forever (RM.START → RM.VALID is illegal), so the invitee could
    never validate — the #2548 family AC-4 guards.  The advance must be
    forward-only on the *actual* RM state: RM.START → RM.RECEIVED is legal, so
    the retry completes the interrupted birth.
    """
    from vultron.core.behaviors.case.nodes import (
        AdvanceInviteeToReceivedNode,
    )
    from vultron.core.models.participant_status import (
        participant_status_rm_state,
    )
    from vultron.core.states.rm import RM

    invitee_id = "https://example.org/actors/invitee-strand"
    case, participant_id = _seed_case_with_persisted_invitee(
        bt_scenario, invitee_id
    )
    stranded = bt_scenario.dl.read(participant_id)
    assert isinstance(stranded, CaseParticipant)
    assert participant_status_rm_state(stranded.participant_status) == RM.START

    # Retry with the resume flag set — the participant already exists.
    result = bt_scenario.run(
        AdvanceInviteeToReceivedNode(case_id=case.id_, invitee_id=invitee_id),
        actor_id=bt_scenario.actor_id,
        invitee_already_participant=True,
    )
    assert result.status == Status.SUCCESS

    recovered = bt_scenario.dl.read(participant_id)
    assert isinstance(recovered, CaseParticipant)
    assert (
        participant_status_rm_state(recovered.participant_status)
        == RM.RECEIVED
    ), "retry must complete the interrupted birth, not strand it at RM.START"


def test_advance_invitee_resume_leaves_already_advanced_participant(
    bt_scenario: BTTestScenario,
) -> None:
    """Issue #3283: a genuine backfill-resume does not re-advance or regress.

    When the existing participant has already progressed to RM.RECEIVED or
    beyond, the advance is skipped: forcing it back to RM.RECEIVED would be an
    illegal backward transition, and re-advancing would append a redundant rung.
    """
    from vultron.core.behaviors.case.nodes import (
        AdvanceInviteeToReceivedNode,
    )
    from vultron.core.models.participant_status import (
        participant_status_rm_state,
    )
    from vultron.core.states.rm import RM

    invitee_id = "https://example.org/actors/invitee-resume"
    case, participant_id = _seed_case_with_persisted_invitee(
        bt_scenario, invitee_id
    )

    # First advance completes the birth: RM.START → RM.RECEIVED.
    first = bt_scenario.run(
        AdvanceInviteeToReceivedNode(case_id=case.id_, invitee_id=invitee_id),
        actor_id=bt_scenario.actor_id,
        invitee_already_participant=False,
    )
    assert first.status == Status.SUCCESS
    after_first = bt_scenario.dl.read(participant_id)
    assert isinstance(after_first, CaseParticipant)
    assert (
        participant_status_rm_state(after_first.participant_status)
        == RM.RECEIVED
    )
    rungs_after_first = len(after_first.participant_statuses)

    # Resume: the participant is already at RM.RECEIVED — skip, do not re-append.
    second = bt_scenario.run(
        AdvanceInviteeToReceivedNode(case_id=case.id_, invitee_id=invitee_id),
        actor_id=bt_scenario.actor_id,
        invitee_already_participant=True,
    )
    assert second.status == Status.SUCCESS
    after_second = bt_scenario.dl.read(participant_id)
    assert isinstance(after_second, CaseParticipant)
    assert (
        participant_status_rm_state(after_second.participant_status)
        == RM.RECEIVED
    )
    assert (
        len(after_second.participant_statuses) == rungs_after_first
    ), "genuine backfill-resume must not append a redundant RM.RECEIVED rung"
