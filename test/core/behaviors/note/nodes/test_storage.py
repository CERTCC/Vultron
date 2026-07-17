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

"""Tests for note.nodes.storage."""

import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.note.nodes.storage import (
    AttachNoteToCaseNode,
    SaveNoteNode,
)
from vultron.core.models.note import VultronNote
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

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
    return VultronNote(id_=NOTE_ID, content="Test note content")


class TestSaveNoteNode:
    def test_saves_note_to_datalayer(self, bridge, dl, note):
        tree = SaveNoteNode(note_obj=note)
        result = bridge.execute_with_setup(tree=tree, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS
        assert dl.read(NOTE_ID) is not None

    def test_idempotent_on_duplicate(self, bridge, dl, note):
        dl.create(note)
        tree = SaveNoteNode(note_obj=note)
        result = bridge.execute_with_setup(tree=tree, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS


class TestAttachNoteToCaseNode:
    def test_attaches_note_to_case(self, bridge, dl, note):
        case = as_VulnerabilityCase(id_=CASE_ID, name="Test Case")
        dl.create(case)
        dl.save(note)
        tree = AttachNoteToCaseNode(note_id=NOTE_ID, case_id=CASE_ID)
        result = bridge.execute_with_setup(tree=tree, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS
        refreshed = dl.read(CASE_ID)
        assert refreshed is not None
        assert NOTE_ID in refreshed.notes

    def test_idempotent_when_note_already_attached(self, bridge, dl, note):
        case = as_VulnerabilityCase(
            id_=CASE_ID, name="Test Case", notes=[NOTE_ID]
        )
        dl.create(case)
        dl.save(note)
        tree = AttachNoteToCaseNode(note_id=NOTE_ID, case_id=CASE_ID)
        result = bridge.execute_with_setup(tree=tree, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS
        refreshed = dl.read(CASE_ID)
        assert refreshed is not None
        assert refreshed.notes.count(NOTE_ID) == 1

    def test_succeeds_when_case_id_is_none(self, bridge, dl, note):
        dl.save(note)
        tree = AttachNoteToCaseNode(note_id=NOTE_ID, case_id=None)
        result = bridge.execute_with_setup(tree=tree, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS

    def test_fails_when_case_not_in_datalayer(self, bridge, dl, note):
        dl.save(note)
        tree = AttachNoteToCaseNode(
            note_id=NOTE_ID,
            case_id="https://example.org/cases/does-not-exist",
        )
        result = bridge.execute_with_setup(tree=tree, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE
