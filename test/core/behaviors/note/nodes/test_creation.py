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

"""Tests for note.nodes.creation."""

import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.note.nodes.creation import (
    AttachNoteFromResultNode,
    CreateNoteNode,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

ACTOR_ID = "https://example.org/actors/finder"
CASE_ID = "https://example.org/cases/case-01"
NOTE_ID = "https://example.org/notes/note-01"


class _FakeTriggerFactory:
    def create_note(
        self,
        *,
        name: str,
        content: str,
        context_id: str,
        attributed_to: str,
        in_reply_to: str | None,
    ) -> tuple[str, dict[str, str]]:
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
    return SqliteDataLayer("sqlite:///:memory:")


@pytest.fixture
def bridge(dl):
    return BTBridge(datalayer=dl)


class TestCreateNoteNode:
    def test_writes_note_result_payload(self, bridge):
        result_out: dict[str, object] = {}
        node = CreateNoteNode(
            note_name="Test note",
            note_content="content",
            case_id=CASE_ID,
            result_out=result_out,
        )
        result = bridge.execute_with_setup(
            tree=node,
            actor_id=ACTOR_ID,
            trigger_activity_factory=_FakeTriggerFactory(),
        )
        assert result.status == Status.SUCCESS
        assert result_out["note_id"] == NOTE_ID
        assert isinstance(result_out["note_dict"], dict)

    def test_fails_without_trigger_factory(self, bridge):
        result_out: dict[str, object] = {}
        node = CreateNoteNode(
            note_name="Test note",
            note_content="content",
            case_id=CASE_ID,
            result_out=result_out,
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE


class TestAttachNoteFromResultNode:
    def test_attaches_note_id_from_result_out(self, bridge, dl):
        dl.create(as_VulnerabilityCase(id_=CASE_ID, name="Test Case"))
        result_out = {"note_id": NOTE_ID}
        node = AttachNoteFromResultNode(case_id=CASE_ID, result_out=result_out)
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS
        refreshed = dl.read(CASE_ID)
        assert refreshed is not None
        assert NOTE_ID in refreshed.notes

    def test_fails_without_note_id(self, bridge):
        node = AttachNoteFromResultNode(case_id=CASE_ID, result_out={})
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE
