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
compute any actor's private key: never deploy seeded keys.  So the code
holds the line the keys cannot: an actor's outbox signs only that actor's own
messages (:func:`sign_as_author`, SIG-05-004).  The one other caller is the
docs example renderer, which signs a documentation example as that
example's own ``actor`` (:func:`sign_docs_example`): a body no server sends,
shown as its actor's outbox would seal it.  Verification never
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
import re
from collections.abc import Mapping
from datetime import datetime
from typing import Any, NoReturn

import base58
import rfc8785
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from vultron.core.models._helpers import format_timestamp
from vultron.core.models.multikey import MULTIKEY_TYPE, Multikey
from vultron.primitives import normalise_actor_id
from vultron.wire.as2.errors import (
    VultronForeignAuthorError,
    VultronJsonSyntaxError,
    VultronMultikeyError,
    VultronProofInvalidError,
    VultronRefusedJsonError,
    VultronUnsignableJsonError,
)

logger = logging.getLogger(__name__)

#: The JSON-LD context that defines the proof terms (FEP-8b32).
DATA_INTEGRITY_CONTEXT = "https://w3id.org/security/data-integrity/v2"
#: The JSON-LD context that defines the key terms an actor profile publishes:
#: ``assertionMethod``, ``Multikey``, ``controller``, ``publicKeyMultibase``.
MULTIKEY_CONTEXT = "https://w3id.org/security/multikey/v1"
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
_ED25519_SIGNATURE_LENGTH = 64
#: Multibase prefix for base58btc.
_BASE58BTC = "z"
#: The base58btc alphabet; a value with any other character, whitespace
#: included, is not base58btc.
_BASE58_TEXT = re.compile(r"[1-9A-HJ-NP-Za-km-z]+")
#: The shape of an XML Schema ``dateTimeStamp``, which Data Integrity requires
#: of ``created``: a full RFC 3339 date-time with seconds and an explicit
#: offset (CS-13-006).  Range checks are left to ``datetime.fromisoformat``.
_TIMESTAMP_TEXT = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})"
)
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

    def __reduce__(self) -> NoReturn:
        raise TypeError("a SigningKey cannot be pickled or copied out")


def key_id_for(actor_id: str) -> str:
    """The id of *actor_id*'s signing key: ``<actor id>#main-key``."""
    return f"{actor_id}#{KEY_FRAGMENT}"


def seeded_signing_key(actor_id: str) -> SigningKey:
    """The prototype key pair for *actor_id*, computed from a fixed seed.

    The same actor id gives the same key in every process and store
    (SIG-05-001).  This makes **no security claim**: the scheme is guessable
    by design (ADR-0164 prototype; real per-actor secret keys are #1184), so
    anyone who knows it can compute any actor's private key.  The guarantee
    is in the code instead: only the owning actor's outbox signs for that
    actor, through :func:`sign_as_author`, which refuses a document another
    actor wrote (SIG-05-004).  The one other signer is the docs example
    renderer (:func:`sign_docs_example`), which signs only documentation
    examples, bodies no server sends, each as its own ``actor``.  The
    actor's own profile route also computes the key, to publish its public
    half.  A verifier reads the published key instead (SIG-05-002).
    """
    if not actor_id:
        raise ValueError("a seeded key needs a non-empty actor id")
    private = Ed25519PrivateKey.from_private_bytes(_seed_for(actor_id))
    return SigningKey(private, key_id_for(actor_id))


def published_multikey(key: SigningKey, controller: str) -> Multikey:
    """The ``Multikey`` *controller*'s profile lists for *key*.

    The entry an actor publishes under ``assertionMethod`` (ENC-01-002): the
    key id its proofs name, its controller and its public half only.  The
    private key never enters it (ENC-01-007).

    Raises:
        ValueError: *key*'s id is not a fragment of *controller*'s id, so the
            profile could not list it (pydantic's ``ValidationError``).
    """
    return Multikey(
        id_=key.key_id,
        type_=MULTIKEY_TYPE,
        controller=controller,
        public_key_multibase=key.public_key_multibase,
    )


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
    decoded = _decode_base58btc(value)
    if decoded is None:
        raise VultronMultikeyError(f"an Ed25519 {what} is not valid base58btc")
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


