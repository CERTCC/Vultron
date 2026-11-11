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
"""The inbox's verification stage, below the route (SIG-03, SIG-04-002).

The route-level refusals are in ``test_signed_delivery_refusal.py``; these
tests drive :class:`ProfileKeyProofVerifier` and :func:`decode_inbox_body`
directly, for the cases a route test reaches only indirectly.
"""

import asyncio
import json
from typing import Any

import pytest
from fastapi import FastAPI
from starlette.requests import Request

from test.support.signing import PublishedProfileFetcher, signed_body
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.db_record import object_to_record
from vultron.adapters.driven.http_actor_profile_fetch import (
    HttpActorProfileFetchAdapter,
)
from vultron.adapters.driving.fastapi.deps import (
    ACTOR_PROFILE_FETCHER_STATE,
    get_actor_profile_fetcher,
)
from vultron.adapters.driving.fastapi.inbox_orchestration import (
    FastAPIIngressAdapter,
)
from vultron.adapters.driving.fastapi.inbox_verification import (
    ProfileKeyProofVerifier,
    decode_inbox_body,
)
from vultron.core.models.actor import CoreActor
from vultron.core.models.verified_proof import VerifiedProof
from vultron.core.ports.proof_verification import ProofVerificationPort
from vultron.errors import VultronProofVerificationError
from vultron.wire.as2 import signing
from vultron.wire.as2.errors import (
    VultronJsonSyntaxError,
    VultronProofInvalidError,
    VultronRefusedJsonError,
)

RECEIVER = "https://receiver.example/actors/receiver"
MANAGER = "https://manager.example/actors/manager"
AUTHOR = "https://author.example/actors/author"


def _verifier(
    fetcher: PublishedProfileFetcher | None = None,
) -> ProfileKeyProofVerifier:
    return ProfileKeyProofVerifier(
        fetcher or PublishedProfileFetcher(), RECEIVER
    )


def _verify(document: dict[str, Any], **kwargs: Any) -> None:
    asyncio.run(_verifier(**kwargs).verify(document))


def _note(actor: str = AUTHOR) -> dict[str, Any]:
    return {
        "type": "Create",
        "id": "https://author.example/activities/1",
        "actor": actor,
        "object": {"type": "Note", "content": "signed"},
    }


def _announce(snapshot: dict[str, Any]) -> dict[str, Any]:
    return signed_body(
        {
            "type": "Announce",
            "id": "https://manager.example/announces/1",
            "actor": MANAGER,
            "object": {
                "type": "CaseLedgerEntry",
                "id": "https://manager.example/entries/1",
                "payloadSnapshot": snapshot,
            },
        }
    )


def test_the_stage_conforms_to_the_verification_port():
    assert isinstance(_verifier(), ProofVerificationPort)


@pytest.mark.spec("SIG-03-002")
def test_a_body_its_author_signed_verifies():
    _verify(signed_body(_note()))


@pytest.mark.spec("SIG-05-005")
def test_a_body_naming_no_actor_has_no_author_to_verify_it():
    body = signed_body({"type": "Create", "id": "x"}, author=AUTHOR)

    with pytest.raises(VultronProofInvalidError, match="names no actor"):
        _verify(body)


@pytest.mark.spec("SIG-04-002")
def test_a_relayed_entry_needs_both_proofs():
    _verify(_announce(signed_body(_note())))


def _published(actor_id: str) -> str:
    """The key *actor_id*'s profile publishes, as the fetcher serves it."""
    key = signing.seeded_signing_key(actor_id)
    return signing.published_multikey(key, actor_id).public_key_multibase


@pytest.mark.spec("SIG-03-004")
def test_the_stage_returns_the_proof_it_verified_and_its_key():
    verified = asyncio.run(_verifier().verify(signed_body(_note())))

    assert verified == (
        VerifiedProof(
            author_id=AUTHOR,
            verification_method=f"{AUTHOR}#main-key",
            public_key_multibase=_published(AUTHOR),
        ),
    )


@pytest.mark.spec("SIG-03-004")
def test_a_relayed_entry_returns_the_managers_proof_then_the_authors():
    verified = asyncio.run(_verifier().verify(_announce(signed_body(_note()))))

    assert [
        (proof.author_id, proof.verification_method) for proof in verified
    ] == [(MANAGER, f"{MANAGER}#main-key"), (AUTHOR, f"{AUTHOR}#main-key")]
    assert [proof.public_key_multibase for proof in verified] == [
        _published(MANAGER),
        _published(AUTHOR),
    ]


@pytest.mark.spec("SIG-04-002")
def test_a_relayed_snapshot_without_its_authors_proof_is_refused():
    with pytest.raises(VultronProofVerificationError) as refused:
        _verify(_announce(_note()))

    assert "payloadSnapshot" in str(refused.value)
    assert AUTHOR in str(refused.value)


@pytest.mark.spec("SIG-04-002")
def test_the_snapshot_author_must_publish_the_key():
    fetcher = PublishedProfileFetcher([MANAGER])

    with pytest.raises(VultronProofVerificationError, match="payloadSnapshot"):
        _verify(_announce(signed_body(_note())), fetcher=fetcher)

    assert fetcher.asked == [MANAGER, AUTHOR]


@pytest.mark.spec("SIG-04-002")
def test_the_managers_native_snapshot_is_checked_by_its_key():
    """A native entry's snapshot names the CASE_MANAGER and carries its proof."""
    fetcher = PublishedProfileFetcher([MANAGER])

    _verify(_announce(signed_body(_note(actor=MANAGER))), fetcher=fetcher)

    assert fetcher.asked == [MANAGER, MANAGER]


