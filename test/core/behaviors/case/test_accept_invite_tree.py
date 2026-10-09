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

AC-4: The invitee MUST be a signatory (AGREED row for the active embargo) after signing embargo consent.
"""

from datetime import UTC, datetime
from types import SimpleNamespace

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.bt_harness import BTTestScenario
from test.support.embargo_register import register
from vultron.core.behaviors.case.nodes import (
    ActivateInviteeParticipantNode,
    InviteeHasParticipantRecordNode,
)
from vultron.core.behaviors.case.nodes.invite_embargo_consent import (
    _CheckEmbargoActiveStateNode,
    _SignEmbargoConsentLeafNode,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.embargo_register import EmbargoRegisterEntry
from vultron.core.states.embargo_register import EmbargoRegisterStatus
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.enums.roles import CVDRole

_ACTOR_ID = "https://example.org/actors/invitee"
_EMBARGO_ID = "https://example.org/embargoes/embargo-001"
_EARLIER_EMBARGO_ID = "https://example.org/embargoes/embargo-000"


def _run_sign_node(
    bt_scenario: BTTestScenario,
    starting: EmbargoConsentState = EmbargoConsentState.UNINVITED,
    *,
    earlier_accepted: bool = False,
) -> tuple[Status, CaseParticipant]:
    """Create a CaseParticipant whose row for the active embargo is ``starting``.

    ``earlier_accepted`` adds an AGREED row for an earlier embargo the active
    one replaced, so the participant has lapsed from the one in force.  Run
    the sign node, return the result.
    """
    rows = [
        EmbargoConsent(
            embargo_id=_EARLIER_EMBARGO_ID, state=EmbargoConsentState.AGREED
        )
        for _ in range(1 if earlier_accepted else 0)
    ]
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
        """Regression: an UNINVITED invitee must reach AGREED.

        Before the ADR-0048 fix the consent write was fail-open, leaving the
        invitee unbound while the node logged success — CM-10-001 violated.
        """
        status, participant = _run_sign_node(bt_scenario)
        assert status == Status.SUCCESS
        assert participant.is_signatory(_EMBARGO_ID)

    def test_invitee_reaches_signatory_from_invited(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """Invitee who was formally INVITED also reaches AGREED."""
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
        register = [
            EmbargoRegisterEntry(
                embargo=_EARLIER_EMBARGO_ID,
                status=EmbargoRegisterStatus.SUPERSEDED,
            ),
            EmbargoRegisterEntry(
                embargo=_EMBARGO_ID,
                status=EmbargoRegisterStatus.ACTIVE,
                replaces=_EARLIER_EMBARGO_ID,
            ),
        ]
        assert (
            participant.consent_for(_EARLIER_EMBARGO_ID)
            is EmbargoConsentState.AGREED
        )
        assert status == Status.SUCCESS
        assert participant.is_signatory(_EMBARGO_ID)
        assert not participant.has_lapsed(register)

    def test_already_signatory_is_idempotent(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """AGREED: AGREE is skipped, node succeeds, no duplicate row.

        An AGREED row agreeing again is a no-op: the guard skips the illegal
        AGREE trigger, and there is still exactly one row for the embargo
        (CM-18-005).
        """
        status, participant = _run_sign_node(
            bt_scenario, EmbargoConsentState.AGREED
        )
        assert status == Status.SUCCESS
        assert participant.is_signatory(_EMBARGO_ID)
        assert [r.embargo_id for r in participant.embargo_consents] == [
            _EMBARGO_ID
        ]

    def test_declined_participant_agree_is_skipped(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """DECLINED: AGREE is skipped (AGREE from DECLINED is invalid), SUCCESS.

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
        """The active embargo's consent row becomes AGREED."""
        _, participant = _run_sign_node(bt_scenario)
        assert (
            participant.consent_for(_EMBARGO_ID) == EmbargoConsentState.AGREED
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


_REGISTERS = {
    "ACTIVE": lambda: register(active=_EMBARGO_ID),
    "REVISE": lambda: register(active=_EMBARGO_ID, proposed=[_REVISION_ID]),
    "NONE": lambda: [],
}


def _case_at(em_state: str) -> VulnerabilityCase:
    """A case whose embargo register derives *em_state* (ADR-0122)."""
    case_id = "https://example.org/cases/joiner"
    return VulnerabilityCase(
        id_=case_id, embargo_register=_REGISTERS[em_state]()
    )


@pytest.mark.spec("CM-10-004")
@pytest.mark.spec("CM-10-001")
def test_joiner_during_revise_signs_the_terms_in_force_not_the_revision(
    bt_scenario: BTTestScenario,
) -> None:
    """At REVISE the whole consent step signs the active embargo only.

    The open revision is not the joiner's to accept: it records the active
    embargo's id, is marked AGREED through ``apply_pec_transition``, and
    the revision's row stays UNINVITED (EP-05-001 then
    lapses it if the owner activates longer terms).
    """
    from vultron.core.behaviors.case.accept_invite_tree import (
        MaybeSignEmbargoConsentNode,
    )

    case = _case_at("REVISE")
    participant = CaseParticipant(
        id_=_ACTOR_ID,
        attributed_to=_ACTOR_ID,
    )
    case.add_participant(participant)
    node = MaybeSignEmbargoConsentNode(case_id=case.id_, invitee_id=_ACTOR_ID)

    result = bt_scenario.run(
        node,
        actor_id=_ACTOR_ID,
        invitee_case=case,
        new_invite_participant=participant,
    )

    assert result.status == Status.SUCCESS
    assert participant.is_signatory(_EMBARGO_ID)
    assert participant.consent_for(_REVISION_ID) is (
        EmbargoConsentState.UNINVITED
    )
    assert case.is_active_participant(participant)


@pytest.mark.spec("CM-10-004")
@pytest.mark.parametrize(
    ("em_state", "signs"),
    [
        ("ACTIVE", True),
        ("REVISE", True),
        ("NONE", False),
    ],
)
def test_joiner_signs_the_embargo_in_force(
    bt_scenario: BTTestScenario, em_state: str, signs: bool
) -> None:
    """A joiner signs the terms in force at ACTIVE *and* during REVISE.

    Signing only at ACTIVE left a joiner that accepted during a revision
    without a row under an active embargo — inert (CM-10-004), and never asked:
    the revision Invite was relayed before it joined (#4046).
    """
    case = _case_at(em_state)
    node = _CheckEmbargoActiveStateNode(case_id=case.id_)

    result = bt_scenario.run(node, actor_id=_ACTOR_ID, invitee_case=case)

    expected = Status.SUCCESS if signs else Status.FAILURE
    assert result.status == expected
    stored = py_trees.blackboard.Blackboard.storage.get("/active_embargo_id")
    assert stored == (_EMBARGO_ID if signs else None)


_CM21_CASE_ID = "https://example.org/cases/case-cm21"
_CM21_INVITEE_ID = "https://example.org/actors/vendor-invitee"


def _case_with_inert_invitee() -> tuple[VulnerabilityCase, CaseParticipant]:
    """A case holding the invitee's inert record, as the stub Invite leaves it."""
    participant = CaseParticipant(
        id_=f"{_CM21_CASE_ID}/participants/vendor-invitee",
        attributed_to=_CM21_INVITEE_ID,
        context=_CM21_CASE_ID,
        case_roles=[CVDRole.VENDOR],
        joined=False,
    )
    case = VulnerabilityCase(id_=_CM21_CASE_ID)
    case.case_participants.append(participant.id_)
    case.actor_participant_index[_CM21_INVITEE_ID] = participant.id_
    return case, participant


@pytest.mark.spec("CM-11-021")
def test_accept_with_no_participant_record_is_refused_before_any_write(
    bt_scenario: BTTestScenario,
) -> None:
    """CM-11-021: an Accept never creates a participant.

    The case holds no record for the invitee, so the guard fails with a reason
    naming the missing record and writes nothing.
    """
    case = VulnerabilityCase(id_=_CM21_CASE_ID)
    bt_scenario.seed(case)
    node = InviteeHasParticipantRecordNode(
        case_id=_CM21_CASE_ID, invitee_id=_CM21_INVITEE_ID
    )

    result = bt_scenario.run(node, actor_id=bt_scenario.actor_id)

    assert result.status == Status.FAILURE
    assert "participant record" in node.feedback_message
    assert "CM-11-021" in node.feedback_message
    stored = bt_scenario.dl.read(_CM21_CASE_ID)
    assert isinstance(stored, VulnerabilityCase)
    assert stored.case_participants == []


@pytest.mark.spec("CM-11-021")
@pytest.mark.spec("CM-11-006")
def test_accept_with_an_inert_record_reuses_it(
    bt_scenario: BTTestScenario,
) -> None:
    """With the stub Invite's record in place the guard passes it on."""
    case, participant = _case_with_inert_invitee()
    bt_scenario.seed(case, participant)
    node = InviteeHasParticipantRecordNode(
        case_id=_CM21_CASE_ID, invitee_id=_CM21_INVITEE_ID
    )

    result = bt_scenario.run(node, actor_id=bt_scenario.actor_id)

    assert result.status == Status.SUCCESS
    stored = py_trees.blackboard.Blackboard.storage.get(
        "/new_invite_participant"
    )
    assert isinstance(stored, CaseParticipant)
    assert stored.id_ == participant.id_


_ACCEPT_PUBLISHED = datetime(2026, 10, 9, 13, 0, 0, tzinfo=UTC)


def _received_accept() -> SimpleNamespace:
    """The received Accept as the node sees it: its id and carried time."""
    return SimpleNamespace(
        activity_id="https://example.org/activities/accept-1",
        activity=SimpleNamespace(published=_ACCEPT_PUBLISHED),
    )


@pytest.mark.spec("CM-11-001")
def test_activating_the_inert_record_marks_it_joined_and_keeps_rm(
    bt_scenario: BTTestScenario,
) -> None:
    """Accepting the stub is joining: ``joined`` flips, RM is not touched."""
    _case, participant = _case_with_inert_invitee()
    bt_scenario.seed(participant)
    node = ActivateInviteeParticipantNode(
        case_id=_CM21_CASE_ID, invitee_id=_CM21_INVITEE_ID
    )
    rm_before = participant.participant_status

    result = bt_scenario.run(
        node,
        actor_id=bt_scenario.actor_id,
        new_invite_participant=participant,
        activity=_received_accept(),
    )

    assert result.status == Status.SUCCESS
    stored = bt_scenario.dl.read(participant.id_)
    assert isinstance(stored, CaseParticipant)
    assert stored.joined is True
    assert stored.participant_status == rm_before
    # The time is the Accept's claimed one, never the local clock (ADR-0103).
    assert stored.updated == _ACCEPT_PUBLISHED


@pytest.mark.spec("CM-11-001")
def test_activating_a_joined_record_changes_nothing(
    bt_scenario: BTTestScenario,
) -> None:
    """Backfill resume: an already joined record is left as it is."""
    _case, participant = _case_with_inert_invitee()
    participant.joined = True
    bt_scenario.seed(participant)
    node = ActivateInviteeParticipantNode(
        case_id=_CM21_CASE_ID, invitee_id=_CM21_INVITEE_ID
    )
    before = participant.model_dump()

    result = bt_scenario.run(
        node,
        actor_id=bt_scenario.actor_id,
        new_invite_participant=participant,
        activity=_received_accept(),
    )

    assert result.status == Status.SUCCESS
    stored = bt_scenario.dl.read(participant.id_)
    assert isinstance(stored, CaseParticipant)
    assert stored.model_dump() == before


def test_accept_tree_has_no_participant_creating_node() -> None:
    """The Accept tree creates no participant (CM-11-021, ADR-0114)."""
    from vultron.core.behaviors.case.accept_invite_tree import (
        create_accept_invite_actor_to_case_tree,
    )

    tree = create_accept_invite_actor_to_case_tree(
        case_id=_CM21_CASE_ID,
        invitee_id=_CM21_INVITEE_ID,
        invite_id=f"{_CM21_CASE_ID}/invitations/1",
    )
    names = {type(n).__name__ for n in tree.iterate()}
    assert "InviteeHasParticipantRecordNode" in names
    assert not {n for n in names if n.startswith(("Create", "Persist"))}


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

    effect_prefixes = ("Activate", "Advance", "Emit", "Backfill")
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
    ``ActivateInviteeParticipantNode`` has run.  Placed before
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
