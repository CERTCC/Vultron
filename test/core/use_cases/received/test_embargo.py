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
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.models.case_log_entry import VultronCaseLogEntry
from vultron.core.models.protocols import is_log_entry_model
from vultron.core.states.em import EM
from vultron.core.use_cases.received.embargo import (
    AnnounceEmbargoEventToCaseReceivedUseCase,
    CreateEmbargoEventReceivedUseCase,
    AddEmbargoEventToCaseReceivedUseCase,
    RemoveEmbargoEventFromCaseReceivedUseCase,
    InviteToEmbargoOnCaseReceivedUseCase,
    AcceptInviteToEmbargoOnCaseReceivedUseCase,
    RejectInviteToEmbargoOnCaseReceivedUseCase,
)
from vultron.core.use_cases.triggers.embargo import SvcAcceptEmbargoUseCase
from vultron.core.use_cases.triggers.requests import (
    AcceptEmbargoTriggerRequest,
)
from vultron.errors import VultronInvalidStateTransitionError
from vultron.wire.as2.factories import (
    add_embargo_to_case_activity,
    announce_embargo_activity,
    em_accept_embargo_activity,
    em_propose_embargo_activity,
    em_reject_embargo_activity,
    remove_embargo_from_case_activity,
)
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase


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

    def test_add_embargo_event_to_case_activates_embargo(
        self, monkeypatch, make_payload
    ):
        """add_embargo_event_to_case sets the active embargo on the case (PROPOSED → ACTIVE)."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

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

        activity = add_embargo_to_case_activity(
            embargo,
            target=case,
            actor="https://example.org/users/vendor",
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
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

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

        activity = add_embargo_to_case_activity(
            embargo,
            target=case,
            actor="https://example.org/users/vendor",
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

        event = make_payload(proposal)

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

    def test_remove_embargo_from_proposed_clears_proposed_list(
        self, make_payload
    ):
        """remove_embargo_event removes embargo from proposed_embargoes."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
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

        activity = remove_embargo_from_case_activity(
            embargo,
            origin=case,
            actor="https://example.org/users/coord",
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

    def test_remove_active_embargo_transitions_em_to_exited(
        self, make_payload
    ):
        """remove_embargo_event transitions EM from ACTIVE to EXITED via BT."""
        import py_trees
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        py_trees.blackboard.Blackboard.enable_activity_stream()
        py_trees.blackboard.Blackboard.storage.clear()

        dl = SqliteDataLayer("sqlite:///:memory:")
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_rem2",
            name="Remove Embargo ACTIVE→EXITED",
        )
        embargo = EmbargoEvent(
            id_="https://example.org/cases/case_rem2/embargo_events/e2",
            context=case.id_,
        )
        case.active_embargo = embargo.id_
        case.current_status.em_state = EM.ACTIVE
        dl.create(case)

        activity = remove_embargo_from_case_activity(
            embargo,
            origin=case,
            actor="https://example.org/users/coord",
        )
        event = make_payload(activity)

        RemoveEmbargoEventFromCaseReceivedUseCase(dl, event).execute()

        updated = dl.read(case.id_)
        assert updated is not None
        updated = cast(VulnerabilityCase, updated)
        assert updated.active_embargo is None
        assert updated.current_status.em_state == EM.EXITED

    def test_remove_active_embargo_unusual_state_uses_override(
        self, caplog, make_payload
    ):
        """remove_embargo_event uses state-sync override when EM is PROPOSED but embargo is active."""
        import py_trees
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        py_trees.blackboard.Blackboard.enable_activity_stream()
        py_trees.blackboard.Blackboard.storage.clear()

        dl = SqliteDataLayer("sqlite:///:memory:")
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_rem3",
            name="Remove Embargo unusual state override",
        )
        embargo = EmbargoEvent(
            id_="https://example.org/cases/case_rem3/embargo_events/e3",
            context=case.id_,
        )
        case.active_embargo = embargo.id_
        case.current_status.em_state = EM.PROPOSED
        dl.create(case)

        activity = remove_embargo_from_case_activity(
            embargo,
            origin=case,
            actor="https://example.org/users/coord",
        )
        event = make_payload(activity)

        RemoveEmbargoEventFromCaseReceivedUseCase(dl, event).execute()

        updated = dl.read(case.id_)
        assert updated is not None
        updated = cast(VulnerabilityCase, updated)
        assert updated.active_embargo is None
        assert updated.current_status.em_state == EM.EXITED

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
        from vultron.core.states.roles import CVDRole
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


