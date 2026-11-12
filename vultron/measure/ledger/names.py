"""The display-name resolver shared by every ledger reader (CEH-01-006, DRPT-03-001).

Two tools that read the same ledger and name the same actor differently are hard
to read side by side, so the demo report and the measure layer resolve an actor
URI, and label an entry's object, through this one resolver. It lives beside the ledger reader so the demo
layer imports both from here and the two packages never import each other
(``notes/case-event-history.md`` § "Reuse the One JSONL Walker").
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

from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from vultron.core.display import friendly_name
from vultron.measure.ledger.fields import payload_of

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
    obj: object,
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
    replicas: Mapping[str, Iterable[Mapping[str, Any]]],
) -> dict[str, str]:
    """Build a URI→display-name map by scanning all raw ledger entries.

    Walks every payload snapshot in ``replicas`` looking for actor objects
    that carry both an ``id`` (URI) and a ``name`` field.  Returns a
    ``{uri: name}`` mapping used to resolve UUID-based actor URIs to semantic
    labels (e.g. "Vendor", "Reporter").  Replicas are scanned in sorted key
    order, so the first name seen for a URI does not depend on input order.
    """
    names: dict[str, str] = {}
    for key in sorted(replicas):
        for raw in replicas[key]:
            _collect_actor_names_from_obj(payload_of(raw), names)
    return names


def _collect_participant_actors_from_obj(
    obj: object, out: dict[str, str]
) -> None:
    """Recursively map each ``CaseParticipant`` id to the actor it stands for."""
    if isinstance(obj, list):
        for item in obj:
            _collect_participant_actors_from_obj(item, out)
        return
    if not isinstance(obj, dict):
        return
    obj_type = obj.get("type") or obj.get("type_")
    obj_id = obj.get("id") or obj.get("id_")
    actor = obj.get("attributedTo") or obj.get("attributed_to")
    if (
        obj_type == "CaseParticipant"
        and isinstance(obj_id, str)
        and isinstance(actor, str)
        and obj_id
        and actor
    ):
        out.setdefault(obj_id, actor)
    for value in obj.values():
        _collect_participant_actors_from_obj(value, out)


def collect_participant_actors(
    replicas: Mapping[str, Iterable[Mapping[str, Any]]],
) -> dict[str, str]:
    """Build a participant-id→actor-URI map by scanning all raw ledger entries.

    An activity often names a participant by its ``CaseParticipant`` id
    alone, an opaque identifier; the case snapshots carry each participant
    inline with the actor it is ``attributedTo``.  The map lets a label name
    that actor instead (DRPT-03-009).  Replicas are scanned in sorted key
    order, and the first actor seen for an id is kept.
    """
    actors: dict[str, str] = {}
    for key in sorted(replicas):
        for raw in replicas[key]:
            _collect_participant_actors_from_obj(payload_of(raw), actors)
    return actors


def friendly_actor_name(
    actor_uri: str | None,
    actor_names: Mapping[str, str] | None = None,
) -> str:
    """Return a short, friendly actor label derived from an actor URI.

    Checks ``actor_names`` first (a URI→display-name map built from payload
    snapshots); falls back to the URI path-segment heuristic of
    :func:`vultron.core.display.friendly_name` (``…/actors/reporter`` →
    "Reporter"), and to the raw last segment when that heuristic leaves no
    word.  Returns an em dash only when no acting actor is recorded (e.g.
    genesis entries).
    """
    if not actor_uri:
        return "—"
    if actor_names and actor_uri in actor_names:
        return actor_names[actor_uri]
    label = friendly_name(actor_uri)
    if label == "—":
        # No word survives titleizing (e.g. ``…/actors/---``): show the raw
        # segment, which names *something*, rather than the no-actor dash.
        return actor_uri.rstrip("/").rsplit("/", 1)[-1]
    return label


# ---------------------------------------------------------------------------
# Object labels (DRPT-03-001, DRPT-03-009)
# ---------------------------------------------------------------------------

#: Activity-Streams wrapper types whose ``object`` child is the real semantic target.
WRAPPER_TYPES = frozenset({"Accept", "Reject", "Offer", "Invite"})

#: Wire types that resolve to actor names; use friendly_actor_name on their id instead of a generic noun.
ACTOR_LIKE_TYPES = frozenset(
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

#: The label :func:`display_label` gives an actor that has no display name
#: and whose URI holds no readable word (DRPT-03-009).
UNNAMED_ACTOR = "unnamed actor"

#: The label :func:`display_label` gives an untyped reference that has no
#: display name and whose URI holds no readable word (DRPT-03-009).
UNNAMED_OBJECT = "unnamed object"


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
    if obj_type in ACTOR_LIKE_TYPES:
        return friendly_actor_name(obj_ref)
    return friendly_target_noun(obj_type)


def _is_opaque(ref: str) -> bool:
    """Whether *ref* holds no readable word: a URN, or a UUID last segment."""
    if ref.lower().startswith("urn:"):
        return True
    segment = ref.rstrip("/").rsplit("/", 1)[-1]
    try:
        uuid.UUID(segment)
    except ValueError:
        return False
    return True


def display_label(
    ref: str | None,
    obj_type: str | None,
    actor_names: Mapping[str, str],
    *,
    case_id: str | None = None,
) -> str | None:
    """Label a reference without ever showing a bare URI or UUID (DRPT-03-009).

    The display name collected from the payloads wins.  Otherwise the case
    itself reads "case", a typed non-actor object reads as its type's noun
    (:func:`friendly_target_noun`), and an actor, or a reference with no type,
    reads as the URI path-segment heuristic of :func:`friendly_actor_name`.
    When that heuristic would show an opaque identifier — a ``urn:`` reference
    or a UUID last segment — the label is :data:`UNNAMED_ACTOR` for an actor
    and :data:`UNNAMED_OBJECT` for an untyped reference.  Returns ``None``
    when there is neither a reference nor a type.
    """
    if ref and ref in actor_names:
        return actor_names[ref]
    if ref and case_id and ref == case_id:
        return _TARGET_NOUNS["VulnerabilityCase"]
    if obj_type and obj_type not in ACTOR_LIKE_TYPES:
        return friendly_target_noun(obj_type)
    if not ref:
        return UNNAMED_ACTOR if obj_type else None
    if _is_opaque(ref):
        return UNNAMED_ACTOR if obj_type else UNNAMED_OBJECT
    return friendly_actor_name(ref)


@dataclass(frozen=True)
class EntryReferences:
    """The object and destination one ledger entry's activity names.

    Fields:
        object_ref: The id of the innermost non-wrapper object (for a
            ``CaseParticipant``, the actor it is attributed to).
        object_type: That object's wire type, when the payload carries it.
        target_ref: The id of the activity's destination (``target``).
        target_type: The destination's wire type, when carried.
    """

    object_ref: str | None = None
    object_type: str | None = None
    target_ref: str | None = None
    target_type: str | None = None


def _ref_and_type(value: object) -> tuple[str | None, str | None]:
    """The id and wire type of an inline object, or the id a string names."""
    if isinstance(value, str):
        return value, None
    if not isinstance(value, dict):
        return None, None
    ref = value.get("id") or value.get("id_")
    obj_type = value.get("type") or value.get("type_")
    # CaseParticipant is a proxy; use attributedTo for name resolution.
    if obj_type == "CaseParticipant":
        ref = value.get("attributedTo") or value.get("attributed_to") or ref
    return (
        str(ref) if ref else None,
        str(obj_type) if obj_type else None,
    )


def entry_references(payload: Mapping[str, Any]) -> EntryReferences:
    """Return the object and destination an entry's payload snapshot names.

    Unwraps AS wrapper activities (Accept, Reject, Offer, Invite) until the
    innermost non-wrapper object (handles ``Accept(Offer(X))`` and
    ``Accept(Invite(X)[target=Y])`` chains).  The destination is the
    payload's own ``target``, falling back to the innermost wrapper's, so a
    nested wrapper such as an accepted invitation still names it.
    """
    raw_object = payload.get("object") or payload.get("object_")
    inner_target = None
    while (
        isinstance(raw_object, dict)
        and (raw_object.get("type") or raw_object.get("type_"))
        in WRAPPER_TYPES
    ):
        inner_target = raw_object.get("target") or inner_target
        inner = raw_object.get("object") or raw_object.get("object_")
        if not isinstance(inner, (dict, str)):
            break
        raw_object = inner
    object_ref, object_type = _ref_and_type(raw_object)
    target_ref, target_type = _ref_and_type(
        payload.get("target") or inner_target
    )
    return EntryReferences(
        object_ref=object_ref,
        object_type=object_type,
        target_ref=target_ref,
        target_type=target_type,
    )
