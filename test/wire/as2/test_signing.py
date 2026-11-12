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
import inspect
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import base58
import pytest

from test.support.signatures import signature_of
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.embargo_register.entry import EmbargoRegisterEntry
from vultron.core.states.embargo_register import EmbargoRegisterStatus
from vultron.wire.as2 import signing
from vultron.wire.as2.errors import (
    VultronJsonSyntaxError,
    VultronMultikeyError,
    VultronProofInvalidError,
    VultronRefusedJsonError,
    VultronUnsignableJsonError,
)
from vultron.wire.as2.factories.sync import announce_log_entry_activity
from vultron.wire.as2.vocab.examples import (
    _base as examples,
    case as case_examples,
    embargo as embargo_examples,
    participant as participant_examples,
    status as status_examples,
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


@pytest.mark.spec("CS-13-002")
def test_a_proof_takes_its_created_time_and_never_reads_a_clock():
    """``created`` is required: signing has no clock fallback (ADR-0176)."""
    created = signature_of(signing.sign).parameters["created"]

    assert created.kind is inspect.Parameter.KEYWORD_ONLY
    assert created.default is inspect.Parameter.empty


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
        signing.sign(
            document, signing.seeded_signing_key(ACTOR), created=CREATED
        )


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
        {"id": "urn:x:1", "count": 2**53 - 1, "low": -(2**53) + 1},
        key,
        created=CREATED,
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

    with pytest.raises(VultronRefusedJsonError):
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


def test_a_published_multikey_lists_the_keys_id_and_public_half():
    actor_id = "https://example.org/actors/vendorco"
    key = signing.seeded_signing_key(actor_id)

    published = signing.published_multikey(key, actor_id)

    assert published.model_dump(mode="json", by_alias=True) == {
        "id": f"{actor_id}#main-key",
        "type": "Multikey",
        "controller": actor_id,
        "publicKeyMultibase": key.public_key_multibase,
    }


def test_a_key_outside_its_controllers_document_is_not_published():
    key = signing.seeded_signing_key("https://example.org/actors/vendorco")

    with pytest.raises(ValueError, match="fragment of its controller"):
        signing.published_multikey(key, "https://example.org/actors/other")


# --- Strict JSON ------------------------------------------------------------------


def test_load_json_reads_a_signed_body():
    signed = _signed_note()

    loaded = signing.load_json(json.dumps(signed).encode())

    assert loaded == signed
    signing.verify(
        loaded, signing.seeded_signing_key(ACTOR).public_key_multibase
    )


@pytest.mark.parametrize(
    ("text", "error", "message"),
    [
        ('{"id": "a", "id": "b"}', VultronRefusedJsonError, "more than once"),
        (
            '{"object": {"type": "Note", "type": "Article"}}',
            VultronRefusedJsonError,
            "more than once",
        ),
        ('{"ratio": NaN}', VultronJsonSyntaxError, "NaN"),
        ('{"ratio": -Infinity}', VultronJsonSyntaxError, "Infinity"),
        ('{"ratio": 1e400}', VultronRefusedJsonError, "too large"),
        ('{"id": ', VultronJsonSyntaxError, "not JSON"),
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
def test_load_json_refuses_what_parsers_disagree_on(
    text: str, error: type[VultronUnsignableJsonError], message: str
):
    """RFC 8259 syntax faults and refused well-formed JSON raise apart.

    ``NaN``, ``Infinity`` and truncated text are not JSON by RFC 8259's
    grammar; a duplicate key and an overflowing number are JSON the
    receiver refuses to read, so a receiver can answer them differently.
    """
    with pytest.raises(error, match=message):
        signing.load_json(text)


@pytest.mark.parametrize(
    ("text", "error", "message"),
    [
        (
            '{"count": ' + "1" * 5000 + "}",
            VultronRefusedJsonError,
            "cannot be read",
        ),
        (b'{"name": "\xff"}', VultronJsonSyntaxError, "not JSON"),
        ('{"name": "a"}'.encode("utf-16"), VultronJsonSyntaxError, "utf-8"),
        ('{"name": "a"}'.encode("utf-32"), VultronJsonSyntaxError, "utf-8"),
        (b'\xef\xbb\xbf{"name": "a"}', VultronJsonSyntaxError, "BOM"),
        (
            "[" * 100_000 + "]" * 100_000,
            VultronRefusedJsonError,
            "nested too deeply",
        ),
    ],
    ids=[
        "too-many-digits",
        "not-utf8",
        "utf-16",
        "utf-32",
        "utf-8-bom",
        "deep-nesting",
    ],
)
def test_load_json_refuses_text_python_cannot_read(
    text: str | bytes, error: type[VultronUnsignableJsonError], message: str
):
    with pytest.raises(error, match=message):
        signing.load_json(text)


def test_a_value_nested_too_deeply_cannot_be_canonicalized():
    value: Any = []
    for _ in range(100_000):
        value = [value]

    with pytest.raises(VultronUnsignableJsonError, match="nested too deeply"):
        signing.canonicalize(value)


LIMIT = signing.MAX_JSON_DEPTH


def _nested(depth: int, opener: str = "[", closer: str = "]") -> str:
    return opener * depth + closer * depth


def _objects(depth: int) -> str:
    return '{"a":' * (depth - 1) + "{}" + "}" * (depth - 1)


def _mixed(depth: int) -> str:
    """Arrays holding objects, alternately, *depth* levels deep (even)."""
    pairs = depth // 2
    return '[{"a":' * (pairs - 1) + "[{}]" + "}]" * (pairs - 1)


def _depth(value: Any) -> int:
    """The nesting depth of *value*: ``[]`` is 1, a scalar 0."""
    if isinstance(value, dict):
        return 1 + max(map(_depth, value.values()), default=0)
    if isinstance(value, list):
        return 1 + max(map(_depth, value), default=0)
    return 0


@pytest.mark.parametrize(
    "text",
    [_nested(LIMIT), _objects(LIMIT), _mixed(LIMIT)],
    ids=["arrays", "objects", "mixed"],
)
def test_load_json_reads_nesting_at_the_limit(text: str):
    assert _depth(signing.load_json(text)) == LIMIT


@pytest.mark.parametrize(
    "text",
    [
        _nested(LIMIT + 1),
        _objects(LIMIT + 1),
        "[" + _mixed(LIMIT) + "]",
        '["text", ' + _nested(LIMIT) + "]",
    ],
    ids=["arrays", "objects", "mixed", "after-a-string"],
)
def test_load_json_refuses_nesting_past_the_limit(text: str):
    """The limit is the code's own, whatever the Python version or stack."""
    with pytest.raises(
        VultronRefusedJsonError, match=f"more than {LIMIT} levels"
    ):
        signing.load_json(text)


@pytest.mark.parametrize(
    "text",
    [
        '["' + "[{" * LIMIT + '"]',
        '{"' + "{[" * LIMIT + '": "' + "]}" * LIMIT + '"}',
        '["\\"' + "[" * LIMIT + '"]',
        '["\\\\", "' + "{" * LIMIT + '"]',
    ],
    ids=[
        "in-a-value",
        "in-a-key",
        "after-an-escaped-quote",
        "after-an-escape",
    ],
)
def test_brackets_in_a_string_are_not_nesting(text: str):
    assert _depth(signing.load_json(text)) == 1


def test_an_escaped_backslash_ends_before_the_closing_quote():
    """``"\\\\"`` is a whole string, so the brackets after it nest."""
    with pytest.raises(VultronRefusedJsonError, match="nested too deeply"):
        signing.load_json('["\\\\", ' + _nested(LIMIT) + "]")


def test_wide_json_with_many_brackets_is_not_deep():
    """More openers than the limit, side by side, is shallow nesting."""
    text = "[" + ", ".join(["[{}]"] * LIMIT) + "]"

    assert _depth(signing.load_json(text)) == 3


def test_text_nested_past_the_limit_is_refused_even_when_not_json():
    """The check runs before the parse, so it does not wait for the syntax."""
    with pytest.raises(VultronRefusedJsonError, match="nested too deeply"):
        signing.load_json("[" * (LIMIT + 1))


def test_unterminated_string_text_is_not_json():
    """A string that never closes hides no nesting and is not JSON."""
    with pytest.raises(VultronJsonSyntaxError, match="not JSON"):
        signing.load_json('["' + "[" * (LIMIT + 1))


def test_a_stack_that_runs_out_below_the_limit_is_still_a_refusal(
    monkeypatch: pytest.MonkeyPatch,
):
    """The ``RecursionError`` catch stays as the second line of defence."""

    def overflow(*args: Any, **kwargs: Any) -> Any:
        raise RecursionError("maximum recursion depth exceeded")

    # A namespace only signing sees, not the process-wide json module.
    monkeypatch.setattr(
        signing,
        "json",
        SimpleNamespace(loads=overflow, JSONDecodeError=json.JSONDecodeError),
    )

    with pytest.raises(VultronRefusedJsonError, match="nested too deeply"):
        signing.load_json("[[]]")


def _full_case_announcement() -> str:
    """``Announce(CaseLedgerEntry(Create(VulnerabilityCase)))`` as JSON text.

    The deepest body the demos deliver is a ledger entry announced to a
    participant, whose snapshot is an activity carrying the whole case.  This
    one's case holds a report, a case status, an active embargo, and three
    participants with roles, statuses and embargo consent rows.
    """
    embargo = embargo_examples.embargo_event()
    participants = [
        participant_examples.vendor_participant(),
        participant_examples.finder_participant(),
        participant_examples.coordinator_participant(),
    ]
    for participant in participants:
        participant.write_uninvited_rows([embargo.id_])
    case = examples.case(
        vulnerability_reports=[examples.gen_report()],
        case_participants=participants,
        actor_participant_index={p.attributed_to: p.id_ for p in participants},
        case_statuses=[status_examples.case_status()],
        embargo_register=[
            EmbargoRegisterEntry(
                embargo=embargo, status=EmbargoRegisterStatus.ACTIVE
            )
        ],
    )
    create = case_examples.create_case().model_copy(update={"object_": case})
    snapshot = json.loads(
        create.model_dump_json(by_alias=True, exclude_none=True)
    )
    record = HashChainLedgerRecord(
        case_id=case.id_,
        log_index=0,
        object_id=snapshot["id"],
        semantic_type="create_case",
        payload_snapshot=snapshot,
        prev_log_hash=case.genesis_hash,
        received_at=examples.EXAMPLE_TIMESTAMP,
    )
    announcement = announce_log_entry_activity(
        record.to_ledger_entry(),
        actor=examples.case_actor().id_,
        at=examples.EXAMPLE_TIMESTAMP,
    )
    return announcement.model_dump_json(by_alias=True, exclude_none=True)


def test_a_full_case_in_an_activity_nests_far_below_the_limit():
    """Real bodies keep wide headroom under the limit.

    A model change that nests a body much deeper fails here first, before
    a real body nears the limit and is refused.
    """
    body = signing.load_json(_full_case_announcement())

    assert body["object"]["payloadSnapshot"]["object"]["caseParticipants"]
    assert _depth(body) < LIMIT // 4


def test_base58_with_whitespace_is_refused():
    signed = _signed_note()
    signed["proof"]["proofValue"] += " "

    with pytest.raises(VultronMultikeyError, match="base58btc"):
        signing.decode_public_key_multibase(VECTOR_PUBLIC_KEY + "\n")
    with pytest.raises(VultronProofInvalidError, match="base58btc"):
        signing.verify(
            signed, signing.seeded_signing_key(ACTOR).public_key_multibase
        )


#: ``created`` values Data Integrity refuses: it requires an XML Schema
#: ``dateTimeStamp``, a full date-time with an explicit offset (CS-13-006).
NOT_TIMESTAMPS = [
    "not a time",
    "2026-01-01",
    "2026-01-01T00:00:00",
    "20260101T000000Z",
    "2026-W01-1",
    "2026-01-01 00:00:00Z",
    "2026-01-01T00:00Z",
    "2026-02-30T00:00:00Z",
]
NOT_TIMESTAMP_IDS = [
    "words",
    "date-only",
    "no-offset",
    "basic-format",
    "week-date",
    "space-separator",
    "no-seconds",
    "no-such-day",
]


@pytest.mark.parametrize(
    "created", [5, *NOT_TIMESTAMPS], ids=["int", *NOT_TIMESTAMP_IDS]
)
def test_a_created_time_that_is_not_a_time_is_refused_when_signing(
    created: Any,
):
    with pytest.raises(VultronUnsignableJsonError, match="created"):
        signing.sign(
            {"id": "urn:x:1"},
            signing.seeded_signing_key(ACTOR),
            created=created,
        )


@pytest.mark.parametrize("created", NOT_TIMESTAMPS, ids=NOT_TIMESTAMP_IDS)
def test_a_created_time_that_is_not_a_time_is_refused_when_verifying(
    created: str,
):
    signed = _signed_note()
    signed["proof"]["created"] = created

    with pytest.raises(VultronProofInvalidError, match="created"):
        signing.verify(
            signed, signing.seeded_signing_key(ACTOR).public_key_multibase
        )


@pytest.mark.parametrize(
    "created",
    [
        "2023-02-24T23:36:38Z",
        "2023-02-24T23:36:38.123Z",
        "2023-02-24T23:36:38-05:00",
    ],
    ids=["utc", "fraction", "offset"],
)
def test_a_created_string_that_sign_accepts_verifies(created: str):
    """Signer and verifier agree on what a created time is (SIG-05-003)."""
    key = signing.seeded_signing_key(ACTOR)
    signed = signing.sign({"id": "urn:x:1"}, key, created=created)

    assert signed["proof"]["created"] == created
    signing.verify(signed, key.public_key_multibase)


def test_a_bare_multibase_prefix_is_refused():
    signed = _signed_note()
    signed["proof"]["proofValue"] = "z"

    with pytest.raises(VultronMultikeyError, match="base58btc"):
        signing.decode_public_key_multibase("z")
    with pytest.raises(VultronProofInvalidError, match="base58btc"):
        signing.verify(
            signed, signing.seeded_signing_key(ACTOR).public_key_multibase
        )


@pytest.mark.parametrize(
    "text",
    ['{"id": "a", "id": "b"}', '{"ratio": NaN}', '{"ratio": 1e400}'],
    ids=["duplicate-key", "nan", "overflow"],
)
def test_a_refused_kind_of_json_is_not_reported_as_unreadable(text: str):
    """The refusal names its reason; it is not re-wrapped as "not JSON"."""
    with pytest.raises(VultronUnsignableJsonError) as refused:
        signing.load_json(text)

    assert not str(refused.value).startswith("not JSON")


@pytest.mark.spec("SIG-01-003")
def test_a_context_appended_after_signing_does_not_verify():
    """Stricter than W3C eddsa-jcs-2022, which would admit it (SIG-01-003)."""
    signed = _signed_note()
    signed["@context"] = [*signed["@context"], {"content": "urn:x:other"}]

    with pytest.raises(VultronProofInvalidError, match="does not verify"):
        signing.verify(
            signed, signing.seeded_signing_key(ACTOR).public_key_multibase
        )
