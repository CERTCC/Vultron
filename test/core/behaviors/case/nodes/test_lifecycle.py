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

"""Unit tests for CommitCaseLedgerEntryNode."""

import json
from typing import Any
from unittest.mock import patch

import py_trees
import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge, BTExecutionResult
from vultron.core.behaviors.case.nodes import CommitCaseLedgerEntryNode
from vultron.core.models.actor import VultronService
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.events.base import MessageSemantics, VultronEvent

_FACTORY_PATH = (
    "vultron.core.behaviors.case.nodes.lifecycle.create_commit_log_entry_tree"
)
_INNER_BRIDGE_PATH = "vultron.core.behaviors.case.nodes.lifecycle.BTBridge"

ACTOR_ID = "https://example.org/actors/vendor"
CASE_ID = "https://example.org/cases/case-001"
ACTIVITY_ID = "https://example.org/activities/act-001"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def datalayer():
    dl = SqliteDataLayer(
        "sqlite:///:memory:",
        actor_id=ACTOR_ID,
    )
    actor = VultronService(id_=ACTOR_ID, name="Vendor Co")
    dl.create(actor)
    return dl


@pytest.fixture
def bridge(datalayer):
    # No wire render port: a received entry records the received body, so
    # the node renders nothing (ADR-0107).
    return BTBridge(datalayer=datalayer)


# ---------------------------------------------------------------------------
# Helper: a received event carrying its received body
# ---------------------------------------------------------------------------


_CREATE_BODY: dict[str, Any] = {"id": ACTIVITY_ID, "type": "Create"}


def _received(
    body: dict[str, Any] | None = None,
    semantic_type: MessageSemantics = MessageSemantics.CREATE_CASE,
    actor_id: str = ACTOR_ID,
) -> VultronEvent:
    """A received event whose evidence is *body*, as the parser sealed it."""
    return VultronEvent(
        semantic_type=semantic_type,
        activity_id=ACTIVITY_ID,
        actor_id=actor_id,
        received_evidence=json.dumps(_CREATE_BODY if body is None else body),
    )


# ---------------------------------------------------------------------------
# Structure tests
# ---------------------------------------------------------------------------


def test_node_instantiates_with_case_id():
    node = CommitCaseLedgerEntryNode(case_id=CASE_ID)
    assert node is not None
    assert node.name == "CommitCaseLedgerEntryNode"


def test_node_instantiates_without_case_id():
    node = CommitCaseLedgerEntryNode()
    assert node is not None


# ---------------------------------------------------------------------------
# Execution tests
# ---------------------------------------------------------------------------


def test_no_case_id_returns_failure_without_building_inner_tree(bridge):
    """Node returns FAILURE when no case_id is available (ARCH-15-001)."""
    node = CommitCaseLedgerEntryNode()
    with (
        patch(_FACTORY_PATH) as mock_factory,
        patch(_INNER_BRIDGE_PATH) as mock_bridge,
    ):
        result = bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID, activity=None
        )
    assert result.status == Status.FAILURE
    mock_factory.assert_not_called()
    mock_bridge.assert_not_called()


def test_constructor_case_id_builds_inner_commit_tree(bridge):
    """Node composes CommitLogEntryBT when case_id is given at build."""
    activity = _received()
    node = CommitCaseLedgerEntryNode(case_id=CASE_ID)
    with (
        patch(_FACTORY_PATH) as mock_factory,
        patch(_INNER_BRIDGE_PATH) as mock_bridge_cls,
    ):
        mock_bridge_cls.return_value.execute_with_setup.return_value = (
            BTExecutionResult(status=Status.SUCCESS)
        )
        bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID, activity=activity
        )
    mock_factory.assert_called_once_with(
        case_id=CASE_ID,
        object_id=ACTIVITY_ID,
        semantic_type=MessageSemantics.CREATE_CASE.value,
        payload_snapshot=_CREATE_BODY,
    )
    execute_kwargs = (
        mock_bridge_cls.return_value.execute_with_setup.call_args.kwargs
    )
    assert execute_kwargs["actor_id"] == ACTOR_ID


