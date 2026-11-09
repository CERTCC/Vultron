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
"""Sign what a test delivers to an inbox, as its author's outbox would.

Every activity an actor sends carries its author's proof (SIG-01-001), and
every proof a test makes goes through the one signing module
(:mod:`vultron.wire.as2.signing`, SIG-05-003).  A test that delivers a body
signs it here, never by hand:

- :func:`signed_body` signs a body with its author's seeded key.
- :func:`resigned` re-signs an altered copy of a signed body in one call, for
  a test that changes a body on purpose and still needs a valid proof, such
  as "same id, different body" (IE-10-002).
- :func:`post_signed` signs a body and posts it to an inbox.
- :func:`post_delivered` posts a body that is already signed, such as one
  from ``delivered_body``, unchanged, and checks the inbox accepts it.
- :class:`AcceptingProofVerifier` stands in for the inbox's verification
  stage (:class:`~vultron.core.ports.proof_verification.ProofVerificationPort`),
  through the route's ``get_proof_verifier`` dependency.
- :class:`PublishedProfileFetcher` answers a receiving app's profile fetch
  for each named author, as that author's own profile route would, so the
  inbox's verification stage finds the key that verifies the author's proof
  (SIG-02-001).  :func:`serve_published_profiles` installs one on an app.

Proofs here are deterministic: the author's key is seeded from its actor id
(SIG-05-001) and ``created`` defaults to :data:`TEST_PROOF_CREATED`, so
signing the same body twice gives the same bytes.  A redelivery test relies
on that: a resend that differs from the archived body by its proof alone is a
different body, and is refused as a reused id (IE-10-002).
"""

import copy
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx2 import Response

from vultron.adapters.driving.fastapi.deps import ACTOR_PROFILE_FETCHER_STATE
from vultron.core.models.actor import CoreActor, VultronOrganization
from vultron.errors import VultronActorProfileFetchError
from vultron.primitives import normalise_actor_id
from vultron.wire.as2 import signing

#: The ``created`` time of every proof a test makes unless it names another.
TEST_PROOF_CREATED = "2026-01-01T00:00:00Z"


def author_of(body: Mapping[str, Any]) -> str:
    """The actor id that signs *body*: its ``actor``, as an id or an object.

    The outbox finds the author the same way (:func:`signing.author_of`).

    Raises:
        ValueError: *body* names no actor, so the test must name the author.
    """
    try:
        return signing.author_of(body)
    except ValueError as error:
        raise ValueError(f"{error}; pass author= explicitly") from error


def signed_body(
    body: Mapping[str, Any],
    *,
    author: str | None = None,
    created: str = TEST_PROOF_CREATED,
) -> dict[str, Any]:
    """A copy of *body* carrying a proof made with its author's seeded key.

    *author* defaults to the body's ``actor`` (:func:`author_of`); name it to
    sign a body with no actor, or to sign with another actor's key on
    purpose.  *body* is left unchanged.  A body that already carries a proof
    is refused, as the signing module refuses it: use :func:`resigned`.
    """
    key = signing.seeded_signing_key(author or author_of(body))
    return signing.sign(body, key, created=created)


def resigned(
    body: Mapping[str, Any],
    *,
    alter: Callable[[dict[str, Any]], None] | None = None,
    author: str | None = None,
    created: str = TEST_PROOF_CREATED,
    **updates: Any,
) -> dict[str, Any]:
    """A copy of *body*, altered and then signed again.

    Drops *body*'s proof, if it carries one, sets each top-level key in
    *updates*, then calls *alter* on the copy for a change *updates* cannot
    express (a nested object, or a key that is not a Python name such as
    ``@context``), and signs the result.  So the altered copy's proof is
    valid, and only what the test changed differs from *body*.  *body* is
    left unchanged.
    """
    altered = {k: copy.deepcopy(v) for k, v in body.items() if k != "proof"}
    altered.update(copy.deepcopy(updates))
    if alter is not None:
        alter(altered)
    return signed_body(altered, author=author, created=created)


