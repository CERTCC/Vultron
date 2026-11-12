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
"""Core capability declaration for ``actor_resolution``.

The class declares one named capability's blackboard contract as typed
ports (BT-18-012).  Its simulation node, in
``vultron.demo.fuzzer.actor_resolution``, subclasses the declaration rather
than restating it (BT-18-021).

Actor resolution is the known-id lookup: a request names a peer by URI and
the actor holds no record of it.  It is distinct from asking who else
belongs in a case, which names no peer to look up.
"""

from __future__ import annotations

from typing import Final

from py_trees.ports import PortInformation

from vultron.core.behaviors.call_out.capability import RetrieverCapability
from vultron.core.models.actor import CoreActor

#: Blackboard key of the peer URI the capability resolves.
PEER_ACTOR_ID_KEY: Final[str] = "peer_actor_id"

#: Blackboard key of the acting actor, on whose behalf it resolves.  BTBridge
#: writes it for every tree it runs.
REQUESTER_ACTOR_ID_KEY: Final[str] = "actor_id"

#: Blackboard key the resolved actor record is written to on *yes*.
RESOLVED_ACTOR_KEY: Final[str] = "resolved_actor"


class ResolveActorDetailsCapability(RetrieverCapability):
    """Return the actor record of a peer this actor knows only by its URI.

    Blackboard contract (BT-18-001):
      Input keys:  peer_actor_id: str  (the peer's URI, as a request named it)
                   actor_id: str  (the acting actor, written by BTBridge)
      Output keys: resolved_actor: CoreActor  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)

    *Yes* carries the peer's own record, as its profile states it.  *No*
    means the source holds no record for that peer; *error* means the source
    could not be asked.  The caller records only a record whose id is the
    peer's, and otherwise the peer's URI alone, so resolution never blocks
    the request (AKM-05-001, AKM-02-006).

    Store-held answer (BT-18-039): **can** — the actor's own store holds the
    record of every peer it knows, so the caller reads the store first and
    does not ask for a peer it already holds.
    """

    INPUT_PORTS = {
        PEER_ACTOR_ID_KEY: PortInformation(data_type=str, required=True),
        REQUESTER_ACTOR_ID_KEY: PortInformation(data_type=str, required=True),
    }
    OUTPUT_PORTS = {
        RESOLVED_ACTOR_KEY: PortInformation(
            data_type=CoreActor, required=True
        ),
    }


__all__ = [
    "PEER_ACTOR_ID_KEY",
    "REQUESTER_ACTOR_ID_KEY",
    "RESOLVED_ACTOR_KEY",
    "ResolveActorDetailsCapability",
]
