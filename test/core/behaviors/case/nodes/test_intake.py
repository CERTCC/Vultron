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

"""Intake node: archive what arrived before judging it (ADR-0111, CLP-10-017).

Node-level tests run :class:`IntakeReceivedActivityNode` alone through the
bridge; the handler-level test at the end posts an assertion a guard refuses
and shows the archive survives the refusal (CLP-10-018).
"""

import json
from typing import cast

import pytest
from py_trees.behaviours import Failure
from py_trees.common import Status

from test.core.behaviors.bt_harness import BTTestScenario
from test.support.act_clock import ACT_AT
from test.support.act_runner import run_in_act
from test.support.case_owner import CASE_OWNER_ID
from test.support.objects import make
from test.support.received import (
    TEST_SENDER_POSITION,
    extract_stamped,
    hold_deferred,
    received_event,
    with_evidence,
)
from test.support.signing import signed_body
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.case.nodes.intake import (
    IntakeReceivedActivityNode,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.helpers import (
    ACTIVITY_UNAVAILABLE,
    DATALAYER_UNAVAILABLE,
)
from vultron.core.models._helpers import now_utc
from vultron.core.models.activity import VultronActivity
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.events.note import AddNoteToCaseReceivedEvent
from vultron.core.models.events.status import (
    AddParticipantStatusToParticipantReceivedEvent,
)
from vultron.core.models.note import VultronNote
from vultron.core.models.pending_case_inbox import VultronPendingCaseInbox
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
    ReceivedStage,
)
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.received_activity import sealed_body_of
from vultron.core.services.received_outcome import write_receipt_stub
from vultron.core.states.rm import RM
from vultron.core.use_cases.received.status import (
    AddParticipantStatusToParticipantReceivedUseCase,
)
from vultron.wire.as2.factories import (
    add_note_to_case_activity,
    add_status_to_participant_activity,
)
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import as_ParticipantStatus
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

SENDER = "https://example.org/actors/reporter"
RECEIVER = "https://example.org/actors/vendor"
NOTE_ID = "https://example.org/notes/n-1"
CASE_ID = "https://example.org/cases/c-1"
ACTIVITY_ID = "https://example.org/activities/add-note-1"


def _note_event(note: VultronNote) -> AddNoteToCaseReceivedEvent:
    """An ``Add(Note)`` event whose wire activity inlines *note*."""
    activity = make(
        VultronActivity,
        id_=ACTIVITY_ID,
        type_="Add",
        actor=SENDER,
        object_=note,
        target=CASE_ID,
        to=[RECEIVER],
    )
    return with_evidence(
        AddNoteToCaseReceivedEvent(
            ledger_position=TEST_SENDER_POSITION,
            activity_id=activity.id_,
            actor_id=SENDER,
            object_=note,
            activity=activity,
            receiving_actor_id=RECEIVER,
        )
    )


def _rich_note() -> VultronNote:
    return make(
        VultronNote, id_=NOTE_ID, content="what arrived", context=CASE_ID
    )


def _archived(dl: SqliteDataLayer, activity_id: str) -> bool:
    """True when *activity_id* is archived under the receiver's derived key."""
    record = dl.read(ReceivedActivityRecord.build_id(activity_id))
    return (
        isinstance(record, ReceivedActivityRecord)
        and record.activity_id == activity_id
    )


def _archive_count(dl: SqliteDataLayer) -> int:
    """How many received records intake has *recorded*.

    One record holds a received message at every stage (ADR-0154), so the
    table also holds a body the inbox is still holding for a replay.  Only a
    ``HELD`` row owing no replay is something intake wrote.
    """
    return sum(
        1
        for row in dl.by_type("ReceivedActivityRecord").values()
        if row.get("stage") == ReceivedStage.HELD.value
        and not row.get("replay_owed")
    )


@pytest.fixture
def scenario() -> BTTestScenario:
    return BTTestScenario(actor_id=RECEIVER)


# ---------------------------------------------------------------------------
# Archive the activity, idempotently, and nothing else
# ---------------------------------------------------------------------------