def test_blackboard_case_id_builds_inner_commit_tree(bridge, datalayer):
    """Node reads case_id from blackboard written by a prior node."""
    node = CommitCaseLedgerEntryNode()  # no constructor param
    activity = _received()

    # Manually write case_id to the blackboard via a helper sequence node
    class _WriteCaseId(py_trees.behaviour.Behaviour):
        def __init__(self):
            super().__init__(name="_WriteCaseId")

        def setup(self, **kwargs):
            self.blackboard = self.attach_blackboard_client(
                name="_WriteCaseId"
            )
            self.blackboard.register_key(
                key="case_id", access=py_trees.common.Access.WRITE
            )

        def update(self) -> Status:
            self.blackboard.case_id = CASE_ID
            return Status.SUCCESS

    seq = py_trees.composites.Sequence(
        name="TestSeq", memory=False, children=[_WriteCaseId(), node]
    )

    with (
        patch(_FACTORY_PATH) as mock_factory,
        patch(_INNER_BRIDGE_PATH) as mock_bridge_cls,
    ):
        mock_bridge_cls.return_value.execute_with_setup.return_value = (
            BTExecutionResult(status=Status.SUCCESS)
        )
        bridge.execute_with_setup(
            tree=seq, actor_id=ACTOR_ID, activity=activity
        )

    mock_factory.assert_called_once_with(
        case_id=CASE_ID,
        object_id=ACTIVITY_ID,
        semantic_type=MessageSemantics.CREATE_CASE.value,
        payload_snapshot=_CREATE_BODY,
    )


def test_activity_on_blackboard_semantics_become_the_entry_semantic_type(
    bridge,
):
    """The entry's semantic_type is derived from activity.semantic_type.value."""
    activity = _received()
    node = CommitCaseLedgerEntryNode(case_id=CASE_ID)
    with (
        patch(_FACTORY_PATH) as mock_factory,
        patch(_INNER_BRIDGE_PATH) as mock_bridge_cls,
    ):
        mock_bridge_cls.return_value.execute_with_setup.return_value = (
            BTExecutionResult(status=Status.SUCCESS)
        )
        bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID, activity=activity
        )
    mock_factory.assert_called_once_with(
        case_id=CASE_ID,
        object_id=ACTIVITY_ID,
        semantic_type=MessageSemantics.CREATE_CASE.value,
        payload_snapshot=_CREATE_BODY,
    )


@pytest.mark.spec("CLP-07-011")
def test_received_body_is_forwarded_as_payload_snapshot_unchanged(bridge):
    """The snapshot is the received body as it arrived (ADR-0107).

    It names no case, as the Offer that opened a case does not, and the node
    writes none in: the entry names its case on the envelope.
    """
    body = {
        "id": ACTIVITY_ID,
        "type": "Create",
        "actor": ACTOR_ID,
        # Bare references stay bare: a replica dereferences them, the
        # receiver does not fill them in from its store.
        "object": "https://example.org/notes/held",
        "unknownExtension": {"kept": True},
    }
    node = CommitCaseLedgerEntryNode(case_id=CASE_ID)
    with (
        patch(_FACTORY_PATH) as mock_factory,
        patch(_INNER_BRIDGE_PATH) as mock_bridge_cls,
    ):
        mock_bridge_cls.return_value.execute_with_setup.return_value = (
            BTExecutionResult(status=Status.SUCCESS)
        )
        bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID, activity=_received(body)
        )
    mock_factory.assert_called_once_with(
        case_id=CASE_ID,
        object_id=ACTIVITY_ID,
        semantic_type=MessageSemantics.CREATE_CASE.value,
        payload_snapshot=body,
    )


@pytest.mark.spec("VM-08-002")
@pytest.mark.spec("IE-10-001")
def test_an_unrecorded_event_without_evidence_is_refused_not_recorded(bridge):
    """An event with no received body has nothing to record.

    It is a resend of an activity archived but never recorded (IE-10-001).
    It is not rebuilt from the event's objects: the node refuses it, a
    FAILURE the handler reports as REFUSED, rather than an internal error.
    """
    event = VultronEvent(
        semantic_type=MessageSemantics.CREATE_CASE,
        activity_id=ACTIVITY_ID,
        actor_id=ACTOR_ID,
    )
    node = CommitCaseLedgerEntryNode(case_id=CASE_ID)
    with patch(_FACTORY_PATH) as mock_factory:
        result = bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID, activity=event
        )

    assert result.status == Status.FAILURE
    assert result.internal_error is False
    assert "carries no received body" in (result.feedback_message or "")
    mock_factory.assert_not_called()


