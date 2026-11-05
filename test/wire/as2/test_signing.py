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
"""The signing module against published vectors, and its refusals (ADR-0164).

The vectors are copied verbatim from two sources:

- W3C Data Integrity EdDSA Cryptosuites v1.0, Appendix B.3
  "Representation: eddsa-jcs-2022" (Examples 29 to 39),
  <https://www.w3.org/TR/vc-di-eddsa/#representation-eddsa-jcs-2022>.
- FEP-8b32 ``fep-8b32.feature``, scenarios "Signing a document" and
  "Verifying a signature",
  <https://codeberg.org/fediverse/fep/src/branch/main/fep/8b32/fep-8b32.feature>.
"""

import copy
import hashlib
import json
from datetime import UTC, datetime
from typing import Any

import base58
import pytest

from vultron.wire.as2 import signing
from vultron.wire.as2.errors import (
    VultronMultikeyError,
    VultronProofInvalidError,
    VultronUnsignableJsonError,
)

#: W3C Example 29 and FEP-8b32 share one key pair.
VECTOR_PRIVATE_KEY = "z3u2en7t5LR2WtQH5PfFqMqwVHBeXouLzo6haApm8XHqvjxq"
VECTOR_PUBLIC_KEY = "z6MkrJVnaZkeFzdQyMZu1cgjg7k1pZZ6pvBQ7XJPt4swbTQ2"
CREATED = "2023-02-24T23:36:38Z"

_W3C_CONTEXT = [
    "https://www.w3.org/ns/credentials/v2",
    "https://www.w3.org/ns/credentials/examples/v2",
]
#: W3C Example 30, a credential without a proof.
W3C_CREDENTIAL: dict[str, Any] = {
    "@context": _W3C_CONTEXT,
    "id": "urn:uuid:58172aac-d8ba-11ed-83dd-0b3aef56cc33",
    "type": ["VerifiableCredential", "AlumniCredential"],
    "name": "Alumni Credential",
    "description": "A minimum viable example of an Alumni Credential.",
    "issuer": "https://vc.example/issuers/5678",
    "validFrom": "2023-01-01T00:00:00Z",
    "credentialSubject": {
        "id": "did:example:abcdefgh",
        "alumniOf": "The School of Examples",
    },
}
#: W3C Example 33, the proof options document.
W3C_PROOF_OPTIONS: dict[str, Any] = {
    "type": "DataIntegrityProof",
    "cryptosuite": "eddsa-jcs-2022",
    "created": CREATED,
    "verificationMethod": f"did:key:{VECTOR_PUBLIC_KEY}#{VECTOR_PUBLIC_KEY}",
    "proofPurpose": "assertionMethod",
    "@context": _W3C_CONTEXT,
}
#: W3C Example 31.
W3C_CANONICAL_CREDENTIAL = (
    '{"@context":["https://www.w3.org/ns/credentials/v2",'
    '"https://www.w3.org/ns/credentials/examples/v2"],'
    '"credentialSubject":{"alumniOf":"The School of Examples",'
    '"id":"did:example:abcdefgh"},'
    '"description":"A minimum viable example of an Alumni Credential.",'
    '"id":"urn:uuid:58172aac-d8ba-11ed-83dd-0b3aef56cc33",'
    '"issuer":"https://vc.example/issuers/5678","name":"Alumni Credential",'
    '"type":["VerifiableCredential","AlumniCredential"],'
    '"validFrom":"2023-01-01T00:00:00Z"}'
)
#: W3C Example 34.
W3C_CANONICAL_PROOF_OPTIONS = (
    '{"@context":["https://www.w3.org/ns/credentials/v2",'
    '"https://www.w3.org/ns/credentials/examples/v2"],'
    '"created":"2023-02-24T23:36:38Z","cryptosuite":"eddsa-jcs-2022",'
    '"proofPurpose":"assertionMethod","type":"DataIntegrityProof",'
    '"verificationMethod":"did:key:z6MkrJVnaZkeFzdQyMZu1cgjg7k1pZZ6pvBQ7XJPt4swbTQ2'
    '#z6MkrJVnaZkeFzdQyMZu1cgjg7k1pZZ6pvBQ7XJPt4swbTQ2"}'
)
#: W3C Examples 32 and 35.
W3C_CREDENTIAL_HASH = (
    "59b7cb6251b8991add1ce0bc83107e3db9dbbab5bd2c28f687db1a03abc92f19"
)
W3C_PROOF_OPTIONS_HASH = (
    "66ab154f5c2890a140cb8388a22a160454f80575f6eae09e5a097cabe539a1db"
)
#: W3C Example 38.
W3C_PROOF_VALUE = (
    "z2HnFSSPPBzR36zdDgK8PbEHeXbR56YF24jwMpt3R1eHXQzJDMWS93FCzpvJpwTWd3GAVF"
    "uUfjoJdcnTMuVor51aX"
)

