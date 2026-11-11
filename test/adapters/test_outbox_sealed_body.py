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
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""Sealing an outbound activity's body (VM-08-003), signed (SIG-01-001).

Module under test: ``vultron/adapters/outbox_sealed_body.py``.
"""

import json

import pytest

from test.support.objects import make
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.outbox_sealed_body import (
    OUTBOUND_DUMP_KWARGS,
    SealedOutboundBody,
    parse_sealed_body,
    read_sealed_body,
    seal_outbound_body,
    sealed_body_id,
)
from vultron.errors import VultronValidationError
from vultron.wire.as2 import signing
from vultron.wire.as2.errors import (
    VultronForeignAuthorError,
    VultronProofInvalidError,
    VultronUnsignableJsonError,
)
from vultron.wire.as2.factories import rm_invite_to_case_activity
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_ACTOR = "https://example.org/actors/coordinator"
_INVITEE = "https://example.org/actors/vendor"


@pytest.fixture
def dl():
    _dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_ACTOR)
    yield _dl
    _dl.clear_all()
    _dl.close()


def _invite(actor: str = _ACTOR):
    case = make(
        as_VulnerabilityCase,
        name="CVE-2026-0001",
        stub_summary="RCE in widget for stub test",
        attributed_to=_ACTOR,
    )
    return rm_invite_to_case_activity(
        invitee=_INVITEE, target=case, actor=actor, to=[_INVITEE]
    )


def _published_key(actor_id: str) -> str:
    key = signing.seeded_signing_key(actor_id)
    return signing.published_multikey(key, actor_id).public_key_multibase


def _unsigned(body: dict) -> dict:
    """*body* as it was before signing: no proof, its own ``@context``."""
    unsigned = {k: v for k, v in body.items() if k != "proof"}
    unsigned["@context"] = [
        entry
        for entry in body["@context"]
        if entry != signing.DATA_INTEGRITY_CONTEXT
    ]
    if len(unsigned["@context"]) == 1:
        [unsigned["@context"]] = unsigned["@context"]
    return unsigned


@pytest.mark.spec("VM-08-003")
def test_seal_stores_the_factory_dump_with_its_proof(dl):
    """The sealed text is the factory object's own dump, signed, and stored."""
    invite = _invite()

    body = seal_outbound_body(dl, invite)

    assert _unsigned(json.loads(body)) == json.loads(
        invite.model_dump_json(**OUTBOUND_DUMP_KWARGS)
    )
    stored = dl.read(sealed_body_id(invite.id_))
    assert isinstance(stored, SealedOutboundBody)
    assert stored.activity_id == invite.id_
    assert stored.body == body


@pytest.mark.spec("SIG-01-001")
@pytest.mark.spec("SIG-01-002")
def test_the_sealed_body_carries_its_authors_proof(dl):
    """The seal is signed with the actor's key, and the proof verifies."""
    body = json.loads(seal_outbound_body(dl, _invite()))

    proof = body["proof"]
    assert proof["type"] == signing.PROOF_TYPE
    assert proof["cryptosuite"] == signing.CRYPTOSUITE
    assert proof["proofPurpose"] == signing.PROOF_PURPOSE
    assert proof["verificationMethod"] == signing.key_id_for(_ACTOR)
    assert body["@context"][-1] == signing.DATA_INTEGRITY_CONTEXT
    signing.verify(body, _published_key(_ACTOR))


@pytest.mark.spec("SIG-01-003")
def test_the_sealed_proof_covers_the_nested_objects(dl):
    """Changing the inline case stub after sealing breaks the proof."""
    body = json.loads(seal_outbound_body(dl, _invite()))
    body["target"]["name"] = "changed after sealing"

    with pytest.raises(VultronProofInvalidError):
        signing.verify(body, _published_key(_ACTOR))


def test_seal_refuses_an_activity_naming_no_actor(dl):
    """An activity with no ``actor`` has no author to sign it, so no seal."""
    invite = _invite().model_copy(update={"actor": None})

    with pytest.raises(VultronUnsignableJsonError, match="names no actor"):
        seal_outbound_body(dl, invite)
    assert read_sealed_body(dl, invite.id_) is None


@pytest.mark.spec("SIG-05-004")
def test_seal_refuses_an_activity_another_actor_wrote(dl, monkeypatch):
    """An actor's store never signs or seals an activity naming another actor.

    The refusal comes before the signer computes any key and before the
    store is read or written.
    """
    foreign = _invite(actor=_INVITEE)
    computed: list[str] = []
    monkeypatch.setattr(signing, "seeded_signing_key", computed.append)

    with pytest.raises(VultronForeignAuthorError, match="SIG-05-004"):
        seal_outbound_body(dl, foreign)
    assert computed == [], "no key was computed for the foreign author"
    assert read_sealed_body(dl, foreign.id_) is None


@pytest.mark.spec("SIG-05-004")
def test_seal_refuses_an_inline_actor_naming_another_actor(dl):
    """An inline ``actor`` object is read by its id, and refused the same way."""
    foreign = _invite().model_copy(update={"actor": {"id": _INVITEE}})

    with pytest.raises(VultronForeignAuthorError):
        seal_outbound_body(dl, foreign)
    assert read_sealed_body(dl, foreign.id_) is None