def _decode_base58btc(value: str) -> bytes | None:
    """The bytes of a ``z``-prefixed base58btc value, or ``None`` if invalid."""
    if not _BASE58_TEXT.fullmatch(value[1:]):
        return None
    return base58.b58decode(value[1:])


def load_json(text: str | bytes) -> Any:
    """Parse JSON text that is to be verified or signed.

    Refuses what parsers disagree on, so the verifier canonicalizes the same
    value the sender signed: a duplicate object key (each parser keeps a
    different one), ``NaN`` or ``Infinity``, and a number too large for a
    double.  Integers beyond ±(2^53 - 1) are refused when the value is
    canonicalized.

    Raises:
        VultronJsonSyntaxError: the text is not JSON by RFC 8259's grammar:
            it does not decode, its bytes are not UTF-8 (UTF-16 and UTF-32
            included) or start with a byte-order mark, or it holds ``NaN``
            or ``Infinity``.
        VultronRefusedJsonError: the text is JSON of one of the refused
            kinds: a duplicate key, a number too large for a double, an
            integer with too many digits to read, or nesting too deep to
            parse.
    """
    try:
        # Bytes are read as UTF-8 only (RFC 8259 section 8.1): json.loads
        # would otherwise detect UTF-16 or UTF-32 and read them too.  A
        # leading byte-order mark stays in the text, which json.loads
        # refuses.
        if isinstance(text, bytes):
            text = text.decode("utf-8")
        return json.loads(
            text,
            object_pairs_hook=_refuse_duplicate_keys,
            parse_constant=_refuse_constant,
            parse_float=_finite_float,
        )
    except VultronUnsignableJsonError:
        raise
    except RecursionError as error:
        raise VultronRefusedJsonError(
            "JSON is nested too deeply to parse"
        ) from error
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise VultronJsonSyntaxError(f"not JSON: {error}") from error
    except ValueError as error:
        # Python's limit on the digits of an integer: the text is JSON.
        raise VultronRefusedJsonError(
            f"JSON number cannot be read: {error}"
        ) from error


def _refuse_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise VultronRefusedJsonError(
                f"JSON object has the key {key!r} more than once"
            )
        result[key] = value
    return result


def _refuse_constant(name: str) -> Any:
    raise VultronJsonSyntaxError(f"JSON number {name} is not allowed")


def _finite_float(text: str) -> float:
    value = float(text)
    if value in (float("inf"), float("-inf")):
        raise VultronRefusedJsonError(
            f"JSON number {text} is too large for a double"
        )
    return value


def canonicalize(value: Any) -> bytes:
    """The RFC 8785 (JCS) canonical form of *value*.

    This is not the ledger hash's canonical form, which is not JCS.

    Raises:
        VultronRefusedJsonError: *value* holds an integer outside
            ±(2^53 - 1), a non-finite float, a non-string key or a value JSON
            cannot carry.
    """
    try:
        return rfc8785.dumps(value)
    except RecursionError as error:
        raise VultronRefusedJsonError(
            "value is nested too deeply to canonicalize"
        ) from error
    except rfc8785.CanonicalizationError as error:
        raise VultronRefusedJsonError(
            f"value cannot be canonicalized: {error}"
        ) from error