def post_signed(
    client: TestClient,
    inbox: str,
    body: Mapping[str, Any],
    *,
    author: str | None = None,
) -> Response:
    """Sign *body* (:func:`signed_body`) and post it to *inbox*."""
    return client.post(inbox, json=signed_body(body, author=author))


def post_delivered(
    client: TestClient, inbox: str, body: Mapping[str, Any]
) -> None:
    """Post *body*, already signed by its author, to *inbox*; it accepts it.

    *body* is posted unchanged, as its author's outbox sends it
    (SIG-01-001): it comes signed from
    :func:`test.support.received.delivered_body`, :func:`signed_body` or
    :func:`resigned`, so signing it here would add a second proof.  A
    redelivery is the same bytes, so a second post of it is routed as the
    archived copy (IE-10-001).  An unsigned body is a test bug, refused here.
    """
    assert "proof" in body, "sign the body before posting it (SIG-01-001)"
    response = client.post(inbox, json=dict(body))
    assert response.status_code == 202, response.text


class AcceptingProofVerifier:
    """A stand-in proof verifier that accepts every document and records it.

    Conforms to
    :class:`~vultron.core.ports.proof_verification.ProofVerificationPort`,
    the inbox's verification stage, for a test that is not about
    verification: override the route's ``get_proof_verifier`` dependency
    with it, and every body reaches the parser.
    :attr:`verified` lists the documents it was asked to verify, so a test
    can show the stage ran.  It never derives or reads a key (SIG-05-002).
    """

    def __init__(self) -> None:
        self.verified: list[Mapping[str, Any]] = []

    async def verify(self, document: Mapping[str, Any]) -> None:
        """Accept *document*, recording that it was asked to verify it."""
        self.verified.append(document)


class PublishedProfileFetcher:
    """Answers a profile fetch as each named author's own server would.

    Conforms to
    :class:`~vultron.core.ports.actor_profile_fetch.ActorProfileFetchPort`.
    A test app serves only the receiver; the authors that post to it are
    not hosted anywhere a fetch could reach.  This stands in for their
    profile routes: the profile it returns for an author lists that
    author's published key, as the owner's own ``/profile`` route lists it
    (SIG-02-002).  The receiving app never derives the key itself
    (SIG-05-002): it reads it from this profile, as it would from a fetched
    one.

    *authors* names the actors that publish a profile; ``None``, the
    default, means every actor does.  A fetch for an actor not named fails
    as an unreachable profile does.  :attr:`asked` lists the actor ids
    fetched.
    """

    def __init__(self, authors: Iterable[str] | None = None) -> None:
        self._authors = (
            None
            if authors is None
            else {normalise_actor_id(actor) for actor in authors}
        )
        self.asked: list[str] = []

    async def fetch_profile(
        self, actor_id: str, requester_id: str
    ) -> CoreActor:
        """The profile *actor_id* publishes, with its key."""
        self.asked.append(actor_id)
        owner = normalise_actor_id(actor_id)
        if self._authors is not None and owner not in self._authors:
            raise VultronActorProfileFetchError(
                f"no test server publishes the profile of {actor_id!r}"
            )
        key = signing.published_multikey(
            signing.seeded_signing_key(owner), owner
        )
        return VultronOrganization(
            id_=owner, name=owner, assertion_method=[key]
        )


def serve_published_profiles(
    app: FastAPI, authors: Iterable[str] | None = None
) -> PublishedProfileFetcher:
    """Install a :class:`PublishedProfileFetcher` as *app*'s profile fetch.

    The inbox's verification stage then reads each named author's key from
    the profile it answers (``deps.get_actor_profile_fetcher``).  Returns the
    fetcher, so a test can see what was fetched.
    """
    fetcher = PublishedProfileFetcher(authors)
    setattr(app.state, ACTOR_PROFILE_FETCHER_STATE, fetcher)
    return fetcher


__all__ = [
    "AcceptingProofVerifier",
    "PublishedProfileFetcher",
    "TEST_PROOF_CREATED",
    "author_of",
    "post_delivered",
    "post_signed",
    "resigned",
    "serve_published_profiles",
    "signed_body",
]
