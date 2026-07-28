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
"""Unit tests for CloseCaseReceivedUseCase CaseActor ledger routing.

Pins the pre-flight guard (CLP-10-003): only the CaseActor writes a
``close_case`` ledger entry; other actors skip it silently.
"""

from __future__ import annotations

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.core.models.activity import VultronActivity
from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.events.case import CloseCaseReceivedEvent
from vultron.enums.roles import CVDRole
from vultron.core.use_cases.received.case.lifecycle import (
    CloseCaseReceivedUseCase,
)
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CASE_ACTOR_ID = "https://example.org/actors/case-actor-close"
VENDOR_ID = "https://example.org/actors/vendor-close"
CASE_ID = "https://example.org/cases/c-close-test"


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
    """DataLayer as seen by the CaseActor: case + CASE_MANAGER participant."""
    dl = _make_dl()

    ca_svc = VultronCaseActor(id_=CASE_ACTOR_ID, context=CASE_ID)
    dl.save(ca_svc)

    case = as_VulnerabilityCase(
        id_=CASE_ID,
        name="CloseCase Routing Test",
        attributed_to=CASE_ACTOR_ID,
    )

    cm_participant = as_CaseParticipant(
        attributed_to=CASE_ACTOR_ID,
        context=CASE_ID,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    dl.create(cm_participant)
    case.case_participants.append(cm_participant.id_)
    case.actor_participant_index[CASE_ACTOR_ID] = cm_participant.id_
    dl.save(case)

    return dl


def _make_close_case_event(
    receiving_actor_id: str | None = CASE_ACTOR_ID,
    leave_actor_id: str = VENDOR_ID,
) -> CloseCaseReceivedEvent:
    """Construct a CloseCaseReceivedEvent (Leave(as_VulnerabilityCase)).

    Args:
        receiving_actor_id: The actor whose inbox is processing this Leave.
        leave_actor_id: The ``actor`` field on the Leave activity wire object.
            Defaults to VENDOR_ID (participant-originated Leave).  Pass
            CASE_ACTOR_ID to simulate the AutoCloseBranchNode path where the
            case-actor emits the Leave to itself.
    """
    case_obj = as_VulnerabilityCase(id_=CASE_ID)
    activity = VultronActivity(
        id_="https://example.org/activities/leave-case",
        type_="Leave",
        actor=leave_actor_id,
        object_=case_obj,
    )
    return CloseCaseReceivedEvent(
        semantic_type=MessageSemantics.CLOSE_CASE,
        activity_id=activity.id_,
        actor_id=leave_actor_id,
        object_=case_obj,
        activity=activity,
        receiving_actor_id=receiving_actor_id,
    )


def _ledger_event_types(dl: SqliteDataLayer) -> list[str]:
    return [
        getattr(e, "event_type", "")
        for e in dl.list_objects("CaseLedgerEntry")
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCloseCaseLedgerRouting:
    """CaseActor-guarded commit tests for CloseCaseReceivedUseCase."""

    def test_caseactor_commits_close_case_ledger_entry(self):
        """Guarded commit fires when receiving_actor_id == case_actor_id.

        Per CLP-10-002: the CaseActor MUST commit a canonical ledger entry
        when it receives a close_case (Leave) activity.
        """
        dl = _make_case_actor_dl()
        CloseCaseReceivedUseCase(
            dl=dl,
            request=_make_close_case_event(receiving_actor_id=CASE_ACTOR_ID),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        event_types = _ledger_event_types(dl)
        assert "close_case" in event_types, (
            "Expected a CaseLedgerEntry with event_type='close_case';"
            f" found: {event_types}"
        )

    def test_non_caseactor_does_not_commit_ledger_entry(self):
        """Guarded commit does NOT fire when receiving_actor_id != case_actor_id.

        Per CLP-10-003: non-CaseActor receiving actors must skip the commit.
        """
        dl = _make_case_actor_dl()
        CloseCaseReceivedUseCase(
            dl=dl,
            request=_make_close_case_event(receiving_actor_id=VENDOR_ID),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        event_types = _ledger_event_types(dl)
        assert "close_case" not in event_types, (
            "Non-CaseActor receiving actor must NOT write a close_case"
            f" ledger entry; found: {event_types}"
        )

    def test_caseactor_self_leave_commits_close_case_ledger_entry(self):
        """Case-actor-authored Leave (AutoCloseBranchNode path) is committed.

        AutoCloseBranchNode emits Leave(as_VulnerabilityCase) with
        actor=case_actor_id to signal that all participants have closed.  The
        case-actor must accept its own Leave as a canonical ledger entry
        because the close_case signature IS case-authored (DEMOMA-07-003 step 5).

        This test pins the _CASE_AUTHORED_SIGNATURES entry for
        ("Leave", "VulnerabilityCase") in chain.py.  Without it the
        _validate_canonical_entry check raises:
        "payloadSnapshot.actor must not be the CaseActor for non-case-authored
        entries (signature=('Leave', 'VulnerabilityCase'))"
        """
        dl = _make_case_actor_dl()
        CloseCaseReceivedUseCase(
            dl=dl,
            request=_make_close_case_event(
                receiving_actor_id=CASE_ACTOR_ID,
                leave_actor_id=CASE_ACTOR_ID,
            ),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        event_types = _ledger_event_types(dl)
        assert "close_case" in event_types, (
            "Expected a CaseLedgerEntry with event_type='close_case'"
            " when the case-actor is both sender and receiver (AutoClose path);"
            f" found: {event_types}"
        )
