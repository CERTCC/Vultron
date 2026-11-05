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
"""A seeded private key never reaches a log or an API response (ENC-01-007).

The private key is searched for in every encoding it could be written in:
hex, base64, base64url, base58btc multibase (the ``secretKeyMultibase``
form) and the ``bytes`` repr.
"""

import base64
import logging
import pickle
from collections.abc import Iterator

import base58
import pytest

from test.adapters.driving.fastapi._redelivery import served_store
from vultron.adapters.driven.actor_hosts import canonical_actor_uri
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.wire.as2 import signing

_SEGMENT = "key-disclosure-vendor"


def _secret_encodings(actor_id: str) -> list[str]:
    seed = signing._seed_for(actor_id)
    return [
        seed.hex(),
        seed.hex().upper(),
        base64.b64encode(seed).decode(),
        base64.urlsafe_b64encode(seed).decode().rstrip("="),
        "z" + base58.b58encode(b"\x80\x26" + seed).decode(),
        base58.b58encode(seed).decode(),
        repr(seed),
    ]


def _assert_discloses_nothing(text: str, actor_id: str) -> None:
    for encoding in _secret_encodings(actor_id):
        assert encoding not in text, "a private key encoding was disclosed"


def test_the_search_finds_a_disclosed_key():
    """Each encoding is findable, so a clean result is not vacuous."""
    actor_id = canonical_actor_uri(_SEGMENT)
    for encoding in _secret_encodings(actor_id):
        with pytest.raises(AssertionError):
            _assert_discloses_nothing(f"leaked: {encoding}", actor_id)


@pytest.mark.spec("ENC-01-007")
def test_a_signing_key_shows_only_its_public_half():
    actor_id = canonical_actor_uri(_SEGMENT)
    key = signing.seeded_signing_key(actor_id)

    shown = f"{key!r} {key!s} {key} %s" % (key,)

    _assert_discloses_nothing(shown, actor_id)
    assert key.public_key_multibase in shown
    with pytest.raises(TypeError):
        pickle.dumps(key)


def _fail_with(key: signing.SigningKey) -> None:
    raise RuntimeError(f"signing failed for {key}")


@pytest.fixture
def served_actor(tmp_path) -> Iterator[tuple[str, object]]:
    actor_id = canonical_actor_uri(_SEGMENT)
    dl = SqliteDataLayer(
        f"sqlite:///{tmp_path / 'vendor.db'}", actor_id=actor_id
    )
    with served_store(dl, actor_id, _SEGMENT) as (client, _emitter):
        yield actor_id, client


@pytest.mark.spec("ENC-01-007")
def test_a_seeded_private_key_reaches_no_log_and_no_api_response(
    served_actor, caplog: pytest.LogCaptureFixture
):
    actor_id, client = served_actor
    caplog.set_level(logging.DEBUG)
    key = signing.seeded_signing_key(actor_id)

    signed = signing.sign(
        {"id": f"{actor_id}/activities/1", "type": "Create"}, key
    )
    signing.verify(signed, key.public_key_multibase)
    logging.getLogger(__name__).debug("signing with %s, %r", key, key)
    responses = [
        client.get(f"/api/v2/actors/{_SEGMENT}/profile"),
        client.get(f"/api/v2/actors/{_SEGMENT}"),
        client.get("/api/v2/actors/"),
    ]

    try:
        _fail_with(key)
    except RuntimeError:
        logging.getLogger(__name__).exception("failed", extra={"key": key})

    assert caplog.records, "nothing was logged, so the check is vacuous"
    formatter = logging.Formatter()
    for record in caplog.records:
        # The formatted record carries exception text; vars() carries every
        # extra= field, rendered as a handler that prints them would.
        _assert_discloses_nothing(formatter.format(record), actor_id)
        _assert_discloses_nothing(repr(vars(record)), actor_id)
    for response in responses:
        assert response.status_code == 200, response.text
        _assert_discloses_nothing(response.text, actor_id)
