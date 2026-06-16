#!/usr/bin/env python

#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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
"""
Addressing and reference-dehydration helpers for outbox delivery.

Provides pure functions for extracting recipient actor IDs from AS2 activities
and collapsing domain-object dicts in reference fields to URI strings before
wire serialisation (MV-10-001, OX-08-001).
"""

# Reference fields that must be collapsed to URI strings before validating as
# VultronActivity.  ``object`` is intentionally excluded — it must remain a
# full inline typed object so recipients can determine the semantic type
# (MV-09-001).
#
# ``target`` is also partially excluded: minimal stub dicts
# ``{id, type[, summary]}`` are preserved so that ``Invite.target`` carries
# the case type to the recipient (MV-10-001).
_DEHYDRATION_FIELDS: frozenset[str] = frozenset(
    {
        "actor",
        "target",
        "to",
        "cc",
        "bto",
        "bcc",
        "origin",
        "result",
        "instrument",
    }
)

# Keys permitted in a stub dict (MV-10-001).  Any other key causes full
# dehydration to a bare URI so that only intentional stubs are preserved.
_STUB_KEYS: frozenset[str] = frozenset({"id", "type", "summary", "@context"})

# AS2 object types that are intentional stubs and must be preserved in-line
# rather than collapsed to a bare URI string.
_STUB_OBJECT_TYPES: frozenset[str] = frozenset({"VulnerabilityCase"})


def _is_stub_object_dict(value: dict[object, object]) -> bool:
    """Return True when ``value`` is an intentional selective-disclosure stub."""
    return (
        value.get("type") in _STUB_OBJECT_TYPES and value.keys() <= _STUB_KEYS
    )


def _coerce_reference_value(value: object) -> object:
    """Collapse reference dicts to URI strings unless they are stubs."""
    if not isinstance(value, dict):
        return value
    if _is_stub_object_dict(value):
        return value
    # Prefer href (AS2 Link) then id (any AS2 object)
    uri = value.get("href") or value.get("id")
    return uri if uri is not None else value


def _dehydrate_references(activity_dict: dict) -> dict:
    """Collapse domain-object dicts in reference fields to URI strings.

    Adapts a raw ``model_dump(by_alias=True)`` dict for ``VultronActivity``
    validation.  Wire-layer AS2 activities may carry full domain objects
    (e.g. ``VulnerabilityCase``) in reference fields such as ``target``.
    ``VultronActivity`` expects those fields to be URI strings, so this
    function collapses any dict with ``"href"`` or ``"id"`` to the
    corresponding URI string.  List fields are handled element-wise.

    ``"object"`` is explicitly excluded from dehydration because outbound
    initiating activities must carry a fully inline typed object for semantic
    routing on the receiving side (MV-09-001).

    Args:
        activity_dict: Raw ``dict`` produced by ``model_dump(by_alias=True)``
            on a typed AS2 activity model.

    Returns:
        A new ``dict`` with reference fields collapsed to URI strings where
        possible.
    """
    result = dict(activity_dict)
    for field in _DEHYDRATION_FIELDS:
        value = result.get(field)
        if value is None:
            continue
        if isinstance(value, list):
            result[field] = [_coerce_reference_value(item) for item in value]
        else:
            result[field] = _coerce_reference_value(value)
    return result


def _format_object(obj: object) -> str:
    """Return a concise one-line summary of an AS2 object for log messages.

    Produces ``<ClassName> <id>`` for Pydantic-like domain objects, passes
    strings through unchanged, and falls back to ``str(obj)`` otherwise.
    Handles ``None`` gracefully.

    Args:
        obj: The object to format — may be a domain model, a URI string, or
             ``None``.

    Returns:
        A short, human-readable representation of the object.
    """
    if obj is None:
        return "None"
    if isinstance(obj, str):
        return obj
    type_name = type(obj).__name__
    obj_id = getattr(obj, "id_", None)
    if obj_id is not None:
        return f"{type_name} {obj_id}"
    return type_name


def _extract_recipients(activity) -> list[str]:
    """Extract deduplicated recipient actor IDs from an AS2 activity.

    Reads the ``to``, ``cc``, ``bto``, and ``bcc`` addressing fields and
    returns a list of actor ID strings in the order first encountered.

    Args:
        activity: An AS2 activity with to/cc/bto/bcc attributes.

    Returns:
        Deduplicated list of recipient actor ID strings.
    """

    def _item_actor_id(item: object) -> str | None:
        if isinstance(item, str):
            return item
        if hasattr(item, "id_"):
            actor_id = getattr(item, "id_", None)
            if isinstance(actor_id, str):
                return actor_id
        return None

    seen: set[str] = set()
    recipients: list[str] = []
    for field in ("to", "cc", "bto", "bcc"):
        val = getattr(activity, field, None)
        if val is None:
            continue
        items = val if isinstance(val, list) else [val]
        for item in items:
            actor_id = _item_actor_id(item)
            if actor_id is None:
                continue
            if actor_id not in seen:
                seen.add(actor_id)
                recipients.append(actor_id)
    return recipients
