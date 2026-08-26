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

"""One place that answers "which store belongs to this actor?" (ADR-0073).

Under per-actor storage a store is always some actor's own, so any node that
operates on behalf of an actor other than the one whose DataLayer it was handed
has to say so explicitly (DL-07-005).  ``clone_for_actor`` is that named
operation; this module holds the guard logic around it so the answer does not
get re-derived — slightly differently each time — at every call site.

Three variants of this logic existed before: ``BTBridge._store_for_actor``,
``WritePendingReportCaseLinkNode._store_for``, and a third in the demo seeding
helpers.  They disagreed about what to do when the store is a test double and
about whether a store can be opened for an actor this node does not host.
"""

import logging
from typing import Any, TypeVar, cast
from urllib.parse import urlsplit

from vultron.core.ports.case_persistence import CasePersistence

logger = logging.getLogger(__name__)

_P = TypeVar("_P")

#: The store handed to :func:`store_for_actor`, whatever port it satisfies.
#:
#: Deliberately unbound.  The function reaches every attribute it uses through
#: ``getattr`` and returns either the store it was given or that store's own
#: ``clone_for_actor`` result, so it preserves the caller's type rather than
#: narrowing to one port.  Callers legitimately hold different ones: BT nodes a
#: :class:`~vultron.core.ports.case_persistence.CasePersistence`, the trigger
#: routes a :class:`~vultron.core.ports.datalayer.DataLayer` (which is *not* a
#: ``CasePersistence`` — it declares no ``actor_id``).  Binding to either would
#: force the other side to cast, and a cast here would assert a shape this
#: function specifically does not require: a store that reports no ``actor_id``
#: at all is a supported input, documented below and relied on by test doubles.
_S = TypeVar("_S")

#: Name of the optional rebinding method a port may expose (DL-07-009).
_REBIND = "for_store"


def same_authority(a: str, b: str) -> bool:
    """True when *a* and *b* are actor URIs served by the same node.

    Compared on scheme and netloc only.  The path prefix varies (``/api/v2``)
    without changing which process answers, and the final segment is the actor
    slug — the very thing that differs between two actors on one node.

    This is what decides whether a store can be opened for another actor at all:
    a node hosts the actors under its own authority and no others, so
    ``clone_for_actor`` on a foreign-authority id would mint an empty local
    store rather than reach the real one.
    """
    if not a or not b:
        return False
    ua, ub = urlsplit(a), urlsplit(b)
    return (ua.scheme, ua.netloc) == (ub.scheme, ub.netloc)


def store_for_actor(
    store: _S,
    actor_id: str,
    *,
    require_same_authority: bool = False,
) -> _S | None:
    """Return the store belonging to *actor_id*, or ``None`` if unreachable.

    Args:
        store: The DataLayer this caller was handed.  Returned unchanged when it
            already belongs to *actor_id*, or when it is not actor-scoped at all
            (a test double, or any implementation that reports no ``actor_id``)
            — those callers were correct before per-actor storage and stay so.
        actor_id: Canonical URI of the actor whose store is wanted.
        require_same_authority: When true, refuse to open a store for an actor
            under a different authority and return ``None`` instead.  Set this
            when the point of the write is to *publish* something the named actor
            serves — an inbox endpoint, say.  ``clone_for_actor`` succeeds for
            any well-formed id, so without this guard a remote actor's id yields
            a fresh empty local store that looks like a success and publishes
            nothing (#2484).

    Returns:
        The store to use, or ``None`` when *actor_id* is not hosted here and
        *require_same_authority* is set.
    """
    if not actor_id:
        return store
    own_actor_id = getattr(store, "actor_id", None)
    if not isinstance(own_actor_id, str) or not own_actor_id:
        return store
    if own_actor_id == actor_id:
        return store
    if require_same_authority and not same_authority(own_actor_id, actor_id):
        logger.debug(
            "Actor '%s' is not hosted alongside '%s'; no local store for it",
            actor_id,
            own_actor_id,
        )
        return None
    clone_for_actor = getattr(store, "clone_for_actor", None)
    if not callable(clone_for_actor):
        return store
    # An actor id is a public identifier, not a credential: it is the URL
    # outbound delivery POSTs an inbox to, and it appears in every AS2 activity
    # on the wire.  CodeQL classifies it as a secret because one of the fields
    # it can be read from is named
    # `VultronReportCaseLink.trusted_case_actor_id`, and the heuristic keys on
    # "trust" in the name rather than on the value.  Suppressed rather than
    # renamed: the field name states the bootstrap-trust relation CBT-01-005
    # and CBT-01-006 define.
    logger.debug(
        "Scoping DataLayer from actor '%s' to actor '%s'",
        own_actor_id,
        actor_id,  # codeql[py/clear-text-logging-sensitive-data]
    )
    # `clone_for_actor` came from getattr, so it is untyped. The cast is safe
    # because every port that declares the method declares it as returning that
    # same port (`CasePersistence.clone_for_actor -> CasePersistence`,
    # `DataLayer.clone_for_actor -> DataLayer`); the getattr exists only so that
    # test doubles and any non-actor-scoped implementation fall through the
    # guards above untouched.
    return cast(_S, clone_for_actor(actor_id))


def port_for_store(port: _P, store: CasePersistence) -> _P:
    """Return *port* rebound to *store*, or *port* unchanged.

    :func:`store_for_actor` answers "which store belongs to this actor?", but a
    store is not the only thing that holds one.  A driven adapter handed to a BT
    — ``TriggerActivityPort``, ``SyncActivityPort`` — keeps its *own* reference
    to the DataLayer it was constructed with, and that adapter is the code that
    actually persists the outbound activity.  Reconciling only the blackboard's
    ``datalayer`` therefore fixes half of a two-halved write: the activity is
    created through the port, in the requesting actor's store, while
    ``outbox_append()`` goes through the reconciled store, into the executing
    actor's outbox.  The queue entry then names an activity its own store does
    not hold, delivery logs "not found ... skipping delivery", and the
    invitation is silently never sent (ISSUE-2548, DL-07-009).

    Rebinding is *opt-in* by design.  A port participates by defining a
    ``for_store(store)`` method that returns an equivalent port reading and
    writing *store*; anything else is returned untouched, because a port with no
    DataLayer of its own has nothing to reconcile and a stateless one must not be
    replaced behind its caller's back.

    The lookup is deliberately on ``type(port)`` rather than the instance.  A
    bare ``Mock()`` answers *any* attribute with another callable ``Mock``, so an
    instance-level ``getattr`` would "rebind" every test double to a Mock return
    value and quietly break assertions made against the original.  Classes do not
    synthesise attributes, so asking the class is what keeps test doubles out.

    Args:
        port: The port to rebind.  May be ``None``.
        store: The store the port should read and write.

    Returns:
        The rebound port, or *port* itself when it does not opt in.
    """
    if port is None:
        return port
    rebind = getattr(type(port), _REBIND, None)
    if not callable(rebind):
        return port
    rebound: Any = rebind(port, store)
    logger.debug(
        "Rebound %s to the store of actor '%s'",
        type(port).__name__,
        getattr(store, "actor_id", "<unscoped>"),
    )
    return cast(_P, rebound)
