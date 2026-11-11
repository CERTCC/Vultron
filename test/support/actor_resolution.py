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
"""Shared test doubles for actor resolution (#6306).

- :func:`peer_profile` builds a peer's profile with no clock-read times;
- :class:`BodyFetcher` is an ``ObjectFetcher`` that answers every fetch
  with one body, for the live adapter over the real profile fetch.
"""

from __future__ import annotations

from typing import Any

from test.support.objects import make
from vultron.adapters.driven.http_object_fetch import ObjectFetchResult
from vultron.core.models.actor import VultronOrganization
from vultron.core.models.object_fetch import ObjectReference


def peer_profile(actor_id: str, **fields: Any) -> VultronOrganization:
    """*actor_id*'s profile, named ``Peer Org``, with *fields* set too."""
    return make(
        VultronOrganization,
        **{
            "id_": actor_id,
            "name": "Peer Org",
            "published": None,
            "updated": None,
            **fields,
        },
    )


class BodyFetcher:
    """An ``ObjectFetcher`` answering every fetch with one body or failure."""

    def __init__(
        self, body: dict[str, Any] | None, failure: str | None = None
    ) -> None:
        self._body = body
        self._failure = failure
        self.asked: list[tuple[ObjectReference, str]] = []

    @classmethod
    def serving(cls, profile: VultronOrganization) -> BodyFetcher:
        """A fetcher that serves *profile* as its wire JSON."""
        return cls(profile.model_dump(mode="json", by_alias=True))

    async def fetch(
        self, reference: ObjectReference, requester_id: str
    ) -> ObjectFetchResult:
        self.asked.append((reference, requester_id))
        return ObjectFetchResult(self._body, self._failure, 1)


__all__ = ["BodyFetcher", "peer_profile"]
