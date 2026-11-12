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

"""Driven port: the actor record of a peer, given the peer's id.

The actor-resolution call-out
(:class:`~vultron.core.behaviors.call_out.capabilities.actor_resolution.ResolveActorDetailsCapability`)
answers through this port when an actor is named a peer it holds no record
of (AKM-05-002).  Two adapters implement it, in
:mod:`vultron.adapters.driven.actor_resolution`: a static one that returns a
profile declared up front, and a live one that fetches the peer's profile
over HTTP and validates it.

A call-out answers synchronously, within one tick and the call-out time
budget (BT-18-011, BT-18-015), so the port is synchronous: an adapter that
does I/O bounds it and returns, and never hands core a coroutine.
"""

from typing import Protocol, runtime_checkable

from vultron.core.models.actor import CoreActor


@runtime_checkable
class ActorResolutionPort(Protocol):
    """Port: the actor record a source holds for a peer's id."""

    def resolve_actor(
        self, actor_id: str, requester_id: str
    ) -> CoreActor | None:
        """Return *actor_id*'s record, looked up on behalf of *requester_id*.

        Returns:
            The record, as the source holds it, or ``None`` when the source
            holds no record for *actor_id*.  ``None`` is the source's
            answer, not a failure.

        Raises:
            VultronActorProfileFetchError: The source could not be asked, or
                its answer is not *actor_id*'s profile.
        """
        ...  # pragma: no cover


__all__ = ["ActorResolutionPort"]
