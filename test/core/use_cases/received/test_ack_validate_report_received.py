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
"""Tests for AckReport, ValidateReport, and full-flow integration."""

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.activity import VultronActivity
from vultron.core.models.base import VultronObject
from vultron.core.models.events import MessageSemantics
from vultron.core.models.events.report import (
    AckReportReceivedEvent,
    SubmitReportReceivedEvent,
    ValidateReportReceivedEvent,
)
from vultron.core.models.report import VultronReport
from vultron.core.models._helpers import _report_phase_status_id
from vultron.core.use_cases.received.report import (
    AckReportReceivedUseCase,
    SubmitReportReceivedUseCase,
    ValidateReportReceivedUseCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
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
    1. SubmitReportReceivedUseCase creates a as_VulnerabilityCase at RM.RECEIVED.
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
            to=[self.VENDOR_ID],
        )
        report = VultronReport(id_=self.REPORT_ID)
        return SubmitReportReceivedEvent(
            semantic_type=MessageSemantics.SUBMIT_REPORT,
            activity_id=self.OFFER_ID,
            actor_id=self.FINDER_ID,
            object_=report,
            activity=activity,
            receiving_actor_id=self.VENDOR_ID,
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
            receiving_actor_id=self.VENDOR_ID,
        )

    def test_full_flow_case_created_at_received(self):
        """SubmitReportReceivedUseCase creates exactly one case at RM.RECEIVED.

        Per ADR-0015: case creation happens at RM.RECEIVED, not RM.VALID.
        """
        dl = self._setup_dl()
        SubmitReportReceivedUseCase(dl, self._make_submit_event()).execute()

        cases = dl.get_all("VulnerabilityCase")
        assert len(cases) == 1, "Expected exactly one as_VulnerabilityCase"
        case_report_ids = [
            rid
            for c in cases
            for rid in (c.get("data_", {}) or {}).get(
                "vulnerability_reports", []
            )
        ]
        assert (
            self.REPORT_ID in case_report_ids
        ), f"as_VulnerabilityCase must reference report {self.REPORT_ID}"

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
        RECEIVED to VALID; this state change must be persisted.
        Engage/defer is a separate, explicit protocol step.
        """
        from vultron.core.states.rm import RM

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

    def test_full_flow_finder_remains_rm_accepted(self):
        """Finder participant is RM.ACCEPTED after submit and remains so after validate.

        The finder submitted the report, so they enter RM.ACCEPTED at receipt.
        The subsequent validate-report step must not change the finder's state.
        """
        from vultron.core.states.rm import RM

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

        Verifies the combined invariants of ADR-0015:
        - Exactly one as_VulnerabilityCase
        - Vendor participant has RM.VALID in history after validate-report
        - Finder participant at RM.ACCEPTED (reporter is accepted upon submission)
        """
        from vultron.core.states.rm import RM

        dl = self._setup_dl()
        SubmitReportReceivedUseCase(dl, self._make_submit_event()).execute()
        ValidateReportReceivedUseCase(
            dl, self._make_validate_event()
        ).execute()

        cases = dl.get_all("VulnerabilityCase")
        assert len(cases) == 1, "Expected exactly one as_VulnerabilityCase"

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


