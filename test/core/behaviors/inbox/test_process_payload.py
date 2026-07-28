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

from typing import Any

import pytest

from vultron.core.behaviors.inbox import (
    InboxOutcome,
    process_payload,
)
from vultron.core.models.events import VultronEvent
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
    """DispatchAdapter stub that records dispatched events."""

    def __init__(self, should_fail: bool = False) -> None:
        self.dispatched: list[VultronEvent] = []
        self._should_fail = should_fail

    def dispatch(self, event: VultronEvent) -> None:
        if self._should_fail:
            raise RuntimeError("Dispatch error (stub)")
        self.dispatched.append(event)


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
        o = InboxOutcome(status="processed")
        assert o.status == "processed"
        assert o.context_id is None
        assert o.failure_reason is None

    def test_deferred_status_with_fields(self):
        o = InboxOutcome(
            status="deferred",
            context_id=CASE_ID,
            failure_reason="case not yet known",
        )
        assert o.status == "deferred"
        assert o.context_id == CASE_ID
        assert o.failure_reason == "case not yet known"

    def test_rejected_status_with_reason(self):
        o = InboxOutcome(status="rejected", failure_reason="parse failed")
        assert o.status == "rejected"
        assert o.failure_reason == "parse failed"


# ---------------------------------------------------------------------------
# AC-6: rejected InboxOutcome for invalid payloads — no exception raised
# ---------------------------------------------------------------------------


class TestProcessPayloadRejectsInvalidInput:
    def test_none_parse_result_returns_rejected(self, report_activity):
        """When IngressAdapter.parse returns None, outcome is rejected."""
        ingress = _StubIngressAdapter(activity=None, fail_parse=True)
        dispatch = _StubDispatchAdapter()

        outcome = process_payload({}, ingress, dispatch)

        assert isinstance(outcome, InboxOutcome)
        assert outcome.status == "rejected"
        assert outcome.failure_reason is not None

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
