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
"""Unit tests for embargo received use-case CaseActor ledger routing.

Pins the pre-flight guard (CLP-10-003):
- InviteToEmbargoOnCaseReceivedUseCase: only CaseActor writes a ledger entry.
- AcceptInviteToEmbargoOnCaseReceivedUseCase: only CaseActor writes a ledger
  entry.
"""

from __future__ import annotations

from typing import cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.states.em import EM
from vultron.core.states.roles import CVDRole
from vultron.core.use_cases.received.embargo import (
    AcceptInviteToEmbargoOnCaseReceivedUseCase,
    InviteToEmbargoOnCaseReceivedUseCase,
)
from vultron.wire.as2.factories import (
    em_accept_embargo_activity,
    em_propose_embargo_activity,
)
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_blackboard():
    import py_trees

    py_trees.blackboard.Blackboard.storage.clear()
    yield
    py_trees.blackboard.Blackboard.storage.clear()


def _make_embargo_case(
    case_id: str,
    author_id: str,
    case_actor_id: str,
) -> tuple[SqliteDataLayer, VultronCaseActor, VulnerabilityCase, EmbargoEvent]:
    """Return (dl, case_actor, case, embargo) ready for routing tests."""
    dl = SqliteDataLayer("sqlite:///:memory:")

    case_actor = VultronCaseActor(
        id_=case_actor_id,
        name=f"CaseActor for {case_id}",
        attributed_to=author_id,
        context=case_id,
    )
    dl.create(case_actor)

    case = VulnerabilityCase(
        id_=case_id,
        name="Embargo Routing Test",
        attributed_to=author_id,
    )
    p1_id = f"{case_id}/participants/p1"
    case.actor_participant_index[author_id] = p1_id
    p1 = CaseParticipant(id_=p1_id, context=case_id, attributed_to=author_id)
    dl.create(p1)

    cm_participant = CaseParticipant(
        id_=f"{case_id}/participants/cm",
        attributed_to=case_actor_id,
        context=case_id,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    dl.create(cm_participant)
    case.case_participants.append(cm_participant.id_)
    case.actor_participant_index[case_actor_id] = cm_participant.id_
    dl.save(case)

    embargo = EmbargoEvent(
        id_=f"{case_id}/embargo_events/e1",
        content="Routing test embargo",
        context=case_id,
    )
    dl.create(embargo)

    return dl, case_actor, case, embargo


def _ledger_event_types(dl: SqliteDataLayer) -> list[str]:
    return [
        getattr(e, "event_type", "")
        for e in dl.list_objects("CaseLedgerEntry")
    ]


# ---------------------------------------------------------------------------
# Tests: InviteToEmbargoOnCaseReceivedUseCase
# ---------------------------------------------------------------------------


class TestInviteToEmbargoRoutingGuard:
    """Pre-flight guard for InviteToEmbargoOnCaseReceivedUseCase."""

    AUTHOR_ID = "https://example.org/actors/coord-invite"
    CASE_ID = "https://example.org/cases/c-invite-em"
    CASE_ACTOR_ID = f"{CASE_ID}/actor"
    INVITEE_ID = "https://example.org/actors/invitee-em"

    def _setup(self):
        return _make_embargo_case(
            self.CASE_ID, self.AUTHOR_ID, self.CASE_ACTOR_ID
        )

    def test_caseactor_commits_invite_to_embargo_ledger_entry(
        self, make_payload
    ):
        """Guarded commit fires when receiving_actor_id == case_actor_id.

        Per CLP-10-002: the CaseActor MUST commit a canonical ledger entry.
        """
        dl, case_actor, case, embargo = self._setup()

        proposal = em_propose_embargo_activity(
            embargo,
            context=self.CASE_ID,
            actor=self.AUTHOR_ID,
            id_=f"{self.CASE_ID}/proposals/1",
        )
        dl.create(proposal)

        event = make_payload(proposal, receiving_actor_id=self.CASE_ACTOR_ID)
        InviteToEmbargoOnCaseReceivedUseCase(
            dl, event, sync_port=SyncActivityAdapter(dl)
        ).execute()

        event_types = _ledger_event_types(dl)
        assert "invite_to_embargo_on_case" in event_types, (
            "Expected CaseLedgerEntry with event_type='invite_to_embargo_on_case';"
            f" found: {event_types}"
        )

    def test_non_caseactor_does_not_commit_invite_ledger_entry(
        self, make_payload
    ):
        """Guarded commit does NOT fire when receiving_actor_id != case_actor_id.

        Per CLP-10-003: the invitee (non-CaseActor) must skip the commit.
        """
        dl, case_actor, case, embargo = self._setup()

        proposal = em_propose_embargo_activity(
            embargo,
            context=self.CASE_ID,
            actor=self.AUTHOR_ID,
            id_=f"{self.CASE_ID}/proposals/1",
        )
        dl.create(proposal)

        event = make_payload(proposal, receiving_actor_id=self.INVITEE_ID)
        InviteToEmbargoOnCaseReceivedUseCase(
            dl, event, sync_port=SyncActivityAdapter(dl)
        ).execute()

        event_types = _ledger_event_types(dl)
        assert "invite_to_embargo_on_case" not in event_types, (
            "Non-CaseActor (invitee) must NOT write an invite_to_embargo_on_case"
            f" ledger entry; found: {event_types}"
        )


# ---------------------------------------------------------------------------
# Tests: AcceptInviteToEmbargoOnCaseReceivedUseCase
# ---------------------------------------------------------------------------


class TestAcceptInviteToEmbargoRoutingGuard:
    """Pre-flight guard for AcceptInviteToEmbargoOnCaseReceivedUseCase."""

    COORD_ID = "https://example.org/actors/coord-accept"
    CASE_ID = "https://example.org/cases/c-accept-em"
    CASE_ACTOR_ID = f"{CASE_ID}/actor"

    def _setup(self):
        dl, case_actor, case, embargo = _make_embargo_case(
            self.CASE_ID, self.COORD_ID, self.CASE_ACTOR_ID
        )
        case = cast(VulnerabilityCase, dl.read(case.id_))
        assert case is not None
        case.current_status.em_state = EM.PROPOSED
        dl.save(case)

        proposal = em_propose_embargo_activity(
            embargo,
            context=case,
            actor=self.COORD_ID,
            id_=f"{self.CASE_ID}/proposals/1",
        )
        dl.create(proposal)

        accept = em_accept_embargo_activity(
            proposal,
            context=case,
            actor=self.COORD_ID,
        )

        return dl, case_actor, case, accept

    def test_caseactor_commits_accept_invite_ledger_entry(self, make_payload):
        """Guarded commit fires when receiving_actor_id == case_actor_id.

        Per CLP-10-002: the CaseActor MUST commit a canonical ledger entry.
        """
        dl, case_actor, case, accept = self._setup()

        event = make_payload(accept, receiving_actor_id=self.CASE_ACTOR_ID)
        AcceptInviteToEmbargoOnCaseReceivedUseCase(
            dl, event, sync_port=SyncActivityAdapter(dl)
        ).execute()

        event_types = _ledger_event_types(dl)
        assert "accept_invite_to_embargo_on_case" in event_types, (
            "Expected CaseLedgerEntry with"
            " event_type='accept_invite_to_embargo_on_case';"
            f" found: {event_types}"
        )

    def test_non_caseactor_does_not_commit_accept_invite_ledger_entry(
        self, make_payload
    ):
        """Guarded commit does NOT fire when receiving_actor_id != case_actor_id.

        Per CLP-10-003: non-CaseActor receiving actors must skip the commit.
        """
        dl, case_actor, case, accept = self._setup()

        non_case_actor_id = "https://example.org/actors/other-vendor"
        event = make_payload(accept, receiving_actor_id=non_case_actor_id)
        AcceptInviteToEmbargoOnCaseReceivedUseCase(
            dl, event, sync_port=SyncActivityAdapter(dl)
        ).execute()

        event_types = _ledger_event_types(dl)
        assert "accept_invite_to_embargo_on_case" not in event_types, (
            "Non-CaseActor must NOT write an accept_invite_to_embargo_on_case"
            f" ledger entry; found: {event_types}"
        )
