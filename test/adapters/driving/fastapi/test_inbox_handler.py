import asyncio
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import Mock, MagicMock

import pytest

from vultron.adapters.driving.fastapi import inbox_handler as ih
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.pending_case_inbox import VultronPendingCaseInbox
from vultron.core.models.events import MessageSemantics, VultronEvent
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase


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

    def fail_and_requeue(
        actor_id, canonical_actor_id, item_id, item, dl, queue_dl
    ):
        queue_dl.inbox_append(item_id)
        return False

    monkeypatch.setattr(ih, "_process_inbox_item", fail_and_requeue)

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
        ih,
        "get_dispatcher",
        lambda use_case_map, port_factories=None: mock_dispatcher,
    )

    ih.init_dispatcher()
    assert ih._DISPATCHER is mock_dispatcher


def test_dispatch_or_defer_inbox_item_queues_unknown_case_context(monkeypatch):
    actor_id = "https://example.org/actors/participant"
    case_id = "https://example.org/cases/case-unknown"
    item_id = "https://example.org/activities/add-note-1"
    shared_dl = SqliteDataLayer("sqlite:///:memory:")
    queue_dl = shared_dl.clone_for_actor(actor_id)
    item = as_Activity(
        id_=item_id,
        type_="Add",
        actor="https://example.org/actors/case-actor",
        context=case_id,
        name="queued-note",
    )
    fake_event = VultronEvent(
        semantic_type=MessageSemantics.ADD_NOTE_TO_CASE,
        activity_id=item_id,
        actor_id="https://example.org/actors/case-actor",
    )

    monkeypatch.setattr(
        ih, "prepare_for_dispatch", lambda activity: fake_event
    )
    mock_dispatcher = Mock()
    monkeypatch.setattr(ih, "_DISPATCHER", mock_dispatcher)

    result = ih._dispatch_or_defer_inbox_item(
        actor_id=actor_id,
        obj=item,
        dl=shared_dl,
        queue_dl=queue_dl,
    )

    assert result is None
    pending = queue_dl.read(VultronPendingCaseInbox.build_id(case_id))
    assert isinstance(pending, VultronPendingCaseInbox)
    assert pending.activity_ids == [item_id]
    mock_dispatcher.dispatch.assert_not_called()


def test_inbox_handler_replays_deferred_items_after_case_announce(monkeypatch):
    actor_id = "https://example.org/actors/participant"
    case_id = "https://example.org/cases/case-replay"
    note_id = "https://example.org/activities/add-note-2"
    announce_id = "https://example.org/activities/announce-case-1"
    shared_dl = SqliteDataLayer("sqlite:///:memory:")
    shared_dl.save(as_Service(id_=actor_id, name="Participant"))
    queue_dl = shared_dl.clone_for_actor(actor_id)
    queue_dl.inbox_append(note_id)
    queue_dl.inbox_append(announce_id)

    note_item = as_Activity(
        id_=note_id,
        type_="Add",
        actor="https://example.org/actors/case-actor",
        context=case_id,
        name="deferred-note",
    )
    announce_item = as_Activity(
        id_=announce_id,
        type_="Announce",
        actor="https://example.org/actors/case-actor",
        context=case_id,
        name="announce-case",
    )
    items = {note_id: note_item, announce_id: announce_item}

    def fake_prepare(activity: as_Activity) -> VultronEvent:
        if activity.id_ == note_id:
            return VultronEvent(
                semantic_type=MessageSemantics.ADD_NOTE_TO_CASE,
                activity_id=note_id,
                actor_id="https://example.org/actors/case-actor",
            )
        return VultronEvent(
            semantic_type=MessageSemantics.ANNOUNCE_VULNERABILITY_CASE,
            activity_id=announce_id,
            actor_id="https://example.org/actors/case-actor",
        )

    dispatched: list[str] = []

    def fake_dispatch(event: VultronEvent, dl: SqliteDataLayer) -> None:
        dispatched.append(event.activity_id)
        if event.semantic_type == MessageSemantics.ANNOUNCE_VULNERABILITY_CASE:
            dl.save(VulnerabilityCase(id_=case_id, name="Replica"))

    async def fake_outbox_handler(*_args: object, **_kwargs: object) -> None:
        return None

    mock_dispatcher = Mock()
    mock_dispatcher.dispatch.side_effect = fake_dispatch
    monkeypatch.setattr(ih, "_DISPATCHER", mock_dispatcher)
    monkeypatch.setattr(ih, "prepare_for_dispatch", fake_prepare)
    monkeypatch.setattr(
        ih, "rehydrate", lambda item_id, dl=None: items[item_id]
    )
    monkeypatch.setattr(ih, "outbox_handler", fake_outbox_handler)

    asyncio.run(ih.inbox_handler(actor_id, shared_dl, queue_dl))

    assert dispatched == [announce_id, note_id]
    assert queue_dl.read(VultronPendingCaseInbox.build_id(case_id)) is None
