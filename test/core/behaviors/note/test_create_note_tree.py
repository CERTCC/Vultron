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

"""Tests for note BT nodes and create_note_tree factory."""

import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.note.create_note_tree import create_note_tree
from vultron.core.behaviors.note.nodes import (
    AttachNoteToCaseNode,
    SaveNoteNode,
)
from vultron.core.models.note import VultronNote
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase

ACTOR_ID = "https://example.org/actors/finder"
CASE_ID = "https://example.org/cases/case-01"
NOTE_ID = "https://example.org/notes/note-01"


@pytest.fixture
def dl():
    return SqliteDataLayer("sqlite:///:memory:")


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


@pytest.fixture
def case(dl):
    obj = VulnerabilityCase(id_=CASE_ID, name="Test Case")
    dl.create(obj)
    return obj


# ---------------------------------------------------------------------------
# SaveNoteNode tests
# ---------------------------------------------------------------------------


class TestSaveNoteNode:
    def test_saves_note_to_datalayer(self, bridge, dl, note):
        tree = SaveNoteNode(note_obj=note)
        result = bridge.execute_with_setup(tree=tree, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS
        stored = dl.read(NOTE_ID)
        assert stored is not None

    def test_idempotent_on_duplicate(self, bridge, dl, note):
        """SaveNoteNode succeeds even when note already in DataLayer."""
        dl.create(note)
        tree = SaveNoteNode(note_obj=note)
        result = bridge.execute_with_setup(tree=tree, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS


# ---------------------------------------------------------------------------
# AttachNoteToCaseNode tests
# ---------------------------------------------------------------------------


class TestAttachNoteToCaseNode:
    def test_attaches_note_to_case(self, bridge, dl, note, case):
        dl.save(note)
        tree = AttachNoteToCaseNode(note_id=NOTE_ID, case_id=CASE_ID)
        result = bridge.execute_with_setup(tree=tree, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS
        refreshed = dl.read(CASE_ID)
        assert refreshed is not None
        assert NOTE_ID in refreshed.notes

    def test_idempotent_when_note_already_attached(self, bridge, dl, note):
        obj = VulnerabilityCase(id_=CASE_ID, name="Test Case", notes=[NOTE_ID])
        dl.create(obj)
        dl.save(note)

        tree = AttachNoteToCaseNode(note_id=NOTE_ID, case_id=CASE_ID)
        result = bridge.execute_with_setup(tree=tree, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS

        refreshed = dl.read(CASE_ID)
        assert refreshed is not None
        assert refreshed.notes.count(NOTE_ID) == 1

    def test_succeeds_when_case_id_is_none(self, bridge, dl, note):
        """AttachNoteToCaseNode succeeds immediately when case_id is None."""
        dl.save(note)
        tree = AttachNoteToCaseNode(note_id=NOTE_ID, case_id=None)
        result = bridge.execute_with_setup(tree=tree, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS

    def test_fails_when_case_not_in_datalayer(self, bridge, dl, note):
        """AttachNoteToCaseNode returns FAILURE when case is missing."""
        dl.save(note)
        missing_case_id = "https://example.org/cases/does-not-exist"
        tree = AttachNoteToCaseNode(note_id=NOTE_ID, case_id=missing_case_id)
        result = bridge.execute_with_setup(tree=tree, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE


# ---------------------------------------------------------------------------
# create_note_tree tests
# ---------------------------------------------------------------------------


class TestCreateNoteTree:
    def test_saves_note_and_attaches_to_case(
        self, bridge, dl, note_with_case, case
    ):
        tree = create_note_tree(note_obj=note_with_case, case_id=CASE_ID)
        result = bridge.execute_with_setup(tree=tree, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS

        stored_note = dl.read(NOTE_ID)
        assert stored_note is not None

        refreshed_case = dl.read(CASE_ID)
        assert refreshed_case is not None
        assert NOTE_ID in refreshed_case.notes

    def test_saves_note_without_case_attachment(self, bridge, dl, note):
        """When case_id is None, only the note is saved."""
        tree = create_note_tree(note_obj=note, case_id=None)
        result = bridge.execute_with_setup(tree=tree, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS

        stored_note = dl.read(NOTE_ID)
        assert stored_note is not None

    def test_idempotent_replay(self, bridge, dl, note_with_case, case):
        """Running the same tree twice produces the same outcome."""
        for _ in range(2):
            tree = create_note_tree(note_obj=note_with_case, case_id=CASE_ID)
            result = bridge.execute_with_setup(tree=tree, actor_id=ACTOR_ID)
            assert result.status == Status.SUCCESS

        refreshed = dl.read(CASE_ID)
        assert refreshed is not None
        assert refreshed.notes.count(NOTE_ID) == 1

    def test_tree_name_is_create_note_bt(self, note, dl):
        tree = create_note_tree(note_obj=note, case_id=None)
        assert tree.name == "CreateNoteBT"

    def test_tree_has_two_children(self, note, dl):
        tree = create_note_tree(note_obj=note, case_id=CASE_ID)
        assert len(tree.children) == 2
        assert isinstance(tree.children[0], SaveNoteNode)
        assert isinstance(tree.children[1], AttachNoteToCaseNode)
