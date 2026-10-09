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

from test.support.embargo_register import activate, propose
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_actor import CaseActor
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.use_cases.received.embargo import (
    AcceptInviteToEmbargoOnCaseReceivedUseCase,
    InviteToEmbargoOnCaseReceivedUseCase,
    RemoveEmbargoEventFromCaseReceivedUseCase,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import (
    em_accept_embargo_activity,
    em_propose_embargo_activity,
    remove_embargo_from_case_activity,
)
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_embargo_case(
    case_id: str,
    author_id: str,
    case_actor_id: str,
) -> tuple[SqliteDataLayer, CaseActor, as_VulnerabilityCase, as_EmbargoEvent]:
    """Return (dl, case_actor, case, embargo) ready for routing tests."""
    # The case actor holds the canonical ledger these routing tests assert on,
    # and it is the receiving actor for the on-path cases, so this is its store.
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=case_actor_id)

    case_actor = CaseActor(
        id_=case_actor_id,
        name=f"CaseActor for {case_id}",
        attributed_to=author_id,
        context=case_id,
    )
    dl.create(case_actor)

    case = as_VulnerabilityCase(
        id_=case_id,
        name="Embargo Routing Test",
        attributed_to=author_id,
    )
    p1_id = f"{case_id}/participants/p1"
    case.actor_participant_index[author_id] = p1_id
    # The author owns the case, so it may terminate the embargo (ADR-0115).
    p1 = as_CaseParticipant(
        id_=p1_id,
        context=case_id,
        attributed_to=author_id,
        case_roles=[CVDRole.CASE_OWNER],
    )
    dl.create(p1)

    cm_participant = as_CaseParticipant(
        id_=f"{case_id}/participants/cm",
        attributed_to=case_actor_id,
        context=case_id,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    dl.create(cm_participant)
    case.case_participants.append(cm_participant.id_)
    case.actor_participant_index[case_actor_id] = cm_participant.id_
    dl.save(case)

    embargo = as_EmbargoEvent(
        id_=f"{case_id}/embargo_events/e1",
        content="Routing test embargo",
        context=case_id,
        end_time=days_from_now_utc(45),
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

    def test_absent_stamp_uses_store_owner_invite_to_embargo(
        self, make_payload
    ):
        """When receiving_actor_id is absent the store owner processes the invite.

        Absent-stamp path (CLP-10-005): resolve_receiving_actor_id falls back to
        dl.actor_id (CASE_ACTOR_ID), so the guarded commit fires and the
        ``invite_to_embargo_on_case`` ledger entry IS written.
        """
        dl, _case_actor, _case, embargo = self._setup()

        proposal = em_propose_embargo_activity(
            embargo,
            context=self.CASE_ID,
            actor=self.AUTHOR_ID,
            to=[self.CASE_ACTOR_ID],
            id_=f"{self.CASE_ID}/proposals/nostamp",
        )
        dl.create(proposal)

        event = make_payload(proposal, receiving_actor_id=None)
        InviteToEmbargoOnCaseReceivedUseCase(
            dl,
            event,
            sync_port=SyncActivityAdapter(dl),
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        event_types = _ledger_event_types(dl)
        assert "invite_to_embargo_on_case" in event_types, (
            "Store-owner fallback (CaseActor) MUST write an"
            " invite_to_embargo_on_case ledger entry when receiving_actor_id"
            f" is absent; found: {event_types}"
        )

    def test_caseactor_commits_invite_to_embargo_ledger_entry(
        self, make_payload
    ):
        """Guarded commit fires when receiving_actor_id == case_actor_id.

        Per CLP-10-002: the CaseActor MUST commit a canonical ledger entry.
        """
        dl, _case_actor, _case, embargo = self._setup()

        proposal = em_propose_embargo_activity(
            embargo,
            context=self.CASE_ID,
            actor=self.AUTHOR_ID,
            to=[self.CASE_ACTOR_ID],
            id_=f"{self.CASE_ID}/proposals/1",
        )
        dl.create(proposal)

        event = make_payload(proposal, receiving_actor_id=self.CASE_ACTOR_ID)
        InviteToEmbargoOnCaseReceivedUseCase(
            dl,
            event,
            sync_port=SyncActivityAdapter(dl),
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
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
        dl, _case_actor, _case, embargo = self._setup()

        # The invitee's replica takes the Invite from the CASE_MANAGER, which
        # relays the author's proposal (ADR-0115).
        proposal = em_propose_embargo_activity(
            embargo,
            context=self.CASE_ID,
            actor=self.CASE_ACTOR_ID,
            attributed_to=self.AUTHOR_ID,
            to=[self.INVITEE_ID],
            id_=f"{self.CASE_ID}/proposals/1",
        )
        # The invitee holds its own replica of the case.
        replica = SqliteDataLayer(
            "sqlite:///:memory:", actor_id=self.INVITEE_ID
        )
        for obj_id in [
            _case.id_,
            embargo.id_,
            *(str(p) for p in _case.case_participants),
            *(str(p) for p in _case.actor_participant_index.values()),
        ]:
            obj = dl.read(obj_id)
            if obj is not None and replica.read(obj_id) is None:
                replica.create(obj)
        dl = replica
        dl.create(proposal)

        event = make_payload(proposal, receiving_actor_id=self.INVITEE_ID)
        result = InviteToEmbargoOnCaseReceivedUseCase(
            dl,
            event,
            sync_port=SyncActivityAdapter(dl),
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        assert result.disposition is not HandlerDisposition.REFUSED, (
            "the Invite must reach the tree, so the absent entry is the"
            f" guard's doing: {result.reason}"
        )
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
        propose(case, embargo.id_)
        dl.save(case)

        # The CASE_MANAGER relayed the Invite to the coordinator, who answers.
        proposal = em_propose_embargo_activity(
            embargo,
            context=case.id_,
            actor=self.CASE_ACTOR_ID,
            to=[self.COORD_ID],
            id_=f"{self.CASE_ID}/proposals/1",
        )
        dl.create(proposal)

        # Addressed to the CaseActor with a copy to the non-CaseActor, so
        # both pass the door check (HP-01-005) and the role gate decides.
        accept = em_accept_embargo_activity(
            proposal,
            context=case.id_,
            actor=self.COORD_ID,
            to=[self.CASE_ACTOR_ID],
            cc=["https://example.org/actors/other-vendor"],
        )

        return dl, case_actor, case, accept

    def test_caseactor_commits_accept_invite_ledger_entry(self, make_payload):
        """Guarded commit fires when receiving_actor_id == case_actor_id.

        Per CLP-10-002: the CaseActor MUST commit a canonical ledger entry.
        """
        dl, _case_actor, _case, accept = self._setup()

        event = make_payload(accept, receiving_actor_id=self.CASE_ACTOR_ID)
        AcceptInviteToEmbargoOnCaseReceivedUseCase(
            dl,
            event,
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
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
        dl, _case_actor, _case, accept = self._setup()

        non_case_actor_id = "https://example.org/actors/other-vendor"
        event = make_payload(accept, receiving_actor_id=non_case_actor_id)
        AcceptInviteToEmbargoOnCaseReceivedUseCase(
            dl,
            event,
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        event_types = _ledger_event_types(dl)
        assert "accept_invite_to_embargo_on_case" not in event_types, (
            "Non-CaseActor must NOT write an accept_invite_to_embargo_on_case"
            f" ledger entry; found: {event_types}"
        )

    def test_absent_stamp_uses_store_owner_accept_invite_to_embargo(
        self, make_payload
    ):
        """When receiving_actor_id is absent the store owner processes the accept.

        Absent-stamp path (CLP-10-005): resolve_receiving_actor_id falls back to
        dl.actor_id (CASE_ACTOR_ID), so the guarded commit fires and the
        ``accept_invite_to_embargo_on_case`` ledger entry IS written.
        """
        dl, _case_actor, _case, accept = self._setup()

        event = make_payload(accept, receiving_actor_id=None)
        AcceptInviteToEmbargoOnCaseReceivedUseCase(
            dl,
            event,
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        event_types = _ledger_event_types(dl)
        assert "accept_invite_to_embargo_on_case" in event_types, (
            "Store-owner fallback (CaseActor) MUST write an"
            " accept_invite_to_embargo_on_case ledger entry when"
            f" receiving_actor_id is absent; found: {event_types}"
        )


# ---------------------------------------------------------------------------
# Tests: RemoveEmbargoEventFromCaseReceivedUseCase
# ---------------------------------------------------------------------------


class TestRemoveEmbargoRoutingGuard:
    """Pre-flight guard for RemoveEmbargoEventFromCaseReceivedUseCase.

    The guarded commit is embedded in ``remove_embargo_from_case_tree`` and
    runs via the single ``execute_with_setup`` call with
    ``actor_id=receiving_actor_id``.  ``CheckIsCaseManagerNode`` inside the
    tree fires only when that actor holds ``CVDRole.CASE_MANAGER``.
    """

    AUTHOR_ID = "https://example.org/actors/coord-remove"
    CASE_ID = "https://example.org/cases/c-remove-em"
    CASE_ACTOR_ID = f"{CASE_ID}/actor"
    OTHER_ACTOR_ID = "https://example.org/actors/vendor-remove"

    def _setup(
        self,
    ) -> tuple[
        SqliteDataLayer,
        CaseActor,
        as_VulnerabilityCase,
        as_EmbargoEvent,
    ]:
        dl, case_actor, case, embargo = _make_embargo_case(
            self.CASE_ID, self.AUTHOR_ID, self.CASE_ACTOR_ID
        )
        # Make the embargo the one in force: Remove ends the active embargo
        # (a Remove naming a merely-proposed one changes nothing, ADR-0122).
        read_case = dl.read(case.id_)
        assert read_case is not None
        case = cast(as_VulnerabilityCase, read_case)
        activate(case, embargo.id_)
        dl.save(case)
        return dl, case_actor, case, embargo

    def test_caseactor_commits_remove_embargo_ledger_entry(self, make_payload):
        """Guarded commit fires when receiving_actor_id == case_actor_id.

        Per CLP-10-002: the CaseActor MUST commit a canonical ledger entry.
        """
        dl, _case_actor, _case, embargo = self._setup()

        remove_activity = remove_embargo_from_case_activity(
            embargo,
            origin=self.CASE_ID,
            actor=self.AUTHOR_ID,
            to=[self.CASE_ACTOR_ID],
            cc=[self.OTHER_ACTOR_ID],
        )

        event = make_payload(
            remove_activity, receiving_actor_id=self.CASE_ACTOR_ID
        )
        RemoveEmbargoEventFromCaseReceivedUseCase(
            dl,
            event,
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        event_types = _ledger_event_types(dl)
        assert "remove_embargo_event_from_case" in event_types, (
            "Expected CaseLedgerEntry with"
            " event_type='remove_embargo_event_from_case';"
            f" found: {event_types}"
        )

    def test_non_caseactor_does_not_commit_remove_embargo_ledger_entry(
        self, make_payload
    ):
        """Guarded commit does NOT fire when receiving_actor_id != case_actor_id.

        Per CLP-10-003: non-CaseActor receiving actors must skip the commit.
        """
        dl, _case_actor, _case, embargo = self._setup()

        remove_activity = remove_embargo_from_case_activity(
            embargo,
            origin=self.CASE_ID,
            actor=self.AUTHOR_ID,
            to=[self.CASE_ACTOR_ID],
            cc=[self.OTHER_ACTOR_ID],
        )

        event = make_payload(
            remove_activity, receiving_actor_id=self.OTHER_ACTOR_ID
        )
        RemoveEmbargoEventFromCaseReceivedUseCase(
            dl,
            event,
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        event_types = _ledger_event_types(dl)
        assert "remove_embargo_event_from_case" not in event_types, (
            "Non-CaseActor must NOT write a remove_embargo_event_from_case"
            f" ledger entry; found: {event_types}"
        )

    def test_absent_stamp_uses_store_owner_remove_embargo(self, make_payload):
        """When receiving_actor_id is absent the store owner processes the remove.

        Absent-stamp path (CLP-10-005): resolve_receiving_actor_id falls back to
        dl.actor_id (CASE_ACTOR_ID), so the guarded commit fires and the
        ``remove_embargo_event_from_case`` ledger entry IS written.
        """
        dl, _case_actor, _case, embargo = self._setup()

        remove_activity = remove_embargo_from_case_activity(
            embargo,
            origin=self.CASE_ID,
            actor=self.AUTHOR_ID,
            to=[self.CASE_ACTOR_ID],
            cc=[self.OTHER_ACTOR_ID],
        )

        event = make_payload(remove_activity, receiving_actor_id=None)
        RemoveEmbargoEventFromCaseReceivedUseCase(
            dl,
            event,
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        event_types = _ledger_event_types(dl)
        assert "remove_embargo_event_from_case" in event_types, (
            "Store-owner fallback (CaseActor) MUST write a"
            " remove_embargo_event_from_case ledger entry when"
            f" receiving_actor_id is absent; found: {event_types}"
        )
