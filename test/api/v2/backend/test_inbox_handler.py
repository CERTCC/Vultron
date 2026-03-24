import asyncio
from types import SimpleNamespace
from unittest.mock import Mock, MagicMock

import pytest

from vultron.adapters.driving.fastapi import inbox_handler as ih
from vultron.core.models.events import MessageSemantics, VultronEvent


def test_prepare_for_dispatch_returns_vultron_event(monkeypatch):
    """prepare_for_dispatch should return a VultronEvent from extract_intent."""
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
    event = ih.prepare_for_dispatch(mapping_activity)

    assert isinstance(event, VultronEvent)
    assert event.semantic_type == MessageSemantics.UNKNOWN
    assert event.activity_id == "act-123"


def test_handle_inbox_item_dispatches(monkeypatch):
    class FakeActivity:
        as_type = "TestActivity"
        name = "fake"

        def model_dump_json(self, **kwargs):
            return '{"name":"fake"}'

    fake_activity = FakeActivity()
    mock_dl = MagicMock()

    fake_event = SimpleNamespace(activity_id="aid", semantic_type="stest")
    monkeypatch.setattr(
        ih, "prepare_for_dispatch", lambda activity: fake_event
    )

    mock_dispatcher = Mock()
    monkeypatch.setattr(ih, "_DISPATCHER", mock_dispatcher)

    ih.handle_inbox_item(actor_id="actor1", obj=fake_activity, dl=mock_dl)

    mock_dispatcher.dispatch.assert_called_once_with(fake_event, mock_dl)


def test_inbox_handler_retries_and_aborts_after_too_many_errors(monkeypatch):
    item = SimpleNamespace(
        as_type="irrelevant", name="itm", model_dump_json=lambda **kw: "{}"
    )
    inbox = SimpleNamespace(items=[item])
    actor_io = SimpleNamespace(inbox=inbox)

    mock_dl = MagicMock()
    mock_dl.read.return_value = None

    monkeypatch.setattr(
        ih, "get_actor_io", lambda actor_id, raise_on_missing=True: actor_io
    )
    monkeypatch.setattr(ih, "rehydrate", lambda x, dl=None: x)

    def always_raise(actor_id, obj, dl):
        raise RuntimeError("boom")

    monkeypatch.setattr(ih, "handle_inbox_item", always_raise)

    asyncio.run(ih.inbox_handler("actor-xyz", mock_dl))

    assert len(actor_io.inbox.items) == 1
    assert actor_io.inbox.items[0] is item


def test_dispatch_raises_if_not_initialised(monkeypatch):
    monkeypatch.setattr(ih, "_DISPATCHER", None)
    fake_event = SimpleNamespace(activity_id="x", semantic_type="y")
    mock_dl = MagicMock()
    with pytest.raises(RuntimeError, match="not initialised"):
        ih.dispatch(fake_event, mock_dl)


def test_init_dispatcher_sets_dispatcher(monkeypatch):
    mock_dispatcher = Mock()
    monkeypatch.setattr(ih, "_DISPATCHER", None)
    monkeypatch.setattr(
        ih, "get_dispatcher", lambda use_case_map: mock_dispatcher
    )

    ih.init_dispatcher()
    assert ih._DISPATCHER is mock_dispatcher
