import asyncio
from types import SimpleNamespace
from unittest.mock import Mock, MagicMock

import pytest

from vultron.api.v2.backend import inbox_handler as ih
from vultron.core.models.events import InboundPayload, MessageSemantics


def test_prepare_for_dispatch_parses_activity_and_constructs_dispatchactivity(
    monkeypatch,
):
    """prepare_for_dispatch should parse the passed activity and let pydantic construct the payload model."""
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Create,
    )

    import vultron.wire.as2.extractor as extractor_mod

    monkeypatch.setattr(
        extractor_mod,
        "find_matching_semantics",
        lambda activity: MessageSemantics.UNKNOWN,
    )

    mapping_activity = as_Create(
        as_id="act-123", actor="actor-1", object="obj-1"
    )
    dispatch_msg = ih.prepare_for_dispatch(mapping_activity)

    assert dispatch_msg.semantic_type == MessageSemantics.UNKNOWN
    assert dispatch_msg.activity_id == "act-123"
    assert isinstance(dispatch_msg.payload, InboundPayload)
    assert dispatch_msg.payload.activity_id == "act-123"


def test_handle_inbox_item_dispatches(monkeypatch):
    class FakeActivity:
        as_type = "TestActivity"
        name = "fake"

        def model_dump_json(self, **kwargs):
            return '{"name":"fake"}'

    fake_activity = FakeActivity()

    # Prepare a fake dispatchable and make prepare_for_dispatch return it
    dispatchable = SimpleNamespace(activity_id="aid", semantic_type="stest")
    monkeypatch.setattr(
        ih, "prepare_for_dispatch", lambda activity: dispatchable
    )

    # Initialise the module-level dispatcher with a mock
    mock_dispatcher = Mock()
    monkeypatch.setattr(ih, "_DISPATCHER", mock_dispatcher)

    # Act
    ih.handle_inbox_item(actor_id="actor1", obj=fake_activity)

    # Assert: dispatch was called with the dispatchable
    mock_dispatcher.dispatch.assert_called_once_with(dispatchable)


def test_inbox_handler_retries_and_aborts_after_too_many_errors(monkeypatch):
    # Arrange: create an inbox with one item
    item = SimpleNamespace(
        as_type="irrelevant", name="itm", model_dump_json=lambda **kw: "{}"
    )
    inbox = SimpleNamespace(items=[item])
    actor_io = SimpleNamespace(inbox=inbox)

    mock_dl = MagicMock()
    mock_dl.read.return_value = None

    # get_actor_io should return our actor_io
    monkeypatch.setattr(
        ih, "get_actor_io", lambda actor_id, raise_on_missing=True: actor_io
    )

    # rehydrate returns the same item
    monkeypatch.setattr(ih, "rehydrate", lambda x: x)

    # Make handle_inbox_item always raise to trigger retry logic and ultimately abort after >3 errors
    def always_raise(actor_id, obj):
        raise RuntimeError("boom")

    monkeypatch.setattr(ih, "handle_inbox_item", always_raise)

    # Act: run the async inbox_handler with the injected dl
    asyncio.run(ih.inbox_handler("actor-xyz", mock_dl))

    # Assert: after aborting, the item should have been reinserted into the inbox
    assert len(actor_io.inbox.items) == 1
    assert actor_io.inbox.items[0] is item


def test_dispatch_raises_if_not_initialised(monkeypatch):
    monkeypatch.setattr(ih, "_DISPATCHER", None)
    dispatchable = SimpleNamespace(activity_id="x", semantic_type="y")
    with pytest.raises(RuntimeError, match="not initialised"):
        ih.dispatch(dispatchable)


def test_init_dispatcher_sets_dispatcher(monkeypatch):
    mock_dl = MagicMock()
    mock_dispatcher = Mock()

    monkeypatch.setattr(ih, "_DISPATCHER", None)
    monkeypatch.setattr(
        ih, "get_dispatcher", lambda handler_map, dl: mock_dispatcher
    )

    ih.init_dispatcher(dl=mock_dl)
    assert ih._DISPATCHER is mock_dispatcher
