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
"""Tests for report and case use-case classes."""

from typing import cast
from unittest.mock import MagicMock

from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
from vultron.core.models.activity import VultronActivity
from vultron.core.models.events import MessageSemantics
from vultron.core.models.events.report import (
    CreateReportReceivedEvent,
    SubmitReportReceivedEvent,
)
from vultron.core.models.report import VultronReport
from vultron.core.states.rm import RM
from vultron.core.use_cases._helpers import _report_phase_status_id
from vultron.core.use_cases.received.case import CreateCaseReceivedUseCase
from vultron.core.use_cases.received.report import (
    CreateReportReceivedUseCase,
    SubmitReportReceivedUseCase,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Create
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)


class TestUseCaseExecution:
    """Test that use cases execute with valid semantics."""

    def test_create_report_executes_with_valid_semantics(self, make_payload):
        """CreateReportReceivedUseCase executes when semantics match."""
        report = VulnerabilityReport(
            name="TEST-002", content="Test vulnerability report"
        )
        create_activity = as_Create(
            actor="https://example.org/users/tester", object_=report
        )
        event = make_payload(create_activity)

        mock_dl = MagicMock()
        result = CreateReportReceivedUseCase(mock_dl, event).execute()
        assert result is None

    def test_create_case_executes_with_valid_semantics(self, make_payload):
        """CreateCaseReceivedUseCase executes when semantics match."""
        case = VulnerabilityCase(
            name="TEST-CASE-002", content="Test vulnerability case"
        )
        create_activity = as_Create(
            actor="https://example.org/users/tester", object_=case
        )
        event = make_payload(create_activity)

        mock_dl = MagicMock()
        result = CreateCaseReceivedUseCase(mock_dl, event).execute()
        assert result is None

    def test_use_case_executes_with_real_datalayer(self, make_payload):
        """CreateReportReceivedUseCase executes without raising on real DataLayer."""
        dl = TinyDbDataLayer(db_path=None)
        report = VulnerabilityReport(
            name="TEST-003", content="Test report for shim delegation"
        )
        create_activity = as_Create(
            actor="https://example.org/users/tester", object_=report
        )
        event = make_payload(create_activity)
        result = CreateReportReceivedUseCase(dl, event).execute()
        assert result is None


