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
- :class:`AcceptingProofVerifier` stands in for proof verification in a test
  that replaces the ingress with a stub, so no body reaches a real verifier.

Proofs here are deterministic: the author's key is seeded from its actor id
(SIG-05-001) and ``created`` defaults to :data:`TEST_PROOF_CREATED`, so
signing the same body twice gives the same bytes.  A redelivery test relies
on that: a resend that differs from the archived body by its proof alone is a
different body, and is refused as a reused id (IE-10-002).
"""

import copy
from collections.abc import Callable, Mapping
from typing import Any

from fastapi.testclient import TestClient
from httpx2 import Response

from vultron.wire.as2 import signing

#: The ``created`` time of every proof a test makes unless it names another.
TEST_PROOF_CREATED = "2026-01-01T00:00:00Z"


def author_of(body: Mapping[str, Any]) -> str:
    """The actor id that signs *body*: its ``actor``, as an id or an object.

    Raises:
        ValueError: *body* names no actor, so the test must name the author.
    """
    actor = body.get("actor")
    if isinstance(actor, Mapping):
        actor = actor.get("id")
    if not isinstance(actor, str) or not actor:
        raise ValueError(
            "the body names no actor to sign it; pass author= explicitly"
        )
    return actor


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


class AcceptingProofVerifier:
    """A proof verifier that accepts every document and records each one.

    For a test that replaces the ingress with a stub (as
    ``test/core/behaviors/inbox/test_process_payload.py`` does, posting
    ``{}``): no body reaches a real verifier there, so the test passes this
    stand-in where the inbox takes its verifier.  :attr:`verified` lists the
    documents it was asked to verify, so a test can show the stage ran.  It
    never derives or reads a key (SIG-05-002).
    """

    def __init__(self) -> None:
        self.verified: list[Mapping[str, Any]] = []

    def verify(self, document: Mapping[str, Any]) -> None:
        """Accept *document*, recording that it was asked to verify it."""
        self.verified.append(document)


__all__ = [
    "AcceptingProofVerifier",
    "TEST_PROOF_CREATED",
    "author_of",
    "post_signed",
    "resigned",
    "signed_body",
]
