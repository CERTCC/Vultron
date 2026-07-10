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
"""Tests for SubmitReportReceivedUseCase: log messages, case creation, offer addressing."""

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.models.activity import VultronActivity
from vultron.core.models.events import MessageSemantics
from vultron.core.models.events.report import SubmitReportReceivedEvent
from vultron.core.models.report import VultronReport
from vultron.core.states.rm import RM
from vultron.core.use_cases.received.report import SubmitReportReceivedUseCase


class TestSubmitReportLogMessages:
    """Tests that SubmitReportReceivedUseCase emits clear log messages."""

    def test_submit_report_log_identifies_vendor_and_report(self, caplog):
        """SubmitReportReceivedUseCase logs vendor actor and report IDs.

        Per HP-09-001, SubmitReportReceivedUseCase uses receiving_actor_id
        (from activity.to) to create a case.  The log must identify both the
        receiving actor and the report being received.  Per D5-6-STATE.
        """
        import logging

        from vultron.core.models.case_actor import VultronCaseActor

        report = VultronReport(id_="https://example.org/reports/r-log-1")
        activity = VultronActivity(
            id_="https://example.org/activities/submit-log-1",
            type_="Offer",
            actor="https://example.org/users/finder",
            to=["https://example.org/actors/vendor"],
        )
        event = SubmitReportReceivedEvent(
            semantic_type=MessageSemantics.SUBMIT_REPORT,
            activity_id="https://example.org/activities/submit-log-1",
            actor_id="https://example.org/users/finder",
            object_=report,
            activity=activity,
            receiving_actor_id="https://example.org/actors/vendor",
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        # CreateCaseParticipantNode reads the vendor actor from DataLayer.
        dl.save(VultronCaseActor(id_="https://example.org/actors/vendor"))

        with caplog.at_level(logging.INFO):
            SubmitReportReceivedUseCase(
                dl, event, trigger_activity=TriggerActivityAdapter(dl)
            ).execute()

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
        from vultron.core.models.case_actor import VultronCaseActor

        report = VultronReport(id_=report_id)
        activity = VultronActivity(
            id_=offer_id,
            type_="Offer",
            actor=finder_id,
            to=[vendor_id],
        )
        event = SubmitReportReceivedEvent(
            semantic_type=MessageSemantics.SUBMIT_REPORT,
            activity_id=offer_id,
            actor_id=finder_id,
            object_=report,
            activity=activity,
            receiving_actor_id=vendor_id,
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
        SubmitReportReceivedUseCase(
            dl, event, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

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
        SubmitReportReceivedUseCase(
            dl, event, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

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
        SubmitReportReceivedUseCase(
            dl, event, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

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
        SubmitReportReceivedUseCase(
            dl, event, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()
        SubmitReportReceivedUseCase(
            dl, event, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

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

    def test_submit_report_skips_case_creation_when_not_in_to(self):
        """SubmitReportReceivedUseCase skips BT when receiving actor not in to.

        If Offer.to is absent (or receiving actor is not listed), the use case
        logs a WARNING and returns without creating a case (HP-09-001).
        """
        report = VultronReport(id_="https://example.org/reports/r-no-to-1")
        activity = VultronActivity(
            id_="https://example.org/activities/offer-no-to-1",
            type_="Offer",
            actor=self.FINDER_ID,
        )
        event = SubmitReportReceivedEvent(
            semantic_type=MessageSemantics.SUBMIT_REPORT,
            activity_id="https://example.org/activities/offer-no-to-1",
            actor_id=self.FINDER_ID,
            object_=report,
            activity=activity,
            receiving_actor_id=self.VENDOR_ID,
        )
        dl = SqliteDataLayer("sqlite:///:memory:")

        SubmitReportReceivedUseCase(
            dl, event, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        all_cases = dl.get_all("VulnerabilityCase")
        assert (
            all_cases == []
        ), "Expected no VulnerabilityCase when receiving actor not in to"


class TestSubmitReportAutoCreateCasePolicy:
    """auto_create_case policy gating of SubmitReportReceivedUseCase (CM-15-001)."""

    VENDOR_ID = "https://example.org/actors/vendor"
    FINDER_ID = "https://example.org/users/finder"
    REPORT_ID = "https://example.org/reports/r-policy-1"
    OFFER_ID = "https://example.org/activities/offer-policy-1"

    def _make_event_and_dl(self):
        from vultron.core.models.case_actor import VultronCaseActor

        report = VultronReport(id_=self.REPORT_ID)
        activity = VultronActivity(
            id_=self.OFFER_ID,
            type_="Offer",
            actor=self.FINDER_ID,
            to=[self.VENDOR_ID],
        )
        event = SubmitReportReceivedEvent(
            semantic_type=MessageSemantics.SUBMIT_REPORT,
            activity_id=self.OFFER_ID,
            actor_id=self.FINDER_ID,
            object_=report,
            activity=activity,
            receiving_actor_id=self.VENDOR_ID,
        )
        dl = SqliteDataLayer("sqlite:///:memory:")
        dl.save(VultronCaseActor(id_=self.VENDOR_ID))
        return event, dl

    def test_auto_create_disabled_stores_report_and_offer_no_case(self):
        """AC-2: auto_create_case=False stores report + Offer but no case."""
        from vultron.core.models.actor_config import ActorConfig

        event, dl = self._make_event_and_dl()
        SubmitReportReceivedUseCase(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            actor_config=ActorConfig(auto_create_case=False),
        ).execute()

        # Report and Offer(Report) activity are persisted.
        assert dl.read(self.REPORT_ID) is not None
        offer_ids = [row.get("id_") for row in dl.get_all("Offer")]
        assert self.OFFER_ID in offer_ids
        # No VulnerabilityCase is created.
        assert dl.get_all("VulnerabilityCase") == []

    def test_auto_create_disabled_leaves_outbox_empty(self):
        """AC-2: auto_create_case=False leaves the receiver's outbox empty."""
        from vultron.core.models.actor_config import ActorConfig

        event, dl = self._make_event_and_dl()
        SubmitReportReceivedUseCase(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            actor_config=ActorConfig(auto_create_case=False),
        ).execute()

        assert dl.outbox_list() == []

    def test_auto_create_enabled_creates_case(self):
        """AC-1: auto_create_case=True (explicit) still creates the case."""
        from vultron.core.models.actor_config import ActorConfig

        event, dl = self._make_event_and_dl()
        dl.save(VultronReport(id_=self.REPORT_ID))
        SubmitReportReceivedUseCase(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            actor_config=ActorConfig(auto_create_case=True),
        ).execute()

        assert len(dl.get_all("VulnerabilityCase")) >= 1

    def test_no_actor_config_creates_case(self):
        """AC-1: absent ActorConfig preserves always-create behavior."""
        event, dl = self._make_event_and_dl()
        dl.save(VultronReport(id_=self.REPORT_ID))
        SubmitReportReceivedUseCase(
            dl, event, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        assert len(dl.get_all("VulnerabilityCase")) >= 1


class TestOfferAddressingSemantics:
    """Tests for HP-09-001 / HP-09-002: Offer(Report) to/cc addressing semantics."""

    VENDOR_ID = "https://example.org/actors/vendor"
    OTHER_ID = "https://example.org/actors/other"
    FINDER_ID = "https://example.org/users/finder"
    REPORT_ID = "https://example.org/reports/r-addr-1"
    OFFER_ID = "https://example.org/activities/offer-addr-1"

    def _make_event(
        self,
        to: list[str] | None = None,
        cc: list[str] | None = None,
        target: str | None = None,
        receiving_actor_id: str | None = None,
    ) -> SubmitReportReceivedEvent:
        report = VultronReport(id_=self.REPORT_ID)
        activity = VultronActivity(
            id_=self.OFFER_ID,
            type_="Offer",
            actor=self.FINDER_ID,
            to=to,
            cc=cc,
            target=target,
        )
        return SubmitReportReceivedEvent(
            semantic_type=MessageSemantics.SUBMIT_REPORT,
            activity_id=self.OFFER_ID,
            actor_id=self.FINDER_ID,
            object_=report,
            activity=activity,
            receiving_actor_id=receiving_actor_id,
        )

    def _make_dl(self) -> SqliteDataLayer:
        from vultron.core.models.case_actor import VultronCaseActor

        dl = SqliteDataLayer("sqlite:///:memory:")
        dl.save(VultronReport(id_=self.REPORT_ID))
        dl.save(VultronCaseActor(id_=self.VENDOR_ID))
        return dl

    def test_receiving_actor_in_to_creates_case(self):
        """HP-09-001: Receiving actor in Offer.to → case created."""
        event = self._make_event(
            to=[self.VENDOR_ID], receiving_actor_id=self.VENDOR_ID
        )
        dl = self._make_dl()

        SubmitReportReceivedUseCase(
            dl, event, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        all_cases = dl.get_all("VulnerabilityCase")
        assert len(all_cases) >= 1, "Expected case when receiving actor in to"

    def test_receiving_actor_in_cc_logs_warning_no_case(self, caplog):
        """HP-09-002: Receiving actor in Offer.cc → WARNING logged, no case."""
        import logging

        event = self._make_event(
            cc=[self.VENDOR_ID], receiving_actor_id=self.VENDOR_ID
        )
        dl = self._make_dl()

        with caplog.at_level(logging.WARNING):
            SubmitReportReceivedUseCase(
                dl, event, trigger_activity=TriggerActivityAdapter(dl)
            ).execute()

        all_cases = dl.get_all("VulnerabilityCase")
        assert (
            all_cases == []
        ), "Expected no case when receiving actor only in cc"

        warning_text = " ".join(
            r.message for r in caplog.records if r.levelno >= logging.WARNING
        )
        assert (
            "cc" in warning_text.lower()
        ), "Expected a WARNING mentioning cc addressing"

    def test_receiving_actor_in_neither_logs_warning_no_case(self, caplog):
        """HP-09-001: Receiving actor in neither to nor cc → WARNING, no case."""
        import logging

        event = self._make_event(
            to=[self.OTHER_ID], receiving_actor_id=self.VENDOR_ID
        )
        dl = self._make_dl()

        with caplog.at_level(logging.WARNING):
            SubmitReportReceivedUseCase(
                dl, event, trigger_activity=TriggerActivityAdapter(dl)
            ).execute()

        all_cases = dl.get_all("VulnerabilityCase")
        assert (
            all_cases == []
        ), "Expected no case when receiving actor not in to or cc"

        warning_text = " ".join(
            r.message for r in caplog.records if r.levelno >= logging.WARNING
        )
        assert (
            self.VENDOR_ID in warning_text
        ), "Expected WARNING to mention the receiving actor ID"

    def test_offer_target_not_consulted_to_wins(self):
        """HP-09-002: Offer.target is not consulted; to field determines case creation.

        With target=OTHER_ID but to=[VENDOR_ID] and receiving_actor_id=VENDOR_ID,
        the case must be created (target is ignored).
        """
        event = self._make_event(
            to=[self.VENDOR_ID],
            target=self.OTHER_ID,
            receiving_actor_id=self.VENDOR_ID,
        )
        dl = self._make_dl()

        SubmitReportReceivedUseCase(
            dl, event, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        all_cases = dl.get_all("VulnerabilityCase")
        assert (
            len(all_cases) >= 1
        ), "Expected case when receiving actor in to, even if target differs"

    def test_offer_target_set_but_not_in_to_no_case(self):
        """HP-09-002 inverse: target=VENDOR_ID but to=[OTHER_ID] → no case.

        Even though target matches the receiving actor, the use case must
        only consult to/cc — not target.
        """
        event = self._make_event(
            to=[self.OTHER_ID],
            target=self.VENDOR_ID,
            receiving_actor_id=self.VENDOR_ID,
        )
        dl = self._make_dl()

        SubmitReportReceivedUseCase(
            dl, event, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        all_cases = dl.get_all("VulnerabilityCase")
        assert (
            all_cases == []
        ), "Expected no case when receiving actor in target but not in to"
