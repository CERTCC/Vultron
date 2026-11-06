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

"""What remains after each final outcome (AC-3 of #5045, ADR-0154).

The outcome stage runs after the dispatch, on every path the dispatch can
take, and maps the handler's one verdict onto what the receiver keeps:

- applied, skipped: the record intake wrote is archived with the sealed body
  (CLP-10-017, CLP-10-073);
- refused: a receipt stub, with the sender, the activity id, the time of
  receipt, the reason and the body's digest, and no body (CLP-10-018), also
  when no record was written yet because nothing ran intake;
- a semantic type no use case handles: refused, so a receipt stub and no body
  (CLP-10-074);
- a duplicate of an applied message: ``SKIPPED``, and nothing new stored;
- deferred: the message is still waiting, so the holding record stands
  (IO-03-009);
- a dispatch that raised: nothing judged the message, so the body stays for
  the re-run (ADR-0151, CLP-10-074).

Each test drives the real inbox tree through ``process_payload`` with the
production ingress, dispatch and outcome adapters.  The handler is a stub for
the per-verdict tests, because the verdict is exactly the variable under
test; the duplicate test uses the production dispatcher end to end.
"""

import json
import logging
from typing import Any, cast

import pytest

from test.support.received import delivered_body, intake_received
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
from vultron.core.dispatcher import DirectActivityDispatcher
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
    ReceivedStage,
)
from vultron.core.models.received_body import received_body_digest
from vultron.core.models.use_case_result import HandlerResult
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.dispatcher import ActivityDispatcher
from vultron.core.services.received_activity import (
    held_received_body,
    held_received_record,
)
from vultron.core.services.received_holding import hold_for_replay
from vultron.wire.as2.factories import rm_create_report_activity
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

_SENDER_ID = "https://example.org/actors/outcome-sender"
_RECEIVER_ID = "https://example.org/actors/outcome-receiver"
_REASON = "sender is not a participant of the case (HP-01-006)"


@pytest.fixture
def dl():
    """The receiving actor's own store (ADR-0073)."""
    store = SqliteDataLayer("sqlite:///:memory:", actor_id=_RECEIVER_ID)
    yield store
    store.close()


def _report_activity(tag: str = "1"):
    return rm_create_report_activity(
        report=as_VulnerabilityReport(
            id_=f"https://example.org/reports/r-outcome-{tag}",
            content=f"outcome report {tag}",
        ),
        actor=_SENDER_ID,
        to=[_RECEIVER_ID],
    )


@pytest.fixture
def activity():
    return _report_activity()


@pytest.fixture
def body(activity) -> dict[str, Any]:
    return delivered_body(activity)


class _ReadsTheBodyThenAnswers:
    """A handler that reads the body from the record, then returns a verdict.

    It reads it through :func:`held_received_body`, which is the function the
    refusal notice reads it through, so a stub written before the handler ran
    would fail this handler exactly as it would fail the notice
    (CLP-05-001, CLP-10-073).
    """

    verdict: HandlerResult = HandlerResult.applied()
    bodies_read: list[dict[str, Any]] = []

    def __init__(self, dl: Any, request: Any) -> None:
        self._dl = dl
        self._request = request

    def execute(self) -> HandlerResult:
        type(self).bodies_read.append(
            held_received_body(
                cast(CasePersistence, self._dl), self._request.activity_id
            )
        )
        return type(self).verdict


class _DefersAndHolds:
    """A handler that holds the body for a replay, then defers.

    The shape of the buffered ``Announce(CaseLedgerEntry)`` whose handler
    finds a ledger gap after intake recorded the body (SYNC-14-001): the
    record is in holding *and* owes a replay when the outcome stage runs.
    """

    def __init__(self, dl: Any, request: Any) -> None:
        self._dl = dl
        self._request = request

    def execute(self) -> HandlerResult:
        persistence = cast(CasePersistence, self._dl)
        record = held_received_record(persistence, self._request.activity_id)
        assert record is not None and record.received_body is not None
        hold_for_replay(
            persistence, self._request.activity_id, record.received_body
        )
        return HandlerResult.deferred("awaiting entry 3")


