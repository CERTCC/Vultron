#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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
"""Tests for note-related use-case classes."""

from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
from vultron.core.use_cases.note import (
    AddNoteToCaseReceivedUseCase,
    CreateNoteReceivedUseCase,
    RemoveNoteFromCaseReceivedUseCase,
)
from vultron.wire.as2.extractor import extract_intent
from vultron.wire.as2.vocab.activities.case import AddNoteToCaseActivity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Create,
    as_Remove,
)
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase


def _make_payload(activity, **extra_fields):
    event = extract_intent(activity)
    if extra_fields:
        return event.model_copy(update=extra_fields)
    return event


class TestNoteUseCases:
    """Tests for note management handlers."""

    def test_create_note_stores_note(self, monkeypatch):
        """create_note persists the Note to the DataLayer."""
        dl = TinyDbDataLayer(db_path=None)

        note = as_Note(
            id="https://example.org/notes/note1",
            content="Test note content",
        )
        activity = as_Create(
            actor="https://example.org/users/finder",
            object=note,
        )

        event = _make_payload(activity)

        CreateNoteReceivedUseCase(dl, event).execute()

        stored = dl.get(note.as_type.value, note.as_id)
        assert stored is not None

    def test_create_note_idempotent(self, monkeypatch):
        """create_note skips storing a duplicate Note."""
        dl = TinyDbDataLayer(db_path=None)

        note = as_Note(
            id="https://example.org/notes/note2",
            content="Duplicate note",
        )
        activity = as_Create(
            actor="https://example.org/users/finder",
            object=note,
        )
        event = _make_payload(activity)

        dl.create(note)
        CreateNoteReceivedUseCase(dl, event).execute()

        stored = dl.get(note.as_type.value, note.as_id)
        assert stored is not None

    def test_add_note_to_case_appends_note(self, monkeypatch):
        """add_note_to_case appends note ID to case.notes and persists."""
        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.wire.as2.rehydration.get_datalayer",
            lambda **_: dl,
        )

        case = VulnerabilityCase(
            id="https://example.org/cases/case_n1",
            name="Note Case",
        )
        note = as_Note(
            id="https://example.org/notes/note3",
            content="A note",
        )
        dl.create(case)
        dl.create(note)

        activity = AddNoteToCaseActivity(
            actor="https://example.org/users/finder",
            object=note,
            target=case,
        )
        event = _make_payload(activity)

        AddNoteToCaseReceivedUseCase(dl, event).execute()

        case = dl.read(case.as_id)
        assert note.as_id in case.notes

    def test_add_note_to_case_idempotent(self, monkeypatch):
        """add_note_to_case skips adding a note already in the case."""
        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.wire.as2.rehydration.get_datalayer",
            lambda **_: dl,
        )

        note = as_Note(
            id="https://example.org/notes/note4",
            content="A note",
        )
        case = VulnerabilityCase(
            id="https://example.org/cases/case_n2",
            name="Note Case Idempotent",
            notes=[note.as_id],
        )
        dl.create(case)
        dl.create(note)

        activity = AddNoteToCaseActivity(
            actor="https://example.org/users/finder",
            object=note,
            target=case,
        )
        event = _make_payload(activity)

        AddNoteToCaseReceivedUseCase(dl, event).execute()

        assert case.notes.count(note.as_id) == 1

    def test_remove_note_from_case_removes_note(self, monkeypatch):
        """remove_note_from_case removes note ID from case.notes and persists."""
        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.wire.as2.rehydration.get_datalayer",
            lambda **_: dl,
        )

        note = as_Note(
            id="https://example.org/notes/note5",
            content="A note",
        )
        case = VulnerabilityCase(
            id="https://example.org/cases/case_n3",
            name="Remove Note Case",
            notes=[note.as_id],
        )
        dl.create(case)
        dl.create(note)

        activity = as_Remove(
            actor="https://example.org/users/finder",
            object=note,
            target=case,
        )
        event = _make_payload(activity)

        RemoveNoteFromCaseReceivedUseCase(dl, event).execute()

        case = dl.read(case.as_id)
        assert note.as_id not in case.notes

    def test_remove_note_from_case_idempotent(self, monkeypatch):
        """remove_note_from_case is idempotent when note not in case."""
        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.wire.as2.rehydration.get_datalayer",
            lambda **_: dl,
        )

        note = as_Note(
            id="https://example.org/notes/note6",
            content="A note",
        )
        case = VulnerabilityCase(
            id="https://example.org/cases/case_n4",
            name="Remove Note Idempotent",
        )
        dl.create(case)
        dl.create(note)

        activity = as_Remove(
            actor="https://example.org/users/finder",
            object=note,
            target=case,
        )
        event = _make_payload(activity)

        result = RemoveNoteFromCaseReceivedUseCase(dl, event).execute()
        assert result is None
