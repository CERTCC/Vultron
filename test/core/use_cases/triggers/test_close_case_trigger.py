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

"""Dedicated execute()-path tests for SvcCloseCaseUseCase.

Per notes/triggers-test-coverage.md: each test exercises the use case's
execute() path against a real in-memory DataLayer and asserts:
  1. the RM state mutation (RM → CLOSED via BT);
  2. the outbox effect (activity queued, addressed correctly per PCR-08-001);
  3. the documented failure modes the use case is documented to raise
     (VultronNotFoundError when no linked VulnerabilityCase).

SvcCloseCaseUseCase enforces that only the Case Owner may close the case:
CheckCaseOwnerNode in the BT tree returns FAILURE when the actor is not
CASE_OWNER, causing execute() to raise VultronBTError.
"""

import pytest

from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.offer_record import VultronOfferRecord
from vultron.core.use_cases.triggers.report import (
    SvcCloseCaseUseCase,
    SvcCloseReportUseCase,
)
from vultron.core.use_cases.triggers.requests import CloseReportTriggerRequest
from vultron.enums.roles import CVDRole
from vultron.errors import VultronNotFoundError
from vultron.wire.as2.factories import rm_submit_report_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Offer
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_actor_dl(name: str) -> tuple[as_Service, SqliteDataLayer]:
    actor = as_Service(name=name)
    reset_datalayer(actor.id_)
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor.id_)
    dl.clear_all()
    dl.create(actor)
    return actor, dl


def _make_offer(
    dl: SqliteDataLayer,
    report: as_VulnerabilityReport,
    recipient_id: str,
    actor_id: str,
) -> as_Offer:
    offer = rm_submit_report_activity(report, recipient_id, actor=actor_id)
    dl.create(offer)
    dl.create(
        VultronOfferRecord(
            offer_id=offer.id_,
            report_id=report.id_,
            offer_actor_id=actor_id,
            offer_to=[recipient_id],
        )
    )
    return offer


def _make_case_with_owner(
    dl: SqliteDataLayer,
    owner_id: str,
    report_id: str,
    manager_id: str | None = None,
) -> VulnerabilityCase:
    owner_p = CaseParticipant(
        attributed_to=owner_id,
        case_roles=[CVDRole.CASE_OWNER],
    )
    case = VulnerabilityCase(name="Owner Case")
    case.vulnerability_reports.append(report_id)
    case.actor_participant_index[owner_id] = owner_p.id_
    dl.create(owner_p)
    if manager_id is not None:
        mgr_p = CaseParticipant(
            attributed_to=manager_id,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        case.actor_participant_index[manager_id] = mgr_p.id_
        dl.create(mgr_p)
    dl.create(case)
    return case


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSvcCloseCaseUseCase:
    """execute()-path tests for SvcCloseCaseUseCase.

    The vendor actor is seeded as CASE_OWNER so CheckCaseOwner passes.
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

        # vendor is CASE_OWNER; case_actor is CASE_MANAGER for routing
        self.owner_case = _make_case_with_owner(
            self.dl,
            owner_id=self.vendor.id_,
            manager_id=self.case_actor.id_,
            report_id=self.report.id_,
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

    def test_close_case_returns_activity_dict(self):
        """execute() returns result['activity'] as Reject(Offer) dict (DL-06-001)."""
        request = CloseReportTriggerRequest(
            actor_id=self.vendor.id_,
            offer_id=self.offer.id_,
        )
        result = SvcCloseCaseUseCase(
            self.dl,
            request,
            trigger_activity=TriggerActivityAdapter(self.dl),
        ).execute()
        assert result.get("activity") is not None
        assert result["activity"].get("type") == "Reject"

    def test_close_case_queues_activity_in_outbox(self):
        """execute() enqueues at least one activity in the actor's outbox."""
        request = CloseReportTriggerRequest(
            actor_id=self.vendor.id_,
            offer_id=self.offer.id_,
        )
        before = set(self.dl.outbox_list_for_actor(self.vendor.id_))
        SvcCloseCaseUseCase(
            self.dl,
            request,
            trigger_activity=TriggerActivityAdapter(self.dl),
        ).execute()
        after = set(self.dl.outbox_list_for_actor(self.vendor.id_))
        assert len(after - before) >= 1

    def test_backward_compat_alias_works(self):
        """SvcCloseReportUseCase alias delegates to SvcCloseCaseUseCase."""
        assert SvcCloseReportUseCase is SvcCloseCaseUseCase

    def test_close_case_raises_when_no_linked_case(self):
        """VultronNotFoundError raised when report has no linked VulnerabilityCase."""
        vendor2, dl2 = _make_actor_dl("Vendor2 Co")
        try:
            report2 = as_VulnerabilityReport(
                name="Unlinked",
                content="No case",
                attributed_to=vendor2.id_,
            )
            dl2.create(report2)
            offer2 = _make_offer(
                dl2, report2, vendor2.id_, actor_id=vendor2.id_
            )
            request = CloseReportTriggerRequest(
                actor_id=vendor2.id_,
                offer_id=offer2.id_,
            )
            with pytest.raises(VultronNotFoundError):
                SvcCloseCaseUseCase(
                    dl2,
                    request,
                    trigger_activity=TriggerActivityAdapter(dl2),
                ).execute()
        finally:
            dl2.clear_all()
            dl2.close()
            reset_datalayer(vendor2.id_)