class _HoldsThenRefuses(_DefersAndHolds):
    """A handler that holds the body for a replay, then refuses.

    The record still owes that replay when the outcome stage runs, so the
    body is the replay's to route and is not given up (CLP-10-076).
    """

    def execute(self) -> HandlerResult:
        super().execute()
        return HandlerResult.refused(_REASON)


class _SpyOutcomePort(FastAPIReceivedOutcomePort):
    """The production port, recording every outcome that reaches it."""

    def __init__(self, dl: SqliteDataLayer) -> None:
        super().__init__(dl)
        self.refused: list[str] = []
        self.applied: list[str] = []

    def apply(self, activity_id: str) -> None:
        self.applied.append(activity_id)
        super().apply(activity_id)

    def refuse(
        self,
        activity_id: str,
        *,
        sender_id: str,
        reason: str,
        received_body: str | None,
    ) -> None:
        self.refused.append(activity_id)
        super().refuse(
            activity_id,
            sender_id=sender_id,
            reason=reason,
            received_body=received_body,
        )


class _RefusesUnread:
    """A handler that refuses without reading anything, as a door does."""

    def __init__(self, dl: Any, request: Any) -> None:
        pass

    def execute(self) -> HandlerResult:
        return HandlerResult.refused(_REASON)


class _AppliesUnread:
    """A handler that applies without running intake: no tree at all."""

    def __init__(self, dl: Any, request: Any) -> None:
        pass

    def execute(self) -> HandlerResult:
        return HandlerResult.applied()


class _Raises:
    """A handler whose dispatch raises: an internal error, not a verdict."""

    def __init__(self, dl: Any, request: Any) -> None:
        pass

    def execute(self) -> HandlerResult:
        raise RuntimeError("a bug in the handler, not the sender's doing")


def _dispatcher_for(use_case: type | None) -> DirectActivityDispatcher:
    """A dispatcher routing ``Create(Report)`` to *use_case*, or to nothing."""
    return DirectActivityDispatcher(
        use_case_map=(
            {}
            if use_case is None
            else {MessageSemantics.CREATE_REPORT: use_case}
        )
    )


def _deliver(
    dl: SqliteDataLayer,
    body: dict[str, Any],
    dispatcher: ActivityDispatcher,
    outcome_port: FastAPIReceivedOutcomePort | None = None,
) -> InboxOutcome:
    """One delivery through the real inbox tree, outcome port wired."""
    return process_payload(
        body,
        FastAPIIngressAdapter(dl=dl),
        FastAPIDispatchAdapter(
            dl=dl, actor_id=_RECEIVER_ID, dispatcher=dispatcher
        ),
        received_outcome_port=outcome_port or FastAPIReceivedOutcomePort(dl),
    )


def _answering(verdict: HandlerResult) -> type:
    """:class:`_ReadsTheBodyThenAnswers`, armed with *verdict*."""
    _ReadsTheBodyThenAnswers.verdict = verdict
    _ReadsTheBodyThenAnswers.bodies_read = []
    return _ReadsTheBodyThenAnswers


def _records(dl: SqliteDataLayer) -> list[ReceivedActivityRecord]:
    return [
        obj
        for obj in dl.list_objects(ReceivedActivityRecord.__name__)
        if isinstance(obj, ReceivedActivityRecord)
    ]


# ---------------------------------------------------------------------------
# applied and skipped: the record intake wrote is archived
# ---------------------------------------------------------------------------


@pytest.mark.spec("CLP-10-017")
@pytest.mark.spec("CLP-10-073")
@pytest.mark.parametrize(
    "verdict",
    [HandlerResult.applied(), HandlerResult.skipped("already applied")],
    ids=["applied", "skipped"],
)
def test_an_applied_or_skipped_message_keeps_its_sealed_body(
    dl, activity, body, verdict
):
    intake_received(dl, activity)
    sealed = json.dumps(body, sort_keys=False)

    outcome = _deliver(dl, body, _dispatcher_for(_answering(verdict)))

    assert outcome.status is InboxOutcomeStatus.PROCESSED
    record = held_received_record(dl, activity.id_)
    assert record is not None
    assert record.stage is ReceivedStage.ARCHIVED
    assert record.received_body is not None
    assert json.loads(record.received_body) == json.loads(sealed)
    # Nothing derived from the body is stored beside it (ADR-0149).
    assert record.sender_id is None
    assert record.refusal_reason is None
    assert record.body_hash is None
    assert len(_records(dl)) == 1


