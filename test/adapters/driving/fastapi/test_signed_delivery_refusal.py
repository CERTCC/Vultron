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
"""The inbox refuses an activity without a valid proof (SIG, ADR-0164).

The CASE_MANAGER is served by a real app, and the case owner's trigger
adapter builds each ``Add(Note)`` as its outbox seals it, signed.  The app
reads each author's key from the profile that author publishes
(``serve_published_profiles``), so only the proof decides.  An altered body
that must still carry a valid proof is re-signed through the shared test
helper (``resigned``).
"""

import json
from collections.abc import Iterator
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from test.adapters.driving.fastapi._redelivery import served_store
from test.core.use_cases.received._ledger_network import (
    BYSTANDER,
    MANAGER,
    OWNER,
    LedgerNetwork,
)
from test.support.ledger import ledger_entries
from test.support.signing import (
    AcceptingProofVerifier,
    resigned,
    serve_published_profiles,
)
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driving.fastapi.app import create_app
from vultron.adapters.driving.fastapi.deps import ACTOR_PROFILE_FETCHER_STATE
from vultron.adapters.driving.fastapi.routers.actors._inbox import (
    get_proof_verifier,
)
from vultron.core.models.actor import VultronOrganization
from vultron.core.models.multikey import Multikey
from vultron.wire.as2 import signing
from vultron.wire.as2.vocab.base.objects.object_types import as_Note

pytestmark = pytest.mark.integration

CASE_ID = "https://example.org/cases/signed-delivery-refusal"
_INBOX = "/api/v2/actors/coord/inbox/"
#: A proof of the right shape whose value verifies against no key.
_INVALID_PROOF = {
    "type": "DataIntegrityProof",
    "cryptosuite": "eddsa-jcs-2022",
    "verificationMethod": f"{OWNER}#main-key",
    "proofPurpose": "assertionMethod",
    "created": "2026-10-28T00:00:00Z",
    "proofValue": "z" + "1" * 86,
}


@pytest.fixture
def served_manager() -> Iterator[tuple[TestClient, LedgerNetwork]]:
    """The CASE_MANAGER's store served by a real app, plus its network."""
    net = LedgerNetwork(CASE_ID)
    with served_store(net.stores[MANAGER], MANAGER, "Coordinator") as (
        client,
        _emitter,
    ):
        yield client, net


def _owner_note(net: LedgerNetwork, note_id: str) -> dict[str, Any]:
    """The sealed body the owner's adapter builds for a new note."""
    dl = net.stores[OWNER]
    if dl.read(note_id) is None:
        dl.create(as_Note(id_=note_id, content="signed", context=CASE_ID))
    _activity_id, body = TriggerActivityAdapter(dl).add_note_to_case(
        note_id=note_id, case_id=CASE_ID, actor=OWNER, to=[MANAGER]
    )
    return cast(dict[str, Any], json.loads(body))


def _assert_refused_for_its_proof(response: Any) -> None:
    assert response.status_code == 422, response.text
    assert response.json()["detail"]["error"] == "ProofVerificationError"
    assert "proof" in response.text.lower()


def _assert_nothing_stored(net: LedgerNetwork, activity_id: str) -> None:
    dl = net.stores[MANAGER]
    assert dl.read(activity_id) is None
    assert [
        entry
        for entry in ledger_entries(dl, CASE_ID)
        if entry.semantic_type == "add_note_to_case"
    ] == []


@pytest.mark.spec("SIG-01-001")
def test_a_body_its_author_signed_is_accepted(
    served_manager: tuple[TestClient, LedgerNetwork],
):
    """The control for every refusal here: the sealed body passes."""
    client, net = served_manager
    body = _owner_note(net, "https://example.org/notes/accepted")

    response = client.post(_INBOX, json=body)

    assert response.status_code == 202, response.text


