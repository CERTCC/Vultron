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
"""Tests for embargo proposal, invitation, accept, and reject use cases."""

import logging
from typing import Any, cast
from unittest.mock import MagicMock

from vultron.adapters.driven.db_record import StorableRecord
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.states.em import EM
from vultron.core.use_cases.received.embargo import (
    AcceptInviteToEmbargoOnCaseReceivedUseCase,
    CreateEmbargoEventReceivedUseCase,
    InviteToEmbargoOnCaseReceivedUseCase,
    RejectInviteToEmbargoOnCaseReceivedUseCase,
)
from vultron.core.use_cases.triggers.embargo import SvcAcceptEmbargoUseCase
from vultron.core.use_cases.triggers.requests import (
    AcceptEmbargoTriggerRequest,
)
from vultron.errors import VultronInvalidStateTransitionError
from vultron.wire.as2.factories import (
    em_accept_embargo_activity,
    em_propose_embargo_activity,
    em_reject_embargo_activity,
)


class TestEmbargoProposalLifecycle:
    """Tests for embargo create, invite, accept, and reject use cases."""

    def test_create_embargo_event_stores_event(
        self, monkeypatch, make_payload
    ):
        """create_embargo_event persists the EmbargoEvent to the DataLayer."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.base.objects.activities.transitive import (
            as_Create,
        )
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")

        case = VulnerabilityCase(
            id_="https://example.org/cases/case_cem1",
            name="Create Embargo Test",
        )
        embargo = EmbargoEvent(
            id_="https://example.org/cases/case_cem1/embargo_events/embargo1",
            content="Proposed embargo",
        )
        activity = as_Create(
            actor="https://example.org/users/vendor",
            object_=embargo,
            context=case,
        )

        event = make_payload(activity)

        CreateEmbargoEventReceivedUseCase(dl, event).execute()

        stored = dl.get(embargo.type_, embargo.id_)
        assert stored is not None

    def test_create_embargo_event_idempotent(self, monkeypatch, make_payload):
        """create_embargo_event skips storing a duplicate EmbargoEvent."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.base.objects.activities.transitive import (
            as_Create,
        )
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")

        case = VulnerabilityCase(
            id_="https://example.org/cases/case_cem2",
            name="Create Embargo Idempotent",
        )
        embargo = EmbargoEvent(
            id_="https://example.org/cases/case_cem2/embargo_events/embargo2",
            content="Proposed embargo",
        )
        activity = as_Create(
            actor="https://example.org/users/vendor",
            object_=embargo,
            context=case,
        )
        event = make_payload(activity)

        CreateEmbargoEventReceivedUseCase(dl, event).execute()
        CreateEmbargoEventReceivedUseCase(
            dl, event
        ).execute()  # second call no-op

        stored = dl.get(embargo.type_, embargo.id_)
        assert stored is not None

    def test_invite_to_embargo_on_case_stores_proposal(
        self, monkeypatch, make_payload
    ):
        """invite_to_embargo_on_case persists the EmProposeEmbargoActivity activity."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent

        dl = SqliteDataLayer("sqlite:///:memory:")

        embargo = EmbargoEvent(
            id_="https://example.org/cases/case_em2/embargo_events/e2",
            content="Proposed embargo",
        )
        proposal = em_propose_embargo_activity(
            embargo,
            context="https://example.org/cases/case_em2",
            actor="https://example.org/users/vendor",
            id_="https://example.org/cases/case_em2/embargo_proposals/1",
        )

        event = make_payload(
            proposal, receiving_actor_id="https://example.org/users/vendor"
        )

        InviteToEmbargoOnCaseReceivedUseCase(dl, event).execute()

        stored = dl.get(proposal.type_.value, proposal.id_)
        assert stored is not None

    def test_accept_invite_to_embargo_on_case_activates_embargo(
        self, monkeypatch, make_payload
    ):
        """accept_invite_to_embargo_on_case activates the embargo on the case (PROPOSED → ACTIVE)."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        coordinator_id = "https://example.org/users/coordinator"
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_em3",
            name="EM Accept Test",
            attributed_to=coordinator_id,
        )
        embargo = EmbargoEvent(
            id_="https://example.org/cases/case_em3/embargo_events/e3",
            content="Embargo",
        )
        # Use inline objects (not string IDs) so rehydration skips DataLayer lookup
        proposal = em_propose_embargo_activity(
            embargo,
            context=case,
            actor="https://example.org/users/vendor",
            id_="https://example.org/cases/case_em3/embargo_proposals/1",
        )
        # Start from PROPOSED — the standard pre-condition for activation.
        case.current_status.em_state = EM.PROPOSED
        dl.create(case)
        dl.create(embargo)
        dl.create(proposal)

        accept = em_accept_embargo_activity(
            proposal,
            context=case,
            actor=coordinator_id,
        )
        event = make_payload(accept, receiving_actor_id=coordinator_id)

        AcceptInviteToEmbargoOnCaseReceivedUseCase(dl, event).execute()

        case = dl.read(case.id_)
        assert case is not None
        case = cast(VulnerabilityCase, case)
        assert case.active_embargo is not None
        assert case.current_status.em_state == EM.ACTIVE

    def test_accept_invite_to_embargo_warns_on_non_standard_transition(
        self, monkeypatch, make_payload, caplog
    ):
        """accept_invite_to_embargo_on_case ledgers WARNING when EM state is not on the standard machine path."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        coordinator_id = "https://example.org/users/coordinator"
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_em3_warn",
            name="EM Accept Warn Test",
            attributed_to=coordinator_id,
        )
        embargo = EmbargoEvent(
            id_="https://example.org/cases/case_em3_warn/embargo_events/e3",
            content="Embargo",
        )
        proposal = em_propose_embargo_activity(
            embargo,
            context=case,
            actor="https://example.org/users/vendor",
            id_="https://example.org/cases/case_em3_warn/embargo_proposals/1",
        )
        # Default em_state is NONE — not a valid predecessor for ACTIVE.
        dl.create(case)
        dl.create(embargo)
        dl.create(proposal)

        accept = em_accept_embargo_activity(
            proposal,
            context=case,
            actor=coordinator_id,
        )
        event = make_payload(accept, receiving_actor_id=coordinator_id)

        with caplog.at_level(logging.WARNING):
            AcceptInviteToEmbargoOnCaseReceivedUseCase(dl, event).execute()

        assert any("state-sync override" in r.message for r in caplog.records)
        case = dl.read(case.id_)
        assert case is not None
        case = cast(VulnerabilityCase, case)
        assert case.current_status.em_state == EM.ACTIVE

    def test_accept_invite_to_embargo_records_embargo_on_participant(
        self, monkeypatch, make_payload
    ):
        """accept_invite_to_embargo_on_case records embargo ID in participant.accepted_embargo_ids (CM-10-002, CM-10-003)."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.objects.case_participant import (
            CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        coordinator_id = "https://example.org/users/coordinator"
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_em5",
            name="EM Accept Participant Test",
        )
        embargo = EmbargoEvent(
            id_="https://example.org/cases/case_em5/embargo_events/e5",
            content="Embargo",
        )
        participant = CaseParticipant(
            id_="https://example.org/cases/case_em5/participants/coord",
            attributed_to=coordinator_id,
            context=case.id_,
        )
        case.add_participant(participant)
        proposal = em_propose_embargo_activity(
            embargo,
            context=case,
            actor="https://example.org/users/vendor",
            id_="https://example.org/cases/case_em5/embargo_proposals/1",
        )
        dl.create(case)
        dl.create(embargo)
        dl.create(participant)
        dl.create(proposal)

        accept = em_accept_embargo_activity(
            proposal,
            context=case,
            actor=coordinator_id,
        )
        event = make_payload(accept, receiving_actor_id=coordinator_id)

        AcceptInviteToEmbargoOnCaseReceivedUseCase(dl, event).execute()

        updated_participant = dl.get(id_=participant.id_)
        assert updated_participant is not None
        updated_participant = cast(Any, updated_participant)
        assert embargo.id_ in updated_participant.accepted_embargo_ids

    def test_accept_invite_to_embargo_records_case_event(
        self, monkeypatch, make_payload
    ):
        """accept_invite_to_embargo_on_case transitions EM state to ACTIVE
        and persists the case (CM-02-009).

        record_event('embargo_accepted') was removed in #789; the behavioral
        invariant is verified by checking case.active_embargo is not None
        after acceptance.
        """
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        coordinator_id = "https://example.org/users/coordinator"
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_em6",
            name="EM Accept Event Test",
            attributed_to=coordinator_id,
        )
        embargo = EmbargoEvent(
            id_="https://example.org/cases/case_em6/embargo_events/e6",
            content="Embargo",
        )
        proposal = em_propose_embargo_activity(
            embargo,
            context=case,
            actor="https://example.org/users/vendor",
            id_="https://example.org/cases/case_em6/embargo_proposals/1",
        )
        dl.create(case)
        dl.create(embargo)
        dl.create(proposal)

        accept = em_accept_embargo_activity(
            proposal,
            context=case,
            actor=coordinator_id,
        )
        event = make_payload(accept, receiving_actor_id=coordinator_id)

        AcceptInviteToEmbargoOnCaseReceivedUseCase(dl, event).execute()

        case = dl.read(case.id_)
        assert case is not None
        case = cast(VulnerabilityCase, case)
        assert (
            case.active_embargo is not None
        ), "Expected active_embargo to be set after embargo acceptance"

    def test_reject_invite_to_embargo_on_case_ledgers_rejection(
        self, make_payload
    ):
        """reject_invite_to_embargo_on_case ledgers without raising."""
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent

        embargo = EmbargoEvent(
            id_="https://example.org/cases/case_em4/embargo_events/e4",
            content="Embargo",
        )
        proposal = em_propose_embargo_activity(
            embargo,
            context="https://example.org/cases/case_em4",
            actor="https://example.org/users/vendor",
            id_="https://example.org/cases/case_em4/embargo_proposals/1",
        )
        reject = em_reject_embargo_activity(
            proposal,
            context="https://example.org/cases/case_em4",
            actor="https://example.org/users/coordinator",
        )

        event = make_payload(reject)

        result = RejectInviteToEmbargoOnCaseReceivedUseCase(
            MagicMock(), event
        ).execute()
        assert result is None

    def test_evaluate_embargo_raises_invalid_state_transition_when_em_state_invalid(
        self,
    ):
        """SvcAcceptEmbargoUseCase raises VultronInvalidStateTransitionError when EM state does not allow ACCEPT."""
        import pytest
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )
        from vultron.wire.as2.vocab.base.objects.actors import (
            as_Actor as Actor,
            as_Service,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        actor = Actor(id_="https://example.org/users/vendor", name="Vendor")
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_eval_invalid",
            name="Evaluate Invalid EM State",
            attributed_to=actor.id_,
        )
        embargo = EmbargoEvent(
            id_="https://example.org/cases/case_eval_invalid/embargo_events/e1",
            context=case.id_,
        )
        proposal = em_propose_embargo_activity(
            embargo,
            context=case.id_,
            actor=actor.id_,
            id_="https://example.org/cases/case_eval_invalid/proposals/p1",
        )
        # EM state is NONE — ACCEPT transition is not valid from NONE.
        dl.create(
            StorableRecord(
                id_=actor.id_,
                type_="Actor",
                data_=actor.model_dump(exclude_none=True, by_alias=True),
            )
        )
        dl.create(case)
        dl.create(embargo)
        dl.create(proposal)

        # Add a Case Manager participant so routing proceeds to the
        # EM-state validation check (the test's actual assertion target).
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.objects.case_participant import (
            CaseParticipant as CP,
        )

        case_actor = as_Service(
            id_="https://example.org/actors/case-manager",
            name="Case Manager",
        )
        dl.create(case_actor)
        cm_p = CP(
            attributed_to=case_actor.id_,
            context=case.id_,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        dl.create(cm_p)
        case.actor_participant_index[case_actor.id_] = cm_p.id_
        dl.save(case)

        request = AcceptEmbargoTriggerRequest(
            actor_id=actor.id_,
            case_id=case.id_,
            proposal_id=proposal.id_,
        )
        with pytest.raises(VultronInvalidStateTransitionError):
            SvcAcceptEmbargoUseCase(
                dl, request, trigger_activity=TriggerActivityAdapter(dl)
            ).execute()