class TestValidateReportReceivedGuardedCommit:
    """Tests for ValidateReportReceivedUseCase guarded commit behavior (AC-5).

    Per ADR-0021 CLP-10-002, CLP-10-003: the received use case MUST skip the
    canonical commit step when receiving_actor_id != case_actor_id. These tests
    verify that the pre-flight guard works correctly.
    """

    CASE_ACTOR_ID = "https://example.org/actors/case-actor"
    VENDOR_ID = "https://example.org/actors/vendor"
    REPORT_ID = "https://example.org/reports/r-guarded-commit"
    OFFER_ID = "https://example.org/activities/offer-guarded"

    def _make_validate_event_with_receiving_actor(
        self,
        report_id: str = REPORT_ID,
        offer_id: str = OFFER_ID,
        receiving_actor_id: str | None = None,
    ) -> ValidateReportReceivedEvent:
        """Create a ValidateReportReceivedEvent with specified receiving_actor_id."""
        activity = VultronActivity(
            id_=self.OFFER_ID,
            type_="Accept",
            actor=self.VENDOR_ID,
        )
        offer = VultronObject(id_=offer_id, type_="Offer")
        report = VultronReport(id_=report_id)
        return ValidateReportReceivedEvent(
            semantic_type=MessageSemantics.VALIDATE_REPORT,
            activity_id=self.OFFER_ID,
            actor_id=self.VENDOR_ID,
            object_=offer,
            inner_object=report,
            activity=activity,
            receiving_actor_id=receiving_actor_id,
        )

    def test_skip_commit_when_no_receiving_actor(self, caplog):
        """ValidateReportReceivedUseCase skips commit when receiving_actor_id is None.

        Per CLP-10-003: when receiving_actor_id is not set, the commit is skipped.
        """
        import logging

        dl = SqliteDataLayer("sqlite:///:memory:")
        event = self._make_validate_event_with_receiving_actor(
            receiving_actor_id=None
        )

        with caplog.at_level(logging.DEBUG):
            ValidateReportReceivedUseCase(dl, event).execute()

        assert any(
            "receiving_actor_id not set" in r.message for r in caplog.records
        ), "Expected debug log indicating skip due to missing receiving_actor_id"

    def test_skip_commit_when_no_case_found(self, caplog):
        """ValidateReportReceivedUseCase skips commit when no case for report.

        Per CLP-10-003: when no case is linked to the report,
        the commit is skipped.
        """
        import logging

        dl = SqliteDataLayer("sqlite:///:memory:")
        event = self._make_validate_event_with_receiving_actor(
            receiving_actor_id=self.CASE_ACTOR_ID
        )

        with caplog.at_level(logging.DEBUG):
            ValidateReportReceivedUseCase(dl, event).execute()

        assert any(
            "no case found" in r.message.lower() for r in caplog.records
        ), "Expected debug log indicating skip due to missing case"

    def test_skip_commit_when_receiving_actor_not_case_actor(self):
        """ValidateReportReceivedUseCase skips commit when receiving_actor != CaseActor.

        Per CLP-10-003: the guarded commit BT MUST skip the canonical commit
        when the receiving actor is not the CaseActor.  In the single-BT
        pattern (ADR-0022) this is enforced in-tree by CheckIsCaseManagerNode
        rather than via a Python pre-flight guard.  We verify at the data level
        that no CaseLedgerEntry is written.
        """
        from vultron.wire.as2.vocab.objects.report_case_link import (
            VultronReportCaseLink,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")

        # Create a report and link it to a case with CaseActor
        report = VultronReport(id_=self.REPORT_ID)
        dl.save(report)

        case = as_VulnerabilityCase(
            id_="https://example.org/cases/c-guarded",
            name="Guarded Commit Test Case",
        )
        case.vulnerability_reports.append(self.REPORT_ID)
        # Register case actor as CASE_MANAGER
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )

        cm_participant = as_CaseParticipant(
            attributed_to=self.CASE_ACTOR_ID,
            context=case.id_,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        dl.create(cm_participant)
        case.case_participants.append(cm_participant.id_)
        case.actor_participant_index[self.CASE_ACTOR_ID] = cm_participant.id_
        dl.save(case)

        # Create a ReportCaseLink to establish the CaseActor mapping
        link = VultronReportCaseLink(
            report_id=self.REPORT_ID,
            case_id=case.id_,
            trusted_case_actor_id=self.CASE_ACTOR_ID,
        )
        dl.save(link)

        # Send the event as a different actor (not the CaseActor)
        event = self._make_validate_event_with_receiving_actor(
            receiving_actor_id=self.VENDOR_ID  # != case_actor_id
        )

        ValidateReportReceivedUseCase(dl, event).execute()

        entries = list(dl.list_objects("CaseLedgerEntry"))
        assert not entries, (
            "Expected no CaseLedgerEntry when receiving actor is not the CaseActor"
            f" (CLP-10-003); found: {entries}"
        )

    def test_calls_commit_bt_when_receiving_actor_is_case_actor(
        self, monkeypatch
    ):
        """Guarded commit BT runs when receiving_actor_id == case_actor_id (CLP-10-002).

        When all pre-flight guards pass — receiving_actor_id is set and a case
        is linked to the report with the receiving actor holding CASE_MANAGER
        role — the guarded commit BT MUST execute, resulting in a persisted
        CaseLedgerEntry.
        """
        import vultron.core.behaviors.report.received_report_trees as rrt_module
        from vultron.core.models.report_case_link import VultronReportCaseLink
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        CASE_ID = "https://example.org/cases/c-commit-positive"

        dl = SqliteDataLayer("sqlite:///:memory:")

        report = VultronReport(id_=self.REPORT_ID)
        dl.save(report)

        case = as_VulnerabilityCase(
            id_=CASE_ID,
            name="Guarded Commit Positive Test",
        )
        case.vulnerability_reports.append(self.REPORT_ID)
        # Register the CASE_ACTOR as CASE_MANAGER so CheckIsCaseManagerNode passes
        cm_participant = as_CaseParticipant(
            attributed_to=self.CASE_ACTOR_ID,
            context=CASE_ID,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        dl.create(cm_participant)
        case.case_participants.append(cm_participant.id_)
        case.actor_participant_index[self.CASE_ACTOR_ID] = cm_participant.id_
        dl.save(case)

        # VultronReportCaseLink establishes the case_id lookup.
        link = VultronReportCaseLink(
            report_id=self.REPORT_ID,
            case_id=CASE_ID,
            trusted_case_actor_id=self.CASE_ACTOR_ID,
        )
        dl.save(link)

        # Receiving actor IS the CaseActor — CheckIsCaseManagerNode must pass.
        event = self._make_validate_event_with_receiving_actor(
            receiving_actor_id=self.CASE_ACTOR_ID
        )

        # Track calls to create_receive_activity_tree in
        # received_report_trees (where it is called in the ADR-0022 pattern).
        original_create = rrt_module.create_receive_activity_tree
        commit_tree_calls: list[str | None] = []

        def tracking_create(
            name: str,
            case_id: str | None = None,
            precondition_guards: list | None = None,
            effect_nodes: list | None = None,
        ):
            commit_tree_calls.append(case_id)
            return original_create(
                name=name,
                case_id=case_id,
                precondition_guards=precondition_guards or [],
                effect_nodes=effect_nodes or [],
            )

        monkeypatch.setattr(
            rrt_module,
            "create_receive_activity_tree",
            tracking_create,
        )

        ValidateReportReceivedUseCase(dl, event).execute()

        assert commit_tree_calls, (
            "Expected create_receive_activity_tree to be "
            "called when receiving_actor_id == case_actor_id (CLP-10-002)"
        )
        assert commit_tree_calls[0] == CASE_ID, (
            f"Expected guarded commit called for case {CASE_ID!r}, "
            f"got {commit_tree_calls[0]!r}"
        )
