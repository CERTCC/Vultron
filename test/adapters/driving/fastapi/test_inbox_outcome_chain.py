#!/usr/bin/env python
"""End-to-end: a handler's verdict reaches ``InboxOutcome`` (UCORG-05-010/011).

The defect #3373 fixes is that the *chain* dropped the verdict — every link
between ``execute()`` and ``DispatchNode`` returned ``None``, so a unit test of
the disposition mapping alone could pass while the pipeline still reported
``processed``. These tests therefore drive the real links: the FastAPI ingress
and dispatch adapters, ``inbox_handler.dispatch``, ``DirectActivityDispatcher``
and the inbox BT, with only the use case itself stubbed.
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

from __future__ import annotations

import asyncio
import logging
from typing import Any
from unittest.mock import AsyncMock

import py_trees
import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driving.fastapi.inbox_orchestration import (
    FastAPIDispatchAdapter,
    FastAPIIngressAdapter,
    run_inbox_pipeline,
)
from vultron.core.behaviors.inbox import (
    InboxOutcome,
    InboxOutcomeStatus,
    process_payload,
)
from vultron.core.dispatcher import DirectActivityDispatcher
from vultron.core.models.events import MessageSemantics
from vultron.core.models.use_case_result import HandlerResult
from vultron.errors import UnroutableActivityError
from vultron.wire.as2.factories import rm_create_report_activity
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

_SENDER_ID = "https://example.org/actors/sender-chain"
_RECEIVER_ID = "https://example.org/actors/receiver-chain"
_ORCHESTRATION_LOGGER = "vultron.adapters.driving.fastapi.inbox_orchestration"


@pytest.fixture(autouse=True)
def clear_blackboard():
    py_trees.blackboard.Blackboard.storage.clear()
    yield
    py_trees.blackboard.Blackboard.storage.clear()


@pytest.fixture(autouse=True)
def clear_actor_locks():
    from vultron.adapters.driving.fastapi import inbox_orchestration

    inbox_orchestration._actor_inbox_locks.clear()
    yield
    inbox_orchestration._actor_inbox_locks.clear()


@pytest.fixture
def dl():
    """The receiving actor's own store (ADR-0073)."""
    db = SqliteDataLayer("sqlite:///:memory:", actor_id=_RECEIVER_ID)
    yield db
    db.close()


@pytest.fixture
def body() -> dict[str, Any]:
    report = as_VulnerabilityReport(
        id_="https://example.org/reports/r-chain-1", content="chain report"
    )
    activity = rm_create_report_activity(
        report, actor=_SENDER_ID, to=[_RECEIVER_ID]
    )
    return activity.model_dump(mode="json", by_alias=True, exclude_none=True)


def _use_case_returning(verdict: HandlerResult) -> type:
    """A received use case that does nothing but return *verdict*."""

    class _StubUseCase:
        def __init__(self, dl: Any, request: Any) -> None:
            pass

        def execute(self) -> HandlerResult:
            return verdict

    return _StubUseCase


def _dispatcher_for(verdict: HandlerResult) -> DirectActivityDispatcher:
    return DirectActivityDispatcher(
        use_case_map={
            MessageSemantics.CREATE_REPORT: _use_case_returning(verdict)
        }
    )


def _process(
    dl: SqliteDataLayer,
    body: dict[str, Any],
    dispatcher: DirectActivityDispatcher,
) -> InboxOutcome:
    """Run one payload through the real FastAPI adapters and the inbox BT."""
    return process_payload(
        body,
        FastAPIIngressAdapter(dl=dl, body=body),
        FastAPIDispatchAdapter(
            dl=dl, actor_id=_RECEIVER_ID, dispatcher=dispatcher
        ),
    )


@pytest.mark.spec("UCORG-05-011")
def test_refused_handler_yields_rejected_with_its_reason(dl, body):
    outcome = _process(
        dl, body, _dispatcher_for(HandlerResult.refused("not a participant"))
    )

    assert outcome.status is InboxOutcomeStatus.REJECTED
    assert outcome.failure_reason == "not a participant"


