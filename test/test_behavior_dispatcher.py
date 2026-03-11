import logging
from unittest.mock import MagicMock

from vultron import behavior_dispatcher as bd
from vultron.core.models.events import InboundPayload, MessageSemantics


def test_get_dispatcher_returns_local_dispatcher():
    """get_dispatcher should return an object implementing dispatch()."""
    from unittest.mock import MagicMock

    dispatcher = bd.get_dispatcher(handler_map={}, dl=MagicMock())
    assert hasattr(dispatcher, "dispatch") and callable(dispatcher.dispatch)


def test_local_dispatcher_dispatch_logs_payload(caplog):
    """
    DirectActivityDispatcher.dispatch should log an info message about dispatching and a debug
    message containing the activity id.
    """
    caplog.set_level(logging.DEBUG)
    mock_dl = MagicMock()
    dispatcher = bd.DirectActivityDispatcher(
        handler_map={MessageSemantics.CREATE_REPORT: MagicMock()}, dl=mock_dl
    )

    # Construct a DispatchActivity directly with InboundPayload (no AS2 construction needed)
    dispatchable = bd.DispatchActivity(
        semantic_type=MessageSemantics.CREATE_REPORT,
        activity_id="act-xyz",
        payload=InboundPayload(
            activity_id="act-xyz",
            actor_id="https://example.org/users/tester",
            object_type="VulnerabilityReport",
        ),
    )

    dispatcher.dispatch(dispatchable)

    info_msgs = [
        r.getMessage() for r in caplog.records if r.levelno == logging.INFO
    ]
    debug_msgs = [
        r.getMessage() for r in caplog.records if r.levelno == logging.DEBUG
    ]

    assert any("Dispatching activity" in m for m in info_msgs)
    # debug should include the activity id
    assert any("act-xyz" in m for m in debug_msgs)
