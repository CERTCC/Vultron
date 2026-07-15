#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
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

"""
Dedicated execute()-path tests for SvcValidateReportUseCase and
SvcSubmitReportUseCase.

Per notes/triggers-test-coverage.md: each test exercises the use case's
execute() path against a real in-memory DataLayer and asserts:
  1. the RM state mutation (as_ParticipantStatus / as_CaseParticipant transition);
  2. the outbox effect (activity queued, addressed correctly per PCR-08-001);
  3. the documented failure modes the use case is documented to raise.
"""

import pytest

from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.core.use_cases._helpers import _report_phase_status_id
from vultron.core.use_cases.triggers.report import (
    SvcSubmitReportUseCase,
    SvcValidateReportUseCase,
)
from vultron.core.use_cases.triggers.requests import (
    SubmitReportTriggerRequest,
    ValidateReportTriggerRequest,
)
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.errors import VultronNotFoundError, VultronValidationError
from vultron.wire.as2.factories import rm_submit_report_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Offer
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import (
    as_CaseParticipant,
    FinderParticipant,
)
from vultron.wire.as2.vocab.objects.case_status import (
    as_ParticipantStatus as WireParticipantStatus,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_actor_dl(actor_name: str) -> tuple[as_Service, SqliteDataLayer]:
    actor = as_Service(name=actor_name)
    actor_id = actor.id_
    reset_datalayer(actor_id)
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)
    dl.clear_all()
    dl.create(actor)
    return actor, dl


def _make_offer(
    dl: SqliteDataLayer,
    report: as_VulnerabilityReport,
    recipient_id: str,
    actor_id: str,
) -> as_Offer:
    offer = rm_submit_report_activity(
        report,
        recipient_id,
        actor=actor_id,
    )
    dl.create(offer)
    return offer


def _make_case_with_embargo(
    dl: SqliteDataLayer,
    vendor_id: str,
    finder_id: str,
    case_actor_id: str,
    report_id: str,
) -> as_VulnerabilityCase:
    """Build a as_VulnerabilityCase with finder, vendor, CASE_MANAGER participants,
    an active embargo, and the report linked via vulnerability_reports."""
    embargo = as_EmbargoEvent(context="urn:placeholder")
    dl.create(embargo)

    case = as_VulnerabilityCase(name="Test Case")
    case.set_embargo(embargo.id_)
    case.vulnerability_reports.append(report_id)

    vendor_participant = as_CaseParticipant(
        attributed_to=vendor_id,
        context=case.id_,
        case_roles=[CVDRole.VENDOR],
    )
    # Seed RM.RECEIVED so the RECEIVED → VALID transition is valid.
    vendor_participant.participant_statuses.append(
        WireParticipantStatus(context=case.id_, rm_state=RM.RECEIVED)
    )
    finder_participant = FinderParticipant(
        attributed_to=finder_id,
        context=case.id_,
    )
    case_manager_participant = as_CaseParticipant(
        attributed_to=case_actor_id,
        context=case.id_,
        case_roles=[CVDRole.CASE_MANAGER],
    )

    case.actor_participant_index[vendor_id] = vendor_participant.id_
    case.actor_participant_index[finder_id] = finder_participant.id_
    case.actor_participant_index[case_actor_id] = case_manager_participant.id_

    case.case_participants.append(vendor_participant.id_)
    case.case_participants.append(finder_participant.id_)
    case.case_participants.append(case_manager_participant.id_)

    dl.create(case)
    dl.create(vendor_participant)
    dl.create(finder_participant)
    dl.create(case_manager_participant)
    return case


# ---------------------------------------------------------------------------
# SvcValidateReportUseCase
# ---------------------------------------------------------------------------


