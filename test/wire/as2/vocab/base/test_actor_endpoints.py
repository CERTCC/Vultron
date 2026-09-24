#!/usr/bin/env python
"""Tests for an actor's ``inbox``/``outbox`` endpoint collections.

An actor's inbox and outbox are *addresses* (ActivityPub publishes them as
URIs); the AS2 ``as_Actor`` branch wraps each in an ``as_OrderedCollection``,
and ``CoreActor`` — which the Vultron actor types now are on the wire too
(ADR-0099) — reduces it to the URL.  Each arrival shape — a full collection
dict, a bare URI, ``None``, absent — must end up at the actor's inbox URL
(ISSUE-3563 AC-5), and the serialized form must not change as a side effect of
registering the collection types (ARCH-23-003, ISSUE-3564 AC-5).
"""

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

import json
from typing import Any

import pytest

from vultron.core.models.actor import (
    VultronApplication,
    VultronGroup,
    VultronOrganization,
    VultronPerson,
    VultronService,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor, as_Service
from vultron.wire.as2.vocab.base.objects.collections import (
    as_OrderedCollection,
)

ACTOR_ID = "https://example.org/actors/alice"
_ACTOR_CLASSES = [as_Actor, as_Service]
_CORE_ACTOR_CLASSES = [
    VultronPerson,
    VultronOrganization,
    VultronService,
    VultronApplication,
    VultronGroup,
]
_ENDPOINTS = ["inbox", "outbox"]


def _arrival_shapes(field_name: str) -> dict[str, dict[str, Any]]:
    """Return the ways an endpoint can arrive, keyed by a readable id."""
    url = f"{ACTOR_ID}/{field_name}"
    return {
        "collection-dict": {
            field_name: {"type": "OrderedCollection", "id": url, "items": []}
        },
        "bare-uri": {field_name: url},
        "none": {field_name: None},
        "absent": {},
    }


@pytest.mark.parametrize("actor_cls", _ACTOR_CLASSES)
@pytest.mark.parametrize("field_name", _ENDPOINTS)
@pytest.mark.parametrize(
    "shape", ["collection-dict", "bare-uri", "none", "absent"]
)
def test_every_arrival_shape_resolves_to_the_actor_endpoint_url(
    actor_cls, field_name, shape
):
    """Each arrival shape yields a wire collection at ``{actor_id}/{field}``.

    ``absent`` and ``none`` previously produced a random ``urn:uuid:``:
    the field's default factory gave the collection an id, so the
    ``id_ is None`` test meant to derive it from the actor never fired.
    """
    data = {"id": ACTOR_ID, **_arrival_shapes(field_name)[shape]}

    actor = actor_cls.model_validate(data)

    collection = getattr(actor, field_name)
    assert type(collection) is as_OrderedCollection
    assert collection.id_ == f"{ACTOR_ID}/{field_name}"


@pytest.mark.parametrize("actor_cls", _CORE_ACTOR_CLASSES)
@pytest.mark.parametrize("field_name", _ENDPOINTS)
@pytest.mark.parametrize(
    "shape", ["collection-dict", "bare-uri", "none", "absent"]
)
def test_core_actor_reduces_every_arrival_shape_to_the_url(
    actor_cls, field_name, shape
):
    """``CoreActor`` holds every arrival shape as the ``{actor_id}/{field}`` URL.

    Core models an endpoint as an address, not a list: a collection dict
    reduces to its ``id``, and an absent or ``None`` endpoint is derived from
    the actor's ``id_``.  The Vultron actor types are the wire form too
    (ADR-0099), so without the derivation they would publish ``null`` where
    ActivityPub requires an inbox and outbox (ISSUE-3616).
    """
    data = {"id": ACTOR_ID, **_arrival_shapes(field_name)[shape]}

    actor = actor_cls.model_validate(data)

    assert getattr(actor, field_name) == f"{ACTOR_ID}/{field_name}"


@pytest.mark.parametrize("field_name", _ENDPOINTS)
def test_core_actor_serializes_derived_endpoints(field_name):
    """A constructed actor with no endpoints publishes the derived URLs.

    Checked under ``exclude_unset`` too: the derived value is recorded as set,
    so a dump that drops defaults still carries the address (ISSUE-3616).
    """
    actor = VultronOrganization(id_=ACTOR_ID, name="Alice")

    expected = f"{ACTOR_ID}/{field_name}"
    assert json.loads(actor.model_dump_json(by_alias=True))[field_name] == (
        expected
    )
    assert actor.model_dump(exclude_unset=True)[field_name] == expected


@pytest.mark.parametrize("field_name", _ENDPOINTS)
def test_core_actor_rederives_an_endpoint_reassigned_to_none(field_name):
    """Assigning ``None`` cannot leave an actor without an endpoint."""
    actor = VultronOrganization(id_=ACTOR_ID, name="Alice")

    setattr(actor, field_name, None)

    assert getattr(actor, field_name) == f"{ACTOR_ID}/{field_name}"


@pytest.mark.spec("ARCH-23-003")
def test_serialized_endpoints_carry_only_address_type_and_items():
    """An endpoint serializes as an address, type and items — nothing else.

    Pins the wire form byte-for-byte on the fields this area owns.  In
    particular ``current`` is gone: it serialized as ``0``, but AS2's
    ``current`` is a reference to a page, not an integer (ISSUE-3563).
    """
    actor = as_Service.model_validate(
        {
            "id": ACTOR_ID,
            "inbox": f"{ACTOR_ID}/inbox",
            "outbox": f"{ACTOR_ID}/outbox",
        }
    )

    dumped = json.loads(actor.to_json())

    for field_name in _ENDPOINTS:
        endpoint = dumped[field_name]
        endpoint.pop("published")
        endpoint.pop("updated")
        assert endpoint == {
            "@context": "https://www.w3.org/ns/activitystreams",
            "id": f"{ACTOR_ID}/{field_name}",
            "type": "OrderedCollection",
            "items": [],
        }


@pytest.mark.parametrize("actor_cls", _ACTOR_CLASSES)
def test_unmodelled_actor_collections_are_tolerated_and_not_echoed(actor_cls):
    """A remote actor's ``followers``/``following`` URIs parse and are dropped.

    Vultron no longer models these collections (ISSUE-3563), so a remote
    actor publishing them must still validate, and must not have them
    re-emitted as if Vultron owned them.
    """
    actor = actor_cls.model_validate(
        {
            "id": ACTOR_ID,
            "followers": f"{ACTOR_ID}/followers",
            "following": f"{ACTOR_ID}/following",
            "liked": f"{ACTOR_ID}/liked",
        }
    )

    dumped = json.loads(actor.to_json())

    assert dumped["inbox"]["id"] == f"{ACTOR_ID}/inbox"
    assert {"followers", "following", "liked"}.isdisjoint(dumped)