@pytest.mark.spec("VM-08-002")
@pytest.mark.spec("IE-10-001")
def test_a_recorded_resend_without_evidence_reuses_its_first_entry(
    bridge, datalayer
):
    """A resend of an archived activity is routed with no received evidence.

    Its first delivery's entry is its record, so the node commits nothing
    and succeeds rather than reporting a wiring fault.
    """
    datalayer.create(
        CaseLedgerEntry(
            case_id=CASE_ID,
            log_object_id=ACTIVITY_ID,
            semantic_type=MessageSemantics.CREATE_CASE.value,
            payload_snapshot=_CREATE_BODY,
            entry_hash="hash-1",
            prev_log_hash="hash-0",
            log_index=0,
        )
    )
    resend = VultronEvent(
        semantic_type=MessageSemantics.CREATE_CASE,
        activity_id=ACTIVITY_ID,
        actor_id=ACTOR_ID,
    )
    node = CommitCaseLedgerEntryNode(case_id=CASE_ID)
    with patch(_FACTORY_PATH) as mock_factory:
        result = bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID, activity=resend
        )

    assert result.status == Status.SUCCESS
    mock_factory.assert_not_called()


@pytest.mark.spec("CLP-07-013")
@pytest.mark.spec("IE-10-001")
def test_a_resend_whose_id_is_recorded_as_another_activity_is_refused(
    bridge, datalayer
):
    """An id the ledger records for one activity is not another's record.

    An archived redelivery is rebuilt from the body that arrived, so a resend
    reusing the id with a different activity type routes to another handler.
    Taking the first entry as its record would let that handler's effects run
    with no entry; the node refuses it instead, committing nothing.
    """
    datalayer.create(
        CaseLedgerEntry(
            case_id=CASE_ID,
            log_object_id=ACTIVITY_ID,
            semantic_type=MessageSemantics.CREATE_CASE.value,
            payload_snapshot=_CREATE_BODY,
            entry_hash="hash-1",
            prev_log_hash="hash-0",
            log_index=0,
        )
    )
    resend = VultronEvent(
        semantic_type=MessageSemantics.CLOSE_CASE,
        activity_id=ACTIVITY_ID,
        actor_id=ACTOR_ID,
    )
    node = CommitCaseLedgerEntryNode(case_id=CASE_ID)
    with patch(_FACTORY_PATH) as mock_factory:
        result = bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID, activity=resend
        )

    assert result.status == Status.FAILURE
    assert result.internal_error is False
    assert "as another activity" in (result.feedback_message or "")
    mock_factory.assert_not_called()


@pytest.mark.spec("ARCH-15-001")
def test_blackboard_activity_that_is_not_an_event_is_a_wiring_fault(bridge):
    """Only a received event carries a received body to record."""

    class _NotAnEvent:
        activity_id = ACTIVITY_ID
        semantic_type = MessageSemantics.CREATE_CASE

    node = CommitCaseLedgerEntryNode(case_id=CASE_ID)
    with patch(_FACTORY_PATH) as mock_factory:
        result = bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID, activity=_NotAnEvent()
        )

    assert result.status == Status.FAILURE
    assert result.internal_error is True
    assert "is not a received event" in (result.feedback_message or "")
    mock_factory.assert_not_called()


def test_no_activity_returns_failure(bridge):
    """When no activity on blackboard, node returns FAILURE with a warning log."""
    node = CommitCaseLedgerEntryNode(case_id=CASE_ID)
    with (
        patch(_FACTORY_PATH) as mock_factory,
        patch(_INNER_BRIDGE_PATH) as mock_bridge_cls,
    ):
        mock_bridge_cls.return_value.execute_with_setup.return_value = (
            BTExecutionResult(status=Status.SUCCESS)
        )
        result = bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID, activity=None
        )
    assert result.status == Status.FAILURE
    mock_factory.assert_not_called()


