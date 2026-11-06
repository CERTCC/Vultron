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

"""The seen-before door answers a resend from its record (ADR-0154).

Each record the receiver can hold for an activity is seeded, a received tree
built by the shared factory is run on a delivery of that activity, and the
handler's verdict and what ran are asserted:

- a receipt stub: ``REFUSED`` with the stub's reason, nothing run;
- an archive: ``SKIPPED``, nothing run;
- a record waiting for a replay: ``SKIPPED``, nothing run, the hold intact;
- a record a run left in holding with no verdict: the delivery runs again;
- no record: the delivery runs, and intake records it.

A nested received tree meets the record its enclosing tree's intake wrote,
and still runs (the close-case tree's inner tree, CM-23-002).
"""

from typing import cast

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.bt_harness import BTTestScenario
from test.support.received import (
    TEST_SENDER_POSITION,
    archive_received,
    intake_received,
    with_evidence,
)
from vultron.core.behaviors.case.nodes.addressee import (
    ENCLOSING_TREE_ADDRESSEE_CHECK,
)
from vultron.core.behaviors.case.nodes.post_close import PostCloseExemption
from vultron.core.behaviors.case.nodes.seen_before import (
    ActivityNotSeenBeforeNode,
    SeenBefore,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.helpers import ACTIVITY_UNAVAILABLE
from vultron.core.models.activity import VultronActivity
from vultron.core.models.events.note import AddNoteToCaseReceivedEvent
from vultron.core.models.note import VultronNote
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
    ReceivedStage,
)
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.received_holding import hold_for_replay
from vultron.core.services.received_outcome import write_receipt_stub
from vultron.core.use_cases.received._bt_verdict import (
    seen_before_verdict,
    verdict_from_bt,
)

SENDER = "https://example.org/actors/reporter"
RECEIVER = "https://example.org/actors/vendor"
CASE_ID = "https://example.org/cases/c-seen"
ACTIVITY_ID = "https://example.org/activities/add-note-seen"
STUB_REASON = "SampleBT: the first delivery's refusal (HP-01-006)"


class _Ran(py_trees.behaviour.Behaviour):
    """A guard that records that the handling tree reached it."""

    def __init__(self, name: str = "Ran") -> None:
        super().__init__(name=name)
        self.ticks = 0

    def update(self) -> Status:
        self.ticks += 1
        return Status.SUCCESS