@pytest.mark.spec("SIG-03-001")
@pytest.mark.spec("SIG-03-002")
@pytest.mark.parametrize("proof", ["missing", "invalid"])
def test_an_activity_without_a_valid_proof_is_refused_and_stores_nothing(
    served_manager: tuple[TestClient, LedgerNetwork], proof: str
):
    client, net = served_manager
    body = _owner_note(net, f"https://example.org/notes/refused-{proof}")
    if proof == "missing":
        body.pop("proof", None)
    else:
        body["proof"] = _INVALID_PROOF

    response = client.post(_INBOX, json=body)

    _assert_refused_for_its_proof(response)
    _assert_nothing_stored(net, body["id"])


@pytest.mark.spec("SIG-01-003")
def test_a_body_changed_after_signing_is_refused(
    served_manager: tuple[TestClient, LedgerNetwork],
):
    client, net = served_manager
    body = _owner_note(net, "https://example.org/notes/changed")
    body["object"]["content"] = "changed after signing"

    response = client.post(_INBOX, json=body)

    _assert_refused_for_its_proof(response)
    _assert_nothing_stored(net, body["id"])


@pytest.mark.spec("SIG-02-001")
def test_a_proof_naming_a_key_outside_the_authors_profile_is_refused(
    served_manager: tuple[TestClient, LedgerNetwork],
):
    client, net = served_manager
    body = _owner_note(net, "https://example.org/notes/other-key")
    # Signed with the bystander's own key, so the signature verifies against
    # the key it names and only the key's owner is wrong.  The refusal must
    # name the foreign key and the author, so that a refusal for a bad
    # signature cannot pass this test.
    body = resigned(body, author=BYSTANDER)
    foreign_key = body["proof"]["verificationMethod"]
    assert foreign_key.startswith(BYSTANDER)

    response = client.post(_INBOX, json=body)

    _assert_refused_for_its_proof(response)
    assert foreign_key in response.text and OWNER in response.text
    _assert_nothing_stored(net, body["id"])


@pytest.mark.spec("SIG-05-002")
def test_an_author_whose_profile_cannot_be_read_is_refused(
    served_manager: tuple[TestClient, LedgerNetwork],
):
    client, net = served_manager
    body = _owner_note(net, "https://example.org/notes/no-profile")
    # The CASE_MANAGER holds no copy of the owner's profile, and no server
    # publishes it, so only a verifier that derives the owner's key from its
    # seed could admit the body.
    assert net.stores[MANAGER].read(OWNER) is None
    fetcher = serve_published_profiles(cast(Any, client.app), authors=[])

    response = client.post(_INBOX, json=body)

    _assert_refused_for_its_proof(response)
    assert fetcher.asked == [OWNER]
    # The refusal goes back to the sender, so it says nothing of the fetch.
    assert "no test server" not in response.text
    _assert_nothing_stored(net, body["id"])


@pytest.mark.spec("SIG-03-003")
def test_a_bad_proof_is_refused_before_the_schema_is_checked(
    served_manager: tuple[TestClient, LedgerNetwork],
):
    client, net = served_manager
    body = _owner_note(net, "https://example.org/notes/bad-proof-and-schema")
    body["proof"] = _INVALID_PROOF
    body["published"] = "not a timestamp"

    response = client.post(_INBOX, json=body)

    _assert_refused_for_its_proof(response)
    assert "published" not in response.text


@pytest.mark.spec("SIG-02-001")
@pytest.mark.spec("OID-01-006")
def test_an_author_spelled_with_a_trailing_slash_verifies_by_its_key(
    served_manager: tuple[TestClient, LedgerNetwork],
):
    """The author's id is compared normalised, so its own key verifies."""
    client, net = served_manager
    body = _owner_note(net, "https://example.org/notes/slashed-author")
    slashed = resigned(body, actor=f"{OWNER}/", author=OWNER)

    response = client.post(_INBOX, json=slashed)

    assert response.status_code == 202, response.text


