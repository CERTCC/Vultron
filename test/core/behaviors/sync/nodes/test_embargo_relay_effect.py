#!/usr/bin/env python
"""Tests for the embargo revision relay ledger effect nodes (EP-09-007).

Covers the relay classifier, the four apply nodes and their slots in
``AnnounceLogEntryReceivedBT``.  Each test runs in the participant's replica
store (``PARTICIPANT_ACTOR_ID``, see ``conftest.py``) and applies an entry the
CASE_MANAGER committed (ADR-0108, ADR-0113).
"""

from datetime import timedelta
from typing import Any, cast

import pytest
from py_trees.common import Status

from test.core.behaviors.sync.nodes.conftest import (
    CASE_ID,
    OWNER_ACTOR_ID,
    PARTICIPANT_ACTOR_ID,
    _make_event,
    _to_persistable_entry,
)
from test.support.embargo_register import activate
from vultron.core.behaviors.embargo.nodes import (
    ApplyEmbargoAcceptanceFromLedgerNode,
    ApplyEmbargoInviteFromLedgerNode,
    ApplyEmbargoProposalFromLedgerNode,
    ApplyEmbargoRejectionFromLedgerNode,
)
from vultron.core.behaviors.embargo.nodes.relay import (
    EMBARGO_INVITE_EVENT_TYPE,
)
from vultron.core.behaviors.sync.announce_tree import (
    create_announce_log_entry_tree,
)
from vultron.core.behaviors.sync.nodes.event_conditions import (
    IsEmbargoInviteRelayEventNode,
    IsEmbargoProposalEventNode,
    is_relayed_embargo_invite,
)
from vultron.core.models._helpers import now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.enums.roles import CVDRole
from vultron.errors import VultronWiringError

MANAGER_ACTOR_ID = "https://example.org/actors/case-manager"
PROPOSER_ACTOR_ID = "https://example.org/actors/vendor2"
ACTIVE_EMBARGO_ID = f"{CASE_ID}/embargo_events/e0"
REVISION_ID = f"{CASE_ID}/embargo_events/e1"
PROPOSAL_ID = "https://example.org/activities/propose-e1"
INVITE_ID = "https://example.org/activities/invite-e1"
_DEADLINE = "2026-10-07T12:00:00+00:00"


def _iso(days: int) -> str:
    return (now_utc() + timedelta(days=days)).isoformat()


def _embargo_snapshot(embargo_id: str = REVISION_ID) -> dict[str, Any]:
    """The inline ``EmbargoEvent`` a canonical entry carries (CLP-10-017)."""
    return {
        "type": "EmbargoEvent",
        "id": embargo_id,
        "context": CASE_ID,
        "endTime": _iso(60),
    }


def _invite_snapshot(
    *,
    actor: str = MANAGER_ACTOR_ID,
    attributed_to: str | None = PROPOSER_ACTOR_ID,
    to: list[str] | None = None,
    embargo: Any = None,
    end_time: str | None = _DEADLINE,
) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "type": "Invite",
        "id": INVITE_ID,
        "actor": actor,
        "to": to if to is not None else [PARTICIPANT_ACTOR_ID],
        "context": CASE_ID,
        "object": embargo if embargo is not None else _embargo_snapshot(),
    }
    if attributed_to is not None:
        snapshot["attributedTo"] = attributed_to
    if end_time is not None:
        snapshot["endTime"] = end_time
    return snapshot


def _proposal_snapshot(embargo: Any = None) -> dict[str, Any]:
    return {
        "type": "Invite",
        "id": PROPOSAL_ID,
        "actor": PROPOSER_ACTOR_ID,
        "to": [MANAGER_ACTOR_ID],
        "context": CASE_ID,
        "object": embargo if embargo is not None else _embargo_snapshot(),
    }


def _answer_snapshot(verb: str, actor: str) -> dict[str, Any]:
    return {
        "type": verb,
        "actor": actor,
        "to": [MANAGER_ACTOR_ID],
        "context": CASE_ID,
        "object": _invite_snapshot(to=[actor]),
    }


def _entry(event_type: str, snapshot: dict[str, Any]) -> CaseLedgerEntry:
    return _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=0,
            object_id=str(snapshot.get("id") or f"urn:{event_type}"),
            event_type=event_type,
            payload_snapshot=snapshot,
            prev_log_hash="0" * 64,
        )
    )


