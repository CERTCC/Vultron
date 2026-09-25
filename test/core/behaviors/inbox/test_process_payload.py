#!/usr/bin/env python
"""Tests for the core BT inbox orchestration module.

Asserts on :class:`InboxOutcome` fields only — no patching of internal
BT node helpers (IO-04-002).
"""

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

import logging
from enum import StrEnum
from typing import Any

import pytest
from pydantic import ValidationError

from vultron.core.behaviors.inbox import (
    InboxOutcome,
    InboxOutcomeStatus,
    process_payload,
)
from vultron.core.models.events import VultronEvent
from vultron.core.models.use_case_result import HandlerResult
from vultron.wire.as2.factories import (
    add_note_to_case_activity,
    announce_vulnerability_case_activity,
    rm_create_report_activity,
)
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

SENDER_ID = "https://example.org/actors/sender"
RECEIVER_ID = "https://example.org/actors/receiver"
CASE_ID = "https://example.org/cases/case-io-test"
UNKNOWN_CASE_ID = "https://example.org/cases/case-unknown"


# ---------------------------------------------------------------------------
# Stub implementations
# ---------------------------------------------------------------------------


class _StubIngressAdapter:
    """IngressPayloadAdapter stub for unit tests."""

    def __init__(
        self,
        activity: Any = None,
        rehydrated: Any = None,
        fail_parse: bool = False,
    ) -> None:
        self._activity = activity
        self._rehydrated = rehydrated or activity
        self._fail_parse = fail_parse

    def parse(self, payload: Any) -> Any:
        if self._fail_parse:
            return None
        return self._activity

    def rehydrate(self, activity: Any) -> Any:
        return self._rehydrated or activity


class _StubDispatchAdapter:
    """DispatchAdapter stub that records dispatched events.

    Returns *result* from every dispatch; ``APPLIED`` unless a test says
    otherwise.
    """

    def __init__(
        self,
        should_fail: bool = False,
        result: HandlerResult | None = None,
    ) -> None:
        self.dispatched: list[VultronEvent] = []
        self._should_fail = should_fail
        self._result = result or HandlerResult.applied()

    def dispatch(self, event: VultronEvent) -> HandlerResult:
        if self._should_fail:
            raise RuntimeError("Dispatch error (stub)")
        self.dispatched.append(event)
        return self._result


class _StubQueuePort:
    """PendingCaseQueuePort stub for testing defer/replay logic."""

    def __init__(
        self,
        case_known: bool = True,
        queue_expired: bool = False,
    ) -> None:
        self._case_known = case_known
        self._queue_expired = queue_expired
        self.queued: list[tuple[str, str, str | None]] = []
        self.replayed: list[str] = []

    def is_case_known(self, case_id: str) -> bool:
        return self._case_known

    def queue(
        self,
        activity_id: str,
        case_id: str,
        case_actor_id: str | None = None,
    ) -> None:
        self.queued.append((activity_id, case_id, case_actor_id))

    def check_and_expire(self, case_id: str) -> bool:
        return self._queue_expired

    def replay(self, case_id: str) -> None:
        self.replayed.append(case_id)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def report_activity():
    report = as_VulnerabilityReport(
        id_="https://example.org/reports/r-io-1",
        content="test report",
    )
    return rm_create_report_activity(report, actor=SENDER_ID, to=[RECEIVER_ID])


@pytest.fixture()
def case_activity():
    case = as_VulnerabilityCase(
        id_=CASE_ID,
        name="CASE-IO",
    )
    return announce_vulnerability_case_activity(
        case, actor=SENDER_ID, to=[RECEIVER_ID]
    )


@pytest.fixture()
def note_activity_unknown_case():
    note = as_Note(id_="https://example.org/notes/n-io-1", content="note")
    return add_note_to_case_activity(
        note,
        target=UNKNOWN_CASE_ID,
        context=UNKNOWN_CASE_ID,
        actor=SENDER_ID,
        to=[RECEIVER_ID],
    )


# ---------------------------------------------------------------------------
# AC-2: InboxOutcome model
# ---------------------------------------------------------------------------


