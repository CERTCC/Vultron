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

"""The inbox's proof verification stage (SIG-03).

A delivery is verified on its decoded body, after the JSON-shape check and
before ``parse_activity`` (SIG-03-003): nothing of a forged body reaches
expansion, validation or hydration.  The body is decoded with
:func:`vultron.wire.as2.signing.load_json`, so the verifier reads the same
value the sender signed: a duplicate key is refused, not resolved one way here
and another way by a parser.

:class:`ProfileKeyProofVerifier` implements
:class:`~vultron.core.ports.proof_verification.ProofVerificationPort`.  It
checks the activity's proof against the key its ``actor`` publishes
(SIG-05-005: the actor is the signer), resolved from that actor's profile
(SIG-02-001).  On an ``Announce(CaseLedgerEntry)`` whose ``payloadSnapshot``
names another actor, it checks the snapshot's author's proof too, so a
replica refuses the whole entry when either fails (SIG-04-002).  The
snapshot's proof is read from the body as received: the parser drops
``proof``, so no parsed copy carries it.

No key is derived from a seed here (SIG-05-002).
"""

import logging
from collections.abc import Mapping
from typing import Any, cast

from vultron.core.ports.actor_profile_fetch import ActorProfileFetchPort
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.datalayer import DataLayer
from vultron.core.services.verification_key import (
    key_owner_id,
    resolve_verification_key,
)
from vultron.errors import (
    VultronProofVerificationError,
    VultronVerificationKeyError,
)
from vultron.primitives import normalise_actor_id
from vultron.wire.as2 import signing
from vultron.wire.as2.errors import (
    VultronMultikeyError,
    VultronProofInvalidError,
    VultronRefusedJsonError,
    VultronUnsignableJsonError,
)

logger = logging.getLogger(__name__)

#: The ``type`` of an inline ledger entry an ``Announce`` relays.
_LEDGER_ENTRY_TYPE = "CaseLedgerEntry"


def decode_inbox_body(raw: bytes) -> dict[str, Any]:
    """The JSON object a delivery's *raw* body holds.

    Raises:
        VultronJsonSyntaxError: *raw* is not JSON by RFC 8259's grammar
            (:func:`signing.load_json`).
        VultronRefusedJsonError: *raw* is JSON the receiver refuses: a kind
            :func:`signing.load_json` refuses, or a value that is not an
            object, since an activity is one.
    """
    body = signing.load_json(raw)
    if not isinstance(body, dict):
        raise VultronRefusedJsonError(
            f"an activity is a JSON object, not a JSON {_json_kind(body)}"
        )
    return body


def _json_kind(value: Any) -> str:
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, bool):
        return "boolean"
    if value is None:
        return "null"
    return "number"


def _author(document: Mapping[str, Any], what: str) -> str:
    """The actor that signed *document*: its ``actor`` (SIG-05-005).

    Raises:
        VultronProofInvalidError: *document* names no actor, so no author's
            key can verify its proof.
    """
    try:
        return signing.author_of(document)
    except VultronUnsignableJsonError as exc:
        raise VultronProofInvalidError(
            f"the {what} names no actor, so no author's key can verify its"
            " proof (SIG-05-005)"
        ) from exc


def _ledger_snapshot(document: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """The ``payloadSnapshot`` an ``Announce(CaseLedgerEntry)`` carries."""
    if document.get("type") != "Announce":
        return None
    entry = document.get("object")
    if not isinstance(entry, Mapping):
        return None
    if entry.get("type") != _LEDGER_ENTRY_TYPE:
        return None
    snapshot = entry.get("payloadSnapshot")
    return snapshot if isinstance(snapshot, Mapping) else None


class ProfileKeyProofVerifier:
    """Verify a received body by keys read from its authors' profiles.

    Args:
        dl: The receiving actor's own store, which holds its copies of other
            actors' profiles (read first, AKM-05-012).
        fetcher: Fetches a profile the held copy does not list the key in.
        receiver_id: The receiving actor, named on a fetch.
    """

    def __init__(
        self,
        dl: DataLayer,
        fetcher: ActorProfileFetchPort,
        receiver_id: str,
    ) -> None:
        self._dl = cast(CasePersistence, dl)
        self._fetcher = fetcher
        self._receiver_id = receiver_id

    async def verify(self, document: Mapping[str, Any]) -> None:
        """Return when *document*'s proofs verify; raise when one does not.

        The activity's proof is checked against its ``actor``'s key.  An
        ``Announce(CaseLedgerEntry)`` whose snapshot names another actor
        also needs that author's proof on the snapshot (SIG-04-002); a
        snapshot naming the same actor, or none, is covered by the outer
        proof, which signs every nested object (SIG-01-003).

        Raises:
            VultronProofVerificationError: A proof is missing or does not
                verify, or its key cannot be read.  A snapshot's refusal
                names ``payloadSnapshot`` and its author.
            VultronRefusedJsonError: A proof covers a value that cannot be
                canonicalized, such as an integer outside ±(2^53 - 1).
        """
        author = _author(document, "activity")
        await self._verify_as(document, author)
        snapshot = _ledger_snapshot(document)
        if snapshot is None or snapshot.get("actor") is None:
            return
        snapshot_author = _author(snapshot, "payloadSnapshot")
        if normalise_actor_id(snapshot_author) == normalise_actor_id(author):
            return
        try:
            await self._verify_as(snapshot, snapshot_author)
        except VultronProofVerificationError as exc:
            raise VultronProofVerificationError(
                "the ledger entry's payloadSnapshot is not verified as"
                f" written by its author {snapshot_author!r}, so the whole"
                f" entry is refused (SIG-04-002): {exc}"
            ) from exc

    async def _verify_as(
        self, document: Mapping[str, Any], author: str
    ) -> None:
        """Verify *document*'s proof by *author*'s published key."""
        method = signing.proof_verification_method(document)
        key = await resolve_verification_key(
            method,
            author_id=author,
            dl=self._dl,
            fetcher=self._fetcher,
            requester_id=self._receiver_id,
        )
        try:
            signing.verify(document, key.public_key_multibase)
        except VultronMultikeyError as exc:
            # The author published a key no proof can be checked against:
            # the key cannot be read, as when no profile lists it.
            raise VultronVerificationKeyError(
                f"key {method!r} in the profile of {key_owner_id(method)!r}"
                " is not an Ed25519 Multikey, so the proof cannot be checked"
                " (SIG-02-001)"
            ) from exc
        logger.debug(
            "Verified the proof of %s by %s for actor_id=%s",
            document.get("id"),
            author,
            self._receiver_id,
        )


__all__ = ["ProfileKeyProofVerifier", "decode_inbox_body"]
