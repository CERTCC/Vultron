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

"""``run_trigger`` orders the outbox flush after the dispatch (TRIG-07-001).

The flush is queued on ``BackgroundTasks`` only once ``trigger()`` has
returned, so the 202 never waits on delivery (TRIG-01-004) and a trigger that
raised flushes nothing; a domain error becomes the structured HTTP error the
trigger API promises (TRIG-01-003); and the helper's return type is the
request's bound result, resolved statically with no cast (UCORG-05-006).

The dispatchers here are hand-written classes conforming to the
``TriggerDispatcher`` Protocol that record *when* they were called relative to
the task queue — not ``Mock(spec=...)`` (``vultron/core/ports/AGENTS.md``); the
real registry-backed dispatcher is exercised end to end by the route tests.
"""

from typing import Any, assert_type, cast

import pytest
from fastapi import BackgroundTasks, HTTPException

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driving.fastapi.outbox_handler import outbox_handler
from vultron.adapters.driving.fastapi.trigger_runner import (
    emitting_outbox,
    run_trigger,
)
from vultron.core.models.use_case_result import (
    ActivityResult,
    StatusResult,
    TriggerResult,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.trigger_dispatcher import TriggerDispatcher
from vultron.core.states.cs import CS_vf
from vultron.core.use_cases.triggers.requests import (
    AddOnBehalfStatusTriggerRequest,
    ResultT_co,
    TriggerRequest,
)
from vultron.errors import VultronCanonicalEntryError, VultronNotFoundError

_ACTOR = "https://example.org/actors/cm"
_CASE = "https://example.org/cases/c1"
_VENDOR = "https://example.org/actors/vendor"


def _request() -> AddOnBehalfStatusTriggerRequest:
    return AddOnBehalfStatusTriggerRequest(
        actor_id=_ACTOR,
        case_id=_CASE,
        target_actor_id=_VENDOR,
        vf_state=CS_vf.Vf,
    )


class _RecordingDispatcher:
    """Returns a canned result and records the queue depth when called."""

    def __init__(
        self, tasks: BackgroundTasks, result: TriggerResult | None = None
    ) -> None:
        self._tasks = tasks
        self._result = result or StatusResult(
            activity_id="urn:uuid:a", status_id="urn:uuid:s"
        )
        self.queued_when_called: int | None = None
        self.seen_dl: object = None

    def trigger(
        self,
        request: TriggerRequest[ResultT_co],
        dl: CaseOutboxPersistence,
    ) -> ResultT_co:
        self.queued_when_called = len(self._tasks.tasks)
        self.seen_dl = dl
        # The stub returns whatever it was handed; the static binding under
        # test lives on the request, not on this stub, so the erasure is
        # closed here the way ``RegistryTriggerDispatcher`` closes it.
        return self._result  # type: ignore[return-value]


class _RaisingDispatcher:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def trigger(
        self,
        request: TriggerRequest[ResultT_co],
        dl: CaseOutboxPersistence,
    ) -> ResultT_co:
        raise self._exc


@pytest.fixture
def dl() -> SqliteDataLayer:
    return SqliteDataLayer("sqlite:///:memory:", actor_id=_ACTOR)


@pytest.mark.spec("TRIG-07-001")
@pytest.mark.spec("TRIG-01-004")
def test_flush_is_queued_only_after_trigger_returns(
    dl: SqliteDataLayer,
) -> None:
    tasks = BackgroundTasks()
    dispatcher = _RecordingDispatcher(tasks)

    result = run_trigger(
        _request(), dispatcher=dispatcher, dl=dl, background_tasks=tasks
    )

    assert dispatcher.queued_when_called == 0, "flush queued before dispatch"
    assert dispatcher.seen_dl is dl
    assert len(tasks.tasks) == 1
    (task,) = tasks.tasks
    assert task.func is outbox_handler
    assert task.args == (_ACTOR, dl)
    assert result.status_id == "urn:uuid:s"


@pytest.mark.spec("UCORG-05-006")
def test_return_type_is_the_requests_bound_result_without_a_cast(
    dl: SqliteDataLayer,
) -> None:
    """mypy and pyright resolve ``StatusResult`` from the request alone."""
    tasks = BackgroundTasks()
    dispatcher: TriggerDispatcher = _RecordingDispatcher(tasks)
    result = run_trigger(
        _request(), dispatcher=dispatcher, dl=dl, background_tasks=tasks
    )
    assert_type(result, StatusResult)
    assert isinstance(result, StatusResult)


@pytest.mark.spec("TRIG-07-001")
@pytest.mark.spec("TRIG-01-003")
def test_domain_error_is_translated_and_nothing_is_flushed(
    dl: SqliteDataLayer,
) -> None:
    tasks = BackgroundTasks()
    dispatcher = _RaisingDispatcher(VultronNotFoundError("Actor", _ACTOR))

    with pytest.raises(HTTPException) as info:
        run_trigger(
            _request(), dispatcher=dispatcher, dl=dl, background_tasks=tasks
        )

    assert info.value.status_code == 404
    # ``translate_domain_errors`` builds a structured ``dict`` detail; the
    # exception type annotates it as ``str``.
    detail = cast(dict[str, Any], info.value.detail)
    assert detail["error"] == "NotFound"
    assert tasks.tasks == [], "a trigger that raised must not flush the outbox"


@pytest.mark.spec("TRIG-07-001")
def test_unmapped_domain_error_propagates_and_nothing_is_flushed(
    dl: SqliteDataLayer,
) -> None:
    """An error ``domain_error_translation()`` has no HTTP mapping for reaches
    the route unchanged, still with no flush queued."""
    tasks = BackgroundTasks()
    dispatcher = _RaisingDispatcher(VultronCanonicalEntryError("declined"))

    with pytest.raises(VultronCanonicalEntryError):
        run_trigger(
            _request(), dispatcher=dispatcher, dl=dl, background_tasks=tasks
        )

    assert tasks.tasks == []


# ---------------------------------------------------------------------------
# Which outbox is drained (CM-24-001)
# ---------------------------------------------------------------------------

_CASE_ACTOR = "https://example.org/actors/case-actor"
_FOREIGN_ACTOR = "https://elsewhere.example/actors/case-actor"


@pytest.mark.spec("TRIG-07-001")
@pytest.mark.spec("CM-24-001")
def test_flush_targets_the_emitting_actor_when_the_result_names_one(
    dl: SqliteDataLayer,
) -> None:
    """A delegated emit queued in the CASE_MANAGER's outbox is drained there."""
    tasks = BackgroundTasks()
    dispatcher = _RecordingDispatcher(
        tasks, ActivityResult(activity=None, emitting_actor_id=_CASE_ACTOR)
    )

    run_trigger(
        _request(), dispatcher=dispatcher, dl=dl, background_tasks=tasks
    )

    (task,) = tasks.tasks
    assert task.func is outbox_handler
    flush_id, flush_dl = task.args
    assert flush_id == _CASE_ACTOR
    assert isinstance(flush_dl, SqliteDataLayer) and flush_dl is not dl
    assert flush_dl.actor_id == _CASE_ACTOR


def test_flush_stays_with_the_requester_when_it_is_the_emitter(
    dl: SqliteDataLayer,
) -> None:
    tasks = BackgroundTasks()
    dispatcher = _RecordingDispatcher(
        tasks, ActivityResult(activity=None, emitting_actor_id=_ACTOR)
    )
    run_trigger(
        _request(), dispatcher=dispatcher, dl=dl, background_tasks=tasks
    )
    (task,) = tasks.tasks
    assert task.args == (_ACTOR, dl)


def test_emitting_outbox_falls_back_for_a_foreign_authority(
    dl: SqliteDataLayer,
) -> None:
    """A CaseActor on another container cannot be drained from here; the emit
    was kept in the requester's store, so that is what is drained (#2484)."""
    assert emitting_outbox(_FOREIGN_ACTOR, _ACTOR, dl) == (_ACTOR, dl)
    assert emitting_outbox(_ACTOR, _ACTOR, dl) == (_ACTOR, dl)
    flush_id, flush_dl = emitting_outbox(_CASE_ACTOR, _ACTOR, dl)
    assert isinstance(flush_dl, SqliteDataLayer)
    assert (flush_id, flush_dl.actor_id) == (_CASE_ACTOR, _CASE_ACTOR)
