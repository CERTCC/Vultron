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
            target=vendor_id,
        )
        from vultron.core.models.base import VultronObject

        event = SubmitReportReceivedEvent(
            semantic_type=MessageSemantics.SUBMIT_REPORT,
            activity_id=activity_id,
            actor_id="https://example.org/users/finder",
            object_=report,
            activity=activity,
            target=VultronObject(id_=vendor_id, type_="Actor"),
        )
        return (report, event)

    def test_submit_report_no_warning_on_duplicate_report(self, caplog):
        """SubmitReportReceivedUseCase emits no WARNING when report already stored.

        The inbox endpoint pre-stores the nested VulnerabilityReport before
        dispatching; the use case must degrade to DEBUG, not WARNING.
        Per D5-6-DUP.
        """
        import logging

        from vultron.core.models.activity import VultronOffer
        from vultron.core.models.case_actor import VultronCaseActor

        report, event = self._make_submit_event(
            "https://example.org/reports/r-dup-1",
            "https://example.org/activities/offer-dup-1",
        )
        dl = TinyDbDataLayer(db_path=None)
        # Simulate inbox pre-storage of the nested objects.
        dl.save(report)
        # CreateFinderParticipantNode reads the vendor actor from DataLayer.
        dl.save(VultronCaseActor(id_="https://example.org/actors/vendor"))
        # Pre-store the Offer so CreateFinderParticipantNode can read it.
        offer_obj = VultronOffer(
            id_="https://example.org/activities/offer-dup-1",
            actor="https://example.org/users/finder",
            object_=report.id_,
            target="https://example.org/actors/vendor",
        )
        dl.save(offer_obj)

        with caplog.at_level(logging.WARNING):
            SubmitReportReceivedUseCase(dl, event).execute()

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
        dl = TinyDbDataLayer(db_path=None)
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


class TestSubmitReportLogMessages:
    """Tests that SubmitReportReceivedUseCase emits clear log messages."""

    def test_submit_report_log_identifies_vendor_and_report(self, caplog):
        """SubmitReportReceivedUseCase logs vendor actor and report IDs.

        Per ADR-0015, SubmitReportReceivedUseCase now invokes the
        receive_report_case_tree BT using the vendor's actor_id
        (request.target_id).  The log must identify both the vendor and
        the report being received.  Per D5-6-STATE.
        """
        import logging

        from vultron.core.models.activity import VultronOffer
        from vultron.core.models.base import VultronObject
        from vultron.core.models.case_actor import VultronCaseActor

        report = VultronReport(id_="https://example.org/reports/r-log-1")
        activity = VultronActivity(
            id_="https://example.org/activities/submit-log-1",
            type_="Offer",
            actor="https://example.org/users/finder",
            target="https://example.org/actors/vendor",
        )
        event = SubmitReportReceivedEvent(
            semantic_type=MessageSemantics.SUBMIT_REPORT,
            activity_id="https://example.org/activities/submit-log-1",
            actor_id="https://example.org/users/finder",
            object_=report,
            activity=activity,
            target=VultronObject(
                id_="https://example.org/actors/vendor", type_="Actor"
            ),
        )

        dl = TinyDbDataLayer(db_path=None)
        # CreateFinderParticipantNode reads the vendor actor from DataLayer.
        dl.save(VultronCaseActor(id_="https://example.org/actors/vendor"))
        # Pre-store the offer so CreateFinderParticipantNode can look it up.
        offer_obj = VultronOffer(
            id_="https://example.org/activities/submit-log-1",
            actor="https://example.org/users/finder",
            object_=report.id_,
            target="https://example.org/actors/vendor",
        )
        dl.save(offer_obj)

        with caplog.at_level(logging.INFO):
            SubmitReportReceivedUseCase(dl, event).execute()

        log_text = " ".join(r.message for r in caplog.records)
        assert (
            "https://example.org/actors/vendor" in log_text
        ), "Log must include the vendor (receiving) actor ID"
        assert (
            "https://example.org/reports/r-log-1" in log_text
        ), "Log must include the report ID"