FEP_KEY_ID = "https://server.example/users/alice#ed25519-key"
_FEP_CONTEXT = [
    "https://www.w3.org/ns/activitystreams",
    "https://w3id.org/security/data-integrity/v2",
]
#: FEP-8b32 "Signing a document": the document.
FEP_DOCUMENT: dict[str, Any] = {
    "@context": _FEP_CONTEXT,
    "id": "https://server.example/activities/1",
    "type": "Create",
    "actor": "https://server.example/users/alice",
    "object": {
        "id": "https://server.example/objects/1",
        "type": "Note",
        "attributedTo": "https://server.example/users/alice",
        "content": "Hello world",
        "location": {
            "type": "Place",
            "longitude": -71.184902,
            "latitude": 25.273962,
        },
    },
}
FEP_CANONICAL_DOCUMENT = (
    '{"@context":["https://www.w3.org/ns/activitystreams",'
    '"https://w3id.org/security/data-integrity/v2"],'
    '"actor":"https://server.example/users/alice",'
    '"id":"https://server.example/activities/1",'
    '"object":{"attributedTo":"https://server.example/users/alice",'
    '"content":"Hello world","id":"https://server.example/objects/1",'
    '"location":{"latitude":25.273962,"longitude":-71.184902,"type":"Place"},'
    '"type":"Note"},"type":"Create"}'
)
FEP_CANONICAL_PROOF_CONFIG = (
    '{"@context":["https://www.w3.org/ns/activitystreams",'
    '"https://w3id.org/security/data-integrity/v2"],'
    '"created":"2023-02-24T23:36:38Z","cryptosuite":"eddsa-jcs-2022",'
    '"proofPurpose":"assertionMethod","type":"DataIntegrityProof",'
    '"verificationMethod":"https://server.example/users/alice#ed25519-key"}'
)
FEP_COMBINED_HASH = (
    "cf63e2308ce7d1137667192c5c5e751ba7b1c6e3d5e746a7b717d309654ad198"
    "0793e8d97e2de4b989b2b2d7a5fae8cf941f102a03c0ecab00f03eaa2330c650"
)
#: FEP-8b32 "Signing a document": the signed document.
FEP_SIGNED_DOCUMENT: dict[str, Any] = {
    **FEP_DOCUMENT,
    "proof": {
        "@context": _FEP_CONTEXT,
        "type": "DataIntegrityProof",
        "cryptosuite": "eddsa-jcs-2022",
        "verificationMethod": FEP_KEY_ID,
        "proofPurpose": "assertionMethod",
        "proofValue": (
            "z42ffGu6AUKPCFcFPiabmUvnGLPJzC7e4DGWC52NUasSSH37UMa9c58tdgVs"
            "zUcZfytxa4fQ5TYHaJENCxUDe9SdL"
        ),
        "created": CREATED,
    },
}

ACTOR = "https://example.org/actors/vendor"
OTHER_ACTOR = "https://example.org/actors/finder"


def _signed_note() -> dict[str, Any]:
    note = {
        "@context": "https://www.w3.org/ns/activitystreams",
        "id": "https://example.org/activities/1",
        "type": "Create",
        "actor": ACTOR,
        "object": {"id": "https://example.org/notes/1", "type": "Note"},
    }
    return signing.sign(
        note, signing.seeded_signing_key(ACTOR), created=CREATED
    )


