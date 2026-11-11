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
(SIG-02-001).  On an ``Announce(CaseLedgerEntry)`` it checks the
``payloadSnapshot``'s proof too, by the key of the snapshot's own ``actor``,
so a replica refuses the whole entry when either fails (SIG-04-002).  The
snapshot's proof is read from the body as received: the parser drops
``proof``, so no parsed copy carries it.

No key is derived from a seed here (SIG-05-002).
"""

import logging
from collections.abc import Mapping
from typing import Any

from starlette.concurrency import run_in_threadpool

from vultron.core.models.verified_proof import VerifiedProof
from vultron.core.ports.actor_profile_fetch import ActorProfileFetchPort
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
from vultron.wire.as2.unknown_keys import normalise

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


def _spelled(document: Mapping[str, Any], name: str) -> list[Any]:
    """Every value *document* holds under a spelling of the field *name*.

    The parser reads a field by its alias and by its field name (CS-14-001),
    such as ``object`` and ``object_``, or ``payloadSnapshot`` and
    ``payload_snapshot``, and refuses other near misses (MV-11-002).  So the
    stage reads every key that normalises to *name*, as the near-miss test
    does: a check that read only the alias could be stepped around by the
    field name the parser accepts in its place.
    """
    target = normalise(name)
    return [
        value for key, value in document.items() if normalise(key) == target
    ]


def _has_type(document: Mapping[str, Any], type_name: str) -> bool:
    return type_name in _spelled(document, "type")


def _ledger_snapshots(document: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """The snapshots an ``Announce(CaseLedgerEntry)`` carries, by any spelling.

    Raises:
        VultronProofInvalidError: A snapshot is not a JSON object, so no
            author's proof on it can be read.
    """
    if not _has_type(document, "Announce"):
        return []
    snapshots: list[Mapping[str, Any]] = []
    for entry in _spelled(document, "object"):
        if not isinstance(entry, Mapping) or not _has_type(
            entry, _LEDGER_ENTRY_TYPE
        ):
            continue
        for snapshot in _spelled(entry, "payloadSnapshot"):
            if not isinstance(snapshot, Mapping):
                raise VultronProofInvalidError(
                    "the ledger entry's payloadSnapshot is not a JSON object,"
                    " so its author's proof cannot be read (SIG-04-002)"
                )
            snapshots.append(snapshot)
    return snapshots


class ProfileKeyProofVerifier:
    """Verify a received body by keys fetched from its authors' profiles.

    Args:
        fetcher: Fetches each author's profile from its own URL; no stored
            copy is read (SIG-02-003).
        receiver_id: The receiving actor, named on a fetch.
    """

    def __init__(
        self,
        fetcher: ActorProfileFetchPort,
        receiver_id: str,
    ) -> None:
        self._fetcher = fetcher
        self._receiver_id = receiver_id

    async def verify(
        self, document: Mapping[str, Any]
    ) -> tuple[VerifiedProof, ...]:
        """Return what verified when *document*'s proofs do; raise if not.

        The activity's proof is checked against its ``actor``'s key.  An
        ``Announce(CaseLedgerEntry)`` also needs its snapshot's proof, by the
        key of the snapshot's own ``actor``: the CASE_MANAGER's for a native
        entry, the author's for a relayed act (SIG-04-002).  A snapshot
        naming no actor is refused.  The entry and its snapshot are found
        under every spelling the parser accepts.

        Returns one :class:`VerifiedProof` per proof checked, the
        activity's first, naming the key each verified against as fetched,
        for the delivery's archived record (SIG-03-004).

        Raises:
            VultronProofVerificationError: A proof is missing or does not
                verify, or its key cannot be read.  A snapshot's refusal
                names ``payloadSnapshot`` and its author.
            VultronRefusedJsonError: A proof covers a value that cannot be
                canonicalized, such as an integer outside ±(2^53 - 1).
        """
        author = _author(document, "activity")
        verified = [await self._verify_as(document, author)]
        for snapshot in _ledger_snapshots(document):
            verified.append(await self._verify_snapshot(snapshot))
        return tuple(verified)

    async def _verify_snapshot(
        self, snapshot: Mapping[str, Any]
    ) -> VerifiedProof:
        """Verify a relayed snapshot's proof by its own ``actor``'s key.

        Every activity names its signer (SIG-05-005), so one check covers
        each entry: a native entry's snapshot names the CASE_MANAGER and is
        checked by its key, a relayed participant's act names that author
        and is checked by the author's key (SIG-04-002).  A snapshot naming
        no actor, or a blank one, has no signer and is refused.
        """
        snapshot_author = _author(snapshot, "payloadSnapshot")
        try:
            return await self._verify_as(snapshot, snapshot_author)
        except VultronProofVerificationError as exc:
            raise VultronProofVerificationError(
                "the ledger entry's payloadSnapshot is not verified as"
                f" written by its actor {snapshot_author!r}, so the whole"
                f" entry is refused (SIG-04-002): {exc}"
            ) from exc

    async def _verify_as(
        self, document: Mapping[str, Any], author: str
    ) -> VerifiedProof:
        """Verify *document*'s proof by *author*'s published key.

        Returns the proof's author, its key id and the key as fetched.
        """
        method = signing.proof_verification_method(document)
        key = await resolve_verification_key(
            method,
            author_id=author,
            fetcher=self._fetcher,
            requester_id=self._receiver_id,
        )
        try:
            # Canonicalizing and checking a large body is CPU work: off the
            # event loop, so the server keeps answering (IE-06-002).
            await run_in_threadpool(
                signing.verify, document, key.public_key_multibase
            )
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
        return VerifiedProof(
            author_id=normalise_actor_id(author),
            verification_method=method,
            public_key_multibase=key.public_key_multibase,
        )


__all__ = ["ProfileKeyProofVerifier", "decode_inbox_body"]
