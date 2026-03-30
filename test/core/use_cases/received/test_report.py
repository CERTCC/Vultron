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
            actor="https://example.org/users/tester", as_object=report
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
            actor="https://example.org/users/tester", as_object=case
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
            actor="https://example.org/users/tester", as_object=report
        )
        event = make_payload(create_activity)
        result = CreateReportReceivedUseCase(dl, event).execute()
        assert result is None


class TestReportReceiptPersistsParticipantStatus:
    """Tests that report-receipt use cases persist a VultronParticipantStatus record."""

    def test_create_report_persists_participant_status(self):
        """CreateReportReceivedUseCase persists a RM.RECEIVED ParticipantStatus."""
        report = VultronReport(as_id="https://example.org/reports/r-persist-1")
        activity = VultronActivity(
            as_id="https://example.org/activities/create-p1",
            as_type="Create",
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

    def test_submit_report_persists_participant_status(self):
        """SubmitReportReceivedUseCase persists a RM.RECEIVED ParticipantStatus."""
        report = VultronReport(as_id="https://example.org/reports/r-persist-2")
        activity = VultronActivity(
            as_id="https://example.org/activities/submit-p1",
            as_type="Offer",
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
            RM.RECEIVED.value,
        )
        stored = dl.get("ParticipantStatus", expected_id)
        assert (
            stored is not None
        ), "Expected a ParticipantStatus record in DataLayer"
        stored_record = cast(dict[str, object], stored)
        data = cast(dict[str, object], stored_record["data_"])
        assert data["rm_state"] == RM.RECEIVED.value
        assert data["context"] == "https://example.org/reports/r-persist-2"
        assert data["attributed_to"] == "https://example.org/users/finder"

    def test_create_report_participant_status_is_idempotent(self):
        """Calling CreateReportReceivedUseCase twice creates only one ParticipantStatus."""
        report = VultronReport(as_id="https://example.org/reports/r-idem-1")
        activity = VultronActivity(
            as_id="https://example.org/activities/create-idem-1",
            as_type="Create",
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
