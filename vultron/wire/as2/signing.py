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
"""The one module that creates and verifies object integrity proofs.

Every proof this codebase makes or checks goes through here (SIG-05-003,
ADR-0164), the way ``vultron.wire.as2.factories`` owns outbound construction.
It is the only module that imports the Ed25519 and JCS primitives, so the
signer and the verifier cannot drift apart.

A proof is a FEP-8b32 ``DataIntegrityProof`` using the ``eddsa-jcs-2022``
cryptosuite (SIG-01-002): Ed25519 over the SHA-256 hashes of the RFC 8785
canonical forms of the proof options and of the document.  Public keys are
``Multikey`` values, multibase base58btc with the Ed25519 multicodec prefix.

**Seeded keys make no security claim.**  :func:`seeded_signing_key` computes a
prototype actor's key pair from a fixed seed tied to its actor id
(SIG-05-001), so proofs repeat across runs.  Anyone who knows the scheme can
compute any actor's private key: never deploy seeded keys.  Verification never
derives a key from a seed (SIG-05-002); it takes the published
``publicKeyMultibase`` from the author's profile.

A private key never leaves a :class:`SigningKey`: no function exports it, and
the object's ``repr`` and ``str`` show only the public key, so logging one
does not disclose it (ENC-01-007).

JSON that parsers disagree on is refused rather than signed or verified:
:func:`load_json` refuses duplicate object keys and non-finite numbers, and
canonicalization refuses integers outside the I-JSON range ±(2^53 - 1).
"""

import copy
import hashlib
import json
import logging
from collections.abc import Mapping
from datetime import datetime
from typing import Any

import base58
import rfc8785
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from vultron.core.models._helpers import format_timestamp, now_utc
from vultron.wire.as2.errors import (
    VultronMultikeyError,
    VultronProofInvalidError,
    VultronUnsignableJsonError,
)

logger = logging.getLogger(__name__)

#: The JSON-LD context that defines the proof terms (FEP-8b32).
DATA_INTEGRITY_CONTEXT = "https://w3id.org/security/data-integrity/v2"
PROOF_TYPE = "DataIntegrityProof"
CRYPTOSUITE = "eddsa-jcs-2022"
PROOF_PURPOSE = "assertionMethod"
#: The fragment that names an actor's signing key in its profile.
KEY_FRAGMENT = "main-key"

#: Multicodec prefixes: ``ed25519-pub`` (0xed) and ``ed25519-priv`` (0x1300),
#: each as an unsigned varint.
_ED25519_PUBLIC_PREFIX = b"\xed\x01"
_ED25519_SECRET_PREFIX = b"\x80\x26"
_ED25519_KEY_LENGTH = 32
#: Multibase prefix for base58btc.
_BASE58BTC = "z"
#: Domain separation for seeds, versioned so a scheme change changes every key.
_SEED_LABEL = b"vultron-prototype-seeded-key/v1\n"


class SigningKey:
    """An actor's Ed25519 key pair and the key id its proofs name.

    The private key stays inside: there is no accessor for it, and ``repr``
    shows only the key id and the public key (ENC-01-007).
    """

    __slots__ = ("_private", "key_id", "public_key_multibase")

    def __init__(self, private: Ed25519PrivateKey, key_id: str) -> None:
        if not key_id:
            raise ValueError("a signing key needs a non-empty key id")
        self._private = private
        self.key_id = key_id
        self.public_key_multibase = encode_public_key_multibase(
            private.public_key()
        )

    @classmethod
    def from_secret_multibase(cls, secret: str, key_id: str) -> "SigningKey":
        """Load a key from a ``secretKeyMultibase`` value, as test vectors give one."""
        seed = _decode_multibase(secret, _ED25519_SECRET_PREFIX, "secret key")
        return cls(Ed25519PrivateKey.from_private_bytes(seed), key_id)

    def _sign(self, data: bytes) -> bytes:
        return self._private.sign(data)

    def __repr__(self) -> str:
        return (
            f"SigningKey(key_id={self.key_id!r}, "
            f"public_key_multibase={self.public_key_multibase!r})"
        )

    __str__ = __repr__

    def __reduce__(self) -> Any:
        raise TypeError("a SigningKey cannot be pickled or copied out")


