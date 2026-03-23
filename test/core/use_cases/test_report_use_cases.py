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

from unittest.mock import MagicMock

from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Create
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)
from vultron.core.models.events import MessageSemantics
from vultron.core.use_cases.report import (
    CreateReportReceivedUseCase,
    SubmitReportReceivedUseCase,
    AckReportReceivedUseCase,
)
from vultron.core.use_cases.case import CreateCaseReceivedUseCase


class TestUseCaseExecution:
    """Test that use cases execute with valid semantics."""

    def test_create_report_executes_with_valid_semantics(self, make_payload):
        """CreateReportReceivedUseCase executes when semantics match."""
        report = VulnerabilityReport(
            name="TEST-002", content="Test vulnerability report"
        )
        create_activity = as_Create(
            actor="https://example.org/users/tester", object=report
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
            actor="https://example.org/users/tester", object=case
        )
        event = make_payload(create_activity)

        mock_dl = MagicMock()
        result = CreateCaseReceivedUseCase(mock_dl, event).execute()
        assert result is None

    def test_use_case_executes_with_real_datalayer(self, make_payload):
        """CreateReportReceivedUseCase executes without raising on real DataLayer."""
        from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer

        dl = TinyDbDataLayer(db_path=None)
        report = VulnerabilityReport(
            name="TEST-003", content="Test report for shim delegation"
        )
        create_activity = as_Create(
            actor="https://example.org/users/tester", object=report
        )
        event = make_payload(create_activity)
        result = CreateReportReceivedUseCase(dl, event).execute()
        assert result is None


class TestReportReceiptRM:
    """Tests that report-receipt use cases fire the RM START→RECEIVED transition."""

    def setup_method(self):
        """Clear STATUS layer before each test to avoid cross-test pollution."""
        from vultron.core.models.status import get_status_layer

        get_status_layer().clear()

    def test_create_report_sets_rm_received(self):
        """CreateReportReceivedUseCase sets RM.RECEIVED in the STATUS layer."""
        from vultron.core.models.status import get_status_layer
        from vultron.core.states.rm import RM
        from vultron.core.models.events.report import CreateReportReceivedEvent
        from vultron.core.models.report import VultronReport
        from vultron.core.models.activity import VultronActivity

        report = VultronReport(as_id="https://example.org/reports/r-create-1")
        activity = VultronActivity(
            id="https://example.org/activities/create-1",
            type="Create",
            actor="https://example.org/users/finder",
        )
        event = CreateReportReceivedEvent(
            semantic_type=MessageSemantics.CREATE_REPORT,
            activity_id="https://example.org/activities/create-1",
            actor_id="https://example.org/users/finder",
            object_id="https://example.org/reports/r-create-1",
            object_type="VulnerabilityReport",
            report=report,
            activity=activity,
        )

        mock_dl = MagicMock()
        CreateReportReceivedUseCase(mock_dl, event).execute()

        sl = get_status_layer()
        actor_key = "https://example.org/users/finder"
        report_key = "https://example.org/reports/r-create-1"
        assert report_key in sl.get("VulnerabilityReport", {})
        assert (
            sl["VulnerabilityReport"][report_key][actor_key]["status"]
            == RM.RECEIVED.value
        )

    def test_submit_report_sets_rm_received(self):
        """SubmitReportReceivedUseCase sets RM.RECEIVED in the STATUS layer."""
        from vultron.core.models.status import get_status_layer
        from vultron.core.states.rm import RM
        from vultron.core.models.events.report import SubmitReportReceivedEvent
        from vultron.core.models.report import VultronReport
        from vultron.core.models.activity import VultronActivity

        report = VultronReport(as_id="https://example.org/reports/r-submit-1")
        activity = VultronActivity(
            id="https://example.org/activities/submit-1",
            type="Offer",
            actor="https://example.org/users/finder",
        )
        event = SubmitReportReceivedEvent(
            semantic_type=MessageSemantics.SUBMIT_REPORT,
            activity_id="https://example.org/activities/submit-1",
            actor_id="https://example.org/users/finder",
            object_id="https://example.org/reports/r-submit-1",
            object_type="VulnerabilityReport",
            report=report,
            activity=activity,
        )

        mock_dl = MagicMock()
        SubmitReportReceivedUseCase(mock_dl, event).execute()

        sl = get_status_layer()
        actor_key = "https://example.org/users/finder"
        report_key = "https://example.org/reports/r-submit-1"
        assert report_key in sl.get("VulnerabilityReport", {})
        assert (
            sl["VulnerabilityReport"][report_key][actor_key]["status"]
            == RM.RECEIVED.value
        )

    def test_ack_report_sets_rm_received_for_inner_report(self):
        """AckReportReceivedUseCase sets RM.RECEIVED using inner_object_id (the report)."""
        from vultron.core.models.status import get_status_layer
        from vultron.core.states.rm import RM
        from vultron.core.models.events.report import AckReportReceivedEvent
        from vultron.core.models.activity import VultronActivity

        activity = VultronActivity(
            id="https://example.org/activities/ack-1",
            type="Read",
            actor="https://example.org/users/coordinator",
        )
        event = AckReportReceivedEvent(
            semantic_type=MessageSemantics.ACK_REPORT,
            activity_id="https://example.org/activities/ack-1",
            actor_id="https://example.org/users/coordinator",
            object_id="https://example.org/offers/offer-1",
            object_type="Offer",
            inner_object_id="https://example.org/reports/r-ack-1",
            inner_object_type="VulnerabilityReport",
            activity=activity,
        )

        mock_dl = MagicMock()
        AckReportReceivedUseCase(mock_dl, event).execute()

        sl = get_status_layer()
        actor_key = "https://example.org/users/coordinator"
        report_key = "https://example.org/reports/r-ack-1"
        assert report_key in sl.get("VulnerabilityReport", {})
        assert (
            sl["VulnerabilityReport"][report_key][actor_key]["status"]
            == RM.RECEIVED.value
        )
