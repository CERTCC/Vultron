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

Spec: specs/outbox.yaml OX-03-001; specs/case-management.yaml CM-06.
"""

import pytest

from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.core.states.em import EM
from vultron.enums.roles import CVDRole
from vultron.errors import VultronValidationError
from vultron.core.use_cases.triggers.case import (
    SvcAddParticipantStatusUseCase,
    SvcDeferCaseUseCase,
    SvcEngageCaseUseCase,
)
from vultron.core.use_cases.triggers.embargo import (
    SvcAcceptEmbargoUseCase,
    SvcProposeEmbargoUseCase,
    SvcProposeEmbargoRevisionUseCase,
    SvcRejectEmbargoUseCase,
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
    AddParticipantStatusTriggerRequest,
    AcceptEmbargoTriggerRequest,
    ProposeEmbargoTriggerRequest,
    ProposeEmbargoRevisionTriggerRequest,
    RejectEmbargoTriggerRequest,
    TerminateEmbargoTriggerRequest,
    CloseReportTriggerRequest,
    InvalidateReportTriggerRequest,
    RejectReportTriggerRequest,
)
from vultron.wire.as2.factories import (
    em_propose_embargo_activity,
    rm_submit_report_activity,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import (
    CaseParticipant,
    FinderParticipant,
)
from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)

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


def _make_case_with_case_manager(
    dl: SqliteDataLayer,
    actor_id: str,
    finder_id: str,
    case_actor_id: str,
) -> VulnerabilityCase:
    """Create a VulnerabilityCase with a Finder participant and a Case Actor
    (CVDRole.CASE_MANAGER).  Persists all objects in *dl*.

    The actor participant is pre-initialized to RM.VALID so that
    engage (→ ACCEPTED) and defer (→ DEFERRED) transitions are valid.
    """
    from vultron.core.states.rm import RM
    from vultron.wire.as2.vocab.objects.case_status import (
        ParticipantStatus as WireParticipantStatus,
    )

    case = VulnerabilityCase(name="Test Case")

    actor_participant = CaseParticipant(
        attributed_to=actor_id,
        context=case.id_,
        case_roles=[CVDRole.VENDOR],
    )
    # Pre-advance actor to RM.VALID so engage/defer transitions will succeed

    actor_participant.participant_statuses.append(
        WireParticipantStatus(context=case.id_, rm_state=RM.RECEIVED)
    )
    actor_participant.participant_statuses.append(
        WireParticipantStatus(context=case.id_, rm_state=RM.VALID)
    )

    finder_participant = FinderParticipant(
        attributed_to=finder_id,
        context=case.id_,
    )
    case_manager_participant = CaseParticipant(
        attributed_to=case_actor_id,
        context=case.id_,
        case_roles=[CVDRole.CASE_MANAGER],
    )

    case.actor_participant_index[actor_id] = actor_participant.id_
    case.actor_participant_index[finder_id] = finder_participant.id_
    case.actor_participant_index[case_actor_id] = case_manager_participant.id_

    case.case_participants.append(actor_participant.id_)
    case.case_participants.append(finder_participant.id_)
    case.case_participants.append(case_manager_participant.id_)

    dl.create(case)
    dl.create(actor_participant)
    dl.create(finder_participant)
    dl.create(case_manager_participant)
    return case


def _make_two_actor_case(
    dl, vendor_id: str, finder_id: str
) -> VulnerabilityCase:
    """Create a VulnerabilityCase with vendor and finder — no CASE_MANAGER.

    Both ``case_participants`` and ``actor_participant_index`` are kept in
    sync via ``add_participant()``.  Participant objects are stored in the
    DataLayer so ``resolve_case_participant_id_for_actor`` can resolve them
    from the canonical list without hitting divergence errors.

    Use ``_make_case_with_case_manager`` for tests that need PCR-08-001
    routing or an ``EngageCaseTriggerRequest``/``AddParticipantStatusTriggerRequest``.
    """
    case = VulnerabilityCase(name="Test Case")
    vendor_participant = CaseParticipant(
        id_=f"{case.id_}/participants/vendor",
        attributed_to=vendor_id,
        context=case.id_,
        case_roles=[CVDRole.VENDOR],
    )
    finder_participant = CaseParticipant(
        id_=f"{case.id_}/participants/finder",
        attributed_to=finder_id,
        context=case.id_,
        case_roles=[CVDRole.FINDER],
    )
    case.add_participant(vendor_participant)
    case.add_participant(finder_participant)
    dl.create(vendor_participant)
    dl.create(finder_participant)
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
        self.finder = as_Service(name="Finder Co")
        self.case_actor = as_Service(name="Case Actor")
        self.dl.create(self.finder)
        self.dl.create(self.case_actor)
        self.case = _make_case_with_case_manager(
            self.dl,
            self.vendor.id_,
            self.finder.id_,
            self.case_actor.id_,
        )
        yield
        self.dl.clear_all()
        self.dl.close()
        reset_datalayer(self.vendor.id_)

    def test_engage_case_to_field_addresses_case_actor_only(self):
        """SvcEngageCaseUseCase queues activity addressed only to Case Actor
        (PCR-08-001)."""
        request = EngageCaseTriggerRequest(
            actor_id=self.vendor.id_,
            case_id=self.case.id_,
        )
        result = SvcEngageCaseUseCase(
            self.dl, request, trigger_activity=TriggerActivityAdapter(self.dl)
        ).execute()

        _, act_obj = _new_outbox_activity(self.vendor, self.dl, result)
        recipients = _to_field(act_obj)

        assert recipients is not None, "to field must not be None"
        assert (
            len(recipients) == 1
        ), f"Expected exactly 1 recipient, got {len(recipients)}: {recipients}"
        assert recipients[0] == self.case_actor.id_
        assert self.finder.id_ not in recipients
        assert self.vendor.id_ not in recipients

    def test_defer_case_to_field_addresses_case_actor_only(self):
        """SvcDeferCaseUseCase queues activity addressed only to Case Actor
        (PCR-08-001)."""
        request = DeferCaseTriggerRequest(
            actor_id=self.vendor.id_,
            case_id=self.case.id_,
        )
        result = SvcDeferCaseUseCase(
            self.dl, request, trigger_activity=TriggerActivityAdapter(self.dl)
        ).execute()

        _, act_obj = _new_outbox_activity(self.vendor, self.dl, result)
        recipients = _to_field(act_obj)

        assert recipients is not None, "to field must not be None"
        assert (
            len(recipients) == 1
        ), f"Expected exactly 1 recipient, got {len(recipients)}: {recipients}"
        assert recipients[0] == self.case_actor.id_
        assert self.finder.id_ not in recipients
        assert self.vendor.id_ not in recipients

    def test_add_participant_status_to_field_addresses_case_actor_only(self):
        """SvcAddParticipantStatusUseCase queues activity to only Case Actor."""
        request = AddParticipantStatusTriggerRequest(
            actor_id=self.vendor.id_,
            case_id=self.case.id_,
        )
        result = SvcAddParticipantStatusUseCase(
            self.dl, request, trigger_activity=TriggerActivityAdapter(self.dl)
        ).execute()

        act_obj = self.dl.read(result["activity_id"])
        recipients = _to_field(act_obj)

        assert recipients is not None
        assert (
            len(recipients) == 1
        ), f"Expected exactly 1 recipient, got {len(recipients)}: {recipients}"
        assert recipients[0] == self.case_actor.id_
        assert self.finder.id_ not in recipients
        assert self.vendor.id_ not in recipients

    def test_engage_case_raises_when_no_case_manager(self):
        """SvcEngageCaseUseCase raises VultronValidationError when no CASE_MANAGER."""
        case_solo = VulnerabilityCase(name="Solo Case")
        case_solo.actor_participant_index[self.vendor.id_] = (
            f"{case_solo.id_}/participants/vendor"
        )
        self.dl.create(case_solo)

        request = EngageCaseTriggerRequest(
            actor_id=self.vendor.id_,
            case_id=case_solo.id_,
        )
        with pytest.raises(VultronValidationError):
            SvcEngageCaseUseCase(
                self.dl,
                request,
                trigger_activity=TriggerActivityAdapter(self.dl),
            ).execute()


# ---------------------------------------------------------------------------
# Embargo trigger use cases
# ---------------------------------------------------------------------------


class TestEmbargoTriggerToField:
    """All embargo trigger use cases address only the Case Actor (PCR-08-001)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.vendor, self.dl = _make_actor_dl("Vendor Co")
        self.finder = as_Service(name="Finder Co")
        self.case_actor = as_Service(name="Case Actor")
        self.dl.create(self.finder)
        self.dl.create(self.case_actor)
        self.case = _make_case_with_case_manager(
            self.dl,
            self.vendor.id_,
            self.finder.id_,
            self.case_actor.id_,
        )
        yield
        self.dl.clear_all()
        self.dl.close()
        reset_datalayer(self.vendor.id_)

    def test_propose_embargo_to_field_addresses_case_actor_only(self):
        """SvcProposeEmbargoUseCase queues activity addressed only to Case Actor."""
        request = ProposeEmbargoTriggerRequest(
            actor_id=self.vendor.id_,
            case_id=self.case.id_,
            end_time=FUTURE_END_DATETIME,
        )
        result = SvcProposeEmbargoUseCase(
            self.dl, request, trigger_activity=TriggerActivityAdapter(self.dl)
        ).execute()

        _, act_obj = _new_outbox_activity(self.vendor, self.dl, result)
        recipients = _to_field(act_obj)

        assert recipients is not None
        assert (
            len(recipients) == 1
        ), f"Expected exactly 1 recipient, got {len(recipients)}: {recipients}"
        assert recipients[0] == self.case_actor.id_
        assert self.finder.id_ not in recipients
        assert self.vendor.id_ not in recipients

    def test_evaluate_embargo_to_field_addresses_case_actor_only(self):
        """SvcAcceptEmbargoUseCase queues activity addressed only to Case Actor."""
        embargo = EmbargoEvent(context=self.case.id_)
        self.dl.create(embargo)
        proposal = em_propose_embargo_activity(
            embargo, context=self.case.id_, actor=self.finder.id_
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
        result = SvcAcceptEmbargoUseCase(
            self.dl, request, trigger_activity=TriggerActivityAdapter(self.dl)
        ).execute()

        _, act_obj = _new_outbox_activity(self.vendor, self.dl, result)
        recipients = _to_field(act_obj)

        assert recipients is not None
        assert (
            len(recipients) == 1
        ), f"Expected exactly 1 recipient, got {len(recipients)}: {recipients}"
        assert recipients[0] == self.case_actor.id_
        assert self.finder.id_ not in recipients
        assert self.vendor.id_ not in recipients

    def test_terminate_embargo_to_field_addresses_case_actor_only(self):
        """SvcTerminateEmbargoUseCase queues activity addressed only to Case Actor."""
        embargo = EmbargoEvent(context=self.case.id_)
        self.dl.create(embargo)
        self.case.set_embargo(embargo.id_)
        self.case.current_status.em_state = EM.ACTIVE
        self.dl.save(self.case)

        request = TerminateEmbargoTriggerRequest(
            actor_id=self.vendor.id_,
            case_id=self.case.id_,
        )
        result = SvcTerminateEmbargoUseCase(
            self.dl, request, trigger_activity=TriggerActivityAdapter(self.dl)
        ).execute()

        _, act_obj = _new_outbox_activity(self.vendor, self.dl, result)
        recipients = _to_field(act_obj)

        assert recipients is not None
        assert (
            len(recipients) == 1
        ), f"Expected exactly 1 recipient, got {len(recipients)}: {recipients}"
        assert recipients[0] == self.case_actor.id_
        assert self.finder.id_ not in recipients
        assert self.vendor.id_ not in recipients

    def test_reject_embargo_to_field_addresses_case_actor_only(self):
        """SvcRejectEmbargoUseCase queues activity addressed only to Case Actor."""
        embargo = EmbargoEvent(context=self.case.id_)
        self.dl.create(embargo)
        proposal = em_propose_embargo_activity(
            embargo, context=self.case.id_, actor=self.finder.id_
        )
        self.dl.create(proposal)
        self.case.current_status.em_state = EM.PROPOSED
        self.case.proposed_embargoes.append(embargo.id_)
        self.dl.save(self.case)

        request = RejectEmbargoTriggerRequest(
            actor_id=self.vendor.id_,
            case_id=self.case.id_,
            proposal_id=proposal.id_,
        )
        result = SvcRejectEmbargoUseCase(
            self.dl, request, trigger_activity=TriggerActivityAdapter(self.dl)
        ).execute()
        _, act_obj = _new_outbox_activity(self.vendor, self.dl, result)
        recipients = _to_field(act_obj)

        assert recipients is not None
        assert (
            len(recipients) == 1
        ), f"Expected exactly 1 recipient, got {len(recipients)}: {recipients}"
        assert recipients[0] == self.case_actor.id_
        assert self.finder.id_ not in recipients
        assert self.vendor.id_ not in recipients

    def test_propose_embargo_revision_to_field_addresses_case_actor_only(self):
        """SvcProposeEmbargoRevisionUseCase queues activity to only Case Actor."""
        embargo = EmbargoEvent(context=self.case.id_)
        self.dl.create(embargo)
        self.case.set_embargo(embargo.id_)
        self.case.current_status.em_state = EM.ACTIVE
        self.dl.save(self.case)

        request = ProposeEmbargoRevisionTriggerRequest(
            actor_id=self.vendor.id_,
            case_id=self.case.id_,
            end_time=FUTURE_END_DATETIME,
        )
        result = SvcProposeEmbargoRevisionUseCase(
            self.dl, request, trigger_activity=TriggerActivityAdapter(self.dl)
        ).execute()

        _, act_obj = _new_outbox_activity(self.vendor, self.dl, result)
        recipients = _to_field(act_obj)

        assert recipients is not None
        assert (
            len(recipients) == 1
        ), f"Expected exactly 1 recipient, got {len(recipients)}: {recipients}"
        assert recipients[0] == self.case_actor.id_
        assert self.finder.id_ not in recipients
        assert self.vendor.id_ not in recipients


# ---------------------------------------------------------------------------
# Report trigger use cases
# ---------------------------------------------------------------------------


class TestReportTriggerToField:
    """SvcCloseReportUseCase, SvcInvalidateReportUseCase, and
    SvcRejectReportUseCase populate ``to`` with either the Case Actor
    (when a linked case exists) or the offer submitter."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.vendor, self.dl = _make_actor_dl("Vendor Co")
        self.finder = as_Service(name="Finder Co")
        self.case_actor = as_Service(name="Case Actor")
        self.dl.create(self.finder)
        self.dl.create(self.case_actor)

        self.report = VulnerabilityReport(
            name="CVE-TEST",
            content="Report content",
            attributed_to=self.finder.id_,
        )
        self.dl.create(self.report)

        self.offer = rm_submit_report_activity(
            self.report,
            self.vendor.id_,
            actor=self.finder.id_,
        )
        self.dl.create(self.offer)
        yield
        self.dl.clear_all()
        self.dl.close()
        reset_datalayer(self.vendor.id_)

    def test_close_report_to_field_falls_back_to_offer_actor(self):
        """SvcCloseReportUseCase uses offer actor as to when no case exists."""
        request = CloseReportTriggerRequest(
            actor_id=self.vendor.id_,
            offer_id=self.offer.id_,
        )
        result = SvcCloseReportUseCase(
            self.dl, request, trigger_activity=TriggerActivityAdapter(self.dl)
        ).execute()

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
        result = SvcInvalidateReportUseCase(
            self.dl, request, trigger_activity=TriggerActivityAdapter(self.dl)
        ).execute()

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
        result = SvcRejectReportUseCase(
            self.dl, request, trigger_activity=TriggerActivityAdapter(self.dl)
        ).execute()

        _, act_obj = _new_outbox_activity(self.vendor, self.dl, result)
        recipients = _to_field(act_obj)

        assert recipients is not None
        assert self.finder.id_ in recipients
        assert self.vendor.id_ not in recipients

    def test_close_report_to_field_uses_case_actor_when_case_exists(
        self,
    ):
        """SvcCloseReportUseCase routes case-scoped close to the Case Actor."""
        case = _make_case_with_case_manager(
            self.dl,
            self.vendor.id_,
            self.finder.id_,
            self.case_actor.id_,
        )
        case.vulnerability_reports.append(self.report.id_)
        self.dl.save(case)

        request = CloseReportTriggerRequest(
            actor_id=self.vendor.id_,
            offer_id=self.offer.id_,
        )
        result = SvcCloseReportUseCase(
            self.dl, request, trigger_activity=TriggerActivityAdapter(self.dl)
        ).execute()

        _, act_obj = _new_outbox_activity(self.vendor, self.dl, result)
        recipients = _to_field(act_obj)

        assert recipients is not None
        assert len(recipients) == 1
        assert recipients[0] == self.case_actor.id_
        assert self.finder.id_ not in recipients
        assert self.vendor.id_ not in recipients

    def test_invalidate_report_to_field_uses_case_actor_when_case_exists(self):
        """SvcInvalidateReportUseCase routes case-scoped invalidation to Case Actor."""
        case = _make_case_with_case_manager(
            self.dl,
            self.vendor.id_,
            self.finder.id_,
            self.case_actor.id_,
        )
        case.vulnerability_reports.append(self.report.id_)
        self.dl.save(case)

        request = InvalidateReportTriggerRequest(
            actor_id=self.vendor.id_,
            offer_id=self.offer.id_,
        )
        result = SvcInvalidateReportUseCase(
            self.dl, request, trigger_activity=TriggerActivityAdapter(self.dl)
        ).execute()
        _, act_obj = _new_outbox_activity(self.vendor, self.dl, result)
        recipients = _to_field(act_obj)

        assert recipients is not None
        assert len(recipients) == 1
        assert recipients[0] == self.case_actor.id_
        assert self.finder.id_ not in recipients
        assert self.vendor.id_ not in recipients

    def test_reject_report_to_field_uses_case_actor_when_case_exists(self):
        """SvcRejectReportUseCase routes case-scoped reject to the Case Actor."""
        case = _make_case_with_case_manager(
            self.dl,
            self.vendor.id_,
            self.finder.id_,
            self.case_actor.id_,
        )
        case.vulnerability_reports.append(self.report.id_)
        self.dl.save(case)

        request = RejectReportTriggerRequest(
            actor_id=self.vendor.id_,
            offer_id=self.offer.id_,
        )
        result = SvcRejectReportUseCase(
            self.dl, request, trigger_activity=TriggerActivityAdapter(self.dl)
        ).execute()
        _, act_obj = _new_outbox_activity(self.vendor, self.dl, result)
        recipients = _to_field(act_obj)

        assert recipients is not None
        assert len(recipients) == 1
        assert recipients[0] == self.case_actor.id_
        assert self.finder.id_ not in recipients
        assert self.vendor.id_ not in recipients

    def test_close_report_raises_when_case_exists_without_case_manager(self):
        """Case-scoped close fails fast when no CASE_MANAGER is resolvable."""
        case = _make_two_actor_case(self.dl, self.vendor.id_, self.finder.id_)
        case.vulnerability_reports.append(self.report.id_)
        self.dl.save(case)

        request = CloseReportTriggerRequest(
            actor_id=self.vendor.id_,
            offer_id=self.offer.id_,
        )
        with pytest.raises(VultronValidationError):
            SvcCloseReportUseCase(
                self.dl,
                request,
                trigger_activity=TriggerActivityAdapter(self.dl),
            ).execute()