# ---------------------------------------------------------------------------
# refused: a receipt stub, with no body
# ---------------------------------------------------------------------------


@pytest.mark.spec("CLP-10-018")
@pytest.mark.spec("CLP-10-073")
def test_a_refused_message_leaves_a_receipt_stub_with_no_body(
    dl, activity, body
):
    stored = intake_received(dl, activity)
    sealed = stored.received_body
    assert sealed is not None

    outcome = _deliver(
        dl, body, _dispatcher_for(_answering(HandlerResult.refused(_REASON)))
    )

    assert outcome.status is InboxOutcomeStatus.REJECTED
    record = held_received_record(dl, activity.id_)
    assert record is not None
    assert record.is_receipt_stub
    assert record.received_body is None
    assert record.sender_id == _SENDER_ID
    assert record.refusal_reason is not None
    assert _REASON in record.refusal_reason
    assert record.body_hash == received_body_digest(sealed)
    assert record.received_at == stored.received_at
    # One row, not a stub beside the archive it replaced.
    assert len(_records(dl)) == 1


@pytest.mark.spec("CLP-05-001")
def test_the_run_reads_the_body_before_the_stub_replaces_it(
    dl, activity, body
):
    """The refusal notice embeds the body, so the stub comes after the run.

    The handler here reads it through the same function the notice reads it
    through.  Were the stub written before the dispatch, this read would
    raise and the outcome would be an internal error, not a refusal.
    """
    intake_received(dl, activity)
    use_case = _answering(HandlerResult.refused(_REASON))

    outcome = _deliver(dl, body, _dispatcher_for(use_case))

    assert outcome.status is InboxOutcomeStatus.REJECTED
    assert outcome.failure_reason is not None
    assert _REASON in outcome.failure_reason
    assert [read["id"] for read in use_case.bodies_read] == [activity.id_]
    record = held_received_record(dl, activity.id_)
    assert record is not None and record.is_receipt_stub


# ---------------------------------------------------------------------------
# deferred: the message is still waiting
# ---------------------------------------------------------------------------


@pytest.mark.spec("IO-03-009")
@pytest.mark.spec("CLP-10-073")
def test_a_deferred_message_stays_in_holding_with_its_body(dl, activity, body):
    stored = intake_received(dl, activity)
    sealed = stored.received_body
    assert sealed is not None
    port = _SpyOutcomePort(dl)

    outcome = _deliver(dl, body, _dispatcher_for(_DefersAndHolds), port)

    assert outcome.status is InboxOutcomeStatus.DEFERRED
    # Deferred is no outcome: the port is asked neither to archive nor to
    # leave a stub.
    assert port.refused == []
    assert port.applied == []
    record = held_received_record(dl, activity.id_)
    assert record is not None
    assert record.received_body == sealed
    assert record.replay_owed is True
    assert record.stage is ReceivedStage.HELD


@pytest.mark.spec("CLP-10-076")
def test_a_refusal_of_a_body_still_owed_to_a_replay_leaves_it_held(
    dl, activity, body, caplog
):
    """The replay routes that body, so the refusal gives nothing up.

    Not a fault either: nothing is logged at ERROR (the held message
    reaches its own outcome when the replay runs).
    """
    stored = intake_received(dl, activity)
    sealed = stored.received_body
    port = _SpyOutcomePort(dl)

    with caplog.at_level(logging.INFO):
        outcome = _deliver(dl, body, _dispatcher_for(_HoldsThenRefuses), port)

    assert outcome.status is InboxOutcomeStatus.REJECTED
    assert port.refused == [activity.id_]
    record = held_received_record(dl, activity.id_)
    assert record is not None
    assert not record.is_receipt_stub
    assert record.received_body == sealed
    assert record.replay_owed is True
    assert [r for r in caplog.records if r.levelno >= logging.ERROR] == []