def with_context(context: Any, entry: str) -> list[Any]:
    """*context* as a list that ends with *entry* unless it already has it.

    A single context becomes a list, an absent one a list of *entry* alone,
    and the existing entries keep their order, so whatever default
    ``@context`` the document had stays first.
    """
    entries = _context_entries(context)
    if entry not in entries:
        entries.append(entry)
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
    created: datetime | str,
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
            the one serialized form a time has, a string is used as given
            once it is a timestamp :func:`verify` accepts.  Required: signing
            reads no clock (ADR-0176), so the caller names the time, and the
            same document signed with the same key and time gives the same
            proof on every run (SIG-05-001).

    Raises:
        VultronUnsignableJsonError: *document* already carries a proof, holds
            a value that cannot be canonicalized, or *created* is not an RFC
            3339 date-time with an offset.
    """
    if not isinstance(document, Mapping):
        raise VultronUnsignableJsonError("only a JSON object can be signed")
    if "proof" in document:
        raise VultronUnsignableJsonError(
            "document already carries a proof; an object carries one at most"
        )
    if isinstance(created, datetime):
        created = format_timestamp(created)
    if not _is_timestamp(created):
        raise VultronUnsignableJsonError(
            "a proof's created time must be a datetime or an RFC 3339 "
            "date-time with an offset"
        )

    unsecured = copy.deepcopy(dict(document))
    unsecured["@context"] = with_context(
        unsecured.get("@context"), DATA_INTEGRITY_CONTEXT
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


def author_of(document: Mapping[str, Any]) -> str:
    """The actor id whose key signs *document*: its ``actor``.

    The ``actor`` may be an id or an inline object with one.

    Raises:
        VultronUnsignableJsonError: *document* names no actor, so there is
            no author to sign it.
    """
    actor = document.get("actor")
    if isinstance(actor, Mapping):
        actor = actor.get("id")
    if not isinstance(actor, str) or not actor:
        raise VultronUnsignableJsonError(
            f"{document.get('id', 'a document without an id')} names no "
            "actor to sign it"
        )
    return actor


def authored_time(document: Mapping[str, Any]) -> str:
    """The time *document*'s author wrote it: its ``published``, as written.

    An outbound activity's ``published`` is the instant of the act that
    authored it (ADR-0176), so it is the time a proof on that activity is
    created: the act signs what it writes, at the instant it writes it, and
    signing reads no clock of its own.

    Raises:
        VultronUnsignableJsonError: *document* has no ``published``, or one
            that is not an RFC 3339 date-time with an offset, so there is no
            authored time to give its proof.
    """
    published = document.get("published")
    if not isinstance(published, str) or not _is_timestamp(published):
        raise VultronUnsignableJsonError(
            f"{document.get('id', 'a document without an id')} has no"
            " published time that is an RFC 3339 date-time with an offset,"
            " so its proof has no created time"
        )
    return published


def sign_as_author(
    document: Mapping[str, Any],
    *,
    owner_id: str,
) -> dict[str, Any]:
    """*document* signed with its author's own seeded key (:func:`sign`).

    For the author's own outbox only.  *owner_id* is the actor whose store
    and outbox are signing; the document's ``actor`` must name that same
    actor, differing at most by a trailing slash, or nothing is signed
    (SIG-05-004).  The proof is made with the owner's key and names the
    owner's key id.

    The proof's ``created`` is the document's ``published``
    (:func:`authored_time`): the instant of the act that wrote it, never a
    clock read (ADR-0176).  So sealing one activity gives one proof however
    often, and wherever, it is sealed (SIG-05-001).

    The seed scheme is guessable by design (ADR-0164; real per-actor secret
    keys are #1184), so any code could compute any actor's key.  The
    guarantee is in the code instead: only the owning actor's outbox calls
    the signer, and only for that actor.  The one other caller is the docs
    example renderer, through :func:`sign_docs_example`, for bodies no
    server sends; ``test/architecture/test_seeded_signer_callers.py`` lists
    both.  A verifier reads the published key instead (SIG-05-002).

    Raises:
        VultronUnsignableJsonError: *document* names no actor
            (:func:`author_of`), has no authored time
            (:func:`authored_time`), or :func:`sign` refuses it.
        VultronForeignAuthorError: *document*'s ``actor`` is not *owner_id*.
    """
    owner = require_own_document(document, owner_id)
    return sign(
        document, seeded_signing_key(owner), created=authored_time(document)
    )


def sign_docs_example(document: Mapping[str, Any]) -> dict[str, Any]:
    """A documentation example, signed as its own ``actor`` would sign it.

    For the docs example renderers only
    (``vultron.wire.as2.vocab.examples._base``): an example shows a reader
    the body its ``actor``'s outbox would seal, proof included
    (SIG-01-001).  No server sends it, and its actor is a made-up one no
    server hosts, so the proof is made with the seeded key of the
    example's own ``actor``, never with any other actor's
    (:func:`sign_as_author`, SIG-05-004).  The proof's ``created`` is the
    example's ``published`` (:func:`authored_time`), the same rule the
    outbox follows.  Every example is stamped with the examples' fixed
    moment, so a regeneration writes the same bytes: Ed25519 signatures are
    deterministic, and the key is seeded from the actor id (SIG-05-001).

    ``test/architecture/test_seeded_signer_callers.py`` keeps every other
    module from calling this.

    Raises:
        VultronUnsignableJsonError: *document* names no ``actor``, has no
            authored time (:func:`authored_time`), or :func:`sign` refuses
            it.
    """
    return sign_as_author(document, owner_id=author_of(document))


def require_own_document(document: Mapping[str, Any], owner_id: str) -> str:
    """Return *owner_id*, normalised, when *document* is that actor's own.

    The ``actor`` of *document* (:func:`author_of`) and *owner_id* are
    compared without a trailing slash (OID-01-006).

    Raises:
        VultronUnsignableJsonError: *document* names no actor.
        VultronForeignAuthorError: *owner_id* is empty, or the document's
            ``actor`` names another actor (SIG-05-004).
    """
    author = author_of(document)
    owner = normalise_actor_id(owner_id) if owner_id else ""
    if not owner or normalise_actor_id(author) != owner:
        raise VultronForeignAuthorError(
            f"{document.get('id', 'a document without an id')} is written by"
            f" '{author}', not by '{owner_id}' whose outbox is sealing it; an"
            " actor signs only its own messages (SIG-05-004)"
        )
    return owner


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


def _is_timestamp(value: Any) -> bool:
    """Whether *value* is a ``created`` time both sign and verify accept."""
    if not isinstance(value, str) or not _TIMESTAMP_TEXT.fullmatch(value):
        return False
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return False
    return True


def verify(document: Mapping[str, Any], public_key_multibase: str) -> None:
    """Check *document*'s proof against the author's published key.

    *public_key_multibase* must come from the author's actor profile
    (SIG-02-001); this function never derives a key.  Parse received text
    with :func:`load_json` first, so a duplicate key is refused rather than
    resolved one way here and another way by the parser.

    The signature covers the document's whole ``@context``.  W3C
    ``eddsa-jcs-2022`` lets a verifier replace it with the proof's
    ``@context`` once the prefix matches, which admits contexts appended
    after signing.  This verifier does not: a proof must cover the whole
    activity as sent (SIG-01-003), and an appended context can change what
    its terms mean.  A body this module signs always has the two equal.

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
    if created is not None and not _is_timestamp(created):
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
    signature = _decode_base58btc(proof_value)
    if signature is None:
        raise VultronProofInvalidError("proofValue is not valid base58btc")
    if len(signature) != _ED25519_SIGNATURE_LENGTH:
        raise VultronProofInvalidError(
            f"proofValue must be a {_ED25519_SIGNATURE_LENGTH}-byte Ed25519 "
            f"signature, not {len(signature)} bytes"
        )
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
    "MULTIKEY_CONTEXT",
    "PROOF_PURPOSE",
    "PROOF_TYPE",
    "SigningKey",
    "author_of",
    "authored_time",
    "canonicalize",
    "decode_public_key_multibase",
    "encode_public_key_multibase",
    "key_id_for",
    "load_json",
    "proof_verification_method",
    "published_multikey",
    "require_own_document",
    "seeded_signing_key",
    "sign",
    "sign_as_author",
    "sign_docs_example",
    "verify",
    "with_context",
]
