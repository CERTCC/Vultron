#!/usr/bin/env python
"""
Test for bug: 'str' object has no attribute 'as_id' in receive_report_demo.py

The bug occurs when inbox items are stored as string URIs instead of full objects.
When the demo tries to access item.as_id on a string, it fails.

Per ActivityStreams spec, collection items can be:
- Full objects (with as_id attribute)
- Links (with as_id attribute)
- String URIs (no as_id attribute)
- None (for optional fields)

The demo code needs to handle all these cases.
"""

from vultron.as_vocab.base.objects.actors import as_Actor
from vultron.as_vocab.base.objects.collections import as_OrderedCollection
from vultron.as_vocab.base.objects.activities.base import as_Activity


def test_inbox_items_can_be_strings():
    """Test that inbox items can be string URIs (per ActivityStreams spec)."""
    actor = as_Actor(
        as_id="https://example.org/alice",
        name="Alice",
    )

    # Add a string URI to inbox (this is valid per ActivityStreams spec)
    activity_uri = "https://example.org/activities/123"
    actor.inbox.items.append(activity_uri)

    # This should not raise an error
    assert len(actor.inbox.items) == 1
    assert actor.inbox.items[0] == activity_uri

    # Accessing as_id on a string should fail (this is the bug)
    # We need to handle this gracefully
    item = actor.inbox.items[0]
    if isinstance(item, str):
        item_id = item  # String IS the ID
    else:
        item_id = item.as_id  # Object has as_id attribute

    assert item_id == activity_uri


def test_inbox_items_can_be_objects():
    """Test that inbox items can be full objects."""
    actor = as_Actor(
        as_id="https://example.org/alice",
        name="Alice",
    )

    # Add a full activity object to inbox
    activity = as_Activity(
        as_id="https://example.org/activities/123",
        actor="https://example.org/bob",
    )
    actor.inbox.items.append(activity)

    # This should work
    assert len(actor.inbox.items) == 1
    assert actor.inbox.items[0].as_id == activity.as_id


def test_inbox_items_mixed_types():
    """Test that inbox can contain both strings and objects."""
    actor = as_Actor(
        as_id="https://example.org/alice",
        name="Alice",
    )

    # Add both strings and objects
    uri1 = "https://example.org/activities/123"
    activity2 = as_Activity(
        as_id="https://example.org/activities/456",
        actor="https://example.org/bob",
    )
    uri3 = "https://example.org/activities/789"

    actor.inbox.items.append(uri1)
    actor.inbox.items.append(activity2)
    actor.inbox.items.append(uri3)

    assert len(actor.inbox.items) == 3

    # Helper function to extract ID from any item type
    def get_item_id(item):
        if isinstance(item, str):
            return item
        return item.as_id

    assert get_item_id(actor.inbox.items[0]) == uri1
    assert get_item_id(actor.inbox.items[1]) == activity2.as_id
    assert get_item_id(actor.inbox.items[2]) == uri3
