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
"""An actor profile embedded in a received activity loses its keys (SIG-02-003).

A verifier trusts only a key fetched from the author's own profile URL, so the
parse edge drops ``assertionMethod`` from every actor profile a received
activity embeds: no parsed object, and so no stored copy, carries a peer's
key.  The received evidence keeps the body as received (VM-08-002).  A
profile the key lookup fetches keeps its keys: that parse is
``parse_fetched_object``'s (``test_http_actor_profile_fetch.py``).
"""

import logging
from typing import Any

import pytest

from vultron.core.models.actor import CoreActor
from vultron.wire.as2 import signing
from vultron.wire.as2.parser import parse_activity

AUTHOR = "https://example.org/actors/author"
PEER = "https://example.org/actors/peer"


def _key_of(actor_id: str) -> dict[str, Any]:
    return signing.published_multikey(
        signing.seeded_signing_key(actor_id), actor_id
    ).model_dump(mode="json", by_alias=True, exclude_none=True)


def _profile(actor_id: str, key_field: str = "assertionMethod") -> dict:
    return {
        "type": "Organization",
        "id": actor_id,
        "name": "embedded",
        key_field: [_key_of(actor_id)],
    }


def _body(**fields: Any) -> dict[str, Any]:
    return {
        "type": "Create",
        "id": "https://example.org/activities/embedded-1",
        "published": "2026-01-01T00:00:00+00:00",
        "actor": AUTHOR,
        "object": {
            "type": "Note",
            "id": "https://example.org/notes/n",
            "content": "n",
        },
        **fields,
    }


@pytest.mark.spec("SIG-02-004")
@pytest.mark.parametrize("key_field", ["assertionMethod", "assertion_method"])
def test_an_inline_sender_profile_is_parsed_without_its_keys(key_field: str):
    activity = parse_activity(_body(actor=_profile(AUTHOR, key_field)))

    actor = activity.actor
    assert isinstance(actor, CoreActor), type(actor)
    assert actor.assertion_method == []
    dumped = activity.model_dump(mode="json", by_alias=True)
    assert "assertionMethod" not in str(dumped)
    assert "assertion_method" not in str(dumped)


@pytest.mark.spec("SIG-02-004")
def test_an_embedded_peer_profile_is_parsed_without_its_keys():
    activity = parse_activity(_body(object=_profile(PEER)))

    peer = getattr(activity, "object_", None)
    assert isinstance(peer, CoreActor), type(peer)
    assert peer.assertion_method == []


@pytest.mark.spec("SIG-02-004")
def test_the_dropped_keys_are_reported_and_kept_in_the_evidence(
    caplog: pytest.LogCaptureFixture,
):
    with caplog.at_level(logging.INFO):
        activity = parse_activity(_body(actor=_profile(AUTHOR)))

    assert "assertionMethod" in caplog.text
    assert "assertionMethod" in (activity.received_evidence_json or "")
