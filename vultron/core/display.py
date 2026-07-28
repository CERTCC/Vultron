"""Display helpers for human-readable rendering of domain objects (DRPT-03)."""

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

from vultron.core.models.base import VultronBase


def friendly_name(obj: VultronBase | str | None) -> str:
    """Return a short, friendly display name for a domain object or URI.

    Resolution order:

    1. ``obj.name`` — explicit human-readable name on the object.
    2. URI path-segment heuristic — last non-empty segment of ``obj.id_``
       (or the string itself when *obj* is already a ``str``); UUID-like
       hex tokens (6+ all-hex characters) are stripped so a URI like
       ``…/actors/case-actor-a1b2c3`` collapses to ``"Case Actor"``.
    3. ``"—"`` — returned when *obj* is ``None`` or no usable segment exists.

    Args:
        obj: A ``VultronBase`` domain object, a plain URI string, or ``None``.

    Returns:
        A short, human-readable label.
    """
    if obj is None:
        return "—"

    if isinstance(obj, VultronBase):
        if obj.name:
            return obj.name
        uri: str | None = getattr(obj, "id_", None)
    else:
        uri = str(obj) if obj else None

    if not uri:
        return "—"

    segment = uri.rstrip("/").rsplit("/", 1)[-1]
    label = _titleize_segment(segment)
    return label or "—"


def _looks_like_hex_token(token: str) -> bool:
    """Return True for a pure-hex token of length >= 6 (a likely UUID chunk)."""
    return len(token) >= 6 and all(
        c in "0123456789abcdef" for c in token.lower()
    )


def _titleize_segment(segment: str) -> str:
    """Convert a URI/directory segment to a friendly title-case label.

    Splits on ``-`` and ``_``, drops UUID-like hex tokens, and capitalises the
    remaining words.  Returns an empty string if no non-hex words remain.
    """
    raw = segment.replace("_", " ").replace("-", " ").split()
    words = [w for w in raw if not _looks_like_hex_token(w)]
    if not words:
        words = raw
    return " ".join(w.capitalize() for w in words)
