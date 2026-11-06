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

"""The HTTP profile fetch the verification-key resolver uses (SIG-02-001)."""

import asyncio
import urllib.parse
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from test.adapters.driving.fastapi._redelivery import served_store
from vultron.adapters.driven import http_actor_profile_fetch as apf
from vultron.adapters.driven.actor_hosts import canonical_actor_uri
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.http_object_fetch import (
    ObjectFetchResult,
    fetch_url,
)
from vultron.core.models.actor import VultronOrganization
from vultron.core.models.object_fetch import (
    ObjectFetchSource,
    ObjectReference,
)
from vultron.core.ports.actor_profile_fetch import ActorProfileFetchPort
from vultron.core.services.verification_key import resolve_verification_key
from vultron.errors import VultronActorProfileFetchError
from vultron.wire.as2 import signing

AUTHOR = "https://author.example/api/v2/actors/author"
RECEIVER = "https://receiver.example/api/v2/actors/receiver"


class _TableFetcher:
    """An ``ObjectFetcher`` answering every fetch with one result."""

    def __init__(self, result: ObjectFetchResult) -> None:
        self._result = result
        self.asked: list[tuple[ObjectReference, str]] = []

    async def fetch(
        self, reference: ObjectReference, requester_id: str
    ) -> ObjectFetchResult:
        self.asked.append((reference, requester_id))
        return self._result


class _ClientFetcher:
    """An ``ObjectFetcher`` that GETs the fetch URL from a served app."""

    def __init__(self, client: TestClient) -> None:
        self._client = client

    async def fetch(
        self, reference: ObjectReference, requester_id: str
    ) -> ObjectFetchResult:
        path = urllib.parse.urlsplit(fetch_url(reference)).path
        response = self._client.get(path)
        assert response.status_code == 200, response.text
        return ObjectFetchResult(response.json(), None, 1)


def _fetched(body: dict[str, Any]) -> ObjectFetchResult:
    return ObjectFetchResult(body, None, 1)


def _fetch(fetcher: _TableFetcher, actor_id: str = AUTHOR) -> Any:
    adapter = apf.HttpActorProfileFetchAdapter(fetcher)
    return asyncio.run(adapter.fetch_profile(actor_id, RECEIVER))


def test_the_adapter_implements_the_port():
    assert isinstance(
        apf.HttpActorProfileFetchAdapter(), ActorProfileFetchPort
    )


@pytest.mark.spec("SIG-02-001")
@pytest.mark.spec("SIG-02-002")
def test_a_served_profile_yields_the_key_that_verifies_the_actors_proof(
    tmp_path: Path,
):
    """End to end: the profile route's key, fetched, verifies a proof."""
    segment = "resolver-author"
    author = canonical_actor_uri(segment)
    dl = SqliteDataLayer(
        f"sqlite:///{tmp_path / 'author.db'}", actor_id=author
    )
    signed = signing.sign(
        {"id": f"{author}/activities/1", "type": "Create"},
        signing.seeded_signing_key(author),
    )
    receiver = SqliteDataLayer("sqlite:///:memory:", actor_id=RECEIVER)
    actor = VultronOrganization(id_=author, name=segment)

    with served_store(dl, author, segment, actor) as (client, _emitter):
        adapter = apf.HttpActorProfileFetchAdapter(_ClientFetcher(client))
        key = asyncio.run(
            resolve_verification_key(
                signing.proof_verification_method(signed),
                author_id=author,
                dl=receiver,
                fetcher=adapter,
                requester_id=RECEIVER,
            )
        )

    signing.verify(signed, key.public_key_multibase)


@pytest.mark.spec("SIG-02-002")
def test_the_fetch_is_a_profile_fetch_of_the_actor():
    profile = VultronOrganization(id_=AUTHOR, name="Author")
    fetcher = _TableFetcher(
        _fetched(profile.model_dump(mode="json", by_alias=True))
    )

    fetched = _fetch(fetcher)

    assert fetched.id_ == AUTHOR
    [(reference, requester)] = fetcher.asked
    assert reference.source is ObjectFetchSource.ACTOR_PROFILE
    assert reference.host_actor_id == AUTHOR
    assert requester == RECEIVER


def test_a_failed_fetch_raises_with_the_failure():
    fetcher = _TableFetcher(
        ObjectFetchResult(None, "GET answered HTTP 503", 3)
    )

    with pytest.raises(VultronActorProfileFetchError) as caught:
        _fetch(fetcher)

    assert "GET answered HTTP 503" in str(caught.value)
    assert "3 attempt" in str(caught.value)


def test_an_actor_id_that_is_no_uri_is_refused_without_a_fetch():
    fetcher = _TableFetcher(_fetched({}))

    with pytest.raises(VultronActorProfileFetchError) as caught:
        _fetch(fetcher, actor_id="vendor")

    assert "'vendor' is not an actor id" in str(caught.value)
    assert fetcher.asked == []


def test_a_profile_typed_actor_is_refused_by_its_generic_type():
    """The generic type drops ``assertionMethod`` at parse, so name it."""
    key = signing.published_multikey(
        signing.seeded_signing_key(AUTHOR), AUTHOR
    )
    body = {
        "type": "Actor",
        "id": AUTHOR,
        "assertionMethod": [key.model_dump(mode="json", by_alias=True)],
    }

    with pytest.raises(VultronActorProfileFetchError) as caught:
        _fetch(_TableFetcher(_fetched(body)))

    assert "'Actor'" in str(caught.value)
    assert "concrete actor type" in str(caught.value)


def test_a_profile_of_another_actor_is_refused():
    other = VultronOrganization(
        id_="https://other.example/api/v2/actors/other", name="Other"
    )
    fetcher = _TableFetcher(
        _fetched(other.model_dump(mode="json", by_alias=True))
    )

    with pytest.raises(VultronActorProfileFetchError) as caught:
        _fetch(fetcher)

    assert "is not the" in str(caught.value)


def test_a_body_that_is_not_an_actor_is_refused():
    body = {"type": "Note", "id": AUTHOR, "content": "not a profile"}

    with pytest.raises(VultronActorProfileFetchError) as caught:
        _fetch(_TableFetcher(_fetched(body)))

    assert "not an actor profile" in str(caught.value)


def test_a_body_of_no_known_type_is_refused():
    body = {"type": "NoSuchType", "id": AUTHOR}

    with pytest.raises(VultronActorProfileFetchError):
        _fetch(_TableFetcher(_fetched(body)))


def test_the_configured_fetcher_is_built_on_first_use(
    monkeypatch: pytest.MonkeyPatch,
):
    profile = VultronOrganization(id_=AUTHOR, name="Author")
    fetcher = _TableFetcher(
        _fetched(profile.model_dump(mode="json", by_alias=True))
    )
    built: list[_TableFetcher] = []

    def _default() -> _TableFetcher:
        built.append(fetcher)
        return fetcher

    monkeypatch.setattr(apf, "default_object_fetcher", _default)
    adapter = apf.HttpActorProfileFetchAdapter()

    asyncio.run(adapter.fetch_profile(AUTHOR, RECEIVER))
    asyncio.run(adapter.fetch_profile(AUTHOR, RECEIVER))

    assert len(built) == 1
    assert len(fetcher.asked) == 2
