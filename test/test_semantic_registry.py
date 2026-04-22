"""Tests for the unified SemanticRegistry module."""

from vultron.core.models.events import MessageSemantics
from vultron.semantic_registry import (
    SEMANTIC_REGISTRY,
    lookup_entry,
    use_case_map,
    semantics_to_activity_class,
)


def test_registry_covers_all_semantics():
    registered = {e.semantics for e in SEMANTIC_REGISTRY}
    assert registered == set(MessageSemantics)


def test_registry_unknown_is_last():
    assert SEMANTIC_REGISTRY[-1].semantics == MessageSemantics.UNKNOWN


def test_registry_unresolvable_object_is_second_to_last():
    assert (
        SEMANTIC_REGISTRY[-2].semantics
        == MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT
    )


def test_non_unknown_entries_have_patterns():
    _no_pattern_sentinels = {
        MessageSemantics.UNKNOWN,
        MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT,
    }
    missing = [
        e.semantics
        for e in SEMANTIC_REGISTRY
        if e.semantics not in _no_pattern_sentinels and e.pattern is None
    ]
    assert not missing, f"Missing patterns: {missing}"


def test_non_unknown_entries_have_event_class():
    missing = [
        e.semantics
        for e in SEMANTIC_REGISTRY
        if e.semantics != MessageSemantics.UNKNOWN and e.event_class is None
    ]
    assert not missing, f"Missing event_class: {missing}"


def test_non_unknown_entries_have_use_case_class():
    missing = [
        e.semantics
        for e in SEMANTIC_REGISTRY
        if e.semantics != MessageSemantics.UNKNOWN and e.use_case_class is None
    ]
    assert not missing, f"Missing use_case_class: {missing}"


def test_use_case_map_keys_match_semantics():
    ucm = use_case_map()
    registered = set(ucm.keys())
    expected = set(MessageSemantics)
    assert registered == expected


def test_lookup_entry_returns_correct_entry():
    entry = lookup_entry(MessageSemantics.CREATE_REPORT)
    assert entry is not None
    assert entry.semantics == MessageSemantics.CREATE_REPORT


def test_lookup_entry_unknown_returns_unknown():
    entry = lookup_entry(MessageSemantics.UNKNOWN)
    assert entry is not None
    assert entry.semantics == MessageSemantics.UNKNOWN


def test_semantics_to_activity_class_excludes_none_wire_class():
    mapping = semantics_to_activity_class()
    for semantics, cls in mapping.items():
        assert cls is not None, f"{semantics} mapped to None"


def test_no_duplicate_semantics():
    seen = set()
    for entry in SEMANTIC_REGISTRY:
        assert entry.semantics not in seen, f"Duplicate: {entry.semantics}"
        seen.add(entry.semantics)
