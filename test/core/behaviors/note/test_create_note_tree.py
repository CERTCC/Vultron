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

"""Tests for create_note_tree factory."""

import pytest
from py_trees.common import Status

from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.intake import (
    IntakeReceivedActivityNode,
)
from vultron.core.behaviors.case.nodes.role_gates import CaseManagerGate
from vultron.core.behaviors.note.create_note_tree import create_note_tree
from vultron.core.behaviors.note.nodes import (
    AttachNoteToCaseNode,
    SaveNoteNode,
)
from vultron.core.models.note import VultronNote
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.semantic_registry import extract_event
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Create,
)
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

ACTOR_ID = "https://example.org/actors/finder"
CASE_ID = "https://example.org/cases/case-01"
NOTE_ID = "https://example.org/notes/note-01"


@pytest.fixture
def dl():
    return SqliteDataLayer(
        "sqlite:///:memory:",
        actor_id=ACTOR_ID,
    )


@pytest.fixture
def bridge(dl):
    return BTBridge(datalayer=dl)


@pytest.fixture
def note():
    return VultronNote(
        id_=NOTE_ID,
        content="Test note content",
    )


@pytest.fixture
def note_with_case():
    return VultronNote(
        id_=NOTE_ID,
        content="Test note content",
        context=CASE_ID,
    )


def _create_note_event(note: VultronNote):
    """The extracted ``Create(Note)`` event that carries *note*'s activity."""
    return extract_event(
        as_Create(
            actor=ACTOR_ID,
            object_=as_Note(
                id_=note.id_, content=note.content, context=note.context
            ),
        )
    )


def _archived(dl, event) -> bool:
    return (
        dl.read(ReceivedActivityRecord.build_id(event.activity_id)) is not None
    )


@pytest.fixture
def case(dl):
    # RSH-08-003 (#3814): AttachNoteToCaseNode is CASE_MANAGER-gated, so the
    # executing actor (ACTOR_ID, the store owner) must hold the role for the
    # attach to run; attributed_to seeds the CLP-08 genesis anchor.
    obj = as_VulnerabilityCase(
        id_=CASE_ID, name="Test Case", attributed_to=ACTOR_ID
    )
    seed_case_manager_participant(dl, obj, ACTOR_ID)
    dl.create(obj)
    return obj


# ---------------------------------------------------------------------------
# create_note_tree tests
# ---------------------------------------------------------------------------


class TestCreateNoteTree:
    @pytest.mark.spec("CM-02-007")
    def test_saves_note_and_attaches_to_case(
        self, bridge, dl, note_with_case, case
    ):
        event = _create_note_event(note_with_case)
        tree = create_note_tree(note_obj=note_with_case, case_id=CASE_ID)
        result = bridge.execute_with_setup(
            tree=tree, actor_id=ACTOR_ID, activity=event
        )
        assert result.status == Status.SUCCESS

        stored_note = dl.read(NOTE_ID)
        assert stored_note is not None
        assert _archived(dl, event)

        refreshed_case = dl.read(CASE_ID)
        assert refreshed_case is not None
        assert NOTE_ID in refreshed_case.notes

    def test_saves_note_without_case_attachment(self, bridge, dl, note):
        """When case_id is None, only the note is saved."""
        event = _create_note_event(note)
        tree = create_note_tree(note_obj=note, case_id=None)
        result = bridge.execute_with_setup(
            tree=tree, actor_id=ACTOR_ID, activity=event
        )
        assert result.status == Status.SUCCESS

        stored_note = dl.read(NOTE_ID)
        assert stored_note is not None

    @pytest.mark.spec("CM-13-007")
    def test_idempotent_replay(self, bridge, dl, note_with_case, case):
        """Running the same tree twice produces the same outcome."""
        event = _create_note_event(note_with_case)
        for _ in range(2):
            tree = create_note_tree(note_obj=note_with_case, case_id=CASE_ID)
            result = bridge.execute_with_setup(
                tree=tree, actor_id=ACTOR_ID, activity=event
            )
            assert result.status == Status.SUCCESS

        refreshed = dl.read(CASE_ID)
        assert refreshed is not None
        assert refreshed.notes.count(NOTE_ID) == 1

    def test_tree_name_is_create_note_bt(self, note, dl):
        tree = create_note_tree(note_obj=note, case_id=None)
        assert tree.name == "CreateNoteBT"

    def test_tree_runs_intake_then_save_then_attach(self, note, dl):
        # RSH-08-003 (#3814): the attach is now wrapped in the factory's
        # CASE_MANAGER gate as the last child; the Note object is still saved
        # ungated.
        tree = create_note_tree(note_obj=note, case_id=CASE_ID)
        assert len(tree.children) == 3
        assert isinstance(tree.children[0], IntakeReceivedActivityNode)
        assert isinstance(tree.children[1], SaveNoteNode)
        gate = tree.children[2]
        assert isinstance(gate, CaseManagerGate)
        assert isinstance(gate.gated_branch, AttachNoteToCaseNode)

    @pytest.mark.spec("CLP-10-018")
    def test_unmanaged_case_archives_the_activity_and_attaches_nothing(
        self, bridge, dl, note_with_case
    ):
        """The case is not held, so the actor is not its CASE_MANAGER: the
        attach is gated out (RSH-08-003, #3814) and the tree still succeeds,
        archiving the Create and writing no attachment (CLP-10-018)."""
        event = _create_note_event(note_with_case)
        tree = create_note_tree(note_obj=note_with_case, case_id=CASE_ID)
        result = bridge.execute_with_setup(
            tree=tree, actor_id=ACTOR_ID, activity=event
        )
        assert result.status == Status.SUCCESS
        assert _archived(dl, event)
        assert dl.read(CASE_ID) is None