# --- Published vectors -------------------------------------------------------


def test_a_secret_key_vector_gives_the_published_public_key():
    key = signing.SigningKey.from_secret_multibase(
        VECTOR_PRIVATE_KEY, FEP_KEY_ID
    )

    assert key.public_key_multibase == VECTOR_PUBLIC_KEY


def test_the_w3c_canonical_forms_and_hashes_are_reproduced():
    credential = signing.canonicalize(W3C_CREDENTIAL)
    options = signing.canonicalize(W3C_PROOF_OPTIONS)

    assert credential.decode() == W3C_CANONICAL_CREDENTIAL
    assert options.decode() == W3C_CANONICAL_PROOF_OPTIONS
    assert hashlib.sha256(credential).hexdigest() == W3C_CREDENTIAL_HASH
    assert hashlib.sha256(options).hexdigest() == W3C_PROOF_OPTIONS_HASH


@pytest.mark.spec("SIG-01-002")
def test_the_w3c_signed_credential_verifies():
    signed = {
        **W3C_CREDENTIAL,
        "proof": {**W3C_PROOF_OPTIONS, "proofValue": W3C_PROOF_VALUE},
    }

    signing.verify(signed, VECTOR_PUBLIC_KEY)


def test_the_fep_canonical_forms_and_combined_hash_are_reproduced():
    document = signing.canonicalize(FEP_DOCUMENT)
    config = signing.canonicalize(
        {
            k: v
            for k, v in FEP_SIGNED_DOCUMENT["proof"].items()
            if k != "proofValue"
        }
    )

    assert document.decode() == FEP_CANONICAL_DOCUMENT
    assert config.decode() == FEP_CANONICAL_PROOF_CONFIG
    combined = (
        hashlib.sha256(config).digest() + hashlib.sha256(document).digest()
    )
    assert combined.hex() == FEP_COMBINED_HASH


@pytest.mark.spec("SIG-01-002")
def test_signing_the_fep_document_gives_the_published_signed_document():
    key = signing.SigningKey.from_secret_multibase(
        VECTOR_PRIVATE_KEY, FEP_KEY_ID
    )

    signed = signing.sign(FEP_DOCUMENT, key, created=CREATED)

    assert signed == FEP_SIGNED_DOCUMENT


def test_the_fep_signed_document_verifies():
    signing.verify(FEP_SIGNED_DOCUMENT, VECTOR_PUBLIC_KEY)


# --- Seeded keys --------------------------------------------------------------


@pytest.mark.spec("SIG-05-001")
def test_a_seeded_key_is_the_same_for_one_actor_id_and_differs_across_ids():
    first = signing.seeded_signing_key(ACTOR)
    again = signing.seeded_signing_key(ACTOR)
    other = signing.seeded_signing_key(OTHER_ACTOR)

    assert first.public_key_multibase == again.public_key_multibase
    assert first.public_key_multibase != other.public_key_multibase
    assert first.key_id == f"{ACTOR}#main-key" == signing.key_id_for(ACTOR)


def test_a_seeded_key_needs_an_actor_id():
    with pytest.raises(ValueError):
        signing.seeded_signing_key("")


def test_a_signing_key_needs_a_key_id():
    with pytest.raises(ValueError):
        signing.SigningKey.from_secret_multibase(VECTOR_PRIVATE_KEY, "")


def test_a_secret_key_with_the_public_codec_is_refused():
    with pytest.raises(VultronMultikeyError, match="multicodec prefix"):
        signing.SigningKey.from_secret_multibase(VECTOR_PUBLIC_KEY, FEP_KEY_ID)


# --- Signing --------------------------------------------------------------------


@pytest.mark.spec("SIG-01-002")
def test_a_proof_names_the_cryptosuite_purpose_and_key():
    proof = _signed_note()["proof"]

    assert proof["type"] == "DataIntegrityProof"
    assert proof["cryptosuite"] == "eddsa-jcs-2022"
    assert proof["proofPurpose"] == "assertionMethod"
    assert proof["verificationMethod"] == f"{ACTOR}#main-key"
    assert proof["created"] == CREATED
    assert proof["proofValue"].startswith("z")


