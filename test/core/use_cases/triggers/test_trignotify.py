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
Tests for D5-7-TRIGNOTIFY-1: verify that trigger use cases populate the
``to`` field in outbound activities.

Spec: specs/outbox.md OX-03-001; specs/case-management.md CM-06.
"""

import pytest

from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.core.states.em import EM
from vultron.core.use_cases.triggers.case import (
    SvcDeferCaseUseCase,
    SvcEngageCaseUseCase,
)
from vultron.core.use_cases.triggers.embargo import (
    SvcAcceptEmbargoUseCase,
    SvcProposeEmbargoUseCase,
    SvcTerminateEmbargoUseCase,
)
from vultron.core.use_cases.triggers.report import (
    SvcCloseReportUseCase,
    SvcInvalidateReportUseCase,
    SvcRejectReportUseCase,
)
from vultron.core.use_cases.triggers.requests import (
    DeferCaseTriggerRequest,
    EngageCaseTriggerRequest,
    AcceptEmbargoTriggerRequest,
    ProposeEmbargoTriggerRequest,
    TerminateEmbargoTriggerRequest,
    CloseReportTriggerRequest,
    InvalidateReportTriggerRequest,
    RejectReportTriggerRequest,
)
from vultron.wire.as2.vocab.activities.embargo import EmProposeEmbargoActivity
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)
from vultron.wire.as2.vocab.activities.report import RmSubmitReportActivity

from datetime import datetime, timezone

FUTURE_END_TIME = "2099-12-01T00:00:00Z"
FUTURE_END_DATETIME = datetime(2099, 12, 1, 0, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_actor_dl(actor_name: str):
    """Create an as_Service actor and a matching per-actor SqliteDataLayer."""
    actor = as_Service(name=actor_name)
    actor_id = actor.id_
    reset_datalayer(actor_id)
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)
    dl.clear_all()
    dl.create(actor)
    return actor, dl


def _make_two_actor_case(
    dl, vendor_id: str, finder_id: str
) -> VulnerabilityCase:
    """Create a VulnerabilityCase with vendor and finder in actor_participant_index."""
    case = VulnerabilityCase(name="Test Case")
    case.actor_participant_index[vendor_id] = f"{case.id_}/participants/vendor"
    case.actor_participant_index[finder_id] = f"{case.id_}/participants/finder"
    dl.create(case)
    return case


def _new_outbox_activity(vendor, vendor_dl, result: dict):
    """Return the first new activity added to vendor's outbox during execute()."""
    activity_id = None
    if "activity" in result and result["activity"]:
        activity_id = result["activity"].get("id")
    if activity_id is None and "offer" in result:
        activity_id = result["offer"].get("id")
    if activity_id is None:
        return None, None
    obj = vendor_dl.read(activity_id)
    return activity_id, obj


def _to_field(activity_obj) -> list[str] | None:
    """Return the ``to`` field of an activity as a list of strings."""
    if activity_obj is None:
        return None
    to = getattr(activity_obj, "to", None)
    if to is None:
        return None
    if isinstance(to, list):
        return [
            (
                item
                if isinstance(item, str)
                else getattr(item, "id_", str(item))
            )
            for item in to
        ]
    if isinstance(to, str):
        return [to]
    return None


# ---------------------------------------------------------------------------
# Case trigger use cases
# ---------------------------------------------------------------------------


