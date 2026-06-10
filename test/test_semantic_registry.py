"""Tests for the unified SemanticRegistry module."""

import importlib

import pytest

from vultron.core.models.events import MessageSemantics
from vultron.core.models.events.base import VultronEvent
from vultron.errors import RegistryOrderError
from vultron.semantic_registry import (
    SEMANTIC_REGISTRY,
    _validate_registry_order,
    lookup_entry,
    semantics_to_activity_class,
    use_case_map,
)
from vultron.semantic_registry._entry import SemanticEntry
from vultron.wire.as2.enums import as_TransitiveActivityType as TAtype
from vultron.wire.as2.extractor import ActivityPattern
from vultron.core.models.enums import VultronObjectType as VOtype


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


# ---------------------------------------------------------------------------
# _validate_registry_order() unit tests
# ---------------------------------------------------------------------------


class _StubEvent(VultronEvent):
    """Minimal VultronEvent subclass for use in validator unit tests."""


class _StubUseCase:
    """Minimal use-case stub for use in validator unit tests."""


def _make_entry(
    semantics: MessageSemantics, pattern: ActivityPattern
) -> SemanticEntry:
    return SemanticEntry(
        semantics=semantics,
        pattern=pattern,
        event_class=_StubEvent,
        use_case_class=_StubUseCase,
    )


def test_validate_registry_order_valid_ordering_passes():
    """Specific-before-general ordering must not raise."""
    # specific: Create + VulnerabilityReport object
    specific = _make_entry(
        MessageSemantics.CREATE_REPORT,
        ActivityPattern(
            activity_=TAtype.CREATE,
            object_=VOtype.VULNERABILITY_REPORT,
        ),
    )
    # general: Create only
    general = _make_entry(
        MessageSemantics.CREATE_CASE,
        ActivityPattern(activity_=TAtype.CREATE),
    )
    # specific first — correct order
    _validate_registry_order([specific, general])


def test_validate_registry_order_reversed_pair_raises():
    """General-before-specific ordering must raise RegistryOrderError."""
    specific = _make_entry(
        MessageSemantics.CREATE_REPORT,
        ActivityPattern(
            activity_=TAtype.CREATE,
            object_=VOtype.VULNERABILITY_REPORT,
        ),
    )
    general = _make_entry(
        MessageSemantics.CREATE_CASE,
        ActivityPattern(activity_=TAtype.CREATE),
    )
    # general first — wrong order
    with pytest.raises(RegistryOrderError):
        _validate_registry_order([general, specific])


def test_validate_registry_order_same_specificity_passes():
    """Entries with identical pattern dumps must not raise.

    The import-time guard checks only strict-subset violations; equal-specificity
    (ambiguous) pairs are left to test_non_overlapping_activity_patterns().
    """
    pattern_a = _make_entry(
        MessageSemantics.CREATE_REPORT,
        ActivityPattern(
            activity_=TAtype.CREATE,
            object_=VOtype.VULNERABILITY_REPORT,
        ),
    )
    pattern_b = _make_entry(
        MessageSemantics.CREATE_CASE,
        ActivityPattern(
            activity_=TAtype.CREATE,
            object_=VOtype.VULNERABILITY_REPORT,
        ),
    )
    _validate_registry_order([pattern_a, pattern_b])


def test_live_registry_import_guard_passes():
    """Reload semantic_registry to exercise the import-time order guard.

    Verifies that _validate_registry_order(SEMANTIC_REGISTRY) is called at
    module load and does not raise for the live registry.
    """
    import vultron.semantic_registry

    importlib.reload(vultron.semantic_registry)