def key_id_for(actor_id: str) -> str:
    """The id of *actor_id*'s signing key: ``<actor id>#main-key``."""
    return f"{actor_id}#{KEY_FRAGMENT}"


def seeded_signing_key(actor_id: str) -> SigningKey:
    """The prototype key pair for *actor_id*, computed from a fixed seed.

    The same actor id gives the same key in every process and store
    (SIG-05-001).  This makes **no security claim**: anyone who knows the
    scheme can compute the private key.  Only the key's owner calls this;
    a verifier reads the published key instead (SIG-05-002).
    """
    if not actor_id:
        raise ValueError("a seeded key needs a non-empty actor id")
    private = Ed25519PrivateKey.from_private_bytes(_seed_for(actor_id))
    return SigningKey(private, key_id_for(actor_id))


def _seed_for(actor_id: str) -> bytes:
    return hashlib.sha256(_SEED_LABEL + actor_id.encode("utf-8")).digest()


def encode_public_key_multibase(public_key: Ed25519PublicKey) -> str:
    """The ``publicKeyMultibase`` value of an Ed25519 public key."""
    raw = public_key.public_bytes_raw()
    return _BASE58BTC + base58.b58encode(_ED25519_PUBLIC_PREFIX + raw).decode()


def decode_public_key_multibase(value: str) -> Ed25519PublicKey:
    """Read an Ed25519 public key from a ``publicKeyMultibase`` value.

    Raises:
        VultronMultikeyError: *value* is not a base58btc Ed25519 ``Multikey``.
    """
    raw = _decode_multibase(value, _ED25519_PUBLIC_PREFIX, "public key")
    return Ed25519PublicKey.from_public_bytes(raw)


def _decode_multibase(value: str, prefix: bytes, what: str) -> bytes:
    if not isinstance(value, str) or not value.startswith(_BASE58BTC):
        raise VultronMultikeyError(
            f"an Ed25519 {what} must be multibase base58btc ('z' prefix)"
        )
    try:
        decoded = base58.b58decode(value[1:])
    except ValueError as error:
        raise VultronMultikeyError(
            f"an Ed25519 {what} is not valid base58btc"
        ) from error
    if not decoded.startswith(prefix):
        raise VultronMultikeyError(
            f"an Ed25519 {what} must carry the multicodec prefix "
            f"0x{prefix.hex()}"
        )
    raw = decoded[len(prefix) :]
    if len(raw) != _ED25519_KEY_LENGTH:
        raise VultronMultikeyError(
            f"an Ed25519 {what} must be {_ED25519_KEY_LENGTH} bytes, "
            f"not {len(raw)}"
        )
    return raw


def load_json(text: str | bytes) -> Any:
    """Parse JSON text that is to be verified or signed.

    Refuses what parsers disagree on, so the verifier canonicalizes the same
    value the sender signed: a duplicate object key (each parser keeps a
    different one), ``NaN`` or ``Infinity``, and a number too large for a
    double.  Integers beyond ±(2^53 - 1) are refused when the value is
    canonicalized.

    Raises:
        VultronUnsignableJsonError: the text is not JSON, or is JSON of one
            of the refused kinds.
    """
    try:
        return json.loads(
            text,
            object_pairs_hook=_refuse_duplicate_keys,
            parse_constant=_refuse_constant,
            parse_float=_finite_float,
        )
    except json.JSONDecodeError as error:
        raise VultronUnsignableJsonError(f"not JSON: {error}") from error


def _refuse_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise VultronUnsignableJsonError(
                f"JSON object has the key {key!r} more than once"
            )
        result[key] = value
    return result


