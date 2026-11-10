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

"""Driven port: fetch an actor's published profile.

The verification-key resolver
(:func:`vultron.core.services.verification_key.resolve_verification_key`)
fetches an author's profile through this port for every lookup: a key is
trusted only as fetched from the author's own profile URL (SIG-02-001,
SIG-02-003).  The adapter makes the HTTP
``GET`` and parses the body at the edge, so core never sees wire JSON
(ADR-0032).
"""

from typing import Protocol, runtime_checkable

from vultron.core.models.actor import CoreActor


@runtime_checkable
class ActorProfileFetchPort(Protocol):
    """Port: the profile an actor publishes, fetched from the actor itself."""

    async def fetch_profile(
        self, actor_id: str, requester_id: str
    ) -> CoreActor:
        """Fetch *actor_id*'s profile on behalf of *requester_id*.

        The request carries no proof: an actor serves its profile to anyone
        (SIG-02-002).  The returned profile is *actor_id*'s, parsed as one
        of the concrete actor types; the fetch is not stored.

        Raises:
            VultronActorProfileFetchError: The fetch failed, or the answer is
                not *actor_id*'s profile.
        """
        ...  # pragma: no cover


__all__ = ["ActorProfileFetchPort"]
