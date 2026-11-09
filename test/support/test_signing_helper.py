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
"""The shared test signing helper makes proofs the signing module verifies.

The test reads each author's public key from its seeded key here, as the
author's profile will publish it; a verifier never does (SIG-05-002).
"""

import asyncio
import copy
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from test.support.signing import (
    TEST_PROOF_CREATED,
    AcceptingProofVerifier,
    PublishedProfileFetcher,
    author_of,
    post_signed,
    resigned,
    signed_body,
)
from vultron.core.ports.actor_profile_fetch import ActorProfileFetchPort
from vultron.core.ports.proof_verification import ProofVerificationPort
from vultron.errors import VultronActorProfileFetchError
from vultron.wire.as2 import signing
from vultron.wire.as2.errors import (
    VultronProofInvalidError,
    VultronUnsignableJsonError,
)

AUTHOR = "https://example.org/actors/finder"
OTHER = "https://example.org/actors/vendor"


def _body(**extra: Any) -> dict[str, Any]:
    return {
        "@context": "https://certcc.github.io/Vultron/ns/context.jsonld",
        "type": "Create",
        "id": "https://example.org/activities/create-1",
        "actor": AUTHOR,
        "object": {"type": "Note", "content": "first"},
        **extra,
    }


def _published_key(actor_id: str) -> str:
    return signing.seeded_signing_key(actor_id).public_key_multibase


@pytest.mark.spec("SIG-05-003")
def test_a_signed_body_verifies_against_its_authors_key():
    body = _body()

    signed = signed_body(body)

    signing.verify(signed, _published_key(AUTHOR))
    assert signed["proof"]["verificationMethod"] == signing.key_id_for(AUTHOR)
    assert signed["proof"]["created"] == TEST_PROOF_CREATED
    assert body == _body(), "the caller's body is left unchanged"


@pytest.mark.spec("SIG-05-001")
def test_signing_the_same_body_twice_gives_the_same_bytes():
    assert signed_body(_body()) == signed_body(_body())


def test_the_author_is_read_from_an_inline_actor():
    body = _body(actor={"id": AUTHOR, "type": "Person"})

    assert author_of(body) == AUTHOR
    signing.verify(signed_body(body), _published_key(AUTHOR))


@pytest.mark.parametrize("actor", [None, "", {"type": "Person"}])
def test_a_body_naming_no_actor_needs_an_explicit_author(actor: Any):
    body = _body(actor=actor)

    with pytest.raises(ValueError, match="author="):
        signed_body(body)
    signing.verify(signed_body(body, author=OTHER), _published_key(OTHER))


def test_a_named_author_signs_with_its_own_key():
    signed = signed_body(_body(), author=OTHER)

    signing.verify(signed, _published_key(OTHER))
    with pytest.raises(VultronProofInvalidError):
        signing.verify(signed, _published_key(AUTHOR))


def test_a_signed_body_is_not_signed_again():
    with pytest.raises(VultronUnsignableJsonError):
        signed_body(signed_body(_body()))


@pytest.mark.spec("SIG-01-003")
def test_an_altered_copy_is_resigned_in_one_call():
    """Same id, different body (IE-10-002), still with a valid proof."""
    first = signed_body(_body())
    frozen = copy.deepcopy(first)

    def change_note(body: dict[str, Any]) -> None:
        body["object"]["content"] = "second"

    second = resigned(first, summary="second", alter=change_note)

    signing.verify(second, _published_key(AUTHOR))
    assert second["id"] == first["id"]
    assert second["summary"] == "second"
    assert second["object"]["content"] == "second"
    assert second["proof"] != first["proof"]
    assert first == frozen, "the signed original is left unchanged"


def test_resigning_an_unsigned_body_signs_it():
    signing.verify(resigned(_body()), _published_key(AUTHOR))


def test_a_change_without_resigning_does_not_verify():
    """The helper is needed: an edit after signing breaks the proof."""
    changed = signed_body(_body())
    changed["summary"] = "changed after signing"

    with pytest.raises(VultronProofInvalidError):
        signing.verify(changed, _published_key(AUTHOR))


class _RecordingClient:
    def __init__(self) -> None:
        self.posted: list[tuple[str, dict[str, Any]]] = []

    def post(self, url: str, *, json: dict[str, Any]) -> str:
        self.posted.append((url, json))
        return "response"


def test_post_signed_posts_the_signed_body():
    client = _RecordingClient()

    response = post_signed(cast(TestClient, client), "/inbox/", _body())

    assert cast(object, response) == "response"
    [(url, posted)] = client.posted
    assert url == "/inbox/"
    assert posted == signed_body(_body())


def test_the_accepting_verifier_records_each_document():
    verifier = AcceptingProofVerifier()
    first, second = _body(), signed_body(_body())

    asyncio.run(verifier.verify(first))
    asyncio.run(verifier.verify(second))

    assert verifier.verified == [first, second]


def test_the_accepting_verifier_conforms_to_the_verification_port():
    assert isinstance(AcceptingProofVerifier(), ProofVerificationPort)


def test_a_published_profile_lists_the_key_that_verifies_its_author():
    author = "https://example.org/actors/author"
    fetcher = PublishedProfileFetcher([author])
    body = signed_body({**_body(), "actor": author})

    profile = asyncio.run(fetcher.fetch_profile(author + "/", "receiver"))

    assert isinstance(fetcher, ActorProfileFetchPort)
    assert profile.id_ == author
    [key] = profile.assertion_method
    signing.verify(body, key.public_key_multibase)


def test_an_author_not_named_publishes_no_profile():
    fetcher = PublishedProfileFetcher(["https://example.org/actors/a"])

    with pytest.raises(VultronActorProfileFetchError):
        asyncio.run(fetcher.fetch_profile("https://example.org/actors/b", "r"))
    assert fetcher.asked == ["https://example.org/actors/b"]
