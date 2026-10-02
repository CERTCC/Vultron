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

"""Relay nodes for an adjudicated embargo proposal (``nodes/relay.py``).

The CASE_MANAGER relays a proposal to every participant except the proposer,
committing each emission and applying the invitee's PEC ``INVITE`` where
CM-18-003 allows it (EP-09-002, EP-09-004, ADR-0113).  These tests pin the
leaves: the read-only EM guard, the recipient roster, and the per-recipient
factory → commit → outbox → consent chain — including that a failure anywhere
in that chain fails the node rather than queuing a partial relay (BT-14-001).
"""

from datetime import datetime, timedelta
from typing import cast
from unittest.mock import MagicMock

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.bt_harness import BTTestScenario
from vultron.config.actor import ActorConfig
from vultron.core.behaviors.bridge import BTBridge, BTExecutionResult
from vultron.core.behaviors.embargo.nodes.relay import (
    EMBARGO_INVITE_EVENT_TYPE,
    CollectEmbargoInviteRecipientsNode,
    EmbargoProposalNotYetRecordedNode,
    EmStateAdmitsProposalNode,
    RelayEmbargoInviteToEachNode,
    case_manager_admits_proposal_guard,
)
from vultron.core.behaviors.helpers import TRIGGER_FACTORY_UNAVAILABLE
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.activity import VultronActivity
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (  # noqa: F401
    as_VulnerabilityCase,
)

CASE_ID = "https://example.org/cases/relay-nodes"
EMBARGO_ID = f"{CASE_ID}/embargo_events/revision"
MANAGER = "https://example.org/actors/relay-manager"
PROPOSER = "https://example.org/actors/relay-proposer"
OTHER_A = "https://example.org/actors/relay-a"
OTHER_B = "https://example.org/actors/relay-b"


def _participant(actor_id: str, pec: PEC = PEC.UNBOUND) -> CaseParticipant:
    return CaseParticipant(
        id_=f"{CASE_ID}/participants/{actor_id.rsplit('/', 1)[-1]}",
        attributed_to=actor_id,
        context=CASE_ID,
        embargo_consent_state=pec,
        case_roles=(
            [CVDRole.CASE_MANAGER] if actor_id == MANAGER else [CVDRole.VENDOR]
        ),
    )


def _seed_case(
    scenario: BTTestScenario,
    *,
    em_state: EM = EM.ACTIVE,
    participants: dict[str, PEC] | None = None,
) -> VulnerabilityCase:
    """A case at *em_state* with the manager, the proposer and *participants*."""
    roster = {MANAGER: PEC.UNBOUND, PROPOSER: PEC.UNBOUND}
    roster.update(participants or {})
    records = [_participant(actor, pec) for actor, pec in roster.items()]
    case = VulnerabilityCase(
        id_=CASE_ID,
        name="Relay nodes",
        attributed_to=MANAGER,
        case_participants=[p.id_ for p in records],
        actor_participant_index={
            cast(str, p.attributed_to): p.id_ for p in records
        },
    )
    case.append_case_status(em_state=em_state)
    embargo = as_EmbargoEvent(
        id_=EMBARGO_ID, context=CASE_ID, end_time=days_from_now_utc(60)
    )
    scenario.seed(*records, case, embargo)
    return case


def _pec(scenario: BTTestScenario, actor_id: str) -> PEC:
    case = cast(VulnerabilityCase, scenario.dl.read(CASE_ID))
    participant = scenario.dl.read(case.actor_participant_index[actor_id])
    assert isinstance(participant, CaseParticipant)
    return PEC(participant.embargo_consent_state)


def _queued_invites(scenario: BTTestScenario) -> list[VultronActivity]:
    return [
        a
        for a in (
            cast(VultronActivity, scenario.dl.read(i))
            for i in scenario.dl.outbox_list()
        )
        if a.type_ == "Invite"
    ]


def _collected_recipients() -> list[str]:
    """The roster the collect node left on the (process-global) blackboard."""
    return cast(
        list[str],
        py_trees.blackboard.Blackboard.storage["/embargo_invite_recipients"],
    )


def _ledger_event_types(scenario: BTTestScenario) -> list[str]:
    return [
        cast(CaseLedgerEntry, e).event_type
        for e in scenario.dl.list_objects("CaseLedgerEntry")
    ]


