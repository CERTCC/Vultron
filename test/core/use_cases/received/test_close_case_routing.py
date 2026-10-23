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

from test.support.case_owner import CASE_OWNER_ID
from test.support.received import with_evidence
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.models.activity import VultronActivity
from vultron.core.models.actor import VultronService
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.events.case import CloseCaseReceivedEvent
from vultron.core.use_cases.received.case.lifecycle import (
    CloseCaseReceivedUseCase,
)
from vultron.enums.roles import CVDRole
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


def _make_dl(actor_id: str = CASE_ACTOR_ID) -> SqliteDataLayer:
    """The store of *actor_id*, defaulting to the case actor.

    The canonical ledger these tests assert on belongs to the case actor, and the
    commit is gated on its CASE_MANAGER role, so that is the store the tree runs in.
    """
    return SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)


def _make_case_actor_dl(
    case_manager_owns: bool = False,
) -> SqliteDataLayer:
    """DataLayer as seen by the CaseActor: case, CASE_MANAGER and a vendor.

    With *case_manager_owns* the CASE_MANAGER also holds CASE_OWNER, the
    combined role a case-creating actor can hold.
    """
    dl = _make_dl()

    ca_svc = VultronService(id_=CASE_ACTOR_ID, context=CASE_ID)
    dl.save(ca_svc)

    case = as_VulnerabilityCase(
        id_=CASE_ID,
        name="CloseCase Routing Test",
        attributed_to=CASE_ACTOR_ID,
    )

    cm_participant = as_CaseParticipant(
        attributed_to=CASE_ACTOR_ID,
        context=CASE_ID,
        case_roles=(
            [CVDRole.CASE_MANAGER, CVDRole.CASE_OWNER]
            if case_manager_owns
            else [CVDRole.CASE_MANAGER]
        ),
    )
    dl.create(cm_participant)
    case.case_participants.append(cm_participant.id_)
    case.actor_participant_index[CASE_ACTOR_ID] = cm_participant.id_

    # The Leave's default sender: a participant may leave (HP-01-006).
    vendor_participant = as_CaseParticipant(
        attributed_to=VENDOR_ID,
        context=CASE_ID,
        case_roles=[CVDRole.VENDOR],
    )
    dl.create(vendor_participant)
    case.case_participants.append(vendor_participant.id_)
    case.actor_participant_index[VENDOR_ID] = vendor_participant.id_
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
    case_obj = as_VulnerabilityCase(attributed_to=CASE_OWNER_ID, id_=CASE_ID)
    activity = VultronActivity(
        id_="https://example.org/activities/leave-case",
        type_="Leave",
        actor=leave_actor_id,
        to=[CASE_ACTOR_ID],
        object_=case_obj,
    )
    return with_evidence(
        CloseCaseReceivedEvent(
            semantic_type=MessageSemantics.CLOSE_CASE,
            activity_id=activity.id_,
            actor_id=leave_actor_id,
            object_=case_obj,
            activity=activity,
            receiving_actor_id=receiving_actor_id,
        )
    )


def _ledger_semantic_types(dl: SqliteDataLayer) -> list[str]:
    return [
        getattr(e, "semantic_type", "")
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
            wire_render_port=As2WireRenderAdapter(),
            # The leaver's closure steps are factory-built (VM-08-003).
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()

        semantic_types = _ledger_semantic_types(dl)
        assert "close_case" in semantic_types, (
            "Expected a CaseLedgerEntry with semantic_type='close_case';"
            f" found: {semantic_types}"
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
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        semantic_types = _ledger_semantic_types(dl)
        assert "close_case" not in semantic_types, (
            "Non-CaseActor receiving actor must NOT write a close_case"
            f" ledger entry; found: {semantic_types}"
        )

    def test_caseactor_self_leave_commits_close_case_ledger_entry(self):
        """Case-actor-authored Leave (AutoCloseBranchNode path) is committed.

        AutoCloseBranchNode emits Leave(as_VulnerabilityCase) with
        actor=case_actor_id to signal that all participants have closed.  The
        case-actor must accept its own Leave as a canonical ledger entry
        because the close_case signature IS case-authored (DEMOMA-07-003 step 5).

        This test pins the _CASE_AUTHORED_SIGNATURES entry for
        ("Leave", "VulnerabilityCase") in
        vultron/core/behaviors/sync/nodes/canonical_entry.py.  Without it the
        _validate_canonical_entry check raises:
        "payloadSnapshot.actor must not be the CaseActor for non-case-authored
        entries (signature=('Leave', 'VulnerabilityCase'))"

        The CASE_MANAGER here also holds CASE_OWNER: a CASE_MANAGER that is
        not the Case Owner cannot leave, because its RM.CLOSED is the
        owner-close boundary (CM-23-010).
        """
        dl = _make_case_actor_dl(case_manager_owns=True)
        CloseCaseReceivedUseCase(
            dl=dl,
            request=_make_close_case_event(
                receiving_actor_id=CASE_ACTOR_ID,
                leave_actor_id=CASE_ACTOR_ID,
            ),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            # The closure steps' entries are factory-built (VM-08-003); a
            # closure the CASE_MANAGER cannot record is not made (#4442).
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()

        semantic_types = _ledger_semantic_types(dl)
        assert "close_case" in semantic_types, (
            "Expected a CaseLedgerEntry with semantic_type='close_case'"
            " when the case-actor is both sender and receiver (AutoClose path);"
            f" found: {semantic_types}"
        )

    def test_absent_stamp_uses_store_owner_for_commit(self):
        """When receiving_actor_id is absent the store owner processes the Leave.

        Absent-stamp path (CLP-10-005): resolve_receiving_actor_id falls back to
        dl.actor_id (CASE_ACTOR_ID here), so the guarded commit fires and the
        ``close_case`` ledger entry IS written.
        """
        dl = _make_case_actor_dl()
        CloseCaseReceivedUseCase(
            dl=dl,
            request=_make_close_case_event(receiving_actor_id=None),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            # The leaver's closure steps are factory-built (VM-08-003).
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()

        semantic_types = _ledger_semantic_types(dl)
        assert "close_case" in semantic_types, (
            "Store-owner fallback (CaseActor) MUST write a close_case"
            f" ledger entry when receiving_actor_id is absent; found: {semantic_types}"
        )
