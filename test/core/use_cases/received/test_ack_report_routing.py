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
"""Unit tests for who may send an AckReport (RK) and where it goes.

RK goes from an actor the ``Offer(VulnerabilityReport)`` was addressed to, to
the reporter, which checks the sender against its own record of the Offer
(RMB-08-004).  Nobody sends RK to the CASE_MANAGER, so the handler forwards
nothing and commits no ledger entry (RMB-08-003).
"""

from __future__ import annotations

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.models.activity import VultronActivity
from vultron.core.models.actor import VultronService
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.events.report import AckReportReceivedEvent
from vultron.core.models.offer_record import VultronOfferRecord
from vultron.core.models.report import VulnerabilityReport
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.use_cases.received.report import AckReportReceivedUseCase
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CASE_ACTOR_ID = "https://example.org/actors/case-actor-ack"
VENDOR_ID = "https://example.org/actors/vendor-ack"
FINDER_ID = "https://example.org/actors/finder-ack"
STRANGER_ID = "https://example.org/actors/stranger-ack"
REPORT_ID = "https://example.org/reports/r-ack-test"
OFFER_ID = "https://example.org/activities/offer-ack"
CASE_ID = "https://example.org/cases/c-ack-test"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_store(
    owner_id: str, *, offer_record: bool = True, case: bool = True
) -> SqliteDataLayer:
    """*owner_id*'s store holding the report and, optionally, more.

    ``offer_record`` seeds the record of the Finder's Offer to the Vendor,
    which the Finder (the reporter) and the Vendor (its addressee) both hold.
    ``case`` seeds a case for the report with the CaseActor as CASE_MANAGER,
    so a test can show that an RK forwards nothing to it even when it exists.
    """
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=owner_id)
    dl.save(as_VulnerabilityReport(id_=REPORT_ID, name="Test Vuln Report"))
    if offer_record:
        dl.create(
            VultronOfferRecord(
                offer_id=OFFER_ID,
                report_id=REPORT_ID,
                offer_actor_id=FINDER_ID,
                offer_to=[VENDOR_ID],
            )
        )
    if case:
        dl.save(VultronService(id_=CASE_ACTOR_ID, context=CASE_ID))
        vul_case = as_VulnerabilityCase(
            id_=CASE_ID, name="AckReport Test", attributed_to=CASE_ACTOR_ID
        )
        vul_case.vulnerability_reports.append(REPORT_ID)
        manager = as_CaseParticipant(
            attributed_to=CASE_ACTOR_ID,
            context=CASE_ID,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        dl.create(manager)
        vul_case.case_participants.append(manager.id_)
        vul_case.actor_participant_index[CASE_ACTOR_ID] = manager.id_
        dl.save(vul_case)
    return dl


def _make_ack_event(
    sender_id: str, receiving_actor_id: str
) -> AckReportReceivedEvent:
    """An AckReportReceivedEvent (``Read(Offer(Report))``) from *sender_id*."""
    report_obj = VulnerabilityReport(id_=REPORT_ID)
    offer_obj = VultronActivity(
        id_=OFFER_ID,
        type_="Offer",
        actor=FINDER_ID,
        object_=report_obj,
        to=[VENDOR_ID],
    )
    read_activity = VultronActivity(
        id_=f"https://example.org/activities/read-ack-{len(sender_id)}",
        type_="Read",
        actor=sender_id,
        object_=offer_obj,
        to=[FINDER_ID],
    )
    return AckReportReceivedEvent(
        semantic_type=MessageSemantics.ACK_REPORT,
        activity_id=read_activity.id_,
        actor_id=sender_id,
        object_=offer_obj,
        inner_object=report_obj,
        activity=read_activity,
        receiving_actor_id=receiving_actor_id,
    )


def _run(dl: SqliteDataLayer, event: AckReportReceivedEvent) -> HandlerResult:
    return AckReportReceivedUseCase(
        dl=dl,
        request=event,
        sync_port=SyncActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()


def _ledger_event_types(dl: SqliteDataLayer) -> list[str]:
    return [
        getattr(e, "event_type", "")
        for e in dl.list_objects("CaseLedgerEntry")
    ]


def _written(before: dict[str, int], after: dict[str, int]) -> dict[str, int]:
    """Per-table row growth between two ``count_all()`` snapshots."""
    return {
        table: after.get(table, 0) - before.get(table, 0)
        for table in set(before) | set(after)
        if after.get(table, 0) != before.get(table, 0)
    }


#: What intake writes for one received RK: its record of the ``Read``, nothing
#: else (CLP-10-017).
INTAKE_ONLY = {"ReceivedActivityRecord": 1}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAckReportSender:
    """The reporter admits RK only from an addressee of its Offer."""

    @pytest.mark.spec("RMB-08-004")
    @pytest.mark.spec("HP-01-006")
    def test_offer_addressee_is_admitted(self):
        dl = _make_store(FINDER_ID)
        before = dl.count_all()

        result = _run(dl, _make_ack_event(VENDOR_ID, FINDER_ID))

        assert result.disposition is HandlerDisposition.APPLIED
        # An acknowledgement changes no state (RMB-08-001).
        assert _written(before, dl.count_all()) == INTAKE_ONLY
        assert dl.outbox_list() == []

    @pytest.mark.spec("RMB-08-004")
    @pytest.mark.spec("HP-01-006")
    def test_sender_that_is_not_an_addressee_is_refused(self):
        dl = _make_store(FINDER_ID)
        before = dl.count_all()

        result = _run(dl, _make_ack_event(STRANGER_ID, FINDER_ID))

        assert result.disposition is HandlerDisposition.REFUSED
        assert "not an addressee" in (result.reason or "")
        assert _written(before, dl.count_all()) == INTAKE_ONLY
        assert dl.outbox_list() == []

    @pytest.mark.spec("RMB-08-004")
    def test_store_without_a_record_of_the_offer_refuses(self):
        dl = _make_store(FINDER_ID, offer_record=False, case=False)
        before = dl.count_all()

        result = _run(dl, _make_ack_event(VENDOR_ID, FINDER_ID))

        assert result.disposition is HandlerDisposition.REFUSED
        assert "No record of Offer" in (result.reason or "")
        assert _written(before, dl.count_all()) == INTAKE_ONLY
        assert dl.outbox_list() == []


class TestAckReportIsNotSentToTheCaseManager:
    """No RK is forwarded to the CASE_MANAGER or ledgered (RMB-08-003)."""

    @pytest.mark.spec("RMB-08-003")
    def test_own_ack_is_not_forwarded_to_the_case_manager(self):
        """The Vendor's own ``Read`` in its own inbox emits nothing (#2667)."""
        dl = _make_store(VENDOR_ID)

        result = _run(dl, _make_ack_event(VENDOR_ID, VENDOR_ID))

        assert result.disposition is HandlerDisposition.APPLIED
        assert dl.outbox_list() == []
        assert _ledger_event_types(dl) == []

    @pytest.mark.spec("RMB-08-003")
    def test_case_manager_commits_no_ledger_entry(self):
        """The CASE_MANAGER holds no record of the Offer, so it refuses RK."""
        dl = _make_store(CASE_ACTOR_ID, offer_record=False)

        result = _run(dl, _make_ack_event(VENDOR_ID, CASE_ACTOR_ID))

        assert result.disposition is HandlerDisposition.REFUSED
        assert _ledger_event_types(dl) == []
        assert dl.outbox_list() == []

    @pytest.mark.spec("RMB-08-003")
    def test_reporter_commits_no_ledger_entry_even_with_a_case(self):
        dl = _make_store(FINDER_ID)

        _run(dl, _make_ack_event(VENDOR_ID, FINDER_ID))

        assert _ledger_event_types(dl) == []
