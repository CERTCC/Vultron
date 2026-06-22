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
"""Tests for CreateReportReceivedUseCase: creation, no-standalone-status, duplicate handling."""

from unittest.mock import MagicMock

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.models.activity import VultronActivity
from vultron.core.models.events import MessageSemantics
from vultron.core.models.events.report import (
    CreateReportReceivedEvent,
    SubmitReportReceivedEvent,
)
from vultron.core.models.report import VultronReport
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
        dl = SqliteDataLayer("sqlite:///:memory:")
        report = VulnerabilityReport(
            name="TEST-003", content="Test report for shim delegation"
        )
        create_activity = as_Create(
            actor="https://example.org/users/tester", object_=report
        )
        event = make_payload(create_activity)
        result = CreateReportReceivedUseCase(dl, event).execute()
        assert result is None


class TestCreateReportNoStandaloneParticipantStatus:
    """CreateReportReceivedUseCase must NOT create standalone ParticipantStatus.

    Per IDEA-260408-01-6: RM history lives in VultronParticipant.participant_statuses
    within case objects, not in standalone ParticipantStatus records.
    """

    def test_create_report_does_not_persist_participant_status(self):
        """CreateReportReceivedUseCase stores the report and activity only."""
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

        dl = SqliteDataLayer("sqlite:///:memory:")
        CreateReportReceivedUseCase(dl, event).execute()

        all_statuses = dl.get_all("ParticipantStatus")
        assert all_statuses == [], (
            "CreateReportReceivedUseCase must not create standalone "
            "ParticipantStatus records (IDEA-260408-01-6)"
        )

    def test_create_report_still_stores_report_and_activity(self):
        """CreateReportReceivedUseCase still stores the report and activity."""
        report = VultronReport(id_="https://example.org/reports/r-store-1")
        activity = VultronActivity(
            id_="https://example.org/activities/create-store-1",
            type_="Create",
            actor="https://example.org/users/finder",
        )
        event = CreateReportReceivedEvent(
            semantic_type=MessageSemantics.CREATE_REPORT,
            activity_id="https://example.org/activities/create-store-1",
            actor_id="https://example.org/users/finder",
            object_=report,
            activity=activity,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        CreateReportReceivedUseCase(dl, event).execute()

        stored_report = dl.read("https://example.org/reports/r-store-1")
        assert (
            stored_report is not None
        ), "VulnerabilityReport should be stored"


class TestDuplicateReportHandling:
    """Tests that duplicate VulnerabilityReport warnings are not emitted.

    The inbox endpoint pre-stores nested objects before dispatching to use
    cases.  When the use case then tries to store the same report, the
    duplicate must be silently demoted to DEBUG — not WARNING — because it
    is an expected idempotency condition, not a real error (D5-6-DUP).
    """

    def _make_submit_event(
        self,
        report_id: str,
        activity_id: str,
        vendor_id: str = "https://example.org/actors/vendor",
    ):
        report = VultronReport(id_=report_id)
        activity = VultronActivity(
            id_=activity_id,
            type_="Offer",
            actor="https://example.org/users/finder",
            to=[vendor_id],
        )
        event = SubmitReportReceivedEvent(
            semantic_type=MessageSemantics.SUBMIT_REPORT,
            activity_id=activity_id,
            actor_id="https://example.org/users/finder",
            object_=report,
            activity=activity,
            receiving_actor_id=vendor_id,
        )
        return (report, event)

    def test_submit_report_no_warning_on_duplicate_report(
        self, caplog, monkeypatch
    ):
        """SubmitReportReceivedUseCase emits no WARNING when report already stored.

        The inbox endpoint pre-stores the nested VulnerabilityReport before
        dispatching; the use case must degrade to DEBUG, not WARNING.
        Per D5-6-DUP.
        """
        import logging

        from vultron.core.models.case_actor import VultronCaseActor
        from vultron.core.use_cases.received import report as report_use_cases

        monkeypatch.setattr(
            report_use_cases,
            "_run_submit_report_case_creation",
            lambda *args, **kwargs: None,
        )

        report, event = self._make_submit_event(
            "https://example.org/reports/r-dup-1",
            "https://example.org/activities/offer-dup-1",
        )
        dl = SqliteDataLayer("sqlite:///:memory:")
        # Simulate inbox pre-storage of the nested objects.
        dl.save(report)
        # CreateCaseParticipantNode reads the vendor actor from DataLayer.
        dl.save(VultronCaseActor(id_="https://example.org/actors/vendor"))

        with caplog.at_level(logging.WARNING):
            SubmitReportReceivedUseCase(
                dl, event, trigger_activity=TriggerActivityAdapter(dl)
            ).execute()

        warning_records = [
            r for r in caplog.records if r.levelno >= logging.WARNING
        ]
        assert warning_records == [], (
            "No WARNING should be emitted when VulnerabilityReport is "
            f"pre-stored by inbox endpoint; got: {[r.message for r in warning_records]}"
        )

    def test_create_report_no_warning_on_duplicate_report(self, caplog):
        """CreateReportReceivedUseCase emits no WARNING when report already stored.

        Per D5-6-DUP.
        """
        import logging

        report = VultronReport(
            id_="https://example.org/reports/r-dup-create-1"
        )
        activity = VultronActivity(
            id_="https://example.org/activities/create-dup-1",
            type_="Create",
            actor="https://example.org/users/finder",
        )
        event = CreateReportReceivedEvent(
            semantic_type=MessageSemantics.CREATE_REPORT,
            activity_id="https://example.org/activities/create-dup-1",
            actor_id="https://example.org/users/finder",
            object_=report,
            activity=activity,
        )
        dl = SqliteDataLayer("sqlite:///:memory:")
        # Simulate inbox pre-storage of the nested object.
        dl.save(report)

        with caplog.at_level(logging.WARNING):
            CreateReportReceivedUseCase(dl, event).execute()

        warning_records = [
            r for r in caplog.records if r.levelno >= logging.WARNING
        ]
        assert warning_records == [], (
            "No WARNING should be emitted when VulnerabilityReport is "
            f"pre-stored by inbox endpoint; got: {[r.message for r in warning_records]}"
        )
