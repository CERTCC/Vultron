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


@pytest.mark.spec("SE-03-001")
@pytest.mark.spec("VAM-01-001")
def test_registry_covers_all_semantics():
    registered = {e.semantics for e in SEMANTIC_REGISTRY}
    assert registered == set(MessageSemantics)


@pytest.mark.spec("VAM-09-002")
def test_registry_unknown_is_last():
    assert SEMANTIC_REGISTRY[-1].semantics == MessageSemantics.UNKNOWN


@pytest.mark.spec("SE-04-002")
def test_registry_unresolvable_object_is_second_to_last():
    assert (
        SEMANTIC_REGISTRY[-2].semantics
        == MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT
    )


@pytest.mark.spec("SE-03-001")
@pytest.mark.spec("SE-05-001")
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


@pytest.mark.spec("SE-05-002")
def test_non_unknown_entries_have_use_case_class():
    missing = [
        e.semantics
        for e in SEMANTIC_REGISTRY
        if e.semantics != MessageSemantics.UNKNOWN and e.use_case_class is None
    ]
    assert not missing, f"Missing use_case_class: {missing}"


@pytest.mark.spec("SE-05-002")
def test_use_case_map_keys_match_semantics():
    ucm = use_case_map()
    registered = set(ucm.keys())
    expected = set(MessageSemantics)
    assert registered == expected


@pytest.mark.spec("SE-02-001")
def test_lookup_entry_returns_correct_entry():
    entry = lookup_entry(MessageSemantics.CREATE_REPORT)
    assert entry is not None
    assert entry.semantics == MessageSemantics.CREATE_REPORT


@pytest.mark.spec("SE-02-003")
def test_lookup_entry_unknown_returns_unknown():
    entry = lookup_entry(MessageSemantics.UNKNOWN)
    assert entry is not None
    assert entry.semantics == MessageSemantics.UNKNOWN


@pytest.mark.spec("VAM-01-001")
def test_semantics_to_activity_class_excludes_none_wire_class():
    mapping = semantics_to_activity_class()
    for semantics, cls in mapping.items():
        assert cls is not None, f"{semantics} mapped to None"


@pytest.mark.spec("VAM-01-001")
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
        phrase="{actor} performed an action",
    )


@pytest.mark.spec("SE-03-002")
@pytest.mark.spec("VAM-01-003")
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


@pytest.mark.spec("SE-03-002")
@pytest.mark.spec("VAM-01-003")
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


@pytest.mark.spec("SE-03-002")
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


@pytest.mark.spec("SE-03-002")
@pytest.mark.spec("VAM-01-003")
def test_live_registry_import_guard_passes():
    """Reload semantic_registry to exercise the import-time order guard.

    Verifies that _validate_registry_order(SEMANTIC_REGISTRY) is called at
    module load and does not raise for the live registry.
    """
    import vultron.semantic_registry

    importlib.reload(vultron.semantic_registry)


# ---------------------------------------------------------------------------
# SE-07 phrase field requirements (AC-6)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "entry", SEMANTIC_REGISTRY, ids=lambda e: e.semantics.name
)
def test_every_entry_has_non_empty_phrase(entry):
    """Every registry entry MUST have a non-empty phrase (SE-07-001, SE-07-003)."""
    assert entry.phrase, f"{entry.semantics.name} has empty phrase"


@pytest.mark.parametrize(
    "entry", SEMANTIC_REGISTRY, ids=lambda e: e.semantics.name
)
def test_phrase_format_map_with_defaults_returns_non_empty(entry):
    """Phrase format_map with defaultdict fallback must not raise and return
    a non-empty string (SE-07-004)."""
    from collections import defaultdict

    slots: dict[str, str] = defaultdict(lambda: "X")
    result = entry.phrase.format_map(slots)
    assert (
        result
    ), f"{entry.semantics.name} phrase produced empty string after format_map"


def test_create_case_proposal_phrase_has_no_target_slot():
    """CREATE_CASE_PROPOSAL must not reference a ``{target}`` slot (#1787).

    ``create_case_proposal_activity`` builds a ``Create(as_CaseProposal)`` with
    no ``target`` field, so a ``{target}`` slot can never be filled at render
    time and always resolves to the em-dash fallback — producing a dangling
    ``"proposed a case to —"``.  The two SE-07 tests above do not catch this:
    they fill every slot from a ``defaultdict``, so an unfillable slot still
    renders non-empty.  Pin the phrase to a form that carries no ``{target}``.
    """
    entry = lookup_entry(MessageSemantics.CREATE_CASE_PROPOSAL)
    assert "{target}" not in entry.phrase, (
        "CREATE_CASE_PROPOSAL phrase references {target}, but the factory "
        "sets no target; the slot renders as a dangling em-dash. See #1787."
    )


