"""Tests for ``StoreReceivedObjectNode``'s outcomes (HP-01-003).

The node runs as an effect after intake: it stores the object, or reports it
as already held, absent, or a bare reference, and intake archives the activity
in every case.
"""

import pytest
from py_trees.common import Status

from test.core.behaviors.case.note_delivery import create_note_delivery
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.store_received_object import (
    StoreReceivedObjectNode,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.use_cases.received._bt_verdict import find_node


def _run(datalayer, actor_id, event, store_node):
    tree = create_receive_activity_tree(
        name="StoreReceivedObjectTest",
        case_id=None,
        precondition_guards=[],
        replica_effects=[store_node],
    )
    result = BTBridge(datalayer=datalayer).execute_with_setup(
        tree=tree, actor_id=actor_id, activity=event
    )
    return tree, result


def _node(event, obj=None, id_key=None):
    return StoreReceivedObjectNode(
        event.object_type,
        id_key or event.object_id,
        obj if obj is not None else event.object_,
        "Note",
        event.activity_id,
    )


@pytest.mark.spec("HP-01-003")
def test_stores_the_object_and_archives_the_activity(datalayer, actor_id):
    note, activity, event = create_note_delivery(actor_id)

    tree, result = _run(datalayer, actor_id, event, _node(event))

    assert result.status == Status.SUCCESS
    node = find_node(tree, StoreReceivedObjectNode)
    assert node is not None and node.outcome is not None
    assert node.outcome.disposition is HandlerDisposition.APPLIED
    assert datalayer.read(note.id_) is not None
    assert isinstance(
        datalayer.read(ReceivedActivityRecord.build_id(activity.id_)),
        ReceivedActivityRecord,
    )


@pytest.mark.spec("HP-01-003")
def test_an_object_already_held_is_skipped(datalayer, actor_id):
    note, _, event = create_note_delivery(actor_id)
    datalayer.create(note)

    tree, result = _run(datalayer, actor_id, event, _node(event))

    node = find_node(tree, StoreReceivedObjectNode)
    assert result.status == Status.SUCCESS
    assert node is not None and node.outcome is not None
    assert node.outcome.disposition is HandlerDisposition.SKIPPED
    assert "already stored" in (node.outcome.reason or "")


@pytest.mark.spec("HP-01-003")
def test_a_missing_object_is_skipped_not_failed(datalayer, actor_id):
    _, activity, event = create_note_delivery(actor_id)
    node = StoreReceivedObjectNode("Note", "urn:x:absent", None, "Note")

    _, result = _run(datalayer, actor_id, event, node)

    assert result.status == Status.SUCCESS
    assert node.outcome is not None
    assert node.outcome.disposition is HandlerDisposition.SKIPPED
    # Intake still archived the activity that carried nothing storable.
    assert (
        datalayer.read(ReceivedActivityRecord.build_id(activity.id_))
        is not None
    )
