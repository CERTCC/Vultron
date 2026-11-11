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

from datetime import datetime, timedelta
from typing import cast

import pytest
from pydantic import ValidationError

from test.support.act_clock import ACT_AT
from test.support.act_runner import FixedClock, run_in_act
from test.support.embargo_register import activate
from test.support.future_dates import days_from_now
from test.support.trigger_results import activity_of
from vultron.adapters.driven.clock import SystemClock
from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import (
    RmDimension,
)
from vultron.core.models.offer_record import VultronOfferRecord
from vultron.core.models.report import (
    VulnerabilityReport as CoreVulnerabilityReport,
)
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.models.use_case_result import OfferResult
from vultron.core.states.rm import RM
from vultron.core.use_cases.triggers.report import (
    SvcInvalidateReportUseCase,
    SvcRejectReportUseCase,
    SvcSubmitReportUseCase,
    SvcValidateReportUseCase,
)
from vultron.core.use_cases.triggers.requests import (
    InvalidateReportTriggerRequest,
    RejectReportTriggerRequest,
    SubmitReportTriggerRequest,
    ValidateReportTriggerRequest,
)
from vultron.enums.roles import CVDRole
from vultron.errors import (
    VultronInvalidStateTransitionError,
    VultronNotFoundError,
    VultronValidationError,
)
from vultron.wire.as2.factories import rm_submit_report_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Offer
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import (
    ReporterParticipant,
    as_CaseParticipant,
)
from vultron.wire.as2.vocab.objects.case_status import (
    as_ParticipantStatus as WireParticipantStatus,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (  # noqa: F401
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
    offer_record = VultronOfferRecord(
        offer_id=offer.id_,
        report_id=report.id_,
        offer_actor_id=actor_id,
        offer_to=[recipient_id],
    )
    dl.create(offer_record)
    return offer


def _make_case_with_embargo(
    dl: SqliteDataLayer,
    vendor_id: str,
    finder_id: str,
    case_actor_id: str,
    report_id: str,
) -> VulnerabilityCase:
    """Build a VulnerabilityCase with finder, vendor, CASE_MANAGER participants,
    an active embargo, and the report linked via vulnerability_reports."""
    embargo = as_EmbargoEvent(
        context="urn:placeholder", end_time=days_from_now(45)
    )
    dl.create(embargo)

    case = VulnerabilityCase(name="Test Case", attributed_to=vendor_id)
    activate(case, embargo.id_)
    case.vulnerability_reports.append(report_id)

    vendor_participant = as_CaseParticipant(
        attributed_to=vendor_id,
        context=case.id_,
        case_roles=[CVDRole.VENDOR],
    )
    # Seed RM.RECEIVED so the RECEIVED → VALID transition is valid.
    vendor_participant.participant_statuses.append(
        WireParticipantStatus(
            context=case.id_, rm=RmDimension(state=RM.RECEIVED)
        )
    )
    finder_participant = ReporterParticipant(
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
        self.dl.create(
            VultronReportCaseLink(
                report_id=self.report.id_, rm_state=RM.RECEIVED
            )
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

    @pytest.mark.spec("TRIG-02-001")
    @pytest.mark.spec("RSH-08-006")
    def test_validate_report_leaves_the_link_to_the_case_manager(self):
        """execute() sends the validation and does not latch the report link.

        The trigger checks the move and writes nothing of its own: the
        CASE_MANAGER latches its link and records RM VALID when it accepts
        the validation (RSH-08-006, CM-23-016).
        """
        request = ValidateReportTriggerRequest(
            actor_id=self.vendor.id_,
            offer_id=self.offer.id_,
        )
        before = set(self.dl.outbox_list())
        run_in_act(
            SvcValidateReportUseCase(
                self.dl,
                request,
                trigger_activity=TriggerActivityAdapter(self.dl),
                clock=SystemClock(),
            )
        )

        assert set(self.dl.outbox_list()) - before
        link = self.dl.read(VultronReportCaseLink.build_id(self.report.id_))
        assert (
            isinstance(link, VultronReportCaseLink)
            and link.rm_state == RM.RECEIVED
        )

    @pytest.mark.spec("TRIG-02-001")
    def test_validate_report_leaves_the_participant_to_the_case_manager(
        self,
    ):
        """execute() writes no participant status of its own (RSH-08-003).

        The CASE_MANAGER records RM VALID when it accepts the validation and
        commits that status as its own entry; the replica copies it
        (CLP-07-013, CM-23-016).
        """
        request = ValidateReportTriggerRequest(
            actor_id=self.vendor.id_,
            offer_id=self.offer.id_,
        )
        vendor_participant_id = self.case.actor_participant_index[
            self.vendor.id_
        ]
        before = cast(
            CaseParticipant, self.dl.read(vendor_participant_id)
        ).participant_statuses
        run_in_act(
            SvcValidateReportUseCase(
                self.dl,
                request,
                trigger_activity=TriggerActivityAdapter(self.dl),
                clock=SystemClock(),
            )
        )

        updated = self.dl.read(vendor_participant_id)
        assert updated is not None
        assert isinstance(updated, CaseParticipant)
        assert updated.participant_statuses
        assert updated.participant_statuses == before

    # --- AC-2: outbox effect -----------------------------------------------

    @pytest.mark.spec("TRIG-07-001")
    @pytest.mark.spec("TRIG-02-001")
    def test_validate_report_queues_activity_in_outbox(self):
        """execute() enqueues at least one activity in the actor's outbox."""
        request = ValidateReportTriggerRequest(
            actor_id=self.vendor.id_,
            offer_id=self.offer.id_,
        )
        before = set(self.dl.outbox_list())
        run_in_act(
            SvcValidateReportUseCase(
                self.dl,
                request,
                trigger_activity=TriggerActivityAdapter(self.dl),
                clock=SystemClock(),
            )
        )
        after = set(self.dl.outbox_list())
        assert len(after - before) >= 1

    @pytest.mark.spec("TRIG-07-001")
    def test_validate_report_outbox_activity_addressed_to_case_actor(self):
        """Activity queued by execute() is addressed only to the Case Actor
        (PCR-08-001)."""
        request = ValidateReportTriggerRequest(
            actor_id=self.vendor.id_,
            offer_id=self.offer.id_,
        )
        before = set(self.dl.outbox_list())
        run_in_act(
            SvcValidateReportUseCase(
                self.dl,
                request,
                trigger_activity=TriggerActivityAdapter(self.dl),
                clock=SystemClock(),
            )
        )
        after = set(self.dl.outbox_list())
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
            run_in_act(
                SvcValidateReportUseCase(
                    self.dl,
                    request,
                    trigger_activity=TriggerActivityAdapter(self.dl),
                    clock=SystemClock(),
                )
            )

    def test_validate_report_raises_when_offer_not_found(self):
        """VultronNotFoundError raised when offer_id is unknown."""
        request = ValidateReportTriggerRequest(
            actor_id=self.vendor.id_,
            offer_id="urn:uuid:no-such-offer",
        )
        with pytest.raises(VultronNotFoundError):
            run_in_act(
                SvcValidateReportUseCase(
                    self.dl,
                    request,
                    trigger_activity=TriggerActivityAdapter(self.dl),
                    clock=SystemClock(),
                )
            )

    def test_validate_report_raises_when_offer_record_missing(self):
        """VultronNotFoundError raised when no VultronOfferRecord exists for offer_id.

        Per ADR-0035: _resolve_offer_and_report reads VultronOfferRecord, not
        the stored wire Offer. If no record was written at offer creation time,
        the lookup returns None → VultronNotFoundError.
        """
        request = ValidateReportTriggerRequest(
            actor_id=self.vendor.id_,
            offer_id="urn:uuid:offer-with-no-record",
        )
        with pytest.raises(VultronNotFoundError):
            run_in_act(
                SvcValidateReportUseCase(
                    self.dl,
                    request,
                    trigger_activity=TriggerActivityAdapter(self.dl),
                    clock=SystemClock(),
                )
            )

    def test_validate_report_requires_trigger_activity_port(self):
        """RuntimeError raised when trigger_activity port is not supplied."""
        request = ValidateReportTriggerRequest(
            actor_id=self.vendor.id_,
            offer_id=self.offer.id_,
        )
        with pytest.raises(RuntimeError):
            run_in_act(
                SvcValidateReportUseCase(
                    self.dl,
                    request,
                    trigger_activity=None,
                    clock=SystemClock(),
                )
            )

    @pytest.mark.spec("TRIG-07-001")
    def test_validate_report_returns_activity_dict(self):
        """execute() returns result.activity as Accept(Offer) dict (AC-3, DL-06-001)."""
        request = ValidateReportTriggerRequest(
            actor_id=self.vendor.id_,
            offer_id=self.offer.id_,
        )
        result = run_in_act(
            SvcValidateReportUseCase(
                self.dl,
                request,
                trigger_activity=TriggerActivityAdapter(self.dl),
                clock=SystemClock(),
            )
        )

        assert result.activity is not None
        assert activity_of(result).get("type") == "Accept"

    def test_validate_report_idempotent_when_already_valid(self):
        """Second execute() on an already-VALID report does not re-transition RM."""
        request = ValidateReportTriggerRequest(
            actor_id=self.vendor.id_,
            offer_id=self.offer.id_,
        )
        ta = TriggerActivityAdapter(self.dl)
        run_in_act(
            SvcValidateReportUseCase(
                self.dl, request, trigger_activity=ta, clock=SystemClock()
            )
        )

        vendor_participant_id = self.case.actor_participant_index[
            self.vendor.id_
        ]
        p1 = self.dl.read(vendor_participant_id)
        assert isinstance(p1, CaseParticipant)
        statuses_after_first = list(p1.participant_statuses)

        # Second call: CheckRMStateValid short-circuits before TransitionRMtoValid;
        # participant_statuses list must not grow.
        run_in_act(
            SvcValidateReportUseCase(
                self.dl, request, trigger_activity=ta, clock=SystemClock()
            )
        )

        p2 = self.dl.read(vendor_participant_id)
        assert isinstance(p2, CaseParticipant)
        assert len(p2.participant_statuses) == len(statuses_after_first), (
            "Second validate re-appended a duplicate RM status entry"
        )


# ---------------------------------------------------------------------------
# SvcInvalidateReportUseCase / SvcRejectReportUseCase
# ---------------------------------------------------------------------------


class _ReportTriggerBase:
    """Shared fixture for use cases that act on a received offer."""

    #: Seed the case the report belongs to; ``False`` for the pre-case path.
    with_case: bool = True

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

        if self.with_case:
            self.case = _make_case_with_embargo(
                self.dl,
                self.vendor.id_,
                self.finder.id_,
                self.case_actor.id_,
                self.report.id_,
            )
        self.dl.create(
            VultronReportCaseLink(
                report_id=self.report.id_, rm_state=RM.RECEIVED
            )
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


class TestSvcInvalidateReportUseCase(_ReportTriggerBase):
    """execute() path tests for SvcInvalidateReportUseCase."""

    @pytest.mark.spec("TRIG-02-001")
    @pytest.mark.spec("TRIG-07-001")
    def test_invalidate_report_returns_activity_dict(self):
        """execute() returns result.activity with type 'TentativeReject' (DL-06-001)."""
        request = InvalidateReportTriggerRequest(
            actor_id=self.vendor.id_,
            offer_id=self.offer.id_,
        )
        result = run_in_act(
            SvcInvalidateReportUseCase(
                self.dl,
                request,
                trigger_activity=TriggerActivityAdapter(self.dl),
                clock=SystemClock(),
            )
        )

        assert result.activity is not None
        assert activity_of(result).get("type") == "TentativeReject"

    @pytest.mark.spec("TRIG-02-001")
    @pytest.mark.spec("TRIG-07-001")
    def test_invalidate_report_queues_activity_in_outbox(self):
        """execute() enqueues at least one activity in the actor's outbox."""
        request = InvalidateReportTriggerRequest(
            actor_id=self.vendor.id_,
            offer_id=self.offer.id_,
        )
        before = set(self.dl.outbox_list())
        run_in_act(
            SvcInvalidateReportUseCase(
                self.dl,
                request,
                trigger_activity=TriggerActivityAdapter(self.dl),
                clock=SystemClock(),
            )
        )
        after = set(self.dl.outbox_list())
        assert len(after - before) >= 1

    def test_invalidate_report_raises_when_actor_not_found(self):
        """Ported from the retired ``TriggerService`` suite (#3833)."""
        request = InvalidateReportTriggerRequest(
            actor_id="urn:uuid:no-such-actor", offer_id=self.offer.id_
        )
        with pytest.raises(VultronNotFoundError):
            run_in_act(
                SvcInvalidateReportUseCase(
                    self.dl,
                    request,
                    trigger_activity=TriggerActivityAdapter(self.dl),
                    clock=SystemClock(),
                )
            )

    def test_invalidate_report_raises_when_offer_not_found(self):
        """Ported from the retired ``TriggerService`` suite (#3833)."""
        request = InvalidateReportTriggerRequest(
            actor_id=self.vendor.id_, offer_id="urn:uuid:no-such-offer"
        )
        with pytest.raises(VultronNotFoundError):
            run_in_act(
                SvcInvalidateReportUseCase(
                    self.dl,
                    request,
                    trigger_activity=TriggerActivityAdapter(self.dl),
                    clock=SystemClock(),
                )
            )


class TestSvcRejectReportUseCase(_ReportTriggerBase):
    """execute() path tests for SvcRejectReportUseCase, before any case.

    A hard reject sends ``Reject(Offer(VulnerabilityReport))``, which is the
    pre-case path: once a case holds the report the trigger fails closed
    (:class:`TestSvcRejectReportOnACase`).
    """

    with_case = False

    def _seed_invalid(self):
        """Pre-seed RM.INVALID so INVALID→CLOSED is a valid transition (BTND-10-001)."""
        self.dl.save(
            VultronReportCaseLink(
                report_id=self.report.id_, rm_state=RM.INVALID
            )
        )

    @pytest.mark.spec("TRIG-02-001")
    @pytest.mark.spec("TRIG-07-001")
    def test_reject_report_returns_activity_dict(self):
        """execute() returns result.activity with type 'Reject' (DL-06-001)."""
        self._seed_invalid()
        request = RejectReportTriggerRequest(
            actor_id=self.vendor.id_,
            offer_id=self.offer.id_,
        )
        result = run_in_act(
            SvcRejectReportUseCase(
                self.dl,
                request,
                trigger_activity=TriggerActivityAdapter(self.dl),
                clock=SystemClock(),
            )
        )

        assert result.activity is not None
        assert activity_of(result).get("type") == "Reject"

    @pytest.mark.spec("TRIG-02-001")
    @pytest.mark.spec("TRIG-07-001")
    def test_reject_report_queues_activity_in_outbox(self):
        """execute() enqueues at least one activity in the actor's outbox."""
        self._seed_invalid()
        request = RejectReportTriggerRequest(
            actor_id=self.vendor.id_,
            offer_id=self.offer.id_,
        )
        before = set(self.dl.outbox_list())
        run_in_act(
            SvcRejectReportUseCase(
                self.dl,
                request,
                trigger_activity=TriggerActivityAdapter(self.dl),
                clock=SystemClock(),
            )
        )
        after = set(self.dl.outbox_list())
        assert len(after - before) >= 1

    @pytest.mark.spec("RMB-14-004")
    def test_reject_report_from_received_closes_the_report(self):
        """A hard reject from RECEIVED is the ``R → C`` transition."""
        request = RejectReportTriggerRequest(
            actor_id=self.vendor.id_,
            offer_id=self.offer.id_,
        )
        result = run_in_act(
            SvcRejectReportUseCase(
                self.dl,
                request,
                trigger_activity=TriggerActivityAdapter(self.dl),
                clock=SystemClock(),
            )
        )

        assert activity_of(result).get("type") == "Reject"
        link = self.dl.read(VultronReportCaseLink.build_id(self.report.id_))
        assert isinstance(link, VultronReportCaseLink)
        assert link.rm_state == RM.CLOSED

    @pytest.mark.spec("RMB-14-004")
    @pytest.mark.spec("VP-02-004")
    def test_reject_report_from_valid_raises_invalid_transition(self):
        """VALID has no close edge: no Reject is sent and the error is a 409."""
        self.dl.save(
            VultronReportCaseLink(report_id=self.report.id_, rm_state=RM.VALID)
        )
        request = RejectReportTriggerRequest(
            actor_id=self.vendor.id_,
            offer_id=self.offer.id_,
        )
        before = set(self.dl.outbox_list())
        with pytest.raises(VultronInvalidStateTransitionError, match="VALID"):
            run_in_act(
                SvcRejectReportUseCase(
                    self.dl,
                    request,
                    trigger_activity=TriggerActivityAdapter(self.dl),
                    clock=SystemClock(),
                )
            )
        assert set(self.dl.outbox_list()) == before

    def test_reject_report_raises_when_actor_not_found(self):
        """Ported from the retired ``TriggerService`` suite (#3833)."""
        self._seed_invalid()
        request = RejectReportTriggerRequest(
            actor_id="urn:uuid:no-such-actor",
            offer_id=self.offer.id_,
            note="Reason.",
        )
        with pytest.raises(VultronNotFoundError):
            run_in_act(
                SvcRejectReportUseCase(
                    self.dl,
                    request,
                    trigger_activity=TriggerActivityAdapter(self.dl),
                    clock=SystemClock(),
                )
            )

    def test_reject_report_raises_when_offer_not_found(self):
        """Ported from the retired ``TriggerService`` suite (#3833)."""
        request = RejectReportTriggerRequest(
            actor_id=self.vendor.id_,
            offer_id="urn:uuid:no-such-offer",
            note="Reason.",
        )
        with pytest.raises(VultronNotFoundError):
            run_in_act(
                SvcRejectReportUseCase(
                    self.dl,
                    request,
                    trigger_activity=TriggerActivityAdapter(self.dl),
                    clock=SystemClock(),
                )
            )


class TestSvcRejectReportOnACase(_ReportTriggerBase):
    """Once a case holds the report, reject-report fails closed (CM-23-053)."""

    @pytest.mark.spec("CM-23-052")
    @pytest.mark.spec("CM-23-053")
    def test_reject_report_on_a_case_raises_and_sends_nothing(self):
        """The case's owner closes it by ``Leave``, never by a report closure.

        No ``Reject(Offer(VulnerabilityReport))`` is sent.
        """
        request = RejectReportTriggerRequest(
            actor_id=self.vendor.id_,
            offer_id=self.offer.id_,
        )
        before = set(self.dl.outbox_list())
        with pytest.raises(
            VultronInvalidStateTransitionError,
            match=r"Leave\(VulnerabilityCase\)",
        ):
            run_in_act(
                SvcRejectReportUseCase(
                    self.dl,
                    request,
                    trigger_activity=TriggerActivityAdapter(self.dl),
                    clock=SystemClock(),
                )
            )
        assert set(self.dl.outbox_list()) == before
        link = self.dl.read(VultronReportCaseLink.build_id(self.report.id_))
        assert isinstance(link, VultronReportCaseLink)
        assert link.rm_state == RM.RECEIVED


# ---------------------------------------------------------------------------
# A participant that joined through an Invite never answers the report Offer
# ---------------------------------------------------------------------------


class TestReportTriggersRefuseAnActorNotSentTheOffer(_ReportTriggerBase):
    """validate/invalidate/reject-report refuse an actor the Offer was not sent to."""

    @pytest.mark.spec("CM-11-051")
    @pytest.mark.spec("CM-11-020")
    @pytest.mark.parametrize(
        ("use_case", "request_cls", "verb"),
        [
            (
                SvcValidateReportUseCase,
                ValidateReportTriggerRequest,
                "validate-report",
            ),
            (
                SvcInvalidateReportUseCase,
                InvalidateReportTriggerRequest,
                "invalidate-report",
            ),
            (
                SvcRejectReportUseCase,
                RejectReportTriggerRequest,
                "reject-report",
            ),
        ],
    )
    def test_actor_not_sent_the_offer_is_refused_with_a_reason(
        self, use_case, request_cls, verb
    ):
        joiner, _ = _make_actor_dl("Joiner Co")
        self.dl.create(joiner)
        before = set(self.dl.outbox_list())

        with pytest.raises(VultronValidationError, match=verb) as excinfo:
            run_in_act(
                use_case(
                    self.dl,
                    request_cls(actor_id=joiner.id_, offer_id=self.offer.id_),
                    trigger_activity=TriggerActivityAdapter(self.dl),
                    clock=SystemClock(),
                )
            )

        assert "full-case Invite" in str(excinfo.value)
        assert set(self.dl.outbox_list()) == before


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
        result = run_in_act(
            SvcSubmitReportUseCase(
                self.dl,
                request,
                trigger_activity=TriggerActivityAdapter(self.dl),
                clock=SystemClock(),
            )
        )

        # Confirm the report object ID is readable from the DataLayer
        offer_dict = result.offer or {}
        report_obj = offer_dict.get("object") or {}
        report_id = report_obj.get("id")
        assert report_id is not None, "offer['object']['id'] is missing"
        stored = self.dl.read(report_id)
        assert stored is not None, (
            "as_VulnerabilityReport not found in DataLayer"
        )
        assert isinstance(stored, CoreVulnerabilityReport)
        assert stored.name == "CVE-TEST"

    def test_submit_report_persists_report_case_link(self):
        """execute() stores a VultronReportCaseLink keyed by report ID."""
        request = SubmitReportTriggerRequest(
            actor_id=self.finder.id_,
            report_name="CVE-TEST",
            report_content="Vulnerability details",
            recipient_id=self.vendor.id_,
        )
        result = run_in_act(
            SvcSubmitReportUseCase(
                self.dl,
                request,
                trigger_activity=TriggerActivityAdapter(self.dl),
                clock=SystemClock(),
            )
        )

        offer_dict = result.offer or {}
        report_id = (offer_dict.get("object") or {}).get("id")
        assert report_id is not None
        link_id = VultronReportCaseLink.build_id(report_id)
        link = self.dl.read(link_id)
        assert link is not None, "VultronReportCaseLink not found in DataLayer"
        assert isinstance(link, VultronReportCaseLink)
        assert link.report_id == report_id
        assert link.case_creator_id == self.vendor.id_

    @pytest.mark.spec("TRIG-07-001")
    def test_submit_report_returns_offer_dict(self):
        """execute() returns {'offer': <offer_dict>} with a non-None offer."""
        request = SubmitReportTriggerRequest(
            actor_id=self.finder.id_,
            report_name="CVE-TEST",
            report_content="Vulnerability details",
            recipient_id=self.vendor.id_,
        )
        result = run_in_act(
            SvcSubmitReportUseCase(
                self.dl,
                request,
                trigger_activity=TriggerActivityAdapter(self.dl),
                clock=SystemClock(),
            )
        )

        assert result.offer is not None
        assert result.offer.get("type") == "Offer"

    # --- AC-2: outbox effect -----------------------------------------------

    @pytest.mark.spec("TRIG-07-001")
    def test_submit_report_queues_offer_in_outbox(self):
        """execute() enqueues the offer activity in the actor's outbox."""
        request = SubmitReportTriggerRequest(
            actor_id=self.finder.id_,
            report_name="CVE-TEST",
            report_content="Vulnerability details",
            recipient_id=self.vendor.id_,
        )
        before = set(self.dl.outbox_list())
        run_in_act(
            SvcSubmitReportUseCase(
                self.dl,
                request,
                trigger_activity=TriggerActivityAdapter(self.dl),
                clock=SystemClock(),
            )
        )
        after = set(self.dl.outbox_list())
        assert len(after - before) >= 1

    def test_submit_report_offer_addressed_to_recipient(self):
        """Offer activity is addressed to the specified recipient."""
        request = SubmitReportTriggerRequest(
            actor_id=self.finder.id_,
            report_name="CVE-TEST",
            report_content="Vulnerability details",
            recipient_id=self.vendor.id_,
        )
        before = set(self.dl.outbox_list())
        run_in_act(
            SvcSubmitReportUseCase(
                self.dl,
                request,
                trigger_activity=TriggerActivityAdapter(self.dl),
                clock=SystemClock(),
            )
        )
        after = set(self.dl.outbox_list())
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
            run_in_act(
                SvcSubmitReportUseCase(
                    self.dl,
                    request,
                    trigger_activity=TriggerActivityAdapter(self.dl),
                    clock=SystemClock(),
                )
            )

    def test_submit_report_requires_trigger_activity_port(self):
        """RuntimeError raised when trigger_activity port is not supplied."""
        request = SubmitReportTriggerRequest(
            actor_id=self.finder.id_,
            report_name="CVE-TEST",
            report_content="content",
            recipient_id=self.vendor.id_,
        )
        with pytest.raises(RuntimeError):
            run_in_act(
                SvcSubmitReportUseCase(
                    self.dl,
                    request,
                    trigger_activity=None,
                    clock=SystemClock(),
                )
            )

    def test_submit_report_idempotent_on_duplicate_report(self):
        """Second execute() with same actor/name still succeeds without error."""
        request = SubmitReportTriggerRequest(
            actor_id=self.finder.id_,
            report_name="CVE-TEST",
            report_content="Vulnerability details",
            recipient_id=self.vendor.id_,
        )
        ta = TriggerActivityAdapter(self.dl)
        r1 = run_in_act(
            SvcSubmitReportUseCase(
                self.dl, request, trigger_activity=ta, clock=SystemClock()
            )
        )
        r2 = run_in_act(
            SvcSubmitReportUseCase(
                self.dl, request, trigger_activity=ta, clock=SystemClock()
            )
        )
        # Both calls return a valid offer
        assert r1.offer is not None
        assert r2.offer is not None
        assert r1.offer.get("type") == "Offer"
        assert r2.offer.get("type") == "Offer"


# ---------------------------------------------------------------------------
# SvcSubmitReportUseCase — the Reporter's proposed embargo terms (EP-04-004)
# ---------------------------------------------------------------------------


class TestSubmitReportProposedEmbargo:
    """``proposed_embargo_end_time`` rides the Offer as ``proposedEmbargo``.

    The Reporter states terms once, on the Offer (ADR-0096); the use case
    stores the ``EmbargoEvent`` about the *report* (EP-04-009) so the Reporter
    later recognises its own terms on the case, where the CASE_MANAGER keeps
    the event's identity when they win (EP-04-004).  #3971.
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

    def _submit(self, **extra) -> OfferResult:
        request = SubmitReportTriggerRequest(
            actor_id=self.finder.id_,
            report_name="CVE-TEST",
            report_content="Vulnerability details",
            recipient_id=self.vendor.id_,
            **extra,
        )
        return run_in_act(
            SvcSubmitReportUseCase(
                self.dl,
                request,
                trigger_activity=TriggerActivityAdapter(self.dl),
                clock=SystemClock(),
            )
        )

    @pytest.mark.spec("EP-04-014")
    @pytest.mark.spec("EP-04-004")
    @pytest.mark.spec("EP-04-009")
    def test_the_offer_carries_the_stored_terms_about_the_report(self):
        from vultron.core.models.embargo_event import EmbargoEvent

        end = days_from_now(10)
        offer = self._submit(proposed_embargo_end_time=end).offer
        assert offer is not None

        proposed = offer["proposedEmbargo"]
        report_id = offer["object"]["id"]
        assert proposed["type"] == "EmbargoEvent"
        assert proposed["context"] == report_id
        stored = self.dl.read(proposed["id"])
        assert isinstance(stored, EmbargoEvent)
        assert stored.context == report_id
        assert stored.end_time == end

    def test_no_terms_means_no_proposed_embargo_on_the_offer(self):
        offer = self._submit().offer
        assert offer is not None

        assert "proposedEmbargo" not in offer
        assert list(self.dl.list_objects("EmbargoEvent")) == []

    def test_a_naive_end_is_refused_at_the_request(self):
        with pytest.raises(ValidationError, match="must be timezone-aware"):
            SubmitReportTriggerRequest(
                actor_id=self.finder.id_,
                report_name="CVE-TEST",
                report_content="Vulnerability details",
                recipient_id=self.vendor.id_,
                proposed_embargo_end_time=datetime(2030, 1, 1),  # noqa: DTZ001 — deliberately naive
            )

    @pytest.mark.spec("CS-13-002")
    @pytest.mark.parametrize(
        "offset",
        [timedelta(0), -timedelta(days=1)],
        ids=["at-the-act", "before-the-act"],
    )
    def test_an_end_not_after_the_act_is_refused_and_nothing_stored(
        self, offset
    ):
        """Judged at the act's instant, not a clock read (ADR-0176).

        The act runs at :data:`ACT_AT`, months before the wall clock, so an
        end the wall clock would call past is still in this act's future;
        only an end at or before the act's own instant is refused.
        """
        request = SubmitReportTriggerRequest(
            actor_id=self.finder.id_,
            report_name="CVE-TEST",
            report_content="Vulnerability details",
            recipient_id=self.vendor.id_,
            proposed_embargo_end_time=ACT_AT + offset,
        )
        with pytest.raises(VultronValidationError, match="in the future"):
            run_in_act(
                SvcSubmitReportUseCase(
                    self.dl,
                    request,
                    trigger_activity=TriggerActivityAdapter(self.dl),
                    clock=FixedClock(ACT_AT),
                )
            )

        assert list(self.dl.list_objects("VulnerabilityReport")) == []
        assert list(self.dl.list_objects("EmbargoEvent")) == []

    @pytest.mark.spec("CS-13-002")
    def test_an_end_just_after_the_act_is_kept_though_the_clock_is_past_it(
        self,
    ):
        end = ACT_AT + timedelta(microseconds=1)
        request = SubmitReportTriggerRequest(
            actor_id=self.finder.id_,
            report_name="CVE-TEST",
            report_content="Vulnerability details",
            recipient_id=self.vendor.id_,
            proposed_embargo_end_time=end,
        )
        offer = run_in_act(
            SvcSubmitReportUseCase(
                self.dl,
                request,
                trigger_activity=TriggerActivityAdapter(self.dl),
                clock=FixedClock(ACT_AT),
            )
        ).offer

        assert offer is not None
        assert "proposedEmbargo" in offer
