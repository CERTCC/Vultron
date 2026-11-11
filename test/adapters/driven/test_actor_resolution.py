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
from types import SimpleNamespace

import pytest

from test.support.actor_resolution import BodyFetcher, peer_profile
from vultron.adapters.driven.actor_resolution import (
    BUDGET_SHARE,
    HttpActorResolutionAdapter,
    StaticActorResolutionAdapter,
    resolution_profile_fetcher,
)
from vultron.adapters.driven.http_actor_profile_fetch import (
    MAX_VERIFICATION_PROFILE_BYTES,
    HttpActorProfileFetchAdapter,
)
from vultron.config.app import load_actor_config
from vultron.core.models.actor import CoreActor, VultronOrganization
from vultron.core.ports.actor_resolution import ActorResolutionPort
from vultron.errors import VultronActorProfileFetchError

PEER = "https://peer.example/api/v2/actors/peer"
REQUESTER = "https://acting.example/api/v2/actors/acting"


class _BlockingProfileFetch:
    """An ``ActorProfileFetchPort`` that answers only once *release* is set."""

    def __init__(self, release: threading.Event) -> None:
        self._release = release

    async def fetch_profile(
        self, actor_id: str, requester_id: str
    ) -> CoreActor:
        while not self._release.is_set():
            await asyncio.sleep(0.01)
        return peer_profile(actor_id)