class TestEmStateAdmitsProposalNode:
    @pytest.mark.executes_as(MANAGER)
    @pytest.mark.parametrize(
        "em_state", [EM.NONE, EM.PROPOSED, EM.ACTIVE, EM.REVISE]
    )
    def test_states_the_em_machine_can_propose_from_pass(
        self, bt_scenario: BTTestScenario, em_state: EM
    ) -> None:
        _seed_case(bt_scenario, em_state=em_state)
        result = bt_scenario.run(EmStateAdmitsProposalNode(case_id=CASE_ID))
        assert result.status == Status.SUCCESS

    @pytest.mark.executes_as(MANAGER)
    @pytest.mark.spec("EP-09-001")
    def test_exited_admits_no_proposal(
        self, bt_scenario: BTTestScenario
    ) -> None:
        _seed_case(bt_scenario, em_state=EM.EXITED)
        result = bt_scenario.run(EmStateAdmitsProposalNode(case_id=CASE_ID))
        assert result.status == Status.FAILURE
        assert "EXITED" in result.feedback_message

    @pytest.mark.executes_as(MANAGER)
    def test_missing_case_fails(self, bt_scenario: BTTestScenario) -> None:
        result = bt_scenario.run(EmStateAdmitsProposalNode(case_id=CASE_ID))
        assert result.status == Status.FAILURE