def test_inner_commit_bt_failure_propagates(bridge):
    node = CommitCaseLedgerEntryNode(case_id=CASE_ID)
    with (
        patch(_FACTORY_PATH) as mock_factory,
        patch(_INNER_BRIDGE_PATH) as mock_bridge_cls,
    ):
        mock_factory.return_value = object()
        mock_bridge_cls.return_value.execute_with_setup.return_value = (
            BTExecutionResult(
                status=Status.FAILURE, feedback_message="commit failed"
            )
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
    assert result.status == Status.FAILURE


# ---------------------------------------------------------------------------
# Pending assertions — design note
# ---------------------------------------------------------------------------
# CommitCaseLedgerEntryNode runs exclusively on the CaseActor side. Per
# SYNC-11-004, the CaseActor MUST NOT use the pending-assertion store for
# its own commits; DataLayer idempotency (_find_equivalent_recorded_entry)
# already guards against duplicate CaseActor commits.
#
# Participant-side pending assertions are recorded in trigger use cases
# (e.g., SvcAddNoteToCaseUseCase) after the activity is successfully
# enqueued, and cleared in AnnounceLedgerEntryReceivedUseCase when the
# matching Announce(CaseLedgerEntry) arrives — see SYNC-11-002/003.


# ---------------------------------------------------------------------------
# CLP-07-003: actor-identity check in the receive pipeline
# ---------------------------------------------------------------------------


DIFFERENT_ACTOR = "https://example.org/actors/impostor"
CASE_ID_CLP = "https://example.org/cases/case-007"


@pytest.mark.spec("CLP-07-003")
def test_actor_identity_mismatch_returns_failure(bridge):
    """CLP-07-003: CommitCaseLedgerEntryNode raises VultronCanonicalEntryError
    when payloadSnapshot.actor does not match activity.actor_id; the bridge
    converts it to FAILURE and records the error in the feedback message."""
    payload = {
        "type": "Add",
        "actor": DIFFERENT_ACTOR,
        "object": {
            "type": "Note",
            "id": "https://example.org/notes/n1",
            "context": CASE_ID_CLP,
        },
        "context": CASE_ID_CLP,
        "published": "2026-01-01T12:00:00+00:00",
    }
    activity = _received(
        payload,
        semantic_type=MessageSemantics.ADD_NOTE_TO_CASE,
        actor_id=ACTOR_ID,
    )
    node = CommitCaseLedgerEntryNode(case_id=CASE_ID_CLP)
    with patch(_FACTORY_PATH) as mock_factory, patch(_INNER_BRIDGE_PATH):
        result = bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID, activity=activity
        )
    assert result.status == Status.FAILURE
    assert "CLP-07-003" in (result.feedback_message or "")
    mock_factory.assert_not_called()


@pytest.mark.spec("CLP-07-003")
def test_case_manager_as_participant_commits_without_error(bridge):
    """CLP-07-003: a CASE_MANAGER who is also a participant may assert
    participant activities — snapshot.actor == activity.actor_id, so no error.
    """
    CASE_MANAGER_ID = "https://example.org/actors/case-manager"
    payload = {
        "type": "Add",
        "actor": CASE_MANAGER_ID,
        "object": {
            "type": "Note",
            "id": "https://example.org/notes/n2",
            "context": CASE_ID_CLP,
        },
        "context": CASE_ID_CLP,
        "published": "2026-01-01T12:00:00+00:00",
    }
    activity = _received(
        payload,
        semantic_type=MessageSemantics.ADD_NOTE_TO_CASE,
        actor_id=CASE_MANAGER_ID,
    )
    node = CommitCaseLedgerEntryNode(case_id=CASE_ID_CLP)
    with (
        patch(_FACTORY_PATH) as mock_factory,
        patch(_INNER_BRIDGE_PATH) as mock_bridge_cls,
    ):
        mock_bridge_cls.return_value.execute_with_setup.return_value = (
            BTExecutionResult(status=Status.SUCCESS)
        )
        result = bridge.execute_with_setup(
            tree=node, actor_id=CASE_MANAGER_ID, activity=activity
        )
    assert result.status == Status.SUCCESS
    mock_factory.assert_called_once()


def _note_payload(actor: str, note_id: str) -> dict:
    return {
        "type": "Add",
        "actor": actor,
        "object": {
            "type": "Note",
            "id": note_id,
            "context": CASE_ID_CLP,
        },
        "context": CASE_ID_CLP,
        "published": "2026-01-01T12:00:00+00:00",
    }