def _participant(
    datalayer,
    case: VulnerabilityCase,
    actor_id: str,
    consents: dict[str, EmbargoConsentState] | None = None,
    **kw: Any,
) -> str:
    """Seat *actor_id* holding one consent row per ``embargo id -> state``."""
    participant = CaseParticipant(
        attributed_to=actor_id,
        context=CASE_ID,
        embargo_consents=[
            EmbargoConsent(embargo_id=embargo_id, state=state)
            for embargo_id, state in (consents or {}).items()
        ],
        **kw,
    )
    datalayer.create(participant)
    case.actor_participant_index[actor_id] = participant.id_
    return participant.id_


@pytest.fixture
def revising_case(datalayer) -> VulnerabilityCase:
    """A replica case with an active embargo and a CASE_MANAGER.

    The owner, the participant and the proposer are all signatories of the
    active embargo.
    """
    active = EmbargoEvent(
        id_=ACTIVE_EMBARGO_ID,
        context=CASE_ID,
        end_time=now_utc() + timedelta(days=30),
    )
    datalayer.create(active)
    case = VulnerabilityCase(id_=CASE_ID, attributed_to=OWNER_ACTOR_ID)
    activate(case, ACTIVE_EMBARGO_ID)
    _participant(
        datalayer,
        case,
        MANAGER_ACTOR_ID,
        {ACTIVE_EMBARGO_ID: EmbargoConsentState.ACCEPTED},
        case_roles=[CVDRole.CASE_MANAGER],
    )
    for actor_id in (OWNER_ACTOR_ID, PARTICIPANT_ACTOR_ID, PROPOSER_ACTOR_ID):
        _participant(
            datalayer,
            case,
            actor_id,
            {ACTIVE_EMBARGO_ID: EmbargoConsentState.ACCEPTED},
        )
    datalayer.save(case)
    return case


def _run(bridge, node, entry: CaseLedgerEntry):
    return bridge.execute_with_setup(
        tree=node,
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=_make_event(entry, actor_id=MANAGER_ACTOR_ID),
    )


def _case(datalayer) -> VulnerabilityCase:
    return cast(VulnerabilityCase, datalayer.read(CASE_ID))


def _record(datalayer, actor_id: str) -> CaseParticipant:
    case = _case(datalayer)
    return cast(
        CaseParticipant,
        datalayer.read(case.actor_participant_index[actor_id]),
    )


def _replay_proposal(bridge) -> None:
    result = _run(
        bridge,
        ApplyEmbargoProposalFromLedgerNode(name="Proposal"),
        _entry("invite_to_embargo_on_case", _proposal_snapshot()),
    )
    assert result.status == Status.SUCCESS


# ---------------------------------------------------------------------------
# Classifier: a relayed Invite versus the proposal (EP-09-002, PCR-08-010)
# ---------------------------------------------------------------------------


class TestIsRelayedEmbargoInvite:
    @pytest.mark.spec("EP-09-007")
    def test_manager_emission_attributed_to_proposer_is_a_relay(
        self, datalayer, revising_case
    ):
        assert is_relayed_embargo_invite(
            _invite_snapshot(), revising_case, datalayer
        )

    @pytest.mark.spec("PCR-08-010")
    def test_third_party_attribution_by_a_non_manager_is_the_proposal(
        self, datalayer, revising_case
    ):
        spoofed = _invite_snapshot(
            actor=PROPOSER_ACTOR_ID, attributed_to=OWNER_ACTOR_ID
        )
        assert not is_relayed_embargo_invite(spoofed, revising_case, datalayer)

    @pytest.mark.spec("EP-09-007")
    def test_no_attribution_is_the_proposal(self, datalayer, revising_case):
        assert not is_relayed_embargo_invite(
            _invite_snapshot(attributed_to=None), revising_case, datalayer
        )

    @pytest.mark.spec("EP-09-007")
    def test_self_attribution_is_the_proposal(self, datalayer, revising_case):
        assert not is_relayed_embargo_invite(
            _invite_snapshot(attributed_to=MANAGER_ACTOR_ID),
            revising_case,
            datalayer,
        )

    @pytest.mark.spec("EP-09-007")
    def test_without_a_case_authorship_alone_decides(self, datalayer):
        assert is_relayed_embargo_invite(_invite_snapshot(), None, datalayer)