@pytest.mark.spec("CLP-10-036")
def test_intake_archives_the_received_activity(scenario):
    event = _note_event(_rich_note())
    node = IntakeReceivedActivityNode()

    result = scenario.run(node, activity=event)

    scenario.assert_success(result)
    assert _archived(scenario.dl, ACTIVITY_ID)
    # The archive is the receiver's row, not a row under the sender's id.
    assert scenario.dl.read(ACTIVITY_ID) is None
    assert scenario.dl.by_type("Add") == {}
    record = scenario.dl.read(ReceivedActivityRecord.build_id(ACTIVITY_ID))
    assert isinstance(record, ReceivedActivityRecord)
    # The record is the body the event carries, verbatim, and nothing
    # derived from it (ADR-0149), in holding until the outcome stage settles
    # it (CLP-10-073).
    assert record.received_body == event.received_evidence
    assert record.stage is ReceivedStage.HELD
    assert record.replay_owed is False
    body = json.loads(sealed_body_of(record))
    assert body["type"] == "Add"
    assert body["actor"] == SENDER
    assert body["object"]["id"] == NOTE_ID


@pytest.mark.spec("CLP-10-078")
def test_intake_keeps_nothing_for_a_later_stage(scenario):
    """Whether a delivery is new is the record's, not intake's memory.

    After a run the node holds only what it was given: no list or flag of
    what it stored or found that a later stage could read (ADR-0154).
    """
    node = IntakeReceivedActivityNode()
    before = set(vars(node))

    scenario.assert_success(
        scenario.run(node, activity=_note_event(_rich_note()))
    )

    assert set(vars(node)) - before == set()
    # The only collections it holds are the ones every py_trees node holds.
    assert {
        name
        for name, value in vars(node).items()
        if isinstance(value, (list, set, frozenset))
    } == {"children", "blackboards"}


@pytest.mark.spec("VM-08-002")
@pytest.mark.spec("CLP-10-036")
def test_the_archive_is_the_body_the_parser_sealed(scenario):
    """The archive holds the decoded body re-serialized, as the parser
    sealed it: the sender's keys, key order and values, not the request's
    bytes (VM-08-002, ADR-0107)."""
    unsigned = (
        '{ "type": "Add",  "published": "2026-01-01T00:00:00+00:00",'
        ' "id": "https://example.org/activities/sealed-1",'
        f' "actor": "{SENDER}", "target": "{CASE_ID}",'
        ' "object": {"type": "Note", "id": "https://example.org/notes/s-1",'
        ' "content": "caf\u00e9"}, "fooBar": [1, 2]'
    )
    # The sender signs what it sends (SIG-01-001); the context the proof
    # names and the proof are written into the request bytes, so they stay
    # the sender's own spacing.
    signed = signed_body(json.loads(unsigned + "}"))
    request_bytes = (
        f'{unsigned}, "@context": {json.dumps(signed["@context"])},'
        f' "proof": {json.dumps(signed["proof"])} }}'
    )
    parsed = parse_activity(json.loads(request_bytes))
    event = extract_stamped(parsed)

    scenario.assert_success(
        scenario.run(IntakeReceivedActivityNode(), activity=event)
    )

    record = scenario.dl.read(ReceivedActivityRecord.build_id(parsed.id_))
    assert isinstance(record, ReceivedActivityRecord)
    assert record.received_body == parsed.received_evidence_json
    assert record.received_body != request_bytes
    assert record.received_body == json.dumps(
        json.loads(request_bytes), ensure_ascii=False
    )
    # Keys the vocabulary does not name survive in the archive.
    assert json.loads(sealed_body_of(record))["fooBar"] == [1, 2]


@pytest.mark.spec("CLP-10-038")
@pytest.mark.spec("PCR-03-004")
def test_intake_writes_no_core_record_from_the_letter(scenario):
    """The note inlined in the activity is a message, not core's note record.

    Core writes its records from a copy, in an effect node, after the guards.
    Intake writing them here would let any sender seed a replica ahead of the
    trust checks — a stored case row *is* the replica (PCR-03-004).
    """
    note = _rich_note()
    node = IntakeReceivedActivityNode()

    scenario.assert_success(scenario.run(node, activity=_note_event(note)))

    scenario.assert_object_absent(NOTE_ID)
    assert len(scenario.dl.by_type("Note")) == 0