@pytest.mark.spec("SIG-05-004")
def test_seal_accepts_the_owner_spelled_with_a_trailing_slash(dl):
    """``…/coordinator/`` is the store's own actor, signed with its own key."""
    invite = _invite(actor=f"{_ACTOR}/")

    body = json.loads(seal_outbound_body(dl, invite))

    assert body["proof"]["verificationMethod"] == signing.key_id_for(_ACTOR)
    signing.verify(body, _published_key(_ACTOR))


@pytest.mark.spec("SIG-05-004")
def test_sign_as_author_refuses_a_foreign_author():
    """The signer itself refuses a document its owner did not write."""
    document = {"id": "urn:uuid:x", "actor": _INVITEE}

    with pytest.raises(VultronForeignAuthorError):
        signing.sign_as_author(document, owner_id=_ACTOR)


@pytest.mark.spec("SIG-05-004")
def test_sign_as_author_refuses_an_empty_owner():
    """No owner is no one to sign as, never every actor."""
    with pytest.raises(VultronForeignAuthorError):
        signing.sign_as_author(
            {"id": "urn:uuid:x", "actor": _ACTOR}, owner_id=""
        )


@pytest.mark.spec("CS-13-002")
def test_a_sealed_proof_is_created_at_the_activitys_published_time(dl):
    """The proof takes the time the act wrote the activity, not a clock read.

    ADR-0176: an act reads the clock once, at its edge; the activity's
    ``published`` carries that act's time, so the proof is created then.
    """
    invite = _invite()
    body = json.loads(seal_outbound_body(dl, invite))

    assert body["proof"]["created"] == body["published"]
    signing.verify(body, _published_key(_ACTOR))


@pytest.mark.spec("SIG-05-001")
def test_one_activity_sealed_in_two_stores_carries_one_proof():
    """Sealing reads no clock, so one activity always seals to one text."""
    invite = _invite()
    bodies = []
    for _ in range(2):
        store = SqliteDataLayer("sqlite:///:memory:", actor_id=_ACTOR)
        try:
            bodies.append(seal_outbound_body(store, invite))
        finally:
            store.clear_all()
            store.close()

    assert bodies[0] == bodies[1]


@pytest.mark.parametrize(
    "published",
    [None, "", "2026-01-01", "2026-01-01T00:00:00", "not a time", 0],
    ids=["missing", "empty", "date-only", "no-offset", "text", "number"],
)
def test_sign_as_author_refuses_a_document_with_no_authored_time(published):
    """No ``published`` timestamp is no time to create a proof at.

    The signer refuses rather than reading a clock in its place (ADR-0176,
    ARCH-10-001).
    """
    document: dict = {"id": "urn:uuid:x", "actor": _ACTOR}
    if published is not None:
        document["published"] = published

    with pytest.raises(VultronUnsignableJsonError, match="published"):
        signing.sign_as_author(document, owner_id=_ACTOR)


def test_seal_refuses_an_activity_with_no_authored_time(dl):
    """A body with no ``published`` is refused, and nothing is stored."""
    invite = _invite().model_copy(update={"published": None})

    with pytest.raises(VultronUnsignableJsonError):
        seal_outbound_body(dl, invite)
    assert read_sealed_body(dl, invite.id_) is None


@pytest.mark.spec("VM-08-003")
def test_sealed_body_keeps_the_case_stub_inline(dl):
    """What is sealed is what the factory built: the Invite's case stub.

    Delivery reads the sealed body and not the activity record (#2655), so
    the stub reaches the wire exactly as the factory built it.
    """
    invite = _invite()
    body = json.loads(seal_outbound_body(dl, invite))
    assert isinstance(body["target"], dict)
    assert body["target"]["type"] == "VulnerabilityCaseStub"
    assert body["context"] == body["target"]["caseId"]


def test_seal_is_write_once_per_activity_id(dl):
    """A second seal under the same id returns the first body unchanged."""
    invite = _invite()
    first = seal_outbound_body(dl, invite)
    # A re-emission under the same id, dumped differently.
    reissued = invite.model_copy(update={"summary": "changed"})
    second = seal_outbound_body(dl, reissued)
    assert second == first, "the first body and its proof stand"
    assert read_sealed_body(dl, invite.id_).body == first  # type: ignore[union-attr]


def test_read_sealed_body_returns_none_when_unsealed(dl):
    assert read_sealed_body(dl, "urn:uuid:never-sealed") is None


def test_seal_refuses_an_activity_without_an_id(dl):
    class _NoId:
        def model_dump_json(self, **_kw):  # pragma: no cover - never reached
            return "{}"

    with pytest.raises(ValueError):
        seal_outbound_body(dl, _NoId())  # type: ignore[arg-type]


def test_sealed_body_id_is_derived_from_the_activity_id():
    assert sealed_body_id("urn:uuid:abc") == "urn:uuid:abc#sealed-body"


def test_parse_sealed_body_refuses_text_that_is_not_json():
    """A seal that is not JSON is a defect, reported as one (not a bare
    ``JSONDecodeError`` the retry loop would treat as transient)."""
    sealed = SealedOutboundBody(
        id_=sealed_body_id("urn:uuid:a1"), activity_id="urn:uuid:a1", body="{"
    )
    with pytest.raises(VultronValidationError, match="is not JSON"):
        parse_sealed_body(sealed)


def test_parse_sealed_body_refuses_a_json_scalar():
    sealed = SealedOutboundBody(
        id_=sealed_body_id("urn:uuid:a2"), activity_id="urn:uuid:a2", body="[]"
    )
    with pytest.raises(VultronValidationError, match="not a JSON object"):
        parse_sealed_body(sealed)