# ---------------------------------------------------------------------------
# ApplyEmbargoProposalFromLedgerNode
# ---------------------------------------------------------------------------


class TestApplyEmbargoProposal:
    @pytest.mark.spec("EP-09-007")
    @pytest.mark.spec("EMB-18-003")
    def test_revision_moves_replica_to_revise_and_stores_the_embargo(
        self, bridge, datalayer, revising_case
    ):
        _replay_proposal(bridge)

        case = _case(datalayer)
        assert case.current_status.em.state == EM.REVISE
        assert case.active_embargo_id == ACTIVE_EMBARGO_ID
        assert case.proposed_embargo_ids == [REVISION_ID]
        assert case.pending_embargo_proposal_index[REVISION_ID] == PROPOSAL_ID
        assert isinstance(datalayer.read(REVISION_ID), EmbargoEvent)

    @pytest.mark.spec("MSM-07-005")
    def test_records_proposer_consent_and_changes_nobody_elses(
        self, bridge, datalayer, revising_case
    ):
        _replay_proposal(bridge)

        proposer = _record(datalayer, PROPOSER_ACTOR_ID)
        assert (
            proposer.consent_for(REVISION_ID) is EmbargoConsentState.ACCEPTED
        )
        assert proposer.is_signatory(ACTIVE_EMBARGO_ID)
        other = _record(datalayer, PARTICIPANT_ACTOR_ID)
        assert other.consent_for(REVISION_ID) is None
        assert other.is_signatory(ACTIVE_EMBARGO_ID)

    @pytest.mark.spec("EP-09-007")
    def test_keeps_an_existing_pending_index_entry(
        self, bridge, datalayer, revising_case
    ):
        revising_case.pending_embargo_proposal_index[REVISION_ID] = INVITE_ID
        datalayer.save(revising_case)

        _replay_proposal(bridge)

        index = _case(datalayer).pending_embargo_proposal_index
        assert index[REVISION_ID] == INVITE_ID

    @pytest.mark.spec("EP-09-002")
    @pytest.mark.spec("EP-09-007")
    def test_managers_self_relayed_invite_also_invites_its_recipient(
        self, bridge, datalayer, revising_case
    ):
        """The manager's own terms relayed to one participant (#4085).

        Self-attributed, so it lands in this proposal slot; it is also the
        relayed Invite of its sole recipient, which is recorded as invited.
        """
        newcomer = "https://example.org/actors/newcomer"
        _participant(datalayer, revising_case, newcomer)
        datalayer.save(revising_case)

        result = _run(
            bridge,
            ApplyEmbargoProposalFromLedgerNode(name="Proposal"),
            _entry(
                "invite_to_embargo_on_case",
                _invite_snapshot(
                    attributed_to=MANAGER_ACTOR_ID, to=[newcomer]
                ),
            ),
        )

        assert result.status == Status.SUCCESS
        assert _case(datalayer).proposed_embargo_ids == [REVISION_ID]
        record = _record(datalayer, newcomer)
        assert record.consent_for(REVISION_ID) is EmbargoConsentState.INVITED
        assert record.invite_rsvp_deadline is not None

    @pytest.mark.spec("EP-09-007")
    def test_managers_own_proposal_entry_invites_nobody(
        self, bridge, datalayer, revising_case
    ):
        """Addressed to nobody, the manager's proposal entry is not a relay."""
        newcomer = "https://example.org/actors/newcomer"
        _participant(datalayer, revising_case, newcomer)
        datalayer.save(revising_case)
        snapshot = _invite_snapshot(attributed_to=None, to=[])
        snapshot.pop("to")

        result = _run(
            bridge,
            ApplyEmbargoProposalFromLedgerNode(name="Proposal"),
            _entry("invite_to_embargo_on_case", snapshot),
        )

        assert result.status == Status.SUCCESS
        assert _case(datalayer).proposed_embargo_ids == [REVISION_ID]
        assert _record(datalayer, newcomer).embargo_consents == []

    @pytest.mark.spec("SYNC-12-001")
    def test_partial_replica_without_the_case_skips(self, bridge, datalayer):
        _replay_proposal(bridge)
        assert datalayer.read(REVISION_ID) is None

    @pytest.mark.spec("SYNC-12-001")
    @pytest.mark.spec("EMB-18-003")
    def test_unreconstructable_embargo_fails(
        self, bridge, datalayer, revising_case
    ):
        result = _run(
            bridge,
            ApplyEmbargoProposalFromLedgerNode(name="Proposal"),
            _entry(
                "invite_to_embargo_on_case",
                _proposal_snapshot(embargo=REVISION_ID),
            ),
        )
        assert result.status == Status.FAILURE
        assert _case(datalayer).current_status.em.state == EM.ACTIVE

    @pytest.mark.spec("SYNC-12-001")
    def test_malformed_inline_embargo_fails(
        self, bridge, datalayer, revising_case
    ):
        malformed = {"type": "EmbargoEvent", "id": REVISION_ID}
        result = _run(
            bridge,
            ApplyEmbargoProposalFromLedgerNode(name="Proposal"),
            _entry(
                "invite_to_embargo_on_case",
                _proposal_snapshot(embargo=malformed),
            ),
        )
        assert result.status == Status.FAILURE
        assert datalayer.read(REVISION_ID) is None


