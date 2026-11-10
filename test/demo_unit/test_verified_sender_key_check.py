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
"""The demo check that a receiver verified a sender by its published key.

``verify_receiver_verified_sender_key`` reads what the receiver recorded on
verifying (SIG-03-004) and compares the key with the one the sender's own
container publishes (SIG-02-001).  Each failure it can report is pinned
here against stub containers; the scenarios run the passing path.
"""

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.demo.helpers.polling import (
    received as polling_received,
    wait_for_verified_proofs,
)
from vultron.demo.helpers.verification import (
    records,
    verify_receiver_verified_sender_key,
)

_NODE = "http://vendor:7999/api/v2"
_RECEIVER = f"{_NODE}/actors/vendorco"
_SENDER = "http://finder:7999/api/v2/actors/finn"
_OFFER = "urn:uuid:offer"
_KEY_ID = f"{_SENDER}#main-key"
_KEY = "z6MkPublished"


def _proof(**updates: str) -> dict[str, str]:
    proof = {
        "author_id": _SENDER,
        "verification_method": _KEY_ID,
        "public_key_multibase": _KEY,
    }
    proof.update(updates)
    return proof


def _receiver(record: dict[str, Any] | None) -> MagicMock:
    """A receiver container serving *record* as the Offer's received record."""
    client = MagicMock()
    client.base_url = _NODE
    client.actor_id = _RECEIVER
    client.dl_path.side_effect = lambda key="", actor_id=None: f"{actor_id}|"
    rows = (
        {}
        if record is None
        else {ReceivedActivityRecord.build_id(_OFFER): record}
    )
    client.get.side_effect = lambda path, params=None: rows
    return client


def _archived(*proofs: dict[str, str]) -> dict[str, Any]:
    return {
        "type": "ReceivedActivityRecord",
        "stage": "archived",
        "received_body": json.dumps({"id": _OFFER, "type": "Offer"}),
        "verified_proofs": list(proofs),
    }


def _sender(key: str | None = _KEY, key_id: str = _KEY_ID) -> MagicMock:
    """A sender container whose profile publishes *key* under *key_id*."""
    client = MagicMock()
    client.base_url = "http://finder:7999/api/v2"
    methods = (
        []
        if key is None
        else [{"id": key_id, "type": "Multikey", "publicKeyMultibase": key}]
    )
    client.get.return_value = {"id": _SENDER, "assertionMethod": methods}
    return client


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failing wait gives up after one read."""
    real = polling_received.wait_for_verified_proofs

    def _once(client: Any, receiver_id: str, activity_id: str, **_: Any):
        return real(
            client,
            receiver_id,
            activity_id,
            timeout_seconds=0.0,
            poll_interval=0.0,
        )

    monkeypatch.setattr(records, "wait_for_verified_proofs", _once)


def _check(receiver: MagicMock, sender: MagicMock) -> Any:
    return verify_receiver_verified_sender_key(
        receiver, _RECEIVER, _OFFER, sender, _SENDER
    )


@pytest.mark.spec("SIG-03-004")
def test_a_key_the_sender_publishes_passes():
    proof = _check(_receiver(_archived(_proof())), _sender())

    assert proof.verification_method == _KEY_ID
    assert proof.public_key_multibase == _KEY


@pytest.mark.parametrize(
    "record",
    [
        None,
        {**_archived(_proof()), "stage": "held"},
        _archived(),
    ],
    ids=["no-record", "not-archived", "no-proofs"],
)
def test_no_archived_record_naming_a_proof_times_out(record: Any):
    with pytest.raises(AssertionError, match="SIG-03-004"):
        _check(_receiver(record), _sender())


def test_no_proof_by_the_sender_fails():
    other = "http://other:7999/api/v2/actors/eve"
    record = _archived(
        _proof(author_id=other, verification_method=f"{other}#main-key")
    )

    with pytest.raises(AssertionError, match="recorded no proof by"):
        _check(_receiver(record), _sender())


def test_a_key_of_another_actor_fails():
    record = _archived(
        _proof(verification_method="http://other:7999/actors/eve#main-key")
    )

    with pytest.raises(AssertionError, match="is not a key of"):
        _check(_receiver(record), _sender())


def test_a_key_the_profile_does_not_list_fails():
    with pytest.raises(AssertionError, match="lists no key"):
        _check(_receiver(_archived(_proof())), _sender(key=None))


def test_a_different_published_key_fails():
    with pytest.raises(AssertionError, match="a key other than"):
        _check(_receiver(_archived(_proof())), _sender(key="z6MkOther"))


def test_a_trailing_slash_on_the_published_key_id_still_matches():
    sender = _sender(key_id=f"{_SENDER}/#main-key")

    assert _check(_receiver(_archived(_proof())), sender).public_key_multibase


def test_the_wait_returns_the_typed_proofs():
    proofs = wait_for_verified_proofs(
        _receiver(_archived(_proof())), _RECEIVER, _OFFER
    )

    assert [p.author_id for p in proofs] == [_SENDER]