class TestSvcValidateReportUseCase:
    """execute() path tests for SvcValidateReportUseCase.

    Covers: RM state mutation, outbox effect (PCR-08-001 routing), and
    documented failure modes.
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        self.vendor, self.dl = _make_actor_dl("Vendor Co")
        self.finder, self.finder_dl = _make_actor_dl("Finder Co")
        self.case_actor, self.case_actor_dl = _make_actor_dl("Case Actor")

        self.report = as_VulnerabilityReport(
            name="CVE-TEST",
            content="Vulnerability report content",
            attributed_to=self.finder.id_,
        )
        self.dl.create(self.report)

        self.offer = _make_offer(
            self.dl,
            self.report,
            self.vendor.id_,
            actor_id=self.finder.id_,
        )

        self.case = _make_case_with_embargo(
            self.dl,
            self.vendor.id_,
            self.finder.id_,
            self.case_actor.id_,
            self.report.id_,
        )
        yield
        self.dl.clear_all()
        self.dl.close()
        self.finder_dl.clear_all()
        self.finder_dl.close()
        self.case_actor_dl.clear_all()
        self.case_actor_dl.close()
        reset_datalayer(self.vendor.id_)
        reset_datalayer(self.finder.id_)
        reset_datalayer(self.case_actor.id_)

    # --- AC-1: RM state transition -----------------------------------------

    def test_validate_report_creates_rm_valid_status_record(self):
        """execute() creates a as_ParticipantStatus record for RM.VALID."""
        request = ValidateReportTriggerRequest(
            actor_id=self.vendor.id_,
            offer_id=self.offer.id_,
        )
        SvcValidateReportUseCase(
            self.dl,
            request,
            trigger_activity=TriggerActivityAdapter(self.dl),
        ).execute()

        valid_id = _report_phase_status_id(
            self.vendor.id_, self.report.id_, RM.VALID.value
        )
        status_record = self.dl.read(valid_id)
        assert status_record is not None

    def test_validate_report_updates_case_participant_rm_state(self):
        """execute() advances the as_CaseParticipant.participant_statuses to RM.VALID."""
        request = ValidateReportTriggerRequest(
            actor_id=self.vendor.id_,
            offer_id=self.offer.id_,
        )
        SvcValidateReportUseCase(
            self.dl,
            request,
            trigger_activity=TriggerActivityAdapter(self.dl),
        ).execute()

        vendor_participant_id = self.case.actor_participant_index[
            self.vendor.id_
        ]
        updated = self.dl.read(vendor_participant_id)
        assert updated is not None
        assert isinstance(updated, as_CaseParticipant)
        assert updated.participant_statuses
        assert updated.participant_statuses[-1].rm_state == RM.VALID

    # --- AC-2: outbox effect -----------------------------------------------

    def test_validate_report_queues_activity_in_outbox(self):
        """execute() enqueues at least one activity in the actor's outbox."""
        request = ValidateReportTriggerRequest(
            actor_id=self.vendor.id_,
            offer_id=self.offer.id_,
        )
        before = set(self.dl.outbox_list_for_actor(self.vendor.id_))
        SvcValidateReportUseCase(
            self.dl,
            request,
            trigger_activity=TriggerActivityAdapter(self.dl),
        ).execute()
        after = set(self.dl.outbox_list_for_actor(self.vendor.id_))
        assert len(after - before) >= 1

    def test_validate_report_outbox_activity_addressed_to_case_actor(self):
        """Activity queued by execute() is addressed only to the Case Actor
        (PCR-08-001)."""
        request = ValidateReportTriggerRequest(
            actor_id=self.vendor.id_,
            offer_id=self.offer.id_,
        )
        before = set(self.dl.outbox_list_for_actor(self.vendor.id_))
        SvcValidateReportUseCase(
            self.dl,
            request,
            trigger_activity=TriggerActivityAdapter(self.dl),
        ).execute()
        after = set(self.dl.outbox_list_for_actor(self.vendor.id_))
        new_ids = after - before
        assert new_ids, "No new outbox item was queued"

        activity_id = next(iter(new_ids))
        activity = self.dl.read(activity_id)
        assert activity is not None
        to = getattr(activity, "to", None)
        to_ids = (
            [
                (
                    item
                    if isinstance(item, str)
                    else getattr(item, "id_", str(item))
                )
                for item in to
            ]
            if isinstance(to, list)
            else ([to] if isinstance(to, str) else [])
        )
        assert self.case_actor.id_ in to_ids
        assert self.vendor.id_ not in to_ids
        # PCR-08-001 requires exclusive routing to Case Actor only.
        assert self.finder.id_ not in to_ids
        assert len(to_ids) == 1, f"Expected exactly 1 recipient, got {to_ids}"

    # --- AC-3: failure modes -----------------------------------------------

    def test_validate_report_raises_when_actor_not_found(self):
        """VultronNotFoundError raised when actor_id is unknown."""
        request = ValidateReportTriggerRequest(
            actor_id="urn:uuid:no-such-actor",
            offer_id=self.offer.id_,
        )
        with pytest.raises(VultronNotFoundError):
            SvcValidateReportUseCase(
                self.dl,
                request,
                trigger_activity=TriggerActivityAdapter(self.dl),
            ).execute()

    def test_validate_report_raises_when_offer_not_found(self):
        """VultronNotFoundError raised when offer_id is unknown."""
        request = ValidateReportTriggerRequest(
            actor_id=self.vendor.id_,
            offer_id="urn:uuid:no-such-offer",
        )
        with pytest.raises(VultronNotFoundError):
            SvcValidateReportUseCase(
                self.dl,
                request,
                trigger_activity=TriggerActivityAdapter(self.dl),
            ).execute()

    def test_validate_report_raises_when_offer_is_wrong_type(self):
        """VultronValidationError raised when offer_id resolves to wrong type."""
        # Store a plain as_VulnerabilityReport (not an Offer) as the offer_id.
        non_offer = as_VulnerabilityReport(
            name="Not an offer",
            content="wrong type object",
            attributed_to=self.vendor.id_,
        )
        self.dl.create(non_offer)

        request = ValidateReportTriggerRequest(
            actor_id=self.vendor.id_,
            offer_id=non_offer.id_,
        )
        with pytest.raises(VultronValidationError):
            SvcValidateReportUseCase(
                self.dl,
                request,
                trigger_activity=TriggerActivityAdapter(self.dl),
            ).execute()

    def test_validate_report_requires_trigger_activity_port(self):
        """RuntimeError raised when trigger_activity port is not supplied."""
        request = ValidateReportTriggerRequest(
            actor_id=self.vendor.id_,
            offer_id=self.offer.id_,
        )
        with pytest.raises(RuntimeError):
            SvcValidateReportUseCase(
                self.dl,
                request,
                trigger_activity=None,
            ).execute()

    def test_validate_report_idempotent_when_already_valid(self):
        """Second execute() on an already-VALID report does not re-transition RM."""
        request = ValidateReportTriggerRequest(
            actor_id=self.vendor.id_,
            offer_id=self.offer.id_,
        )
        ta = TriggerActivityAdapter(self.dl)
        SvcValidateReportUseCase(
            self.dl, request, trigger_activity=ta
        ).execute()

        vendor_participant_id = self.case.actor_participant_index[
            self.vendor.id_
        ]
        p1 = self.dl.read(vendor_participant_id)
        assert isinstance(p1, as_CaseParticipant)
        statuses_after_first = list(p1.participant_statuses)

        # Second call: CheckRMStateValid short-circuits before TransitionRMtoValid;
        # participant_statuses list must not grow.
        SvcValidateReportUseCase(
            self.dl, request, trigger_activity=ta
        ).execute()

        p2 = self.dl.read(vendor_participant_id)
        assert isinstance(p2, as_CaseParticipant)
        assert len(p2.participant_statuses) == len(
            statuses_after_first
        ), "Second validate re-appended a duplicate RM status entry"


