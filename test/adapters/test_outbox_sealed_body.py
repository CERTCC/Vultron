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

"""Sealing an outbound activity's body (VM-08-003).

Module under test: ``vultron/adapters/outbox_sealed_body.py``.
"""

import json

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.outbox_sealed_body import (
    OUTBOUND_DUMP_KWARGS,
    SealedOutboundBody,
    read_sealed_body,
    seal_outbound_body,
    sealed_body_id,
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


def _invite():
    case = as_VulnerabilityCase(name="CVE-2026-0001", attributed_to=_ACTOR)
    return rm_invite_to_case_activity(
        invitee=_INVITEE, target=case, actor=_ACTOR, to=[_INVITEE]
    )


@pytest.mark.spec("VM-08-003")
def test_seal_stores_the_exact_factory_dump(dl):
    """The sealed text is the factory object's own dump, byte for byte."""
    invite = _invite()

    body = seal_outbound_body(dl, invite)

    assert body == invite.model_dump_json(**OUTBOUND_DUMP_KWARGS)
    stored = dl.read(sealed_body_id(invite.id_))
    assert isinstance(stored, SealedOutboundBody)
    assert stored.activity_id == invite.id_
    assert stored.body == body


@pytest.mark.spec("VM-08-003")
def test_sealed_body_keeps_the_case_stub_inline(dl):
    """What is sealed is what the factory built: the Invite's case stub.

    The activity *record* cannot say this — persistence dehydrates ``target``
    to an id and read-back rehydrates it into the full stored case — which is
    why delivery reads the sealed body and not the record (#2655).
    """
    invite = _invite()
    body = json.loads(seal_outbound_body(dl, invite))
    assert isinstance(body["target"], dict)
    assert body["target"]["type"] == "VulnerabilityCase"
    assert body["context"] == body["target"]["id"]


def test_seal_is_write_once_per_activity_id(dl):
    """A second seal under the same id returns the first body unchanged."""
    invite = _invite()
    first = seal_outbound_body(dl, invite)
    # A re-emission under the same id, dumped differently.
    reissued = invite.model_copy(update={"summary": "changed"})
    second = seal_outbound_body(dl, reissued)
    assert second == first
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