# ---------------------------------------------------------------------------
# ApplyEmbargoInviteFromLedgerNode
# ---------------------------------------------------------------------------


def _proposers_invite() -> dict[str, Any]:
    """A relayed Invite whose proposer is this store's actor."""
    return _invite_snapshot(
        attributed_to=PARTICIPANT_ACTOR_ID, to=[OWNER_ACTOR_ID]
    )


class TestApplyEmbargoInvite:
    @pytest.mark.spec("CM-28-013")
    @pytest.mark.spec("EP-09-004")
    def test_signatory_keeps_its_consent_and_is_invited_to_the_revision(
        self, bridge, datalayer, revising_case
    ):
        result = _run(
            bridge,
            ApplyEmbargoInviteFromLedgerNode(name="Invite"),
            _entry("invite_to_embargo_on_case", _invite_snapshot()),
        )

        assert result.status == Status.SUCCESS
        record = _record(datalayer, PARTICIPANT_ACTOR_ID)
        assert record.is_signatory(ACTIVE_EMBARGO_ID)
        assert record.consent_for(REVISION_ID) is EmbargoConsentState.INVITED
        assert record.invite_rsvp_deadline is not None
        assert record.invite_rsvp_deadline.isoformat() == _DEADLINE

    @pytest.mark.spec("EP-09-007")
    def test_invitee_without_a_row_becomes_invited(
        self, bridge, datalayer, revising_case
    ):
        newcomer = "https://example.org/actors/newcomer"
        _participant(datalayer, revising_case, newcomer)
        datalayer.save(revising_case)

        result = _run(
            bridge,
            ApplyEmbargoInviteFromLedgerNode(name="Invite"),
            _entry(
                "invite_to_embargo_on_case",
                _invite_snapshot(to=[newcomer], end_time=None),
            ),
        )

        assert result.status == Status.SUCCESS
        record = _record(datalayer, newcomer)
        assert record.consent_for(REVISION_ID) is EmbargoConsentState.INVITED
        assert record.invite_rsvp_deadline is None

    @pytest.mark.spec("EP-09-010")
    def test_more_than_one_recipient_fails(
        self, bridge, datalayer, revising_case
    ):
        result = _run(
            bridge,
            ApplyEmbargoInviteFromLedgerNode(name="Invite"),
            _entry(
                "invite_to_embargo_on_case",
                _invite_snapshot(to=[PARTICIPANT_ACTOR_ID, OWNER_ACTOR_ID]),
            ),
        )
        assert result.status == Status.FAILURE

    @pytest.mark.spec("EP-09-007")
    def test_invitee_without_a_record_here_is_skipped(
        self, bridge, datalayer, revising_case
    ):
        result = _run(
            bridge,
            ApplyEmbargoInviteFromLedgerNode(name="Invite"),
            _entry(
                "invite_to_embargo_on_case",
                _invite_snapshot(to=["https://example.org/actors/stranger"]),
            ),
        )
        assert result.status == Status.SUCCESS

    @pytest.mark.spec("EP-08-002")
    @pytest.mark.spec("EP-04-011")
    def test_the_proposers_replica_indexes_the_invite(
        self, bridge, datalayer, revising_case
    ):
        """A creation-time revision has no proposal activity, so the relayed
        Invite is how the proposer's replica learns what to select."""
        result = _run(
            bridge,
            ApplyEmbargoInviteFromLedgerNode(name="Invite"),
            _entry("invite_to_embargo_on_case", _proposers_invite()),
        )

        assert result.status == Status.SUCCESS
        assert _case(datalayer).pending_embargo_proposal_index == {
            REVISION_ID: INVITE_ID
        }

    @pytest.mark.spec("EP-08-002")
    def test_the_proposers_replica_keeps_its_own_proposal_id(
        self, bridge, datalayer, revising_case
    ):
        """The propose trigger indexed the proposer's own activity first."""
        revising_case.pending_embargo_proposal_index = {
            REVISION_ID: PROPOSAL_ID
        }
        datalayer.save(revising_case)

        result = _run(
            bridge,
            ApplyEmbargoInviteFromLedgerNode(name="Invite"),
            _entry("invite_to_embargo_on_case", _proposers_invite()),
        )

        assert result.status == Status.SUCCESS
        assert _case(datalayer).pending_embargo_proposal_index == {
            REVISION_ID: PROPOSAL_ID
        }

    @pytest.mark.spec("EP-04-011")
    def test_the_invitees_replica_writes_no_index(
        self, bridge, datalayer, revising_case
    ):
        """An index entry here would make the invitee's idempotency guard
        read its Invite as already answered; it indexes when it answers."""
        result = _run(
            bridge,
            ApplyEmbargoInviteFromLedgerNode(name="Invite"),
            _entry("invite_to_embargo_on_case", _invite_snapshot()),
        )

        assert result.status == Status.SUCCESS
        assert _case(datalayer).pending_embargo_proposal_index == {}


