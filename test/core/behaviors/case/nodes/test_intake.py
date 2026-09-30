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

from typing import cast

import pytest
from py_trees.behaviours import Failure
from py_trees.common import Status

from test.core.behaviors.bt_harness import BTTestScenario
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
from vultron.core.models.activity import VultronActivity
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.events.note import CreateNoteReceivedEvent
from vultron.core.models.events.status import (
    AddParticipantStatusToParticipantReceivedEvent,
)
from vultron.core.models.note import VultronNote
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.rm import RM
from vultron.core.use_cases.received.status import (
    AddParticipantStatusToParticipantReceivedUseCase,
)
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import add_status_to_participant_activity
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import as_ParticipantStatus
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

SENDER = "https://example.org/actors/reporter"
RECEIVER = "https://example.org/actors/vendor"
NOTE_ID = "https://example.org/notes/n-1"
CASE_ID = "https://example.org/cases/c-1"
ACTIVITY_ID = "https://example.org/activities/create-note-1"


def _note_event(note: VultronNote) -> CreateNoteReceivedEvent:
    """A ``Create(Note)`` event whose wire activity inlines *note*."""
    activity = VultronActivity(
        id_=ACTIVITY_ID,
        type_="Create",
        actor=SENDER,
        object_=note,
        to=[RECEIVER],
    )
    return CreateNoteReceivedEvent(
        activity_id=activity.id_,
        actor_id=SENDER,
        object_=note,
        activity=activity,
        receiving_actor_id=RECEIVER,
    )


def _rich_note() -> VultronNote:
    return VultronNote(id_=NOTE_ID, content="what arrived", context=CASE_ID)


def _archived_ids(dl: SqliteDataLayer, type_: str) -> set[str]:
    return set(dl.by_type(type_).keys())


@pytest.fixture
def scenario() -> BTTestScenario:
    return BTTestScenario(actor_id=RECEIVER)


# ---------------------------------------------------------------------------
# Archive the activity, idempotently, and nothing else
# ---------------------------------------------------------------------------


@pytest.mark.spec("CLP-10-017")
def test_intake_archives_the_received_activity(scenario):
    event = _note_event(_rich_note())
    node = IntakeReceivedActivityNode()

    result = scenario.run(node, activity=event)

    scenario.assert_success(result)
    assert ACTIVITY_ID in _archived_ids(scenario.dl, "Create")
    assert node.stored_ids == [ACTIVITY_ID]
    assert node.found_ids == []
    assert node.stored_anything


@pytest.mark.spec("CLP-10-017")
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
def test_inlined_case_does_not_become_a_replica(scenario):
    case = VulnerabilityCase(id_=CASE_ID, name="not mine to seed")
    activity = VultronActivity(
        id_="https://example.org/activities/announce-1",
        type_="Announce",
        actor=SENDER,
        object_=case,
    )
    event = CreateNoteReceivedEvent(
        activity_id=activity.id_,
        actor_id=SENDER,
        object_=case,
        activity=activity,
    )

    scenario.assert_success(
        scenario.run(IntakeReceivedActivityNode(), activity=event)
    )

    assert scenario.dl.read_case(CASE_ID) is None
    assert activity.id_ in _archived_ids(scenario.dl, "Announce")


@pytest.mark.spec("CLP-10-017")
def test_second_intake_of_the_same_activity_writes_nothing(scenario):
    event = _note_event(_rich_note())
    scenario.assert_success(
        scenario.run(IntakeReceivedActivityNode(), activity=event)
    )
    before = scenario.dl.by_type("Create")

    second = IntakeReceivedActivityNode()
    result = scenario.run(second, activity=event)

    scenario.assert_success(result)
    assert second.stored_ids == []
    assert second.found_ids == [ACTIVITY_ID]
    assert not second.stored_anything
    assert scenario.dl.by_type("Create") == before


@pytest.mark.spec("CLP-10-017")
def test_intake_with_no_wire_activity_archives_nothing_and_succeeds(scenario):
    """A drain event carries an object and no activity: nothing to fail on."""
    event = CreateNoteReceivedEvent(
        activity_id="urn:vultron:drain:1",
        actor_id=SENDER,
        object_=_rich_note(),
    )
    node = IntakeReceivedActivityNode()

    scenario.assert_success(scenario.run(node, activity=event))

    assert node.stored_ids == []
    assert node.found_ids == []
    assert not node.stored_anything


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
    bare = VultronActivity(type_="Create", actor=SENDER, object_=_rich_note())

    result = scenario.run(node, activity=bare)

    assert result.status == Status.FAILURE
    assert node.feedback_message == ACTIVITY_UNAVAILABLE
    assert len(scenario.dl.by_type("Create")) == 0


# ---------------------------------------------------------------------------
# Factory placement: intake is the first child of every tree it builds
# ---------------------------------------------------------------------------


@pytest.mark.spec("CLP-10-017")
@pytest.mark.spec("CLP-10-018")
def test_shared_factory_runs_intake_first_even_when_a_guard_refuses(scenario):
    """Intake precedes the guards, so a refusal leaves the archive in place."""
    event = _note_event(_rich_note())
    tree = create_receive_activity_tree(
        name="RefusedBT",
        case_id=None,
        precondition_guards=[Failure(name="RefuseIt")],
        effect_nodes=[],
    )

    result = scenario.run(tree, activity=event)

    assert result.status == Status.FAILURE
    assert isinstance(tree.children[0], IntakeReceivedActivityNode)
    assert ACTIVITY_ID in _archived_ids(scenario.dl, "Create")


# ---------------------------------------------------------------------------
# Handler level: a refused assertion is still on record (CLP-10-018)
# ---------------------------------------------------------------------------


@pytest.mark.spec("CLP-10-018")
def test_refused_participant_status_leaves_the_archive_readable():
    """``Add(ParticipantStatus)`` from a stranger is REFUSED by the sender guard.

    ``VerifySenderIsParticipantNode`` refuses a sender who is not on the
    case; intake ran first, so the activity is archived in the receiver's
    store afterwards.
    """
    receiver = "https://example.org/users/vendor-intake"
    stranger = "https://example.org/users/stranger-intake"
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=receiver)

    case_id = "https://example.org/cases/case-intake"
    manager = as_CaseParticipant(
        id_=f"{case_id}/participants/vendor",
        context=case_id,
        attributed_to=receiver,
    )
    dl.create(manager)
    case = as_VulnerabilityCase(id_=case_id, name="Intake Test Case")
    case.case_participants.append(manager.id_)
    case.actor_participant_index[receiver] = manager.id_
    dl.create(case)

    status = as_ParticipantStatus(
        id_=f"{case_id}/participants/stranger/statuses/s1",
        context=case_id,
        rm=RmDimension(state=RM.VALID),
    )
    target = as_CaseParticipant(
        id_=f"{case_id}/participants/stranger",
        context=case_id,
        attributed_to=stranger,
    )
    activity = add_status_to_participant_activity(
        status, target=target, actor=stranger, context=case
    )
    event = cast(
        AddParticipantStatusToParticipantReceivedEvent,
        extract_event(activity),
    ).model_copy(update={"receiving_actor_id": receiver})

    result = AddParticipantStatusToParticipantReceivedUseCase(
        dl, event
    ).execute()

    assert result.disposition == HandlerDisposition.REFUSED
    assert activity.id_ in _archived_ids(dl, "Add"), "archive lost on refusal"
