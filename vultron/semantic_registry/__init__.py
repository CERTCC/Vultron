"""Consolidated semantic dispatch registry for the Vultron Protocol.

``SEMANTIC_REGISTRY`` is the single source of truth that maps each
``MessageSemantics`` value to the five components needed to process an
inbound ActivityStreams activity:

- ``pattern`` — wire-layer ``ActivityPattern`` for recognising the activity
- ``event_class`` — core domain ``VultronEvent`` subclass to construct
- ``use_case_class`` — core use-case class to execute
- ``wire_activity_class`` — wire-layer ``as_Activity`` subclass for
  DataLayer coercion (may be ``None`` for types without a specific wire class)
- ``include_activity`` — whether to populate ``VultronEvent.activity``
  during extraction (replaces the old ``_ACTIVITY_SEMANTICS`` set)

Ordering of entries in ``SEMANTIC_REGISTRY`` matches the previously-defined
``SEMANTICS_ACTIVITY_PATTERNS`` ordering — more specific patterns before
general ones, ``UNKNOWN`` last.

This package is a neutral layer importable by wire, core, adapter, and test
code.  ``extractor.py`` must NOT import from this package (it provides the
``ActivityPattern`` instances imported here).

Each domain sub-module (``report``, ``case``, ``actor``, ``embargo``,
``sync``, ``case_participant``, ``note``, ``status``, ``unknown``) exports
an ``ENTRIES`` list.  This ``__init__`` assembles them in the order that
preserves the original single-file dispatch sequence:

  report → case → actor → embargo → sync → case_participant → note → status → unknown

``sync`` begins with ``CLOSE_CASE`` (position 32 in the original file),
followed by the case-log sync entries.  ``case_participant`` entries follow
sync (positions 35–37).  ``unknown`` MUST remain last.

Public API
----------
``SemanticEntry`` — dataclass holding all dispatch components for one type
``SEMANTIC_REGISTRY`` — ordered list of ``SemanticEntry`` values
``find_matching_semantics(activity)`` — iterates ``SEMANTIC_REGISTRY`` directly
``extract_event(activity)`` — convenience wrapper: pattern-match + extract
``lookup_entry(semantics)`` — O(1) entry lookup by ``MessageSemantics``
``use_case_map()`` — returns ``MessageSemantics`` → use-case class mapping
``semantics_to_activity_class()`` — returns ``MessageSemantics`` → wire class
``matches_semantics(activity, expected)`` — predicate for test authors
"""

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

from vultron.core.models.events.base import MessageSemantics, VultronEvent
from vultron.semantic_registry._entry import SemanticEntry
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from . import (
    actor,
    case,
    case_participant,
    embargo,
    note,
    report,
    status,
    sync,
    unknown,
)

# ---------------------------------------------------------------------------
# The registry.  Order matters: find_matching_semantics() returns the first
# pattern that matches, so more specific patterns must appear before general
# ones.  The unknown fallback entries (pattern=None) must be last.
# ---------------------------------------------------------------------------

SEMANTIC_REGISTRY: list[SemanticEntry] = (
    report.ENTRIES
    + case.ENTRIES
    + actor.ENTRIES
    + embargo.ENTRIES
    + sync.ENTRIES  # begins with CLOSE_CASE (pos 32), then log-sync entries
    + case_participant.ENTRIES
    + note.ENTRIES
    + status.ENTRIES
    + unknown.ENTRIES  # MUST be last — catch-all sentinels
)

# ---------------------------------------------------------------------------
# Fast-lookup index: O(1) entry access by MessageSemantics value.
# ---------------------------------------------------------------------------

_ENTRY_MAP: dict[MessageSemantics, SemanticEntry] = {
    e.semantics: e for e in SEMANTIC_REGISTRY
}

# Frozenset of activity type strings that have at least one registered pattern.
# Used by find_matching_semantics() to distinguish "known type with unresolvable
# object_" from "genuinely unknown activity type".
_ACTIVITY_TYPES_WITH_PATTERNS: frozenset[str] = frozenset(
    str(e.pattern.activity_)
    for e in SEMANTIC_REGISTRY
    if e.pattern is not None
)