def _refuse_constant(name: str) -> Any:
    raise VultronUnsignableJsonError(f"JSON number {name} is not allowed")


def _finite_float(text: str) -> float:
    value = float(text)
    if value in (float("inf"), float("-inf")):
        raise VultronUnsignableJsonError(
            f"JSON number {text} is too large for a double"
        )
    return value


def canonicalize(value: Any) -> bytes:
    """The RFC 8785 (JCS) canonical form of *value*.

    This is not the ledger hash's canonical form, which is not JCS.

    Raises:
        VultronUnsignableJsonError: *value* holds an integer outside
            ±(2^53 - 1), a non-finite float, a non-string key or a value JSON
            cannot carry.
    """
    try:
        return rfc8785.dumps(value)
    except rfc8785.CanonicalizationError as error:
        raise VultronUnsignableJsonError(
            f"value cannot be canonicalized: {error}"
        ) from error


def _with_data_integrity_context(context: Any) -> list[Any]:
    """*context* as a list that includes the data-integrity context."""
    if context is None:
        entries: list[Any] = []
    elif isinstance(context, list):
        entries = list(context)
    else:
        entries = [context]
    if DATA_INTEGRITY_CONTEXT not in entries:
        entries.append(DATA_INTEGRITY_CONTEXT)
    return entries


def _hash_data(proof_config: Mapping[str, Any], document: Any) -> bytes:
    """The ``eddsa-jcs-2022`` signing input: both hashes, options first."""
    return (
        hashlib.sha256(canonicalize(proof_config)).digest()
        + hashlib.sha256(canonicalize(document)).digest()
    )


def sign(
    document: Mapping[str, Any],
    key: SigningKey,
    *,
    created: datetime | str | None = None,
) -> dict[str, Any]:
    """Return a copy of *document* carrying a proof made with *key*.

    The copy's ``@context`` gains the data-integrity context if it lacks it
    (a single context becomes a list), and the proof carries that same
    ``@context``, as FEP-8b32 shows.  The proof covers the whole document,
    every nested object included (SIG-01-003).

    Args:
        document: the JSON object to sign; it must carry no ``proof``.
        key: the author's signing key; the proof names its key id.
        created: the proof's ``created`` time; a ``datetime`` is written in
            the one serialized form a time has, a string is used as given.
            Defaults to now.

    Raises:
        VultronUnsignableJsonError: *document* already carries a proof, or
            holds a value that cannot be canonicalized.
    """
    if not isinstance(document, Mapping):
        raise VultronUnsignableJsonError("only a JSON object can be signed")
    if "proof" in document:
        raise VultronUnsignableJsonError(
            "document already carries a proof; an object carries one at most"
        )
    if created is None:
        created = now_utc()
    if isinstance(created, datetime):
        created = format_timestamp(created)
    if not created:
        raise VultronUnsignableJsonError("a proof's created time is empty")

    unsecured = copy.deepcopy(dict(document))
    unsecured["@context"] = _with_data_integrity_context(
        unsecured.get("@context")
    )
    proof_config: dict[str, Any] = {
        "@context": copy.deepcopy(unsecured["@context"]),
        "type": PROOF_TYPE,
        "cryptosuite": CRYPTOSUITE,
        "verificationMethod": key.key_id,
        "proofPurpose": PROOF_PURPOSE,
        "created": created,
    }
    signature = key._sign(_hash_data(proof_config, unsecured))
    proof_value = _BASE58BTC + base58.b58encode(signature).decode()
    logger.debug(
        "Signed %s with key %s",
        unsecured.get("id", "a document without an id"),
        key.key_id,
    )
    return {**unsecured, "proof": {**proof_config, "proofValue": proof_value}}


