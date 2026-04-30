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

from typing import Any, cast

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.use_cases.received.note import (
    AddNoteToCaseReceivedUseCase,
    CreateNoteReceivedUseCase,
    RemoveNoteFromCaseReceivedUseCase,
)
from vultron.wire.as2.factories import add_note_to_case_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Create,
    as_Remove,
)
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase


class TestNoteUseCases:
    """Tests for note management handlers."""

    def test_create_note_stores_note(self, monkeypatch, make_payload):
        """create_note persists the Note to the DataLayer."""
        dl = SqliteDataLayer("sqlite:///:memory:")

        note = as_Note(
            id_="https://example.org/notes/note1",
            content="Test note content",
        )
        activity = as_Create(
            actor="https://example.org/users/finder",
            object_=note,
        )

        event = make_payload(activity)

        CreateNoteReceivedUseCase(dl, event).execute()

        stored = dl.get(note.type_.value, note.id_)
        assert stored is not None

    def test_create_note_idempotent(self, monkeypatch, make_payload):
        """create_note skips storing a duplicate Note."""
        dl = SqliteDataLayer("sqlite:///:memory:")

        note = as_Note(
            id_="https://example.org/notes/note2",
            content="Duplicate note",
        )
        activity = as_Create(
            actor="https://example.org/users/finder",
            object_=note,
        )
        event = make_payload(activity)

        dl.create(note)
        CreateNoteReceivedUseCase(dl, event).execute()

        stored = dl.get(note.type_.value, note.id_)
        assert stored is not None

    def test_create_note_attaches_to_case_when_context_set(
        self, monkeypatch, make_payload
    ):
        """create_note attaches the Note to the case when note.context is set."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_cn1",
            name="Context Case",
        )
        dl.create(case)

        note = as_Note(
            id_="https://example.org/notes/note_ctx1",
            content="Note with context",
            context=case.id_,
        )
        activity = as_Create(
            actor="https://example.org/users/finder",
            object_=note,
        )
        event = make_payload(activity)

        CreateNoteReceivedUseCase(dl, event).execute()

        refreshed = dl.read(case.id_)
        assert refreshed is not None
        refreshed = cast(VulnerabilityCase, refreshed)
        assert note.id_ in refreshed.notes

    def test_create_note_attach_to_case_idempotent(
        self, monkeypatch, make_payload
    ):
        """create_note is idempotent when note already attached to case."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        note_id = "https://example.org/notes/note_ctx2"
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_cn2",
            name="Idempotent Case",
            notes=[note_id],
        )
        dl.create(case)

        note = as_Note(
            id_=note_id,
            content="Note already in case",
            context=case.id_,
        )
        activity = as_Create(
            actor="https://example.org/users/finder",
            object_=note,
        )
        event = make_payload(activity)

        CreateNoteReceivedUseCase(dl, event).execute()

        refreshed = dl.read(case.id_)
        assert refreshed is not None
        refreshed = cast(VulnerabilityCase, refreshed)
        assert refreshed.notes.count(note_id) == 1

    def test_add_note_to_case_appends_note(self, monkeypatch, make_payload):
        """add_note_to_case appends note ID to case.notes and persists."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_n1",
            name="Note Case",
        )
        note = as_Note(
            id_="https://example.org/notes/note3",
            content="A note",
        )
        dl.create(case)
        dl.create(note)

        activity = add_note_to_case_activity(
            note, target=case, actor="https://example.org/users/finder"
        )
        event = make_payload(activity)

        AddNoteToCaseReceivedUseCase(dl, event).execute()

        case = dl.read(case.id_)
        assert case is not None
        case = cast(VulnerabilityCase, case)
        assert note.id_ in case.notes

    def test_add_note_to_case_idempotent(self, monkeypatch, make_payload):
        """add_note_to_case skips adding a note already in the case."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        note = as_Note(
            id_="https://example.org/notes/note4",
            content="A note",
        )
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_n2",
            name="Note Case Idempotent",
            notes=[note.id_],
        )
        dl.create(case)
        dl.create(note)

        activity = add_note_to_case_activity(
            note, target=case, actor="https://example.org/users/finder"
        )
        event = make_payload(activity)

        AddNoteToCaseReceivedUseCase(dl, event).execute()

        assert case.notes.count(note.id_) == 1

    def test_remove_note_from_case_removes_note(
        self, monkeypatch, make_payload
    ):
        """remove_note_from_case removes note ID from case.notes and persists."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        note = as_Note(
            id_="https://example.org/notes/note5",
            content="A note",
        )
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_n3",
            name="Remove Note Case",
            notes=[note.id_],
        )
        dl.create(case)
        dl.create(note)

        activity = as_Remove(
            actor="https://example.org/users/finder",
            object_=note,
            target=case,
        )
        event = make_payload(activity)

        RemoveNoteFromCaseReceivedUseCase(dl, event).execute()

        case = dl.read(case.id_)
        assert case is not None
        case = cast(VulnerabilityCase, case)
        assert note.id_ not in case.notes

    def test_remove_note_from_case_idempotent(self, monkeypatch, make_payload):
        """remove_note_from_case is idempotent when note not in case."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        note = as_Note(
            id_="https://example.org/notes/note6",
            content="A note",
        )
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_n4",
            name="Remove Note Idempotent",
        )
        dl.create(case)
        dl.create(note)

        activity = as_Remove(
            actor="https://example.org/users/finder",
            object_=note,
            target=case,
        )
        event = make_payload(activity)

        result = RemoveNoteFromCaseReceivedUseCase(dl, event).execute()
        assert result is None

    # ------------------------------------------------------------------
    # Broadcast tests (CM-06-005)
    # ------------------------------------------------------------------

    def test_add_note_broadcasts_to_participants(self, make_payload):
        """add_note_to_case broadcasts AddNoteToCase to all participants.

        After a note is added to a case, the CaseActor should enqueue an
        AddNoteToCaseActivity for delivery to all participants that are not
        the note author (CM-06-005).
        """
        dl = SqliteDataLayer("sqlite:///:memory:")
        author_id = "https://example.org/users/vendor"
        participant_id = "https://example.org/users/finder"
        case_id = "https://example.org/cases/case_nb1"

        case_actor = VultronCaseActor(
            id_=f"{case_id}/actor",
            name=f"CaseActor for {case_id}",
            attributed_to=author_id,
            context=case_id,
        )
        dl.create(case_actor)

        case = VulnerabilityCase(
            id_=case_id,
            name="Broadcast Note Case",
            attributed_to=author_id,
        )
        case.actor_participant_index[author_id] = (
            "https://example.org/participants/p-nb1-vendor"
        )
        case.actor_participant_index[participant_id] = (
            "https://example.org/participants/p-nb1-finder"
        )
        dl.create(case)

        note = as_Note(
            id_="https://example.org/notes/note_bc1",
            content="Broadcast note",
            context=case_id,
        )
        dl.create(note)

        activity = add_note_to_case_activity(
            note, target=case, actor=author_id
        )
        event = make_payload(activity)

        AddNoteToCaseReceivedUseCase(dl, event).execute()

        # CaseActor outbox should contain the broadcast activity.
        refreshed_actor = dl.read(case_actor.id_)
        assert refreshed_actor is not None
        refreshed_actor = cast(VultronCaseActor, refreshed_actor)
        assert len(refreshed_actor.outbox.items) == 1

        broadcast_id = refreshed_actor.outbox.items[0]
        broadcast = dl.read(broadcast_id)
        assert broadcast is not None
        broadcast = cast(Any, broadcast)
        assert broadcast.actor == case_actor.id_
        assert broadcast.to is not None
        assert participant_id in broadcast.to

        # Verify the broadcast is enqueued for delivery by outbox_handler.
        scoped_dl = SqliteDataLayer(
            "sqlite:///:memory:", actor_id=case_actor.id_
        )
        scoped_dl._engine.dispose()
        scoped_dl._engine = dl._engine
        scoped_dl._owns_engine = False
        queued_ids = scoped_dl.outbox_list()
        assert broadcast_id in queued_ids

    def test_add_note_broadcast_excludes_author(self, make_payload):
        """The note author is excluded from broadcast recipients (CM-06-005)."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        author_id = "https://example.org/users/vendor"
        participant_id = "https://example.org/users/finder"
        case_id = "https://example.org/cases/case_nb2"

        case_actor = VultronCaseActor(
            id_=f"{case_id}/actor",
            name=f"CaseActor for {case_id}",
            attributed_to=author_id,
            context=case_id,
        )
        dl.create(case_actor)

        case = VulnerabilityCase(
            id_=case_id,
            name="Exclude Author Case",
            attributed_to=author_id,
        )
        case.actor_participant_index[author_id] = (
            "https://example.org/participants/p-nb2-vendor"
        )
        case.actor_participant_index[participant_id] = (
            "https://example.org/participants/p-nb2-finder"
        )
        dl.create(case)

        note = as_Note(
            id_="https://example.org/notes/note_bc2",
            content="Author excluded note",
            context=case_id,
        )
        dl.create(note)

        activity = add_note_to_case_activity(
            note, target=case, actor=author_id
        )
        event = make_payload(activity)

        AddNoteToCaseReceivedUseCase(dl, event).execute()

        refreshed_actor = dl.read(case_actor.id_)
        assert refreshed_actor is not None
        refreshed_actor = cast(VultronCaseActor, refreshed_actor)
        assert len(refreshed_actor.outbox.items) == 1

        broadcast_id = refreshed_actor.outbox.items[0]
        broadcast = dl.read(broadcast_id)
        assert broadcast is not None
        broadcast = cast(Any, broadcast)
        assert broadcast.to is not None
        assert author_id not in broadcast.to
        assert participant_id in broadcast.to

    def test_add_note_no_broadcast_when_no_case_actor(self, make_payload):
        """Broadcast is skipped gracefully when no CaseActor exists (CM-06-005)."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        author_id = "https://example.org/users/vendor"
        case_id = "https://example.org/cases/case_nb3"

        case = VulnerabilityCase(
            id_=case_id,
            name="No CaseActor Case",
            attributed_to=author_id,
        )
        dl.create(case)

        note = as_Note(
            id_="https://example.org/notes/note_bc3",
            content="No broadcast note",
            context=case_id,
        )
        dl.create(note)

        activity = add_note_to_case_activity(
            note, target=case, actor=author_id
        )
        event = make_payload(activity)

        # Should not raise; broadcast is silently skipped.
        AddNoteToCaseReceivedUseCase(dl, event).execute()

        # Note should still be added to the case.
        refreshed = dl.read(case_id)
        assert refreshed is not None
        refreshed = cast(VulnerabilityCase, refreshed)
        assert note.id_ in refreshed.notes