class TestInboxOutcomeModel:
    def test_processed_status(self):
        o = InboxOutcome(status=InboxOutcomeStatus.PROCESSED)
        assert o.status == "processed"
        assert o.context_id is None
        assert o.failure_reason is None

    def test_deferred_status_with_fields(self):
        o = InboxOutcome(
            status=InboxOutcomeStatus.DEFERRED,
            context_id=CASE_ID,
            failure_reason="case not yet known",
        )
        assert o.status == "deferred"
        assert o.context_id == CASE_ID
        assert o.failure_reason == "case not yet known"

    def test_rejected_status_with_reason(self):
        o = InboxOutcome(
            status=InboxOutcomeStatus.REJECTED, failure_reason="parse failed"
        )
        assert o.status == "rejected"
        assert o.failure_reason == "parse failed"

    def test_status_is_a_str_enum_member(self):
        """UCORG-05-011: the status vocabulary is a StrEnum, not a Literal."""
        assert issubclass(InboxOutcomeStatus, StrEnum)
        o = InboxOutcome.model_validate({"status": "processed"})
        assert o.status is InboxOutcomeStatus.PROCESSED

    def test_status_members_are_exactly_the_three(self):
        assert {m.value for m in InboxOutcomeStatus} == {
            "processed",
            "deferred",
            "rejected",
        }

    def test_unknown_status_is_rejected(self):
        with pytest.raises(ValidationError):
            InboxOutcome.model_validate({"status": "applied"})

    @pytest.mark.spec("CS-08-002")
    @pytest.mark.parametrize("blank", ["", "   "])
    def test_blank_activity_id_is_rejected(self, blank):
        """If present, ``activity_id`` is non-empty (CS-08-002)."""
        with pytest.raises(ValidationError):
            InboxOutcome(
                status=InboxOutcomeStatus.PROCESSED, activity_id=blank
            )


# ---------------------------------------------------------------------------
# AC-6: rejected InboxOutcome for invalid payloads — no exception raised
# ---------------------------------------------------------------------------


class TestProcessPayloadRejectsInvalidInput:
    @pytest.mark.spec("MV-01-001")
    def test_none_parse_result_returns_rejected(self, report_activity):
        """When IngressAdapter.parse returns None, outcome is rejected."""
        ingress = _StubIngressAdapter(activity=None, fail_parse=True)
        dispatch = _StubDispatchAdapter()

        outcome = process_payload({}, ingress, dispatch)

        assert isinstance(outcome, InboxOutcome)
        assert outcome.status == "rejected"
        assert outcome.failure_reason is not None
        assert outcome.activity_id is None  # no event was extracted

    @pytest.mark.spec("MV-01-007")
    def test_dispatch_failure_returns_rejected(self, report_activity):
        """When dispatch raises, outcome is rejected; no exception propagates."""
        ingress = _StubIngressAdapter(activity=report_activity)
        dispatch = _StubDispatchAdapter(should_fail=True)

        outcome = process_payload({}, ingress, dispatch)

        assert isinstance(outcome, InboxOutcome)
        assert outcome.status == "rejected"
        assert outcome.failure_reason is not None


# ---------------------------------------------------------------------------
# AC-3 / AC-5: happy path returns processed
# ---------------------------------------------------------------------------


class TestProcessPayloadHappyPath:
    def test_processed_for_report_activity(self, report_activity):
        """Non-case-scoped activity is dispatched and returns processed."""
        ingress = _StubIngressAdapter(activity=report_activity)
        dispatch = _StubDispatchAdapter()

        outcome = process_payload({}, ingress, dispatch)

        assert outcome.status == "processed"
        assert outcome.failure_reason is None
        assert len(dispatch.dispatched) == 1

    @pytest.mark.spec("SL-02-001")
    def test_outcome_names_the_dispatched_activity(self, report_activity):
        """The outcome carries the activity id so a rejection log can cite it."""
        outcome = process_payload(
            {},
            _StubIngressAdapter(activity=report_activity),
            _StubDispatchAdapter(result=HandlerResult.refused("no")),
        )

        assert outcome.activity_id == report_activity.id_

    def test_context_id_none_for_non_case_scoped(self, report_activity):
        ingress = _StubIngressAdapter(activity=report_activity)
        dispatch = _StubDispatchAdapter()

        outcome = process_payload({}, ingress, dispatch)

        assert outcome.status == "processed"
        # Reports are not case-scoped
        assert outcome.context_id is None


# ---------------------------------------------------------------------------
# AC-7: deferred outcome when case context unknown
# ---------------------------------------------------------------------------


class TestProcessPayloadDeferral:
    def test_deferred_for_unknown_case(self, note_activity_unknown_case):
        """Activity for unknown case returns deferred outcome."""
        ingress = _StubIngressAdapter(activity=note_activity_unknown_case)
        dispatch = _StubDispatchAdapter()
        queue = _StubQueuePort(case_known=False)

        outcome = process_payload({}, ingress, dispatch, queue)

        assert outcome.status == "deferred"
        assert outcome.failure_reason is not None
        assert len(queue.queued) == 1
        assert len(dispatch.dispatched) == 0

    def test_deferred_carries_context_id(self, note_activity_unknown_case):
        ingress = _StubIngressAdapter(activity=note_activity_unknown_case)
        dispatch = _StubDispatchAdapter()
        queue = _StubQueuePort(case_known=False)

        outcome = process_payload({}, ingress, dispatch, queue)

        assert outcome.status == "deferred"
        assert outcome.context_id == UNKNOWN_CASE_ID

    def test_rejected_when_queue_expired(self, note_activity_unknown_case):
        """Expired pending queue returns rejected, not deferred."""
        ingress = _StubIngressAdapter(activity=note_activity_unknown_case)
        dispatch = _StubDispatchAdapter()
        queue = _StubQueuePort(case_known=False, queue_expired=True)

        outcome = process_payload({}, ingress, dispatch, queue)

        assert outcome.status == "rejected"
        assert outcome.failure_reason is not None
        assert len(queue.queued) == 0