@pytest.mark.spec("PCR-03-004")
@pytest.mark.spec("CLP-10-038")
def test_inlined_case_does_not_become_a_replica(scenario):
    case = make(
        VulnerabilityCase,
        attributed_to=CASE_OWNER_ID,
        id_=CASE_ID,
        name="not mine to seed",
    )
    activity = make(
        VultronActivity,
        id_="https://example.org/activities/announce-1",
        type_="Announce",
        actor=SENDER,
        object_=case,
    )
    event = with_evidence(
        AddNoteToCaseReceivedEvent(
            ledger_position=TEST_SENDER_POSITION,
            activity_id=activity.id_,
            actor_id=SENDER,
            object_=case,
            activity=activity,
        )
    )

    scenario.assert_success(
        scenario.run(IntakeReceivedActivityNode(), activity=event)
    )

    assert scenario.dl.read_case(CASE_ID) is None
    assert _archived(scenario.dl, activity.id_)


@pytest.mark.spec("CLP-10-080")
@pytest.mark.spec("CLP-10-036")
def test_second_intake_of_the_same_activity_marks_the_record_handled(
    scenario,
):
    """The record a run left in holding is the one the re-run uses.

    Intake keeps it, body and all (CLP-10-074), and moves it to ``HANDLED``,
    the record's answer to "is this run a re-run" (ADR-0154).  A third run
    leaves it ``HANDLED``.
    """
    event = _note_event(_rich_note())
    scenario.assert_success(
        scenario.run(IntakeReceivedActivityNode(), activity=event)
    )
    (first,) = scenario.dl.by_type("ReceivedActivityRecord").values()
    assert first["stage"] == ReceivedStage.HELD.value

    scenario.assert_success(
        scenario.run(IntakeReceivedActivityNode(), activity=event)
    )
    (second,) = scenario.dl.by_type("ReceivedActivityRecord").values()
    assert second == {**first, "stage": ReceivedStage.HANDLED.value}

    scenario.assert_success(
        scenario.run(IntakeReceivedActivityNode(), activity=event)
    )
    (third,) = scenario.dl.by_type("ReceivedActivityRecord").values()
    assert third == second


@pytest.mark.spec("CLP-10-036")
def test_sender_chosen_id_cannot_squat_a_receiver_derived_record(scenario):
    """An activity named after a record this actor derives blocks nothing.

    The archive row is keyed by the receiver, so a sender who picks the id of
    the pending-case-inbox marker for a public case id does not occupy that
    id: the receiver's later ``create()`` of the real marker succeeds.
    """
    marker_id = VultronPendingCaseInbox.build_id(CASE_ID)
    squatter = make(
        VultronActivity,
        id_=marker_id,
        type_="Add",
        actor=SENDER,
        object_=_rich_note(),
    )
    event = with_evidence(
        AddNoteToCaseReceivedEvent(
            ledger_position=TEST_SENDER_POSITION,
            activity_id=squatter.id_,
            actor_id=SENDER,
            object_=_rich_note(),
            activity=squatter,
        )
    )

    scenario.assert_success(
        scenario.run(IntakeReceivedActivityNode(), activity=event)
    )

    assert scenario.dl.read(marker_id) is None
    scenario.dl.create(
        VultronPendingCaseInbox(
            case_id=CASE_ID, case_actor_id=RECEIVER, queued_at=ACT_AT
        )
    )
    assert isinstance(scenario.dl.read(marker_id), VultronPendingCaseInbox)
    assert _archived(scenario.dl, marker_id)


@pytest.mark.spec("ARCH-15-001")
@pytest.mark.spec("CLP-10-037")
def test_an_event_with_no_body_is_a_wiring_fault(scenario):
    """No received evidence: there is nothing to record, so intake fails and
    writes nothing (ARCH-15-001).  A resend routed without its own body is
    answered by the seen-before door before intake (ADR-0154)."""
    event = AddNoteToCaseReceivedEvent(
        ledger_position=TEST_SENDER_POSITION,
        activity_id="urn:vultron:no-body:1",
        actor_id=SENDER,
        object_=_rich_note(),
    )
    node = IntakeReceivedActivityNode()

    result = scenario.run(node, activity=event)

    assert result.status == Status.FAILURE
    assert "no received body" in node.feedback_message
    assert _archive_count(scenario.dl) == 0


