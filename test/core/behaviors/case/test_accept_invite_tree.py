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

AC-4: The invitee MUST be a signatory (ACCEPTED row for the active embargo) after signing embargo consent.
CM-17-003: Roles MUST be read from the Accept's embedded Invite, not DataLayer.
"""

import logging
import types
from unittest.mock import patch

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.bt_harness import BTTestScenario
from vultron.core.behaviors.case.nodes import (
    CreateInviteeParticipantNode,
)
from vultron.core.behaviors.case.nodes.invite_embargo_consent import (
    _CheckEmbargoActiveStateNode,
    _SignEmbargoConsentLeafNode,
)
from vultron.core.models.activity import VultronActivity
from vultron.core.models.base import CoreObject
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.events.actor import (
    AcceptInviteActorToCaseReceivedEvent,
)
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import rm_invite_to_case_activity
from vultron.wire.as2.vocab.base.objects.actors import as_Actor

_ACTOR_ID = "https://example.org/actors/invitee"
_EMBARGO_ID = "https://example.org/embargoes/embargo-001"
_EARLIER_EMBARGO_ID = "https://example.org/embargoes/embargo-000"


def _run_sign_node(
    bt_scenario: BTTestScenario,
    starting: EmbargoConsentState | None = None,
    *,
    earlier_accepted: bool = False,
) -> tuple[Status, CaseParticipant]:
    """Create a CaseParticipant whose row for the active embargo is ``starting``.

    ``earlier_accepted`` adds an ACCEPTED row for an earlier embargo, so the
    participant has lapsed from the one in force.  Run the sign node, return
    the result.
    """
    rows = [
        EmbargoConsent(
            embargo_id=_EARLIER_EMBARGO_ID, state=EmbargoConsentState.ACCEPTED
        )
        for _ in range(1 if earlier_accepted else 0)
    ]
    if starting is not None:
        rows.append(EmbargoConsent(embargo_id=_EMBARGO_ID, state=starting))
    participant = CaseParticipant(
        id_=_ACTOR_ID,
        attributed_to=_ACTOR_ID,
        embargo_consents=rows,
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
    """_SignEmbargoConsentLeafNode must make the invitee a signatory (CM-10-001)."""

    def test_invitee_reaches_signatory_from_no_embargo(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """Regression: an invitee with no row must reach ACCEPTED.

        Before the ADR-0048 fix the consent write was fail-open, leaving the
        invitee unbound while the node logged success — CM-10-001 violated.
        """
        status, participant = _run_sign_node(bt_scenario)
        assert status == Status.SUCCESS
        assert participant.is_signatory(_EMBARGO_ID)

    def test_invitee_reaches_signatory_from_invited(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """Invitee who was formally INVITED also reaches ACCEPTED."""
        status, participant = _run_sign_node(
            bt_scenario, EmbargoConsentState.INVITED
        )
        assert status == Status.SUCCESS
        assert participant.is_signatory(_EMBARGO_ID)

    def test_invitee_reaches_signatory_from_lapsed(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """Invitee who lapsed (embargo revised) can re-consent without a new invite."""
        status, participant = _run_sign_node(
            bt_scenario, earlier_accepted=True
        )
        assert participant.consent_for(_EARLIER_EMBARGO_ID) is not None
        assert status == Status.SUCCESS
        assert participant.is_signatory(_EMBARGO_ID)
        assert not participant.has_lapsed(_EMBARGO_ID)

    def test_already_signatory_is_idempotent(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """ACCEPTED: ACCEPT is skipped, node succeeds, no duplicate row.

        An ACCEPTED row re-accepting is a no-op: the guard skips the illegal
        ACCEPT trigger, and there is still exactly one row for the embargo
        (CM-18-005).
        """
        status, participant = _run_sign_node(
            bt_scenario, EmbargoConsentState.ACCEPTED
        )
        assert status == Status.SUCCESS
        assert participant.is_signatory(_EMBARGO_ID)
        assert [r.embargo_id for r in participant.embargo_consents] == [
            _EMBARGO_ID
        ]

    def test_declined_participant_accept_is_skipped(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """DECLINED: ACCEPT is skipped (ACCEPT from DECLINED is invalid), SUCCESS.

        Mirrors the service-layer guard in _record_actor_acceptance.
        A DECLINED participant reaching this node (e.g., out-of-order EA
        without prior EP re-invite) must not crash.
        """
        status, participant = _run_sign_node(
            bt_scenario, EmbargoConsentState.DECLINED
        )
        assert status == Status.SUCCESS
        assert (
            participant.consent_for(_EMBARGO_ID)
            == EmbargoConsentState.DECLINED
        )
        assert not participant.is_signatory(_EMBARGO_ID)

    def test_embargo_row_recorded_on_participant(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """The active embargo gets an ACCEPTED consent row."""
        _, participant = _run_sign_node(bt_scenario)
        assert (
            participant.consent_for(_EMBARGO_ID)
            == EmbargoConsentState.ACCEPTED
        )

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
        )
        node = _SignEmbargoConsentLeafNode(invitee_id=_ACTOR_ID)
        result = bt_scenario.run(
            node,
            actor_id=_ACTOR_ID,
            new_invite_participant=participant,
        )
        assert result.status == Status.FAILURE


_REVISION_ID = "https://example.org/embargoes/embargo-002"


def _case_at(em_state: str, embargo: bool) -> VulnerabilityCase:
    from vultron.core.models.case_status import CaseStatus
    from vultron.core.models.dimensions import EmDimension
    from vultron.core.states.em import EM

    case_id = "https://example.org/cases/joiner"
    return VulnerabilityCase(
        id_=case_id,
        case_statuses=[
            CaseStatus(context=case_id, em=EmDimension(state=EM[em_state]))
        ],
        active_embargo=_EMBARGO_ID if embargo else None,
    )


@pytest.mark.spec("CM-10-004")
@pytest.mark.spec("CM-10-001")
def test_joiner_during_revise_signs_the_terms_in_force_not_the_revision(
    bt_scenario: BTTestScenario,
) -> None:
    """At REVISE the whole consent step signs the active embargo only.

    The open revision is not the joiner's to accept: it records the active
    embargo's id, is marked ACCEPTED through ``apply_pec_transition``, and
    the revision gets no row (EP-05-001 then
    lapses it if the owner activates longer terms).
    """
    from vultron.core.behaviors.case.accept_invite_tree import (
        MaybeSignEmbargoConsentNode,
    )

    case = _case_at("REVISE", embargo=True)
    case.proposed_embargoes.append(_REVISION_ID)
    participant = CaseParticipant(
        id_=_ACTOR_ID,
        attributed_to=_ACTOR_ID,
    )
    node = MaybeSignEmbargoConsentNode(case_id=case.id_, invitee_id=_ACTOR_ID)

    result = bt_scenario.run(
        node,
        actor_id=_ACTOR_ID,
        invitee_case=case,
        new_invite_participant=participant,
    )

    assert result.status == Status.SUCCESS
    assert participant.is_signatory(_EMBARGO_ID)
    assert participant.consent_for(_REVISION_ID) is None
    assert case.is_active_participant(participant)


@pytest.mark.spec("CM-10-004")
@pytest.mark.parametrize(
    ("em_state", "embargo", "signs"),
    [
        ("ACTIVE", True, True),
        ("REVISE", True, True),
        ("NONE", False, False),
    ],
)
def test_joiner_signs_the_embargo_in_force(
    bt_scenario: BTTestScenario, em_state: str, embargo: bool, signs: bool
) -> None:
    """A joiner signs the terms in force at ACTIVE *and* during REVISE.

    Signing only at ACTIVE left a joiner that accepted during a revision
    without a row under an active embargo — inert (CM-10-004), and never asked:
    the revision Invite was relayed before it joined (#4046).
    """
    case = _case_at(em_state, embargo)
    node = _CheckEmbargoActiveStateNode(case_id=case.id_)

    result = bt_scenario.run(node, actor_id=_ACTOR_ID, invitee_case=case)

    expected = Status.SUCCESS if signs else Status.FAILURE
    assert result.status == expected
    stored = py_trees.blackboard.Blackboard.storage.get("/active_embargo_id")
    assert stored == (_EMBARGO_ID if signs else None)


_CM17_CASE_ID = "https://example.org/cases/case-cm17"
_CM17_INVITEE_ID = "https://example.org/actors/vendor-invitee"
_CM17_CASE_ACTOR_ID = "https://example.org/actors/case-actor"
_CM17_INVITE_ID = "https://example.org/activities/invite-cm17"


def _recorded_invite(
    bt_scenario: BTTestScenario,
    invite_id: str,
    case_id: str,
    invitee_id: str,
    roles: list[CVDRole] | None,
) -> None:
    """Record the stub Invite the CASE_MANAGER sent (CM-11-017)."""
    bt_scenario.seed(
        rm_invite_to_case_activity(
            as_Actor(id_=invitee_id),
            target=case_id,
            actor=_CM17_CASE_ACTOR_ID,
            to=[invitee_id],
            roles=[r.value for r in roles] if roles else None,
            id_=invite_id,
        )
    )


@pytest.mark.spec("CM-17-003")
@pytest.mark.spec("CM-11-017")
def test_create_invitee_participant_reads_roles_from_the_recorded_invite(
    bt_scenario: BTTestScenario,
) -> None:
    """CM-11-017: roles come from the recorded Invite, not the reply's copy.

    The Accept embeds a copy of the Invite carrying a forged extra role; the
    participant takes only the roles of the Invite the CASE_MANAGER recorded.
    """
    case = VulnerabilityCase(
        id_=_CM17_CASE_ID, attributed_to=_CM17_CASE_ACTOR_ID
    )
    bt_scenario.seed(case)
    _recorded_invite(
        bt_scenario,
        _CM17_INVITE_ID,
        _CM17_CASE_ID,
        _CM17_INVITEE_ID,
        [CVDRole.VENDOR],
    )

    forged_copy = types.SimpleNamespace(
        roles=[CVDRole.VENDOR, CVDRole.CASE_OWNER]
    )
    accept_activity = VultronActivity(
        id_="https://example.org/activities/accept-cm17",
        type_="Accept",
        actor=_CM17_INVITEE_ID,
        object_=forged_copy,
    )
    event = AcceptInviteActorToCaseReceivedEvent(
        activity_id="https://example.org/activities/accept-cm17",
        actor_id=_CM17_INVITEE_ID,
        object_=CoreObject(id_=_CM17_INVITE_ID, type_="Invite"),
        activity=accept_activity,
    )

    node = CreateInviteeParticipantNode(
        case_id=_CM17_CASE_ID,
        invitee_id=_CM17_INVITEE_ID,
        invite_id=_CM17_INVITE_ID,
    )

    result = bt_scenario.run(
        node,
        actor_id=bt_scenario.actor_id,
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
    assert CVDRole.CASE_OWNER not in participant.case_roles


@pytest.mark.spec("CM-17-003")
@pytest.mark.spec("CM-11-017")
@pytest.mark.spec("CM-11-019")
def test_read_invite_roles_warns_when_no_invite_is_recorded(
    bt_scenario: BTTestScenario,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """CM-11-017 / CM-11-019: no recorded Invite means no roles, so FAILURE.

    The node logs a WARNING that it has no recorded Invite to read roles from
    and fails (never create a participant with empty roles).
    """
    case = VulnerabilityCase(
        id_=_CM17_CASE_ID, attributed_to=_CM17_CASE_ACTOR_ID
    )
    bt_scenario.seed(case)
    node = CreateInviteeParticipantNode(
        case_id=_CM17_CASE_ID,
        invitee_id=_CM17_INVITEE_ID,
        invite_id=_CM17_INVITE_ID,
    )

    with caplog.at_level(logging.WARNING):
        result = bt_scenario.run(
            node,
            actor_id=bt_scenario.actor_id,
            invitee_case=case,
            invitee_already_participant=False,
        )

    assert result.status == Status.FAILURE
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("no recorded Invite" in r.message for r in warnings), (
        f"Expected WARNING about the missing recorded Invite, got: {[r.message for r in warnings]}"
    )


@pytest.mark.spec("CM-17-003")
@pytest.mark.spec("CM-11-019")
def test_read_invite_roles_fails_when_recorded_invite_has_no_roles(
    bt_scenario: BTTestScenario,
) -> None:
    """CM-11-019: a recorded Invite with no roles creates no participant."""
    case = VulnerabilityCase(
        id_=_CM17_CASE_ID, attributed_to=_CM17_CASE_ACTOR_ID
    )
    bt_scenario.seed(case)
    _recorded_invite(
        bt_scenario, _CM17_INVITE_ID, _CM17_CASE_ID, _CM17_INVITEE_ID, None
    )
    node = CreateInviteeParticipantNode(
        case_id=_CM17_CASE_ID,
        invitee_id=_CM17_INVITEE_ID,
        invite_id=_CM17_INVITE_ID,
    )

    result = bt_scenario.run(
        node,
        actor_id=bt_scenario.actor_id,
        invitee_case=case,
        invitee_already_participant=False,
    )

    assert result.status == Status.FAILURE


@pytest.mark.spec("CM-17-003")
@pytest.mark.spec("CM-11-019")
def test_read_invite_roles_warns_and_recovers_on_typeerror(
    bt_scenario: BTTestScenario,
) -> None:
    """#2802 / CM-11-019: TypeError from validate_roles is caught; node FAILS.

    If validate_roles raises TypeError (truthy but non-iterable roles payload),
    the except clause in _read_invite_roles() MUST catch it rather than
    propagating out of update() and aborting the BT sequence.
    Per CM-11-019 the node then FAILS (empty roles list → no participant).
    """
    case = VulnerabilityCase(
        id_=_CM17_CASE_ID, attributed_to=_CM17_CASE_ACTOR_ID
    )
    bt_scenario.seed(case)

    _recorded_invite(
        bt_scenario,
        _CM17_INVITE_ID,
        _CM17_CASE_ID,
        _CM17_INVITEE_ID,
        [CVDRole.VENDOR],
    )
    node = CreateInviteeParticipantNode(
        case_id=_CM17_CASE_ID,
        invitee_id=_CM17_INVITEE_ID,
        invite_id=_CM17_INVITE_ID,
    )

    with patch(
        "vultron.core.behaviors.case.nodes.invite_participant.validate_roles",
        side_effect=TypeError("not iterable"),
    ):
        result = bt_scenario.run(
            node,
            actor_id=bt_scenario.actor_id,
            invitee_case=case,
            invitee_already_participant=False,
        )

    # CM-11-019: coercion failure → empty list → FAILURE (no default VENDOR)
    assert result.status == Status.FAILURE


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

    # CM-11-019: CreateInviteeParticipantNode requires roles in the invite;
    # it reads them from the Invite the CASE_MANAGER recorded (CM-11-017).
    invite_id = f"{case.id_}/invitations/birth"
    _recorded_invite(
        bt_scenario, invite_id, case.id_, invitee_id, [CVDRole.VENDOR]
    )

    # Steps 1 (construct at RM.START) + 2 (attach and save).
    create_then_persist = py_trees.composites.Sequence(
        name="CreateThenPersist",
        memory=True,
        children=[
            CreateInviteeParticipantNode(
                case_id=case.id_, invitee_id=invitee_id, invite_id=invite_id
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

    participant_id = (
        f"{case.id_}/participants/{invitee_id.rsplit('/', maxsplit=1)[-1]}"
    )
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

    # CM-11-019: record an Invite with roles so CreateInviteeParticipantNode
    # can resolve them (CM-11-017).
    invite_id = f"{case.id_}/invitations/seed"
    _recorded_invite(
        bt_scenario, invite_id, case.id_, invitee_id, [CVDRole.VENDOR]
    )

    result = bt_scenario.run(
        py_trees.composites.Sequence(
            name="CreateThenPersist",
            memory=True,
            children=[
                CreateInviteeParticipantNode(
                    case_id=case.id_,
                    invitee_id=invitee_id,
                    invite_id=invite_id,
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
    participant_id = (
        f"{case.id_}/participants/{invitee_id.rsplit('/', maxsplit=1)[-1]}"
    )
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
    assert len(after_second.participant_statuses) == rungs_after_first, (
        "genuine backfill-resume must not append a redundant RM.RECEIVED rung"
    )


# ---------------------------------------------------------------------------
# #3752: admitting the invitee is gated on CASE_MANAGER (BT-17-001)
# ---------------------------------------------------------------------------


@pytest.mark.spec("BT-17-001")
def test_every_accept_invite_effect_is_inside_the_case_manager_gate():
    """No participant write, emit, or backfill is reachable without the gate.

    The gate is the sanctioned composite (BTND-07-005) and follows the receipt
    commit (CLP-10-006), so a receiver that is not the CASE_MANAGER admits
    nobody and queues nothing (#3752, PCR-08-009).
    """
    from vultron.core.behaviors.case.accept_invite_tree import (
        create_accept_invite_actor_to_case_tree,
    )
    from vultron.core.behaviors.case.nodes.conditions import (
        CheckIsCaseManagerNode,
    )

    tree = create_accept_invite_actor_to_case_tree(
        case_id="https://example.org/cases/gate",
        invitee_id="https://example.org/actors/invitee",
        invite_id="https://example.org/cases/gate/invitations/1",
    )
    gates = [
        n
        for n in tree.iterate()
        if isinstance(n, py_trees.composites.Selector)
        and n.name == "AcceptInviteIfCaseManager"
    ]
    assert len(gates) == 1
    gate = gates[0]
    inside = {id(n) for n in gate.iterate()} - {id(gate)}
    assert any(isinstance(n, CheckIsCaseManagerNode) for n in gate.iterate())

    effect_prefixes = ("Create", "Persist", "Advance", "Emit", "Backfill")
    effects = [
        n
        for n in tree.iterate()
        if type(n).__name__.startswith(effect_prefixes)
        and not isinstance(n, py_trees.composites.Composite)
    ]
    assert effects, "the tree must have effect nodes to gate"
    outside = [type(n).__name__ for n in effects if id(n) not in inside]
    assert outside == [], f"effect nodes outside the gate: {outside}"

    children = list(tree.children)
    commit_index = next(
        i
        for i, c in enumerate(children)
        if c.name == "GuardedCommitCaseLedgerEntryBT"
    )
    assert children.index(gate) > commit_index


@pytest.mark.spec("CM-17-009")
@pytest.mark.spec("CM-17-004")
@pytest.mark.spec("CM-31-012")
def test_case_announce_and_backfill_precede_the_first_committing_effect():
    """Effect order: seed the invitee's case before any ledger entry reaches it.

    The full-case Invite is the first effect after the join that commits an
    entry, and that commit fans out to the invitee, active once
    ``PersistInviteeParticipantNode`` has run.  Placed before
    ``EmitAnnounceCaseToInviteeNode`` it would hand the invitee a ledger
    entry for a case it does not hold yet (SYNC-15 pre-genesis reject, then a
    replay that interleaves with the join backfill); CM-17-004 orders the
    announce and the backfill with no fan-out to the invitee in between, so
    every committing effect belongs after both (#2898, fcvcv late joiners).
    No ``Add(CaseParticipant)`` is emitted at all (CM-31-012).
    """
    from vultron.core.behaviors.case.accept_invite_tree import (
        create_accept_invite_actor_to_case_tree,
    )
    from vultron.core.behaviors.case.nodes.full_case_invite import (
        EmitInviteActorToFullCaseNode,
    )
    from vultron.core.behaviors.case.nodes.invite_ledger_backfill import (
        BackfillCanonicalLedgerToInviteeNode,
        EmitAnnounceCaseToInviteeNode,
    )
    from vultron.core.behaviors.case.nodes.invite_revision_relay import (
        RelayOpenProposalsToJoinerNode,
    )

    tree = create_accept_invite_actor_to_case_tree(
        case_id="https://example.org/cases/order",
        invitee_id="https://example.org/actors/late-joiner",
        invite_id="https://example.org/cases/order/invitations/1",
    )
    leaves = [
        type(n)
        for n in tree.iterate()
        if not isinstance(n, py_trees.composites.Composite)
    ]
    announce = leaves.index(EmitAnnounceCaseToInviteeNode)
    backfill = leaves.index(BackfillCanonicalLedgerToInviteeNode)
    full_case_invite = leaves.index(EmitInviteActorToFullCaseNode)
    relay = leaves.index(RelayOpenProposalsToJoinerNode)

    assert announce < backfill < full_case_invite < relay, (
        "expected Announce(VulnerabilityCase) → backfill → full-case Invite"
        f" → proposal relay, got {[t.__name__ for t in leaves]}"
    )
    assert "EmitAddCaseParticipantNode" not in {t.__name__ for t in leaves}
