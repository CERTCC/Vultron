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
"""The static and live adapters of ``ActorResolutionPort`` (#6306, AKM-05-002)."""

import asyncio
import threading
from datetime import timedelta

import pytest

from test.support.objects import make
from vultron.adapters.driven.actor_resolution import (
    HttpActorResolutionAdapter,
    StaticActorResolutionAdapter,
    resolution_profile_fetcher,
)
from vultron.adapters.driven.http_actor_profile_fetch import (
    MAX_VERIFICATION_PROFILE_BYTES,
    HttpActorProfileFetchAdapter,
)
from vultron.adapters.driven.http_object_fetch import ObjectFetchResult
from vultron.core.models.actor import CoreActor, VultronOrganization
from vultron.core.models.object_fetch import ObjectReference
from vultron.core.ports.actor_resolution import ActorResolutionPort
from vultron.errors import VultronActorProfileFetchError

PEER = "https://peer.example/api/v2/actors/peer"
REQUESTER = "https://acting.example/api/v2/actors/acting"


def _profile(actor_id: str = PEER) -> VultronOrganization:
    return make(VultronOrganization, id_=actor_id, name="Peer Org")


class _BodyFetcher:
    """An ``ObjectFetcher`` answering every fetch with one body."""

    def __init__(self, body: dict | None, failure: str | None = None) -> None:
        self._body = body
        self._failure = failure
        self.asked: list[tuple[ObjectReference, str]] = []

    async def fetch(
        self, reference: ObjectReference, requester_id: str
    ) -> ObjectFetchResult:
        self.asked.append((reference, requester_id))
        return ObjectFetchResult(self._body, self._failure, 1)


class _SlowProfileFetch:
    """An ``ActorProfileFetchPort`` that answers only after *delay*."""

    def __init__(self, delay: float) -> None:
        self._delay = delay

    async def fetch_profile(
        self, actor_id: str, requester_id: str
    ) -> CoreActor:
        await asyncio.sleep(self._delay)
        return _profile(actor_id)


def _live(fetcher: object, budget: float = 5.0) -> HttpActorResolutionAdapter:
    return HttpActorResolutionAdapter(
        HttpActorProfileFetchAdapter(fetcher),  # type: ignore[arg-type]
        budget=timedelta(seconds=budget),
    )


def test_both_adapters_implement_the_port():
    assert isinstance(StaticActorResolutionAdapter([]), ActorResolutionPort)
    assert isinstance(
        HttpActorResolutionAdapter(budget=timedelta(seconds=1)),
        ActorResolutionPort,
    )


# --- static ---------------------------------------------------------------


def test_static_adapter_returns_the_declared_profile():
    declared = _profile()
    adapter = StaticActorResolutionAdapter([declared])

    resolved = adapter.resolve_actor(PEER, REQUESTER)

    assert resolved == declared
    assert isinstance(resolved, VultronOrganization)


def test_static_adapter_hands_out_a_copy():
    declared = _profile()
    adapter = StaticActorResolutionAdapter([declared])

    first = adapter.resolve_actor(PEER, REQUESTER)
    assert first is not None
    first.name = "edited by a caller"

    again = adapter.resolve_actor(PEER, REQUESTER)
    assert again is not None and again.name == "Peer Org"


def test_static_adapter_answers_none_for_an_id_it_holds_no_profile_for():
    adapter = StaticActorResolutionAdapter([_profile()])

    assert adapter.resolve_actor(f"{PEER}-other", REQUESTER) is None


def test_static_adapter_refuses_two_profiles_for_one_id():
    with pytest.raises(ValueError, match="two static profiles"):
        StaticActorResolutionAdapter([_profile(), _profile()])


# --- live -----------------------------------------------------------------


def test_live_adapter_fetches_and_validates_the_peers_profile():
    body = _profile().model_dump(mode="json", by_alias=True)
    fetcher = _BodyFetcher(body)

    resolved = _live(fetcher).resolve_actor(PEER, REQUESTER)

    assert isinstance(resolved, VultronOrganization)
    assert resolved.id_ == PEER
    assert [(r.object_id, who) for r, who in fetcher.asked] == [
        (PEER, REQUESTER)
    ]


def test_live_adapter_raises_when_the_fetch_fails():
    fetcher = _BodyFetcher(None, failure="HTTP 404")

    with pytest.raises(VultronActorProfileFetchError, match="HTTP 404"):
        _live(fetcher).resolve_actor(PEER, REQUESTER)


def test_live_adapter_refuses_a_profile_of_another_actor():
    body = _profile(f"{PEER}-impostor").model_dump(mode="json", by_alias=True)

    with pytest.raises(VultronActorProfileFetchError):
        _live(_BodyFetcher(body)).resolve_actor(PEER, REQUESTER)


def test_live_adapter_refuses_a_url_it_may_not_fetch():
    fetcher = _BodyFetcher(_profile().model_dump(mode="json", by_alias=True))

    with pytest.raises(VultronActorProfileFetchError):
        _live(fetcher).resolve_actor("http://127.0.0.1/actors/x", REQUESTER)
    assert fetcher.asked == []


@pytest.mark.spec("BT-18-015")
def test_live_adapter_gives_up_at_its_budget():
    adapter = HttpActorResolutionAdapter(
        _SlowProfileFetch(delay=0.5), budget=timedelta(seconds=0.05)
    )

    with pytest.raises(VultronActorProfileFetchError, match="took longer"):
        adapter.resolve_actor(PEER, REQUESTER)


@pytest.mark.spec("BT-18-011")
def test_live_adapter_answers_synchronously_inside_a_running_loop():
    """A caller on a thread that already runs a loop still gets a record."""
    body = _profile().model_dump(mode="json", by_alias=True)
    adapter = _live(_BodyFetcher(body))

    async def _caller() -> CoreActor:
        record: CoreActor = adapter.resolve_actor(PEER, REQUESTER)
        return record

    resolved = asyncio.run(_caller())

    assert resolved.id_ == PEER


def test_live_adapter_runs_the_fetch_off_the_calling_thread():
    seen: list[int] = []

    class _Recording:
        async def fetch_profile(
            self, actor_id: str, requester_id: str
        ) -> CoreActor:
            seen.append(threading.get_ident())
            return _profile(actor_id)

    HttpActorResolutionAdapter(
        _Recording(), budget=timedelta(seconds=5)
    ).resolve_actor(PEER, REQUESTER)

    assert seen and seen[0] != threading.get_ident()


def test_live_adapter_refuses_a_budget_that_is_not_positive():
    with pytest.raises(ValueError, match="must be positive"):
        HttpActorResolutionAdapter(budget=timedelta(0))


def test_live_adapter_budget_defaults_to_the_call_out_budget():
    from vultron.config.app import load_actor_config

    adapter = HttpActorResolutionAdapter()

    assert adapter._budget == load_actor_config().call_out_time_budget


def test_the_default_live_fetch_makes_one_attempt_within_the_budget():
    fetcher = resolution_profile_fetcher(timedelta(seconds=3))

    inner = fetcher._fetcher
    assert inner is not None
    assert inner._max_attempts == 1  # type: ignore[attr-defined]
    assert inner._timeout == 3.0  # type: ignore[attr-defined]
    assert (
        inner._max_body_bytes  # type: ignore[attr-defined]
        == MAX_VERIFICATION_PROFILE_BYTES
    )
