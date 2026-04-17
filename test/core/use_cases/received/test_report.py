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

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.activity import VultronActivity
from vultron.core.models.base import VultronObject
from vultron.core.models.events import MessageSemantics
from vultron.core.models.events.report import (
    AckReportReceivedEvent,
    CloseReportReceivedEvent,
    CreateReportReceivedEvent,
    InvalidateReportReceivedEvent,
    SubmitReportReceivedEvent,
    ValidateReportReceivedEvent,
)
from vultron.core.models.report import VultronReport
from vultron.core.states.rm import RM
from vultron.core.use_cases._helpers import _report_phase_status_id
from vultron.core.use_cases.received.case import (
    CloseCaseUseCase,
    CreateCaseReceivedUseCase,
    InvalidateCaseUseCase,
)
from vultron.core.use_cases.received.report import (
    AckReportReceivedUseCase,
    CloseReportReceivedUseCase,
    CreateReportReceivedUseCase,
    InvalidateReportReceivedUseCase,
    SubmitReportReceivedUseCase,
    ValidateReportReceivedUseCase,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Create
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)
from vultron.core.models.participant import VultronParticipant


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

        from vultron.core.models.case_actor import VultronCaseActor

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

        dl = SqliteDataLayer("sqlite:///:memory:")
        # CreateCaseParticipantNode reads the vendor actor from DataLayer.
        dl.save(VultronCaseActor(id_="https://example.org/actors/vendor"))

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
        dl = SqliteDataLayer("sqlite:///:memory:")
        # CreateCaseNode reads the report from DataLayer.
        dl.save(report)
        # CreateCaseParticipantNode reads the vendor actor from DataLayer.
        vendor_actor = VultronCaseActor(id_=vendor_id)
        dl.save(vendor_actor)
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
        them via CreateCaseParticipantNode.
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
        dl = SqliteDataLayer("sqlite:///:memory:")

        SubmitReportReceivedUseCase(dl, event).execute()

        all_cases = dl.get_all("VulnerabilityCase")
        assert (
            all_cases == []
        ), "Expected no VulnerabilityCase when vendor_actor_id is None"


class TestCaseLevelUseeCases:
    """Unit tests for InvalidateCaseUseCase, CloseCaseUseCase, ValidateCaseUseCase.

    Per CM-12-005: these are called by report use cases after dereferencing
    report_id to case_id.
    """

    def _make_case_with_participant(
        self, dl: SqliteDataLayer, actor_id: str, initial_rm: RM
    ):
        """Helper: create a VulnerabilityCase with one participant."""
        from vultron.core.models.participant_status import (
            VultronParticipantStatus,
        )

        participant = VultronParticipant(
            id_="https://example.org/participants/p1",
            attributed_to=actor_id,
            context="https://example.org/cases/c1",
            participant_statuses=[
                VultronParticipantStatus(
                    rm_state=initial_rm,
                    context="https://example.org/cases/c1",
                    attributed_to=actor_id,
                )
            ],
        )
        case = VulnerabilityCase(
            id_="https://example.org/cases/c1",
            name="Test Case",
        )
        case.case_participants.append(participant.id_)
        case.actor_participant_index[actor_id] = participant.id_

        dl.save(participant)
        dl.save(case)
        return case, participant

    def test_invalidate_case_transitions_participant_to_invalid(self):
        """InvalidateCaseUseCase sets participant RM state to INVALID."""
        actor_id = "https://example.org/actors/vendor"
        dl = SqliteDataLayer("sqlite:///:memory:")
        case, _ = self._make_case_with_participant(dl, actor_id, RM.RECEIVED)

        InvalidateCaseUseCase(dl, case.id_, actor_id).execute()

        updated_case = cast(VulnerabilityCase, dl.read(case.id_))
        participant_id = updated_case.actor_participant_index[actor_id]
        participant = cast(VultronParticipant, dl.read(participant_id))
        assert participant.participant_statuses[-1].rm_state == RM.INVALID

    def test_close_case_transitions_participant_to_closed(self):
        """CloseCaseUseCase sets participant RM state to CLOSED."""
        actor_id = "https://example.org/actors/vendor"
        dl = SqliteDataLayer("sqlite:///:memory:")
        # CLOSED is only reachable from INVALID, ACCEPTED, or DEFERRED
        case, _ = self._make_case_with_participant(dl, actor_id, RM.INVALID)

        CloseCaseUseCase(dl, case.id_, actor_id).execute()

        updated_case = cast(VulnerabilityCase, dl.read(case.id_))
        participant_id = updated_case.actor_participant_index[actor_id]
        participant = cast(VultronParticipant, dl.read(participant_id))
        assert participant.participant_statuses[-1].rm_state == RM.CLOSED

    def test_invalidate_case_noop_on_missing_case(self, caplog):
        """InvalidateCaseUseCase warns when case_id is not found."""
        import logging

        dl = SqliteDataLayer("sqlite:///:memory:")
        with caplog.at_level(logging.WARNING):
            InvalidateCaseUseCase(
                dl,
                "https://example.org/cases/missing",
                "https://example.org/actors/vendor",
            ).execute()

        assert any(
            "Failed to set RM.INVALID" in r.message for r in caplog.records
        )

    def test_close_case_noop_on_missing_case(self, caplog):
        """CloseCaseUseCase warns when case_id is not found."""
        import logging

        dl = SqliteDataLayer("sqlite:///:memory:")
        with caplog.at_level(logging.WARNING):
            CloseCaseUseCase(
                dl,
                "https://example.org/cases/missing",
                "https://example.org/actors/vendor",
            ).execute()

        assert any(
            "Failed to set RM.CLOSED" in r.message for r in caplog.records
        )


