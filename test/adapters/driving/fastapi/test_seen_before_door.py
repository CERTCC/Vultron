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

"""A resend is answered from what the receiver recorded (AC-4 of #5045).

Each test seeds the record a first delivery left, posts the same body again
through the real inbox tree with the production ingress, dispatcher and
outcome adapters, and asserts the answer and that nothing was re-run:

- a receipt stub: ``REFUSED`` with the stub's reason (ADR-0154);
- an archive: ``SKIPPED``;
- a record waiting for a replay: ``SKIPPED``, the hold left as it was;
- a record a run left in holding with no verdict: the act runs again
  (CLP-10-074);
- in every case but the last, nothing is stored and nothing is sent, so no
  refusal notice goes out again.

A resend whose body differs, from a stub's digest or a held body, is a reused
id that ingress refuses before any door (IE-10-002); those are
``test_ingress_received_evidence.py``'s.
"""

from typing import Any

import pytest

from test.support.received import (
    archive_received,
    delivered_body,
    hold_deferred,
    intake_received,
)
from test.support.signing import signed_body
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driving.fastapi.inbox_handler import make_dispatcher
from vultron.adapters.driving.fastapi.inbox_orchestration import (
    FastAPIDispatchAdapter,
    FastAPIIngressAdapter,
    FastAPIReceivedOutcomePort,
)
from vultron.core.behaviors.inbox import (
    InboxOutcome,
    InboxOutcomeStatus,
    process_payload,
)
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
    ReceivedStage,
)
from vultron.core.services.received_activity import held_received_record
from vultron.core.services.received_outcome import write_receipt_stub
from vultron.wire.as2.factories import rm_create_report_activity
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

_SENDER_ID = "https://example.org/actors/seen-sender"
_RECEIVER_ID = "https://example.org/actors/seen-receiver"
_REPORT_ID = "https://example.org/reports/r-seen-1"
_STUB_REASON = "CreateReportBT: the first delivery was refused (HP-01-006)"


@pytest.fixture
def dl():
    store = SqliteDataLayer("sqlite:///:memory:", actor_id=_RECEIVER_ID)
    yield store
    store.close()


@pytest.fixture
def activity():
    return rm_create_report_activity(
        report=as_VulnerabilityReport(id_=_REPORT_ID, content="seen before"),
        actor=_SENDER_ID,
        to=[_RECEIVER_ID],
    )


@pytest.fixture
def body(activity) -> dict[str, Any]:
    """The body the sender delivers, signed, as intake's record holds it."""
    return signed_body(delivered_body(activity))


def _deliver(dl: SqliteDataLayer, body: dict[str, Any]) -> InboxOutcome:
    return process_payload(
        body,
        FastAPIIngressAdapter(dl=dl),
        FastAPIDispatchAdapter(
            dl=dl, actor_id=_RECEIVER_ID, dispatcher=make_dispatcher()
        ),
        received_outcome_port=FastAPIReceivedOutcomePort(dl),
    )


def _record(dl, activity) -> ReceivedActivityRecord | None:
    return held_received_record(dl, activity.id_)


def _nothing_ran(dl: SqliteDataLayer) -> None:
    """The handling tree did not run: no report stored, nothing sent."""
    assert dl.read(_REPORT_ID) is None
    assert dl.outbox_list() == []


@pytest.mark.spec("CLP-10-018")
@pytest.mark.spec("CLP-10-077")
def test_a_resend_of_a_refused_message_is_refused_with_its_first_reason(
    dl, activity, body
):
    parsed = parse_activity(body)
    write_receipt_stub(
        dl,
        activity.id_,
        sender_id=_SENDER_ID,
        reason=_STUB_REASON,
        received_body=parsed.received_evidence_json,
    )
    stub = _record(dl, activity)

    outcome = _deliver(dl, body)

    assert outcome.status is InboxOutcomeStatus.REJECTED
    assert outcome.failure_reason == _STUB_REASON
    assert _record(dl, activity) == stub
    _nothing_ran(dl)


@pytest.mark.spec("HP-01-003")
@pytest.mark.spec("IE-10-001")
def test_a_resend_of_an_applied_message_is_skipped(dl, activity, body):
    archived = archive_received(dl, activity)

    outcome = _deliver(dl, body)

    assert outcome.status is InboxOutcomeStatus.PROCESSED
    assert _record(dl, activity) == archived
    _nothing_ran(dl)


@pytest.mark.spec("HP-01-003")
@pytest.mark.spec("IO-03-009")
def test_a_resend_of_a_waiting_message_is_skipped_and_the_hold_stands(
    dl, activity, body
):
    held = hold_deferred(dl, activity)

    outcome = _deliver(dl, body)

    assert outcome.status is InboxOutcomeStatus.PROCESSED
    assert _record(dl, activity) == held
    _nothing_ran(dl)


@pytest.mark.spec("CLP-10-074")
def test_a_resend_of_a_message_left_in_holding_runs_it_again(
    dl, activity, body
):
    """The first run raised and left the record ``HELD`` owing nothing.

    A resend cannot meet a run in progress, because inbox runs are
    serialized per actor, so this is a run that ended with no verdict, and
    the act runs again from the held body (ADR-0154).
    """
    intake_received(dl, activity)

    outcome = _deliver(dl, body)

    assert outcome.status is InboxOutcomeStatus.PROCESSED, (
        outcome.failure_reason
    )
    assert dl.read(_REPORT_ID) is not None, "the act ran again"
    record = _record(dl, activity)
    assert record is not None
    assert record.stage is ReceivedStage.ARCHIVED


@pytest.mark.spec("CLP-10-073")
def test_a_first_delivery_is_archived_and_its_resend_skipped(
    dl, activity, body
):
    """End to end: applied once, archived, and the resend runs nothing."""
    first = _deliver(dl, body)
    assert first.status is InboxOutcomeStatus.PROCESSED, first.failure_reason
    record = _record(dl, activity)
    assert record is not None and record.stage is ReceivedStage.ARCHIVED
    sent = list(dl.outbox_list())

    again = _deliver(dl, body)

    assert again.status is InboxOutcomeStatus.PROCESSED
    assert _record(dl, activity) == record
    assert list(dl.outbox_list()) == sent
