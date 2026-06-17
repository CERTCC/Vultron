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
"""Unit tests for AddNoteToCaseReceivedUseCase CaseActor ledger routing.

Pins the pre-flight guard (CLP-10-003): only the CaseActor writes an
``add_note_to_case`` ledger entry; other actors skip it silently.

Also verifies the bug fix where ``receiving_actor_id=None`` no longer
falls back to ``_find_case_actor_id`` and incorrectly commits.
"""

from __future__ import annotations

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.states.roles import CVDRole
from vultron.core.use_cases.received.note import AddNoteToCaseReceivedUseCase
from vultron.wire.as2.factories import add_note_to_case_activity
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CASE_ACTOR_ID = "https://example.org/actors/case-actor-note"
VENDOR_ID = "https://example.org/actors/vendor-note"
CASE_ID = "https://example.org/cases/c-note-test"
NOTE_ID = "https://example.org/notes/n-test"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_blackboard():
    import py_trees

    py_trees.blackboard.Blackboard.storage.clear()
    yield
    py_trees.blackboard.Blackboard.storage.clear()


def _make_dl() -> SqliteDataLayer:
    return SqliteDataLayer("sqlite:///:memory:")


def _make_case_actor_dl() -> SqliteDataLayer:
    """DataLayer as seen by the CaseActor: case + CASE_MANAGER participant + note."""
    dl = _make_dl()

    ca_svc = VultronCaseActor(id_=CASE_ACTOR_ID, context=CASE_ID)
    dl.save(ca_svc)

    case = VulnerabilityCase(id_=CASE_ID, name="AddNote Routing Test")

    cm_participant = CaseParticipant(
        attributed_to=CASE_ACTOR_ID,
        context=CASE_ID,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    dl.create(cm_participant)
    case.case_participants.append(cm_participant.id_)
    case.actor_participant_index[CASE_ACTOR_ID] = cm_participant.id_
    dl.save(case)

    # Persist the note object so the use case can find it.
    note = as_Note(
        id_=NOTE_ID,
        content="Test note content",
        context=CASE_ID,
    )
    dl.create(note)

    return dl


def _ledger_event_types(dl: SqliteDataLayer) -> list[str]:
    return [
        getattr(e, "event_type", "")
        for e in dl.list_objects("CaseLedgerEntry")
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAddNoteToCaseLedgerRouting:
    """CaseActor-guarded commit tests for AddNoteToCaseReceivedUseCase."""

    def test_caseactor_commits_add_note_to_case_ledger_entry(
        self, make_payload
    ):
        """Guarded commit fires when receiving_actor_id == case_actor_id.

        Per CLP-10-002: the CaseActor MUST commit a canonical ledger entry
        when it receives an AddNoteToCase activity.
        """
        dl = _make_case_actor_dl()

        case = dl.read(CASE_ID)
        note = as_Note(id_=NOTE_ID, content="Test note content")
        activity = add_note_to_case_activity(
            note=note,
            target=case,
            actor=VENDOR_ID,
            to=[CASE_ACTOR_ID],
        )
        event = make_payload(activity, receiving_actor_id=CASE_ACTOR_ID)

        AddNoteToCaseReceivedUseCase(
            dl=dl,
            request=event,
            sync_port=SyncActivityAdapter(dl),
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()

        event_types = _ledger_event_types(dl)
        assert "add_note_to_case" in event_types, (
            "Expected a CaseLedgerEntry with event_type='add_note_to_case';"
            f" found: {event_types}"
        )

    def test_non_caseactor_does_not_commit_ledger_entry(self, make_payload):
        """Guarded commit does NOT fire when receiving_actor_id != case_actor_id.

        Per CLP-10-003: non-CaseActor receiving actors must skip the commit.
        """
        dl = _make_case_actor_dl()

        case = dl.read(CASE_ID)
        note = as_Note(id_=NOTE_ID, content="Test note content")
        activity = add_note_to_case_activity(
            note=note,
            target=case,
            actor=VENDOR_ID,
            to=[CASE_ACTOR_ID],
        )
        event = make_payload(activity, receiving_actor_id=VENDOR_ID)

        AddNoteToCaseReceivedUseCase(
            dl=dl,
            request=event,
            sync_port=SyncActivityAdapter(dl),
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()

        event_types = _ledger_event_types(dl)
        assert "add_note_to_case" not in event_types, (
            "Non-CaseActor receiving actor must NOT write an add_note_to_case"
            f" ledger entry; found: {event_types}"
        )

    def test_no_receiving_actor_id_skips_commit(self, make_payload):
        """Guarded commit does NOT fire when receiving_actor_id is None.

        This was the bug: previously, None fell back to _find_case_actor_id,
        causing the commit to run even when no receiving actor was set.
        Per CLP-10-003 the guard must be strict.
        """
        dl = _make_case_actor_dl()

        case = dl.read(CASE_ID)
        note = as_Note(id_=NOTE_ID, content="Test note content")
        activity = add_note_to_case_activity(
            note=note,
            target=case,
            actor=VENDOR_ID,
            to=[CASE_ACTOR_ID],
        )
        event = make_payload(activity)
        # Explicitly clear receiving_actor_id (make_payload may not set it).
        event = event.model_copy(update={"receiving_actor_id": None})

        AddNoteToCaseReceivedUseCase(
            dl=dl,
            request=event,
            sync_port=SyncActivityAdapter(dl),
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()

        event_types = _ledger_event_types(dl)
        assert "add_note_to_case" not in event_types, (
            "Missing receiving_actor_id must NOT write an add_note_to_case"
            f" ledger entry; found: {event_types}"
        )
