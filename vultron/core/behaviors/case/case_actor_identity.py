#!/usr/bin/env python

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

"""The CaseActor's identity: one per container, not one per case.

A CaseActor is a *participant wearing the CASE_MANAGER hat*, not a distinct
object. Which case it is acting on is carried by ``activity.context``, not by its
URI — so its identity is the container's, and the same identity holds many cases
(#1872).

The retired model derived a per-case URI, ``.../actors/case-actor-{slug}``, from
the report or case id. That identity was a phantom: the *sender* computed it, and
nobody registered it as a hosted actor on the receiving side, so
``POST /actors/case-actor-<slug>/inbox/`` answered a permanent **404** and the
CaseProposal round-trip never started.

Provisioning could not rescue it. The slug depends on a report the receiver has
not seen, so it is not computable until the reporter's ``submit-report`` trigger
returns — by which point that trigger's own outbox drain has already delivered
the ``Offer``, the receiver has already proposed, and the 404 has already
happened. A stable identity has no such ordering problem: it comes from
configuration and can be provisioned once, at seed or startup time.

Removing the slug also moves *toward* the eventual "one CaseActor process per
case" direction rather than away from it. That is the special case of "an actor
participates in many cases" where the count is one, and such a process gets its
own first-class actor identity — not a slug suffix on somebody else's.

Spec: CP-04-002, CP-08-002. Per ADR-0041.
"""

from vultron.config import get_config

#: Final path segment of every CaseActor identity. One per container.
CASE_ACTOR_SEGMENT = "case-actor"


def case_actor_identity(base_url: str | None = None) -> str | None:
    """Return the configured CaseActor identity, or ``None`` when unconfigured.

    Args:
        base_url: Override for ``ActorConfig.case_actor_service_url``. Accepts a
            value already ending in ``/actors/case-actor`` and returns it
            unchanged, so a caller that has the identity rather than the base can
            pass it through without special-casing.

    Returns:
        ``{case_actor_service_url}/actors/case-actor``, or ``None`` when no base
        URL is configured — which callers MUST treat as a failure rather than
        substituting a default, since guessing produces exactly the
        unresolvable-identity problem this module exists to remove.
    """
    configured = base_url
    if configured is None:
        url = get_config().actor.case_actor_service_url
        configured = str(url) if url is not None else None
    if not configured:
        return None
    base = str(configured).rstrip("/")
    suffix = f"/actors/{CASE_ACTOR_SEGMENT}"
    if base.endswith(suffix):
        return base
    return f"{base}{suffix}"


def is_case_actor_identity(actor_id: str | None) -> bool:
    """True when *actor_id* names a CaseActor by the container-identity shape.

    Shape-based on purpose: it must answer for a *remote* container's CaseActor
    too, whose configuration this node cannot read.
    """
    if not actor_id:
        return False
    return actor_id.rstrip("/").endswith(f"/actors/{CASE_ACTOR_SEGMENT}")