# ---------------------------------------------------------------------------
# SvcSubmitReportUseCase
# ---------------------------------------------------------------------------


class TestSvcSubmitReportUseCase:
    """execute() path tests for SvcSubmitReportUseCase.

    Covers: outbox effect (offer queued), RM state effect (report and
    ReportCaseLink persisted), and documented failure modes.
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        self.finder, self.dl = _make_actor_dl("Finder Co")
        self.vendor, self.vendor_dl = _make_actor_dl("Vendor Co")
        yield
        self.dl.clear_all()
        self.dl.close()
        self.vendor_dl.clear_all()
        self.vendor_dl.close()
        reset_datalayer(self.finder.id_)
        reset_datalayer(self.vendor.id_)

    # --- AC-2: RM state / persistence mutations ----------------------------

    def test_submit_report_persists_vulnerability_report(self):
        """execute() stores a as_VulnerabilityReport in the actor's DataLayer."""
        request = SubmitReportTriggerRequest(
            actor_id=self.finder.id_,
            report_name="CVE-TEST",
            report_content="Vulnerability details",
            recipient_id=self.vendor.id_,
        )
        result = SvcSubmitReportUseCase(
            self.dl,
            request,
            trigger_activity=TriggerActivityAdapter(self.dl),
        ).execute()

        # Confirm the report object ID is readable from the DataLayer
        offer_dict = result.get("offer") or {}
        report_obj = offer_dict.get("object") or {}
        report_id = report_obj.get("id")
        assert report_id is not None, "offer['object']['id'] is missing"
        stored = self.dl.read(report_id)
        assert (
            stored is not None
        ), "as_VulnerabilityReport not found in DataLayer"
        assert isinstance(stored, as_VulnerabilityReport)
        assert stored.name == "CVE-TEST"

    def test_submit_report_persists_report_case_link(self):
        """execute() stores a VultronReportCaseLink keyed by report ID."""
        request = SubmitReportTriggerRequest(
            actor_id=self.finder.id_,
            report_name="CVE-TEST",
            report_content="Vulnerability details",
            recipient_id=self.vendor.id_,
        )
        result = SvcSubmitReportUseCase(
            self.dl,
            request,
            trigger_activity=TriggerActivityAdapter(self.dl),
        ).execute()

        offer_dict = result.get("offer") or {}
        report_id = (offer_dict.get("object") or {}).get("id")
        assert report_id is not None
        link_id = VultronReportCaseLink.build_id(report_id)
        link = self.dl.read(link_id)
        assert link is not None, "VultronReportCaseLink not found in DataLayer"
        assert isinstance(link, VultronReportCaseLink)
        assert link.report_id == report_id
        assert link.trusted_case_creator_id == self.vendor.id_

    def test_submit_report_returns_offer_dict(self):
        """execute() returns {'offer': <offer_dict>} with a non-None offer."""
        request = SubmitReportTriggerRequest(
            actor_id=self.finder.id_,
            report_name="CVE-TEST",
            report_content="Vulnerability details",
            recipient_id=self.vendor.id_,
        )
        result = SvcSubmitReportUseCase(
            self.dl,
            request,
            trigger_activity=TriggerActivityAdapter(self.dl),
        ).execute()

        assert "offer" in result
        assert result["offer"] is not None
        assert result["offer"].get("type") == "Offer"

    # --- AC-2: outbox effect -----------------------------------------------

    def test_submit_report_queues_offer_in_outbox(self):
        """execute() enqueues the offer activity in the actor's outbox."""
        request = SubmitReportTriggerRequest(
            actor_id=self.finder.id_,
            report_name="CVE-TEST",
            report_content="Vulnerability details",
            recipient_id=self.vendor.id_,
        )
        before = set(self.dl.outbox_list_for_actor(self.finder.id_))
        SvcSubmitReportUseCase(
            self.dl,
            request,
            trigger_activity=TriggerActivityAdapter(self.dl),
        ).execute()
        after = set(self.dl.outbox_list_for_actor(self.finder.id_))
        assert len(after - before) >= 1

    def test_submit_report_offer_addressed_to_recipient(self):
        """Offer activity is addressed to the specified recipient."""
        request = SubmitReportTriggerRequest(
            actor_id=self.finder.id_,
            report_name="CVE-TEST",
            report_content="Vulnerability details",
            recipient_id=self.vendor.id_,
        )
        before = set(self.dl.outbox_list_for_actor(self.finder.id_))
        SvcSubmitReportUseCase(
            self.dl,
            request,
            trigger_activity=TriggerActivityAdapter(self.dl),
        ).execute()
        after = set(self.dl.outbox_list_for_actor(self.finder.id_))
        new_ids = after - before
        assert new_ids, "No new outbox item was queued"

        activity_id = next(iter(new_ids))
        activity = self.dl.read(activity_id)
        assert activity is not None
        to = getattr(activity, "to", None)
        to_ids = (
            [
                (
                    item
                    if isinstance(item, str)
                    else getattr(item, "id_", str(item))
                )
                for item in to
            ]
            if isinstance(to, list)
            else ([to] if isinstance(to, str) else [])
        )
        assert self.vendor.id_ in to_ids

    # --- AC-3: failure modes -----------------------------------------------

    def test_submit_report_raises_when_actor_not_found(self):
        """VultronNotFoundError raised when actor_id is unknown."""
        request = SubmitReportTriggerRequest(
            actor_id="urn:uuid:no-such-actor",
            report_name="CVE-TEST",
            report_content="content",
            recipient_id=self.vendor.id_,
        )
        with pytest.raises(VultronNotFoundError):
            SvcSubmitReportUseCase(
                self.dl,
                request,
                trigger_activity=TriggerActivityAdapter(self.dl),
            ).execute()

    def test_submit_report_requires_trigger_activity_port(self):
        """RuntimeError raised when trigger_activity port is not supplied."""
        request = SubmitReportTriggerRequest(
            actor_id=self.finder.id_,
            report_name="CVE-TEST",
            report_content="content",
            recipient_id=self.vendor.id_,
        )
        with pytest.raises(RuntimeError):
            SvcSubmitReportUseCase(
                self.dl,
                request,
                trigger_activity=None,
            ).execute()

    def test_submit_report_idempotent_on_duplicate_report(self):
        """Second execute() with same actor/name still succeeds without error."""
        request = SubmitReportTriggerRequest(
            actor_id=self.finder.id_,
            report_name="CVE-TEST",
            report_content="Vulnerability details",
            recipient_id=self.vendor.id_,
        )
        ta = TriggerActivityAdapter(self.dl)
        r1 = SvcSubmitReportUseCase(
            self.dl, request, trigger_activity=ta
        ).execute()
        r2 = SvcSubmitReportUseCase(
            self.dl, request, trigger_activity=ta
        ).execute()
        # Both calls return a valid offer
        assert r1.get("offer") is not None
        assert r2.get("offer") is not None
        assert r1["offer"].get("type") == "Offer"
        assert r2["offer"].get("type") == "Offer"