def _live(
    fetcher: BodyFetcher, budget: float = 5.0
) -> HttpActorResolutionAdapter:
    return HttpActorResolutionAdapter(
        HttpActorProfileFetchAdapter(fetcher),
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
    declared = peer_profile(PEER)
    adapter = StaticActorResolutionAdapter([declared])

    resolved = adapter.resolve_actor(PEER, REQUESTER)

    assert resolved == declared
    assert isinstance(resolved, VultronOrganization)


def test_static_adapter_hands_out_a_copy():
    adapter = StaticActorResolutionAdapter([peer_profile(PEER)])

    first = adapter.resolve_actor(PEER, REQUESTER)
    assert first is not None
    first.name = "edited by a caller"

    again = adapter.resolve_actor(PEER, REQUESTER)
    assert again is not None and again.name == "Peer Org"


def test_static_adapter_answers_none_for_an_id_it_holds_no_profile_for():
    adapter = StaticActorResolutionAdapter([peer_profile(PEER)])

    assert adapter.resolve_actor(f"{PEER}-other", REQUESTER) is None


def test_static_adapter_refuses_two_profiles_for_one_id():
    with pytest.raises(ValueError, match="two static profiles"):
        StaticActorResolutionAdapter([peer_profile(PEER), peer_profile(PEER)])


# --- live -----------------------------------------------------------------


def test_live_adapter_fetches_and_validates_the_peers_profile():
    fetcher = BodyFetcher.serving(peer_profile(PEER))

    resolved = _live(fetcher).resolve_actor(PEER, REQUESTER)

    assert isinstance(resolved, VultronOrganization)
    assert resolved.id_ == PEER
    assert [(r.object_id, who) for r, who in fetcher.asked] == [
        (PEER, REQUESTER)
    ]


def test_live_adapter_raises_when_the_fetch_fails():
    fetcher = BodyFetcher(None, failure="HTTP 404")

    with pytest.raises(VultronActorProfileFetchError, match="HTTP 404"):
        _live(fetcher).resolve_actor(PEER, REQUESTER)


def test_live_adapter_refuses_a_profile_of_another_actor():
    fetcher = BodyFetcher.serving(peer_profile(f"{PEER}-impostor"))

    with pytest.raises(VultronActorProfileFetchError):
        _live(fetcher).resolve_actor(PEER, REQUESTER)


def test_live_adapter_refuses_a_url_it_may_not_fetch():
    fetcher = BodyFetcher.serving(peer_profile(PEER))

    with pytest.raises(VultronActorProfileFetchError):
        _live(fetcher).resolve_actor("http://127.0.0.1/actors/x", REQUESTER)
    assert fetcher.asked == []


@pytest.mark.parametrize("endpoint", ["inbox", "outbox"])
def test_live_adapter_refuses_a_profile_naming_a_private_endpoint(endpoint):
    """A stored inbox is where delivery posts, so it meets the URL rule."""
    profile = peer_profile(PEER, **{endpoint: "http://10.0.0.5/inbox/"})

    with pytest.raises(VultronActorProfileFetchError, match=endpoint):
        _live(BodyFetcher.serving(profile)).resolve_actor(PEER, REQUESTER)


def test_live_adapter_keeps_a_profile_with_public_endpoints():
    profile = peer_profile(
        PEER, inbox=f"{PEER}/inbox/", outbox=f"{PEER}/outbox/"
    )

    resolved = _live(BodyFetcher.serving(profile)).resolve_actor(
        PEER, REQUESTER
    )

    assert resolved.inbox == f"{PEER}/inbox/"


@pytest.mark.spec("BT-18-015")
def test_live_adapter_gives_up_at_its_budget_on_a_daemon_worker():
    release = threading.Event()
    adapter = HttpActorResolutionAdapter(
        _BlockingProfileFetch(release), budget=timedelta(seconds=0.05)
    )
    try:
        with pytest.raises(VultronActorProfileFetchError, match="took longer"):
            adapter.resolve_actor(PEER, REQUESTER)
        workers = [
            t for t in threading.enumerate() if t.name == "actor-resolution"
        ]
        # The fetch outlived the wait, and never holds up interpreter exit.
        assert workers and all(t.daemon for t in workers)
    finally:
        release.set()


@pytest.mark.spec("BT-18-011")
def test_live_adapter_answers_synchronously_inside_a_running_loop():
    """A caller on a thread that already runs a loop still gets a record."""
    adapter = _live(BodyFetcher.serving(peer_profile(PEER)))

    async def _caller() -> CoreActor:
        record: CoreActor = adapter.resolve_actor(PEER, REQUESTER)
        return record

    assert asyncio.run(_caller()).id_ == PEER


def test_live_adapter_runs_the_fetch_off_the_calling_thread():
    seen: list[int] = []

    class _Recording:
        async def fetch_profile(
            self, actor_id: str, requester_id: str
        ) -> CoreActor:
            seen.append(threading.get_ident())
            return peer_profile(actor_id)

    HttpActorResolutionAdapter(
        _Recording(), budget=timedelta(seconds=5)
    ).resolve_actor(PEER, REQUESTER)

    assert seen and seen[0] != threading.get_ident()


def test_live_adapter_refuses_a_budget_that_is_not_positive():
    with pytest.raises(ValueError, match="must be positive"):
        HttpActorResolutionAdapter(budget=timedelta(0))


@pytest.mark.spec("BT-18-026")
@pytest.mark.spec("BT-18-027")
def test_live_adapter_waits_less_than_the_call_out_budget_by_default():
    """The rest of the budget is the seam's, so a late peer is an error."""
    budget = load_actor_config().call_out_time_budget

    wait = HttpActorResolutionAdapter()._wait()

    assert wait == budget * BUDGET_SHARE
    assert wait < budget


@pytest.mark.spec("BT-18-026")
@pytest.mark.spec("BT-18-027")
def test_live_adapter_reads_the_budget_at_each_resolution(monkeypatch):
    """A budget changed after the adapter is built still bounds the wait."""
    adapter = HttpActorResolutionAdapter()
    monkeypatch.setattr(
        "vultron.adapters.driven.actor_resolution.load_actor_config",
        lambda: SimpleNamespace(call_out_time_budget=timedelta(seconds=1)),
    )

    assert adapter._wait() == timedelta(seconds=1) * BUDGET_SHARE


def test_live_adapter_refuses_a_configured_budget_that_is_not_positive(
    monkeypatch,
):
    adapter = HttpActorResolutionAdapter()
    monkeypatch.setattr(
        "vultron.adapters.driven.actor_resolution.load_actor_config",
        lambda: SimpleNamespace(call_out_time_budget=timedelta(0)),
    )

    with pytest.raises(ValueError, match="must be positive"):
        adapter.resolve_actor(PEER, REQUESTER)


@pytest.mark.spec("BT-18-011")
def test_a_fetch_ended_by_a_base_exception_is_an_error_answer():
    """A worker cancelled before it answers gives *error*, not a KeyError."""

    class _Cancelled:
        async def fetch_profile(
            self, actor_id: str, requester_id: str
        ) -> CoreActor:
            raise asyncio.CancelledError()

    with pytest.raises(
        VultronActorProfileFetchError, match="ended with CancelledError"
    ):
        HttpActorResolutionAdapter(
            _Cancelled(), budget=timedelta(seconds=5)
        ).resolve_actor(PEER, REQUESTER)


@pytest.mark.spec("AKM-02-006")
def test_live_adapter_invents_no_time_a_profile_body_omits():
    """A peer that states no ``published``/``updated`` gets none stored."""
    body = {
        "@context": "https://www.w3.org/ns/activitystreams",
        "id": PEER,
        "type": "Organization",
        "name": "Peer Org",
        "inbox": f"{PEER}/inbox/",
    }

    resolved = _live(BodyFetcher(body)).resolve_actor(PEER, REQUESTER)

    assert resolved.published is None
    assert resolved.updated is None
    assert resolved.name == "Peer Org"


def test_live_adapter_keeps_the_times_a_profile_body_states():
    stated = "2026-01-02T03:04:05+00:00"
    body = {
        "@context": "https://www.w3.org/ns/activitystreams",
        "id": PEER,
        "type": "Organization",
        "name": "Peer Org",
        "published": stated,
        "updated": stated,
    }

    resolved = _live(BodyFetcher(body)).resolve_actor(PEER, REQUESTER)

    assert resolved.published is not None
    assert resolved.published.isoformat() == stated
    assert resolved.updated == resolved.published


def test_the_default_live_fetch_makes_one_attempt_within_the_wait():
    fetcher = resolution_profile_fetcher(timedelta(seconds=3))

    inner = fetcher._fetcher
    assert inner is not None
    assert inner._max_attempts == 1  # type: ignore[attr-defined]
    assert inner._timeout == 3.0  # type: ignore[attr-defined]
    assert (
        inner._max_body_bytes  # type: ignore[attr-defined]
        == MAX_VERIFICATION_PROFILE_BYTES
    )


def test_live_adapter_refuses_a_fetch_port_answer_that_is_no_actor():
    class _Wrong:
        async def fetch_profile(self, actor_id: str, requester_id: str):
            return {"id": actor_id}

    with pytest.raises(VultronActorProfileFetchError, match="no actor"):
        HttpActorResolutionAdapter(
            _Wrong(),  # type: ignore[arg-type]
            budget=timedelta(seconds=5),
        ).resolve_actor(PEER, REQUESTER)