# ---------------------------------------------------------------------------
# Bootstrap replay trigger
# ---------------------------------------------------------------------------


class TestProcessPayloadBootstrap:
    def test_bootstrap_triggers_replay(self, case_activity):
        """ANNOUNCE_VULNERABILITY_CASE dispatch triggers queue.replay."""
        ingress = _StubIngressAdapter(activity=case_activity)
        dispatch = _StubDispatchAdapter()
        queue = _StubQueuePort(case_known=True)

        outcome = process_payload({}, ingress, dispatch, queue)

        assert outcome.status == "processed"
        assert CASE_ID in queue.replayed

    def test_bootstrap_skips_defer_check(self, case_activity):
        """Bootstrap activity is never deferred even when case unknown."""
        ingress = _StubIngressAdapter(activity=case_activity)
        dispatch = _StubDispatchAdapter()
        # case_known=False would defer non-bootstrap, but bootstrap skips
        queue = _StubQueuePort(case_known=False)

        outcome = process_payload({}, ingress, dispatch, queue)

        assert outcome.status == "processed"
        assert len(queue.queued) == 0


# ---------------------------------------------------------------------------
# No queue_port — skip defer check, allow dispatch
# ---------------------------------------------------------------------------


class TestProcessPayloadNoQueuePort:
    def test_no_queue_port_skips_defer(self, note_activity_unknown_case):
        """Without a queue port, activities proceed to dispatch."""
        ingress = _StubIngressAdapter(activity=note_activity_unknown_case)
        dispatch = _StubDispatchAdapter()

        outcome = process_payload({}, ingress, dispatch, queue_port=None)

        assert outcome.status == "processed"
        assert len(dispatch.dispatched) == 1


# ---------------------------------------------------------------------------
# Thread safety: concurrent calls do not corrupt each other's outcomes
# ---------------------------------------------------------------------------


class TestProcessPayloadThreadSafety:
    def test_concurrent_calls_independent_outcomes(self, report_activity):
        """Multiple calls from different threads get independent outcomes."""
        import threading

        results: list[InboxOutcome] = []
        errors: list[Exception] = []

        def _run() -> None:
            try:
                ingress = _StubIngressAdapter(activity=report_activity)
                dispatch = _StubDispatchAdapter()
                outcome = process_payload({}, ingress, dispatch)
                results.append(outcome)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_run) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert all(o.status == "processed" for o in results)
        assert len(results) == 4


# ---------------------------------------------------------------------------
# Log-level contract (SL-04-007)
# ---------------------------------------------------------------------------


class TestProcessPayloadLogLevels:
    """The `process_payload: outcome status=...` echo is DEBUG (SL-04-007).

    It restates the outcome the caller already has; the meaningful protocol
    lines are emitted by the use cases the dispatcher invokes.
    """

    _LOGGER = "vultron.core.behaviors.inbox._process_payload"

    def _outcome_records(self, caplog):
        return [
            r
            for r in caplog.records
            if "process_payload: outcome" in r.getMessage()
        ]

    def test_outcome_echo_is_debug(self, report_activity, caplog):
        import logging

        ingress = _StubIngressAdapter(activity=report_activity)
        dispatch = _StubDispatchAdapter()

        with caplog.at_level(logging.DEBUG, logger=self._LOGGER):
            process_payload({}, ingress, dispatch)

        records = self._outcome_records(caplog)
        assert records, "Expected the process_payload outcome log entry"
        assert all(r.levelno == logging.DEBUG for r in records)

    def test_outcome_echo_not_emitted_at_info(self, report_activity, caplog):
        import logging

        ingress = _StubIngressAdapter(activity=report_activity)
        dispatch = _StubDispatchAdapter()

        with caplog.at_level(logging.INFO, logger=self._LOGGER):
            process_payload({}, ingress, dispatch)

        assert not self._outcome_records(caplog)


# ---------------------------------------------------------------------------
# Handler disposition → outcome status (UCORG-05-011, HP-01-004)
# ---------------------------------------------------------------------------


class _NoVerdictDispatchAdapter:
    """DispatchAdapter that breaks the contract by returning ``None``."""

    def dispatch(self, event: VultronEvent) -> Any:
        return None


