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

"""Builders for the report semantics."""

from collections.abc import Callable
from typing import Any, cast

from test.support.embargo_register import activate, write_consent_rows
from test.support.future_dates import FAR_FUTURE
from test.support.ledger_rebuild import run_use_case
from test.support.received import received_event
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.config.app import config_override
from vultron.core.models.actor import VultronService
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.received_activity_record import HOLDING_STAGES
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.services.received_activity import held_received_record
from vultron.core.states.rm import RM
from vultron.wire.as2.factories import (
    rm_close_report_activity,
    rm_create_report_activity,
    rm_invalidate_report_activity,
    rm_read_report_activity,
    rm_submit_report_activity,
    rm_validate_report_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Offer
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

from ..test_receive_tree_ledger_commit import (
    CASE_ID,
    FINDER_ID,
    MANAGER_ID,
    _offer,
    _store,
)
from . import Scenario, applied, refused

_BASE = "https://example.org/rerun-sweep/report"
_REPORTER = f"{_BASE}/actors/reporter"
_VENDOR = f"{_BASE}/actors/vendor"


def _intake_recorded(
    activity_id: str,
) -> Callable[[SqliteDataLayer], str | None]:
    """The tree's one effect is intake's record: an RK or a closure (CLP-10-017)."""

    def _check(dl: SqliteDataLayer) -> str | None:
        record = held_received_record(dl, activity_id)
        if record is not None and record.stage in HOLDING_STAGES:
            return None
        return f"intake recorded nothing for {activity_id}: {record}"

    return _check


def _report(tag: str) -> as_VulnerabilityReport:
    return as_VulnerabilityReport(
        id_=f"{_BASE}/reports/{tag}", name=tag, content=f"report {tag}"
    )


@applied(MessageSemantics.CREATE_REPORT)
def create_report() -> Scenario:
    """A reporter's Create(Report): the receiver stores the report."""
    report = _report("create")
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_VENDOR)
    event = received_event(
        rm_create_report_activity(report, actor=_REPORTER, to=[_VENDOR]),
        receiving_actor_id=_VENDOR,
    )

    def _stored(store: SqliteDataLayer) -> str | None:
        if store.read(report.id_) is not None:
            return None
        return f"report {report.id_} was not stored"

    return Scenario(dl=dl, event=event, reached=_stored)


@applied(MessageSemantics.SUBMIT_REPORT)
def submit_report() -> Scenario:
    """A reporter's Offer(Report) to a vendor: it proposes a case (ADR-0041)."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_VENDOR)
    # The proposal Create carries the vendor's own actor record (CP-01-010).
    dl.save(VultronService(id_=_VENDOR))
    event = received_event(
        rm_submit_report_activity(
            _report("submit"), to=_VENDOR, actor=_REPORTER
        ),
        receiving_actor_id=_VENDOR,
    )
    return Scenario(dl=dl, event=event, run=_with_case_actor_service)


def _with_case_actor_service(dl: SqliteDataLayer, event: Any) -> Any:
    """Run one delivery with the case actor's service configured.

    The vendor proposes the case to the CASE_MANAGER it hosts there.
    """
    with config_override(
        VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL="http://case-actor:7999/api/v2"
    ):
        return run_use_case(dl, event)


def _offer_recorded_store() -> tuple[SqliteDataLayer, as_Offer]:
    """The reporter's store, holding the Offer it sent to the vendor."""
    from vultron.core.models.offer_record import VultronOfferRecord

    offer = rm_submit_report_activity(
        _report("offered"), to=_VENDOR, actor=_REPORTER
    )
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_REPORTER)
    dl.create(
        VultronOfferRecord(
            offer_id=offer.id_,
            report_id=f"{_BASE}/reports/offered",
            offer_actor_id=_REPORTER,
            offer_to=[_VENDOR],
        )
    )
    return dl, offer


@applied(MessageSemantics.ACK_REPORT)
def ack_report() -> Scenario:
    """The vendor's RK of the reporter's Offer: intake records it, no more."""
    dl, offer = _offer_recorded_store()
    event = received_event(
        rm_read_report_activity(offer, actor=_VENDOR, to=[_REPORTER]),
        receiving_actor_id=_REPORTER,
    )
    return Scenario(
        dl=dl, event=event, reached=_intake_recorded(event.activity_id)
    )


@applied(MessageSemantics.CLOSE_REPORT)
def close_report() -> Scenario:
    """The vendor closes the reporter's Offer before any case exists.

    No receiver applies a closure (CM-23-019): intake records it and the
    tree refuses it, as about a case the store does not hold (#2255).
    """
    dl, offer = _offer_recorded_store()
    event = received_event(
        rm_close_report_activity(offer, actor=_VENDOR, to=[_REPORTER]),
        receiving_actor_id=_REPORTER,
    )
    return Scenario(
        dl=dl,
        event=event,
        reached=_intake_recorded(event.activity_id),
        disposition=HandlerDisposition.REFUSED,
    )


def _with_embargo(dl: SqliteDataLayer) -> None:
    """Put an embargo in force on the case: RM.VALID needs one (DUR-07-004)."""
    embargo = EmbargoEvent(
        id_=f"{CASE_ID}/embargoes/rerun-sweep",
        context=CASE_ID,
        end_time=FAR_FUTURE,
    )
    dl.save(embargo)
    case = cast(VulnerabilityCase, dl.read(CASE_ID))
    activate(case, embargo.id_)
    dl.save(case)
    write_consent_rows(dl, case)


def _verdict(build, rm: RM = RM.RECEIVED) -> Scenario:
    dl = _store(MANAGER_ID, rm)
    _with_embargo(dl)
    event = received_event(
        build(_offer(), actor=FINDER_ID, to=[MANAGER_ID]), at=dl
    ).model_copy(update={"receiving_actor_id": MANAGER_ID})
    return Scenario(dl=dl, event=event)


@applied(MessageSemantics.VALIDATE_REPORT)
def validate_report() -> Scenario:
    """The finder validates at the CASE_MANAGER: committed with its status."""
    return _verdict(rm_validate_report_activity)


@refused(MessageSemantics.VALIDATE_REPORT)
def validate_report_backward() -> Scenario:
    """Validating after ACCEPTED is backward: refused, with the RSH-06-004 note."""
    return _verdict(rm_validate_report_activity, RM.ACCEPTED)


@applied(MessageSemantics.INVALIDATE_REPORT)
def invalidate_report() -> Scenario:
    """The finder invalidates at the CASE_MANAGER: committed with its status."""
    return _verdict(rm_invalidate_report_activity)


@refused(MessageSemantics.INVALIDATE_REPORT)
def invalidate_report_backward() -> Scenario:
    """Invalidating after ACCEPTED is backward: refused, with the note."""
    return _verdict(rm_invalidate_report_activity, RM.ACCEPTED)
