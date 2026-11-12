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

"""What a receiver keeps of an ``Offer(VulnerabilityReport)``, end to end.

``Offer(VulnerabilityReport)`` takes the ordinary door order (ADR-0154,
#5046).  Delivered through the real inbox pipeline, with production wiring:

- a ``cc``-only copy is refused at the addressee door, and what is left of it
  is a receipt stub, with no report, no offer record and no body
  (HP-10-001, CLP-10-018);
- an addressed copy at a receiver whose ``auto_create_case`` is off keeps the
  report and the Offer, proposes no case, and its outcome is archived with
  the body that arrived (CM-15-002, CLP-10-073).
"""

import pytest

import vultron.adapters.driving.fastapi.inbox_port_factories as port_factories
from test.support.objects import authored_at, make
from test.support.received import delivered_body
from vultron.adapters.driven.actor_hosts import canonical_actor_uri
from vultron.adapters.driven.clock import SystemClock
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driving.fastapi.inbox_handler import make_dispatcher
from vultron.adapters.driving.fastapi.inbox_orchestration import (
    FastAPIDispatchAdapter,
    FastAPIIngressAdapter,
    FastAPIReceivedOutcomePort,
)
from vultron.config.actor import ActorConfig
from vultron.core.behaviors.inbox import (
    InboxOutcome,
    InboxOutcomeStatus,
    process_payload,
)
from vultron.core.models.actor import VultronService
from vultron.core.models.offer_record import VultronOfferRecord
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
    ReceivedStage,
)
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.wire.as2.factories import rm_submit_report_activity
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

_VENDOR = canonical_actor_uri("offer-report-vendor")
_OTHER = canonical_actor_uri("offer-report-other-vendor")
_FINDER = canonical_actor_uri("offer-report-finder")
_REPORT_ID = "https://example.org/reports/offer-report-outcome"
_OFFER_ID = "https://example.org/activities/offer-report-outcome"


def _vendor_store(monkeypatch, *, auto_create_case: bool):
    monkeypatch.setattr(
        port_factories,
        "_resolve_actor_config",
        lambda: ActorConfig(auto_create_case=auto_create_case),
    )
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_VENDOR)
    dl.save(make(VultronService, id_=_VENDOR))
    return dl


@pytest.fixture
def vendor_dl(monkeypatch):
    """The vendor's store, with ``auto_create_case`` off (CM-15-001)."""
    dl = _vendor_store(monkeypatch, auto_create_case=False)
    yield dl
    dl.close()


@pytest.fixture
def proposing_vendor_dl(monkeypatch):
    """The vendor's store, with ``auto_create_case`` on (the default)."""
    monkeypatch.setenv(
        "VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL",
        "http://case-actor:7999/api/v2",
    )
    from vultron.config.app import reload_config

    reload_config()
    dl = _vendor_store(monkeypatch, auto_create_case=True)
    yield dl
    dl.close()
    monkeypatch.undo()
    reload_config()


def _deliver(dl: SqliteDataLayer, *, to: str, cc: list[str]) -> InboxOutcome:
    offer = rm_submit_report_activity(
        make(as_VulnerabilityReport, id_=_REPORT_ID, name="r", content="c"),
        to=to,
        actor=_FINDER,
        cc=cc,
        id_=_OFFER_ID,
        at=authored_at(),
    )
    return process_payload(
        delivered_body(offer),
        FastAPIIngressAdapter(dl=dl),
        FastAPIDispatchAdapter(
            dl=dl, actor_id=_VENDOR, dispatcher=make_dispatcher()
        ),
        received_outcome_port=FastAPIReceivedOutcomePort(dl),
        arrived_at=SystemClock().now(),
    )


def _record(dl: SqliteDataLayer) -> ReceivedActivityRecord:
    record = dl.read(ReceivedActivityRecord.build_id(_OFFER_ID))
    assert isinstance(record, ReceivedActivityRecord)
    return record


@pytest.mark.spec("HP-01-005")
@pytest.mark.spec("HP-10-001")
@pytest.mark.spec("CLP-10-018")
def test_a_cc_only_copy_leaves_only_a_receipt_stub(vendor_dl) -> None:
    outcome = _deliver(vendor_dl, to=_OTHER, cc=[_VENDOR])

    assert outcome.status is InboxOutcomeStatus.REJECTED
    assert "only in cc" in (outcome.failure_reason or "")
    record = _record(vendor_dl)
    assert record.is_receipt_stub
    assert record.received_body is None
    assert vendor_dl.read(_REPORT_ID) is None
    assert vendor_dl.read(VultronOfferRecord.build_id(_OFFER_ID)) is None
    assert vendor_dl.get_all("VulnerabilityCase") == []
    assert vendor_dl.outbox_list() == []


@pytest.mark.spec("CM-15-002")
@pytest.mark.spec("CM-15-005")
@pytest.mark.spec("CLP-10-073")
def test_declining_a_case_keeps_the_report_and_archives_the_offer(
    vendor_dl,
) -> None:
    outcome = _deliver(vendor_dl, to=_VENDOR, cc=[])

    assert outcome.status is InboxOutcomeStatus.PROCESSED, (
        outcome.failure_reason
    )
    record = _record(vendor_dl)
    assert record.stage is ReceivedStage.ARCHIVED
    assert record.received_body is not None
    assert vendor_dl.read(_REPORT_ID) is not None
    offer_record = vendor_dl.read(VultronOfferRecord.build_id(_OFFER_ID))
    assert isinstance(offer_record, VultronOfferRecord)
    assert offer_record.report_id == _REPORT_ID
    assert vendor_dl.get_all("VulnerabilityCase") == []
    assert vendor_dl.outbox_list() == []


@pytest.mark.spec("CM-12-001")
@pytest.mark.spec("HP-09-001")
def test_an_addressed_offer_proposes_a_case_when_auto_create_is_on(
    proposing_vendor_dl,
) -> None:
    """The control for the decline above: with the policy on, the addressed
    Offer passes the ``to``-only eligibility check and proposes its case, so
    the decline test's ``SKIPPED`` is the policy's, not a broken check's."""
    outcome = _deliver(proposing_vendor_dl, to=_VENDOR, cc=[])

    assert outcome.status is InboxOutcomeStatus.PROCESSED, (
        outcome.failure_reason
    )
    assert _record(proposing_vendor_dl).stage is ReceivedStage.ARCHIVED
    assert (
        proposing_vendor_dl.read(VultronReportCaseLink.build_id(_REPORT_ID))
        is not None
    )
    assert proposing_vendor_dl.outbox_list() != []