class TestCaseManagerAdmitsProposalGuard:
    @pytest.mark.executes_as(MANAGER)
    def test_the_manager_is_refused_at_exited(
        self, bt_scenario: BTTestScenario
    ) -> None:
        _seed_case(bt_scenario, em_state=EM.EXITED)
        result = bt_scenario.run(case_manager_admits_proposal_guard(CASE_ID))
        assert result.status == Status.FAILURE

    @pytest.mark.executes_as(OTHER_A)
    def test_a_participant_replica_is_not_gated(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """The guard is the manager's; a replica records whatever arrives."""
        _seed_case(
            bt_scenario,
            em_state=EM.EXITED,
            participants={OTHER_A: PEC.UNBOUND},
        )
        result = bt_scenario.run(case_manager_admits_proposal_guard(CASE_ID))
        assert result.status == Status.SUCCESS


class TestCollectEmbargoInviteRecipientsNode:
    @pytest.mark.executes_as(MANAGER)
    @pytest.mark.spec("EP-09-002")
    def test_excludes_the_proposer_and_the_manager_itself(
        self, bt_scenario: BTTestScenario
    ) -> None:
        _seed_case(
            bt_scenario,
            participants={OTHER_A: PEC.UNBOUND, OTHER_B: PEC.SIGNATORY},
        )
        node = CollectEmbargoInviteRecipientsNode(
            case_id=CASE_ID, proposer_id=PROPOSER
        )
        result = bt_scenario.run(node)
        assert result.status == Status.SUCCESS
        assert sorted(_collected_recipients()) == sorted([OTHER_A, OTHER_B])

    @pytest.mark.executes_as(MANAGER)
    @pytest.mark.spec("CM-10-007")
    def test_reaches_inert_participants_but_not_a_closed_one(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """An Invite asks for consent, so inert participants get it (#4046).

        OTHER_A has not joined and OTHER_B is not SIGNATORY — both inert, both
        invited.  A participant at RM.CLOSED receives nothing further.
        """
        from vultron.core.models.dimensions import RmDimension
        from vultron.core.models.participant_status import ParticipantStatus
        from vultron.core.states.rm import RM

        closed_actor = "https://example.org/actors/relay-closed"
        case = _seed_case(
            bt_scenario,
            participants={OTHER_A: PEC.UNBOUND, OTHER_B: PEC.INVITED},
        )
        unjoined = _participant(OTHER_A).model_copy(update={"joined": False})
        closed = CaseParticipant(
            id_=f"{CASE_ID}/participants/relay-closed",
            attributed_to=closed_actor,
            context=CASE_ID,
            participant_statuses=[
                ParticipantStatus(
                    context=CASE_ID,
                    attributed_to=closed_actor,
                    rm=RmDimension(state=RM.CLOSED),
                )
            ],
        )
        bt_scenario.dl.save(unjoined)
        bt_scenario.dl.save(closed)
        case.add_participant(closed)
        bt_scenario.dl.save(case)

        result = bt_scenario.run(
            CollectEmbargoInviteRecipientsNode(
                case_id=CASE_ID, proposer_id=PROPOSER
            )
        )
        assert result.status == Status.SUCCESS
        assert sorted(_collected_recipients()) == sorted([OTHER_A, OTHER_B])

    @pytest.mark.executes_as(MANAGER)
    def test_a_proposal_from_the_manager_itself_invites_everyone_else(
        self, bt_scenario: BTTestScenario
    ) -> None:
        _seed_case(bt_scenario, participants={OTHER_A: PEC.UNBOUND})
        node = CollectEmbargoInviteRecipientsNode(
            case_id=CASE_ID, proposer_id=MANAGER
        )
        result = bt_scenario.run(node)
        assert result.status == Status.SUCCESS
        assert sorted(_collected_recipients()) == sorted([PROPOSER, OTHER_A])

    @pytest.mark.executes_as(MANAGER)
    @pytest.mark.spec("BT-19-003")
    def test_a_missing_factory_fails_before_any_state_moves(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """The routing guard fails closed so the EM write never runs."""
        _seed_case(bt_scenario, participants={OTHER_A: PEC.UNBOUND})
        bare = BTBridge(datalayer=bt_scenario.dl)
        result = bare.execute_with_setup(
            tree=CollectEmbargoInviteRecipientsNode(
                case_id=CASE_ID, proposer_id=PROPOSER
            ),
            actor_id=MANAGER,
        )
        assert result.status == Status.FAILURE
        assert TRIGGER_FACTORY_UNAVAILABLE in result.feedback_message


class TestRelayEmbargoInviteToEachNode:
    def _relay(
        self,
        scenario: BTTestScenario,
        recipients: list[str],
        actor_config: ActorConfig | None = None,
    ) -> BTExecutionResult:
        return scenario.run(
            RelayEmbargoInviteToEachNode(
                case_id=CASE_ID,
                embargo_id=EMBARGO_ID,
                proposer_id=PROPOSER,
                actor_config=actor_config,
            ),
            embargo_invite_recipients=recipients,
        )

    def _deadline(self, scenario: BTTestScenario, actor_id: str):
        case = cast(VulnerabilityCase, scenario.dl.read(CASE_ID))
        record = scenario.dl.read(case.actor_participant_index[actor_id])
        assert isinstance(record, CaseParticipant)
        return record.invite_rsvp_deadline

    @pytest.mark.executes_as(MANAGER)
    @pytest.mark.spec("CM-28-012")
    @pytest.mark.spec("CM-28-013")
    def test_each_invite_carries_the_managers_deadline_and_records_it(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """``endTime`` = ``published`` + the window, recorded as emitted."""
        _seed_case(
            bt_scenario,
            participants={OTHER_A: PEC.UNBOUND, OTHER_B: PEC.SIGNATORY},
        )
        result = self._relay(bt_scenario, [OTHER_A, OTHER_B])
        bt_scenario.assert_success(result)
        invites = _queued_invites(bt_scenario)
        assert len(invites) == 2
        for invite in invites:
            assert invite.published is not None
            assert invite.end_time is not None
            assert invite.end_time - invite.published == timedelta(days=7)
            (invitee,) = invite.to or []
            # The record takes exactly what the wire carried, signatory too.
            assert self._deadline(bt_scenario, invitee) == invite.end_time

    @pytest.mark.executes_as(MANAGER)
    @pytest.mark.spec("CM-28-012")
    def test_the_configured_window_sets_the_deadline(
        self, bt_scenario: BTTestScenario
    ) -> None:
        _seed_case(bt_scenario, participants={OTHER_A: PEC.UNBOUND})
        result = self._relay(
            bt_scenario,
            [OTHER_A],
            actor_config=ActorConfig(default_rsvp_window=timedelta(days=10)),
        )
        bt_scenario.assert_success(result)
        (invite,) = _queued_invites(bt_scenario)
        assert invite.end_time is not None and invite.published is not None
        assert invite.end_time - invite.published == timedelta(days=10)

    @pytest.mark.executes_as(MANAGER)
    @pytest.mark.spec("CM-28-012")
    @pytest.mark.spec("EP-07-006")
    def test_the_deadline_never_passes_the_embargo_end(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """A window longer than the embargo is capped at the embargo's end."""
        _seed_case(bt_scenario, participants={OTHER_A: PEC.UNBOUND})
        result = self._relay(
            bt_scenario,
            [OTHER_A],
            actor_config=ActorConfig(default_rsvp_window=timedelta(days=90)),
        )
        bt_scenario.assert_success(result)
        embargo = bt_scenario.dl.read(EMBARGO_ID)
        (invite,) = _queued_invites(bt_scenario)
        assert invite.end_time == getattr(embargo, "end_time", None)

    @pytest.mark.executes_as(MANAGER)
    @pytest.mark.spec("CM-28-013")
    @pytest.mark.spec("EP-09-007")
    def test_the_committed_entry_carries_the_deadline_for_replay(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """A replica records the deadline from the entry, so it must be there."""
        _seed_case(bt_scenario, participants={OTHER_A: PEC.UNBOUND})
        result = self._relay(bt_scenario, [OTHER_A])
        bt_scenario.assert_success(result)
        (invite,) = _queued_invites(bt_scenario)
        (entry,) = [
            cast(CaseLedgerEntry, e)
            for e in bt_scenario.dl.list_objects("CaseLedgerEntry")
        ]
        assert invite.end_time is not None
        assert (
            datetime.fromisoformat(entry.payload_snapshot["endTime"])
            == invite.end_time
        )

    @pytest.mark.executes_as(MANAGER)
    @pytest.mark.spec("EP-09-002")
    @pytest.mark.spec("CM-24-001")
    @pytest.mark.spec("CM-24-002")
    @pytest.mark.spec("CM-24-005")
    def test_one_invite_per_recipient_as_the_manager_attributed_to_the_proposer(
        self, bt_scenario: BTTestScenario
    ) -> None:
        _seed_case(
            bt_scenario,
            participants={OTHER_A: PEC.UNBOUND, OTHER_B: PEC.UNBOUND},
        )
        result = self._relay(bt_scenario, [OTHER_A, OTHER_B])
        bt_scenario.assert_success(result)
        invites = _queued_invites(bt_scenario)
        assert sorted(r for a in invites for r in (a.to or [])) == sorted(
            [OTHER_A, OTHER_B]
        )
        assert {a.actor for a in invites} == {MANAGER}
        assert {a.attributed_to for a in invites} == {PROPOSER}

    @pytest.mark.executes_as(MANAGER)
    @pytest.mark.spec("EP-09-002")
    def test_each_emission_is_committed_as_a_canonical_entry(
        self, bt_scenario: BTTestScenario
    ) -> None:
        _seed_case(
            bt_scenario,
            participants={OTHER_A: PEC.UNBOUND, OTHER_B: PEC.UNBOUND},
        )
        result = self._relay(bt_scenario, [OTHER_A, OTHER_B])
        bt_scenario.assert_success(result)
        event_types = _ledger_event_types(bt_scenario)
        assert event_types.count(EMBARGO_INVITE_EVENT_TYPE) == 2
        assert EMBARGO_INVITE_EVENT_TYPE == "invite_to_embargo_on_case"

    @pytest.mark.executes_as(MANAGER)
    @pytest.mark.spec("EP-09-004")
    @pytest.mark.spec("CM-18-003")
    def test_invite_moves_unbound_and_leaves_a_signatory_alone(
        self, bt_scenario: BTTestScenario
    ) -> None:
        _seed_case(
            bt_scenario,
            participants={
                OTHER_A: PEC.UNBOUND,
                OTHER_B: PEC.SIGNATORY,
            },
        )
        result = self._relay(bt_scenario, [OTHER_A, OTHER_B])
        bt_scenario.assert_success(result)
        assert _pec(bt_scenario, OTHER_A) is PEC.INVITED
        assert _pec(bt_scenario, OTHER_B) is PEC.SIGNATORY
        # Both were still asked: consent state is not what decides the relay.
        assert len(_queued_invites(bt_scenario)) == 2

    @pytest.mark.executes_as(MANAGER)
    @pytest.mark.spec("CM-18-003")
    @pytest.mark.parametrize("prior", [PEC.LAPSED, PEC.DECLINED])
    def test_invite_re_invites_lapsed_and_declined(
        self, bt_scenario: BTTestScenario, prior: PEC
    ) -> None:
        _seed_case(bt_scenario, participants={OTHER_A: prior})
        result = self._relay(bt_scenario, [OTHER_A])
        bt_scenario.assert_success(result)
        assert _pec(bt_scenario, OTHER_A) is PEC.INVITED

    @pytest.mark.executes_as(MANAGER)
    def test_no_recipients_is_a_successful_no_op(
        self, bt_scenario: BTTestScenario
    ) -> None:
        _seed_case(bt_scenario)
        result = self._relay(bt_scenario, [])
        bt_scenario.assert_success(result)
        assert _queued_invites(bt_scenario) == []
        assert _ledger_event_types(bt_scenario) == []

    @pytest.mark.executes_as(MANAGER)
    @pytest.mark.spec("BT-14-001")
    def test_a_factory_failure_is_an_internal_error_and_queues_nothing(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """Not a refusal: the node catches nothing, so the bridge classifies it."""
        _seed_case(bt_scenario, participants={OTHER_A: PEC.UNBOUND})
        factory = MagicMock()
        factory.propose_embargo.side_effect = RuntimeError("factory down")
        result = bt_scenario.run(
            RelayEmbargoInviteToEachNode(
                case_id=CASE_ID, embargo_id=EMBARGO_ID, proposer_id=PROPOSER
            ),
            embargo_invite_recipients=[OTHER_A],
            trigger_activity_factory=factory,
        )
        assert result.status == Status.FAILURE
        assert result.internal_error is True
        assert "factory down" in result.feedback_message
        assert bt_scenario.dl.outbox_list() == []
        assert _pec(bt_scenario, OTHER_A) is PEC.UNBOUND

    @pytest.mark.executes_as(MANAGER)
    @pytest.mark.spec("BT-14-001")
    def test_a_recipient_without_a_participant_record_is_an_internal_error(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """The roster named it, so its absence is a fault, not a lenient skip."""
        _seed_case(bt_scenario)
        stranger = "https://example.org/actors/relay-stranger"
        result = self._relay(bt_scenario, [stranger])
        assert result.status == Status.FAILURE
        assert result.internal_error is True
        assert stranger in result.feedback_message

    @pytest.mark.executes_as(MANAGER)
    @pytest.mark.spec("CM-28-012")
    def test_an_embargo_missing_from_the_managers_store_is_an_internal_error(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """The stamp's missing embargo is the manager's fault, never REFUSED."""
        _seed_case(bt_scenario, participants={OTHER_A: PEC.UNBOUND})
        missing = f"{CASE_ID}/embargoes/relay-missing"
        result = bt_scenario.run(
            RelayEmbargoInviteToEachNode(
                case_id=CASE_ID, embargo_id=missing, proposer_id=PROPOSER
            ),
            embargo_invite_recipients=[OTHER_A],
        )
        assert result.status == Status.FAILURE
        assert result.internal_error is True
        assert missing in result.feedback_message
        assert bt_scenario.dl.outbox_list() == []
        assert _pec(bt_scenario, OTHER_A) is PEC.UNBOUND


class TestEmbargoProposalNotYetRecordedNode:
    INVITE_ID = f"{CASE_ID}/embargo_proposals/p1"

    def _guard(self) -> EmbargoProposalNotYetRecordedNode:
        return EmbargoProposalNotYetRecordedNode(
            case_id=CASE_ID, embargo_id=EMBARGO_ID, invite_id=self.INVITE_ID
        )

    @pytest.mark.executes_as(MANAGER)
    def test_a_fresh_proposal_passes(
        self, bt_scenario: BTTestScenario
    ) -> None:
        _seed_case(bt_scenario)
        assert bt_scenario.run(self._guard()).status == Status.SUCCESS

    @pytest.mark.executes_as(MANAGER)
    @pytest.mark.spec("CLP-13-001")
    @pytest.mark.spec("HP-01-003")
    def test_the_same_invite_again_fails_silently(
        self, bt_scenario: BTTestScenario
    ) -> None:
        case = _seed_case(bt_scenario)
        case.pending_embargo_proposal_index = {EMBARGO_ID: self.INVITE_ID}
        bt_scenario.dl.save(case)
        result = bt_scenario.run(self._guard())
        assert result.status == Status.FAILURE
        assert self.INVITE_ID in result.feedback_message
        assert _ledger_event_types(bt_scenario) == []

    @pytest.mark.executes_as(MANAGER)
    def test_a_new_proposal_of_an_indexed_embargo_passes(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """Same terms re-proposed under a new Invite id is a counter, not a repeat."""
        case = _seed_case(bt_scenario)
        case.pending_embargo_proposal_index = {
            EMBARGO_ID: f"{CASE_ID}/embargo_proposals/older"
        }
        bt_scenario.dl.save(case)
        assert bt_scenario.run(self._guard()).status == Status.SUCCESS

    @pytest.mark.executes_as(OTHER_A)
    def test_an_unknown_case_cannot_be_a_repeat(
        self, bt_scenario: BTTestScenario
    ) -> None:
        assert bt_scenario.run(self._guard()).status == Status.SUCCESS
