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

"""Tests for note.add_note_trigger_tree factory."""

import pytest
import py_trees
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.note.add_note_trigger_tree import (
    add_note_to_case_trigger_bt,
)
from vultron.core.behaviors.note.nodes import (
    AttachNoteFromResultNode,
    CreateNoteNode,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import (
    FinderParticipant,
    VendorParticipant,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase

CASE_ACTOR_ID = "https://example.org/actors/case-actor"
ACTIVITY_ID = "https://example.org/activities/act-01"
NOTE_ID = "https://example.org/notes/note-01"
NOTE_NAME = "Test Note"
NOTE_CONTENT = "Test note content"


class _FakeTriggerFactory:
    def create_note(
        self,
        *,
        name: str,
        content: str,
        context_id: str,
        attributed_to: str,
        in_reply_to: str | None,
    ) -> tuple[str, dict]:
        return (
            NOTE_ID,
            {
                "id": NOTE_ID,
                "name": name,
                "content": content,
                "context": context_id,
                "attributedTo": attributed_to,
                "inReplyTo": in_reply_to or "",
            },
        )


@pytest.fixture
def dl():
    actor = as_Service(name="finder")
    reset_datalayer(actor.id_)
    store = SqliteDataLayer("sqlite:///:memory:", actor_id=actor.id_)
    store.clear_all()
    store.create(actor)
    return store, actor


@pytest.fixture
def bridge(dl):
    store, _ = dl
    return BTBridge(datalayer=store)


def _make_case_with_case_manager(
    store: SqliteDataLayer,
    actor_id: str,
) -> VulnerabilityCase:
    case = VulnerabilityCase(name="Test Case")
    finder_participant = FinderParticipant(
        attributed_to=actor_id,
        context=case.id_,
    )
    case_manager_participant = VendorParticipant(
        attributed_to=CASE_ACTOR_ID,
        context=case.id_,
    )
    case_manager_participant.add_role(CVDRole.CASE_MANAGER)
    case.case_participants = [
        finder_participant.id_,
        case_manager_participant.id_,
    ]
    case.actor_participant_index = {
        actor_id: finder_participant.id_,
        CASE_ACTOR_ID: case_manager_participant.id_,
    }
    store.create(case)
    store.create(finder_participant)
    store.create(case_manager_participant)
    return case


class TestAddNoteToCaseTriggerBT:
    def test_tree_name(self):
        result_out: dict = {}
        tree = add_note_to_case_trigger_bt(
            case_id="https://example.org/cases/c1",
            note_name=NOTE_NAME,
            note_content=NOTE_CONTENT,
            result_out=result_out,
            activity_builder=lambda _: [],
        )
        assert tree.name == "AddNoteToCaseTriggerBT"

    def test_tree_has_three_children(self):
        result_out: dict = {}
        tree = add_note_to_case_trigger_bt(
            case_id="https://example.org/cases/c1",
            note_name=NOTE_NAME,
            note_content=NOTE_CONTENT,
            result_out=result_out,
            activity_builder=lambda _: [],
        )
        assert isinstance(tree, py_trees.composites.Sequence)
        children = tree.children
        assert len(children) == 3
        assert isinstance(children[0], CreateNoteNode)
        assert isinstance(children[1], AttachNoteFromResultNode)
        assert isinstance(children[2], py_trees.composites.Sequence)
        assert children[2].name == "SenderSideBT"

    def test_success_creates_note_and_attaches_to_case(self, dl, bridge):
        store, actor = dl
        case = _make_case_with_case_manager(store, actor.id_)
        result_out: dict = {}

        tree = add_note_to_case_trigger_bt(
            case_id=case.id_,
            note_name=NOTE_NAME,
            note_content=NOTE_CONTENT,
            result_out=result_out,
            activity_builder=lambda _: [ACTIVITY_ID],
        )
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=actor.id_,
            trigger_activity_factory=_FakeTriggerFactory(),
        )
        assert result.status == Status.SUCCESS
        assert result_out.get("note_id") == NOTE_ID
        refreshed = store.read(case.id_)
        assert refreshed is not None
        assert NOTE_ID in refreshed.notes

    def test_success_queues_activity_to_outbox(self, dl, bridge):
        store, actor = dl
        case = _make_case_with_case_manager(store, actor.id_)
        result_out: dict = {}

        tree = add_note_to_case_trigger_bt(
            case_id=case.id_,
            note_name=NOTE_NAME,
            note_content=NOTE_CONTENT,
            result_out=result_out,
            activity_builder=lambda _: [ACTIVITY_ID],
        )
        bridge.execute_with_setup(
            tree=tree,
            actor_id=actor.id_,
            trigger_activity_factory=_FakeTriggerFactory(),
        )
        outbox = store.clone_for_actor(actor.id_).outbox_list()
        assert ACTIVITY_ID in outbox

    def test_failure_when_trigger_factory_absent(self, dl, bridge):
        store, actor = dl
        case = _make_case_with_case_manager(store, actor.id_)
        result_out: dict = {}
        tree = add_note_to_case_trigger_bt(
            case_id=case.id_,
            note_name=NOTE_NAME,
            note_content=NOTE_CONTENT,
            result_out=result_out,
            activity_builder=lambda _: [ACTIVITY_ID],
        )
        result = bridge.execute_with_setup(tree=tree, actor_id=actor.id_)
        assert result.status == Status.FAILURE

    def test_failure_when_no_case_manager(self, dl, bridge):
        store, actor = dl
        case = VulnerabilityCase(name="No Manager Case")
        participant = FinderParticipant(
            attributed_to=actor.id_,
            context=case.id_,
        )
        case.case_participants = [participant.id_]
        case.actor_participant_index = {actor.id_: participant.id_}
        store.create(case)
        store.create(participant)
        result_out: dict = {}
        tree = add_note_to_case_trigger_bt(
            case_id=case.id_,
            note_name=NOTE_NAME,
            note_content=NOTE_CONTENT,
            result_out=result_out,
            activity_builder=lambda _: [ACTIVITY_ID],
        )
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=actor.id_,
            trigger_activity_factory=_FakeTriggerFactory(),
        )
        assert result.status == Status.FAILURE
        # The Sequence runs CreateNoteNode and AttachNoteFromResultNode before
        # SenderSideBT fails — so the note IS attached locally (partial write).
        refreshed = store.read(case.id_)
        assert refreshed is not None
        assert NOTE_ID in refreshed.notes

    def test_accepts_in_reply_to(self, dl, bridge):
        store, actor = dl
        case = _make_case_with_case_manager(store, actor.id_)
        parent_note_id = "https://example.org/notes/parent-01"
        result_out: dict = {}

        tree = add_note_to_case_trigger_bt(
            case_id=case.id_,
            note_name=NOTE_NAME,
            note_content=NOTE_CONTENT,
            result_out=result_out,
            activity_builder=lambda _: [ACTIVITY_ID],
            in_reply_to=parent_note_id,
        )
        result = bridge.execute_with_setup(
            tree=tree,
            actor_id=actor.id_,
            trigger_activity_factory=_FakeTriggerFactory(),
        )
        assert result.status == Status.SUCCESS
        assert result_out.get("note_id") == NOTE_ID
        # Verify in_reply_to was forwarded to the factory and recorded in note_dict
        assert result_out["note_dict"]["inReplyTo"] == parent_note_id
