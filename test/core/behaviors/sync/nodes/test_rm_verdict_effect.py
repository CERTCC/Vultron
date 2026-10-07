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
"""Replay of the activity-typed RM moves on a participant replica (#3814 AC-3).

The report verdicts and engage/defer are committed by the CASE_MANAGER as the
act itself; the replica applies the RM state the act records to the act's
*sender* (RSH-08-001), never backwards (RSH-05-007) and without deriving a
rung the ledger does not record (CM-23-016).
"""

import pytest
from py_trees.common import Status

from test.core.behaviors.sync.nodes.conftest import (
    CASE_ID,
    OWNER_ACTOR_ID,
    PARTICIPANT_ACTOR_ID,
    _make_event,
    _to_persistable_entry,
)
from vultron.core.behaviors.sync.nodes.rm_verdict_effect import (
    RM_VERDICT_TARGETS,
    ApplyRmVerdictFromLedgerNode,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import RmDimension, VfDimension
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.states.cs import CS_vf
from vultron.core.states.rm import RM
from vultron.core.use_cases.received.actor.full_case_invite import (
    AcceptInviteActorToFullCaseReceivedUseCase,
    RejectInviteActorToFullCaseReceivedUseCase,
    TentativeRejectInviteActorToFullCaseReceivedUseCase,
)
from vultron.enums.roles import CVDRole
from vultron.semantic_registry import use_case_map

SENDER = "https://example.org/actors/vendor"
SENDER_PARTICIPANT_ID = f"{CASE_ID}/participants/vendor"
REPLICA_PARTICIPANT_ID = f"{CASE_ID}/participants/reporter"
CLAIMED = "2026-10-01T12:00:00+00:00"

_VALIDATE = MessageSemantics.VALIDATE_REPORT.value
_INVALIDATE = MessageSemantics.INVALIDATE_REPORT.value
_CLOSE = MessageSemantics.CLOSE_REPORT.value
_ENGAGE = MessageSemantics.ENGAGE_CASE.value
_DEFER = MessageSemantics.DEFER_CASE.value
_JUDGE_VALID = MessageSemantics.ACCEPT_INVITE_ACTOR_TO_FULL_CASE.value
_JUDGE_INVALID = (
    MessageSemantics.TENTATIVE_REJECT_INVITE_ACTOR_TO_FULL_CASE.value
)
_JUDGE_CLOSED = MessageSemantics.REJECT_INVITE_ACTOR_TO_FULL_CASE.value

#: A predecessor each target is reached from in the RM machine.
_FROM = {
    _VALIDATE: RM.RECEIVED,
    _INVALIDATE: RM.RECEIVED,
    _CLOSE: RM.INVALID,
    _ENGAGE: RM.VALID,
    _DEFER: RM.VALID,
    _JUDGE_VALID: RM.RECEIVED,
    _JUDGE_INVALID: RM.RECEIVED,
    _JUDGE_CLOSED: RM.RECEIVED,
}


def _status(rm: RM, actor: str, **fields) -> ParticipantStatus:
    return ParticipantStatus(
        context=CASE_ID,
        attributed_to=actor,
        rm=RmDimension(state=rm),
        **fields,
    )


def _seed(datalayer, sender_rm: RM, **fields) -> None:
    """A replica holding the case, the sender's participant and its own."""
    sender = CaseParticipant(
        id_=SENDER_PARTICIPANT_ID,
        attributed_to=SENDER,
        context=CASE_ID,
        participant_statuses=[_status(sender_rm, SENDER, **fields)],
    )
    own = CaseParticipant(
        id_=REPLICA_PARTICIPANT_ID,
        attributed_to=PARTICIPANT_ACTOR_ID,
        context=CASE_ID,
        participant_statuses=[_status(RM.RECEIVED, PARTICIPANT_ACTOR_ID)],
    )
    case = VulnerabilityCase(id_=CASE_ID, attributed_to=OWNER_ACTOR_ID)
    case.add_participant(sender)
    case.add_participant(own)
    datalayer.save(sender)
    datalayer.save(own)
    datalayer.save(case)


def _apply(bridge, event_type: str, actor: str = SENDER):
    entry = _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=0,
            object_id=f"https://example.org/activities/{event_type}",
            event_type=event_type,
            payload_snapshot={
                "type": "Accept",
                "actor": actor,
                "context": CASE_ID,
                "published": CLAIMED,
            },
            prev_log_hash="0" * 64,
        )
    )
    return bridge.execute_with_setup(
        tree=ApplyRmVerdictFromLedgerNode(name="ApplyRmVerdict"),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=_make_event(entry, actor_id=OWNER_ACTOR_ID),
    )


def _rm_history(datalayer, participant_id: str) -> list[RM]:
    participant = datalayer.read(participant_id)
    assert isinstance(participant, CaseParticipant)
    return [s.rm.state for s in participant.participant_statuses]


def test_every_activity_typed_rm_move_is_mapped():
    """The act-typed RM moves are the mapping's keys, no more."""
    assert set(RM_VERDICT_TARGETS) == set(_FROM)


