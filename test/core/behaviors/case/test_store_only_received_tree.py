"""Tests for the shared store-only received tree (#3871, CLP-10-005).

Every store-only received handler builds this tree, so its outcomes are pinned
here once: the object is stored or reported as already held / absent / a bare
reference, and intake archives the activity in every case.
"""

import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.store_received_object import (
    StoreReceivedObjectNode,
)
from vultron.core.behaviors.case.store_only_received_tree import (
    create_store_only_received_tree,
)
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.use_cases.received._bt_verdict import find_node
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import create_participant_activity
from vultron.wire.as2.vocab.objects.case_participant import (
    as_CaseParticipant,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_RECEIVER = "https://example.org/actors/receiver"
_SENDER = "https://example.org/actors/sender"
_CASE_ID = "https://example.org/cases/store-only"


@pytest.fixture
def make_payload():
    """Extract the received event from an AS2 activity."""
    return extract_event


@pytest.fixture
def dl() -> SqliteDataLayer:
    return SqliteDataLayer("sqlite:///:memory:", actor_id=_RECEIVER)


def _create_participant(make_payload):
    participant = as_CaseParticipant(
        id_=f"{_CASE_ID}/participants/p1",
        attributed_to=_SENDER,
        context=_CASE_ID,
    )
    activity = create_participant_activity(
        participant,
        target=_CASE_ID,
        actor=_SENDER,
        context=as_VulnerabilityCase(id_=_CASE_ID, name="store-only"),
    )
    return participant, activity, make_payload(activity)


def _run(dl, event, store_node):
    tree = create_store_only_received_tree("StoreOnlyTest", store_node)
    result = BTBridge(datalayer=dl).execute_with_setup(
        tree=tree, actor_id=_RECEIVER, activity=event
    )
    return tree, result


def _node(event, obj=None, id_key=None):
    return StoreReceivedObjectNode(
        event.object_type,
        id_key or event.participant_id,
        obj if obj is not None else event.participant,
        "CaseParticipant",
        event.activity_id,
    )


def test_stores_the_object_and_archives_the_activity(dl, make_payload):
    participant, activity, event = _create_participant(make_payload)

    tree, result = _run(dl, event, _node(event))

    assert result.status == Status.SUCCESS
    node = find_node(tree, StoreReceivedObjectNode)
    assert node is not None and node.outcome is not None
    assert node.outcome.disposition is HandlerDisposition.APPLIED
    assert dl.read(participant.id_) is not None
    assert isinstance(
        dl.read(ReceivedActivityRecord.build_id(activity.id_)),
        ReceivedActivityRecord,
    )


def test_an_object_already_held_is_skipped(dl, make_payload):
    participant, _, event = _create_participant(make_payload)
    dl.create(participant)

    tree, result = _run(dl, event, _node(event))

    node = find_node(tree, StoreReceivedObjectNode)
    assert result.status == Status.SUCCESS
    assert node is not None and node.outcome is not None
    assert node.outcome.disposition is HandlerDisposition.SKIPPED
    assert "already stored" in (node.outcome.reason or "")


def test_a_missing_object_is_skipped_not_failed(dl, make_payload):
    _, activity, event = _create_participant(make_payload)
    node = StoreReceivedObjectNode(
        "CaseParticipant", "urn:x:absent", None, "CaseParticipant"
    )

    _, result = _run(dl, event, node)

    assert result.status == Status.SUCCESS
    assert node.outcome is not None
    assert node.outcome.disposition is HandlerDisposition.SKIPPED
    # Intake still archived the Create that carried nothing storable.
    assert dl.read(ReceivedActivityRecord.build_id(activity.id_)) is not None


def test_intake_only_tree_archives_without_a_store_node(dl, make_payload):
    _, activity, event = _create_participant(make_payload)

    tree, result = _run(dl, event, None)

    assert result.status == Status.SUCCESS
    assert find_node(tree, StoreReceivedObjectNode) is None
    assert dl.read(ReceivedActivityRecord.build_id(activity.id_)) is not None
