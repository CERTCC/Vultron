#!/usr/bin/env python
"""Tests for an actor's ``inbox``/``outbox`` endpoint collections.

An actor's inbox and outbox are *addresses* (ActivityPub publishes them as
URIs); ``as_Actor`` wraps each in an ``as_OrderedCollection`` and ``CoreActor``
reduces it back to the URL.  Each arrival shape — a full collection dict, a
bare URI, ``None``, absent — must end up at the actor's inbox URL (ISSUE-3563
AC-5), and the serialized form must not change as a side effect of registering
the collection types (ARCH-23-003, ISSUE-3564 AC-5).
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

from vultron.core.models.actor import VultronOrganization
from vultron.wire.as2.vocab.base.objects.actors import as_Actor, as_Service
from vultron.wire.as2.vocab.base.objects.collections import (
    as_OrderedCollection,
)
from vultron.wire.as2.vocab.objects.vultron_actor import as_VultronOrganization

ACTOR_ID = "https://example.org/actors/alice"
_ACTOR_CLASSES = [as_Actor, as_Service, as_VultronOrganization]
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


@pytest.mark.parametrize("field_name", _ENDPOINTS)
@pytest.mark.parametrize(
    "shape", ["collection-dict", "bare-uri", "none", "absent"]
)
def test_core_actor_reduces_every_arrival_shape_to_the_url(field_name, shape):
    """``CoreActor`` keeps the URL of a collection dict, and ``None`` otherwise.

    Core models an endpoint as an address, not a list, so an absent or
    ``None`` endpoint stays ``None`` in core; the wire actor derives it.
    """
    data = {"id": ACTOR_ID, **_arrival_shapes(field_name)[shape]}

    actor = VultronOrganization.model_validate(data)

    expected = (
        None if shape in ("none", "absent") else f"{ACTOR_ID}/{field_name}"
    )
    assert getattr(actor, field_name) == expected


def test_core_actor_without_endpoints_renders_actor_derived_urls():
    """A core actor with no inbox reaches the wire at the actor's inbox URL."""
    core = VultronOrganization(id_=ACTOR_ID, name="Alice")

    wire = as_VultronOrganization.model_validate(core.model_dump())

    assert wire.inbox.id_ == f"{ACTOR_ID}/inbox"
    assert wire.outbox.id_ == f"{ACTOR_ID}/outbox"


@pytest.mark.spec("ARCH-23-003")
def test_serialized_endpoints_carry_only_address_type_and_items():
    """An endpoint serializes as an address, type and items — nothing else.

    Pins the wire form byte-for-byte on the fields this area owns.  In
    particular ``current`` is gone: it serialized as ``0``, but AS2's
    ``current`` is a reference to a page, not an integer (ISSUE-3563).
    """
    actor = as_VultronOrganization.model_validate(
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