@pytest.mark.spec("SIG-03-002")
def test_a_published_key_that_is_no_ed25519_multikey_is_a_proof_refusal(
    served_manager: tuple[TestClient, LedgerNetwork],
):
    """A key no proof can be checked against is a key that cannot be read."""
    client, net = served_manager
    body = _owner_note(net, "https://example.org/notes/bad-published-key")

    class _BadKeyProfiles:
        async def fetch_profile(
            self, actor_id: str, requester_id: str
        ) -> VultronOrganization:
            key = Multikey(
                id_=signing.key_id_for(OWNER),
                type_="Multikey",
                controller=OWNER,
                public_key_multibase="zNotAKey",
            )
            return VultronOrganization(
                id_=OWNER, name="owner", assertion_method=[key]
            )

    setattr(
        cast(Any, client.app).state,
        ACTOR_PROFILE_FETCHER_STATE,
        _BadKeyProfiles(),
    )

    response = client.post(_INBOX, json=body)

    _assert_refused_for_its_proof(response)
    assert "not an Ed25519 Multikey" in response.text
    _assert_nothing_stored(net, body["id"])


@pytest.mark.spec("IE-04-002")
def test_an_integer_beyond_the_safe_range_is_refused_as_content(
    served_manager: tuple[TestClient, LedgerNetwork],
):
    """A body no proof can cover is refused up front, 422, not at a seal."""
    client, net = served_manager
    body = _owner_note(net, "https://example.org/notes/huge-number")
    body["object"]["count"] = 2**53

    response = client.post(_INBOX, json=body)

    assert response.status_code == 422, response.text
    assert response.json()["detail"]["error"] == "ValidationError"
    assert "canonicalized" in response.text
    _assert_nothing_stored(net, body["id"])


@pytest.mark.spec("SIG-02-001")
def test_a_post_to_an_actor_this_node_does_not_host_fetches_no_key():
    """The addressed actor is found before any key is looked up."""
    net = LedgerNetwork(CASE_ID)
    app = create_app(docs_url=None, openapi_url=None)
    with TestClient(app) as client:
        fetcher = serve_published_profiles(app)
        body = _owner_note(net, "https://example.org/notes/no-such-actor")

        response = client.post("/api/v2/actors/nobody-here/inbox/", json=body)

    assert response.status_code == 404, response.text
    assert fetcher.asked == []


@pytest.mark.spec("SIG-03-003")
def test_the_stage_sees_the_body_as_received_before_the_parser(
    served_manager: tuple[TestClient, LedgerNetwork],
):
    """The verifier port gets the decoded body, proof included, first.

    With the stage replaced by the accepting stand-in, a schema fault is
    the parser's to refuse, after the stage has seen the body.
    """
    client, net = served_manager
    verifier = AcceptingProofVerifier()
    cast(Any, client.app).dependency_overrides[get_proof_verifier] = lambda: (
        verifier
    )
    body = _owner_note(net, "https://example.org/notes/seen-first")
    body["published"] = "not a timestamp"

    response = client.post(_INBOX, json=body)

    assert response.status_code == 422, response.text
    assert "published" in response.text
    assert verifier.verified == [body]
    assert "proof" in verifier.verified[0]


@pytest.mark.spec("SIG-02-003")
def test_a_stored_peer_key_is_ignored(
    served_manager: tuple[TestClient, LedgerNetwork],
):
    """The key comes only from the author's fetched profile.

    The CASE_MANAGER's store holds a copy of the owner's profile listing a
    key under the owner's key id that is not the owner's.  A verifier that
    read it would refuse the owner's genuine body; the fetched key admits it.
    """
    client, net = served_manager
    planted = Multikey(
        id_=signing.key_id_for(OWNER),
        type_="Multikey",
        controller=OWNER,
        public_key_multibase=signing.seeded_signing_key(
            BYSTANDER
        ).public_key_multibase,
    )
    net.stores[MANAGER].save(
        VultronOrganization(
            id_=OWNER, name="owner", assertion_method=[planted]
        )
    )
    body = _owner_note(net, "https://example.org/notes/stored-peer-key")

    response = client.post(_INBOX, json=body)

    assert response.status_code == 202, response.text