@pytest.mark.parametrize(
    ("context", "expected"),
    [
        (
            "https://www.w3.org/ns/activitystreams",
            [
                "https://www.w3.org/ns/activitystreams",
                signing.DATA_INTEGRITY_CONTEXT,
            ],
        ),
        (_FEP_CONTEXT, _FEP_CONTEXT),
        (
            ["https://www.w3.org/ns/activitystreams", {"vul": "urn:x:"}],
            [
                "https://www.w3.org/ns/activitystreams",
                {"vul": "urn:x:"},
                signing.DATA_INTEGRITY_CONTEXT,
            ],
        ),
        (None, [signing.DATA_INTEGRITY_CONTEXT]),
    ],
)
def test_signing_adds_the_data_integrity_context_once(
    context: Any, expected: list[Any]
):
    document: dict[str, Any] = {"id": "urn:x:1", "type": "Note"}
    if context is not None:
        document["@context"] = context
    key = signing.seeded_signing_key(ACTOR)

    signed = signing.sign(document, key, created=CREATED)

    assert signed["@context"] == expected
    assert signed["proof"]["@context"] == expected
    signing.verify(signed, key.public_key_multibase)


def test_signing_leaves_the_input_unchanged():
    document = copy.deepcopy(FEP_DOCUMENT)
    document["@context"] = "https://www.w3.org/ns/activitystreams"
    before = copy.deepcopy(document)

    signing.sign(document, signing.seeded_signing_key(ACTOR), created=CREATED)

    assert document == before


def test_a_datetime_created_is_written_in_the_one_timestamp_form():
    created = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)

    signed = signing.sign(
        {"id": "urn:x:1"}, signing.seeded_signing_key(ACTOR), created=created
    )

    assert signed["proof"]["created"] == "2026-11-05T12:00:00.000000+00:00"


def test_a_proof_defaults_its_created_time_to_now():
    signed = signing.sign({"id": "urn:x:1"}, signing.seeded_signing_key(ACTOR))

    created = datetime.fromisoformat(signed["proof"]["created"])
    assert abs((datetime.now(UTC) - created).total_seconds()) < 60


@pytest.mark.parametrize(
    "document",
    [
        {"id": "urn:x:1", "proof": {}},
        ["not", "an", "object"],
        {"id": "urn:x:1", "count": 2**53},
        {"id": "urn:x:1", "count": -(2**53)},
        {"id": "urn:x:1", "ratio": float("nan")},
    ],
    ids=["has-a-proof", "not-an-object", "big-int", "big-negative-int", "nan"],
)
def test_signing_refuses_what_cannot_be_signed(document: Any):
    with pytest.raises(VultronUnsignableJsonError):
        signing.sign(document, signing.seeded_signing_key(ACTOR))


def test_an_empty_created_time_is_refused():
    with pytest.raises(VultronUnsignableJsonError, match="created"):
        signing.sign(
            {"id": "urn:x:1"}, signing.seeded_signing_key(ACTOR), created=""
        )


def test_only_an_object_carries_a_proof():
    with pytest.raises(VultronProofInvalidError, match="JSON object"):
        signing.verify(
            ["not", "an", "object"],  # type: ignore[arg-type]
            signing.seeded_signing_key(ACTOR).public_key_multibase,
        )


def test_the_largest_safe_integer_is_signed():
    key = signing.seeded_signing_key(ACTOR)
    signed = signing.sign(
        {"id": "urn:x:1", "count": 2**53 - 1, "low": -(2**53) + 1}, key
    )

    signing.verify(signed, key.public_key_multibase)


# --- Verification ----------------------------------------------------------------


def test_a_signed_note_verifies_with_its_authors_key():
    signing.verify(
        _signed_note(), signing.seeded_signing_key(ACTOR).public_key_multibase
    )