class TestSubmitReportCreatesCase:
    """Tests that SubmitReportReceivedUseCase creates a case at RM.RECEIVED.

    Per ADR-0015, case creation moved from validate_report (RM.VALID) to
    SubmitReportReceivedUseCase (RM.RECEIVED) via receive_report_case_tree.
    """

    VENDOR_ID = "https://example.org/actors/vendor"
    FINDER_ID = "https://example.org/users/finder"
    REPORT_ID = "https://example.org/reports/r-case-1"
    OFFER_ID = "https://example.org/activities/offer-case-1"

    def _make_event_and_dl(
        self,
        report_id: str = REPORT_ID,
        offer_id: str = OFFER_ID,
        vendor_id: str = VENDOR_ID,
        finder_id: str = FINDER_ID,
    ):
        from vultron.core.models.activity import VultronOffer
        from vultron.core.models.base import VultronObject
        from vultron.core.models.case_actor import VultronCaseActor

        report = VultronReport(id_=report_id)
        activity = VultronActivity(
            id_=offer_id,
            type_="Offer",
            actor=finder_id,
            target=vendor_id,
        )
        event = SubmitReportReceivedEvent(
            semantic_type=MessageSemantics.SUBMIT_REPORT,
            activity_id=offer_id,
            actor_id=finder_id,
            object_=report,
            activity=activity,
            target=VultronObject(id_=vendor_id, type_="Actor"),
        )
        dl = TinyDbDataLayer(db_path=None)
        # CreateCaseNode reads the report from DataLayer.
        dl.save(report)
        # CreateFinderParticipantNode reads the vendor actor from DataLayer.
        vendor_actor = VultronCaseActor(id_=vendor_id)
        dl.save(vendor_actor)
        offer_obj = VultronOffer(
            id_=offer_id,
            actor=finder_id,
            object_=report.id_,
            target=vendor_id,
        )
        dl.save(offer_obj)
        return event, dl

    def test_submit_report_creates_case_at_received(self):
        """SubmitReportReceivedUseCase creates a VulnerabilityCase in DataLayer.

        Per ADR-0015, the case is created by receive_report_case_tree during
        RM.RECEIVED processing.
        """
        event, dl = self._make_event_and_dl()
        SubmitReportReceivedUseCase(dl, event).execute()

        all_cases = dl.get_all("VulnerabilityCase")
        assert len(all_cases) >= 1, "Expected at least one VulnerabilityCase"
        # The case must reference our report ID.
        report_ids = [
            rid
            for c in all_cases
            for rid in (c.get("data_", {}) or {}).get(
                "vulnerability_reports", []
            )
        ]
        assert (
            self.REPORT_ID in report_ids
        ), f"VulnerabilityCase should reference report {self.REPORT_ID}"

    def test_submit_report_creates_vendor_participant_at_received(self):
        """SubmitReportReceivedUseCase creates vendor CaseParticipant at RM.RECEIVED."""
        event, dl = self._make_event_and_dl()
        SubmitReportReceivedUseCase(dl, event).execute()

        participants = dl.get_all("CaseParticipant")
        vendor_participants = [
            p
            for p in participants
            if (p.get("data_", {}) or {}).get("attributed_to")
            == self.VENDOR_ID
        ]
        assert (
            len(vendor_participants) >= 1
        ), f"Expected a CaseParticipant for vendor {self.VENDOR_ID}"

    def test_submit_report_creates_finder_participant_accepted(self):
        """SubmitReportReceivedUseCase creates finder's RM.ACCEPTED status.

        The finder submitted the report, so the BT records RM.ACCEPTED for
        them via CreateFinderParticipantNode.
        """
        event, dl = self._make_event_and_dl()
        SubmitReportReceivedUseCase(dl, event).execute()

        all_statuses = dl.get_all("ParticipantStatus")
        finder_accepted = [
            s
            for s in all_statuses
            if (s.get("data_", {}) or {}).get("attributed_to")
            == self.FINDER_ID
            and (s.get("data_", {}) or {}).get("rm_state") == RM.ACCEPTED.value
        ]
        assert (
            len(finder_accepted) >= 1
        ), f"Expected a RM.ACCEPTED ParticipantStatus for finder {self.FINDER_ID}"

    def test_submit_report_case_creation_is_idempotent(self):
        """Calling SubmitReportReceivedUseCase twice creates only one case."""
        event, dl = self._make_event_and_dl()
        SubmitReportReceivedUseCase(dl, event).execute()
        SubmitReportReceivedUseCase(dl, event).execute()

        all_cases = dl.get_all("VulnerabilityCase")
        report_cases = [
            c
            for c in all_cases
            if self.REPORT_ID
            in (c.get("data_", {}) or {}).get("vulnerability_reports", [])
        ]
        assert len(report_cases) == 1, (
            f"Expected exactly one VulnerabilityCase for report {self.REPORT_ID} after"
            " idempotent calls"
        )

    def test_submit_report_skips_case_creation_without_target(self):
        """SubmitReportReceivedUseCase skips BT when vendor_actor_id is None.

        If Offer.target is absent, the use case logs a WARNING and returns
        without creating a case.
        """
        report = VultronReport(id_="https://example.org/reports/r-no-target-1")
        activity = VultronActivity(
            id_="https://example.org/activities/offer-no-target-1",
            type_="Offer",
            actor=self.FINDER_ID,
        )
        event = SubmitReportReceivedEvent(
            semantic_type=MessageSemantics.SUBMIT_REPORT,
            activity_id="https://example.org/activities/offer-no-target-1",
            actor_id=self.FINDER_ID,
            object_=report,
            activity=activity,
        )
        dl = TinyDbDataLayer(db_path=None)

        SubmitReportReceivedUseCase(dl, event).execute()

        all_cases = dl.get_all("VulnerabilityCase")
        assert (
            all_cases == []
        ), "Expected no VulnerabilityCase when vendor_actor_id is None"
