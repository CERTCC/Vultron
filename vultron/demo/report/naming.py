"""Friendly labels and event phrases for the demo report (DRPT-03).

The tolerant field access and the display-name resolver this module once held
live in :mod:`vultron.measure.ledger`, the one ledger reader the report tool and
the measure layer share (``notes/case-event-history.md``).
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
from vultron.measure.ledger import friendly_actor_name
from vultron.semantic_registry import lookup_entry

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
