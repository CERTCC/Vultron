"""Tolerant field access, actor-name extraction and friendly labels (DRPT-02, DRPT-03)."""

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

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from vultron.core.models.events.base import MessageSemantics
from vultron.semantic_registry import lookup_entry

# ---------------------------------------------------------------------------
# Tolerant field access (DRPT-02-003)
# ---------------------------------------------------------------------------


def _first(mapping: dict[str, Any], *names: str, default: Any = None) -> Any:
    """Return the first present, non-None value among ``names``.

    Tolerates the camelCase/snake_case spelling split present in the source
    JSONL (e.g. ``logIndex``/``log_index``), mirroring the accessors in
    ``test/ci/test_case_ledger_invariants.py``.
    """
    for name in names:
        if name in mapping and mapping[name] is not None:
            return mapping[name]
    return default


def _coerce_int(value: Any, default: int) -> int:
    """Best-effort ``int`` coercion; returns ``default`` on failure.

    Keeps :meth:`CaseTimelineEvent.from_raw` tolerant of corrupt entries (e.g.
    a non-numeric ``logIndex``) so a single malformed field degrades one row
    rather than crashing the whole report (DRPT-01-004, DRPT-02-003).
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _actor_uri(actor: Any) -> str | None:
    """Normalize a payload ``actor`` field to a string URI, or ``None``.

    Tolerates both the bare-string spelling and an inline actor object
    (``{"id": "...", "type": "..."}``) so a nested actor does not raise a
    validation error out of the distiller (DRPT-02-003).
    """
    if isinstance(actor, str):
        return actor or None
    if isinstance(actor, dict):
        ref = actor.get("id") or actor.get("id_")
        return str(ref) if ref else None
    return None


def _candidate_dicts(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """Return ``snapshot`` plus nested status-bearing dicts.

    A ``ParticipantStatus``/``CaseStatus`` may be encoded directly in the
    payload snapshot or nested under an ``Add`` activity's ``object`` (and a
    ``CaseStatus`` may itself nest under ``caseStatus``). ``VulnerabilityCase``
    payloads carry a ``caseStatuses`` array; each item in that list is also
    added so EM/CS state on early rows is not missed. This flattens all those
    layers so dimension-state extraction can search all of them.
    """
    seen: list[dict[str, Any]] = []

    def _add(node: Any) -> None:
        if not isinstance(node, dict) or any(node is s for s in seen):
            return
        seen.append(node)
        for key in ("object", "object_", "caseStatus", "case_status"):
            _add(node.get(key))
        for list_key in ("caseStatuses", "case_statuses"):
            items = node.get(list_key)
            if isinstance(items, list):
                for item in items:
                    _add(item)

    _add(snapshot)
    return seen


def _dimension_state(
    candidates: Iterable[dict[str, Any]],
    dimension_key: str,
    *flat_names: str,
) -> str | None:
    """Extract a single state-machine dimension value from candidate dicts.

    Handles all three live shapes: the bare state value a dimension serializes
    to since ARCH-25-005 (ADR-0099) / SDO-01-004 (``{"rm": "..."}``), the ADR-0036
    one-key mapping (``{"rm": {"state": "..."}}``), and the legacy flat wire
    spelling (``{"rmState": "..."}``).  Missing one of them makes every affected
    row report ``None``, which is the #2232 / #2262 failure shape — see
    ``notes/case-ledger-parsing.md``.
    """
    for candidate in candidates:
        dim = candidate.get(dimension_key)
        if isinstance(dim, dict):
            state = dim.get("state")
            if state:
                return str(state)
        elif isinstance(dim, str) and dim:
            return str(dim)
        for flat in flat_names:
            value = candidate.get(flat)
            if value:
                return str(value)
    return None


# ---------------------------------------------------------------------------
# Actor name extraction
# ---------------------------------------------------------------------------

#: ActivityStreams actor types whose ``name`` field, when present, maps the
#: ``id`` to a human-readable display name (e.g. "Vendor", "Reporter").
_NAME_BEARING_TYPES = frozenset(
    {
        "Organization",
        "Person",
        "Service",
        "Application",
        "Group",
        "Actor",
    }
)


def _collect_actor_names_from_obj(
    obj: Any,
    out: dict[str, str],
) -> None:
    """Recursively scan ``obj`` for actor dicts carrying ``id`` + ``name``.

    Populates ``out`` with ``{id: name}`` mappings for every actor-like object
    found at any nesting level in the payload.  Only the first ``name`` seen for
    a given ``id`` is recorded (first-writer-wins so earlier, more authoritative
    entries dominate).
    """
    if isinstance(obj, list):
        for item in obj:
            _collect_actor_names_from_obj(item, out)
        return
    if not isinstance(obj, dict):
        return
    obj_type = obj.get("type") or obj.get("type_")
    obj_id = obj.get("id") or obj.get("id_")
    obj_name = obj.get("name")
    if (
        obj_type in _NAME_BEARING_TYPES
        and obj_id
        and obj_name
        and isinstance(obj_id, str)
        and isinstance(obj_name, str)
        and obj_name.strip()
        and obj_id not in out
    ):
        out[obj_id] = obj_name.strip()
    # Recurse into common nested keys.  ActivityStreams permits ``actor``,
    # ``object``, ``target``, and ``origin`` to carry a list of objects (e.g.
    # multiple recipients); the list branch at the top of this function scans
    # each element, so a plain recursive call handles scalars and lists alike.
    for key in ("actor", "object", "object_", "target", "origin"):
        _collect_actor_names_from_obj(obj.get(key), out)


def collect_actor_names(
    replicas: dict[str, list[dict[str, Any]]],
) -> dict[str, str]:
    """Build a URI→display-name map by scanning all raw ledger entries.

    Walks every payload snapshot in ``replicas`` looking for actor objects
    that carry both an ``id`` (URI) and a ``name`` field.  Returns a
    ``{uri: name}`` mapping used to resolve UUID-based actor URIs to semantic
    labels (e.g. "Vendor", "Reporter") in the rendered report.
    """
    names: dict[str, str] = {}
    for actor_key in sorted(replicas):
        for raw in replicas[actor_key]:
            payload = _first(
                raw, "payload_snapshot", "payloadSnapshot", default={}
            )
            if isinstance(payload, dict):
                _collect_actor_names_from_obj(payload, names)
    return names


# ---------------------------------------------------------------------------
# Friendly naming (DRPT-03)
# ---------------------------------------------------------------------------

#: Activity-Streams wrapper types whose ``object`` child is the real semantic target.
_WRAPPER_TYPES = frozenset({"Accept", "Reject", "Offer", "Invite"})

#: Wire types that resolve to actor names; use friendly_actor_name on their id instead of a generic noun.
_ACTOR_LIKE_TYPES = frozenset(
    {
        "Organization",
        "Actor",
        "Service",
        "Application",
        "Person",
        "Group",
        "CaseParticipant",
    }
)

#: Wire object type → friendly noun for event summaries and the target column.
_TARGET_NOUNS: dict[str, str] = {
    "VulnerabilityReport": "report",
    "VulnerabilityCase": "case",
    "CaseProposal": "case proposal",
    "Note": "note",
    "ParticipantStatus": "participant status",
    "CaseStatus": "case status",
    "EmbargoEvent": "embargo",
    "CaseParticipant": "participant",
    "CaseLedgerEntry": "ledger entry",
    "Actor": "actor",
    "Offer": "offer",
    "Accept": "acceptance",
    "Reject": "rejection",
}


def _titleize(segment: str) -> str:
    """Turn a URI/dir segment into a friendly label ("case-actor" → "Case Actor").

    Splits on ``-``/``_``, drops UUID-like hex tokens (so a
    ``case-actor-<uuid>`` sub-actor id collapses to "Case Actor"), and
    capitalizes the remaining words.
    """
    raw = segment.replace("_", " ").replace("-", " ").split()
    words = [w for w in raw if not _looks_like_hex_token(w)]
    if not words:
        words = raw
    return " ".join(w.capitalize() for w in words)


def _looks_like_hex_token(token: str) -> bool:
    """Return True for a pure-hex token of length >= 6 (a likely UUID chunk)."""
    return len(token) >= 6 and all(
        c in "0123456789abcdef" for c in token.lower()
    )


def friendly_actor_name(
    actor_uri: str | None,
    actor_names: dict[str, str] | None = None,
) -> str:
    """Return a short, friendly actor label derived from an actor URI.

    Checks ``actor_names`` first (a URI→display-name map built from payload
    snapshots); falls back to the last URI path segment when no entry is found
    (``…/actors/reporter`` → "Reporter").  Returns an em dash when no acting actor
    is recorded (e.g. genesis entries).
    """
    if not actor_uri:
        return "—"
    if actor_names and actor_uri in actor_names:
        return actor_names[actor_uri]
    segment = actor_uri.rstrip("/").rsplit("/", 1)[-1]
    return _titleize(segment) or segment


def friendly_target_noun(target_type: str | None) -> str | None:
    """Return a friendly noun for a wire object type (``Note`` → "note")."""
    if not target_type:
        return None
    if target_type in _TARGET_NOUNS:
        return _TARGET_NOUNS[target_type]
    # Fallback: split a CamelCase / prefixed type into lowercase words.
    stripped = (
        target_type[3:] if target_type.startswith("as_") else target_type
    )
    words: list[str] = []
    current = ""
    for char in stripped:
        if char.isupper() and current:
            words.append(current)
            current = char
        else:
            current += char
    if current:
        words.append(current)
    return " ".join(w.lower() for w in words) if words else target_type.lower()


def friendly_object_label(
    obj_type: str | None, obj_ref: str | None
) -> str | None:
    """Return a friendly label for a target object.

    Actor-like types (Organization, Actor, …) are resolved via
    :func:`friendly_actor_name` using their URI so the label reads "Vendor"
    rather than "organization".  All other types fall back to
    :func:`friendly_target_noun`.
    """
    if not obj_type:
        return friendly_actor_name(obj_ref) if obj_ref else None
    if obj_type in _ACTOR_LIKE_TYPES:
        return friendly_actor_name(obj_ref)
    return friendly_target_noun(obj_type)


def event_phrase(semantic_type: str) -> str:
    """Map a semantic type to an active-voice phrase via the semantic registry.

    Looks up the ``SemanticEntry`` for *semantic_type* in ``SEMANTIC_REGISTRY``
    and returns ``entry.phrase`` with all named slots filled with ``"—"``
    (DRPT-03-002).  Falls back to a humanized version of *semantic_type* when
    the semantic type is not a recognized ``MessageSemantics`` value.
    """
    try:
        semantics = MessageSemantics(semantic_type)
    except ValueError:
        humanized = semantic_type.replace("_", " ").strip()
        return humanized or "performed an action"
    entry = lookup_entry(semantics)
    slots: dict[str, str] = defaultdict(lambda: "—")
    return entry.phrase.format_map(slots)