class TestDereferencePatternInReportUseCases:
    """Tests that Invalidate/Close/ValidateReportReceivedUseCase dereference
    report_id to case_id and delegate to case-level use cases (CM-12-005).
    """

    def _setup_case_for_report(
        self,
        dl: SqliteDataLayer,
        report_id: str,
        actor_id: str,
        initial_rm: RM = RM.RECEIVED,
    ):
        """Create a case linked to a report via find_case_by_report_id."""
        from vultron.core.models.participant_status import (
            VultronParticipantStatus,
        )
        from vultron.core.models.report import VultronReport as CoreReport

        report = CoreReport(id_=report_id)
        dl.save(report)

        participant = VultronParticipant(
            id_="https://example.org/participants/p-deref",
            attributed_to=actor_id,
            context="https://example.org/cases/c-deref",
            participant_statuses=[
                VultronParticipantStatus(
                    rm_state=initial_rm,
                    context="https://example.org/cases/c-deref",
                    attributed_to=actor_id,
                )
            ],
        )
        case = VulnerabilityCase(
            id_="https://example.org/cases/c-deref",
            name="Deref Test Case",
        )
        case.vulnerability_reports.append(report_id)
        case.case_participants.append(participant.id_)
        case.actor_participant_index[actor_id] = participant.id_

        dl.save(participant)
        dl.save(case)
        return case, participant

    def test_invalidate_report_delegates_to_case(self):
        """InvalidateReportReceivedUseCase dereferences and sets RM.INVALID."""
        report_id = "https://example.org/reports/r-invalidate-deref"
        actor_id = "https://example.org/actors/vendor"
        dl = SqliteDataLayer("sqlite:///:memory:")
        case, _ = self._setup_case_for_report(dl, report_id, actor_id)

        offer_activity = VultronActivity(
            id_="https://example.org/activities/offer-inv",
            type_="Offer",
            actor="https://example.org/actors/finder",
        )
        event = InvalidateReportReceivedEvent(
            semantic_type=MessageSemantics.INVALIDATE_REPORT,
            activity_id="https://example.org/activities/offer-inv",
            actor_id=actor_id,
            object_=VultronReport(
                id_="https://example.org/activities/offer-inv"
            ),
            inner_object=VultronReport(id_=report_id),
            activity=offer_activity,
        )

        InvalidateReportReceivedUseCase(dl, event).execute()

        updated_case = cast(VulnerabilityCase, dl.read(case.id_))
        participant_id = updated_case.actor_participant_index[actor_id]
        participant = cast(VultronParticipant, dl.read(participant_id))
        assert participant.participant_statuses[-1].rm_state == RM.INVALID

    def test_close_report_delegates_to_case(self):
        """CloseReportReceivedUseCase dereferences and sets RM.CLOSED."""
        report_id = "https://example.org/reports/r-close-deref"
        actor_id = "https://example.org/actors/vendor"
        dl = SqliteDataLayer("sqlite:///:memory:")
        # CLOSED is only reachable from INVALID, ACCEPTED, or DEFERRED
        case, _ = self._setup_case_for_report(
            dl, report_id, actor_id, RM.INVALID
        )

        offer_activity = VultronActivity(
            id_="https://example.org/activities/offer-close",
            type_="Offer",
            actor="https://example.org/actors/finder",
        )
        event = CloseReportReceivedEvent(
            semantic_type=MessageSemantics.CLOSE_REPORT,
            activity_id="https://example.org/activities/offer-close",
            actor_id=actor_id,
            object_=VultronReport(
                id_="https://example.org/activities/offer-close"
            ),
            inner_object=VultronReport(id_=report_id),
            activity=offer_activity,
        )

        CloseReportReceivedUseCase(dl, event).execute()

        updated_case = cast(VulnerabilityCase, dl.read(case.id_))
        participant_id = updated_case.actor_participant_index[actor_id]
        participant = cast(VultronParticipant, dl.read(participant_id))
        assert participant.participant_statuses[-1].rm_state == RM.CLOSED

    def test_invalidate_report_warns_when_no_case(self, caplog):
        """InvalidateReportReceivedUseCase warns when no case linked to report."""
        import logging

        report_id = "https://example.org/reports/r-no-case"
        actor_id = "https://example.org/actors/vendor"
        dl = SqliteDataLayer("sqlite:///:memory:")

        offer_activity = VultronActivity(
            id_="https://example.org/activities/offer-no-case",
            type_="Offer",
            actor="https://example.org/actors/finder",
        )
        event = InvalidateReportReceivedEvent(
            semantic_type=MessageSemantics.INVALIDATE_REPORT,
            activity_id="https://example.org/activities/offer-no-case",
            actor_id=actor_id,
            object_=VultronReport(
                id_="https://example.org/activities/offer-no-case"
            ),
            inner_object=VultronReport(id_=report_id),
            activity=offer_activity,
        )

        with caplog.at_level(logging.WARNING):
            InvalidateReportReceivedUseCase(dl, event).execute()

        assert any(
            "no case found" in r.message.lower() for r in caplog.records
        )

    def test_close_report_warns_when_no_case(self, caplog):
        """CloseReportReceivedUseCase warns when no case linked to report."""
        import logging

        report_id = "https://example.org/reports/r-close-no-case"
        actor_id = "https://example.org/actors/vendor"
        dl = SqliteDataLayer("sqlite:///:memory:")

        offer_activity = VultronActivity(
            id_="https://example.org/activities/offer-close-no-case",
            type_="Offer",
            actor="https://example.org/actors/finder",
        )
        event = CloseReportReceivedEvent(
            semantic_type=MessageSemantics.CLOSE_REPORT,
            activity_id="https://example.org/activities/offer-close-no-case",
            actor_id=actor_id,
            object_=VultronReport(
                id_="https://example.org/activities/offer-close-no-case"
            ),
            inner_object=VultronReport(id_=report_id),
            activity=offer_activity,
        )

        with caplog.at_level(logging.WARNING):
            CloseReportReceivedUseCase(dl, event).execute()

        assert any(
            "no case found" in r.message.lower() for r in caplog.records
        )