@pytest.mark.spec("SIG-04-002")
def test_the_managers_snapshot_without_its_proof_is_refused():
    """The outer proof does not stand in for the snapshot's own."""
    with pytest.raises(VultronProofVerificationError, match="payloadSnapshot"):
        _verify(_announce(_note(actor=MANAGER)))


@pytest.mark.spec("SIG-05-005")
@pytest.mark.parametrize(
    "snapshot",
    [
        {k: v for k, v in _note().items() if k != "actor"},
        {},
        {"semantic_type": "add_note_to_case"},
    ],
    ids=["activity-without-actor", "empty", "placeholder"],
)
def test_a_snapshot_naming_no_actor_is_refused(snapshot: dict[str, Any]):
    """Every activity names its signer, so a snapshot with none is refused."""
    with pytest.raises(VultronProofInvalidError, match="payloadSnapshot"):
        _verify(_announce(snapshot))


@pytest.mark.spec("SIG-04-002")
@pytest.mark.parametrize(
    ("object_key", "snapshot_key", "type_key"),
    [
        ("object_", "payloadSnapshot", "type"),
        ("object", "payload_snapshot", "type"),
        ("object_", "payload_snapshot", "type_"),
    ],
    ids=["object-field-name", "snapshot-field-name", "all-field-names"],
)
def test_a_snapshot_spelled_by_its_field_name_is_checked_too(
    object_key: str, snapshot_key: str, type_key: str
):
    """The parser reads a field by its name too, so the stage does."""
    announce = signed_body(
        {
            "type": "Announce",
            "id": "https://manager.example/announces/1",
            "actor": MANAGER,
            object_key: {
                type_key: "CaseLedgerEntry",
                "id": "https://manager.example/entries/1",
                snapshot_key: _note(),
            },
        }
    )

    with pytest.raises(VultronProofVerificationError, match="payloadSnapshot"):
        _verify(announce)


@pytest.mark.spec("SIG-04-002")
def test_a_snapshot_that_is_not_an_object_is_refused():
    announce = signed_body(
        {
            "type": "Announce",
            "id": "https://manager.example/announces/1",
            "actor": MANAGER,
            "object": {
                "type": "CaseLedgerEntry",
                "id": "https://manager.example/entries/1",
                "payloadSnapshot": "not an object",
            },
        }
    )

    with pytest.raises(VultronProofInvalidError, match="not a JSON object"):
        _verify(announce)


@pytest.mark.spec("SIG-04-002")
def test_a_snapshot_naming_a_blank_actor_is_refused():
    with pytest.raises(VultronProofInvalidError, match="payloadSnapshot"):
        _verify(_announce(_note(actor="")))


@pytest.mark.parametrize(
    ("raw", "error"),
    [
        (b"not json", VultronJsonSyntaxError),
        (b'{"x": NaN}', VultronJsonSyntaxError),
        (b"[1, 2]", VultronRefusedJsonError),
        (b"null", VultronRefusedJsonError),
        (b'{"a": 1, "a": 2}', VultronRefusedJsonError),
    ],
    ids=["not-json", "nan", "array", "null", "duplicate-key"],
)
def test_decoding_tells_a_syntax_fault_from_refused_json(
    raw: bytes, error: type[Exception]
):
    with pytest.raises(error):
        decode_inbox_body(raw)


@pytest.mark.parametrize(
    ("raw", "kind"),
    [
        (b"[]", "array"),
        (b'"x"', "string"),
        (b"true", "boolean"),
        (b"null", "null"),
        (b"3", "number"),
    ],
)
def test_a_value_that_is_not_an_object_is_named_by_its_kind(
    raw: bytes, kind: str
):
    with pytest.raises(VultronRefusedJsonError, match=f"not a JSON {kind}"):
        decode_inbox_body(raw)


def test_decoding_returns_the_object():
    assert decode_inbox_body(b'{"type": "Create"}') == {"type": "Create"}


def _request(app: FastAPI) -> Request:
    return Request({"type": "http", "app": app})


def test_an_app_without_a_harness_fetcher_uses_the_bounded_http_fetch():
    fetcher = get_actor_profile_fetcher(_request(FastAPI()))

    assert isinstance(fetcher, HttpActorProfileFetchAdapter)
    assert fetcher._fetcher._max_attempts == 1  # type: ignore[union-attr]


def test_a_harness_fetcher_installed_on_the_app_is_used():
    app = FastAPI()
    installed = PublishedProfileFetcher()
    setattr(app.state, ACTOR_PROFILE_FETCHER_STATE, installed)

    assert get_actor_profile_fetcher(_request(app)) is installed


@pytest.mark.spec("SIG-02-004")
def test_an_embedded_profile_reaches_storage_without_its_keys():
    """The ingress parse drops the key, so no record of the actor holds one.

    The record is the form every store path writes
    (:func:`object_to_record`), the inbox staging's included.
    """
    key = signing.published_multikey(
        signing.seeded_signing_key(AUTHOR), AUTHOR
    ).model_dump(mode="json", by_alias=True, exclude_none=True)
    body = signed_body(
        {
            **_note(),
            "published": "2026-01-01T00:00:00+00:00",
            "actor": {
                "type": "Organization",
                "id": AUTHOR,
                "name": "author",
                "assertionMethod": [key],
            },
        },
        author=AUTHOR,
    )
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=RECEIVER)

    activity = FastAPIIngressAdapter(dl).parse(body)

    assert activity is not None
    actor = activity.actor
    assert isinstance(actor, CoreActor), type(actor)
    record = object_to_record(actor)
    assert "assertionMethod" not in json.dumps(record.model_dump(mode="json"))
    assert "assertion_method" not in json.dumps(record.model_dump(mode="json"))