def _hold_owing_a_replay(dl: SqliteDataLayer) -> None:
    add = add_note_to_case_activity(
        make(as_Note, id_=NOTE_ID, content="deferred", context=CASE_ID),
        target=CASE_ID,
        context=CASE_ID,
        actor=SENDER,
        to=[RECEIVER],
        id_=ACTIVITY_ID,
    )
    hold_deferred(dl, add)


def _archive(dl: SqliteDataLayer) -> None:
    event = _note_event(_rich_note())
    assert event.received_evidence is not None
    dl.create(
        ReceivedActivityRecord(
            activity_id=ACTIVITY_ID,
            received_body=event.received_evidence,
            received_at=ACT_AT,
        )
    )


def _stub(dl: SqliteDataLayer) -> None:
    _archive(dl)
    dl.delete(
        "ReceivedActivityRecord", ReceivedActivityRecord.build_id(ACTIVITY_ID)
    )
    write_receipt_stub(
        cast(CasePersistence, dl),
        ACTIVITY_ID,
        sender_id=SENDER,
        reason="refused earlier",
        received_body=_note_event(_rich_note()).received_evidence,
        received_at=now_utc(),
    )


@pytest.mark.spec("ARCH-15-001")
@pytest.mark.spec("CLP-10-017")
@pytest.mark.parametrize(
    "seed",
    [_hold_owing_a_replay, _archive, _stub],
    ids=["waiting", "archived", "receipt-stub"],
)
def test_a_record_the_seen_before_door_answers_is_a_wiring_fault(
    scenario, seed
):
    """Intake never writes over a record already at its outcome or waiting.

    The seen-before door answers each of them before intake (ADR-0154), so
    meeting one means the door did not run: intake fails, writes nothing,
    and so never loses the first refusal's reason or a held body.
    """
    seed(scenario.dl)
    before = scenario.dl.by_type("ReceivedActivityRecord")
    node = IntakeReceivedActivityNode()

    result = scenario.run(node, activity=_note_event(_rich_note()))

    assert result.status == Status.FAILURE
    assert result.internal_error
    assert "seen-before door" in node.feedback_message
    assert scenario.dl.by_type("ReceivedActivityRecord") == before


# ---------------------------------------------------------------------------
# Wiring faults: FAILURE, never a silent SUCCESS (ARCH-15-001)
# ---------------------------------------------------------------------------


@pytest.mark.spec("ARCH-15-001")
def test_datalayer_unavailable_returns_failure():
    node = IntakeReceivedActivityNode()
    node.datalayer = None
    node.activity = _note_event(_rich_note())

    assert node.update() == Status.FAILURE
    assert node.feedback_message == DATALAYER_UNAVAILABLE


@pytest.mark.spec("ARCH-15-001")
def test_missing_activity_on_blackboard_returns_failure(scenario):
    """No received event on the blackboard: FAILURE with the wiring reason.

    ``verdict_from_bt`` raises on this reason rather than refusing the sender
    — a handler that omitted ``activity=`` is our fault, not theirs.
    """
    node = IntakeReceivedActivityNode()
    result = scenario.run(node)

    assert result.status == Status.FAILURE
    assert not result.internal_error
    assert node.feedback_message == ACTIVITY_UNAVAILABLE


@pytest.mark.spec("ARCH-15-001")
def test_non_event_activity_returns_failure_with_wiring_reason(scenario):
    """A bare wire activity on the blackboard is not a received event."""
    node = IntakeReceivedActivityNode()
    bare = make(
        VultronActivity, type_="Add", actor=SENDER, object_=_rich_note()
    )

    result = scenario.run(node, activity=bare)

    assert result.status == Status.FAILURE
    assert node.feedback_message == ACTIVITY_UNAVAILABLE
    assert _archive_count(scenario.dl) == 0


