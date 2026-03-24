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
from unittest.mock import MagicMock

from vultron.core.states.em import EM
from vultron.core.use_cases.embargo import (
    CreateEmbargoEventReceivedUseCase,
    AddEmbargoEventToCaseReceivedUseCase,
    RemoveEmbargoEventFromCaseReceivedUseCase,
    InviteToEmbargoOnCaseReceivedUseCase,
    AcceptInviteToEmbargoOnCaseReceivedUseCase,
    RejectInviteToEmbargoOnCaseReceivedUseCase,
)


class TestEmbargoUseCases:
    """Tests for embargo management handlers."""

    def test_create_embargo_event_stores_event(
        self, monkeypatch, make_payload
    ):
        """create_embargo_event persists the EmbargoEvent to the DataLayer."""
        from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
        from vultron.wire.as2.vocab.base.objects.activities.transitive import (
            as_Create,
        )
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)

        case = VulnerabilityCase(
            id="https://example.org/cases/case_cem1",
            name="Create Embargo Test",
        )
        embargo = EmbargoEvent(
            id="https://example.org/cases/case_cem1/embargo_events/embargo1",
            content="Proposed embargo",
        )
        activity = as_Create(
            actor="https://example.org/users/vendor",
            object=embargo,
            context=case,
        )

        event = make_payload(activity)

        CreateEmbargoEventReceivedUseCase(dl, event).execute()

        stored = dl.get(embargo.as_type.value, embargo.as_id)
        assert stored is not None

    def test_create_embargo_event_idempotent(self, monkeypatch, make_payload):
        """create_embargo_event skips storing a duplicate EmbargoEvent."""
        from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
        from vultron.wire.as2.vocab.base.objects.activities.transitive import (
            as_Create,
        )
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)

        case = VulnerabilityCase(
            id="https://example.org/cases/case_cem2",
            name="Create Embargo Idempotent",
        )
        embargo = EmbargoEvent(
            id="https://example.org/cases/case_cem2/embargo_events/embargo2",
            content="Proposed embargo",
        )
        activity = as_Create(
            actor="https://example.org/users/vendor",
            object=embargo,
            context=case,
        )
        event = make_payload(activity)

        CreateEmbargoEventReceivedUseCase(dl, event).execute()
        CreateEmbargoEventReceivedUseCase(
            dl, event
        ).execute()  # second call no-op

        stored = dl.get(embargo.as_type.value, embargo.as_id)
        assert stored is not None

    def test_add_embargo_event_to_case_activates_embargo(
        self, monkeypatch, make_payload
    ):
        """add_embargo_event_to_case sets the active embargo on the case."""
        from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.embargo import (
            AddEmbargoToCaseActivity,
        )
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )
        from vultron.core.states.em import EM

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.wire.as2.rehydration.get_datalayer",
            lambda **_: dl,
        )

        case = VulnerabilityCase(
            id="https://example.org/cases/case_em1",
            name="EM Test Case",
        )
        embargo = EmbargoEvent(
            id="https://example.org/cases/case_em1/embargo_events/e1",
            content="Embargo test",
        )
        dl.create(case)
        dl.create(embargo)

        activity = AddEmbargoToCaseActivity(
            actor="https://example.org/users/vendor",
            object=embargo,
            target=case,
        )
        event = make_payload(activity)

        AddEmbargoEventToCaseReceivedUseCase(dl, event).execute()

        case = dl.read(case.as_id)
        assert case.active_embargo is not None
        assert case.current_status.em_state == EM.ACTIVE

    def test_invite_to_embargo_on_case_stores_proposal(
        self, monkeypatch, make_payload
    ):
        """invite_to_embargo_on_case persists the EmProposeEmbargoActivity activity."""
        from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.embargo import (
            EmProposeEmbargoActivity,
        )
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent

        dl = TinyDbDataLayer(db_path=None)

        embargo = EmbargoEvent(
            id="https://example.org/cases/case_em2/embargo_events/e2",
            content="Proposed embargo",
        )
        proposal = EmProposeEmbargoActivity(
            id="https://example.org/cases/case_em2/embargo_proposals/1",
            actor="https://example.org/users/vendor",
            object=embargo,
            context="https://example.org/cases/case_em2",
        )

        event = make_payload(proposal)

        InviteToEmbargoOnCaseReceivedUseCase(dl, event).execute()

        stored = dl.get(proposal.as_type.value, proposal.as_id)
        assert stored is not None

    def test_accept_invite_to_embargo_on_case_activates_embargo(
        self, monkeypatch, make_payload
    ):
        """accept_invite_to_embargo_on_case activates the embargo on the case."""
        from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.embargo import (
            EmAcceptEmbargoActivity,
            EmProposeEmbargoActivity,
        )
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )
        from vultron.core.states.em import EM

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.wire.as2.rehydration.get_datalayer",
            lambda **_: dl,
        )

        case = VulnerabilityCase(
            id="https://example.org/cases/case_em3",
            name="EM Accept Test",
        )
        embargo = EmbargoEvent(
            id="https://example.org/cases/case_em3/embargo_events/e3",
            content="Embargo",
        )
        # Use inline objects (not string IDs) so rehydration skips DataLayer lookup
        proposal = EmProposeEmbargoActivity(
            id="https://example.org/cases/case_em3/embargo_proposals/1",
            actor="https://example.org/users/vendor",
            object=embargo,
            context=case,
        )
        dl.create(case)
        dl.create(embargo)
        dl.create(proposal)

        accept = EmAcceptEmbargoActivity(
            actor="https://example.org/users/coordinator",
            object=proposal,
            context=case,
        )
        event = make_payload(accept)

        AcceptInviteToEmbargoOnCaseReceivedUseCase(dl, event).execute()

        case = dl.read(case.as_id)
        assert case.active_embargo is not None
        assert case.current_status.em_state == EM.ACTIVE

    def test_accept_invite_to_embargo_records_embargo_on_participant(
        self, monkeypatch, make_payload
    ):
        """accept_invite_to_embargo_on_case records embargo ID in participant.accepted_embargo_ids (CM-10-002, CM-10-003)."""
        from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
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

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.wire.as2.rehydration.get_datalayer",
            lambda **_: dl,
        )

        coordinator_id = "https://example.org/users/coordinator"
        case = VulnerabilityCase(
            id="https://example.org/cases/case_em5",
            name="EM Accept Participant Test",
        )
        embargo = EmbargoEvent(
            id="https://example.org/cases/case_em5/embargo_events/e5",
            content="Embargo",
        )
        participant = CaseParticipant(
            id="https://example.org/cases/case_em5/participants/coord",
            attributed_to=coordinator_id,
            context=case.as_id,
        )
        case.add_participant(participant)
        proposal = EmProposeEmbargoActivity(
            id="https://example.org/cases/case_em5/embargo_proposals/1",
            actor="https://example.org/users/vendor",
            object=embargo,
            context=case,
        )
        dl.create(case)
        dl.create(embargo)
        dl.create(participant)
        dl.create(proposal)

        accept = EmAcceptEmbargoActivity(
            actor=coordinator_id,
            object=proposal,
            context=case,
        )
        event = make_payload(accept)

        AcceptInviteToEmbargoOnCaseReceivedUseCase(dl, event).execute()

        updated_participant = dl.get(id_=participant.as_id)
        assert updated_participant is not None
        assert embargo.as_id in updated_participant.accepted_embargo_ids

    def test_accept_invite_to_embargo_records_case_event(
        self, monkeypatch, make_payload
    ):
        """accept_invite_to_embargo_on_case appends a trusted-timestamp event to case.events (CM-02-009)."""
        from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.embargo import (
            EmAcceptEmbargoActivity,
            EmProposeEmbargoActivity,
        )
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.wire.as2.rehydration.get_datalayer",
            lambda **_: dl,
        )

        case = VulnerabilityCase(
            id="https://example.org/cases/case_em6",
            name="EM Accept Event Test",
        )
        embargo = EmbargoEvent(
            id="https://example.org/cases/case_em6/embargo_events/e6",
            content="Embargo",
        )
        proposal = EmProposeEmbargoActivity(
            id="https://example.org/cases/case_em6/embargo_proposals/1",
            actor="https://example.org/users/vendor",
            object=embargo,
            context=case,
        )
        dl.create(case)
        dl.create(embargo)
        dl.create(proposal)

        accept = EmAcceptEmbargoActivity(
            actor="https://example.org/users/coordinator",
            object=proposal,
            context=case,
        )
        event = make_payload(accept)

        assert len(case.events) == 0

        AcceptInviteToEmbargoOnCaseReceivedUseCase(dl, event).execute()

        case = dl.read(case.as_id)
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
            id="https://example.org/cases/case_em4/embargo_events/e4",
            content="Embargo",
        )
        proposal = EmProposeEmbargoActivity(
            id="https://example.org/cases/case_em4/embargo_proposals/1",
            actor="https://example.org/users/vendor",
            object=embargo,
            context="https://example.org/cases/case_em4",
        )
        reject = EmRejectEmbargoActivity(
            actor="https://example.org/users/coordinator",
            object=proposal,
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
        from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.embargo import (
            RemoveEmbargoFromCaseActivity,
        )
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)
        case = VulnerabilityCase(
            id="https://example.org/cases/case_rem1",
            name="Remove Embargo Proposed",
        )
        embargo = EmbargoEvent(
            id="https://example.org/cases/case_rem1/embargo_events/e1",
            context=case.as_id,
        )
        case.proposed_embargoes.append(embargo.as_id)
        case.current_status.em_state = EM.PROPOSED
        dl.create(case)

        activity = RemoveEmbargoFromCaseActivity(
            actor="https://example.org/users/coord",
            object=embargo,
            origin=case,
        )
        event = make_payload(activity)

        RemoveEmbargoEventFromCaseReceivedUseCase(dl, event).execute()

        updated = dl.read(case.as_id)
        assert embargo.as_id not in [
            e if isinstance(e, str) else e.as_id
            for e in updated.proposed_embargoes
        ]

    def test_remove_active_embargo_proposed_state_transitions_to_none(
        self, make_payload
    ):
        """remove_embargo_event uses REJECT machine trigger when EM is PROPOSED."""
        from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.embargo import (
            RemoveEmbargoFromCaseActivity,
        )
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)
        case = VulnerabilityCase(
            id="https://example.org/cases/case_rem2",
            name="Remove Embargo PROPOSED→NONE",
        )
        embargo = EmbargoEvent(
            id="https://example.org/cases/case_rem2/embargo_events/e2",
            context=case.as_id,
        )
        case.active_embargo = embargo.as_id
        case.current_status.em_state = EM.PROPOSED
        dl.create(case)

        activity = RemoveEmbargoFromCaseActivity(
            actor="https://example.org/users/coord",
            object=embargo,
            origin=case,
        )
        event = make_payload(activity)

        RemoveEmbargoEventFromCaseReceivedUseCase(dl, event).execute()

        updated = dl.read(case.as_id)
        assert updated.active_embargo is None
        assert updated.current_status.em_state == EM.NONE

    def test_remove_active_embargo_active_state_admin_override(
        self, caplog, make_payload
    ):
        """remove_embargo_event logs WARNING when EM state is ACTIVE (admin override)."""
        from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.embargo import (
            RemoveEmbargoFromCaseActivity,
        )
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)
        case = VulnerabilityCase(
            id="https://example.org/cases/case_rem3",
            name="Remove Active Embargo Admin Override",
        )
        embargo = EmbargoEvent(
            id="https://example.org/cases/case_rem3/embargo_events/e3",
            context=case.as_id,
        )
        case.active_embargo = embargo.as_id
        case.current_status.em_state = EM.ACTIVE
        dl.create(case)

        activity = RemoveEmbargoFromCaseActivity(
            actor="https://example.org/users/coord",
            object=embargo,
            origin=case,
        )
        event = make_payload(activity)

        with caplog.at_level(logging.WARNING):
            RemoveEmbargoEventFromCaseReceivedUseCase(dl, event).execute()

        updated = dl.read(case.as_id)
        assert updated.active_embargo is None
        assert updated.current_status.em_state == EM.NONE
        assert any("Admin override" in r.message for r in caplog.records)