class TestCaseTriggerToField:
    """SvcEngageCaseUseCase and SvcDeferCaseUseCase populate ``to``."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.vendor, self.dl = _make_actor_dl("Vendor Co")
        self.finder, _ = _make_actor_dl("Finder Co")
        self.case = _make_two_actor_case(
            self.dl, self.vendor.id_, self.finder.id_
        )
        yield
        self.dl.clear_all()
        reset_datalayer(self.vendor.id_)
        reset_datalayer(self.finder.id_)

    def test_engage_case_to_field_contains_other_participant(self):
        """SvcEngageCaseUseCase queues RmEngageCaseActivity with non-empty to."""
        request = EngageCaseTriggerRequest(
            actor_id=self.vendor.id_,
            case_id=self.case.id_,
        )
        result = SvcEngageCaseUseCase(self.dl, request).execute()

        _, act_obj = _new_outbox_activity(self.vendor, self.dl, result)
        recipients = _to_field(act_obj)

        assert recipients is not None, "to field must not be None"
        assert len(recipients) > 0, "to field must be non-empty"
        assert self.finder.id_ in recipients
        assert self.vendor.id_ not in recipients

    def test_defer_case_to_field_contains_other_participant(self):
        """SvcDeferCaseUseCase queues RmDeferCaseActivity with non-empty to."""
        request = DeferCaseTriggerRequest(
            actor_id=self.vendor.id_,
            case_id=self.case.id_,
        )
        result = SvcDeferCaseUseCase(self.dl, request).execute()

        _, act_obj = _new_outbox_activity(self.vendor, self.dl, result)
        recipients = _to_field(act_obj)

        assert recipients is not None, "to field must not be None"
        assert len(recipients) > 0, "to field must be non-empty"
        assert self.finder.id_ in recipients
        assert self.vendor.id_ not in recipients

    def test_engage_case_to_field_none_when_no_other_participants(self):
        """SvcEngageCaseUseCase sets to=None when vendor is the only participant."""
        case_solo = VulnerabilityCase(name="Solo Case")
        case_solo.actor_participant_index[self.vendor.id_] = (
            f"{case_solo.id_}/participants/vendor"
        )
        self.dl.create(case_solo)

        request = EngageCaseTriggerRequest(
            actor_id=self.vendor.id_,
            case_id=case_solo.id_,
        )
        result = SvcEngageCaseUseCase(self.dl, request).execute()

        _, act_obj = _new_outbox_activity(self.vendor, self.dl, result)
        recipients = _to_field(act_obj)

        assert (
            not recipients
        ), "to should be empty/None when no other participants"


# ---------------------------------------------------------------------------
# Embargo trigger use cases
# ---------------------------------------------------------------------------


class TestEmbargoTriggerToField:
    """All three embargo trigger use cases populate ``to``."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.vendor, self.dl = _make_actor_dl("Vendor Co")
        self.finder, _ = _make_actor_dl("Finder Co")
        self.case = _make_two_actor_case(
            self.dl, self.vendor.id_, self.finder.id_
        )
        yield
        self.dl.clear_all()
        reset_datalayer(self.vendor.id_)
        reset_datalayer(self.finder.id_)

    def test_propose_embargo_to_field_contains_other_participant(self):
        """SvcProposeEmbargoUseCase queues EmProposeEmbargoActivity with to."""
        request = ProposeEmbargoTriggerRequest(
            actor_id=self.vendor.id_,
            case_id=self.case.id_,
            end_time=FUTURE_END_DATETIME,
        )
        result = SvcProposeEmbargoUseCase(self.dl, request).execute()

        _, act_obj = _new_outbox_activity(self.vendor, self.dl, result)
        recipients = _to_field(act_obj)

        assert recipients is not None
        assert self.finder.id_ in recipients
        assert self.vendor.id_ not in recipients

    def test_evaluate_embargo_to_field_contains_other_participant(self):
        """SvcAcceptEmbargoUseCase queues EmAcceptEmbargoActivity with to."""
        embargo = EmbargoEvent(context=self.case.id_)
        self.dl.create(embargo)
        proposal = EmProposeEmbargoActivity(
            actor=self.finder.id_,
            object_=embargo,
            context=self.case.id_,
        )
        self.dl.create(proposal)
        self.case.current_status.em_state = EM.PROPOSED
        self.case.proposed_embargoes.append(embargo.id_)
        self.dl.save(self.case)

        request = AcceptEmbargoTriggerRequest(
            actor_id=self.vendor.id_,
            case_id=self.case.id_,
            proposal_id=proposal.id_,
        )
        result = SvcAcceptEmbargoUseCase(self.dl, request).execute()

        _, act_obj = _new_outbox_activity(self.vendor, self.dl, result)
        recipients = _to_field(act_obj)

        assert recipients is not None
        assert self.finder.id_ in recipients
        assert self.vendor.id_ not in recipients

    def test_terminate_embargo_to_field_contains_other_participant(self):
        """SvcTerminateEmbargoUseCase queues AnnounceEmbargoActivity with to."""
        embargo = EmbargoEvent(context=self.case.id_)
        self.dl.create(embargo)
        self.case.set_embargo(embargo.id_)
        self.case.current_status.em_state = EM.ACTIVE
        self.dl.save(self.case)

        request = TerminateEmbargoTriggerRequest(
            actor_id=self.vendor.id_,
            case_id=self.case.id_,
        )
        result = SvcTerminateEmbargoUseCase(self.dl, request).execute()

        _, act_obj = _new_outbox_activity(self.vendor, self.dl, result)
        recipients = _to_field(act_obj)

        assert recipients is not None
        assert self.finder.id_ in recipients
        assert self.vendor.id_ not in recipients


