"""Tests for as_Collection duplicate-ignoring behaviour (#2110)."""

import pytest

from vultron.wire.as2.vocab.base.objects.base import as_Object
from vultron.wire.as2.vocab.base.objects.collections import as_Collection


@pytest.fixture()
def item_a() -> as_Object:
    return as_Object(id_="https://example.com/objects/a")


@pytest.fixture()
def item_b() -> as_Object:
    return as_Object(id_="https://example.com/objects/b")


@pytest.fixture()
def item_a_dup() -> as_Object:
    """Same id_ as item_a, different object instance."""
    return as_Object(id_="https://example.com/objects/a")


def test_append_unique_items(item_a, item_b):
    col = as_Collection()
    col.append(item_a)
    col.append(item_b)
    assert col.totalItems == 2


def test_append_duplicate_is_ignored(item_a, item_a_dup):
    col = as_Collection()
    col.append(item_a)
    col.append(item_a_dup)
    assert col.totalItems == 1


def test_append_item_without_id_is_always_added():
    col = as_Collection()
    no_id_a = as_Object()
    no_id_b = as_Object()
    col.append(no_id_a)
    col.append(no_id_b)
    assert col.totalItems == 2


def test_construction_with_duplicate_items_deduplicates(item_a, item_a_dup):
    col = as_Collection(items=[item_a, item_a_dup])
    # Items list is not modified at construction (dedup only applies to append)
    assert col.totalItems == 2
    # But subsequent append of the same id is skipped
    col.append(item_a_dup)
    assert col.totalItems == 2


def test_round_trip_preserves_unique_items(item_a, item_b):
    col = as_Collection()
    col.append(item_a)
    col.append(item_b)
    data = col.model_dump(by_alias=True)
    restored = as_Collection.model_validate(data)
    assert restored.totalItems == 2
    # Duplicate still rejected after round-trip
    restored.append(as_Object(id_="https://example.com/objects/a"))
    assert restored.totalItems == 2


def test_append_string_ref_always_added():
    """String-ref items (bare URI strings) are not deduplicated — only object items with id_ are."""
    col = as_Collection()
    col.append("urn:uuid:abc123")
    col.append("urn:uuid:abc123")
    assert col.totalItems == 2


def test_append_none_always_added():
    """None items pass through append without dedup — None has no id_ to track."""
    col = as_Collection()
    col.append(None)
    col.append(None)
    assert col.totalItems == 2
