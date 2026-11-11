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
"""The two adapters of :class:`~vultron.core.ports.actor_resolution.ActorResolutionPort`.

Give either one a peer's id and it returns the peer's profile:

- :class:`StaticActorResolutionAdapter` returns a profile declared up front,
  for demos and tests.  It retrieves nothing; an id it holds no profile for
  answers ``None``, which the call-out reads as *no*.
- :class:`HttpActorResolutionAdapter` retrieves the profile with a ``GET``
  of the actor URL, through the
  :class:`~vultron.core.ports.actor_profile_fetch.ActorProfileFetchPort`
  the verification-key resolver uses
  (:class:`~vultron.adapters.driven.http_actor_profile_fetch.HttpActorProfileFetchAdapter`),
  which refuses a URL it may not fetch and validates the body as that
  actor's profile, at the edge (ADR-0032).

**The async-to-sync seam.**  The profile fetch is a coroutine, and a call-out
answers synchronously, in one tick, within the actor's call-out time budget
(BT-18-011, BT-18-015).  The live adapter therefore runs the fetch to
completion on its own event loop, in a daemon worker thread, and waits at
most :data:`BUDGET_SHARE` of the budget for it, leaving the rest to the seam,
so a slow peer is the adapter's *error* rather than a budget overrun.  A
worker thread works whether or not the ticking thread already runs an event
loop, which ``asyncio.run`` on the ticking thread would not.  The default
fetcher makes one attempt, bounded by the same wait, so the worker ends soon
after a late answer is given up on: resolution enriches a record, so a slow
peer is not retried here (AKM-05-001, AKM-05-008).

A fetched profile's ``inbox`` and ``outbox`` must meet the rule a profile
URL meets, since a stored peer's inbox is where delivery posts.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Iterable
from datetime import timedelta

from vultron.adapters.driven.http_actor_profile_fetch import (
    MAX_VERIFICATION_PROFILE_BYTES,
    HttpActorProfileFetchAdapter,
    check_profile_fetch_target,
)
from vultron.adapters.driven.http_object_fetch import HttpObjectFetcher
from vultron.config.app import load_actor_config
from vultron.core.models.actor import CoreActor
from vultron.core.ports.actor_profile_fetch import ActorProfileFetchPort
from vultron.errors import VultronActorProfileFetchError


class StaticActorResolutionAdapter:
    """:class:`ActorResolutionPort` over profiles declared up front.

    Args:
        profiles: The profiles it holds, each under its own id.

    Raises:
        ValueError: Two profiles share an id.
    """

    def __init__(self, profiles: Iterable[CoreActor]) -> None:
        held: dict[str, CoreActor] = {}
        for profile in profiles:
            if profile.id_ in held:
                raise ValueError(
                    f"two static profiles are declared for {profile.id_!r};"
                    " an id has one profile"
                )
            held[profile.id_] = profile
        self._profiles = held

    def resolve_actor(
        self, actor_id: str, requester_id: str
    ) -> CoreActor | None:
        """Return a copy of the profile declared for *actor_id*, or ``None``.

        *requester_id* is not read: a static profile is the same for every
        requester.  The copy keeps the declared profile unchanged by a
        caller that edits the record it is given.
        """
        profile = self._profiles.get(actor_id)
        return None if profile is None else profile.model_copy(deep=True)


#: The share of the call-out time budget the live adapter waits by default.
#: Waiting the whole budget would give up just after the seam's own
#: stopwatch ran out, so a slow peer would surface as an overrun instead of
#: as the adapter's *error* (BT-18-027); the rest of the budget is the
#: seam's, to take the answer.
BUDGET_SHARE: float = 0.8


def resolution_profile_fetcher(
    wait: timedelta,
) -> HttpActorProfileFetchAdapter:
    """The profile fetcher a live resolution uses within *wait*.

    One attempt, its timeout *wait*, and a body cap
    (``MAX_VERIFICATION_PROFILE_BYTES``): a profile is a few hundred bytes,
    and a peer's server must not stream an unbounded body into memory.
    """
    return HttpActorProfileFetchAdapter(
        HttpObjectFetcher(
            max_attempts=1,
            timeout=wait.total_seconds(),
            max_body_bytes=MAX_VERIFICATION_PROFILE_BYTES,
        )
    )


def _check_endpoints(profile: CoreActor) -> None:
    """Refuse a profile whose ``inbox`` or ``outbox`` is not a fetchable URL.

    A stored peer's inbox is where outbound delivery posts, so a peer's
    server could otherwise point this actor's deliveries at a non-public
    address.  The rule is the one a profile URL meets
    (:func:`check_profile_fetch_target`).

    Raises:
        VultronActorProfileFetchError: An endpoint breaks that rule.
    """
    for name, endpoint in (
        ("inbox", profile.inbox),
        ("outbox", profile.outbox),
    ):
        if endpoint is None:
            continue
        try:
            check_profile_fetch_target(endpoint)
        except VultronActorProfileFetchError as exc:
            raise VultronActorProfileFetchError(
                f"the profile of {profile.id_!r} names an {name} this actor"
                f" does not deliver to: {exc}"
            ) from exc


class HttpActorResolutionAdapter:
    """:class:`ActorResolutionPort` that fetches the peer's profile live.

    Args:
        fetcher: The profile fetcher; defaults to
            :func:`resolution_profile_fetcher` over the wait.
        budget: How long a resolution may take; defaults to
            :data:`BUDGET_SHARE` of the local actor's
            ``call_out_time_budget`` (BT-18-026), read when the adapter is
            built.
    """

    def __init__(
        self,
        fetcher: ActorProfileFetchPort | None = None,
        *,
        budget: timedelta | None = None,
    ) -> None:
        self._budget = (
            budget
            if budget is not None
            else load_actor_config().call_out_time_budget * BUDGET_SHARE
        )
        if self._budget <= timedelta(0):
            raise ValueError(
                f"resolution budget {self._budget} must be positive"
                " (BT-18-015)"
            )
        self._fetcher = (
            fetcher
            if fetcher is not None
            else resolution_profile_fetcher(self._budget)
        )

    def resolve_actor(self, actor_id: str, requester_id: str) -> CoreActor:
        """Fetch *actor_id*'s profile on behalf of *requester_id*.

        Never returns ``None``: a live source either has the profile or
        could not be asked.  The fetch runs on its own event loop in a
        daemon thread, so a fetch that outlives the wait never holds up
        the interpreter's exit.

        Raises:
            VultronActorProfileFetchError: The fetch failed, its answer is
                not *actor_id*'s profile, the profile names an endpoint this
                actor does not deliver to, or the fetch took longer than the
                budget.
        """
        outcome: dict[str, CoreActor | Exception] = {}

        def _fetch() -> None:
            try:
                outcome["profile"] = asyncio.run(
                    self._fetcher.fetch_profile(actor_id, requester_id)
                )
            except Exception as exc:  # noqa: BLE001 (re-raised by the caller)
                outcome["raised"] = exc

        worker = threading.Thread(
            target=_fetch, name="actor-resolution", daemon=True
        )
        worker.start()
        worker.join(timeout=self._budget.total_seconds())
        if worker.is_alive():
            raise VultronActorProfileFetchError(
                f"fetching the profile of {actor_id!r} took longer than"
                f" the resolution budget of {self._budget}"
            )
        raised = outcome.get("raised")
        if isinstance(raised, Exception):
            raise raised
        profile = outcome["profile"]
        if not isinstance(profile, CoreActor):
            raise VultronActorProfileFetchError(
                f"the fetch of {actor_id!r} gave no actor profile"
            )
        _check_endpoints(profile)
        return profile


__all__ = [
    "BUDGET_SHARE",
    "HttpActorResolutionAdapter",
    "StaticActorResolutionAdapter",
    "resolution_profile_fetcher",
]