# ---------------------------------------------------------------------------
# ApplyEmbargoAcceptanceFromLedgerNode / ApplyEmbargoRejectionFromLedgerNode
# ---------------------------------------------------------------------------

_ANSWER_EVENT_TYPE = {
    "Accept": "accept_invite_to_embargo_on_case",
    "Reject": "reject_invite_to_embargo_on_case",
}


def _answer_node(verb: str) -> Any:
    if verb == "Accept":
        return ApplyEmbargoAcceptanceFromLedgerNode(name="Acceptance")
    return ApplyEmbargoRejectionFromLedgerNode(name="Rejection")


def _replay_answer(bridge, verb: str, actor: str):
    return _run(
        bridge,
        _answer_node(verb),
        _entry(_ANSWER_EVENT_TYPE[verb], _answer_snapshot(verb, actor)),
    )


class TestApplyEmbargoAnswers:
    @pytest.mark.spec("MSM-07-005")
    def test_participant_accept_records_consent_only(
        self, bridge, datalayer, revising_case
    ):
        _replay_proposal(bridge)

        result = _replay_answer(bridge, "Accept", PARTICIPANT_ACTOR_ID)

        assert result.status == Status.SUCCESS
        record = _record(datalayer, PARTICIPANT_ACTOR_ID)
        assert record.consent_for(REVISION_ID) is EmbargoConsentState.ACCEPTED
        assert _case(datalayer).current_status.em.state == EM.REVISE

    @pytest.mark.spec("MSM-07-003")
    @pytest.mark.spec("EP-09-007")
    def test_owner_accept_of_an_invite_records_only_its_consent(
        self, bridge, datalayer, revising_case
    ):
        """The owner's Accept(Invite) is its consent, not its decision (ADR-0122)."""
        _replay_proposal(bridge)

        result = _replay_answer(bridge, "Accept", OWNER_ACTOR_ID)

        assert result.status == Status.SUCCESS
        case = _case(datalayer)
        assert case.current_status.em.state == EM.REVISE
        assert case.active_embargo_id == ACTIVE_EMBARGO_ID
        assert case.proposed_embargo_ids == [REVISION_ID]
        record = _record(datalayer, OWNER_ACTOR_ID)
        assert record.consent_for(REVISION_ID) is EmbargoConsentState.ACCEPTED

    @pytest.mark.spec("MSM-07-004")
    def test_participant_reject_keeps_the_proposal_open(
        self, bridge, datalayer, revising_case
    ):
        _replay_proposal(bridge)

        result = _replay_answer(bridge, "Reject", PARTICIPANT_ACTOR_ID)

        assert result.status == Status.SUCCESS
        assert _case(datalayer).proposed_embargo_ids == [REVISION_ID]

    @pytest.mark.spec("MSM-07-004")
    def test_owner_reject_of_an_invite_declines_only_its_row(
        self, bridge, datalayer, revising_case
    ):
        """The owner's Reject(Invite) refuses the terms for itself (ADR-0122).

        The revision stays open — rejecting it for the case is
        ``Reject(EmbargoEvent, target=Case)`` — and the owner stays a
        signatory of the embargo in force.
        """
        _replay_proposal(bridge)

        result = _replay_answer(bridge, "Reject", OWNER_ACTOR_ID)

        assert result.status == Status.SUCCESS
        case = _case(datalayer)
        assert case.current_status.em.state == EM.REVISE
        assert case.proposed_embargo_ids == [REVISION_ID]
        record = _record(datalayer, OWNER_ACTOR_ID)
        assert record.consent_for(REVISION_ID) is EmbargoConsentState.DECLINED
        assert record.is_signatory(ACTIVE_EMBARGO_ID)

    @pytest.mark.spec("SYNC-12-003")
    def test_a_repeated_rejection_replays_as_a_no_op(
        self, bridge, datalayer, revising_case
    ):
        """A Reject of the active embargo declines; its replay is no fault."""
        reject = _answer_snapshot("Reject", PARTICIPANT_ACTOR_ID)
        reject["object"]["object"] = _embargo_snapshot(ACTIVE_EMBARGO_ID)
        entry = _entry(_ANSWER_EVENT_TYPE["Reject"], reject)

        for _ in range(2):
            result = _run(
                bridge,
                ApplyEmbargoRejectionFromLedgerNode(name="Rejection"),
                entry,
            )
            assert result.status == Status.SUCCESS

        record = _record(datalayer, PARTICIPANT_ACTOR_ID)
        assert record.consent_for(ACTIVE_EMBARGO_ID) is (
            EmbargoConsentState.DECLINED
        )

    @pytest.mark.spec("SYNC-12-001")
    @pytest.mark.spec("SYNC-14-001")
    def test_reject_of_an_embargo_no_longer_held_replays_as_a_no_op(
        self, bridge, datalayer, revising_case
    ):
        """Neither active nor open here: nothing to replay, and no stall.

        The CASE_MANAGER commits only a Reject it could apply, so a replica
        that no longer holds the embargo has already applied what followed.
        Failing would block the persist and buffer every later entry.
        """
        before = _record(datalayer, PARTICIPANT_ACTOR_ID).embargo_consents
        result = _replay_answer(bridge, "Reject", PARTICIPANT_ACTOR_ID)
        assert result.status == Status.SUCCESS
        assert "nothing to replay" in result.feedback_message
        record = _record(datalayer, PARTICIPANT_ACTOR_ID)
        assert record.embargo_consents == before

    @pytest.mark.spec("SYNC-12-001")
    @pytest.mark.parametrize("verb", ["Accept", "Reject"])
    def test_answers_skip_on_a_partial_replica(self, bridge, verb):
        result = _replay_answer(bridge, verb, PARTICIPANT_ACTOR_ID)
        assert result.status == Status.SUCCESS


