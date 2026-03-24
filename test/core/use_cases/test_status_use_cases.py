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
"""Tests for status-related use-case classes."""

from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
from vultron.core.states.em import EM
from vultron.core.use_cases.status import (
    AddCaseStatusToCaseReceivedUseCase,
    AddParticipantStatusToParticipantReceivedUseCase,
    CreateCaseStatusReceivedUseCase,
    CreateParticipantStatusReceivedUseCase,
)
from vultron.wire.as2.vocab.activities.case import (
    AddStatusToCaseActivity,
    CreateCaseStatusActivity,
)
from vultron.wire.as2.vocab.activities.case_participant import (
    AddStatusToParticipantActivity,
    CreateStatusForParticipantActivity,
)
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import (
    CaseStatus,
    ParticipantStatus,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase


class TestStatusUseCases:
    """Tests for case status and participant status handlers."""

    def test_create_case_status_stores_status(self, monkeypatch, make_payload):
        """create_case_status persists the CaseStatus to the DataLayer."""

        dl = TinyDbDataLayer(db_path=None)

        case = VulnerabilityCase(
            id="https://example.org/cases/case_cs1",
            name="Case Status Test",
        )
        status = CaseStatus(
            id="https://example.org/cases/case_cs1/statuses/s1",
            context=case.as_id,
        )
        activity = CreateCaseStatusActivity(
            actor="https://example.org/users/vendor",
            object=status,
            context=case.as_id,
        )

        event = make_payload(activity)

        CreateCaseStatusReceivedUseCase(dl, event).execute()

        stored = dl.get(status.as_type.value, status.as_id)
        assert stored is not None

    def test_create_case_status_idempotent(self, monkeypatch, make_payload):
        """create_case_status skips storing a duplicate CaseStatus."""
        dl = TinyDbDataLayer(db_path=None)

        case = VulnerabilityCase(
            id="https://example.org/cases/case_cs2",
            name="Case Status Idempotent",
        )
        status = CaseStatus(
            id="https://example.org/cases/case_cs2/statuses/s2",
            context=case.as_id,
        )
        dl.create(status)

        activity = CreateCaseStatusActivity(
            actor="https://example.org/users/vendor",
            object=status,
            context=case.as_id,
        )
        event = make_payload(activity)

        CreateCaseStatusReceivedUseCase(dl, event).execute()

        stored = dl.get(status.as_type.value, status.as_id)
        assert stored is not None

    def test_add_case_status_to_case_appends_status(
        self, monkeypatch, make_payload
    ):
        """add_case_status_to_case appends status ID to case.case_statuses."""
        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.wire.as2.rehydration.get_datalayer",
            lambda **_: dl,
        )

        case = VulnerabilityCase(
            id="https://example.org/cases/case_cs3",
            name="Add Status Case",
        )
        status = CaseStatus(
            id="https://example.org/cases/case_cs3/statuses/s3",
            context=case.as_id,
        )
        dl.create(case)
        dl.create(status)

        activity = AddStatusToCaseActivity(
            actor="https://example.org/users/vendor",
            object=status,
            target=case,
        )
        event = make_payload(activity)

        AddCaseStatusToCaseReceivedUseCase(dl, event).execute()

        case = dl.read(case.as_id)
        status_ids = [
            (s.as_id if hasattr(s, "as_id") else s) for s in case.case_statuses
        ]
        assert status.as_id in status_ids

    def test_add_case_status_blocks_invalid_em_transition(
        self, monkeypatch, make_payload
    ):
        """Invalid EM transition is blocked; status is not appended."""
        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.wire.as2.rehydration.get_datalayer",
            lambda **_: dl,
        )

        case = VulnerabilityCase(
            id="https://example.org/cases/case_em_guard",
            name="EM Guard Test Case",
        )
        # Seed an existing status with EM.NONE (the initial embargo state)
        initial_status = CaseStatus(
            id="https://example.org/cases/case_em_guard/statuses/s_init",
            context=case.as_id,
            em_state=EM.NONE,
        )
        case.case_statuses.append(initial_status)
        dl.create(case)

        # Try to add a status with EM.ACTIVE — invalid: NONE → ACTIVE
        # skips the required PROPOSED intermediate state
        bad_status = CaseStatus(
            id="https://example.org/cases/case_em_guard/statuses/s_bad",
            context=case.as_id,
            em_state=EM.ACTIVE,
        )
        dl.create(bad_status)

        activity = AddStatusToCaseActivity(
            actor="https://example.org/users/vendor",
            object=bad_status,
            target=case,
        )
        event = make_payload(activity)

        AddCaseStatusToCaseReceivedUseCase(dl, event).execute()

        updated_case = dl.read(case.as_id)
        status_ids = [
            (s.as_id if hasattr(s, "as_id") else s)
            for s in updated_case.case_statuses
        ]
        assert (
            bad_status.as_id not in status_ids
        ), "Bad status should not have been appended"

    def test_add_case_status_allows_valid_em_transition(
        self, monkeypatch, make_payload
    ):
        """Valid EM transition is permitted; status is appended."""
        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.wire.as2.rehydration.get_datalayer",
            lambda **_: dl,
        )

        case = VulnerabilityCase(
            id="https://example.org/cases/case_em_valid",
            name="EM Valid Transition Case",
        )
        initial_status = CaseStatus(
            id="https://example.org/cases/case_em_valid/statuses/s_init",
            context=case.as_id,
            em_state=EM.NONE,
        )
        case.case_statuses.append(initial_status)
        dl.create(case)

        # NONE → PROPOSED is a valid transition
        good_status = CaseStatus(
            id="https://example.org/cases/case_em_valid/statuses/s_good",
            context=case.as_id,
            em_state=EM.PROPOSED,
        )
        dl.create(good_status)

        activity = AddStatusToCaseActivity(
            actor="https://example.org/users/vendor",
            object=good_status,
            target=case,
        )
        event = make_payload(activity)

        AddCaseStatusToCaseReceivedUseCase(dl, event).execute()

        updated_case = dl.read(case.as_id)
        status_ids = [
            (s.as_id if hasattr(s, "as_id") else s)
            for s in updated_case.case_statuses
        ]
        assert good_status.as_id in status_ids

    def test_create_participant_status_stores_status(
        self, monkeypatch, make_payload
    ):
        """create_participant_status persists the ParticipantStatus."""
        dl = TinyDbDataLayer(db_path=None)

        pstatus = ParticipantStatus(
            id="https://example.org/cases/case_ps1/participants/p1/statuses/s1",
            context="https://example.org/cases/case_ps1",
        )
        case_ps1 = VulnerabilityCase(
            id="https://example.org/cases/case_ps1",
            name="PS Case 1",
        )
        activity = CreateStatusForParticipantActivity(
            actor="https://example.org/users/vendor",
            object=pstatus,
            context=case_ps1,
        )

        event = make_payload(activity)

        CreateParticipantStatusReceivedUseCase(dl, event).execute()

        stored = dl.get(pstatus.as_type.value, pstatus.as_id)
        assert stored is not None

    def test_add_participant_status_to_participant_appends_status(
        self, monkeypatch, make_payload
    ):
        """add_participant_status_to_participant appends status to participant."""
        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.wire.as2.rehydration.get_datalayer",
            lambda **_: dl,
        )

        participant = CaseParticipant(
            id="https://example.org/cases/case_ps2/participants/p2",
            context="https://example.org/cases/case_ps2",
            attributed_to="https://example.org/users/vendor",
        )
        pstatus = ParticipantStatus(
            id="https://example.org/cases/case_ps2/participants/p2/statuses/s2",
            context="https://example.org/cases/case_ps2",
        )
        case_ps2 = VulnerabilityCase(
            id="https://example.org/cases/case_ps2",
            name="PS Case 2",
        )
        dl.create(participant)
        dl.create(pstatus)

        activity = AddStatusToParticipantActivity(
            actor="https://example.org/users/vendor",
            object=pstatus,
            target=participant,
            context=case_ps2,
        )
        event = make_payload(activity)

        AddParticipantStatusToParticipantReceivedUseCase(dl, event).execute()

        participant = dl.read(participant.as_id)
        status_ids = [
            (s.as_id if hasattr(s, "as_id") else s)
            for s in participant.participant_statuses
        ]
        assert pstatus.as_id in status_ids
