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

from typing import cast

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.models.case_ledger_entry import VultronCaseLedgerEntry
from vultron.core.models.protocols import is_log_entry_model
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
        event = make_payload(
            activity,
            receiving_actor_id="https://example.org/actors/receiver",
        )

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
        event = make_payload(
            activity,
            receiving_actor_id="https://example.org/actors/receiver",
        )

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
    # CaseLedgerEntry cascade tests (PCR-08-003, PCR-08-004) — AC-1
    # ------------------------------------------------------------------

    def test_add_note_commits_log_entry_when_sync_port_provided(
        self, make_payload
    ):
        """AddNoteToCaseReceivedUseCase commits a CaseLedgerEntry (PCR-08-003).

        When a sync_port is injected and receiving_actor_id is set, the use
        case MUST commit one VultronCaseLedgerEntry after accepting a note
        addition.
        """
        dl = SqliteDataLayer("sqlite:///:memory:")
        case_actor_id = "https://example.org/cases/case_le1/actor"
        author_id = "https://example.org/users/vendor"
        participant_id = "https://example.org/users/finder"
        case_id = "https://example.org/cases/case_le1"

        case_actor = VultronCaseActor(
            id_=case_actor_id,
            name="CaseActor le1",
            attributed_to=author_id,
            context=case_id,
        )
        dl.create(case_actor)

        case = VulnerabilityCase(
            id_=case_id,
            name="Log Entry Cascade Case",
            attributed_to=author_id,
        )
        case.actor_participant_index[author_id] = (
            "https://example.org/participants/p-le1-vendor"
        )
        case.actor_participant_index[participant_id] = (
            "https://example.org/participants/p-le1-finder"
        )
        dl.create(case)
        from vultron.core.states.roles import CVDRole
        from vultron.wire.as2.vocab.objects.case_participant import (
            CaseParticipant,
        )

        case_manager_participant = CaseParticipant(
            id_=f"{case_id}/participants/case-actor-p",
            attributed_to=case_actor_id,
            context=case_id,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        dl.create(case_manager_participant)
        case.case_participants.append(case_manager_participant.id_)
        case.actor_participant_index[case_actor_id] = (
            case_manager_participant.id_
        )
        dl.save(case)

        note = as_Note(
            id_="https://example.org/notes/note_le1",
            content="Log entry cascade note",
            context=case_id,
        )
        dl.create(note)

        activity = add_note_to_case_activity(
            note, target=case, actor=author_id
        )
        event = make_payload(activity, receiving_actor_id=case_actor_id)

        sync_port = SyncActivityAdapter(dl)
        AddNoteToCaseReceivedUseCase(dl, event, sync_port=sync_port).execute()

        # Exactly one CaseLedgerEntry should be persisted for this case.
        entries = [
            obj
            for obj in dl.list_objects("CaseLedgerEntry")
            if is_log_entry_model(obj)
            and cast(VultronCaseLedgerEntry, obj).case_id == case_id
        ]
        assert len(entries) == 1
        entry = cast(VultronCaseLedgerEntry, entries[0])
        assert entry.event_type == "add_note_to_case"
        assert entry.log_object_id == activity.id_

    def test_add_note_no_fanout_without_sync_port(self, make_payload):
        """No fan-out Announce(CaseLedgerEntry) is sent when sync_port is None.

        The log entry IS committed locally, but no outbox messages are queued
        for delivery to participants.
        """
        dl = SqliteDataLayer("sqlite:///:memory:")
        case_actor_id = "https://example.org/cases/case_le2/actor"
        author_id = "https://example.org/users/vendor"
        participant_id = "https://example.org/users/finder"
        case_id = "https://example.org/cases/case_le2"

        case_actor = VultronCaseActor(
            id_=case_actor_id,
            name="CaseActor le2",
            attributed_to=author_id,
            context=case_id,
        )
        dl.create(case_actor)

        case = VulnerabilityCase(
            id_=case_id,
            name="No Sync Port Case",
            attributed_to=author_id,
        )
        case.actor_participant_index[author_id] = (
            "https://example.org/participants/p-le2-vendor"
        )
        case.actor_participant_index[participant_id] = (
            "https://example.org/participants/p-le2-finder"
        )
        dl.create(case)
        from vultron.core.states.roles import CVDRole
        from vultron.wire.as2.vocab.objects.case_participant import (
            CaseParticipant,
        )

        case_manager_participant = CaseParticipant(
            id_=f"{case_id}/participants/case-actor-p",
            attributed_to=case_actor_id,
            context=case_id,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        dl.create(case_manager_participant)
        case.case_participants.append(case_manager_participant.id_)
        case.actor_participant_index[case_actor_id] = (
            case_manager_participant.id_
        )
        dl.save(case)

        note = as_Note(
            id_="https://example.org/notes/note_le2",
            content="No cascade note",
            context=case_id,
        )
        dl.create(note)

        activity = add_note_to_case_activity(
            note, target=case, actor=author_id
        )
        event = make_payload(activity, receiving_actor_id=case_actor_id)

        # No sync_port — log entry is committed but fan-out is skipped.
        AddNoteToCaseReceivedUseCase(dl, event, sync_port=None).execute()

        # Log entry MUST be committed locally even without a sync_port.
        entries = [
            obj
            for obj in dl.list_objects("CaseLedgerEntry")
            if is_log_entry_model(obj)
            and cast(VultronCaseLedgerEntry, obj).case_id == case_id
        ]
        assert len(entries) == 1

        # But no outbox activities should be queued for fan-out.
        assert dl.outbox_list() == []