# ---------------------------------------------------------------------------
# no verdict at all: nothing judged the message
# ---------------------------------------------------------------------------


@pytest.mark.spec("CLP-10-074")
def test_a_dispatch_that_raised_leaves_the_body_for_the_re_run(
    dl, activity, body
):
    """An internal error is not an outcome, so nothing is given up."""
    stored = intake_received(dl, activity)

    outcome = _deliver(dl, body, _dispatcher_for(_Raises))

    assert outcome.status is InboxOutcomeStatus.REJECTED
    record = held_received_record(dl, activity.id_)
    assert record is not None
    assert record.received_body == stored.received_body
    assert not record.is_receipt_stub


@pytest.mark.spec("CLP-10-074")
@pytest.mark.spec("CLP-10-018")
@pytest.mark.spec("IO-01-005")
def test_an_unhandled_semantic_type_leaves_a_stub(dl, activity, body):
    """No use case applies it, so the receiver keeps no copy of it.

    A sender cannot make a receiver keep an arbitrary body by choosing a
    type it does not handle (ADR-0154): like any refusal, it leaves a
    receipt stub with no body.  No use case ran, so no intake wrote a
    record first: the stub is written from the delivery's own sealed body.
    """
    sealed = json.dumps(body, sort_keys=False)

    outcome = _deliver(dl, body, _dispatcher_for(None))

    assert outcome.status is InboxOutcomeStatus.REJECTED
    assert outcome.unhandled
    record = held_received_record(dl, activity.id_)
    assert record is not None
    assert record.is_receipt_stub
    assert record.received_body is None
    assert record.sender_id == _SENDER_ID
    assert record.refusal_reason
    assert record.body_hash is not None
    assert json.loads(sealed)["id"] == activity.id_
    assert len(_records(dl)) == 1


@pytest.mark.spec("CLP-10-018")
def test_a_refusal_before_any_intake_leaves_a_stub_of_the_delivered_body(
    dl, activity, body
):
    """A door refuses before intake writes anything (ADR-0154).

    The handler here records nothing, as a tree whose door refused records
    nothing, so the stub's digest is the delivery's own sealed body's.
    """
    ingress = FastAPIIngressAdapter(dl=dl)
    parsed = ingress.parse(body)
    assert parsed is not None
    sealed = parsed.received_evidence_json
    assert sealed is not None

    outcome = _deliver(dl, body, _dispatcher_for(_RefusesUnread))

    assert outcome.status is InboxOutcomeStatus.REJECTED
    record = held_received_record(dl, activity.id_)
    assert record is not None and record.is_receipt_stub
    assert record.body_hash == received_body_digest(sealed)
    assert record.sender_id == _SENDER_ID


@pytest.mark.spec("CLP-10-073")
def test_an_applied_message_with_no_intake_record_leaves_nothing(
    dl, activity, body
):
    """A tree-less handler wrote no record, so there is nothing to archive."""
    outcome = _deliver(dl, body, _dispatcher_for(_AppliesUnread))

    assert outcome.status is InboxOutcomeStatus.PROCESSED
    assert _records(dl) == []


# ---------------------------------------------------------------------------
# a duplicate of an applied message: SKIPPED, nothing new stored
# ---------------------------------------------------------------------------


@pytest.mark.spec("HP-01-003")
@pytest.mark.spec("IE-10-001")
def test_a_duplicate_of_an_applied_message_stores_nothing_new(dl, body):
    """Driven end to end through the production dispatcher."""
    first = _deliver(dl, body, make_dispatcher())
    assert first.status is InboxOutcomeStatus.PROCESSED, first.failure_reason
    before = cast(dict[str, Any], dl.all())
    snapshot = {
        key: obj.model_dump(mode="json", by_alias=True)
        for key, obj in before.items()
    }

    again = _deliver(dl, body, make_dispatcher())

    assert again.status is InboxOutcomeStatus.PROCESSED
    after = cast(dict[str, Any], dl.all())
    assert {
        key: obj.model_dump(mode="json", by_alias=True)
        for key, obj in after.items()
    } == snapshot
    assert len(_records(dl)) == 1
    assert dl.outbox_list() == []
