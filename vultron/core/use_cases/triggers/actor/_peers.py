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

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.call_out.bundles.actor_discovery import (
    ACTOR_DISCOVERY_DETERMINISTIC,
    ActorDiscoveryCallOutBundle,
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
    call_out: ActorDiscoveryCallOutBundle = ACTOR_DISCOVERY_DETERMINISTIC,
) -> None:
    """Record *actor_id* as a peer this actor now knows, if not already known.

    Being named by URI is enough: a peer's record lives in the store of
    whichever actor knows it (ADR-0073#peer-records-in-knowers-store), and in a real deployment the
    peer is on another node whose record will never be here.  Refusing with
    "Actor '…' not found" therefore refused every cross-node peer — which is
    what made ``suggest-actor-to-case`` answer 404 for a vendor that existed and
    was reachable, just not locally recorded (#2548, rcvcv).

    Recording it is the honest Actor Knowledge Model move: this actor has now
    been told about that peer, so it legitimately knows it.  What it does not
    have is the peer's details; the Retriever call-out in *call_out* is the
    injectable seam for a real directory service (ADR-0024, ADR-0025).

    Minting from an unvalidated string would accept anything, though, so the id
    has to be a deliverable URI first: it *is* the address outbound delivery
    posts to, and a typo'd or relative id becomes an unreachable participant
    that fails much later, in the delivery retry loop, with no trace back here.

    Args:
        dl: The acting actor's own DataLayer.
        actor_id: The peer's canonical URI, as named by the request.
        field: Name of the request field it came from, for the messages.
        acting_actor_id: The acting actor; the backend's tree runs as it.
        call_out: Actor-discovery call-out bundle; defaults to
            :data:`ACTOR_DISCOVERY_DETERMINISTIC` (``AlwaysSucceed``).
            Inject a directory-service backend to resolve actor details.
    """
    if dl.read(actor_id) is not None:
        return
    _require_deliverable_actor_uri(actor_id, field)
    backend = call_out.resolve_actor_factory("ResolveActorDetails")
    # Run the node through a BTBridge so py_trees setup() and initialise() run
    # and the backend's ports (datalayer, actor_id) are wired (#2707); the
    # bundle hands out a SynchronousCallOut guard wrapper (BT-18-011) that
    # needs its child ticked.
    #
    # A backend that returns RUNNING violates the synchronous-answer contract
    # and the guard rejects it by raising (BT-18-011).  The bridge reports that
    # as a non-SUCCESS result, and this function's contract is to record a
    # minimal peer whenever details cannot be resolved, so it degrades the same
    # as any other non-SUCCESS rather than crashing the request.  The offending
    # backend is still surfaced, via the WARNING.
    result = BTBridge(datalayer=dl).execute_with_setup(
        backend, actor_id=acting_actor_id, max_iterations=1
    )
    status = result.status
    reason = status.name
    if result.feedback_message and status != Status.SUCCESS:
        reason = f"{reason} ({result.feedback_message})"
    if status != Status.SUCCESS:
        logger.warning(
            "actor discovery returned %s for %s '%s' — recording minimal peer"
            " (only URI known, not details)",
            reason,
            field,
            actor_id,
        )
    else:
        logger.debug(
            "actor discovery succeeded for %s '%s' — recording peer",
            field,
            actor_id,
        )
    # Only the URI is known: no clock time and no endpoint derived from the
    # id, since the peer stated neither (AKM-02-006, ADR-0159).
    dl.create(CoreActor(id_=actor_id, published=None, updated=None))