# ---------------------------------------------------------------------------
# The announce tree reaches every relay node (EP-09-007, RSH-08-004)
# ---------------------------------------------------------------------------


@pytest.mark.spec("EP-09-007")
@pytest.mark.spec("RSH-08-004")
def test_announce_tree_carries_a_slot_per_relay_event_type():
    names = {node.name for node in create_announce_log_entry_tree().iterate()}
    for label in (
        "EmbargoProposal",
        "EmbargoInviteRelay",
        "EmbargoAcceptance",
        "EmbargoRejection",
        "EmbargoAbandonment",
        "EmbargoActivation",
        "EmbargoProposalRejection",
    ):
        assert any(label in name for name in names), label


@pytest.mark.spec("EP-09-007")
@pytest.mark.parametrize(
    "node_cls", [IsEmbargoProposalEventNode, IsEmbargoInviteRelayEventNode]
)
def test_classifying_an_invite_entry_without_a_store_is_a_wiring_fault(
    node_cls,
):
    """FAILURE would read as "not this slot" in both Inverters (#3915)."""
    node = node_cls(name=node_cls.__name__)
    node.activity = _make_event(
        _entry(EMBARGO_INVITE_EVENT_TYPE, _invite_snapshot()),
        actor_id=MANAGER_ACTOR_ID,
    )
    node.datalayer = None

    with pytest.raises(VultronWiringError):
        node.update()
