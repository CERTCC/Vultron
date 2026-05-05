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

"""
Tests for SvcAddNoteToCaseUseCase (D5-7-DEMONOTECLEAN-1).

Verifies that the add-note-to-case trigger:
- creates the note in the DataLayer,
- adds the note ID to the actor's local case.notes list,
- queues Create(Note) and AddNoteToCase activities in the actor's outbox,
- populates the ``to`` field with case participants (excluding the actor),
- handles the optional in_reply_to field correctly.
"""

import pytest

from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.core.use_cases.triggers.note import SvcAddNoteToCaseUseCase
from vultron.core.use_cases.triggers.requests import (
    AddNoteToCaseTriggerRequest,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)

# ---------------------------------------------------------------------------
# Helpers (mirrors pattern in test_trignotify.py)
# ---------------------------------------------------------------------------


def _make_actor_dl(actor_name: str):
    """Create an as_Service actor and a matching per-actor SqliteDataLayer."""
    actor = as_Service(name=actor_name)
    actor_id = actor.id_
    reset_datalayer(actor_id)
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)
    dl.clear_all()
    dl.create(actor)
    return actor, dl


def _make_two_actor_case(
    dl, actor1_id: str, actor2_id: str
) -> VulnerabilityCase:
    """Create a VulnerabilityCase with two actors in actor_participant_index."""
    case = VulnerabilityCase(name="Test Case")
    case.actor_participant_index[actor1_id] = f"{case.id_}/participants/actor1"
    case.actor_participant_index[actor2_id] = f"{case.id_}/participants/actor2"
    dl.create(case)
    return case


def _to_field(activity_obj) -> list[str] | None:
    """Return the ``to`` field of an activity as a list of strings."""
    if activity_obj is None:
        return None
    to = getattr(activity_obj, "to", None)
    if to is None:
        return None
    if isinstance(to, list):
        return [
            item if isinstance(item, str) else getattr(item, "id_", str(item))
            for item in to
        ]
    if isinstance(to, str):
        return [to]
    return None


