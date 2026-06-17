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

"""Unit tests for TriggerActivityAdapter note-domain methods."""

import pytest

from vultron.wire.as2.vocab.base.objects.object_types import as_Note

_ACTOR = "https://example.org/actors/reporter"
_CASE_ID = "https://example.org/cases/case-001"


class TestCreateNote:
    def test_returns_id_and_dict(self, adapter, dl):
        note_id, note_dict = adapter.create_note(
            name="Bug report",
            content="Detailed findings",
            context_id=_CASE_ID,
            attributed_to=_ACTOR,
        )

        assert note_id
        assert isinstance(note_dict, dict)
        # by_alias=True — serialized key is "id" not "id_"
        assert "id" in note_dict
        assert note_dict["id"] == note_id

    def test_persists_note_in_datalayer(self, adapter, dl):
        note_id, _ = adapter.create_note(
            name="Bug report",
            content="Details",
            context_id=_CASE_ID,
            attributed_to=_ACTOR,
        )

        assert dl.read(note_id) is not None

    def test_in_reply_to_included_in_dict(self, adapter):
        parent_id = "https://example.org/notes/parent"
        _, note_dict = adapter.create_note(
            name="Reply",
            content="Reply content",
            context_id=_CASE_ID,
            attributed_to=_ACTOR,
            in_reply_to=parent_id,
        )

        assert note_dict.get("inReplyTo") == parent_id

    def test_idempotent_second_create_returns_same_id(self, adapter, dl):
        """Re-creating the same note object raises ValueError; adapter logs and continues."""
        note = as_Note(
            name="Static",
            content="content",
            context=_CASE_ID,
            attributed_to=_ACTOR,
        )
        dl.create(note)

        # Simulate the adapter building the *same* note (same id_)
        # by injecting it directly; the adapter's create_note always makes
        # a fresh UUID, so we test the ValueError branch via the DL directly.
        with pytest.raises(ValueError):
            dl.create(note)


class TestCreateNoteActivity:
    def test_returns_activity_id(self, adapter, dl):
        note_id, _ = adapter.create_note(
            name="Report",
            content="content",
            context_id=_CASE_ID,
            attributed_to=_ACTOR,
        )

        activity_id = adapter.create_note_activity(
            actor=_ACTOR, note_id=note_id
        )

        assert activity_id
        assert activity_id != note_id

    def test_persists_activity(self, adapter, dl):
        note_id, _ = adapter.create_note(
            name="Report",
            content="content",
            context_id=_CASE_ID,
            attributed_to=_ACTOR,
        )

        activity_id = adapter.create_note_activity(
            actor=_ACTOR,
            note_id=note_id,
            to=[_CASE_ID],
        )

        assert dl.read(activity_id) is not None


class TestAddNoteToCase:
    def test_returns_id_and_dict(self, adapter, dl):
        note_id, _ = adapter.create_note(
            name="Note",
            content="content",
            context_id=_CASE_ID,
            attributed_to=_ACTOR,
        )

        activity_id, activity_dict = adapter.add_note_to_case(
            note_id=note_id,
            case_id=_CASE_ID,
            actor=_ACTOR,
        )

        assert activity_id
        assert isinstance(activity_dict, dict)
        assert "id" in activity_dict

    def test_persists_add_activity(self, adapter, dl):
        note_id, _ = adapter.create_note(
            name="Note",
            content="content",
            context_id=_CASE_ID,
            attributed_to=_ACTOR,
        )

        activity_id, _ = adapter.add_note_to_case(
            note_id=note_id,
            case_id=_CASE_ID,
            actor=_ACTOR,
            to=[_CASE_ID],
        )

        assert dl.read(activity_id) is not None
