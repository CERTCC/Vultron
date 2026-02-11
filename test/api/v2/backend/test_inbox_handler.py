import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from vultron.api.v2.backend import inbox_handler as ih
from vultron.api.v2.errors import VultronApiValidationError


def test_raise_if_not_valid_activity_raises(monkeypatch):
    # Arrange: ensure VOCABULARY.activities does not contain the test type
    monkeypatch.setattr(
        ih,
        "VOCABULARY",
        SimpleNamespace(activities={"SomeOtherActivity"}),
        raising=False,
    )

    class FakeObj:
        as_type = "NotAnActivity"

    obj = FakeObj()

    # Act / Assert
    with pytest.raises(VultronApiValidationError):
        ih.raise_if_not_valid_activity(obj)


def test_handle_inbox_item_dispatches(monkeypatch):
    # Arrange: make the object look like a valid Activity type
    monkeypatch.setattr(
        ih,
        "VOCABULARY",
        SimpleNamespace(activities={"TestActivity"}),
        raising=False,
    )

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

    # Replace the module DISPATCHER with a Mock dispatcher
    mock_dispatcher = Mock()
    monkeypatch.setattr(ih, "DISPATCHER", mock_dispatcher, raising=False)

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

    # get_datalayer.read can be a noop (actor not required for this test)
    monkeypatch.setattr(
        ih, "get_datalayer", lambda: SimpleNamespace(read=lambda aid: None)
    )

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

    # Act: run the async inbox_handler
    asyncio.run(ih.inbox_handler("actor-xyz"))

    # Assert: after aborting, the item should have been reinserted into the inbox
    assert len(actor_io.inbox.items) == 1
    assert actor_io.inbox.items[0] is item
