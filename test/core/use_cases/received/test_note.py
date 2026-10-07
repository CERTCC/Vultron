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
from unittest.mock import MagicMock

import pytest

from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
    seed_case_owner_participant,
    seed_case_participant,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.models.case_actor import CaseActor
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.use_cases.received.note import (
    AddNoteToCaseReceivedUseCase,
    CreateNoteReceivedUseCase,
    RemoveNoteFromCaseReceivedUseCase,
)
from vultron.errors import VultronBTInternalError
from vultron.wire.as2.factories import add_note_to_case_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Create,
    as_Remove,
)
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_STORE_ACTOR = "https://example.org/actors/cm-store"
_OWNER = "https://example.org/actors/case-owner"


class TestNoteUseCases:
    """Tests for note management handlers."""

    def test_create_note_stores_note(self, monkeypatch, make_payload):
        """create_note persists the Note to the DataLayer."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )

        note = as_Note(
            id_="https://example.org/notes/note1",
            content="Test note content",
        )
        activity = as_Create(
            actor="https://example.org/users/finder",
            object_=note,
        )

        event = make_payload(activity)

        result = CreateNoteReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()
        assert result.disposition == HandlerDisposition.APPLIED

        stored = dl.get(note.type_.value, note.id_)
        assert stored is not None

    def test_create_note_idempotent(self, monkeypatch, make_payload):
        """create_note skips storing a duplicate Note."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )

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
        CreateNoteReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        stored = dl.get(note.type_.value, note.id_)
        assert stored is not None

    def test_create_note_attaches_to_case_when_context_set(
        self, monkeypatch, make_payload
    ):
        """create_note attaches the Note to the case when note.context is set."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case = as_VulnerabilityCase(
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

        CreateNoteReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        refreshed = dl.read(case.id_)
        assert refreshed is not None
        refreshed = cast(as_VulnerabilityCase, refreshed)
        assert note.id_ in refreshed.notes

    def test_create_note_attach_to_case_idempotent(
        self, monkeypatch, make_payload
    ):
        """create_note is idempotent when note already attached to case."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        note_id = "https://example.org/notes/note_ctx2"
        case = as_VulnerabilityCase(
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

        CreateNoteReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        refreshed = dl.read(case.id_)
        assert refreshed is not None
        refreshed = cast(as_VulnerabilityCase, refreshed)
        assert refreshed.notes.count(note_id) == 1

    def _setup_case_with_case_manager(
        self, dl: "SqliteDataLayer", case_id: str, case_actor_id: str
    ) -> "as_VulnerabilityCase":
        """Create a as_VulnerabilityCase with a CaseActor holding CASE_MANAGER."""
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )

        case_actor = CaseActor(
            id_=case_actor_id,
            name="CaseActor",
            attributed_to="https://example.org/users/vendor",
            context=case_id,
        )
        dl.create(case_actor)

        # attributed_to anchors the per-case ledger genesis, without which
        # the CaseActor's receipt commit fails (CLP-08-005).
        case = as_VulnerabilityCase(
            id_=case_id,
            name="Note Case",
            attributed_to="https://example.org/users/vendor",
        )
        case_mgr_participant = as_CaseParticipant(
            id_=f"{case_id}/participants/case-actor-p",
            attributed_to=case_actor_id,
            context=case_id,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        dl.create(case_mgr_participant)
        case.case_participants.append(case_mgr_participant.id_)
        case.actor_participant_index[case_actor_id] = case_mgr_participant.id_
        dl.create(case)
        return case

    def test_add_note_to_case_appends_note(self, monkeypatch, make_payload):
        """CaseActor appends note ID to case.notes on Add(Note, Case)."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://example.org/cases/case_n1/actor",
        )
        case_actor_id = "https://example.org/cases/case_n1/actor"
        case_id = "https://example.org/cases/case_n1"
        case = self._setup_case_with_case_manager(dl, case_id, case_actor_id)

        note = as_Note(
            id_="https://example.org/notes/note3",
            content="A note",
        )
        dl.create(note)

        activity = add_note_to_case_activity(
            note, target=case, actor="https://example.org/users/finder"
        )
        event = make_payload(
            activity,
            receiving_actor_id=case_actor_id,
        )

        result = AddNoteToCaseReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        refreshed = dl.read(case_id)
        assert refreshed is not None
        refreshed = cast(as_VulnerabilityCase, refreshed)
        assert note.id_ in refreshed.notes
        assert result.disposition == HandlerDisposition.APPLIED

    def test_add_note_to_case_idempotent(self, monkeypatch, make_payload):
        """CaseActor skips adding a note already in the case (idempotent)."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://example.org/cases/case_n2/actor",
        )
        case_actor_id = "https://example.org/cases/case_n2/actor"
        case_id = "https://example.org/cases/case_n2"
        note = as_Note(
            id_="https://example.org/notes/note4",
            content="A note",
        )
        dl.create(note)
        case = self._setup_case_with_case_manager(dl, case_id, case_actor_id)
        # Pre-populate note into case to exercise idempotent path
        case.notes.append(note.id_)
        dl.save(case)

        activity = add_note_to_case_activity(
            note, target=case, actor="https://example.org/users/finder"
        )
        event = make_payload(
            activity,
            receiving_actor_id=case_actor_id,
        )

        AddNoteToCaseReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        refreshed = dl.read(case_id)
        assert refreshed is not None
        refreshed = cast(as_VulnerabilityCase, refreshed)
        assert refreshed.notes.count(note.id_) == 1

    @pytest.mark.spec("HP-01-005")
    def test_add_note_refused_for_non_case_manager(
        self, monkeypatch, make_payload
    ):
        """A non-manager receiving Add(Note, Case) neither attaches nor commits.

        Case replica updates arrive exclusively via Announce(CaseLedgerEntry)
        fan-out (SYNC-02-002). The BT CheckIsCaseManagerNode guard keeps the
        non-manager from attaching or committing, and the handler reports the
        misaddressed note as a refusal (#3752).
        """
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://example.org/actors/non-manager",
        )
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/case_n3_noop",
            name="Noop Case",
        )
        # Somebody else holds CASE_MANAGER, so the gate fails on "this actor
        # is not the manager" rather than on "no role holder" (BT-17-005).
        seed_case_manager_participant(
            dl, case, "https://example.org/actors/case-manager"
        )
        note = as_Note(
            id_="https://example.org/notes/note_noop",
            content="A note",
        )
        dl.create(case)
        dl.create(note)

        activity = add_note_to_case_activity(
            note, target=case, actor="https://example.org/users/finder"
        )
        event = make_payload(
            activity,
            receiving_actor_id="https://example.org/actors/non-manager",
        )

        result = AddNoteToCaseReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        refreshed = dl.read(case.id_)
        assert refreshed is not None
        refreshed = cast(as_VulnerabilityCase, refreshed)
        assert note.id_ not in refreshed.notes
        # HP-01-005: a note addressed to the wrong party is refused, not
        # reported as a processed no-op.
        assert result.disposition == HandlerDisposition.REFUSED
        assert result.reason is not None and "CASE_MANAGER" in result.reason

    def _managed_case_with_note(
        self, dl: SqliteDataLayer, case_id: str, note: as_Note, owner_id: str
    ) -> as_VulnerabilityCase:
        """A case the store's actor manages, owned by *owner_id*, holding *note*."""
        case = as_VulnerabilityCase(
            id_=case_id,
            name="Remove Note Case",
            attributed_to=owner_id,
            notes=[note.id_],
        )
        seed_case_manager_participant(dl, case, _STORE_ACTOR)
        seed_case_owner_participant(dl, case, owner_id)
        dl.create(case)
        dl.create(note)
        return case

    def _remove(self, dl, make_payload, sender, note, case):
        event = make_payload(
            as_Remove(actor=sender, object_=note, target=case.id_)
        )
        return RemoveNoteFromCaseReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

    @pytest.mark.spec("CM-30-001")
    @pytest.mark.spec("CLP-10-005")
    def test_remove_note_from_case_removes_note(
        self, monkeypatch, make_payload
    ):
        """The Case Owner's Remove(Note) detaches the note and commits an entry."""
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_STORE_ACTOR)
        note = as_Note(id_="https://example.org/notes/note5", content="A note")
        case = self._managed_case_with_note(
            dl, "https://example.org/cases/case_n3", note, _OWNER
        )

        result = self._remove(dl, make_payload, _OWNER, note, case)

        case = cast(as_VulnerabilityCase, dl.read(case.id_))
        assert note.id_ not in case.notes
        assert result.disposition == HandlerDisposition.APPLIED
        entries = [
            cast(CaseLedgerEntry, o)
            for o in dl.list_objects("CaseLedgerEntry")
            if isinstance(o, CaseLedgerEntry) and o.case_id == case.id_
        ]
        assert [e.event_type for e in entries] == ["remove_note_from_case"]

    @pytest.mark.spec("CM-30-001")
    def test_remove_note_by_its_active_author_is_applied(self, make_payload):
        """The note's author, an active participant, may remove it."""
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_STORE_ACTOR)
        author = "https://example.org/actors/note-author"
        note = as_Note(
            id_="https://example.org/notes/note_author",
            content="A note",
            attributed_to=author,
        )
        case = self._managed_case_with_note(
            dl, "https://example.org/cases/case_n3_author", note, _OWNER
        )
        seed_case_participant(dl, case, author)
        dl.save(case)

        result = self._remove(dl, make_payload, author, note, case)

        assert result.disposition == HandlerDisposition.APPLIED
        case = cast(as_VulnerabilityCase, dl.read(case.id_))
        assert note.id_ not in case.notes

    @pytest.mark.spec("CM-30-001")
    def test_remove_note_by_author_who_left_is_refused(self, make_payload):
        """An author who is no longer a participant has no standing."""
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_STORE_ACTOR)
        author = "https://example.org/actors/departed-author"
        note = as_Note(
            id_="https://example.org/notes/note_departed",
            content="A note",
            attributed_to=author,
        )
        case = self._managed_case_with_note(
            dl, "https://example.org/cases/case_n3_departed", note, _OWNER
        )

        result = self._remove(dl, make_payload, author, note, case)

        assert result.disposition == HandlerDisposition.REFUSED
        case = cast(as_VulnerabilityCase, dl.read(case.id_))
        assert note.id_ in case.notes
        assert dl.list_objects("CaseLedgerEntry") == []

    @pytest.mark.spec("HP-01-005")
    def test_remove_note_at_non_manager_is_refused(self, make_payload):
        """A replica neither detaches nor commits; the CASE_MANAGER sent it."""
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_STORE_ACTOR)
        manager = "https://example.org/actors/the-manager"
        note = as_Note(id_="https://example.org/notes/note_rep", content="x")
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/case_n3_replica",
            name="Replica",
            attributed_to=_OWNER,
            notes=[note.id_],
        )
        seed_case_manager_participant(dl, case, manager)
        dl.create(case)
        dl.create(note)

        result = self._remove(dl, make_payload, manager, note, case)

        assert result.disposition == HandlerDisposition.REFUSED
        case = cast(as_VulnerabilityCase, dl.read(case.id_))
        assert note.id_ in case.notes
        assert dl.list_objects("CaseLedgerEntry") == []

    @pytest.mark.spec("CM-30-001")
    def test_remove_note_at_replica_from_non_manager_is_refused(
        self, make_payload
    ):
        """At a replica only the CASE_MANAGER is an entitled sender."""
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_STORE_ACTOR)
        note = as_Note(id_="https://example.org/notes/note_rep2", content="x")
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/case_n3_replica2",
            name="Replica",
            attributed_to=_OWNER,
            notes=[note.id_],
        )
        seed_case_manager_participant(
            dl, case, "https://example.org/actors/the-manager"
        )
        dl.create(case)
        dl.create(note)

        result = self._remove(dl, make_payload, _OWNER, note, case)

        assert result.disposition == HandlerDisposition.REFUSED
        assert result.reason is not None and "CASE_MANAGER" in result.reason

    def test_remove_note_from_case_idempotent(self, monkeypatch, make_payload):
        """A note the case does not hold is SKIPPED and commits nothing."""
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_STORE_ACTOR)
        note = as_Note(id_="https://example.org/notes/note6", content="A note")
        case = self._managed_case_with_note(
            dl, "https://example.org/cases/case_n4", note, _OWNER
        )
        case.notes.clear()
        dl.save(case)

        result = self._remove(dl, make_payload, _OWNER, note, case)

        # HP-01-003: an idempotent re-removal is a no-op.
        assert result.disposition == HandlerDisposition.SKIPPED
        assert dl.list_objects("CaseLedgerEntry") == []

    @pytest.mark.spec("HP-01-003")
    def test_remove_note_from_unknown_case_is_refused(self, make_payload):
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        note = as_Note(id_="https://example.org/notes/note7", content="x")
        activity = as_Remove(
            actor="https://example.org/users/finder",
            object_=note,
            target="https://example.org/cases/no-such-case",
        )
        event = make_payload(activity)

        result = RemoveNoteFromCaseReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert result.disposition == HandlerDisposition.REFUSED
        assert result.reason is not None and "not found" in result.reason

    @pytest.mark.spec("HP-01-003")
    @pytest.mark.parametrize(
        "use_case",
        [AddNoteToCaseReceivedUseCase, RemoveNoteFromCaseReceivedUseCase],
    )
    def test_note_membership_change_without_ids_is_refused(self, use_case):
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        event = MagicMock()
        event.note_id = None
        event.case_id = "https://example.org/cases/c"

        result = use_case(dl, event).execute()

        assert result.disposition == HandlerDisposition.REFUSED

    @pytest.mark.spec("HP-01-003")
    def test_create_note_without_note_object_is_refused(self):
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        event = MagicMock()
        event.note = None

        result = CreateNoteReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert result.disposition == HandlerDisposition.REFUSED

    @pytest.mark.spec("HP-01-003")
    def test_create_note_for_unknown_case_is_refused(self, make_payload):
        """A note whose context names a case this actor lacks is refused."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        note = as_Note(
            id_="https://example.org/notes/note8",
            content="x",
            context="https://example.org/cases/no-such-case",
        )
        activity = as_Create(
            actor="https://example.org/users/finder", object_=note
        )
        event = make_payload(activity)

        result = CreateNoteReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert result.disposition == HandlerDisposition.REFUSED

    @pytest.mark.spec("HP-01-003")
    def test_add_note_to_unknown_case_is_refused(self, make_payload):
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://example.org/actors/non-manager",
        )
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/never-stored", name="x"
        )
        note = as_Note(id_="https://example.org/notes/note9", content="x")
        activity = add_note_to_case_activity(
            note, target=case, actor="https://example.org/users/finder"
        )
        event = make_payload(
            activity,
            receiving_actor_id="https://example.org/actors/non-manager",
        )

        result = AddNoteToCaseReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert result.disposition == HandlerDisposition.REFUSED

    # ------------------------------------------------------------------
    # CaseLedgerEntry cascade tests (PCR-08-003, PCR-08-004) — AC-1
    # ------------------------------------------------------------------

    def test_add_note_commits_log_entry_when_sync_port_provided(
        self, make_payload
    ):
        """AddNoteToCaseReceivedUseCase commits a CaseLedgerEntry (PCR-08-003).

        When a sync_port is injected and receiving_actor_id is set, the use
        case MUST commit one CaseLedgerEntry after accepting a note
        addition.
        """
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://example.org/cases/case_le1/actor",
        )
        case_actor_id = "https://example.org/cases/case_le1/actor"
        author_id = "https://example.org/users/vendor"
        participant_id = "https://example.org/users/finder"
        case_id = "https://example.org/cases/case_le1"

        case_actor = CaseActor(
            id_=case_actor_id,
            name="CaseActor le1",
            attributed_to=author_id,
            context=case_id,
        )
        dl.create(case_actor)

        case = as_VulnerabilityCase(
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
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )

        case_manager_participant = as_CaseParticipant(
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
        AddNoteToCaseReceivedUseCase(
            dl,
            event,
            sync_port=sync_port,
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        # Exactly one CaseLedgerEntry should be persisted for this case.
        entries = [
            obj
            for obj in dl.list_objects("CaseLedgerEntry")
            if isinstance(obj, CaseLedgerEntry)
            and cast(CaseLedgerEntry, obj).case_id == case_id
        ]
        assert len(entries) == 1
        entry = cast(CaseLedgerEntry, entries[0])
        assert entry.event_type == "add_note_to_case"
        assert entry.log_object_id == activity.id_

    @pytest.mark.spec("SYNC-02-002")
    @pytest.mark.spec("BT-14-001")
    def test_add_note_without_sync_port_raises_as_wiring_fault(
        self, make_payload
    ):
        """A missing sync_port fails the commit instead of skipping fan-out.

        ``RequireSyncPortNode`` raises ``VultronWiringError`` before the entry
        is minted (#4113).  ``CommitCaseLedgerEntryNode`` carries the nested
        bridge's ``internal_error`` across the hop, so the handler raises
        ``VultronBTInternalError`` rather than reporting the sender as refused
        (ADR-0095).  The note is not attached and nothing is announced.
        """
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://example.org/cases/case_le2/actor",
        )
        case_actor_id = "https://example.org/cases/case_le2/actor"
        author_id = "https://example.org/users/vendor"
        participant_id = "https://example.org/users/finder"
        case_id = "https://example.org/cases/case_le2"

        case_actor = CaseActor(
            id_=case_actor_id,
            name="CaseActor le2",
            attributed_to=author_id,
            context=case_id,
        )
        dl.create(case_actor)

        case = as_VulnerabilityCase(
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
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )

        case_manager_participant = as_CaseParticipant(
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

        # No sync_port — the commit's fan-out is a wiring fault.
        with pytest.raises(VultronBTInternalError, match="sync_port"):
            AddNoteToCaseReceivedUseCase(
                dl,
                event,
                sync_port=None,
                wire_render_port=As2WireRenderAdapter(),
            ).execute()

        stored_case = cast(as_VulnerabilityCase, dl.read(case_id))
        assert stored_case is not None
        assert note.id_ not in stored_case.notes

        # The port guard refuses before the mint, so no entry is written
        # that no replica would ever receive.
        entries = [
            obj
            for obj in dl.list_objects("CaseLedgerEntry")
            if isinstance(obj, CaseLedgerEntry)
            and cast(CaseLedgerEntry, obj).case_id == case_id
        ]
        assert entries == []

        # Nothing is announced to participants.
        assert dl.outbox_list() == []
