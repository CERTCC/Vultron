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

"""The outcome stage records an outcome; it never decides one (CLP-10-079).

``SettleReceivedOutcome`` decorates ``DispatchNode``, so it runs on every path
the dispatch can take.  These tests drive the pipeline with a stub dispatch
adapter and a stub outcome port, so what reaches the port, and what the
delivery is answered with, are both visible.  What each outcome leaves in the
store is driven in
``test/adapters/driving/fastapi/test_received_outcome_stage.py``.
"""

from datetime import datetime
from typing import Any

import py_trees
import pytest

from test.support.objects import make
from test.support.received import stamped
from vultron.adapters.driven.clock import SystemClock
from vultron.core.behaviors.blackboard_scope import key_aliases
from vultron.core.behaviors.inbox import (
    InboxOutcomeStatus,
    process_payload,
)
from vultron.core.behaviors.inbox.nodes.pipeline import KEY_DISPOSITION
from vultron.core.models.events import VultronEvent
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.wire.as2.factories import rm_create_report_activity
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

_SENDER_ID = "https://example.org/actors/stage-sender"
_RECEIVER_ID = "https://example.org/actors/stage-receiver"
_REASON = "sender is not a participant of the case"


class _StubIngress:
    """Returns one already-stamped activity, parsing nothing."""

    def __init__(self, activity: Any) -> None:
        self._activity = stamped(activity)

    def parse(self, payload: Any) -> Any:
        return self._activity

    def rehydrate(self, activity: Any) -> Any:
        return activity


class _StubDispatch:
    """Returns *result*, or raises when *raises* is set."""

    def __init__(
        self, result: HandlerResult | None = None, raises: bool = False
    ) -> None:
        self._result = result or HandlerResult.applied()
        self._raises = raises
        self.faults: list[str] = []

    def dispatch(self, event: VultronEvent) -> HandlerResult:
        if self._raises:
            raise RuntimeError("dispatch error (stub)")
        return self._result

    def emit_processing_fault(
        self, event: VultronEvent, failure_class: str
    ) -> None:
        self.faults.append(failure_class)


class _RecordingOutcomePort:
    """Records each outcome; raises instead when *raises* is set."""

    def __init__(self, raises: bool = False) -> None:
        self.refused: list[tuple[str, str, str]] = []
        self.applied: list[str] = []
        self._raises = raises

    def apply(self, activity_id: str) -> None:
        if self._raises:
            raise RuntimeError("store write failed (stub)")
        self.applied.append(activity_id)

    def refuse(
        self,
        activity_id: str,
        *,
        sender_id: str,
        reason: str,
        received_body: str | None,
        received_at: datetime,
    ) -> None:
        if self._raises:
            raise RuntimeError("store write failed (stub)")
        self.refused.append((activity_id, sender_id, reason))


@pytest.fixture
def activity():
    return rm_create_report_activity(
        report=make(
            as_VulnerabilityReport,
            id_="https://example.org/reports/r-stage-1",
            content="stage report",
        ),
        actor=_SENDER_ID,
        to=[_RECEIVER_ID],
    )


def _run(activity, dispatch, port):
    return process_payload(
        {},
        _StubIngress(activity),
        dispatch,
        received_outcome_port=port,
        arrived_at=SystemClock().now(),
    )


@pytest.mark.spec("CLP-10-073")
def test_a_refusal_reaches_the_port_with_the_sender_and_the_reason(activity):
    port = _RecordingOutcomePort()

    outcome = _run(
        activity, _StubDispatch(HandlerResult.refused(_REASON)), port
    )

    assert outcome.status is InboxOutcomeStatus.REJECTED
    assert port.refused == [(activity.id_, _SENDER_ID, _REASON)]


@pytest.mark.spec("CLP-10-073")
@pytest.mark.parametrize(
    "result",
    [HandlerResult.applied(), HandlerResult.skipped("already applied")],
    ids=["applied", "skipped"],
)
def test_an_applied_or_skipped_message_is_archived(activity, result):
    port = _RecordingOutcomePort()

    _run(activity, _StubDispatch(result), port)

    assert port.applied == [activity.id_]
    assert port.refused == []


