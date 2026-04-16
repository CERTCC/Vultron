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
"""Tests for embargo-related use-case classes."""

import logging
from typing import Any, cast
from unittest.mock import MagicMock

from vultron.adapters.driven.db_record import StorableRecord
from vultron.core.states.em import EM
from vultron.core.use_cases.received.embargo import (
    CreateEmbargoEventReceivedUseCase,
    AddEmbargoEventToCaseReceivedUseCase,
    RemoveEmbargoEventFromCaseReceivedUseCase,
    InviteToEmbargoOnCaseReceivedUseCase,
    AcceptInviteToEmbargoOnCaseReceivedUseCase,
    RejectInviteToEmbargoOnCaseReceivedUseCase,
)
from vultron.core.use_cases.triggers.embargo import SvcEvaluateEmbargoUseCase
from vultron.core.use_cases.triggers.requests import (
    EvaluateEmbargoTriggerRequest,
)
from vultron.errors import VultronInvalidStateTransitionError


class TestEmbargoUseCases:
    """Tests for embargo management handlers."""

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

        stored = dl.get(embargo.type_.value, embargo.id_)
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

        stored = dl.get(embargo.type_.value, embargo.id_)
        assert stored is not None

    def test_add_embargo_event_to_case_activates_embargo(
        self, monkeypatch, make_payload
    ):
        """add_embargo_event_to_case sets the active embargo on the case (PROPOSED → ACTIVE)."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.activities.embargo import (
            AddEmbargoToCaseActivity,
        )
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )
        from vultron.core.states.em import EM

        dl = SqliteDataLayer("sqlite:///:memory:")
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_em1",
            name="EM Test Case",
        )
        embargo = EmbargoEvent(
            id_="https://example.org/cases/case_em1/embargo_events/e1",
            content="Embargo test",
        )
        # Start from PROPOSED — the standard pre-condition for activation.
        case.current_status.em_state = EM.PROPOSED
        dl.create(case)
        dl.create(embargo)

        activity = AddEmbargoToCaseActivity(
            actor="https://example.org/users/vendor",
            object_=embargo,
            target=case,
        )
        event = make_payload(activity)

        AddEmbargoEventToCaseReceivedUseCase(dl, event).execute()

        case = dl.read(case.id_)
        assert case is not None
        case = cast(VulnerabilityCase, case)
        assert case.active_embargo is not None
        assert case.current_status.em_state == EM.ACTIVE

    def test_add_embargo_event_to_case_warns_on_non_standard_transition(
        self, monkeypatch, make_payload, caplog
    ):
        """add_embargo_event_to_case logs WARNING when EM state is not on the standard machine path (state-sync override)."""
        import logging
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.activities.embargo import (
            AddEmbargoToCaseActivity,
        )
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )
        from vultron.core.states.em import EM

        dl = SqliteDataLayer("sqlite:///:memory:")
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_em1_warn",
            name="EM Warn Test Case",
        )
        embargo = EmbargoEvent(
            id_="https://example.org/cases/case_em1_warn/embargo_events/e1",
            content="Embargo test",
        )
        # Default em_state is NONE — not a valid predecessor for ACTIVE.
        dl.create(case)
        dl.create(embargo)

        activity = AddEmbargoToCaseActivity(
            actor="https://example.org/users/vendor",
            object_=embargo,
            target=case,
        )
        event = make_payload(activity)

        with caplog.at_level(logging.WARNING):
            AddEmbargoEventToCaseReceivedUseCase(dl, event).execute()

        assert any("state-sync override" in r.message for r in caplog.records)
        case = dl.read(case.id_)
        assert case is not None
        case = cast(VulnerabilityCase, case)
        # State is still updated (synchronization override proceeds).
        assert case.current_status.em_state == EM.ACTIVE

    def test_invite_to_embargo_on_case_stores_proposal(
        self, monkeypatch, make_payload
    ):
        """invite_to_embargo_on_case persists the EmProposeEmbargoActivity activity."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.activities.embargo import (
            EmProposeEmbargoActivity,
        )
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent

        dl = SqliteDataLayer("sqlite:///:memory:")

        embargo = EmbargoEvent(
            id_="https://example.org/cases/case_em2/embargo_events/e2",
            content="Proposed embargo",
        )
        proposal = EmProposeEmbargoActivity(
            id_="https://example.org/cases/case_em2/embargo_proposals/1",
            actor="https://example.org/users/vendor",
            object_=embargo,
            context="https://example.org/cases/case_em2",
        )

        event = make_payload(proposal)

        InviteToEmbargoOnCaseReceivedUseCase(dl, event).execute()

        stored = dl.get(proposal.type_.value, proposal.id_)
        assert stored is not None

    def test_accept_invite_to_embargo_on_case_activates_embargo(
        self, monkeypatch, make_payload
    ):
        """accept_invite_to_embargo_on_case activates the embargo on the case (PROPOSED → ACTIVE)."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.activities.embargo import (
            EmAcceptEmbargoActivity,
            EmProposeEmbargoActivity,
        )
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )
        from vultron.core.states.em import EM

        dl = SqliteDataLayer("sqlite:///:memory:")
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_em3",
            name="EM Accept Test",
        )
        embargo = EmbargoEvent(
            id_="https://example.org/cases/case_em3/embargo_events/e3",
            content="Embargo",
        )
        # Use inline objects (not string IDs) so rehydration skips DataLayer lookup
        proposal = EmProposeEmbargoActivity(
            id_="https://example.org/cases/case_em3/embargo_proposals/1",
            actor="https://example.org/users/vendor",
            object_=embargo,
            context=case,
        )
        # Start from PROPOSED — the standard pre-condition for activation.
        case.current_status.em_state = EM.PROPOSED
        dl.create(case)
        dl.create(embargo)
        dl.create(proposal)

        accept = EmAcceptEmbargoActivity(
            actor="https://example.org/users/coordinator",
            object_=proposal,
            context=case,
        )
        event = make_payload(accept)

        AcceptInviteToEmbargoOnCaseReceivedUseCase(dl, event).execute()

        case = dl.read(case.id_)
        assert case is not None
        case = cast(VulnerabilityCase, case)
        assert case.active_embargo is not None
        assert case.current_status.em_state == EM.ACTIVE

    def test_accept_invite_to_embargo_warns_on_non_standard_transition(
        self, monkeypatch, make_payload, caplog
    ):
        """accept_invite_to_embargo_on_case logs WARNING when EM state is not on the standard machine path."""
        import logging
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.activities.embargo import (
            EmAcceptEmbargoActivity,
            EmProposeEmbargoActivity,
        )
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )
        from vultron.core.states.em import EM

        dl = SqliteDataLayer("sqlite:///:memory:")
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_em3_warn",
            name="EM Accept Warn Test",
        )
        embargo = EmbargoEvent(
            id_="https://example.org/cases/case_em3_warn/embargo_events/e3",
            content="Embargo",
        )
        proposal = EmProposeEmbargoActivity(
            id_="https://example.org/cases/case_em3_warn/embargo_proposals/1",
            actor="https://example.org/users/vendor",
            object_=embargo,
            context=case,
        )
        # Default em_state is NONE — not a valid predecessor for ACTIVE.
        dl.create(case)
        dl.create(embargo)
        dl.create(proposal)

        accept = EmAcceptEmbargoActivity(
            actor="https://example.org/users/coordinator",
            object_=proposal,
            context=case,
        )
        event = make_payload(accept)

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
        from vultron.wire.as2.vocab.activities.embargo import (
            EmAcceptEmbargoActivity,
            EmProposeEmbargoActivity,
        )
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
        proposal = EmProposeEmbargoActivity(
            id_="https://example.org/cases/case_em5/embargo_proposals/1",
            actor="https://example.org/users/vendor",
            object_=embargo,
            context=case,
        )
        dl.create(case)
        dl.create(embargo)
        dl.create(participant)
        dl.create(proposal)

        accept = EmAcceptEmbargoActivity(
            actor=coordinator_id,
            object_=proposal,
            context=case,
        )
        event = make_payload(accept)

        AcceptInviteToEmbargoOnCaseReceivedUseCase(dl, event).execute()

        updated_participant = dl.get(id_=participant.id_)
        assert updated_participant is not None
        updated_participant = cast(Any, updated_participant)
        assert embargo.id_ in updated_participant.accepted_embargo_ids

    def test_accept_invite_to_embargo_records_case_event(
        self, monkeypatch, make_payload
    ):
        """accept_invite_to_embargo_on_case appends a trusted-timestamp event to case.events (CM-02-009)."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.activities.embargo import (
            EmAcceptEmbargoActivity,
            EmProposeEmbargoActivity,
        )
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_em6",
            name="EM Accept Event Test",
        )
        embargo = EmbargoEvent(
            id_="https://example.org/cases/case_em6/embargo_events/e6",
            content="Embargo",
        )
        proposal = EmProposeEmbargoActivity(
            id_="https://example.org/cases/case_em6/embargo_proposals/1",
            actor="https://example.org/users/vendor",
            object_=embargo,
            context=case,
        )
        dl.create(case)
        dl.create(embargo)
        dl.create(proposal)

        accept = EmAcceptEmbargoActivity(
            actor="https://example.org/users/coordinator",
            object_=proposal,
            context=case,
        )
        event = make_payload(accept)

        assert len(case.events) == 0

        AcceptInviteToEmbargoOnCaseReceivedUseCase(dl, event).execute()

        case = dl.read(case.id_)
        assert case is not None
        case = cast(VulnerabilityCase, case)
        assert len(case.events) >= 1
        event_types = [e.event_type for e in case.events]
        assert "embargo_accepted" in event_types

    def test_reject_invite_to_embargo_on_case_logs_rejection(
        self, make_payload
    ):
        """reject_invite_to_embargo_on_case logs without raising."""
        from vultron.wire.as2.vocab.activities.embargo import (
            EmProposeEmbargoActivity,
            EmRejectEmbargoActivity,
        )
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent

        embargo = EmbargoEvent(
            id_="https://example.org/cases/case_em4/embargo_events/e4",
            content="Embargo",
        )
        proposal = EmProposeEmbargoActivity(
            id_="https://example.org/cases/case_em4/embargo_proposals/1",
            actor="https://example.org/users/vendor",
            object_=embargo,
            context="https://example.org/cases/case_em4",
        )
        reject = EmRejectEmbargoActivity(
            actor="https://example.org/users/coordinator",
            object_=proposal,
            context="https://example.org/cases/case_em4",
        )

        event = make_payload(reject)

        result = RejectInviteToEmbargoOnCaseReceivedUseCase(
            MagicMock(), event
        ).execute()
        assert result is None

    def test_remove_embargo_from_proposed_clears_proposed_list(
        self, make_payload
    ):
        """remove_embargo_event removes embargo from proposed_embargoes."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.activities.embargo import (
            RemoveEmbargoFromCaseActivity,
        )
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_rem1",
            name="Remove Embargo Proposed",
        )
        embargo = EmbargoEvent(
            id_="https://example.org/cases/case_rem1/embargo_events/e1",
            context=case.id_,
        )
        case.proposed_embargoes.append(embargo.id_)
        case.current_status.em_state = EM.PROPOSED
        dl.create(case)

        activity = RemoveEmbargoFromCaseActivity(
            actor="https://example.org/users/coord",
            object_=embargo,
            origin=case,
        )
        event = make_payload(activity)

        RemoveEmbargoEventFromCaseReceivedUseCase(dl, event).execute()

        updated = dl.read(case.id_)
        assert updated is not None
        updated = cast(VulnerabilityCase, updated)
        assert embargo.id_ not in [
            e if isinstance(e, str) else getattr(e, "id_", None)
            for e in updated.proposed_embargoes
        ]

    def test_remove_active_embargo_proposed_state_transitions_to_none(
        self, make_payload
    ):
        """remove_embargo_event uses REJECT machine trigger when EM is PROPOSED."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.activities.embargo import (
            RemoveEmbargoFromCaseActivity,
        )
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_rem2",
            name="Remove Embargo PROPOSED→NONE",
        )
        embargo = EmbargoEvent(
            id_="https://example.org/cases/case_rem2/embargo_events/e2",
            context=case.id_,
        )
        case.active_embargo = embargo.id_
        case.current_status.em_state = EM.PROPOSED
        dl.create(case)

        activity = RemoveEmbargoFromCaseActivity(
            actor="https://example.org/users/coord",
            object_=embargo,
            origin=case,
        )
        event = make_payload(activity)

        RemoveEmbargoEventFromCaseReceivedUseCase(dl, event).execute()

        updated = dl.read(case.id_)
        assert updated is not None
        updated = cast(VulnerabilityCase, updated)
        assert updated.active_embargo is None
        assert updated.current_status.em_state == EM.NONE

    def test_remove_active_embargo_active_state_admin_override(
        self, caplog, make_payload
    ):
        """remove_embargo_event logs WARNING when EM state is ACTIVE (admin override)."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.activities.embargo import (
            RemoveEmbargoFromCaseActivity,
        )
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_rem3",
            name="Remove Active Embargo Admin Override",
        )
        embargo = EmbargoEvent(
            id_="https://example.org/cases/case_rem3/embargo_events/e3",
            context=case.id_,
        )
        case.active_embargo = embargo.id_
        case.current_status.em_state = EM.ACTIVE
        dl.create(case)

        activity = RemoveEmbargoFromCaseActivity(
            actor="https://example.org/users/coord",
            object_=embargo,
            origin=case,
        )
        event = make_payload(activity)

        with caplog.at_level(logging.WARNING):
            RemoveEmbargoEventFromCaseReceivedUseCase(dl, event).execute()

        updated = dl.read(case.id_)
        assert updated is not None
        updated = cast(VulnerabilityCase, updated)
        assert updated.active_embargo is None
        assert updated.current_status.em_state == EM.NONE
        assert any("Admin override" in r.message for r in caplog.records)

    def test_evaluate_embargo_raises_invalid_state_transition_when_em_state_invalid(
        self,
    ):
        """SvcEvaluateEmbargoUseCase raises VultronInvalidStateTransitionError when EM state does not allow ACCEPT."""
        import pytest
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.activities.embargo import (
            EmProposeEmbargoActivity,
        )
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )
        from vultron.wire.as2.vocab.base.objects.actors import (
            as_Actor as Actor,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        actor = Actor(id_="https://example.org/users/vendor", name="Vendor")
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_eval_invalid",
            name="Evaluate Invalid EM State",
        )
        embargo = EmbargoEvent(
            id_="https://example.org/cases/case_eval_invalid/embargo_events/e1",
            context=case.id_,
        )
        proposal = EmProposeEmbargoActivity(
            id_="https://example.org/cases/case_eval_invalid/proposals/p1",
            actor=actor.id_,
            object_=embargo,
            context=case.id_,
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

        request = EvaluateEmbargoTriggerRequest(
            actor_id=actor.id_,
            case_id=case.id_,
            proposal_id=proposal.id_,
        )
        with pytest.raises(VultronInvalidStateTransitionError):
            SvcEvaluateEmbargoUseCase(dl, request).execute()
