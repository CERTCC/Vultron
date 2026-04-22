import asyncio
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import Mock, MagicMock

import pytest

from vultron.adapters.driving.fastapi import inbox_handler as ih
from vultron.core.models.events import MessageSemantics, VultronEvent
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity


def test_prepare_for_dispatch_returns_vultron_event(monkeypatch):
    """prepare_for_dispatch should return a VultronEvent from extract_event."""
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Create,
    )
    import vultron.semantic_registry as registry_mod

    monkeypatch.setattr(
        registry_mod,
        "find_matching_semantics",
        lambda activity: MessageSemantics.UNKNOWN,
    )

    mapping_activity = as_Create(
        id_="act-123", actor="actor-1", object_="obj-1"
    )
    event = ih.prepare_for_dispatch(mapping_activity)

    assert isinstance(event, VultronEvent)
    assert event.semantic_type == MessageSemantics.UNKNOWN
    assert event.activity_id == "act-123"


def test_handle_inbox_item_dispatches(monkeypatch):
    class FakeActivity:
        type_ = "TestActivity"
        name = "fake"

        def model_dump_json(self, **kwargs):
            return '{"name":"fake"}'

    fake_activity = FakeActivity()
    mock_dl = MagicMock()

    # Use a real VultronEvent so that model_copy() works correctly when
    # handle_inbox_item injects receiving_actor_id (HP-09-001).
    fake_event = VultronEvent(
        semantic_type=MessageSemantics.UNKNOWN,
        activity_id="https://example.org/activities/aid",
        actor_id="https://example.org/actors/actor1",
    )
    monkeypatch.setattr(
        ih, "prepare_for_dispatch", lambda activity: fake_event
    )

    mock_dispatcher = Mock()
    monkeypatch.setattr(ih, "_DISPATCHER", mock_dispatcher)

    ih.handle_inbox_item(
        actor_id="https://example.org/actors/actor1",
        obj=cast(Any, fake_activity),
        dl=mock_dl,
    )

    mock_dispatcher.dispatch.assert_called_once()
    dispatched_event, dispatched_dl = mock_dispatcher.dispatch.call_args[0]
    assert dispatched_dl is mock_dl
    assert (
        dispatched_event.receiving_actor_id
        == "https://example.org/actors/actor1"
    )


def test_inbox_handler_retries_and_aborts_after_too_many_errors(monkeypatch):
    """inbox_handler retries up to 3 errors then aborts, re-appending the item."""
    item_id = "https://example.org/activities/itm-001"
    item = as_Activity(
        id_=item_id,
        type_="irrelevant",
        actor="https://example.org/actors/test",
        name="itm",
    )

    mock_dl = MagicMock()
    mock_dl.read.return_value = None
    # Inbox contains one item; after abort it should still be there
    _queue = [item_id]
    mock_dl.inbox_list.side_effect = lambda: list(_queue)
    mock_dl.inbox_pop.side_effect = lambda: _queue.pop(0) if _queue else None
    mock_dl.inbox_append.side_effect = lambda x: _queue.append(x)
    # Prevent outbox_handler (called at end of inbox_handler) from looping
    mock_dl.outbox_list.return_value = []

    monkeypatch.setattr(ih, "rehydrate", lambda x, dl=None: item)

    def always_raise(actor_id, obj, dl):
        raise RuntimeError("boom")

    monkeypatch.setattr(ih, "handle_inbox_item", always_raise)

    asyncio.run(ih.inbox_handler("actor-xyz", mock_dl))

    # Item should have been re-appended after each error
    assert item_id in _queue


def test_dispatch_raises_if_not_initialised(monkeypatch):
    monkeypatch.setattr(ih, "_DISPATCHER", None)
    fake_event = cast(
        VultronEvent, SimpleNamespace(activity_id="x", semantic_type="y")
    )
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