@pytest.mark.spec("CLP-10-073")
def test_a_deferred_message_reaches_the_port_with_nothing(activity):
    """Still waiting: it has no outcome yet (IO-03-009)."""
    port = _RecordingOutcomePort()

    _run(activity, _StubDispatch(HandlerResult.deferred("entry 3")), port)

    assert port.applied == []
    assert port.refused == []


@pytest.mark.spec("CLP-10-074")
def test_a_dispatch_that_raised_reaches_the_port_with_nothing(activity):
    """No verdict came back, so there is no outcome to record."""
    port = _RecordingOutcomePort()

    outcome = _run(activity, _StubDispatch(raises=True), port)

    assert outcome.status is InboxOutcomeStatus.REJECTED
    assert port.refused == []
    assert port.applied == []


@pytest.mark.spec("CLP-10-074")
def test_a_nested_run_does_not_inherit_the_enclosing_runs_verdict(activity):
    """A run inside another starts with no verdict of its own.

    The replay a case bootstrap triggers runs inside the outer dispatch,
    after that dispatch published its verdict.  Were that verdict still on
    the blackboard, an inner dispatch that raised would be settled by it.
    """
    storage = py_trees.blackboard.Blackboard.storage
    aliases = key_aliases(KEY_DISPOSITION)
    saved = {
        alias: storage.get(alias) for alias in aliases if alias in storage
    }
    for alias in aliases:
        storage[alias] = HandlerDisposition.REFUSED
    port = _RecordingOutcomePort()
    try:
        outcome = _run(activity, _StubDispatch(raises=True), port)
        restored = {alias: storage.get(alias) for alias in aliases}
    finally:
        for alias in aliases:
            storage.pop(alias, None)
        storage.update(saved)

    assert outcome.status is InboxOutcomeStatus.REJECTED
    assert port.refused == []
    # The enclosing run's verdict is back once the inner run returns.
    assert restored == dict.fromkeys(aliases, HandlerDisposition.REFUSED)


@pytest.mark.spec("CLP-10-079")
def test_a_port_that_raises_leaves_the_verdict_as_the_handler_gave_it(
    activity, caplog
):
    """A bookkeeping failure is logged; the sender's answer does not change."""
    port = _RecordingOutcomePort(raises=True)

    with caplog.at_level("ERROR"):
        outcome = _run(
            activity, _StubDispatch(HandlerResult.refused(_REASON)), port
        )

    assert outcome.status is InboxOutcomeStatus.REJECTED
    assert outcome.failure_reason == _REASON
    assert any(
        record.levelname == "ERROR"
        and "final stage was not recorded" in record.message
        for record in caplog.records
    ), [record.message for record in caplog.records]


@pytest.mark.spec("CLP-10-079")
@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (HandlerResult.applied(), InboxOutcomeStatus.PROCESSED),
        (HandlerResult.skipped("dup"), InboxOutcomeStatus.PROCESSED),
        (HandlerResult.deferred("wait"), InboxOutcomeStatus.DEFERRED),
        (HandlerResult.refused(_REASON), InboxOutcomeStatus.REJECTED),
    ],
    ids=["applied", "skipped", "deferred", "refused"],
)
def test_the_stage_passes_the_dispatchs_status_through(
    activity, result, expected
):
    """The decorator returns the decorated node's status, every verdict."""
    outcome = _run(activity, _StubDispatch(result), _RecordingOutcomePort())

    assert outcome.status is expected


@pytest.mark.spec("CLP-10-073")
def test_a_run_with_no_outcome_port_still_answers_the_sender(activity):
    """The port is the adapter's to supply; its absence changes no verdict."""
    outcome = process_payload(
        {},
        _StubIngress(activity),
        _StubDispatch(HandlerResult.refused(_REASON)),
        arrived_at=SystemClock().now(),
    )

    assert outcome.status is InboxOutcomeStatus.REJECTED
    assert outcome.failure_reason == _REASON
