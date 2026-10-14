"""Tests for ``StoreReceivedObjectNode``'s outcomes (HP-01-003).

The node runs as an effect after intake: it stores the object, or reports it
as already held, absent, or a bare reference, and intake archives the activity
in every case.
"""

import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
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
from vultron.semantic_registry import extract_event
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Create,
)
from vultron.wire.as2.vocab.base.objects.object_types import as_Note

_RECEIVER = "https://example.org/actors/receiver"
_SENDER = "https://example.org/actors/sender"
_CASE_ID = "https://example.org/cases/intake-only"


@pytest.fixture
def dl() -> SqliteDataLayer:
    return SqliteDataLayer("sqlite:///:memory:", actor_id=_RECEIVER)


def _create_note():
    note = as_Note(
        id_=f"{_CASE_ID}/notes/n1",
        name="intake-only",
        content="a note",
        context=_CASE_ID,
    )
    activity = as_Create(actor=_SENDER, object_=note, context=_CASE_ID)
    return note, activity, extract_event(activity)


def _run(dl, event, store_node):
    tree = create_receive_activity_tree(
        name="StoreReceivedObjectTest",
        case_id=None,
        precondition_guards=[],
        replica_effects=[store_node],
    )
    result = BTBridge(datalayer=dl).execute_with_setup(
        tree=tree, actor_id=_RECEIVER, activity=event
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
def test_stores_the_object_and_archives_the_activity(dl):
    note, activity, event = _create_note()

    tree, result = _run(dl, event, _node(event))

    assert result.status == Status.SUCCESS
    node = find_node(tree, StoreReceivedObjectNode)
    assert node is not None and node.outcome is not None
    assert node.outcome.disposition is HandlerDisposition.APPLIED
    assert dl.read(note.id_) is not None
    assert isinstance(
        dl.read(ReceivedActivityRecord.build_id(activity.id_)),
        ReceivedActivityRecord,
    )


@pytest.mark.spec("HP-01-003")
def test_an_object_already_held_is_skipped(dl):
    note, _, event = _create_note()
    dl.create(note)

    tree, result = _run(dl, event, _node(event))

    node = find_node(tree, StoreReceivedObjectNode)
    assert result.status == Status.SUCCESS
    assert node is not None and node.outcome is not None
    assert node.outcome.disposition is HandlerDisposition.SKIPPED
    assert "already stored" in (node.outcome.reason or "")


@pytest.mark.spec("HP-01-003")
def test_a_missing_object_is_skipped_not_failed(dl):
    _, activity, event = _create_note()
    node = StoreReceivedObjectNode("Note", "urn:x:absent", None, "Note")

    _, result = _run(dl, event, node)

    assert result.status == Status.SUCCESS
    assert node.outcome is not None
    assert node.outcome.disposition is HandlerDisposition.SKIPPED
    # Intake still archived the activity that carried nothing storable.
    assert dl.read(ReceivedActivityRecord.build_id(activity.id_)) is not None