@pytest.mark.spec("UCORG-05-011")
@pytest.mark.parametrize(
    "verdict", [HandlerResult.applied(), HandlerResult.skipped("duplicate")]
)
def test_applied_or_skipped_handler_yields_processed(dl, body, verdict):
    outcome = _process(dl, body, _dispatcher_for(verdict))

    assert outcome.status is InboxOutcomeStatus.PROCESSED
    assert outcome.failure_reason is None


@pytest.mark.spec("UCORG-05-011")
def test_deferred_handler_yields_deferred(dl, body):
    outcome = _process(
        dl, body, _dispatcher_for(HandlerResult.deferred("awaiting entry 3"))
    )

    assert outcome.status is InboxOutcomeStatus.DEFERRED
    assert outcome.failure_reason == "awaiting entry 3"


@pytest.mark.spec("UCORG-05-012")
def test_unroutable_activity_is_not_processed(dl, body, monkeypatch):
    """No handler ran, so the dispatcher's synthesized verdict is a refusal."""

    def _unroutable(self: Any, event: Any, dl: Any) -> None:
        raise UnroutableActivityError(event.activity_id, "no case_id")

    monkeypatch.setattr(
        DirectActivityDispatcher, "_enforce_join_backfill_gate", _unroutable
    )

    outcome = _process(dl, body, _dispatcher_for(HandlerResult.applied()))

    assert outcome.status is InboxOutcomeStatus.REJECTED
    assert "unroutable" in (outcome.failure_reason or "")


@pytest.mark.spec("UCORG-05-012")
def test_unhandled_semantics_is_not_processed(dl, body):
    outcome = _process(dl, body, DirectActivityDispatcher(use_case_map={}))

    assert outcome.status is InboxOutcomeStatus.REJECTED
    assert "No use case found" in (outcome.failure_reason or "")


def _run_pipeline(
    dl: SqliteDataLayer, body: dict[str, Any], verdict: HandlerResult
) -> None:
    emitter = AsyncMock()
    asyncio.run(
        run_inbox_pipeline(
            body, body, dl, _RECEIVER_ID, _dispatcher_for(verdict), emitter
        )
    )


def _orchestration_warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        r.getMessage()
        for r in caplog.records
        if r.name == _ORCHESTRATION_LOGGER and r.levelno >= logging.WARNING
    ]


@pytest.mark.spec("UCORG-05-013")
def test_pipeline_logs_a_rejection_above_debug(dl, body, caplog):
    with caplog.at_level(logging.WARNING, logger=_ORCHESTRATION_LOGGER):
        _run_pipeline(dl, body, HandlerResult.refused("not a participant"))

    [message] = _orchestration_warnings(caplog)
    assert "not a participant" in message
    assert _RECEIVER_ID in message
    assert f"activity_id={body['id']}" in message
    assert "replayed=False" in message


@pytest.mark.spec("UCORG-05-013")
def test_pipeline_logs_a_rejected_replay_above_debug(dl, body, caplog):
    """A replayed item that is rejected is surfaced like a fresh one."""
    dl.inbox_append("https://example.org/activities/never-stored")

    with caplog.at_level(logging.WARNING, logger=_ORCHESTRATION_LOGGER):
        _run_pipeline(dl, body, HandlerResult.applied())

    [message] = _orchestration_warnings(caplog)
    assert "replayed=True" in message
    assert _RECEIVER_ID in message


@pytest.mark.spec("UCORG-05-013")
@pytest.mark.parametrize(
    "verdict",
    [HandlerResult.applied(), HandlerResult.deferred("awaiting entry 3")],
)
def test_pipeline_does_not_warn_for_routine_outcomes(
    dl, body, caplog, verdict
):
    with caplog.at_level(logging.WARNING, logger=_ORCHESTRATION_LOGGER):
        _run_pipeline(dl, body, verdict)

    assert _orchestration_warnings(caplog) == []