def _event() -> AddNoteToCaseReceivedEvent:
    note = VultronNote(
        id_="https://example.org/notes/n-seen", content="x", context=CASE_ID
    )
    activity = VultronActivity(
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


def _tree(ran: _Ran) -> py_trees.behaviour.Behaviour:
    return create_receive_activity_tree(
        name="SampleBT", case_id=None, precondition_guards=[ran]
    )


def _record(dl) -> ReceivedActivityRecord | None:
    record = dl.read(ReceivedActivityRecord.build_id(ACTIVITY_ID))
    return record if isinstance(record, ReceivedActivityRecord) else None


def _stub(dl) -> None:
    event = _event()
    write_receipt_stub(
        cast(CasePersistence, dl),
        ACTIVITY_ID,
        sender_id=SENDER,
        reason=STUB_REASON,
        received_body=event.received_evidence,
    )


def _archive(dl) -> None:
    archive_received(dl, _event().activity)


def _waiting(dl) -> None:
    event = _event()
    assert event.received_evidence is not None
    hold_for_replay(
        cast(CasePersistence, dl), ACTIVITY_ID, event.received_evidence
    )


@pytest.fixture
def scenario() -> BTTestScenario:
    return BTTestScenario(actor_id=RECEIVER)


@pytest.mark.spec("CLP-10-018")
@pytest.mark.spec("CLP-10-077")
def test_a_resend_of_a_refused_message_is_refused_with_the_stubs_reason(
    scenario,
):
    """Refused again, for the first reason, and nothing runs (ADR-0154)."""
    _stub(scenario.dl)
    before = _record(scenario.dl)
    ran = _Ran()
    tree = _tree(ran)

    result = scenario.run(tree, activity=_event())

    verdict = verdict_from_bt(tree, result, label="SampleBT")
    assert verdict.disposition is HandlerDisposition.REFUSED
    assert verdict.reason == STUB_REASON
    assert ran.ticks == 0
    assert _record(scenario.dl) == before


@pytest.mark.spec("HP-01-003")
@pytest.mark.spec("IE-10-001")
@pytest.mark.parametrize(
    ("seed", "seen"),
    [(_archive, SeenBefore.APPLIED), (_waiting, SeenBefore.WAITING)],
    ids=["applied", "waiting"],
)
def test_a_resend_of_an_applied_or_waiting_message_is_skipped(
    scenario, seed, seen
):
    """``SKIPPED``, with nothing re-run and the record left as it was."""
    seed(scenario.dl)
    before = _record(scenario.dl)
    ran = _Ran()
    tree = _tree(ran)

    result = scenario.run(tree, activity=_event())

    verdict = verdict_from_bt(tree, result, label="SampleBT")
    assert verdict.disposition is HandlerDisposition.SKIPPED
    door = next(
        n for n in tree.iterate() if isinstance(n, ActivityNotSeenBeforeNode)
    )
    assert door.seen is seen
    assert ran.ticks == 0
    assert _record(scenario.dl) == before


@pytest.mark.spec("CLP-10-074")
def test_a_message_left_in_holding_with_no_verdict_runs_again(scenario):
    """A run that raised left the record ``HELD``; the resend re-runs it.

    Runs are serialized per actor, so the only ``HELD`` record owing nothing
    that a resend can meet is one a finished run left (ADR-0154).
    """
    intake_received(scenario.dl, _event().activity)
    ran = _Ran()
    tree = _tree(ran)

    result = scenario.run(tree, activity=_event())

    assert result.status == Status.SUCCESS
    assert ran.ticks == 1
    record = _record(scenario.dl)
    assert record is not None and record.stage is ReceivedStage.HELD
    # The stages that answer a delivery once read this (SYNC-18-009,
    # SYNC-21-018).
    door = next(
        n for n in tree.iterate() if isinstance(n, ActivityNotSeenBeforeNode)
    )
    assert door.rerun is True


@pytest.mark.spec("CLP-10-017")
def test_a_delivery_never_seen_runs_and_is_recorded(scenario):
    ran = _Ran()
    tree = _tree(ran)

    result = scenario.run(tree, activity=_event())

    assert result.status == Status.SUCCESS
    assert seen_before_verdict(tree) is None
    door = next(
        n for n in tree.iterate() if isinstance(n, ActivityNotSeenBeforeNode)
    )
    assert door.rerun is False
    assert ran.ticks == 1
    record = _record(scenario.dl)
    assert record is not None
    assert (record.stage, record.replay_owed) == (ReceivedStage.HELD, False)


@pytest.mark.spec("CLP-10-010")
@pytest.mark.spec("CM-23-002")
def test_a_nested_received_tree_runs_past_its_enclosing_trees_record(
    scenario,
):
    """The inner tree's door meets the outer intake's record and passes.

    The shape of the close-case tree, whose inner ``CloseCaseReceive`` tree
    is built by the same factory and runs as the outer tree's effect.
    """
    ran = _Ran("InnerRan")
    inner = create_receive_activity_tree(
        name="InnerBT",
        case_id=None,
        precondition_guards=[ran],
        addressee_exemption=ENCLOSING_TREE_ADDRESSEE_CHECK,
        post_close_exemption=PostCloseExemption.ENCLOSING_TREE_GUARDS,
    )
    outer = create_receive_activity_tree(
        name="OuterBT",
        case_id=None,
        precondition_guards=[inner],
    )

    result = scenario.run(outer, activity=_event())

    assert result.status == Status.SUCCESS
    assert ran.ticks == 1
    doors = [
        n for n in outer.iterate() if isinstance(n, ActivityNotSeenBeforeNode)
    ]
    assert [d.status for d in doors] == [Status.SUCCESS, Status.SUCCESS]


@pytest.mark.spec("ARCH-15-001")
def test_the_door_fails_closed_with_no_datalayer() -> None:
    """A door composed without its store refuses nothing silently."""
    door = ActivityNotSeenBeforeNode(label="SampleBT")
    door.datalayer = None

    assert door.update() == Status.FAILURE
    assert door.seen is None


@pytest.mark.spec("ARCH-15-001")
def test_the_door_fails_closed_without_a_received_event(scenario) -> None:
    """A bare value on the blackboard is no received event to look up."""
    door = ActivityNotSeenBeforeNode(label="SampleBT")

    result = scenario.run(door, activity="not-an-event")

    assert result.status == Status.FAILURE
    assert door.seen is None
    assert door.feedback_message == ACTIVITY_UNAVAILABLE