@pytest.mark.spec("CLP-07-003")
@pytest.mark.spec("OID-01-006")
def test_slash_spelled_snapshot_actor_commits(bridge):
    """CLP-07-003: the snapshot keeps the sender's trailing slash while the
    event's ``actor_id`` is normalised; the two name one actor, so the entry
    commits (``same_actor_id``)."""
    activity = _received(
        _note_payload(ACTOR_ID + "/", "https://example.org/notes/n3"),
        semantic_type=MessageSemantics.ADD_NOTE_TO_CASE,
        actor_id=ACTOR_ID,
    )
    node = CommitCaseLedgerEntryNode(case_id=CASE_ID_CLP)
    with (
        patch(_FACTORY_PATH) as mock_factory,
        patch(_INNER_BRIDGE_PATH) as mock_bridge_cls,
    ):
        mock_bridge_cls.return_value.execute_with_setup.return_value = (
            BTExecutionResult(status=Status.SUCCESS)
        )
        result = bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID, activity=activity
        )
    assert result.status == Status.SUCCESS
    mock_factory.assert_called_once()


@pytest.mark.spec("CLP-07-003")
def test_slash_spelled_different_actor_still_refused(bridge):
    """CLP-07-003: the trailing-slash tolerance does not admit a different
    actor — a slash-spelled impostor in the snapshot is still refused."""
    activity = _received(
        _note_payload(DIFFERENT_ACTOR + "/", "https://example.org/notes/n4"),
        semantic_type=MessageSemantics.ADD_NOTE_TO_CASE,
        actor_id=ACTOR_ID,
    )
    node = CommitCaseLedgerEntryNode(case_id=CASE_ID_CLP)
    with patch(_FACTORY_PATH) as mock_factory, patch(_INNER_BRIDGE_PATH):
        result = bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID, activity=activity
        )
    assert result.status == Status.FAILURE
    assert "CLP-07-003" in (result.feedback_message or "")
    mock_factory.assert_not_called()


@pytest.mark.spec("CLP-07-003")
@pytest.mark.spec("OID-01-006")
def test_inline_slash_spelled_snapshot_actor_passes_the_identity_check(
    bridge,
):
    """An inline actor object is read by its id, normalised, not by its
    ``str()``: an inline sender profile spelled with a trailing slash passes
    the CLP-07-003 identity check and reaches the commit."""
    payload = _note_payload(ACTOR_ID, "https://example.org/notes/n5")
    payload["actor"] = {"id": ACTOR_ID + "/", "type": "Person"}
    activity = _received(
        payload,
        semantic_type=MessageSemantics.ADD_NOTE_TO_CASE,
        actor_id=ACTOR_ID,
    )
    node = CommitCaseLedgerEntryNode(case_id=CASE_ID_CLP)
    with (
        patch(_FACTORY_PATH) as mock_factory,
        patch(_INNER_BRIDGE_PATH) as mock_bridge_cls,
    ):
        mock_bridge_cls.return_value.execute_with_setup.return_value = (
            BTExecutionResult(status=Status.SUCCESS)
        )
        result = bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID, activity=activity
        )
    assert result.status == Status.SUCCESS
    mock_factory.assert_called_once()


@pytest.mark.spec("CLP-07-003")
@pytest.mark.spec("OID-01-006")
def test_snapshot_actor_naming_no_id_is_refused(bridge):
    """A snapshot actor that names no id cannot be shown to be the sender,
    so the entry is refused rather than compared as text."""
    payload = _note_payload(ACTOR_ID, "https://example.org/notes/n6")
    payload["actor"] = {"type": "Person", "name": ACTOR_ID}
    activity = _received(
        payload,
        semantic_type=MessageSemantics.ADD_NOTE_TO_CASE,
        actor_id=ACTOR_ID,
    )
    node = CommitCaseLedgerEntryNode(case_id=CASE_ID_CLP)
    with patch(_FACTORY_PATH) as mock_factory, patch(_INNER_BRIDGE_PATH):
        result = bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID, activity=activity
        )
    assert result.status == Status.FAILURE
    assert "CLP-07-003" in (result.feedback_message or "")
    mock_factory.assert_not_called()