# ---------------------------------------------------------------------------
# Report trigger use cases
# ---------------------------------------------------------------------------


class TestReportTriggerToField:
    """SvcCloseReportUseCase, SvcInvalidateReportUseCase, and
    SvcRejectReportUseCase populate ``to`` with either case participants
    (when a linked case exists) or the offer submitter."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.vendor, self.dl = _make_actor_dl("Vendor Co")
        self.finder, _ = _make_actor_dl("Finder Co")

        self.report = VulnerabilityReport(
            name="CVE-TEST",
            content="Report content",
            attributed_to=self.finder.id_,
        )
        self.dl.create(self.report)

        self.offer = RmSubmitReportActivity(
            actor=self.finder.id_,
            object_=self.report,
            target=self.vendor.id_,
            to=[self.vendor.id_],
        )
        self.dl.create(self.offer)
        yield
        self.dl.clear_all()
        reset_datalayer(self.vendor.id_)
        reset_datalayer(self.finder.id_)

    def test_close_report_to_field_falls_back_to_offer_actor(self):
        """SvcCloseReportUseCase uses offer actor as to when no case exists."""
        request = CloseReportTriggerRequest(
            actor_id=self.vendor.id_,
            offer_id=self.offer.id_,
        )
        result = SvcCloseReportUseCase(self.dl, request).execute()

        _, act_obj = _new_outbox_activity(self.vendor, self.dl, result)
        recipients = _to_field(act_obj)

        assert recipients is not None
        assert self.finder.id_ in recipients
        assert self.vendor.id_ not in recipients

    def test_invalidate_report_to_field_falls_back_to_offer_actor(self):
        """SvcInvalidateReportUseCase uses offer actor as to when no case exists."""
        request = InvalidateReportTriggerRequest(
            actor_id=self.vendor.id_,
            offer_id=self.offer.id_,
        )
        result = SvcInvalidateReportUseCase(self.dl, request).execute()

        _, act_obj = _new_outbox_activity(self.vendor, self.dl, result)
        recipients = _to_field(act_obj)

        assert recipients is not None
        assert self.finder.id_ in recipients
        assert self.vendor.id_ not in recipients

    def test_reject_report_to_field_falls_back_to_offer_actor(self):
        """SvcRejectReportUseCase uses offer actor as to when no case exists."""
        request = RejectReportTriggerRequest(
            actor_id=self.vendor.id_,
            offer_id=self.offer.id_,
        )
        result = SvcRejectReportUseCase(self.dl, request).execute()

        _, act_obj = _new_outbox_activity(self.vendor, self.dl, result)
        recipients = _to_field(act_obj)

        assert recipients is not None
        assert self.finder.id_ in recipients
        assert self.vendor.id_ not in recipients

    def test_close_report_to_field_uses_case_participants_when_case_exists(
        self,
    ):
        """SvcCloseReportUseCase uses case participants when linked case exists."""
        case = _make_two_actor_case(self.dl, self.vendor.id_, self.finder.id_)
        case.vulnerability_reports.append(self.report.id_)
        self.dl.save(case)

        request = CloseReportTriggerRequest(
            actor_id=self.vendor.id_,
            offer_id=self.offer.id_,
        )
        result = SvcCloseReportUseCase(self.dl, request).execute()

        _, act_obj = _new_outbox_activity(self.vendor, self.dl, result)
        recipients = _to_field(act_obj)

        assert recipients is not None
        assert self.finder.id_ in recipients
        assert self.vendor.id_ not in recipients