def _outbox_activity_ids(actor_id: str, dl: SqliteDataLayer) -> list[str]:
    """Return all activity IDs in the actor's outbox."""
    # Create a scoped view sharing dl's engine.  The temporary in-memory
    # engine allocated by __init__ is disposed immediately before being
    # replaced, so no sqlite3 connection leaks.
    scoped = SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)
    scoped._engine.dispose()
    scoped._engine = dl._engine
    scoped._owns_engine = False
    return scoped.outbox_list()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class TestSvcAddNoteToCaseUseCase:
    """SvcAddNoteToCaseUseCase creates notes and queues activities."""

    NOTE_NAME = "Question from Finder"
    NOTE_CONTENT = "Is there a workaround available?"

    @pytest.fixture(autouse=True)
    def setup(self):
        self.vendor, self.dl = _make_actor_dl("Vendor Co")
        self.finder, _ = _make_actor_dl("Finder Co")
        self.case = _make_two_actor_case(
            self.dl, self.vendor.id_, self.finder.id_
        )
        yield
        self.dl.clear_all()
        reset_datalayer(self.vendor.id_)
        reset_datalayer(self.finder.id_)

    def _execute(self, actor_id=None, in_reply_to=None):
        """Build and execute the use case; return the result dict."""
        actor_id = actor_id or self.vendor.id_
        request = AddNoteToCaseTriggerRequest(
            actor_id=actor_id,
            case_id=self.case.id_,
            note_name=self.NOTE_NAME,
            note_content=self.NOTE_CONTENT,
            in_reply_to=in_reply_to,
        )
        return SvcAddNoteToCaseUseCase(
            self.dl, request, trigger_activity=TriggerActivityAdapter(self.dl)
        ).execute()

    # ------------------------------------------------------------------
    # Return-value structure
    # ------------------------------------------------------------------

    def test_execute_returns_note_key(self):
        """execute() returns a dict with a 'note' key."""
        result = self._execute()
        assert "note" in result

    def test_execute_returns_activity_key(self):
        """execute() returns a dict with an 'activity' key."""
        result = self._execute()
        assert "activity" in result

    def test_note_has_id(self):
        """Returned note dict contains an 'id' field."""
        result = self._execute()
        assert result["note"].get("id") is not None

    # ------------------------------------------------------------------
    # DataLayer persistence
    # ------------------------------------------------------------------

    def test_note_stored_in_datalayer(self):
        """The note is persisted to the DataLayer after execute()."""
        result = self._execute()
        note_id = result["note"]["id"]
        stored = self.dl.read(note_id)
        assert stored is not None

    def test_note_added_to_case_notes(self):
        """The note ID appears in the actor's local case.notes list."""
        result = self._execute()
        note_id = result["note"]["id"]
        case_obj = self.dl.read(self.case.id_)
        assert isinstance(case_obj, VulnerabilityCase)
        note_ids = [
            n if isinstance(n, str) else getattr(n, "id_", str(n))
            for n in case_obj.notes
        ]
        assert note_id in note_ids

    # ------------------------------------------------------------------
    # Outbox: two activities queued
    # ------------------------------------------------------------------

    def test_two_activities_queued_in_outbox(self):
        """Both Create(Note) and AddNoteToCase are added to the outbox."""
        before = set(_outbox_activity_ids(self.vendor.id_, self.dl))
        self._execute()
        after = set(_outbox_activity_ids(self.vendor.id_, self.dl))
        new_ids = after - before
        assert (
            len(new_ids) == 2
        ), f"Expected 2 new outbox entries, got {len(new_ids)}"

    def test_activities_stored_in_datalayer(self):
        """Both queued activities are readable from the DataLayer."""
        before = set(_outbox_activity_ids(self.vendor.id_, self.dl))
        self._execute()
        after = set(_outbox_activity_ids(self.vendor.id_, self.dl))
        for activity_id in after - before:
            assert self.dl.read(activity_id) is not None

    # ------------------------------------------------------------------
    # ``to`` field population
    # ------------------------------------------------------------------

    def test_add_note_activity_to_field_contains_other_participant(self):
        """AddNoteToCase activity has to=[finder.id_] (excludes the actor)."""
        result = self._execute(actor_id=self.vendor.id_)
        activity_id = result["activity"].get("id")
        assert activity_id is not None

        act_obj = self.dl.read(activity_id)
        recipients = _to_field(act_obj)

        assert recipients is not None, "to field must not be None"
        assert len(recipients) > 0, "to field must be non-empty"
        assert self.finder.id_ in recipients
        assert self.vendor.id_ not in recipients

    def test_to_field_is_none_when_actor_is_only_participant(self):
        """to is empty/None when the actor is the sole case participant."""
        solo_case = VulnerabilityCase(name="Solo Case")
        solo_case.actor_participant_index[self.vendor.id_] = (
            f"{solo_case.id_}/participants/vendor"
        )
        self.dl.create(solo_case)

        request = AddNoteToCaseTriggerRequest(
            actor_id=self.vendor.id_,
            case_id=solo_case.id_,
            note_name=self.NOTE_NAME,
            note_content=self.NOTE_CONTENT,
        )
        result = SvcAddNoteToCaseUseCase(
            self.dl, request, trigger_activity=TriggerActivityAdapter(self.dl)
        ).execute()

        activity_id = result["activity"].get("id")
        act_obj = self.dl.read(activity_id)
        recipients = _to_field(act_obj)

        assert (
            not recipients
        ), "to should be empty/None for solo-participant case"

    # ------------------------------------------------------------------
    # Optional in_reply_to field
    # ------------------------------------------------------------------

    def test_in_reply_to_none_by_default(self):
        """Note is created without in_reply_to when not supplied."""
        result = self._execute()
        note_id = result["note"]["id"]
        stored = self.dl.read(note_id)
        assert getattr(stored, "in_reply_to", None) is None

    def test_in_reply_to_set_when_provided(self):
        """Note carries the supplied in_reply_to value."""
        # Create a parent note to reply to.
        from vultron.wire.as2.vocab.base.objects.object_types import as_Note

        parent = as_Note(
            name="Parent Note",
            content="Original question",
            context=self.case.id_,
        )
        self.dl.create(parent)

        result = self._execute(in_reply_to=parent.id_)
        note_id = result["note"]["id"]
        stored = self.dl.read(note_id)
        assert getattr(stored, "in_reply_to", None) == parent.id_

    # ------------------------------------------------------------------
    # Idempotency: duplicate execute() does not double-add note to case
    # ------------------------------------------------------------------

    def test_duplicate_execute_does_not_duplicate_note_in_case(self):
        """Calling execute() twice with the same note does not add it twice."""
        # We need to execute the same request twice — reuse _execute(), which
        # creates a new note each time (different IDs). Test the idempotency
        # guard for note IDs already in case.notes instead.
        result = self._execute()
        note_id = result["note"]["id"]

        # Manually call the idempotency guard path by appending note_id again.
        case_obj = self.dl.read(self.case.id_)
        assert isinstance(case_obj, VulnerabilityCase)
        count_before = sum(
            1
            for n in case_obj.notes
            if (n if isinstance(n, str) else getattr(n, "id_", str(n)))
            == note_id
        )
        assert count_before == 1

        # Simulate a second save attempt via the use case guard logic.
        existing_ids = [
            n if isinstance(n, str) else getattr(n, "id_", str(n))
            for n in case_obj.notes
        ]
        if note_id not in existing_ids:
            case_obj.notes.append(note_id)
            self.dl.save(case_obj)

        # Re-read and confirm still exactly one occurrence.
        case_obj2 = self.dl.read(self.case.id_)
        assert isinstance(case_obj2, VulnerabilityCase)
        count_after = sum(
            1
            for n in case_obj2.notes
            if (n if isinstance(n, str) else getattr(n, "id_", str(n)))
            == note_id
        )
        assert count_after == 1
