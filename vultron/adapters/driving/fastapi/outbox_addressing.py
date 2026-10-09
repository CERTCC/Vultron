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
Addressing helpers for outbox delivery.

Pure functions over the parsed sealed body (a ``dict``): which actors an
activity is addressed to (OX-08-001), and a one-line summary of its
``object`` for log messages.  Reference *dehydration* used to live here too;
it is gone, because the handler no longer rewrites anything it delivers
(VM-08-003).
"""

from typing import Any


def _format_object(obj: object) -> str:
    """Return a concise one-line summary of an AS2 object for log messages.

    Produces ``<type> <id>`` for an inline object ``dict``, passes strings
    through unchanged, and falls back to ``str(obj)`` otherwise.  Handles
    ``None`` gracefully.

    Args:
        obj: The ``object`` value of a parsed body — an inline object
             ``dict``, a URI string, or ``None``.

    Returns:
        A short, human-readable representation of the object.
    """
    if obj is None:
        return "None"
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        type_name = obj.get("type") or "object"
        obj_id = obj.get("id")
        return (
            f"{type_name} {obj_id}" if obj_id is not None else str(type_name)
        )
    return str(obj)


def _item_actor_id(item: object) -> str | None:
    if isinstance(item, str):
        return item or None
    if isinstance(item, dict):
        actor_id = item.get("id")
        if isinstance(actor_id, str) and actor_id:
            return actor_id
    return None


def _extract_recipients(body: dict[str, Any]) -> list[str]:
    """Extract deduplicated recipient actor IDs from a parsed activity body.

    Reads the ``to``, ``cc``, ``bto``, and ``bcc`` addressing fields and
    returns a list of actor ID strings in the order first encountered.

    Args:
        body: The parsed sealed body of an outbound activity.

    Returns:
        Deduplicated list of recipient actor ID strings.
    """
    seen: set[str] = set()
    recipients: list[str] = []
    for field in ("to", "cc", "bto", "bcc"):
        val = body.get(field)
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
