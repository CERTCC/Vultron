"""The display-name resolver shared by every ledger reader (CEH-01-006, DRPT-03-001).

Two tools that read the same ledger and name the same actor differently are hard
to read side by side, so the demo report and the measure layer resolve an actor
URI through this one resolver. It lives beside the ledger reader so the demo
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

from collections.abc import Iterable, Mapping
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