# ---------------------------------------------------------------------------
# Factory placement: intake follows the door guards of every tree it builds
# ---------------------------------------------------------------------------


@pytest.mark.spec("CLP-10-017")
@pytest.mark.spec("CLP-10-010")
def test_shared_factory_records_after_the_doors_before_the_guards(scenario):
    """A precondition guard's refusal leaves the record for the outcome stage;
    a door's leaves nothing at all (ADR-0154)."""
    event = _note_event(_rich_note())
    tree = create_receive_activity_tree(
        name="RefusedBT",
        case_id=None,
        precondition_guards=[Failure(name="RefuseIt")],
        replica_effects=[],
    )

    result = scenario.run(tree, activity=event)

    assert result.status == Status.FAILURE
    intake = [
        i
        for i, child in enumerate(tree.children)
        if isinstance(child, IntakeReceivedActivityNode)
    ]
    assert intake == [len(tree.door_guards)]
    assert _archived(scenario.dl, ACTIVITY_ID)


@pytest.mark.spec("CLP-10-017")
@pytest.mark.spec("HP-01-005")
def test_a_door_refusal_records_nothing(scenario):
    """A copy not addressed to the receiver is never held in full."""
    event = _note_event(_rich_note())
    assert event.activity is not None
    elsewhere = event.model_copy(
        update={
            "activity": event.activity.model_copy(
                update={"to": ["https://example.org/actors/someone-else"]}
            )
        }
    )
    tree = create_receive_activity_tree(
        name="UnaddressedBT", case_id=None, precondition_guards=[]
    )

    result = scenario.run(tree, activity=elsewhere)

    assert result.status == Status.FAILURE
    assert scenario.dl.by_type("ReceivedActivityRecord") == {}


# ---------------------------------------------------------------------------
# Handler level: a door refusal writes nothing (CLP-10-017)
# ---------------------------------------------------------------------------


@pytest.mark.spec("CLP-10-017")
@pytest.mark.spec("HP-01-006")
def test_a_sender_guard_refusal_records_nothing():
    """``Add(ParticipantStatus)`` from a stranger is REFUSED by the sender guard.

    The receiver is not the CASE_MANAGER, so the guard takes the update from
    the CASE_MANAGER alone (PCR-03-001); the case names none, so the sender
    is refused.  The sender guard is a door, and intake follows the doors,
    so nothing of the message is recorded: the outcome stage leaves its
    receipt stub from the delivery's own body (CLP-10-018,
    ``test/adapters/driving/fastapi/test_received_outcome_stage.py``).
    """
    receiver = "https://example.org/users/vendor-intake"
    stranger = "https://example.org/users/stranger-intake"
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=receiver)

    case_id = "https://example.org/cases/case-intake"
    manager = make(
        as_CaseParticipant,
        id_=f"{case_id}/participants/vendor",
        context=case_id,
        attributed_to=receiver,
    )
    dl.create(manager)
    case = make(
        as_VulnerabilityCase,
        attributed_to=CASE_OWNER_ID,
        id_=case_id,
        name="Intake Test Case",
    )
    case.case_participants.append(manager.id_)
    case.actor_participant_index[receiver] = manager.id_
    dl.create(case)

    status = make(
        as_ParticipantStatus,
        id_=f"{case_id}/participants/stranger/statuses/s1",
        context=case_id,
        rm=RmDimension(state=RM.VALID),
    )
    target = make(
        as_CaseParticipant,
        id_=f"{case_id}/participants/stranger",
        context=case_id,
        attributed_to=stranger,
    )
    activity = add_status_to_participant_activity(
        status, target=target, actor=stranger, context=case
    )
    event = cast(
        AddParticipantStatusToParticipantReceivedEvent,
        received_event(activity, at=dl),
    ).model_copy(update={"receiving_actor_id": receiver})

    result = run_in_act(
        AddParticipantStatusToParticipantReceivedUseCase(dl, event)
    )

    assert result.disposition == HandlerDisposition.REFUSED
    assert not _archived(dl, activity.id_), "a door refusal recorded it"
