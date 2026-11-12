"""Event phrases from the semantic registry, never a table of their own (DRPT-03).

Every phrase comes from ``lookup_entry(semantics).phrase`` (SE-07-001): a
second phrase table would drift as the set of semantic types grows, and the
drift would be invisible until a reader saw a stale phrase (DRPT-03-005,
CEH-01-007).  The demo report and the measure layer render a summary through
:func:`render_event_phrase`, so the two tools word one event alike.
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

from collections import defaultdict

from vultron.core.models.events.base import MessageSemantics
from vultron.semantic_registry import lookup_entry

#: What fills a slot the event record does not supply (DRPT-03-012).
MISSING_SLOT = "—"


def _humanized(semantic_type: str) -> str:
    """A semantic type no registry entry covers, as words (DRPT-03-006)."""
    return semantic_type.replace("_", " ").strip() or "performed an action"


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
        return _humanized(semantic_type)
    slots: dict[str, str] = defaultdict(lambda: MISSING_SLOT)
    return lookup_entry(semantics).phrase.format_map(slots)


def render_event_phrase(
    semantic_type: str, actor: str | None, obj: str | None
) -> str:
    """Render the registry phrase of *semantic_type* with friendly labels.

    *actor* fills ``{actor}``, and *obj* — the entry's object label, with its
    destination as ``object → destination`` — fills both ``{object}`` and
    ``{target}`` (DRPT-03-004); a slot left unfilled reads ``"—"``
    (DRPT-03-012).  A semantic type that is not a ``MessageSemantics`` value
    reads as its humanized string, never an error (DRPT-03-006).  With no
    actor, the leading dash is dropped, and the first letter is capitalized.
    """
    try:
        semantics = MessageSemantics(semantic_type)
    except ValueError:
        phrase = _humanized(semantic_type)
    else:
        slots: dict[str, str] = defaultdict(lambda: MISSING_SLOT)
        slots["actor"] = actor or MISSING_SLOT
        if obj:
            slots["object"] = obj
            slots["target"] = obj
        phrase = lookup_entry(semantics).phrase.format_map(slots)
    if (actor is None or actor == MISSING_SLOT) and phrase.startswith(
        MISSING_SLOT + " "
    ):
        phrase = phrase[2:]
    return phrase[:1].upper() + phrase[1:] if phrase else phrase
