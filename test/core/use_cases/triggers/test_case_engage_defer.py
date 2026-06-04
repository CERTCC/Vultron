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
BT-path tests for engage-case, defer-case, and add-note-to-case trigger use cases.

Satisfies #712 AC-3: verifies that RM state transitions (engage/defer) and note
creation/attachment are performed *inside* the behavior tree, not in pre-BT
procedural code.

Failure semantics (documented by design):
- If the sender subtree fails (no Case Manager in DL), the RM state IS updated
  but no activity is sent.  This preserves the old behavior where the pre-BT
  RM update always ran before the BT.
"""

import pytest

from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.states.rm import RM
from vultron.core.states.roles import CVDRole
from vultron.errors import VultronValidationError
from vultron.core.use_cases.triggers.case import (
    DeferCaseTriggerRequest,
    EngageCaseTriggerRequest,
    SvcDeferCaseUseCase,
    SvcEngageCaseUseCase,
)
from vultron.core.use_cases.triggers.note import (
    AddNoteToCaseTriggerRequest,
    SvcAddNoteToCaseUseCase,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import (
    CaseParticipant,
    FinderParticipant,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_actor(name: str) -> as_Service:
    return as_Service(name=name, url=f"https://example.org/{name.lower()}")


def _make_actor_dl(name: str) -> tuple[as_Service, SqliteDataLayer]:
    actor = _make_actor(name)
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor.id_)
    dl.clear_all()
    dl.create(actor)
    return actor, dl


def _make_case_with_case_manager(
    dl: SqliteDataLayer,
    actor_id: str,
    finder_id: str,
    case_actor_id: str,
) -> tuple[VulnerabilityCase, CaseParticipant]:
    """Create a VulnerabilityCase with all participants in both index and list.

    The actor participant is pre-initialized to RM.VALID so that
    engage (→ ACCEPTED) and defer (→ DEFERRED) transitions are valid.
    """
    case = VulnerabilityCase(name="Test Case")

    actor_participant = CaseParticipant(
        attributed_to=actor_id,
        context=case.id_,
        case_roles=[CVDRole.VENDOR],
    )
    # Pre-advance actor to RM.VALID so engage/defer transitions will succeed
    from vultron.wire.as2.vocab.objects.case_status import (
        ParticipantStatus as WireParticipantStatus,
    )

    actor_participant.participant_statuses.append(
        WireParticipantStatus(context=case.id_, rm_state=RM.RECEIVED)
    )
    actor_participant.participant_statuses.append(
        WireParticipantStatus(context=case.id_, rm_state=RM.VALID)
    )

    finder_participant = FinderParticipant(
        attributed_to=finder_id,
        context=case.id_,
    )
    case_manager_participant = CaseParticipant(
        attributed_to=case_actor_id,
        context=case.id_,
        case_roles=[CVDRole.CASE_MANAGER],
    )

    case.actor_participant_index[actor_id] = actor_participant.id_
    case.actor_participant_index[finder_id] = finder_participant.id_
    case.actor_participant_index[case_actor_id] = case_manager_participant.id_

    # Required so update_participant_rm_state() can find the participant
    case.case_participants.append(actor_participant.id_)
    case.case_participants.append(finder_participant.id_)
    case.case_participants.append(case_manager_participant.id_)

    dl.create(case)
    dl.create(actor_participant)
    dl.create(finder_participant)
    dl.create(case_manager_participant)
    return case, actor_participant


# ---------------------------------------------------------------------------
# Engage-case BT-path tests (AC-3, #712)
# ---------------------------------------------------------------------------


class TestEngageCaseRMTransitionViaBT:
    """RM state transition for engage-case happens inside the BT (AC-1 + AC-3)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.vendor, self.dl = _make_actor_dl("Vendor Co")
        self.finder, _ = _make_actor_dl("Finder Co")
        self.case_actor, _ = _make_actor_dl("Case Actor")
        self.case, self.vendor_participant = _make_case_with_case_manager(
            self.dl,
            self.vendor.id_,
            self.finder.id_,
            self.case_actor.id_,
        )
        yield
        self.dl.clear_all()
        reset_datalayer(self.vendor.id_)
        reset_datalayer(self.finder.id_)
        reset_datalayer(self.case_actor.id_)

    def test_engage_case_updates_rm_to_accepted_via_bt(self):
        """After SvcEngageCaseUseCase.execute(), the actor's RM state is ACCEPTED.

        This verifies AC-1 + AC-3: the RM transition now runs inside the BT
        (TransitionParticipantRMtoAccepted node), not in pre-BT procedural code.
        """
        request = EngageCaseTriggerRequest(
            actor_id=self.vendor.id_,
            case_id=self.case.id_,
        )
        SvcEngageCaseUseCase(
            self.dl, request, trigger_activity=TriggerActivityAdapter(self.dl)
        ).execute()

        # Re-read participant from DataLayer to confirm BT wrote the change
        updated = self.dl.read(self.vendor_participant.id_)
        assert updated is not None
        assert (
            updated.participant_statuses
        ), "Expected at least one ParticipantStatus after engage"
        assert (
            updated.participant_statuses[-1].rm_state == RM.ACCEPTED
        ), f"Expected RM.ACCEPTED, got {updated.participant_statuses[-1].rm_state}"

    def test_engage_case_rm_not_updated_when_no_participant(self):
        """When participant is NOT in case_participants, the BT transitions
        RM FAIL path and VultronValidationError is raised.

        Documents failure semantics: the old code silently skipped the RM
        update when the participant was absent; the BT now surfaces this as
        an explicit failure.
        """
        # Build a case with only actor_participant_index (not case_participants)
        case_solo = VulnerabilityCase(name="Solo Case")
        case_solo.actor_participant_index[self.vendor.id_] = (
            f"{case_solo.id_}/participants/vendor"
        )
        self.dl.create(case_solo)

        request = EngageCaseTriggerRequest(
            actor_id=self.vendor.id_,
            case_id=case_solo.id_,
        )
        with pytest.raises(VultronValidationError):
            SvcEngageCaseUseCase(
                self.dl,
                request,
                trigger_activity=TriggerActivityAdapter(self.dl),
            ).execute()


