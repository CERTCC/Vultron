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
"""A ``Close(Report)`` for a report that belongs to a case is refused (CM-23-019).

Once a report belongs to a case, only the Case Owner holds it, and the Case
Owner closes the case by ``Leave(VulnerabilityCase)``.  The CASE_MANAGER
therefore refuses ``Close(Report)`` from every sender: from the owner it is
the wrong closing act, from anyone else a message it has no report to send.
Nothing is committed, no RM state moves and nothing is sent.  Before this
rule the owner's own ``Close(Report)`` moved it to RM ``CLOSED`` while the
case stayed open (#4746).
"""

from typing import cast

import pytest

from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
    seed_case_owner_participant,
    seed_case_participant,
)
from test.support.received import received_event
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.events.report import CloseReportReceivedEvent
from vultron.core.models.offer_record import VultronOfferRecord
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.rm import RM
from vultron.core.use_cases.received.report import CloseReportReceivedUseCase
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import (
    rm_close_report_activity,
    rm_submit_report_activity,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

_MANAGER = "https://example.org/actors/close-report-manager"
_OWNER = "https://example.org/actors/close-report-owner"
_VENDOR = "https://example.org/actors/close-report-vendor"
_STRANGER = "https://example.org/actors/close-report-stranger"
_REPORT = "https://example.org/reports/close-report-on-case"
_CASE = "https://example.org/cases/close-report-on-case"


def _rm(dl: SqliteDataLayer, actor_id: str) -> RM | None:
    case = cast(as_VulnerabilityCase, dl.read(_CASE))
    record = dl.read(case.actor_participant_index[actor_id])
    assert isinstance(record, CaseParticipant)
    if not record.participant_statuses:
        return None
    return record.participant_statuses[-1].rm.state


def _store(
    *, closed: str | None = None, receiver: str = _MANAGER
) -> SqliteDataLayer:
    """*receiver*'s store: an open case holding the report.

    By default the CASE_MANAGER's store; any other *receiver* holds a
    replica.  The owner and a vendor are participants at RM ``ACCEPTED``;
    when *closed* names one of them, the case records that participant's
    closure.
    """
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=receiver)
    dl.save(as_VulnerabilityReport(id_=_REPORT, name="On-case report"))
    case = as_VulnerabilityCase(
        id_=_CASE, name="Close(Report) on a case", attributed_to=_MANAGER
    )
    case.vulnerability_reports.append(_REPORT)
    seed_case_manager_participant(dl, case, _MANAGER)
    owner = seed_case_owner_participant(dl, case, _OWNER)
    vendor = seed_case_participant(dl, case, _VENDOR, [CVDRole.VENDOR])
    for record in (owner, vendor):
        states = [RM.ACCEPTED]
        if record.attributed_to == closed:
            states.append(RM.CLOSED)
        for state in states:
            record.participant_statuses.append(
                ParticipantStatus(
                    context=_CASE,
                    attributed_to=record.attributed_to,
                    rm=RmDimension(state=state),
                )
            )
        dl.save(record)
    dl.create(case)
    return dl


def _close_report(
    sender: str, receiver: str = _MANAGER
) -> CloseReportReceivedEvent:
    offer = rm_submit_report_activity(
        as_VulnerabilityReport(id_=_REPORT, name="r"),
        to=_OWNER,
        actor=_STRANGER,
    )
    event = received_event(
        rm_close_report_activity(offer, actor=sender, to=[receiver])
    )
    return cast(
        CloseReportReceivedEvent,
        event.model_copy(update={"receiving_actor_id": receiver}),
    )


def _run(
    dl: SqliteDataLayer,
    sender: str,
    event: CloseReportReceivedEvent | None = None,
):
    return CloseReportReceivedUseCase(
        dl=dl,
        request=event if event is not None else _close_report(sender),
        sync_port=SyncActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()


@pytest.mark.spec("CM-23-019")
@pytest.mark.spec("CM-23-001")
@pytest.mark.parametrize("sender", [_OWNER, _VENDOR], ids=["owner", "vendor"])
def test_close_report_on_an_open_case_is_refused(sender: str) -> None:
    """The owner's and a participant's ``Close(Report)`` are both refused."""
    dl = _store()

    result = _run(dl, sender)

    assert result.disposition is HandlerDisposition.REFUSED, result.reason
    assert "No sender is entitled" in (result.reason or "")
    assert _rm(dl, sender) == RM.ACCEPTED
    assert _rm(dl, _OWNER if sender == _VENDOR else _VENDOR) == RM.ACCEPTED
    assert dl.list_objects("CaseLedgerEntry") == []
    assert dl.outbox_list() == []


@pytest.mark.spec("CM-23-019")
def test_close_report_at_a_participant_replica_is_refused() -> None:
    """A participant holding a replica refuses the owner's ``Close(Report)``
    too: no sender is entitled to send it to any case actor."""
    dl = _store(receiver=_VENDOR)

    result = _run(dl, _OWNER, _close_report(_OWNER, receiver=_VENDOR))

    assert result.disposition is HandlerDisposition.REFUSED, result.reason
    assert "No sender is entitled" in (result.reason or "")
    assert _rm(dl, _OWNER) == RM.ACCEPTED
    assert dl.list_objects("CaseLedgerEntry") == []
    assert dl.outbox_list() == []


@pytest.mark.spec("CM-23-019")
@pytest.mark.spec("CM-23-018")
def test_close_report_from_a_closed_sender_is_refused_not_skipped() -> None:
    """A closed participant's ``Close(Report)`` is refused like any other."""
    dl = _store(closed=_VENDOR)

    result = _run(dl, _VENDOR)

    assert result.disposition is HandlerDisposition.REFUSED, result.reason
    assert dl.list_objects("CaseLedgerEntry") == []
    assert dl.outbox_list() == []


@pytest.mark.spec("HP-01-006")
def test_close_report_from_a_non_participant_is_refused() -> None:
    """A sender the case does not list is refused like every other."""
    dl = _store()

    result = _run(dl, _STRANGER)

    assert result.disposition is HandlerDisposition.REFUSED
    assert "No sender is entitled" in (result.reason or "")
    assert dl.list_objects("CaseLedgerEntry") == []
    assert dl.outbox_list() == []


@pytest.mark.spec("CM-23-019")
@pytest.mark.spec("RMB-08-004")
def test_close_report_with_no_case_is_refused_as_before() -> None:
    """With no case for the report the receiver still refuses it (#2255).

    The sender is an addressee of the Offer, the pre-case standing, so the
    refusal is the unknown case's.
    """
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_MANAGER)
    dl.save(as_VulnerabilityReport(id_=_REPORT, name="Bare report"))
    event = _close_report(_VENDOR)
    assert event.offer_id is not None
    dl.create(
        VultronOfferRecord(
            offer_id=event.offer_id,
            report_id=_REPORT,
            offer_actor_id=_MANAGER,
            offer_to=[_VENDOR],
        )
    )

    result = _run(dl, _VENDOR, event)

    assert result.disposition is HandlerDisposition.REFUSED
    assert "no VulnerabilityCase" in (result.reason or "")
    assert dl.outbox_list() == []


@pytest.mark.spec("RMB-08-004")
def test_close_report_with_no_case_from_a_non_addressee_is_refused() -> None:
    """Before a case, only an addressee of the Offer may close it."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_MANAGER)
    dl.save(as_VulnerabilityReport(id_=_REPORT, name="Bare report"))

    result = _run(dl, _STRANGER)

    assert result.disposition is HandlerDisposition.REFUSED
    assert dl.outbox_list() == []
