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
"""Tests for case-level use cases: InvalidateReport, CloseReport, and delegation."""

from typing import cast

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.activity import VultronActivity
from vultron.core.models.events import MessageSemantics
from vultron.core.models.events.report import (
    CloseReportReceivedEvent,
    InvalidateReportReceivedEvent,
)
from vultron.core.models.participant import VultronParticipant
from vultron.core.models.report import VultronReport
from vultron.core.states.rm import RM
from vultron.core.use_cases.received.case import (
    CloseCaseUseCase,
    InvalidateCaseUseCase,
)
from vultron.core.use_cases.received.report import (
    CloseReportReceivedUseCase,
    InvalidateReportReceivedUseCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase


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
            ParticipantStatus,
        )

        participant = VultronParticipant(
            id_="https://example.org/participants/p1",
            attributed_to=actor_id,
            context="https://example.org/cases/c1",
            participant_statuses=[
                ParticipantStatus(
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
            ParticipantStatus,
        )
        from vultron.core.models.report import VultronReport as CoreReport

        report = CoreReport(id_=report_id)
        dl.save(report)

        participant = VultronParticipant(
            id_="https://example.org/participants/p-deref",
            attributed_to=actor_id,
            context="https://example.org/cases/c-deref",
            participant_statuses=[
                ParticipantStatus(
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
