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

from typing import cast

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.states.em import EM
from vultron.core.use_cases.received.status import (
    AddCaseStatusToCaseReceivedUseCase,
    AddParticipantStatusToParticipantReceivedUseCase,
    CreateCaseStatusReceivedUseCase,
    CreateParticipantStatusReceivedUseCase,
)
from vultron.wire.as2.factories import (
    add_status_to_case_activity,
    add_status_to_participant_activity,
    create_case_status_activity,
    create_status_for_participant_activity,
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

        dl = SqliteDataLayer("sqlite:///:memory:")

        case = VulnerabilityCase(
            id_="https://example.org/cases/case_cs1",
            name="Case Status Test",
        )
        status = CaseStatus(
            id_="https://example.org/cases/case_cs1/statuses/s1",
            context=case.id_,
        )
        activity = create_case_status_activity(
            status, actor="https://example.org/users/vendor", context=case.id_
        )

        event = make_payload(activity)

        CreateCaseStatusReceivedUseCase(dl, event).execute()

        stored = dl.get(status.type_.value, status.id_)
        assert stored is not None

    def test_create_case_status_idempotent(self, monkeypatch, make_payload):
        """create_case_status skips storing a duplicate CaseStatus."""
        dl = SqliteDataLayer("sqlite:///:memory:")

        case = VulnerabilityCase(
            id_="https://example.org/cases/case_cs2",
            name="Case Status Idempotent",
        )
        status = CaseStatus(
            id_="https://example.org/cases/case_cs2/statuses/s2",
            context=case.id_,
        )
        dl.create(status)

        activity = create_case_status_activity(
            status, actor="https://example.org/users/vendor", context=case.id_
        )
        event = make_payload(activity)

        CreateCaseStatusReceivedUseCase(dl, event).execute()

        stored = dl.get(status.type_.value, status.id_)
        assert stored is not None

    def test_add_case_status_to_case_appends_status(
        self, monkeypatch, make_payload
    ):
        """add_case_status_to_case appends status ID to case.case_statuses."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_cs3",
            name="Add Status Case",
        )
        status = CaseStatus(
            id_="https://example.org/cases/case_cs3/statuses/s3",
            context=case.id_,
        )
        dl.create(case)
        dl.create(status)

        activity = add_status_to_case_activity(
            status, target=case, actor="https://example.org/users/vendor"
        )
        event = make_payload(activity)

        AddCaseStatusToCaseReceivedUseCase(dl, event).execute()

        case = dl.read(case.id_)
        assert case is not None
        case = cast(VulnerabilityCase, case)
        status_ids = [getattr(s, "id_", s) for s in case.case_statuses]
        assert status.id_ in status_ids

    def test_add_case_status_blocks_invalid_em_transition(
        self, monkeypatch, make_payload
    ):
        """Invalid EM transition is blocked; status is not appended."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_em_guard",
            name="EM Guard Test Case",
        )
        # Seed an existing status with EM.NONE (the initial embargo state)
        initial_status = CaseStatus(
            id_="https://example.org/cases/case_em_guard/statuses/s_init",
            context=case.id_,
            em_state=EM.NONE,
        )
        case.case_statuses.append(initial_status)
        dl.create(case)

        # Try to add a status with EM.ACTIVE — invalid: NONE → ACTIVE
        # skips the required PROPOSED intermediate state
        bad_status = CaseStatus(
            id_="https://example.org/cases/case_em_guard/statuses/s_bad",
            context=case.id_,
            em_state=EM.ACTIVE,
        )
        dl.create(bad_status)

        activity = add_status_to_case_activity(
            bad_status, target=case, actor="https://example.org/users/vendor"
        )
        event = make_payload(activity)

        AddCaseStatusToCaseReceivedUseCase(dl, event).execute()

        updated_case = dl.read(case.id_)
        assert updated_case is not None
        updated_case = cast(VulnerabilityCase, updated_case)
        status_ids = [getattr(s, "id_", s) for s in updated_case.case_statuses]
        assert (
            bad_status.id_ not in status_ids
        ), "Bad status should not have been appended"

    def test_add_case_status_allows_valid_em_transition(
        self, monkeypatch, make_payload
    ):
        """Valid EM transition is permitted; status is appended."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_em_valid",
            name="EM Valid Transition Case",
        )
        initial_status = CaseStatus(
            id_="https://example.org/cases/case_em_valid/statuses/s_init",
            context=case.id_,
            em_state=EM.NONE,
        )
        case.case_statuses.append(initial_status)
        dl.create(case)

        # NONE → PROPOSED is a valid transition
        good_status = CaseStatus(
            id_="https://example.org/cases/case_em_valid/statuses/s_good",
            context=case.id_,
            em_state=EM.PROPOSED,
        )
        dl.create(good_status)

        activity = add_status_to_case_activity(
            good_status, target=case, actor="https://example.org/users/vendor"
        )
        event = make_payload(activity)

        AddCaseStatusToCaseReceivedUseCase(dl, event).execute()

        updated_case = dl.read(case.id_)
        assert updated_case is not None
        updated_case = cast(VulnerabilityCase, updated_case)
        status_ids = [getattr(s, "id_", s) for s in updated_case.case_statuses]
        assert good_status.id_ in status_ids

    def test_create_participant_status_stores_status(
        self, monkeypatch, make_payload
    ):
        """create_participant_status persists the ParticipantStatus."""
        dl = SqliteDataLayer("sqlite:///:memory:")

        pstatus = ParticipantStatus(
            id_="https://example.org/cases/case_ps1/participants/p1/statuses/s1",
            context="https://example.org/cases/case_ps1",
        )
        case_ps1 = VulnerabilityCase(
            id_="https://example.org/cases/case_ps1",
            name="PS Case 1",
        )
        activity = create_status_for_participant_activity(
            pstatus, actor="https://example.org/users/vendor", context=case_ps1
        )

        event = make_payload(activity)

        CreateParticipantStatusReceivedUseCase(dl, event).execute()

        stored = dl.get(pstatus.type_.value, pstatus.id_)
        assert stored is not None

    def test_add_participant_status_to_participant_appends_status(
        self, monkeypatch, make_payload
    ):
        """add_participant_status_to_participant appends status to participant."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        participant = CaseParticipant(
            id_="https://example.org/cases/case_ps2/participants/p2",
            context="https://example.org/cases/case_ps2",
            attributed_to="https://example.org/users/vendor",
        )
        pstatus = ParticipantStatus(
            id_="https://example.org/cases/case_ps2/participants/p2/statuses/s2",
            context="https://example.org/cases/case_ps2",
        )
        case_ps2 = VulnerabilityCase(
            id_="https://example.org/cases/case_ps2",
            name="PS Case 2",
        )
        # Register the vendor actor as a participant so step 1 passes
        case_ps2.case_participants.append(participant.id_)
        case_ps2.actor_participant_index[
            "https://example.org/users/vendor"
        ] = participant.id_
        dl.create(participant)
        dl.create(pstatus)
        dl.create(case_ps2)

        activity = add_status_to_participant_activity(
            pstatus,
            target=participant,
            actor="https://example.org/users/vendor",
            context=case_ps2,
        )
        event = make_payload(activity)

        AddParticipantStatusToParticipantReceivedUseCase(dl, event).execute()

        participant = dl.read(participant.id_)
        assert participant is not None
        participant = cast(CaseParticipant, participant)
        status_ids = [
            getattr(s, "id_", s) for s in participant.participant_statuses
        ]
        assert pstatus.id_ in status_ids