# SE-07-005 — structural slot-allowlist test (CONCERN-1898)
_RUNTIME_POPULATED_SLOTS = frozenset({"actor", "object", "target"})
_RESERVED_UNPOPULATED_SLOTS = frozenset({"context", "origin", "inner_object"})


def test_no_phrase_uses_unpopulated_slots():
    """No phrase may reference a slot the render pipeline never fills (SE-07-005).

    The runtime render pipeline (``CaseTimelineEvent.summary``,
    ``event_phrase()``) only populates ``{actor}``, ``{object}``, and
    ``{target}``.  A phrase referencing ``{context}``, ``{origin}``, or
    ``{inner_object}`` passes ``test_phrase_format_map_with_defaults_returns_non_empty``
    (which uses a ``defaultdict`` that fills every slot) but produces a dangling
    ``"—"`` in production because those slots are never set at render time.
    This test makes unfillable-slot bugs a CI failure (CONCERN-1898).
    """
    import re

    slot_re = re.compile(r"\{(\w+)\}")
    violations: list[str] = []
    for entry in SEMANTIC_REGISTRY:
        slots = set(slot_re.findall(entry.phrase))
        bad = slots & _RESERVED_UNPOPULATED_SLOTS
        if bad:
            violations.append(
                f"{entry.semantics.name}: phrase={entry.phrase!r} uses "
                f"unpopulated slot(s) {sorted(bad)}"
            )
    assert not violations, (
        "The following phrases reference slots the render pipeline never fills:\n"
        + "\n".join(violations)
        + "\nUse only {actor}, {object}, {target}. "
        "If the pipeline is extended to populate a new slot, update "
        "_RUNTIME_POPULATED_SLOTS in this test."
    )


@pytest.mark.parametrize(
    "entry", SEMANTIC_REGISTRY, ids=lambda e: e.semantics.name
)
def test_no_phrase_uses_unknown_slots(entry):
    """Every slot name in a phrase must be a known identifier (SE-07-002).

    Catches typos like ``{actr}`` or new slot names introduced without
    updating the allowlist.  Valid slot names are the runtime-populated set
    plus the reserved-for-future set documented in SE-07-002.
    """
    import re

    all_known = _RUNTIME_POPULATED_SLOTS | _RESERVED_UNPOPULATED_SLOTS
    slot_re = re.compile(r"\{(\w+)\}")
    slots = set(slot_re.findall(entry.phrase))
    unknown = slots - all_known
    assert not unknown, (
        f"{entry.semantics.name}: phrase={entry.phrase!r} uses unknown "
        f"slot(s) {sorted(unknown)}. Valid names: {sorted(all_known)}"
    )


# ---------------------------------------------------------------------------
# SE-07-006 — parametrised behavioural render check (AC-2, AC-4)
# ---------------------------------------------------------------------------


_TRAILING_DASH_XFAIL_REASONS: dict[MessageSemantics, str] = {}


@pytest.mark.spec("SE-07-006")
@pytest.mark.parametrize(
    "entry",
    [
        (
            pytest.param(
                e,
                id=e.semantics.name,
                marks=[
                    pytest.mark.xfail(
                        strict=True,
                        reason=_TRAILING_DASH_XFAIL_REASONS[e.semantics],
                    )
                ],
            )
            if e.semantics in _TRAILING_DASH_XFAIL_REASONS
            else pytest.param(e, id=e.semantics.name)
        )
        for e in SEMANTIC_REGISTRY
    ],
)
def test_event_phrase_render_no_dangling_output(entry):
    """Parametrised: event_phrase() must not produce trailing em-dash or leave
    un-substituted ``{slot}`` markers for any semantic type (SE-07-006, AC-2, AC-4).

    Calls the real runtime render function — unlike the SE-07-004 defaultdict
    test, which fills every slot (including reserved ones), masking the class of
    bug where a phrase references a slot the runtime never populates.
    """
    import re

    from vultron.demo.report import event_phrase

    _slot_re = re.compile(r"\{(\w+)\}")
    result = event_phrase(entry.semantics.value)
    assert not result.endswith(
        "—"
    ), f"{entry.semantics.name}: event_phrase() ends with '—': {result!r}"
    assert not _slot_re.search(
        result
    ), f"{entry.semantics.name}: event_phrase() left un-substituted slot: {result!r}"