class TestAnnounceEmbargoEventToCaseReceivedUseCase:
    """Tests for AnnounceEmbargoEventToCaseReceivedUseCase (no-op receiver)."""

    def test_announce_embargo_is_noop(self, make_payload):
        """execute() is a no-op: EM state and active_embargo are unchanged."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_aem1",
            name="Announce Embargo No-Op Test",
        )
        embargo = EmbargoEvent(
            id_="https://example.org/cases/case_aem1/embargo_events/e1",
            context=case.id_,
        )
        case.active_embargo = embargo.id_
        case.current_status.em_state = EM.ACTIVE
        dl.create(case)

        activity = announce_embargo_activity(
            embargo=embargo,
            context=case,
            actor="https://example.org/users/vendor",
        )
        event = make_payload(activity)

        AnnounceEmbargoEventToCaseReceivedUseCase(dl, event).execute()

        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated is not None
        # State is UNCHANGED — Announce is not the ET message
        assert updated.current_status.em_state == EM.ACTIVE
        assert updated.active_embargo is not None

    def test_announce_embargo_logs_info(self, make_payload, caplog):
        """execute() logs receipt at INFO level."""
        from unittest.mock import MagicMock

        dl = MagicMock()
        mock_event = MagicMock()
        mock_event.activity_id = "https://example.org/activities/ann1"

        with caplog.at_level(logging.INFO):
            AnnounceEmbargoEventToCaseReceivedUseCase(dl, mock_event).execute()

        assert any(
            "no receiver-side state change required" in r.message
            for r in caplog.records
        )


# ---------------------------------------------------------------------------
# CaseLogEntry cascade tests (PCR-08-003, PCR-08-004) — AC-3
# ---------------------------------------------------------------------------


def _make_embargo_case_with_actor(
    case_id: str,
    author_id: str,
    extra_participants: list[str] | None = None,
) -> tuple[SqliteDataLayer, VultronCaseActor, VulnerabilityCase, EmbargoEvent]:
    """Return (dl, case_actor, case, embargo) ready for cascade tests.

    Also creates ``CaseParticipant`` objects so actor → participant lookups
    in the embargo handlers succeed.
    """
    from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant

    dl = SqliteDataLayer("sqlite:///:memory:")
    case_actor_id = f"{case_id}/actor"

    case_actor = VultronCaseActor(
        id_=case_actor_id,
        name=f"CaseActor for {case_id}",
        attributed_to=author_id,
        context=case_id,
    )
    dl.create(case_actor)

    case = VulnerabilityCase(
        id_=case_id,
        name="Embargo Cascade Case",
        attributed_to=author_id,
    )
    p1_id = f"{case_id}/participants/p1"
    case.actor_participant_index[author_id] = p1_id
    p1 = CaseParticipant(id_=p1_id, context=case_id, attributed_to=author_id)
    dl.create(p1)

    for pid in extra_participants or []:
        short = pid.rsplit("/", 1)[-1]
        pn_id = f"{case_id}/participants/{short}"
        case.actor_participant_index[pid] = pn_id
        pn = CaseParticipant(id_=pn_id, context=case_id, attributed_to=pid)
        dl.create(pn)

    dl.create(case)

    embargo = EmbargoEvent(
        id_=f"{case_id}/embargo_events/e1",
        content="Cascade test embargo",
        context=case_id,
    )
    dl.create(embargo)

    return dl, case_actor, case, embargo


class TestEmbargoLogEntryCascade:
    """CaseLogEntry cascade for each embargo received-side handler (AC-3)."""

    def test_add_embargo_event_commits_log_entry(self, make_payload):
        """AddEmbargoEventToCaseReceivedUseCase commits a CaseLogEntry."""
        author_id = "https://example.org/users/coord"
        case_id = "https://example.org/cases/em_cas_add"
        dl, case_actor, case, embargo = _make_embargo_case_with_actor(
            case_id, author_id
        )
        case = cast(VulnerabilityCase, dl.read(case.id_))
        assert case is not None
        case.current_status.em_state = EM.PROPOSED
        dl.save(case)

        activity = add_embargo_to_case_activity(
            embargo, target=case, actor=author_id
        )
        event = make_payload(activity, receiving_actor_id=case_actor.id_)
        sync_port = SyncActivityAdapter(dl)
        AddEmbargoEventToCaseReceivedUseCase(
            dl, event, sync_port=sync_port
        ).execute()

        entries = [
            obj
            for obj in dl.list_objects("CaseLogEntry")
            if is_log_entry_model(obj)
            and cast(VultronCaseLogEntry, obj).case_id == case_id
        ]
        assert len(entries) == 1
        assert cast(VultronCaseLogEntry, entries[0]).event_type == (
            "add_embargo_event_to_case"
        )

    def test_remove_embargo_event_commits_log_entry(self, make_payload):
        """RemoveEmbargoEventFromCaseReceivedUseCase commits a CaseLogEntry."""
        import py_trees

        py_trees.blackboard.Blackboard.enable_activity_stream()
        py_trees.blackboard.Blackboard.storage.clear()

        author_id = "https://example.org/users/coord"
        case_id = "https://example.org/cases/em_cas_rem"
        dl, case_actor, case, embargo = _make_embargo_case_with_actor(
            case_id, author_id
        )
        case = cast(VulnerabilityCase, dl.read(case.id_))
        assert case is not None
        case.current_status.em_state = EM.ACTIVE
        case.proposed_embargoes.append(embargo.id_)
        case.active_embargo = embargo.id_  # type: ignore[assignment]
        dl.save(case)

        activity = remove_embargo_from_case_activity(
            embargo, origin=case, actor=author_id
        )
        event = make_payload(activity, receiving_actor_id=case_actor.id_)
        sync_port = SyncActivityAdapter(dl)
        RemoveEmbargoEventFromCaseReceivedUseCase(
            dl, event, sync_port=sync_port
        ).execute()

        entries = [
            obj
            for obj in dl.list_objects("CaseLogEntry")
            if is_log_entry_model(obj)
            and cast(VultronCaseLogEntry, obj).case_id == case_id
        ]
        assert len(entries) == 1
        assert cast(VultronCaseLogEntry, entries[0]).event_type == (
            "remove_embargo_event_from_case"
        )

    def test_remove_embargo_commits_log_entry_on_bt_failure(
        self, make_payload
    ):
        """RemoveEmbargoEventFromCaseReceivedUseCase cascades even when BT fails.

        BT FAILURE means "embargo already cleared" — it is not an error. The
        CaseLogEntry MUST be committed regardless so participants learn the
        current state.
        """
        import py_trees

        py_trees.blackboard.Blackboard.enable_activity_stream()
        py_trees.blackboard.Blackboard.storage.clear()

        author_id = "https://example.org/users/coord"
        case_id = "https://example.org/cases/em_cas_rem_fail"
        dl, case_actor, case, embargo = _make_embargo_case_with_actor(
            case_id, author_id
        )
        # EM.NONE: no active embargo — BT will FAIL (IsActiveEmbargoNode)
        case = cast(VulnerabilityCase, dl.read(case.id_))
        assert case is not None
        case.current_status.em_state = EM.NONE
        dl.save(case)

        activity = remove_embargo_from_case_activity(
            embargo, origin=case, actor=author_id
        )
        event = make_payload(activity, receiving_actor_id=case_actor.id_)
        sync_port = SyncActivityAdapter(dl)
        RemoveEmbargoEventFromCaseReceivedUseCase(
            dl, event, sync_port=sync_port
        ).execute()

        entries = [
            obj
            for obj in dl.list_objects("CaseLogEntry")
            if is_log_entry_model(obj)
            and cast(VultronCaseLogEntry, obj).case_id == case_id
        ]
        # Cascade must fire even on BT FAILURE.
        assert len(entries) == 1

    def test_invite_to_embargo_commits_log_entry(self, make_payload):
        """InviteToEmbargoOnCaseReceivedUseCase commits a CaseLogEntry."""
        author_id = "https://example.org/users/coord"
        case_id = "https://example.org/cases/em_cas_invite"
        invitee_id = "https://example.org/users/vendor"
        dl, case_actor, case, embargo = _make_embargo_case_with_actor(
            case_id, author_id, extra_participants=[invitee_id]
        )

        proposal = em_propose_embargo_activity(
            embargo,
            context=case_id,
            actor=author_id,
            id_=f"{case_id}/embargo_proposals/1",
        )
        dl.create(proposal)

        # receiving_actor_id must be a participant actor so the handler can
        # look up the participant's consent state.
        event = make_payload(proposal, receiving_actor_id=invitee_id)
        sync_port = SyncActivityAdapter(dl)
        InviteToEmbargoOnCaseReceivedUseCase(
            dl, event, sync_port=sync_port
        ).execute()

        entries = [
            obj
            for obj in dl.list_objects("CaseLogEntry")
            if is_log_entry_model(obj)
            and cast(VultronCaseLogEntry, obj).case_id == case_id
        ]
        assert len(entries) == 1
        assert cast(VultronCaseLogEntry, entries[0]).event_type == (
            "invite_to_embargo_on_case"
        )

    def test_accept_invite_to_embargo_commits_log_entry(self, make_payload):
        """AcceptInviteToEmbargoOnCaseReceivedUseCase commits a CaseLogEntry."""
        coordinator_id = "https://example.org/users/coordinator"
        case_id = "https://example.org/cases/em_cas_accept"
        dl, case_actor, case, embargo = _make_embargo_case_with_actor(
            case_id, coordinator_id
        )
        case = cast(VulnerabilityCase, dl.read(case.id_))
        assert case is not None
        case.current_status.em_state = EM.PROPOSED
        dl.save(case)

        proposal = em_propose_embargo_activity(
            embargo,
            context=case,
            actor="https://example.org/users/vendor",
            id_=f"{case_id}/embargo_proposals/1",
        )
        dl.create(proposal)

        accept = em_accept_embargo_activity(
            proposal,
            context=case,
            actor=coordinator_id,
        )
        event = make_payload(accept, receiving_actor_id=case_actor.id_)
        sync_port = SyncActivityAdapter(dl)
        AcceptInviteToEmbargoOnCaseReceivedUseCase(
            dl, event, sync_port=sync_port
        ).execute()

        entries = [
            obj
            for obj in dl.list_objects("CaseLogEntry")
            if is_log_entry_model(obj)
            and cast(VultronCaseLogEntry, obj).case_id == case_id
        ]
        assert len(entries) == 1
        assert cast(VultronCaseLogEntry, entries[0]).event_type == (
            "accept_invite_to_embargo_on_case"
        )

    def test_reject_invite_to_embargo_commits_log_entry(self, make_payload):
        """RejectInviteToEmbargoOnCaseReceivedUseCase commits a CaseLogEntry."""
        coordinator_id = "https://example.org/users/coordinator"
        case_id = "https://example.org/cases/em_cas_reject"
        dl, case_actor, case, embargo = _make_embargo_case_with_actor(
            case_id, coordinator_id
        )

        proposal = em_propose_embargo_activity(
            embargo,
            context=case_id,
            actor="https://example.org/users/vendor",
            id_=f"{case_id}/embargo_proposals/1",
        )
        dl.create(proposal)

        reject = em_reject_embargo_activity(
            proposal,
            context=case_id,
            actor=coordinator_id,
        )
        event = make_payload(reject, receiving_actor_id=case_actor.id_)
        sync_port = SyncActivityAdapter(dl)
        RejectInviteToEmbargoOnCaseReceivedUseCase(
            dl, event, sync_port=sync_port
        ).execute()

        entries = [
            obj
            for obj in dl.list_objects("CaseLogEntry")
            if is_log_entry_model(obj)
            and cast(VultronCaseLogEntry, obj).case_id == case_id
        ]
        assert len(entries) == 1
        assert cast(VultronCaseLogEntry, entries[0]).event_type == (
            "reject_invite_to_embargo_on_case"
        )


# ---------------------------------------------------------------------------
# Regression tests for #609: inline CaseParticipant in case_participants
# ---------------------------------------------------------------------------


class TestResetEmbargoConsentWithInlineParticipants:
    """Regression tests for #609: _reset_case_participant_embargo_consent
    must tolerate inline CaseParticipant objects in case.case_participants,
    not just plain string IDs.
    """

    def test_remove_active_embargo_with_inline_participant_no_type_error(
        self, make_payload
    ):
        """remove_embargo_from_case must not raise TypeError when
        case.case_participants holds inline CaseParticipant objects
        (as stored on receiver side after fixes #572/#573).

        Regression test for #609.
        """
        import py_trees
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.states.participant_embargo_consent import PEC
        from vultron.wire.as2.vocab.objects.case_participant import (
            CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        py_trees.blackboard.Blackboard.enable_activity_stream()
        py_trees.blackboard.Blackboard.storage.clear()

        actor_id = "https://example.org/users/finder"
        case_id = "https://example.org/cases/case_609_inline"
        participant_id = f"{case_id}/participants/p1"

        dl = SqliteDataLayer("sqlite:///:memory:")

        # Build a participant and store it — it also appears inline in case
        participant = CaseParticipant(
            id_=participant_id,
            context=case_id,
            attributed_to=actor_id,
        )
        # Simulate receiver-side: participant's consent state is SIGNATORY
        participant.embargo_consent_state = PEC.SIGNATORY
        dl.create(participant)

        embargo = EmbargoEvent(
            id_=f"{case_id}/embargo_events/e1",
            context=case_id,
        )
        dl.create(embargo)

        # Store inline CaseParticipant object (not string ID) in
        # case_participants — this is the condition that caused #609.
        case = VulnerabilityCase(
            id_=case_id,
            name="Inline Participant Regression Test",
            attributed_to=actor_id,
        )
        case.active_embargo = embargo.id_
        case.current_status.em_state = EM.ACTIVE
        case.case_participants.append(participant)  # inline object, not str
        case.actor_participant_index[actor_id] = participant_id
        dl.create(case)

        activity = remove_embargo_from_case_activity(
            embargo,
            origin=case,
            actor=actor_id,
        )
        event = make_payload(activity)

        # Must not raise TypeError
        RemoveEmbargoEventFromCaseReceivedUseCase(dl, event).execute()

        updated = cast(VulnerabilityCase, dl.read(case_id))
        assert updated is not None
        assert updated.active_embargo is None
        assert updated.current_status.em_state == EM.EXITED

    def test_reset_consent_with_inline_participant_resets_state(self):
        """_reset_case_participant_embargo_consent resets consent state even
        when case_participants entries are inline wire-layer CaseParticipant
        objects (not string IDs).

        Regression test for #609.
        """
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.models.protocols import is_case_model
        from vultron.core.states.participant_embargo_consent import PEC
        from vultron.core.use_cases._helpers import (
            reset_case_participant_embargo_consent as _reset_case_participant_embargo_consent,
        )
        from vultron.wire.as2.vocab.objects.case_participant import (
            CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        actor_id = "https://example.org/users/finder"
        case_id = "https://example.org/cases/case_609_reset"
        participant_id = f"{case_id}/participants/p1"

        dl = SqliteDataLayer("sqlite:///:memory:")

        # Wire-layer CaseParticipant with non-default consent state.
        # Stored in the DataLayer separately so dl.read(participant_id) works.
        participant = CaseParticipant(
            id_=participant_id,
            context=case_id,
            attributed_to=actor_id,
        )
        participant.embargo_consent_state = PEC.SIGNATORY.value
        dl.create(participant)

        # Inline wire-layer object in case_participants — this is the condition
        # that caused #609 on the receiver side after fixes #572/#573.
        case = VulnerabilityCase(
            id_=case_id,
            name="Reset Consent Inline",
        )
        case.case_participants.append(participant)
        dl.create(case)

        assert is_case_model(
            case
        ), "VulnerabilityCase should satisfy CaseModel"

        # Must not raise TypeError
        _reset_case_participant_embargo_consent(dl, case)

        updated_participant = dl.read(participant_id)
        assert updated_participant is not None
        assert (
            getattr(updated_participant, "embargo_consent_state", None)
            == PEC.NO_EMBARGO.value
        )
