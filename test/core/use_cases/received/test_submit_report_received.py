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
"""Tests for SubmitReportReceivedUseCase: log messages, proposal flow, offer addressing.

ADR-0041: SubmitReportReceivedUseCase no longer creates a VulnerabilityCase.
Instead it writes a pending VultronReportCaseLink and sends Create(as_CaseProposal).
"""

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.models.activity import VultronActivity
from vultron.core.models.events import MessageSemantics
from vultron.core.models.events.report import SubmitReportReceivedEvent
from vultron.core.models.report import VultronReport
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.states.rm import RM
from vultron.core.use_cases.received.report import SubmitReportReceivedUseCase

_CASE_ACTOR_SERVICE_URL = "http://case-actor:7999/api/v2"


@pytest.fixture(autouse=True)
def configure_case_actor_url(monkeypatch):
    """Set VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL for all tests in this module."""
    monkeypatch.setenv(
        "VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL", _CASE_ACTOR_SERVICE_URL
    )
    from vultron.config.app import reload_config

    reload_config()
    yield
    reload_config()


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
    """Tests that SubmitReportReceivedUseCase writes a pending proposal at RM.RECEIVED.

    Per ADR-0041, SubmitReportReceivedUseCase now writes a pending
    VultronReportCaseLink and sends Create(as_CaseProposal) to the CaseActor.
    It does NOT create a VulnerabilityCase locally.
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
        dl.save(report)
        vendor_actor = VultronCaseActor(id_=vendor_id)
        dl.save(vendor_actor)
        return event, dl

    def test_submit_report_creates_case_at_received(self):
        """SubmitReportReceivedUseCase writes a pending VultronReportCaseLink (ADR-0041).

        Per ADR-0041, the vendor no longer creates a VulnerabilityCase.
        Instead it writes a pending link and sends Create(as_CaseProposal).
        """
        event, dl = self._make_event_and_dl()
        SubmitReportReceivedUseCase(
            dl, event, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        link_id = VultronReportCaseLink.build_id(self.REPORT_ID)
        link = dl.read(link_id)
        assert isinstance(
            link, VultronReportCaseLink
        ), "Expected a pending VultronReportCaseLink (ADR-0041)"
        assert link.report_id == self.REPORT_ID
        assert link.case_id is None

    def test_submit_report_creates_vendor_participant_at_received(self):
        """ADR-0041: no VulnerabilityCase → no CaseParticipant created by vendor."""
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
        assert len(vendor_participants) == 0, (
            "ADR-0041: vendor must not create CaseParticipant records"
            " before the CaseActor confirms the case"
        )

    def test_submit_report_creates_finder_participant_accepted(self):
        """ADR-0041: no CaseParticipant with RM.ACCEPTED created by vendor tree."""
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
            and (
                (s.get("data_", {}) or {}).get("rm_state") == RM.ACCEPTED.value
                or (s.get("data_", {}) or {}).get("rm", {}).get("state")
                == RM.ACCEPTED.value
            )
        ]
        assert len(finder_accepted) == 0, (
            "ADR-0041: vendor must not create finder ParticipantStatus records"
            " before the CaseActor confirms the case"
        )

    def test_submit_report_case_creation_is_idempotent(self):
        """Calling SubmitReportReceivedUseCase twice creates only one pending link (ADR-0041)."""
        event, dl = self._make_event_and_dl()
        SubmitReportReceivedUseCase(
            dl, event, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()
        SubmitReportReceivedUseCase(
            dl, event, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        links = [
            obj
            for obj in dl.list_objects("ReportCaseLink")
            if isinstance(obj, VultronReportCaseLink)
            and obj.report_id == self.REPORT_ID
        ]
        assert (
            len(links) == 1
        ), "Expected exactly one VultronReportCaseLink after idempotent calls"

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
        from vultron.config.actor import ActorConfig

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
        from vultron.config.actor import ActorConfig

        event, dl = self._make_event_and_dl()
        SubmitReportReceivedUseCase(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            actor_config=ActorConfig(auto_create_case=False),
        ).execute()

        assert dl.outbox_list() == []

    def test_auto_create_enabled_creates_case(self):
        """AC-1: auto_create_case=True (explicit) writes a pending link (ADR-0041)."""
        from vultron.config.actor import ActorConfig

        event, dl = self._make_event_and_dl()
        dl.save(VultronReport(id_=self.REPORT_ID))
        SubmitReportReceivedUseCase(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            actor_config=ActorConfig(auto_create_case=True),
        ).execute()

        link_id = VultronReportCaseLink.build_id(self.REPORT_ID)
        assert isinstance(dl.read(link_id), VultronReportCaseLink)

    def test_no_actor_config_creates_case(self):
        """AC-1: absent ActorConfig preserves always-send-proposal behavior (ADR-0041)."""
        event, dl = self._make_event_and_dl()
        dl.save(VultronReport(id_=self.REPORT_ID))
        SubmitReportReceivedUseCase(
            dl, event, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        link_id = VultronReportCaseLink.build_id(self.REPORT_ID)
        assert isinstance(dl.read(link_id), VultronReportCaseLink)


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
        """HP-09-001: Receiving actor in Offer.to → pending link written (ADR-0041)."""
        event = self._make_event(
            to=[self.VENDOR_ID], receiving_actor_id=self.VENDOR_ID
        )
        dl = self._make_dl()

        SubmitReportReceivedUseCase(
            dl, event, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        link_id = VultronReportCaseLink.build_id(self.REPORT_ID)
        assert isinstance(
            dl.read(link_id), VultronReportCaseLink
        ), "Expected pending VultronReportCaseLink when receiving actor in to"

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
        """HP-09-002: Offer.target is not consulted; to field determines proposal (ADR-0041).

        With target=OTHER_ID but to=[VENDOR_ID] and receiving_actor_id=VENDOR_ID,
        a pending VultronReportCaseLink must be written (target is ignored).
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

        link_id = VultronReportCaseLink.build_id(self.REPORT_ID)
        assert isinstance(dl.read(link_id), VultronReportCaseLink), (
            "Expected pending VultronReportCaseLink when receiving actor in to,"
            " even if target differs"
        )

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


