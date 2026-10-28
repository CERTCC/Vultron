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
adapter builds each ``Add(Note)`` as its outbox would seal it.  Nothing signs
or verifies yet, so the inbox accepts every one of these bodies, and each test
is a strict ``xfail`` naming the Task that turns it green.  The Task that
lands verification (#5386) replaces each with a passing test that signs
through the shared test helper (#5384).
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
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.wire.as2.vocab.base.objects.object_types import as_Note

pytestmark = pytest.mark.integration

CASE_ID = "https://example.org/cases/signed-delivery-refusal"
_INBOX = "/api/v2/actors/coord/inbox/"
_NOT_VERIFIED = "the inbox does not verify proofs yet. Tracked by #5386."
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
    assert 400 <= response.status_code < 500, response.text
    assert "proof" in response.text


def _assert_nothing_stored(net: LedgerNetwork, activity_id: str) -> None:
    dl = net.stores[MANAGER]
    assert dl.read(activity_id) is None
    assert [
        entry
        for entry in ledger_entries(dl, CASE_ID)
        if entry.semantic_type == "add_note_to_case"
    ] == []


@pytest.mark.xfail(strict=True, reason=f"SIG-03-002: {_NOT_VERIFIED}")
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


@pytest.mark.xfail(
    strict=True,
    reason=(
        "SIG-01-003: nothing signs or verifies yet. Tracked by #5380 "
        "(proof form) and #5386 (refusal)."
    ),
)
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


@pytest.mark.xfail(
    strict=True,
    reason=(
        "SIG-02-001: no key is resolved from a profile yet. Tracked by "
        "#5383 (key resolution) and #5386 (refusal)."
    ),
)
@pytest.mark.spec("SIG-02-001")
def test_a_proof_naming_a_key_outside_the_authors_profile_is_refused(
    served_manager: tuple[TestClient, LedgerNetwork],
):
    client, net = served_manager
    body = _owner_note(net, "https://example.org/notes/other-key")
    body["proof"] = {
        **(body.get("proof") or _INVALID_PROOF),
        "verificationMethod": f"{BYSTANDER}#main-key",
    }

    response = client.post(_INBOX, json=body)

    _assert_refused_for_its_proof(response)
    _assert_nothing_stored(net, body["id"])


@pytest.mark.xfail(
    strict=True,
    reason=(
        "SIG-05-002: no key is resolved from a profile yet. Tracked by "
        "#5383 (key resolution) and #5386 (refusal)."
    ),
)
@pytest.mark.spec("SIG-05-002")
def test_an_author_whose_profile_cannot_be_read_is_refused(
    served_manager: tuple[TestClient, LedgerNetwork],
):
    client, net = served_manager
    body = _owner_note(net, "https://example.org/notes/no-profile")
    # The CASE_MANAGER holds no copy of the owner's profile, and the test app
    # reaches no network, so only a verifier that derives the owner's key
    # from its seed could admit the body.
    assert net.stores[MANAGER].read(OWNER) is None

    response = client.post(_INBOX, json=body)

    _assert_refused_for_its_proof(response)
    _assert_nothing_stored(net, body["id"])


@pytest.mark.xfail(strict=True, reason=f"SIG-03-003: {_NOT_VERIFIED}")
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