@pytest.mark.parametrize(
    "use_case",
    [
        AcceptInviteActorToFullCaseReceivedUseCase,
        TentativeRejectInviteActorToFullCaseReceivedUseCase,
        RejectInviteActorToFullCaseReceivedUseCase,
    ],
)
def test_a_full_case_reply_replays_the_state_the_manager_records(use_case):
    """The replica and the CASE_MANAGER map each reply to one RM state."""
    semantic = next(s for s, uc in use_case_map().items() if uc is use_case)
    assert RM_VERDICT_TARGETS[semantic.value] == use_case.rm_state


@pytest.mark.spec("RSH-08-004")
@pytest.mark.spec("RSH-08-001")
@pytest.mark.parametrize("event_type", sorted(RM_VERDICT_TARGETS))
def test_the_senders_participant_reaches_the_recorded_state(
    bridge, datalayer, event_type
):
    _seed(datalayer, _FROM[event_type])

    result = _apply(bridge, event_type)

    assert result.status == Status.SUCCESS
    assert _rm_history(datalayer, SENDER_PARTICIPANT_ID) == [
        _FROM[event_type],
        RM_VERDICT_TARGETS[event_type],
    ]
    # The replica's own participant is not the subject (RSH-08-001).
    assert _rm_history(datalayer, REPLICA_PARTICIPANT_ID) == [RM.RECEIVED]


@pytest.mark.spec("CM-23-016")
def test_no_rung_the_ledger_does_not_record_is_written(bridge, datalayer):
    """RECEIVED → ACCEPTED is applied as recorded; VALID is not inserted."""
    _seed(datalayer, RM.RECEIVED)

    assert _apply(bridge, _ENGAGE).status == Status.SUCCESS

    assert _rm_history(datalayer, SENDER_PARTICIPANT_ID) == [
        RM.RECEIVED,
        RM.ACCEPTED,
    ]


@pytest.mark.spec("RSH-05-007")
def test_a_backward_move_carries_the_local_value_forward(bridge, datalayer):
    _seed(datalayer, RM.CLOSED)

    assert _apply(bridge, _ENGAGE).status == Status.SUCCESS

    assert _rm_history(datalayer, SENDER_PARTICIPANT_ID) == [RM.CLOSED]


@pytest.mark.spec("RSH-05-007")
def test_a_same_rank_move_is_applied(bridge, datalayer):
    """VALID → INVALID is re-adjudication, not regression."""
    _seed(datalayer, RM.VALID)

    assert _apply(bridge, _INVALIDATE).status == Status.SUCCESS

    assert _rm_history(datalayer, SENDER_PARTICIPANT_ID) == [
        RM.VALID,
        RM.INVALID,
    ]


@pytest.mark.spec("SYNC-12-003")
def test_reapplying_the_entry_writes_nothing(bridge, datalayer):
    _seed(datalayer, RM.VALID)

    for _ in range(2):
        assert _apply(bridge, _DEFER).status == Status.SUCCESS

    assert _rm_history(datalayer, SENDER_PARTICIPANT_ID) == [
        RM.VALID,
        RM.DEFERRED,
    ]


def test_the_written_status_carries_the_participants_other_dimensions(
    bridge, datalayer
):
    _seed(
        datalayer,
        RM.ACCEPTED,
        vf=VfDimension(state=CS_vf.VF),
        cvd_role=[CVDRole.VENDOR],
    )

    assert _apply(bridge, _DEFER).status == Status.SUCCESS

    participant = datalayer.read(SENDER_PARTICIPANT_ID)
    latest = participant.participant_statuses[-1]
    assert latest.rm.state == RM.DEFERRED
    assert latest.vf is not None and latest.vf.state == CS_vf.VF
    assert latest.cvd_role == [CVDRole.VENDOR]
    assert latest.attributed_to == SENDER
    # The sender's claimed time, not the replica's clock (CLP-15-007).
    assert latest.published.isoformat() == CLAIMED


@pytest.mark.spec("CSB-18-001")
@pytest.mark.spec("SYNC-12-001")
def test_an_impossible_composite_state_fails_the_apply(bridge, datalayer):
    """A fix-ready VF cannot sit beside RM INVALID: nothing is written."""
    # An inconsistent stored record (VF ready at RM RECEIVED) is the only way
    # the ratchet lets an entailment-breaking write through.
    _seed(datalayer, RM.RECEIVED, vf=VfDimension(state=CS_vf.VF))

    assert _apply(bridge, _INVALIDATE).status == Status.FAILURE

    assert _rm_history(datalayer, SENDER_PARTICIPANT_ID) == [RM.RECEIVED]


@pytest.mark.spec("SYNC-12-001")
def test_a_replica_without_the_case_skips(bridge, datalayer):
    assert _apply(bridge, _VALIDATE).status == Status.SUCCESS


@pytest.mark.spec("SYNC-12-001")
def test_a_sender_without_a_participant_record_skips(bridge, datalayer):
    _seed(datalayer, RM.RECEIVED)

    result = _apply(bridge, _VALIDATE, actor="https://example.org/actors/x")

    assert result.status == Status.SUCCESS
    assert _rm_history(datalayer, SENDER_PARTICIPANT_ID) == [RM.RECEIVED]
