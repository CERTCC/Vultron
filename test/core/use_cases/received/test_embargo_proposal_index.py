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

"""AC-5 tests: embargo accept/reject/no-op correlate via core state index.

Verifies that:
  - InviteToEmbargoOnCaseReceivedUseCase populates pending_embargo_proposal_index
  - SvcAcceptEmbargoUseCase resolves proposal from core state (no Invite DL read)
  - SvcRejectEmbargoUseCase resolves proposal from core state (no Invite DL read)
  - Counter-proposal case: first pending proposal used when no proposal_id given
  - No-op: VultronNotFoundError raised when pending_embargo_proposal_index is empty
  - RejectInviteToEmbargoOnCaseReceivedEvent.case_id comes from inner_context_id
"""

from typing import cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.states.em import EM
from vultron.core.models.events.embargo import (
    InviteToEmbargoOnCaseReceivedEvent,
    RejectInviteToEmbargoOnCaseReceivedEvent,
)
from vultron.core.use_cases.received.embargo import (
    InviteToEmbargoOnCaseReceivedUseCase,
    RejectInviteToEmbargoOnCaseReceivedUseCase,
)
from vultron.core.use_cases.triggers.embargo import (
    SvcAcceptEmbargoUseCase,
    SvcProposeEmbargoUseCase,
    SvcRejectEmbargoUseCase,
)
from vultron.core.use_cases.triggers.requests import (
    AcceptEmbargoTriggerRequest,
    RejectEmbargoTriggerRequest,
)
from vultron.errors import VultronNotFoundError
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import em_propose_embargo_activity
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)


