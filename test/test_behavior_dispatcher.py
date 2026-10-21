import logging
from unittest.mock import MagicMock

import pytest

from vultron.core.dispatcher import DirectActivityDispatcher, get_dispatcher
from vultron.core.models.activity import VultronActivity
from vultron.core.models.events import (
    CreateReportReceivedEvent,
    MessageSemantics,
)
from vultron.core.models.report import VulnerabilityReport
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)


def _use_case_returning(
    result: object = HandlerResult.applied(),
) -> tuple[MagicMock, MagicMock]:
    """Return ``(instance, class)`` mocks whose ``execute()`` yields *result*.

    *result* defaults to ``HandlerResult.applied()``, the verdict every
    received use case returns today. ``None`` is passed through, so a use
    case that still returns nothing can be tested.
    """
    instance = MagicMock()
    instance.execute.return_value = result
    return instance, MagicMock(return_value=instance)


def test_get_dispatcher_returns_local_dispatcher():
    """get_dispatcher should return an object implementing dispatch()."""
    dispatcher = get_dispatcher(use_case_map={})
    assert hasattr(dispatcher, "dispatch") and callable(dispatcher.dispatch)


def test_local_dispatcher_dispatch_logs_payload(caplog):
    """DirectActivityDispatcher.dispatch should log info + debug messages."""
    caplog.set_level(logging.DEBUG)
    mock_dl = MagicMock()
    dispatcher = DirectActivityDispatcher(
        use_case_map={MessageSemantics.CREATE_REPORT: _use_case_returning()[1]}
    )

    event = CreateReportReceivedEvent(
        activity_id="act-xyz",
        actor_id="https://example.org/users/tester",
        object_=VulnerabilityReport(content="test report"),
        activity=VultronActivity(
            type_="Create", actor="https://example.org/users/tester"
        ),
    )

    dispatcher.dispatch(event, mock_dl)

    info_msgs = [
        r.getMessage() for r in caplog.records if r.levelno == logging.INFO
    ]
    debug_msgs = [
        r.getMessage() for r in caplog.records if r.levelno == logging.DEBUG
    ]

    assert any("Dispatching" in m for m in info_msgs)
    assert any("act-xyz" in m for m in debug_msgs)


def _create_report_event() -> CreateReportReceivedEvent:
    return CreateReportReceivedEvent(
        activity_id="act-verdict",
        actor_id="https://example.org/users/tester",
        object_=VulnerabilityReport(content="test report"),
        activity=VultronActivity(
            type_="Create", actor="https://example.org/users/tester"
        ),
    )


@pytest.mark.spec("UCORG-05-010")
@pytest.mark.parametrize(
    "verdict",
    [
        HandlerResult.applied(),
        HandlerResult.skipped("duplicate"),
        HandlerResult.deferred("awaiting predecessor"),
        HandlerResult.refused("not a participant"),
    ],
)
def test_dispatch_returns_the_use_case_verdict(verdict):
    """The dispatcher carries the handler's result instead of dropping it."""
    _, use_case_class = _use_case_returning(verdict)
    dispatcher = DirectActivityDispatcher(
        use_case_map={MessageSemantics.CREATE_REPORT: use_case_class}
    )

    assert dispatcher.dispatch(_create_report_event(), MagicMock()) == verdict


@pytest.mark.spec("UCORG-05-001")
@pytest.mark.spec("HP-05-001")
@pytest.mark.parametrize("not_a_verdict", [None, {"ok": True}, "applied"])
def test_dispatch_rejects_a_use_case_that_returns_no_handler_result(
    not_a_verdict,
):
    """A non-HandlerResult return is a contract breach and fails fast."""
    _, use_case_class = _use_case_returning(not_a_verdict)
    dispatcher = DirectActivityDispatcher(
        use_case_map={MessageSemantics.CREATE_REPORT: use_case_class}
    )

    with pytest.raises(TypeError, match="not HandlerResult"):
        dispatcher.dispatch(_create_report_event(), MagicMock())


