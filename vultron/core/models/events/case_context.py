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

"""Case-context resolution for inbound activities.

Single authoritative answer to two questions the inbox path asks of every
inbound activity:

1. *Which case does this activity belong to?* — :func:`resolve_case_context_id`
2. *Is this activity the one that bootstraps that case locally?* —
   :func:`is_case_bootstrap`

Both the core behavior-tree inbox pipeline
(``vultron.core.behaviors.inbox.nodes.pipeline``) and the FastAPI inbox
adapters delegate here, so the deferral gate and the replay trigger cannot
drift apart.

Why ``object_id`` wins for bootstrap activities
-----------------------------------------------

A bootstrap activity carries the ``VulnerabilityCase`` inline as its
``object_``, which makes ``event.object_id`` the authoritative case
identifier: it is derived from the case snapshot itself and cannot disagree
with it.

Per CP-05-003 and ADR-0045, ``Create(VulnerabilityCase)`` now sets
``context`` to the case URI (not the Accept URI), so the deferral guard works
correctly for this activity even without the bootstrap exemption.  The
bootstrap exemption is retained for correctness under any ordering of replica
seeding: the inline case object is always authoritative, regardless of what
``context`` contains.
"""

from vultron.core.models.events.base import MessageSemantics, VultronEvent

#: Semantics whose activity carries a full ``VulnerabilityCase`` inline and
#: therefore establishes the local case replica rather than presupposing it.
#: These are never deferred, and each one triggers replay of activities that
#: were deferred pending the case.
CASE_BOOTSTRAP_SEMANTICS: frozenset[MessageSemantics] = frozenset(
    {
        MessageSemantics.ANNOUNCE_VULNERABILITY_CASE,
        MessageSemantics.CREATE_CASE,
    }
)

#: AS2 ``@context`` values live under the W3C namespace and are never case IDs.
_AS2_NAMESPACE_PREFIX = "https://www.w3.org/ns/"


def is_case_bootstrap(event: VultronEvent) -> bool:
    """Return ``True`` when *event* establishes a local case replica."""
    return event.semantic_type in CASE_BOOTSTRAP_SEMANTICS


def resolve_case_context_id(
    event: VultronEvent,
    wire_context: object = None,
) -> str | None:
    """Resolve the case ID that *event* is scoped to, or ``None``.

    Args:
        event: The extracted domain event.
        wire_context: The raw AS2 ``context`` value from the wire activity,
            when the caller has access to it.  Accepts a string URI, an object
            exposing ``id_``, or ``None``.  Used only as a fallback for
            non-bootstrap activities whose event-level ``context`` did not
            rehydrate into a domain object.

    For bootstrap semantics (:data:`CASE_BOOTSTRAP_SEMANTICS`) the inline case
    object wins; see the module docstring for why.
    """
    if is_case_bootstrap(event):
        object_id = event.object_id
        if object_id:
            return object_id

    if event.context_id is not None:
        return event.context_id

    return _wire_context_id(wire_context)


def _wire_context_id(wire_context: object) -> str | None:
    """Extract a case ID from a raw AS2 ``context`` value."""
    if isinstance(wire_context, str):
        if wire_context and not wire_context.startswith(_AS2_NAMESPACE_PREFIX):
            return wire_context
        return None
    if wire_context is None:
        return None
    candidate = getattr(wire_context, "id_", None)
    return candidate if isinstance(candidate, str) and candidate else None