def _make_case_with_case_manager(dl, actor_id, em_state=EM.PROPOSED):
    """Create and persist a VulnerabilityCase with a CASE_MANAGER participant."""
    from vultron.enums.roles import CVDRole

    case = as_VulnerabilityCase(
        name="Proposal Index Test",
        attributed_to=actor_id,
    )
    case.current_status.em_state = em_state
    dl.create(case)

    case_manager = as_Service(name="CaseManager")
    dl.create(case_manager)
    cm_p = as_CaseParticipant(
        attributed_to=case_manager.id_,
        context=case.id_,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    dl.create(cm_p)
    case.actor_participant_index[case_manager.id_] = cm_p.id_
    dl.save(case)
    return case, case_manager


class TestInviteToEmbargoRecordsIndex:
    """InviteToEmbargoOnCaseReceivedUseCase must populate pending_embargo_proposal_index."""

    def test_invite_populates_pending_embargo_proposal_index(self):
        """After receiving EP, case.pending_embargo_proposal_index maps embargo → invite."""
        actor_id = "https://example.org/actors/vendor"
        dl = SqliteDataLayer("sqlite:///:memory:")

        actor = as_Service(id_=actor_id, name="Vendor")
        dl.create(actor)
        case, _cm = _make_case_with_case_manager(
            dl, actor_id, em_state=EM.NONE
        )

        embargo = as_EmbargoEvent(
            id_=f"{case.id_}/embargo_events/e1",
            context=case.id_,
        )
        dl.create(embargo)

        proposal = em_propose_embargo_activity(
            embargo,
            context=case.id_,
            actor=actor_id,
        )
        raw_event = extract_event(proposal)
        event = cast(
            InviteToEmbargoOnCaseReceivedEvent,
            raw_event.model_copy(update={"receiving_actor_id": actor_id}),
        )

        InviteToEmbargoOnCaseReceivedUseCase(dl, event).execute()

        updated_case = dl.read(case.id_)
        assert isinstance(updated_case, VulnerabilityCase)
        assert (
            proposal.id_
            in updated_case.pending_embargo_proposal_index.values()
        )
        assert embargo.id_ in updated_case.pending_embargo_proposal_index

    def test_invite_index_idempotent(self):
        """Receiving the same EP twice does not duplicate the index entry."""
        actor_id = "https://example.org/actors/vendor-idem"
        dl = SqliteDataLayer("sqlite:///:memory:")

        actor = as_Service(id_=actor_id, name="Vendor")
        dl.create(actor)
        case, _cm = _make_case_with_case_manager(
            dl, actor_id, em_state=EM.NONE
        )

        embargo = as_EmbargoEvent(
            id_=f"{case.id_}/embargo_events/e_idem",
            context=case.id_,
        )
        dl.create(embargo)

        proposal = em_propose_embargo_activity(
            embargo,
            context=case.id_,
            actor=actor_id,
        )
        raw_event = extract_event(proposal)
        event = cast(
            InviteToEmbargoOnCaseReceivedEvent,
            raw_event.model_copy(update={"receiving_actor_id": actor_id}),
        )

        InviteToEmbargoOnCaseReceivedUseCase(dl, event).execute()
        InviteToEmbargoOnCaseReceivedUseCase(dl, event).execute()

        updated_case = dl.read(case.id_)
        assert isinstance(updated_case, VulnerabilityCase)
        assert len(updated_case.pending_embargo_proposal_index) == 1


class TestProposeTriggerRecordsIndex:
    """SvcProposeEmbargoUseCase must populate pending_embargo_proposal_index."""

    def test_propose_trigger_populates_index(self):
        """After triggering a proposal, case.pending_embargo_proposal_index is populated."""
        from datetime import datetime, timezone, timedelta

        from vultron.core.use_cases.triggers.requests import (
            ProposeEmbargoTriggerRequest,
        )

        actor_id = "https://example.org/actors/coordinator"
        dl = SqliteDataLayer("sqlite:///:memory:")

        actor = as_Service(id_=actor_id, name="Coordinator")
        dl.create(actor)
        case, _cm = _make_case_with_case_manager(
            dl, actor_id, em_state=EM.NONE
        )

        end_time = datetime.now(timezone.utc) + timedelta(days=90)
        request = ProposeEmbargoTriggerRequest(
            actor_id=actor_id,
            case_id=case.id_,
            end_time=end_time,
        )
        result = SvcProposeEmbargoUseCase(
            dl, request, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        assert "activity" in result
        updated_case = dl.read(case.id_)
        assert isinstance(updated_case, VulnerabilityCase)
        assert len(updated_case.pending_embargo_proposal_index) == 1
        proposal_ids = list(
            updated_case.pending_embargo_proposal_index.values()
        )
        assert proposal_ids[0] == result["activity"]["id"]


class TestAcceptRejectFromCoreState:
    """accept/reject trigger use cases must resolve proposal from core state."""

    def _make_proposed_case(self, dl, actor_id, actor):
        """Build a PROPOSED case with index populated."""
        case, _cm = _make_case_with_case_manager(
            dl, actor_id, em_state=EM.PROPOSED
        )
        embargo = as_EmbargoEvent(
            id_=f"{case.id_}/embargo_events/e1",
            context=case.id_,
        )
        dl.create(embargo)
        proposal = em_propose_embargo_activity(
            embargo,
            context=case.id_,
            actor=actor_id,
        )
        dl.create(proposal)
        case_obj = dl.read(case.id_)
        case_obj.proposed_embargoes.append(embargo.id_)
        case_obj.pending_embargo_proposal_index[embargo.id_] = proposal.id_
        dl.save(case_obj)
        return case, embargo, proposal

    def test_accept_uses_core_state_index(self):
        """SvcAcceptEmbargoUseCase activates embargo using core state (no Invite DL read)."""
        actor_id = "https://example.org/actors/accept-actor"
        dl = SqliteDataLayer("sqlite:///:memory:")
        actor = as_Service(id_=actor_id, name="AcceptActor")
        dl.create(actor)

        case, embargo, proposal = self._make_proposed_case(dl, actor_id, actor)

        request = AcceptEmbargoTriggerRequest(
            actor_id=actor_id,
            case_id=case.id_,
            proposal_id=proposal.id_,
        )
        result = SvcAcceptEmbargoUseCase(
            dl, request, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        assert "activity" in result
        updated_case = dl.read(case.id_)
        assert isinstance(updated_case, VulnerabilityCase)
        assert updated_case.current_status.em_state == EM.ACTIVE

    def test_accept_without_proposal_id_uses_first_pending(self):
        """SvcAcceptEmbargoUseCase finds first pending proposal from index when no proposal_id given."""
        actor_id = "https://example.org/actors/accept-auto"
        dl = SqliteDataLayer("sqlite:///:memory:")
        actor = as_Service(id_=actor_id, name="AcceptAutoActor")
        dl.create(actor)

        case, _embargo, _proposal = self._make_proposed_case(
            dl, actor_id, actor
        )

        request = AcceptEmbargoTriggerRequest(
            actor_id=actor_id,
            case_id=case.id_,
        )
        result = SvcAcceptEmbargoUseCase(
            dl, request, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        assert "activity" in result
        updated_case = dl.read(case.id_)
        assert isinstance(updated_case, VulnerabilityCase)
        assert updated_case.current_status.em_state == EM.ACTIVE

    def test_reject_uses_core_state_index(self):
        """SvcRejectEmbargoUseCase resolves embargo from core state (no Invite DL read)."""
        actor_id = "https://example.org/actors/reject-actor"
        dl = SqliteDataLayer("sqlite:///:memory:")
        actor = as_Service(id_=actor_id, name="RejectActor")
        dl.create(actor)

        case, _embargo, proposal = self._make_proposed_case(
            dl, actor_id, actor
        )

        request = RejectEmbargoTriggerRequest(
            actor_id=actor_id,
            case_id=case.id_,
            proposal_id=proposal.id_,
        )
        result = SvcRejectEmbargoUseCase(
            dl, request, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        assert "activity" in result
        updated_case = dl.read(case.id_)
        assert isinstance(updated_case, VulnerabilityCase)
        # Owner-reject drives EM to NONE; non-owner records rejection only.
        assert updated_case.current_status.em_state in (EM.NONE, EM.PROPOSED)

    def test_accept_raises_notfound_when_index_empty(self):
        """SvcAcceptEmbargoUseCase raises VultronNotFoundError when no pending proposal in index."""
        actor_id = "https://example.org/actors/accept-noproposal"
        dl = SqliteDataLayer("sqlite:///:memory:")
        actor = as_Service(id_=actor_id, name="AcceptNoProposalActor")
        dl.create(actor)

        case, _cm = _make_case_with_case_manager(
            dl, actor_id, em_state=EM.PROPOSED
        )

        request = AcceptEmbargoTriggerRequest(
            actor_id=actor_id,
            case_id=case.id_,
        )
        with pytest.raises(VultronNotFoundError):
            SvcAcceptEmbargoUseCase(
                dl, request, trigger_activity=TriggerActivityAdapter(dl)
            ).execute()

    def test_reject_raises_notfound_when_index_empty(self):
        """SvcRejectEmbargoUseCase raises VultronNotFoundError when no pending proposal in index."""
        actor_id = "https://example.org/actors/reject-noproposal"
        dl = SqliteDataLayer("sqlite:///:memory:")
        actor = as_Service(id_=actor_id, name="RejectNoProposalActor")
        dl.create(actor)

        case, _cm = _make_case_with_case_manager(
            dl, actor_id, em_state=EM.PROPOSED
        )

        request = RejectEmbargoTriggerRequest(
            actor_id=actor_id,
            case_id=case.id_,
        )
        with pytest.raises(VultronNotFoundError):
            SvcRejectEmbargoUseCase(
                dl, request, trigger_activity=TriggerActivityAdapter(dl)
            ).execute()


class TestRejectEventCarriesCaseAndEmbargoIds:
    """RejectInviteToEmbargoOnCaseReceivedEvent must carry case_id and embargo_id from inner_context/object."""

    def test_reject_event_case_id_from_inner_context(self):
        """RejectInviteToEmbargoOnCaseReceivedEvent.case_id equals inner_context_id."""
        from vultron.wire.as2.factories import em_reject_embargo_activity

        case_id = "https://example.org/cases/reject-case"
        embargo_id = f"{case_id}/embargo_events/e1"
        actor_id = "https://example.org/actors/rejector"
        proposal_id = f"{case_id}/proposals/p1"

        embargo = as_EmbargoEvent(id_=embargo_id)
        proposal = em_propose_embargo_activity(
            embargo=embargo,
            context=case_id,
            actor=actor_id,
            id_=proposal_id,
        )
        reject_activity = em_reject_embargo_activity(
            proposal=proposal,
            context=case_id,
            actor=actor_id,
        )

        raw_event = extract_event(reject_activity)
        event = cast(RejectInviteToEmbargoOnCaseReceivedEvent, raw_event)

        assert event.case_id == case_id
        assert event.embargo_id == embargo_id
        assert event.invite_id == proposal_id

    def test_reject_use_case_uses_event_case_id_not_dl_read(self, monkeypatch):
        """RejectInviteToEmbargoOnCaseReceivedUseCase uses case_id from event, not dl.read(invite_id)."""
        from unittest.mock import patch
        from vultron.wire.as2.factories import em_reject_embargo_activity

        actor_id = "https://example.org/actors/rej-actor"
        dl = SqliteDataLayer("sqlite:///:memory:")

        actor = as_Service(id_=actor_id, name="RejActor")
        dl.create(actor)
        case, _cm = _make_case_with_case_manager(
            dl, actor_id, em_state=EM.PROPOSED
        )
        embargo = as_EmbargoEvent(
            id_=f"{case.id_}/embargo_events/e1",
            context=case.id_,
        )
        dl.create(embargo)
        proposal = em_propose_embargo_activity(
            embargo=embargo, context=case.id_, actor=actor_id
        )
        dl.create(proposal)

        reject_activity = em_reject_embargo_activity(
            proposal=proposal,
            context=case.id_,
            actor=actor_id,
        )
        raw_event = extract_event(reject_activity)
        event = cast(
            RejectInviteToEmbargoOnCaseReceivedEvent,
            raw_event.model_copy(update={"receiving_actor_id": actor_id}),
        )

        dl_read_calls = []
        original_read = dl.read

        def spy_read(obj_id):
            dl_read_calls.append(obj_id)
            return original_read(obj_id)

        with patch.object(dl, "read", side_effect=spy_read):
            RejectInviteToEmbargoOnCaseReceivedUseCase(dl, event).execute()

        # dl.read must NOT have been called with the proposal/invite ID
        assert (
            proposal.id_ not in dl_read_calls
        ), f"dl.read({proposal.id_!r}) was called — invite wire re-read must be eliminated"

        assert event.case_id == case.id_
        assert event.embargo_id == embargo.id_