def test_the_verification_method_is_read_before_verifying():
    assert signing.proof_verification_method(_signed_note()) == (
        f"{ACTOR}#main-key"
    )


def _tamper_nested(doc: dict[str, Any]) -> None:
    doc["object"]["type"] = "Article"


def _tamper_top(doc: dict[str, Any]) -> None:
    doc["actor"] = OTHER_ACTOR


def _tamper_created(doc: dict[str, Any]) -> None:
    doc["proof"]["created"] = "2023-02-24T23:36:39Z"


def _tamper_method(doc: dict[str, Any]) -> None:
    doc["proof"]["verificationMethod"] = f"{OTHER_ACTOR}#main-key"


def _tamper_added_key(doc: dict[str, Any]) -> None:
    doc["summary"] = "added after signing"


@pytest.mark.spec("SIG-01-003")
@pytest.mark.parametrize(
    "tamper",
    [
        _tamper_nested,
        _tamper_top,
        _tamper_created,
        _tamper_method,
        _tamper_added_key,
    ],
    ids=["nested", "top-level", "created", "method", "added-key"],
)
def test_a_document_changed_after_signing_does_not_verify(tamper: Any):
    signed = _signed_note()
    tamper(signed)

    with pytest.raises(VultronProofInvalidError, match="does not verify"):
        signing.verify(
            signed, signing.seeded_signing_key(ACTOR).public_key_multibase
        )


def test_another_actors_key_does_not_verify():
    with pytest.raises(VultronProofInvalidError, match="does not verify"):
        signing.verify(
            _signed_note(),
            signing.seeded_signing_key(OTHER_ACTOR).public_key_multibase,
        )


def _drop_proof(doc: dict[str, Any]) -> None:
    del doc["proof"]


def _proof_set(doc: dict[str, Any]) -> None:
    doc["proof"] = [doc["proof"]]


def _proof_field(field: str, value: Any) -> Any:
    def tamper(doc: dict[str, Any]) -> None:
        if value is None:
            del doc["proof"][field]
        else:
            doc["proof"][field] = value

    return tamper


def _context_mismatch(doc: dict[str, Any]) -> None:
    doc["@context"] = [signing.DATA_INTEGRITY_CONTEXT]


@pytest.mark.parametrize(
    ("tamper", "message"),
    [
        (_drop_proof, "carries no proof"),
        (_proof_set, "one JSON object"),
        (_proof_field("type", "Ed25519Signature2020"), "type"),
        (_proof_field("cryptosuite", "eddsa-rdfc-2022"), "cryptosuite"),
        (_proof_field("proofPurpose", "authentication"), "proofPurpose"),
        (_proof_field("verificationMethod", None), "verificationMethod"),
        (_proof_field("proofValue", None), "proofValue"),
        (_proof_field("proofValue", "u" + "A" * 86), "proofValue"),
        (_proof_field("proofValue", "z0OIl"), "base58btc"),
        (_proof_field("created", 0), "created"),
        (_proof_field("created", "not a time"), "created"),
        (_proof_field("proofValue", "z" + "1" * 10), "64-byte"),
        (_context_mismatch, "@context"),
    ],
    ids=[
        "missing",
        "proof-set",
        "type",
        "cryptosuite",
        "purpose",
        "no-method",
        "no-value",
        "not-base58btc",
        "bad-base58",
        "created",
        "created-not-a-time",
        "short-signature",
        "context",
    ],
)
@pytest.mark.spec("SIG-03-002")
def test_a_malformed_proof_is_refused(tamper: Any, message: str):
    signed = _signed_note()
    tamper(signed)

    with pytest.raises(VultronProofInvalidError, match=message):
        signing.verify(
            signed, signing.seeded_signing_key(ACTOR).public_key_multibase
        )


def test_verification_refuses_an_integer_outside_the_safe_range():
    signed = _signed_note()
    signed["object"]["count"] = 2**53

    with pytest.raises(VultronUnsignableJsonError):
        signing.verify(
            signed, signing.seeded_signing_key(ACTOR).public_key_multibase
        )