@pytest.mark.spec("DR-03-002")
def test_dispatch_lets_a_handler_exception_propagate():
    """An exception raised inside ``execute()`` escapes ``dispatch()`` unchanged.

    The dispatcher converts no handler failure into a verdict; every one
    belongs to the adapter boundary (IE-06-004).
    """

    class HandlerFailure(RuntimeError):
        pass

    class RaisingUseCase:
        def __init__(self, dl, request) -> None:
            pass

        def execute(self) -> HandlerResult:
            raise HandlerFailure("handler blew up")

    dispatcher = DirectActivityDispatcher(
        use_case_map={MessageSemantics.CREATE_REPORT: RaisingUseCase}
    )

    with pytest.raises(HandlerFailure, match="handler blew up"):
        dispatcher.dispatch(_create_report_event(), MagicMock())


@pytest.mark.spec("HP-02-001")
@pytest.mark.spec("HP-02-002")
@pytest.mark.spec("SE-05-002")
@pytest.mark.spec("UCORG-05-012")
def test_dispatch_refuses_a_semantics_with_no_registered_use_case():
    """The handler is resolved from ``event.semantic_type`` before any runs.

    A semantics with no use case in the routing table is recognized but not
    handled: the dispatcher returns a ``REFUSED`` verdict saying no use case
    was found, rather than raising (SE-05-002), and no handler ran, so the
    verdict is not success (UCORG-05-012).
    """
    dispatcher = DirectActivityDispatcher(use_case_map={})

    result = dispatcher.dispatch(_create_report_event(), MagicMock())

    assert result.disposition is HandlerDisposition.REFUSED
    assert result.reason == "No use case found for semantics 'create_report'"


@pytest.mark.spec("SE-05-002")
@pytest.mark.spec("SL-03-001")
def test_dispatch_logs_no_use_case_found_at_info_with_context(caplog):
    """No use case found is one INFO record with semantic, activity_id, actor_id.

    A recognized semantic type with no handler is a valid message the receiver
    does not handle, not a failure or an anomaly, so it is logged at INFO with
    no traceback, and names the semantic type, activity_id and actor_id so
    the missing handler is attributable.
    """
    caplog.set_level(logging.DEBUG, logger="vultron.core.dispatcher")
    dispatcher = DirectActivityDispatcher(use_case_map={})
    event = _create_report_event()

    dispatcher.dispatch(event, MagicMock())

    records = [
        r for r in caplog.records if "No use case found" in r.getMessage()
    ]
    assert len(records) == 1, "Expected exactly one 'No use case found' log"
    record = records[0]
    assert record.levelno == logging.INFO
    assert record.exc_info is None
    message = record.getMessage()
    assert str(event.semantic_type) in message
    assert event.activity_id in message
    assert event.actor_id in message


@pytest.mark.spec("HP-06-001")
def test_dispatch_logs_handler_entry_at_debug_with_handler_name(caplog):
    """Handler entry is one DEBUG record naming the handler class and activity."""
    caplog.set_level(logging.DEBUG, logger="vultron.core.dispatcher")

    class NamedStubUseCase:
        """A real class, so the asserted name is the handler's, not a mock's."""

        def __init__(self, dl, request) -> None:
            pass

        def execute(self) -> HandlerResult:
            return HandlerResult.applied()

    dispatcher = DirectActivityDispatcher(
        use_case_map={MessageSemantics.CREATE_REPORT: NamedStubUseCase}
    )

    dispatcher.dispatch(_create_report_event(), MagicMock())

    entries = [
        r.getMessage()
        for r in caplog.records
        if r.levelno == logging.DEBUG and "Entering handler" in r.getMessage()
    ]
    assert len(entries) == 1, caplog.text
    assert "NamedStubUseCase" in entries[0]
    assert "act-verdict" in entries[0]
    assert str(MessageSemantics.CREATE_REPORT) in entries[0]