def proof_verification_method(document: Mapping[str, Any]) -> str:
    """The key id that *document*'s proof names, read before verifying.

    The verifier uses it to find the author's published key (SIG-02-001).

    Raises:
        VultronProofInvalidError: *document* carries no single proof naming a
            key.
    """
    method = _single_proof(document).get("verificationMethod")
    if not isinstance(method, str) or not method:
        raise VultronProofInvalidError("proof names no verificationMethod")
    return method


def _single_proof(document: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(document, Mapping):
        raise VultronProofInvalidError("only a JSON object carries a proof")
    proof = document.get("proof")
    if proof is None:
        raise VultronProofInvalidError("document carries no proof")
    if not isinstance(proof, Mapping):
        raise VultronProofInvalidError(
            "proof must be one JSON object; a proof set or chain is not "
            "supported"
        )
    return proof


def _context_entries(context: Any) -> list[Any]:
    if context is None:
        return []
    return list(context) if isinstance(context, list) else [context]


def verify(document: Mapping[str, Any], public_key_multibase: str) -> None:
    """Check *document*'s proof against the author's published key.

    *public_key_multibase* must come from the author's actor profile
    (SIG-02-001); this function never derives a key.  Parse received text
    with :func:`load_json` first, so a duplicate key is refused rather than
    resolved one way here and another way by the parser.

    Raises:
        VultronProofInvalidError: the proof is missing, is not an
            ``eddsa-jcs-2022`` ``DataIntegrityProof`` for ``assertionMethod``,
            or does not verify.
        VultronMultikeyError: *public_key_multibase* is not an Ed25519
            ``Multikey`` value.
        VultronUnsignableJsonError: the document holds a value that cannot be
            canonicalized.
    """
    proof = _single_proof(document)
    method = proof_verification_method(document)
    for field, expected in (
        ("type", PROOF_TYPE),
        ("cryptosuite", CRYPTOSUITE),
        ("proofPurpose", PROOF_PURPOSE),
    ):
        if proof.get(field) != expected:
            raise VultronProofInvalidError(
                f"proof {field} must be {expected!r}, not {proof.get(field)!r}"
            )
    proof_value = proof.get("proofValue")
    if not isinstance(proof_value, str) or not proof_value.startswith(
        _BASE58BTC
    ):
        raise VultronProofInvalidError(
            "proofValue must be multibase base58btc ('z' prefix)"
        )
    created = proof.get("created")
    if created is not None and (not isinstance(created, str) or not created):
        raise VultronProofInvalidError("proof created must be a timestamp")

    unsecured = {k: v for k, v in document.items() if k != "proof"}
    proof_config = {k: v for k, v in proof.items() if k != "proofValue"}
    if "@context" in proof_config:
        expected_prefix = _context_entries(proof_config["@context"])
        actual = _context_entries(unsecured.get("@context"))
        if actual[: len(expected_prefix)] != expected_prefix:
            raise VultronProofInvalidError(
                "document @context does not start with the proof's @context"
            )

    public_key = decode_public_key_multibase(public_key_multibase)
    try:
        signature = base58.b58decode(proof_value[1:])
    except ValueError as error:
        raise VultronProofInvalidError(
            "proofValue is not valid base58btc"
        ) from error
    try:
        public_key.verify(signature, _hash_data(proof_config, unsecured))
    except InvalidSignature as error:
        raise VultronProofInvalidError(
            f"proof made with {method} does not verify"
        ) from error
    logger.debug(
        "Verified the proof on %s made with %s",
        unsecured.get("id", "a document without an id"),
        method,
    )


__all__ = [
    "CRYPTOSUITE",
    "DATA_INTEGRITY_CONTEXT",
    "KEY_FRAGMENT",
    "PROOF_PURPOSE",
    "PROOF_TYPE",
    "SigningKey",
    "canonicalize",
    "decode_public_key_multibase",
    "encode_public_key_multibase",
    "key_id_for",
    "load_json",
    "proof_verification_method",
    "seeded_signing_key",
    "sign",
    "verify",
]