class TestAckReportNoStandaloneStatus:
    """AckReportReceivedUseCase must NOT create standalone ParticipantStatus.

    Per IDEA-260408-01-6: RM history lives in VultronParticipant.participant_statuses.
    """

    def test_ack_report_does_not_persist_participant_status(self):
        """AckReportReceivedUseCase stores the activity only, not a status."""
        offer_activity = VultronActivity(
            id_="https://example.org/activities/accept-ack-1",
            type_="Accept",
            actor="https://example.org/actors/vendor",
        )
        event = AckReportReceivedEvent(
            semantic_type=MessageSemantics.ACK_REPORT,
            activity_id="https://example.org/activities/accept-ack-1",
            actor_id="https://example.org/actors/vendor",
            object_=VultronReport(
                id_="https://example.org/activities/offer-ack-1"
            ),
            inner_object=VultronReport(
                id_="https://example.org/reports/r-ack-1"
            ),
            activity=offer_activity,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        AckReportReceivedUseCase(dl, event).execute()

        all_statuses = dl.get_all("ParticipantStatus")
        assert all_statuses == [], (
            "AckReportReceivedUseCase must not create standalone "
            "ParticipantStatus records (IDEA-260408-01-6)"
        )


class TestFullReportFlow:
    """Integration test: Offer(Report) receipt → ValidateReport full flow.

    Per IDEA-260408-01-7 and ADR-0015:
    1. SubmitReportReceivedUseCase creates a VulnerabilityCase at RM.RECEIVED.
    2. ValidateReportReceivedUseCase validates without re-creating the case.
    3. Final state: vendor participant at RM.VALID, finder at RM.ACCEPTED.

    These tests verify the separation of concerns mandated by ADR-0015:
    case creation belongs at RM.RECEIVED, not at RM.VALID.
    """

    VENDOR_ID = "https://example.org/actors/vendor-flow"
    FINDER_ID = "https://example.org/users/finder-flow"
    REPORT_ID = "https://example.org/reports/r-flow-1"
    OFFER_ID = "https://example.org/activities/offer-flow-1"
    ACCEPT_ID = "https://example.org/activities/accept-flow-1"

    def _setup_dl(self):
        """Create a DataLayer pre-seeded with the report, vendor, and offer."""
        from vultron.core.models.activity import VultronOffer
        from vultron.core.models.case_actor import VultronCaseActor

        dl = SqliteDataLayer("sqlite:///:memory:")
        report = VultronReport(id_=self.REPORT_ID)
        vendor = VultronCaseActor(id_=self.VENDOR_ID)
        offer = VultronOffer(
            id_=self.OFFER_ID,
            actor=self.FINDER_ID,
            object_=self.REPORT_ID,
            target=self.VENDOR_ID,
        )
        dl.save(report)
        dl.save(vendor)
        dl.save(offer)
        return dl

    def _make_submit_event(self):
        """Build a SubmitReportReceivedEvent (Offer(Report) from finder to vendor)."""
        activity = VultronActivity(
            id_=self.OFFER_ID,
            type_="Offer",
            actor=self.FINDER_ID,
            target=self.VENDOR_ID,
        )
        report = VultronReport(id_=self.REPORT_ID)
        return SubmitReportReceivedEvent(
            semantic_type=MessageSemantics.SUBMIT_REPORT,
            activity_id=self.OFFER_ID,
            actor_id=self.FINDER_ID,
            object_=report,
            activity=activity,
            target=VultronObject(id_=self.VENDOR_ID, type_="Actor"),
        )

    def _make_validate_event(self):
        """Build a ValidateReportReceivedEvent (Accept(Offer(Report)) from vendor)."""
        activity = VultronActivity(
            id_=self.ACCEPT_ID,
            type_="Accept",
            actor=self.VENDOR_ID,
        )
        offer = VultronObject(id_=self.OFFER_ID, type_="Offer")
        report = VultronReport(id_=self.REPORT_ID)
        return ValidateReportReceivedEvent(
            semantic_type=MessageSemantics.VALIDATE_REPORT,
            activity_id=self.ACCEPT_ID,
            actor_id=self.VENDOR_ID,
            object_=offer,
            inner_object=report,
            activity=activity,
        )

    def test_full_flow_case_created_at_received(self):
        """SubmitReportReceivedUseCase creates exactly one case at RM.RECEIVED.

        Per ADR-0015: case creation happens at RM.RECEIVED, not RM.VALID.
        """
        dl = self._setup_dl()
        SubmitReportReceivedUseCase(dl, self._make_submit_event()).execute()

        cases = dl.get_all("VulnerabilityCase")
        assert len(cases) == 1, "Expected exactly one VulnerabilityCase"
        case_report_ids = [
            rid
            for c in cases
            for rid in (c.get("data_", {}) or {}).get(
                "vulnerability_reports", []
            )
        ]
        assert (
            self.REPORT_ID in case_report_ids
        ), f"VulnerabilityCase must reference report {self.REPORT_ID}"

    def test_full_flow_validate_does_not_recreate_case(self):
        """validate-report does NOT create a new case after Offer(Report) receipt.

        Per ADR-0015: the case was already created at RM.RECEIVED, so
        ValidateReportReceivedUseCase must not create an additional case.
        """
        dl = self._setup_dl()
        SubmitReportReceivedUseCase(dl, self._make_submit_event()).execute()
        cases_after_submit = set(dl.by_type("VulnerabilityCase").keys())

        ValidateReportReceivedUseCase(
            dl, self._make_validate_event()
        ).execute()
        cases_after_validate = set(dl.by_type("VulnerabilityCase").keys())

        assert cases_after_validate == cases_after_submit, (
            "validate-report must not create a new case "
            "(case was created at RM.RECEIVED per ADR-0015)"
        )

    def test_full_flow_vendor_in_rm_valid_after_validate(self):
        """After validate-report, vendor participant has RM.VALID in history.

        Per ADR-0015: validation transitions the vendor's RM state from
        RECEIVED to VALID; this state change must be persisted.  The
        subsequent auto-cascade advances to ACCEPTED, but the VALID record
        is still present in the append-only history.
        """
        dl = self._setup_dl()
        SubmitReportReceivedUseCase(dl, self._make_submit_event()).execute()
        ValidateReportReceivedUseCase(
            dl, self._make_validate_event()
        ).execute()

        valid_id = _report_phase_status_id(
            self.VENDOR_ID, self.REPORT_ID, RM.VALID.value
        )
        assert (
            dl.get("ParticipantStatus", valid_id) is not None
        ), f"Vendor {self.VENDOR_ID} must have RM.VALID in history after validate-report"

    def test_full_flow_vendor_auto_engages_after_validate(self):
        """validate-report auto-cascades to engage-case (RM.VALID → RM.ACCEPTED).

        D5-7-AUTOENG-2: after validate-report succeeds, ValidateCaseUseCase
        automatically invokes SvcEngageCaseUseCase so the vendor's
        CaseParticipant ends at RM.ACCEPTED without a separate trigger call.
        """
        dl = self._setup_dl()
        SubmitReportReceivedUseCase(dl, self._make_submit_event()).execute()
        ValidateReportReceivedUseCase(
            dl, self._make_validate_event()
        ).execute()

        case_obj = cast(
            VulnerabilityCase, dl.find_case_by_report_id(self.REPORT_ID)
        )
        assert (
            case_obj is not None
        ), f"VulnerabilityCase for report '{self.REPORT_ID}' must exist"
        participant_id = case_obj.actor_participant_index.get(self.VENDOR_ID)
        assert (
            participant_id is not None
        ), f"Vendor '{self.VENDOR_ID}' must be in actor_participant_index"
        participant = cast(VultronParticipant, dl.read(participant_id))
        assert (
            participant is not None
        ), f"CaseParticipant '{participant_id}' must exist in DataLayer"
        latest_status = participant.participant_statuses[-1]
        assert latest_status.rm_state == RM.ACCEPTED, (
            f"Vendor must auto-engage to RM.ACCEPTED after validate-report "
            f"(got {latest_status.rm_state})"
        )

    def test_full_flow_finder_remains_rm_accepted(self):
        """Finder participant is RM.ACCEPTED after submit and remains so after validate.

        The finder submitted the report, so they enter RM.ACCEPTED at receipt.
        The subsequent validate-report step must not change the finder's state.
        """
        dl = self._setup_dl()
        SubmitReportReceivedUseCase(dl, self._make_submit_event()).execute()

        accepted_id = _report_phase_status_id(
            self.FINDER_ID, self.REPORT_ID, RM.ACCEPTED.value
        )
        assert (
            dl.get("ParticipantStatus", accepted_id) is not None
        ), f"Finder {self.FINDER_ID} must be RM.ACCEPTED after Offer(Report) receipt"

        ValidateReportReceivedUseCase(
            dl, self._make_validate_event()
        ).execute()

        assert (
            dl.get("ParticipantStatus", accepted_id) is not None
        ), f"Finder {self.FINDER_ID} must remain RM.ACCEPTED after validate-report"

    def test_full_flow_produces_correct_final_state(self):
        """Full flow from Offer receipt to validation produces the expected state.

        Verifies the combined invariants of ADR-0015 and D5-7-AUTOENG-2:
        - Exactly one VulnerabilityCase
        - Vendor participant ends at RM.ACCEPTED (auto-cascaded from VALID)
        - Finder participant at RM.ACCEPTED
        """
        dl = self._setup_dl()
        SubmitReportReceivedUseCase(dl, self._make_submit_event()).execute()
        ValidateReportReceivedUseCase(
            dl, self._make_validate_event()
        ).execute()

        cases = dl.get_all("VulnerabilityCase")
        assert len(cases) == 1, "Expected exactly one VulnerabilityCase"

        valid_id = _report_phase_status_id(
            self.VENDOR_ID, self.REPORT_ID, RM.VALID.value
        )
        assert (
            dl.get("ParticipantStatus", valid_id) is not None
        ), "Vendor must have RM.VALID in history after validate-report"

        accepted_id = _report_phase_status_id(
            self.FINDER_ID, self.REPORT_ID, RM.ACCEPTED.value
        )
        assert (
            dl.get("ParticipantStatus", accepted_id) is not None
        ), "Finder must be RM.ACCEPTED after full Offer(Report) to Accept flow"
