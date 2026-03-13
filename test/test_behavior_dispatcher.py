import logging
from unittest.mock import MagicMock

from vultron import behavior_dispatcher as bd
from vultron.core.models.events import (
    CreateReportReceivedEvent,
    MessageSemantics,
    VultronEvent,
)


def test_get_dispatcher_returns_local_dispatcher():
    """get_dispatcher should return an object implementing dispatch()."""
    dispatcher = bd.get_dispatcher(use_case_map={})
    assert hasattr(dispatcher, "dispatch") and callable(dispatcher.dispatch)


def test_local_dispatcher_dispatch_logs_payload(caplog):
    """DirectActivityDispatcher.dispatch should log info + debug messages."""
    caplog.set_level(logging.DEBUG)
    mock_dl = MagicMock()
    dispatcher = bd.DirectActivityDispatcher(
        use_case_map={MessageSemantics.CREATE_REPORT: MagicMock()}
    )

    event = CreateReportReceivedEvent(
        activity_id="act-xyz",
        actor_id="https://example.org/users/tester",
        object_type="VulnerabilityReport",
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