class TestProcessPayloadHandlerDisposition:
    @pytest.mark.spec("UCORG-05-011")
    @pytest.mark.parametrize(
        ("result", "status"),
        [
            (HandlerResult.applied(), InboxOutcomeStatus.PROCESSED),
            (HandlerResult.skipped("duplicate"), InboxOutcomeStatus.PROCESSED),
            (HandlerResult.skipped(), InboxOutcomeStatus.PROCESSED),
            (
                HandlerResult.deferred("awaiting 3"),
                InboxOutcomeStatus.DEFERRED,
            ),
            (HandlerResult.refused("not a peer"), InboxOutcomeStatus.REJECTED),
        ],
    )
    def test_status_follows_disposition(self, report_activity, result, status):
        ingress = _StubIngressAdapter(activity=report_activity)
        dispatch = _StubDispatchAdapter(result=result)

        outcome = process_payload({}, ingress, dispatch)

        assert outcome.status is status

    @pytest.mark.spec("UCORG-05-011")
    def test_refusal_reason_becomes_failure_reason(self, report_activity):
        ingress = _StubIngressAdapter(activity=report_activity)
        dispatch = _StubDispatchAdapter(
            result=HandlerResult.refused("sender is not a participant")
        )

        outcome = process_payload({}, ingress, dispatch)

        assert outcome.failure_reason == "sender is not a participant"

    @pytest.mark.spec("UCORG-05-011")
    def test_handler_deferral_keeps_its_reason(self, report_activity):
        ingress = _StubIngressAdapter(activity=report_activity)
        dispatch = _StubDispatchAdapter(
            result=HandlerResult.deferred("awaiting entry 3")
        )

        outcome = process_payload({}, ingress, dispatch)

        assert outcome.failure_reason == "awaiting entry 3"

    def test_handler_deferral_without_reason_still_explains(
        self, report_activity
    ):
        ingress = _StubIngressAdapter(activity=report_activity)
        dispatch = _StubDispatchAdapter(result=HandlerResult.deferred())

        outcome = process_payload({}, ingress, dispatch)

        assert outcome.status is InboxOutcomeStatus.DEFERRED
        assert outcome.failure_reason

    @pytest.mark.spec("UCORG-05-012")
    def test_dispatch_without_a_verdict_is_rejected(self, report_activity):
        """No verdict is not success: the old "did not raise" inference."""
        ingress = _StubIngressAdapter(activity=report_activity)

        outcome = process_payload({}, ingress, _NoVerdictDispatchAdapter())

        assert outcome.status is InboxOutcomeStatus.REJECTED
        assert "HandlerResult" in (outcome.failure_reason or "")

    @pytest.mark.parametrize(
        ("result", "replays"),
        [
            (HandlerResult.skipped("case already present"), True),
            (HandlerResult.refused("not the case owner"), False),
            (HandlerResult.deferred("awaiting predecessor"), False),
        ],
    )
    def test_bootstrap_replays_only_when_processed(
        self, case_activity, result, replays
    ):
        ingress = _StubIngressAdapter(activity=case_activity)
        queue = _StubQueuePort(case_known=True)

        process_payload(
            {}, ingress, _StubDispatchAdapter(result=result), queue
        )

        assert (CASE_ID in queue.replayed) is replays


class _FailingReplayQueuePort(_StubQueuePort):
    """Queue port whose ``replay()`` raises, as a DataLayer fault would."""

    def replay(self, case_id: str) -> None:
        raise RuntimeError("replay storage fault (stub)")


class TestDispatchNodeFaults:
    @pytest.mark.spec("MV-01-007")
    def test_replay_failure_does_not_reject_an_applied_bootstrap(
        self, case_activity, caplog
    ):
        ingress = _StubIngressAdapter(activity=case_activity)

        with caplog.at_level(logging.ERROR):
            outcome = process_payload(
                {},
                ingress,
                _StubDispatchAdapter(result=HandlerResult.applied()),
                _FailingReplayQueuePort(case_known=True),
            )

        assert outcome.status is InboxOutcomeStatus.PROCESSED
        replay_errors = [
            r for r in caplog.records if "replay failed" in r.getMessage()
        ]
        assert len(replay_errors) == 1
        assert replay_errors[0].exc_info is not None

    def test_dispatch_raise_is_logged_with_its_traceback(
        self, report_activity, caplog
    ):
        """A raise is a programming error, not a REFUSED: keep the trace."""
        ingress = _StubIngressAdapter(activity=report_activity)

        with caplog.at_level(logging.WARNING):
            outcome = process_payload(
                {}, ingress, _StubDispatchAdapter(should_fail=True)
            )

        assert outcome.status is InboxOutcomeStatus.REJECTED
        raised = [
            r for r in caplog.records if "dispatch raised" in r.getMessage()
        ]
        assert len(raised) == 1
        assert raised[0].exc_info is not None
        assert raised[0].exc_info[0] is RuntimeError
