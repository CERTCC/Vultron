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
from typing import Any

import pytest
from fastapi import FastAPI
from starlette.requests import Request

from test.support.signing import PublishedProfileFetcher, signed_body
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.http_actor_profile_fetch import (
    HttpActorProfileFetchAdapter,
)
from vultron.adapters.driving.fastapi.deps import (
    ACTOR_PROFILE_FETCHER_STATE,
    get_actor_profile_fetcher,
)
from vultron.adapters.driving.fastapi.inbox_verification import (
    ProfileKeyProofVerifier,
    decode_inbox_body,
)
from vultron.core.ports.proof_verification import ProofVerificationPort
from vultron.errors import VultronProofVerificationError
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
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=RECEIVER)
    return ProfileKeyProofVerifier(
        dl, fetcher or PublishedProfileFetcher(), RECEIVER
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


@pytest.mark.spec("SIG-01-003")
def test_the_managers_own_snapshot_is_covered_by_the_outer_proof():
    """A snapshot naming the Announce's actor needs no second proof."""
    fetcher = PublishedProfileFetcher([MANAGER])

    _verify(_announce(_note(actor=MANAGER)), fetcher=fetcher)

    assert fetcher.asked == [MANAGER]


@pytest.mark.spec("SIG-04-002")
def test_a_snapshot_naming_no_actor_is_covered_by_the_outer_proof():
    """SIG-04-002 asks for an author's proof only when one is named."""
    fetcher = PublishedProfileFetcher([MANAGER])
    snapshot = {k: v for k, v in _note().items() if k != "actor"}

    _verify(_announce(snapshot), fetcher=fetcher)

    assert fetcher.asked == [MANAGER]


@pytest.mark.spec("SIG-04-002")
def test_an_empty_snapshot_is_covered_by_the_outer_proof():
    fetcher = PublishedProfileFetcher([MANAGER])

    _verify(_announce({}), fetcher=fetcher)

    assert fetcher.asked == [MANAGER]


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