class TestSubmitReportStoresOfferRecord:
    """SubmitReportReceivedUseCase stores VultronOfferRecord for trigger-side lookup.

    Per ADR-0035 DL-06-002: domain facts from the inbound Offer MUST be captured
    as core state so the receiver's trigger paths (validate/invalidate/close) can
    look them up without re-reading the stored wire Offer activity.
    """

    VENDOR_ID = "https://example.org/actors/vendor"
    FINDER_ID = "https://example.org/users/finder"
    REPORT_ID = "https://example.org/reports/r-offer-rec-1"
    OFFER_ID = "https://example.org/activities/offer-rec-1"

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

    def test_stores_offer_record_on_received(self):
        """SubmitReportReceivedUseCase creates VultronOfferRecord in DataLayer."""
        from vultron.core.models.offer_record import VultronOfferRecord

        event, dl = self._make_event_and_dl()
        SubmitReportReceivedUseCase(
            dl, event, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        record_id = VultronOfferRecord.build_id(self.OFFER_ID)
        record = dl.read(record_id)
        assert isinstance(
            record, VultronOfferRecord
        ), "Expected VultronOfferRecord stored for received Offer"
        assert record.offer_id == self.OFFER_ID
        assert record.report_id == self.REPORT_ID
        assert record.offer_actor_id == self.FINDER_ID
        assert self.VENDOR_ID in record.offer_to

    def test_offer_record_is_idempotent(self):
        """Calling SubmitReportReceivedUseCase twice creates only one VultronOfferRecord."""
        from vultron.core.models.offer_record import VultronOfferRecord

        event, dl = self._make_event_and_dl()
        SubmitReportReceivedUseCase(
            dl, event, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()
        SubmitReportReceivedUseCase(
            dl, event, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        record_id = VultronOfferRecord.build_id(self.OFFER_ID)
        records = [
            r for r in dl.get_all("OfferRecord") if r.get("id_") == record_id
        ]
        assert (
            len(records) == 1
        ), "Expected exactly one VultronOfferRecord after idempotent calls"