def lookup_entry(semantics: MessageSemantics) -> SemanticEntry:
    """Return the ``SemanticEntry`` for *semantics*.

    Falls back to the ``UNKNOWN`` entry when *semantics* is not registered
    (which should not happen in practice).
    """
    return _ENTRY_MAP.get(semantics, _ENTRY_MAP[MessageSemantics.UNKNOWN])


from vultron.wire.as2.extractor import (  # noqa: E402
    extract_intent as _extract_intent,
)

__all__ = [
    "SemanticEntry",
    "SEMANTIC_REGISTRY",
    "lookup_entry",
    "find_matching_semantics",
    "matches_semantics",
    "extract_event",
    "use_case_map",
    "semantics_to_activity_class",
]


def extract_event(
    activity: as_Activity,
) -> VultronEvent:
    """Extract a typed ``VultronEvent`` from an AS2 activity.

    This is the public entry point for the inbound activity pipeline.  It
    combines pattern matching (``find_matching_semantics``) with field
    extraction (``extract_intent``) using the registry entry for the matched
    semantics.

    Args:
        activity: The rehydrated AS2 activity to process.

    Returns:
        A concrete ``VultronEvent`` subclass populated with domain fields.
    """
    semantics = find_matching_semantics(activity)
    entry = lookup_entry(semantics)
    return _extract_intent(
        activity,
        semantics=semantics,
        event_class=entry.event_class,
        include_activity=entry.include_activity,
    )


def use_case_map() -> dict[MessageSemantics, type]:
    """Return a mapping of ``MessageSemantics`` → use-case class.

    Equivalent to the old ``USE_CASE_MAP`` dict.  Used by the dispatcher
    initializer to build its routing table.
    """
    return {e.semantics: e.use_case_class for e in SEMANTIC_REGISTRY}


def semantics_to_activity_class() -> dict[MessageSemantics, type[as_Activity]]:
    """Return a mapping of ``MessageSemantics`` → wire activity class.

    Equivalent to the old ``SEMANTICS_TO_ACTIVITY_CLASS`` dict.  Used by the
    DataLayer adapter to coerce stored rows back to typed AS2 activities.
    Only entries with a non-``None`` ``wire_activity_class`` are included.
    """
    return {
        e.semantics: e.wire_activity_class
        for e in SEMANTIC_REGISTRY
        if e.wire_activity_class is not None
    }


def find_matching_semantics(activity: as_Activity) -> MessageSemantics:
    """Find the MessageSemantics for the given AS2 activity.

    Iterates ``SEMANTIC_REGISTRY`` in order and returns the first match.
    Returns ``MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT`` when no pattern
    matches, the activity type is registered (has patterns), and ``object_``
    is still a bare string URI (rehydration did not resolve it).
    Returns ``MessageSemantics.UNKNOWN`` when the activity type is not
    registered at all.

    ``SEMANTIC_REGISTRY`` is the single source of truth for pattern-match order;
    more specific patterns must appear before general ones.

    Args:
        activity: The AS2 activity to classify.

    Returns:
        The matching MessageSemantics value, or MessageSemantics.UNKNOWN.
    """
    for entry in SEMANTIC_REGISTRY:
        if entry.pattern is not None and entry.pattern.match(activity):
            return entry.semantics
    obj = getattr(activity, "object_", None)
    activity_type = str(activity.type_) if activity.type_ else ""
    if isinstance(obj, str) and activity_type in _ACTIVITY_TYPES_WITH_PATTERNS:
        return MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT
    return MessageSemantics.UNKNOWN


def matches_semantics(
    activity: as_Activity,
    expected: MessageSemantics,
) -> bool:
    """Return True if *activity* matches the *expected* MessageSemantics.

    Convenience predicate for test authors — eliminates the need to import
    named ``*Pattern`` constants just to assert semantic identity.

    Args:
        activity: The AS2 activity to classify.
        expected: The expected ``MessageSemantics`` value.

    Returns:
        True when ``find_matching_semantics(activity) == expected``.
    """
    return find_matching_semantics(activity) == expected
