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


"""Record a peer a trigger names, so the actor can deliver to it later.

Shared by the recommendation and ownership-transfer triggers.
No HTTP framework imports permitted here.
"""

import logging
from typing import Any
from urllib.parse import urlparse

from py_trees.common import Status

from vultron.core.behaviors.actor_resolution_tree import (
    create_actor_resolution_tree,
)
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.call_out.bundles.actor_resolution import (
    ACTOR_RESOLUTION_DETERMINISTIC,
    ActorResolutionCallOutBundle,
)
from vultron.core.behaviors.call_out.capabilities.actor_resolution import (
    RESOLVED_ACTOR_KEY,
)
from vultron.core.models.actor import CoreActor
from vultron.errors import (
    VultronValidationError,
)

logger = logging.getLogger(__name__)


def _require_deliverable_actor_uri(actor_id: str, field: str) -> None:
    """Raise ``VultronValidationError`` unless *actor_id* is a deliverable URI.

    A peer actor id is not an opaque name — it is the URL outbound delivery
    POSTs its inbox to.  Only an absolute ``http``/``https`` URI with a netloc
    can be that, so anything else is rejected here rather than minted into a
    participant that no delivery attempt can ever reach.

    Args:
        actor_id: The candidate peer actor URI.
        field: Name of the request field it came from, for the message.
    """
    parsed = urlparse(actor_id)
    if parsed.scheme in ("http", "https") and parsed.netloc:
        return
    raise VultronValidationError(
        f"{field} '{actor_id}' is not a deliverable actor URI: a named peer"
        " must be an absolute http(s) URI, because that URI is where the"
        " message about it is delivered"
    )


def _record_named_peer(
    dl: Any,
    actor_id: str,
    field: str,
    acting_actor_id: str,
    call_out: ActorResolutionCallOutBundle = ACTOR_RESOLUTION_DETERMINISTIC,
) -> None:
    """Record *actor_id* as a peer this actor now knows, if not already known.

    Being named by URI is enough: a peer's record lives in the store of
    whichever actor knows it (ADR-0073#peer-records-in-knowers-store), and in a real deployment the
    peer is on another node whose record will never be here.  Refusing with
    "Actor '…' not found" therefore refused every cross-node peer — which is
    what made ``suggest-actor-to-case`` answer 404 for a vendor that existed and
    was reachable, just not locally recorded (#2548, rcvcv).

    Recording it is the honest Actor Knowledge Model move: this actor has now
    been told about that peer, so it legitimately knows it.  What it may
    lack is the peer's details, which the ResolveActorDetails Retriever in
    *call_out* supplies when a source is wired (AKM-05-002, ADR-0024,
    ADR-0025).

    The fact this function needs is whether this actor already knows the
    peer, and the actor's own store holds that, so the store is read first: a
    peer already recorded there is not looked up again (BT-18-039).  A
    second lookup would spend call-out budget on a peer the actor already
    knows.  Whatever is recorded, the peer is then held, so a peer recorded
    after a failed lookup is not looked up again either.

    Minting from an unvalidated string would accept anything, though, so the id
    has to be a deliverable URI first: it *is* the address outbound delivery
    posts to, and a typo'd or relative id becomes an unreachable participant
    that fails much later, in the delivery retry loop, with no trace back here.

    What is recorded:

    - on *yes* with a record whose id is *actor_id*, that record, as the
      source states it;
    - otherwise the minimal record, the URI alone (AKM-05-001).  That covers
      *no*, *error*, a raise, a ``RUNNING`` return, a *yes* without a record
      and a *yes* whose record names another actor, such as the
      DETERMINISTIC default's placeholder.  A record of another actor is
      never stored under the peer's id, and the minimal record holds no
      value nobody asserted (AKM-02-006, ADR-0159).

    The discovery backend runs in a one-tick ``BTBridge`` tree
    (:func:`~vultron.core.behaviors.actor_resolution_tree.create_actor_resolution_tree`),
    acting as *acting_actor_id*, so its ports are wired before ``update()``
    (#2707).  A backend that fails, returns RUNNING, or raises still ends in
    a minimal peer: discovery never blocks the request.  A raise, RUNNING
    included, is an internal error the bridge logs at ERROR with its
    traceback, before this function's WARNING.

    Args:
        dl: The acting actor's own DataLayer.
        actor_id: The peer's canonical URI, as named by the request.
        field: Name of the request field it came from, for the messages.
        acting_actor_id: The acting actor; the backend's tree runs as it.
        call_out: Actor-resolution call-out bundle; defaults to
            :data:`ACTOR_RESOLUTION_DETERMINISTIC`.  Build one over an
            :class:`~vultron.core.ports.actor_resolution.ActorResolutionPort`
            with
            :func:`~vultron.core.behaviors.call_out.bundles.actor_resolution.actor_resolution_bundle`
            to resolve actor details.
    """
    if dl.read(actor_id) is not None:
        return
    _require_deliverable_actor_uri(actor_id, field)
    kept: dict[str, CoreActor] = {}
    tree = create_actor_resolution_tree(call_out.resolve_actor_factory, kept)
    # Run the tree through a BTBridge so py_trees setup() and initialise() run
    # and the backend's ports (datalayer, actor_id) are wired (#2707); the
    # bundle hands out a SynchronousCallOut guard wrapper (BT-18-011) that
    # needs its child ticked.  The peer's URI goes on the backend's input
    # port, and the output port is cleared for the run, so a record an
    # earlier run left there is never kept.
    #
    # A backend that returns RUNNING violates the synchronous-answer contract
    # and the guard rejects it by raising (BT-18-011).  The bridge never
    # raises: it catches that, or any other exception from the backend, logs
    # it at ERROR with the traceback as an internal error, and reports
    # FAILURE.  This function's contract is to record a minimal peer whenever
    # details cannot be resolved, so it degrades the same as any other
    # non-SUCCESS rather than crashing the request; the WARNING below carries
    # the bridge's message, so the offending backend is named there too.
    # The two keywords are the capability's PEER_ACTOR_ID_KEY and
    # RESOLVED_ACTOR_KEY; the resolution tests fail if they drift apart.
    result = BTBridge(datalayer=dl).execute_with_setup(
        tree,
        actor_id=acting_actor_id,
        max_iterations=1,
        peer_actor_id=actor_id,
        resolved_actor=None,
    )
    status = result.status
    record = kept.get(RESOLVED_ACTOR_KEY)
    if status != Status.SUCCESS:
        reason = status.name
        if result.feedback_message:
            reason = f"{reason} ({result.feedback_message})"
        logger.warning(
            "actor resolution returned %s for %s '%s' — recording minimal peer"
            " (only URI known, not details)",
            reason,
            field,
            actor_id,
        )
        record = None
    elif record is None or record.id_ != actor_id:
        # INFO, not WARNING: the DETERMINISTIC default answers so on every
        # unknown peer, as does any backend with nothing to add.
        logger.info(
            "actor resolution answered no record of %s '%s' (%s) — recording"
            " minimal peer (only URI known, not details)",
            field,
            actor_id,
            "none given" if record is None else f"record of '{record.id_}'",
        )
        record = None
    else:
        logger.debug(
            "actor resolution resolved %s '%s' — recording its record",
            field,
            actor_id,
        )
    if record is None:
        # Only the URI is known: no clock time and no endpoint derived from
        # the id, since the peer stated neither (AKM-02-006, ADR-0159).
        record = CoreActor(id_=actor_id, published=None, updated=None)
    dl.create(record)