class TestReportReceiptPersistsParticipantStatus:
    """Tests that report-receipt use cases persist a VultronParticipantStatus record."""

    def test_create_report_persists_participant_status(self):
        """CreateReportReceivedUseCase persists a RM.RECEIVED ParticipantStatus."""
        report = VultronReport(id_="https://example.org/reports/r-persist-1")
        activity = VultronActivity(
            id_="https://example.org/activities/create-p1",
            type_="Create",
            actor="https://example.org/users/finder",
        )
        event = CreateReportReceivedEvent(
            semantic_type=MessageSemantics.CREATE_REPORT,
            activity_id="https://example.org/activities/create-p1",
            actor_id="https://example.org/users/finder",
            object_=report,
            activity=activity,
        )

        dl = TinyDbDataLayer(db_path=None)
        CreateReportReceivedUseCase(dl, event).execute()

        expected_id = _report_phase_status_id(
            "https://example.org/users/finder",
            "https://example.org/reports/r-persist-1",
            RM.RECEIVED.value,
        )
        stored = dl.get("ParticipantStatus", expected_id)
        assert (
            stored is not None
        ), "Expected a ParticipantStatus record in DataLayer"
        stored_record = cast(dict[str, object], stored)
        data = cast(dict[str, object], stored_record["data_"])
        assert data["rm_state"] == RM.RECEIVED.value
        assert data["context"] == "https://example.org/reports/r-persist-1"
        assert data["attributed_to"] == "https://example.org/users/finder"

    def test_submit_report_persists_finder_participant_status_as_accepted(
        self,
    ):
        """SubmitReportReceivedUseCase persists a RM.ACCEPTED ParticipantStatus for the finder.

        A finder who submits a report is at RM.ACCEPTED from their perspective
        (they created and chose to submit the report). Per D5-6-STATE.
        """
        report = VultronReport(id_="https://example.org/reports/r-persist-2")
        activity = VultronActivity(
            id_="https://example.org/activities/submit-p1",
            type_="Offer",
            actor="https://example.org/users/finder",
        )
        event = SubmitReportReceivedEvent(
            semantic_type=MessageSemantics.SUBMIT_REPORT,
            activity_id="https://example.org/activities/submit-p1",
            actor_id="https://example.org/users/finder",
            object_=report,
            activity=activity,
        )

        dl = TinyDbDataLayer(db_path=None)
        SubmitReportReceivedUseCase(dl, event).execute()

        expected_id = _report_phase_status_id(
            "https://example.org/users/finder",
            "https://example.org/reports/r-persist-2",
            RM.ACCEPTED.value,
        )
        stored = dl.get("ParticipantStatus", expected_id)
        assert (
            stored is not None
        ), "Expected a ParticipantStatus record in DataLayer"
        stored_record = cast(dict[str, object], stored)
        data = cast(dict[str, object], stored_record["data_"])
        assert data["rm_state"] == RM.ACCEPTED.value
        assert data["context"] == "https://example.org/reports/r-persist-2"
        assert data["attributed_to"] == "https://example.org/users/finder"

    def test_submit_report_does_not_store_received_status_for_finder(self):
        """SubmitReportReceivedUseCase must NOT create a RM.RECEIVED record for the finder.

        RM.RECEIVED is the vendor's state; RM.ACCEPTED is the finder's state.
        Per D5-6-STATE.
        """
        report = VultronReport(id_="https://example.org/reports/r-no-recv-1")
        activity = VultronActivity(
            id_="https://example.org/activities/submit-no-recv-1",
            type_="Offer",
            actor="https://example.org/users/finder",
        )
        event = SubmitReportReceivedEvent(
            semantic_type=MessageSemantics.SUBMIT_REPORT,
            activity_id="https://example.org/activities/submit-no-recv-1",
            actor_id="https://example.org/users/finder",
            object_=report,
            activity=activity,
        )

        dl = TinyDbDataLayer(db_path=None)
        SubmitReportReceivedUseCase(dl, event).execute()

        received_id = _report_phase_status_id(
            "https://example.org/users/finder",
            "https://example.org/reports/r-no-recv-1",
            RM.RECEIVED.value,
        )
        stored = dl.get("ParticipantStatus", received_id)
        assert stored is None, (
            "SubmitReportReceivedUseCase must not create a RM.RECEIVED record "
            "for the finder; finder state is RM.ACCEPTED"
        )

    def test_submit_report_participant_status_is_idempotent(self):
        """Calling SubmitReportReceivedUseCase twice creates only one ParticipantStatus."""
        report = VultronReport(id_="https://example.org/reports/r-idem-submit")
        activity = VultronActivity(
            id_="https://example.org/activities/submit-idem-1",
            type_="Offer",
            actor="https://example.org/users/finder",
        )
        event = SubmitReportReceivedEvent(
            semantic_type=MessageSemantics.SUBMIT_REPORT,
            activity_id="https://example.org/activities/submit-idem-1",
            actor_id="https://example.org/users/finder",
            object_=report,
            activity=activity,
        )

        dl = TinyDbDataLayer(db_path=None)
        SubmitReportReceivedUseCase(dl, event).execute()
        SubmitReportReceivedUseCase(dl, event).execute()

        all_statuses = dl.get_all("ParticipantStatus")
        expected_id = _report_phase_status_id(
            "https://example.org/users/finder",
            "https://example.org/reports/r-idem-submit",
            RM.ACCEPTED.value,
        )
        matching = [r for r in all_statuses if r.get("id_") == expected_id]
        assert (
            len(matching) == 1
        ), "Expected exactly one ParticipantStatus after idempotent calls"

    def test_create_report_participant_status_is_idempotent(self):
        """Calling CreateReportReceivedUseCase twice creates only one ParticipantStatus."""
        report = VultronReport(id_="https://example.org/reports/r-idem-1")
        activity = VultronActivity(
            id_="https://example.org/activities/create-idem-1",
            type_="Create",
            actor="https://example.org/users/finder",
        )
        event = CreateReportReceivedEvent(
            semantic_type=MessageSemantics.CREATE_REPORT,
            activity_id="https://example.org/activities/create-idem-1",
            actor_id="https://example.org/users/finder",
            object_=report,
            activity=activity,
        )

        dl = TinyDbDataLayer(db_path=None)
        CreateReportReceivedUseCase(dl, event).execute()
        CreateReportReceivedUseCase(dl, event).execute()

        all_statuses = dl.get_all("ParticipantStatus")
        expected_id = _report_phase_status_id(
            "https://example.org/users/finder",
            "https://example.org/reports/r-idem-1",
            RM.RECEIVED.value,
        )
        matching = [r for r in all_statuses if r.get("id_") == expected_id]
        assert (
            len(matching) == 1
        ), "Expected exactly one ParticipantStatus after idempotent calls"


class TestSubmitReportLogMessages:
    """Tests that SubmitReportReceivedUseCase emits clear, actor-identified log messages."""

    def test_submit_report_log_identifies_finder_and_accepted_state(
        self, caplog
    ):
        """SubmitReportReceivedUseCase logs 'Finder RM:' and 'ACCEPTED'.

        The log message must unambiguously identify that the finder's state
        is being recorded (not the local vendor's) and that the state is
        RM.ACCEPTED. Per D5-6-STATE.
        """
        import logging

        report = VultronReport(id_="https://example.org/reports/r-log-1")
        activity = VultronActivity(
            id_="https://example.org/activities/submit-log-1",
            type_="Offer",
            actor="https://example.org/users/finder",
        )
        event = SubmitReportReceivedEvent(
            semantic_type=MessageSemantics.SUBMIT_REPORT,
            activity_id="https://example.org/activities/submit-log-1",
            actor_id="https://example.org/users/finder",
            object_=report,
            activity=activity,
        )

        dl = TinyDbDataLayer(db_path=None)
        with caplog.at_level(logging.INFO):
            SubmitReportReceivedUseCase(dl, event).execute()

        log_text = " ".join(r.message for r in caplog.records)
        assert (
            "Finder RM" in log_text
        ), "Log must identify the actor whose state is changing as 'Finder RM'"
        assert (
            "ACCEPTED" in log_text
        ), "Log must include 'ACCEPTED' to indicate the finder's RM state"
        assert (
            "https://example.org/users/finder" in log_text
        ), "Log must include the finder's actor ID"