# --- Multikey -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "message"),
    [
        (VECTOR_PUBLIC_KEY[1:], "'z' prefix"),
        ("z0OIl", "base58btc"),
        (VECTOR_PRIVATE_KEY, "multicodec prefix"),
        ("z" + base58.b58encode(b"\xed\x01" + bytes(31)).decode(), "32 bytes"),
    ],
    ids=["no-multibase-prefix", "bad-base58", "secret-key-codec", "short"],
)
def test_a_malformed_public_key_is_refused(value: str, message: str):
    with pytest.raises(VultronMultikeyError, match=message):
        signing.decode_public_key_multibase(value)


def test_a_public_key_round_trips_through_multibase():
    decoded = signing.decode_public_key_multibase(VECTOR_PUBLIC_KEY)

    assert signing.encode_public_key_multibase(decoded) == VECTOR_PUBLIC_KEY


def test_a_malformed_public_key_is_refused_at_verification():
    with pytest.raises(VultronMultikeyError):
        signing.verify(_signed_note(), "not-a-key")


# --- Strict JSON ------------------------------------------------------------------


def test_load_json_reads_a_signed_body():
    signed = _signed_note()

    loaded = signing.load_json(json.dumps(signed).encode())

    assert loaded == signed
    signing.verify(
        loaded, signing.seeded_signing_key(ACTOR).public_key_multibase
    )


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ('{"id": "a", "id": "b"}', "more than once"),
        ('{"object": {"type": "Note", "type": "Article"}}', "more than once"),
        ('{"ratio": NaN}', "NaN"),
        ('{"ratio": -Infinity}', "Infinity"),
        ('{"ratio": 1e400}', "too large"),
        ('{"id": ', "not JSON"),
    ],
    ids=[
        "duplicate-key",
        "nested-duplicate-key",
        "nan",
        "infinity",
        "overflow",
        "truncated",
    ],
)
def test_load_json_refuses_what_parsers_disagree_on(text: str, message: str):
    with pytest.raises(VultronUnsignableJsonError, match=message):
        signing.load_json(text)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ('{"count": ' + "1" * 5000 + "}", "not JSON"),
        (b'{"name": "\xff"}', "not JSON"),
        ("[" * 100_000 + "]" * 100_000, "nested too deeply"),
    ],
    ids=["too-many-digits", "not-utf8", "deep-nesting"],
)
def test_load_json_refuses_text_python_cannot_read(
    text: str | bytes, message: str
):
    with pytest.raises(VultronUnsignableJsonError, match=message):
        signing.load_json(text)


def test_a_value_nested_too_deeply_cannot_be_canonicalized():
    value: Any = []
    for _ in range(100_000):
        value = [value]

    with pytest.raises(VultronUnsignableJsonError, match="nested too deeply"):
        signing.canonicalize(value)


def test_base58_with_whitespace_is_refused():
    signed = _signed_note()
    signed["proof"]["proofValue"] += " "

    with pytest.raises(VultronMultikeyError, match="base58btc"):
        signing.decode_public_key_multibase(VECTOR_PUBLIC_KEY + "\n")
    with pytest.raises(VultronProofInvalidError, match="base58btc"):
        signing.verify(
            signed, signing.seeded_signing_key(ACTOR).public_key_multibase
        )


def test_a_created_time_that_is_not_a_time_is_refused_when_signing():
    with pytest.raises(VultronUnsignableJsonError, match="created"):
        signing.sign(
            {"id": "urn:x:1"},
            signing.seeded_signing_key(ACTOR),
            created=5,  # type: ignore[arg-type]
        )


@pytest.mark.spec("SIG-01-003")
def test_a_context_appended_after_signing_does_not_verify():
    """Stricter than W3C eddsa-jcs-2022, which would admit it (SIG-01-003)."""
    signed = _signed_note()
    signed["@context"] = [*signed["@context"], {"content": "urn:x:other"}]

    with pytest.raises(VultronProofInvalidError, match="does not verify"):
        signing.verify(
            signed, signing.seeded_signing_key(ACTOR).public_key_multibase
        )