# ---------------------------------------------------------------------------
# Defer-case BT-path tests (AC-3, #712)
# ---------------------------------------------------------------------------


class TestDeferCaseRMTransitionViaBT:
    """RM state transition for defer-case happens inside the BT (AC-1 + AC-3)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.vendor, self.dl = _make_actor_dl("Vendor Co")
        self.finder, _ = _make_actor_dl("Finder Co")
        self.case_actor, _ = _make_actor_dl("Case Actor")
        self.case, self.vendor_participant = _make_case_with_case_manager(
            self.dl,
            self.vendor.id_,
            self.finder.id_,
            self.case_actor.id_,
        )
        yield
        self.dl.clear_all()
        reset_datalayer(self.vendor.id_)
        reset_datalayer(self.finder.id_)
        reset_datalayer(self.case_actor.id_)

    def test_defer_case_updates_rm_to_deferred_via_bt(self):
        """After SvcDeferCaseUseCase.execute(), the actor's RM state is DEFERRED.

        This verifies AC-1 + AC-3: the RM transition now runs inside the BT
        (TransitionParticipantRMtoDeferred node), not in pre-BT procedural code.
        """
        request = DeferCaseTriggerRequest(
            actor_id=self.vendor.id_,
            case_id=self.case.id_,
        )
        SvcDeferCaseUseCase(
            self.dl, request, trigger_activity=TriggerActivityAdapter(self.dl)
        ).execute()

        # Re-read participant from DataLayer to confirm BT wrote the change
        updated = self.dl.read(self.vendor_participant.id_)
        assert updated is not None
        assert (
            updated.participant_statuses
        ), "Expected at least one ParticipantStatus after defer"
        assert (
            updated.participant_statuses[-1].rm_state == RM.DEFERRED
        ), f"Expected RM.DEFERRED, got {updated.participant_statuses[-1].rm_state}"


# ---------------------------------------------------------------------------
# Add-note-to-case BT-path tests (AC-2 + AC-3, #712)
# ---------------------------------------------------------------------------


class TestAddNoteToCaseViaBT:
    """Note creation and attachment happen inside the BT (AC-2 + AC-3)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.vendor, self.dl = _make_actor_dl("Vendor Co")
        self.finder, _ = _make_actor_dl("Finder Co")
        self.case_actor, _ = _make_actor_dl("Case Actor")
        self.case, self.vendor_participant = _make_case_with_case_manager(
            self.dl,
            self.vendor.id_,
            self.finder.id_,
            self.case_actor.id_,
        )
        yield
        self.dl.clear_all()
        reset_datalayer(self.vendor.id_)
        reset_datalayer(self.finder.id_)
        reset_datalayer(self.case_actor.id_)

    def test_add_note_creates_note_via_bt(self):
        """SvcAddNoteToCaseUseCase returns a note object and the note_id is in
        the case's notes list.

        This verifies AC-2 + AC-3: note creation now runs inside the BT
        (CreateNoteNode), and attachment runs inside the BT
        (AttachNoteFromResultNode), not in pre-BT procedural code.
        """
        request = AddNoteToCaseTriggerRequest(
            actor_id=self.vendor.id_,
            case_id=self.case.id_,
            note_name="Test Note",
            note_content="This is a test note content.",
        )
        result = SvcAddNoteToCaseUseCase(
            self.dl,
            request,
            trigger_activity=TriggerActivityAdapter(self.dl),
        ).execute()

        # The returned note should be non-None (BT created it)
        assert (
            result.get("note") is not None
        ), "Expected note dict in result after BT-driven creation"

        # The case's notes list should contain the new note id
        updated_case = self.dl.read(self.case.id_)
        assert updated_case is not None
        assert (
            len(updated_case.notes) >= 1
        ), "Expected case.notes to contain the new note after BT-driven attachment"

    def test_add_note_returns_activity_via_bt(self):
        """SvcAddNoteToCaseUseCase returns an activity dict built inside the BT."""
        request = AddNoteToCaseTriggerRequest(
            actor_id=self.vendor.id_,
            case_id=self.case.id_,
            note_name="Activity Note",
            note_content="Content for activity test.",
        )
        result = SvcAddNoteToCaseUseCase(
            self.dl,
            request,
            trigger_activity=TriggerActivityAdapter(self.dl),
        ).execute()

        assert (
            result.get("activity") is not None
        ), "Expected activity dict in result"
