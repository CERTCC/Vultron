#!/usr/bin/env python
"""Tests for an actor's ``inbox``/``outbox`` endpoint collections.

An actor's inbox and outbox are *addresses* (ActivityPub publishes them as
URIs); the AS2 ``as_Actor`` branch wraps each in an ``as_OrderedCollection``,
and ``CoreActor`` — which the Vultron actor types now are on the wire too
(ADR-0099) — reduces it to the URL.  Each arrival shape — a full collection
dict, a bare URI, ``None``, absent, a blank string, an id-less collection —
must end up at the actor's inbox URL (ISSUE-3563 AC-5), and the serialized
form must not change as a side effect of registering the collection types
(ARCH-23-003, ISSUE-3564 AC-5).
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
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from test.support.clock import SteppingClock
from vultron.core.models import _helpers
from vultron.core.models._helpers import INBOUND_CONTEXT_KEY, now_utc
from vultron.core.models.actor import (
    VultronApplication,
    VultronGroup,
    VultronOrganization,
    VultronPerson,
    VultronService,
)
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.objects.actors import (
    as_Actor,
    as_Application,
    as_Group,
    as_Organization,
    as_Person,
    as_Service,
)
from vultron.wire.as2.vocab.base.objects.collections import (
    as_OrderedCollection,
)

ACTOR_ID = "https://example.org/actors/alice"
_ACTOR_CLASSES = [as_Actor, as_Service]
_ALL_WIRE_ACTOR_CLASSES = [
    as_Actor,
    as_Application,
    as_Group,
    as_Organization,
    as_Person,
    as_Service,
]
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
        "empty-string": {field_name: ""},
        "blank-string": {field_name: "   "},
        "idless-collection-dict": {
            field_name: {"type": "OrderedCollection", "items": []}
        },
        # What the parser hands over for an inline id-less collection: a
        # model whose ``id_`` came from ``default_factory``, never set.
        "idless-collection-model": {field_name: as_OrderedCollection()},
    }


_SHAPES = list(_arrival_shapes("inbox"))
_ARRIVED_AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


@pytest.mark.parametrize("actor_cls", _ACTOR_CLASSES)
@pytest.mark.parametrize("field_name", _ENDPOINTS)
@pytest.mark.parametrize("shape", _SHAPES)
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
@pytest.mark.parametrize("shape", _SHAPES)
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


@pytest.mark.parametrize("empty", [None, "", "   "])
@pytest.mark.parametrize("field_name", _ENDPOINTS)
def test_core_actor_never_holds_an_empty_endpoint(field_name, empty):
    """No arrival or assignment leaves an actor without an endpoint.

    ActivityPub requires both, so ``None``, ``""`` and blank strings — at
    construction or by later assignment — all resolve to the derived URL.
    """
    built = VultronOrganization.model_validate(
        {"id": ACTOR_ID, field_name: empty}
    )
    assert getattr(built, field_name) == f"{ACTOR_ID}/{field_name}"

    actor = VultronOrganization(id_=ACTOR_ID, name="Alice")

    setattr(actor, field_name, empty)

    assert getattr(actor, field_name) == f"{ACTOR_ID}/{field_name}"


@pytest.mark.parametrize("field_name", _ENDPOINTS)
def test_wire_actor_serializes_derived_endpoints_under_exclude_unset(
    field_name,
):
    """The AS2 branch records a derived endpoint as set, as ``CoreActor`` does."""
    actor = as_Service(id_=ACTOR_ID)

    dumped = actor.model_dump(exclude_unset=True, by_alias=True)

    assert dumped[field_name]["id"] == f"{ACTOR_ID}/{field_name}"


@pytest.mark.parametrize("field_name", _ENDPOINTS)
def test_padded_endpoint_uri_is_stripped(field_name):
    """Surrounding whitespace is not part of an address, on either branch."""
    padded = {"id": ACTOR_ID, field_name: " https://example.org/box "}

    assert (
        getattr(VultronOrganization.model_validate(padded), field_name)
        == "https://example.org/box"
    )
    assert (
        getattr(as_Service.model_validate(padded), field_name).id_
        == "https://example.org/box"
    )


@pytest.mark.parametrize("field_name", _ENDPOINTS)
def test_inline_idless_collection_through_the_parser_derives_the_url(
    field_name,
):
    """An inline actor whose endpoint collection has no ``id`` gets its URL.

    The parser expands the inline dict into an ``as_OrderedCollection``
    before the actor validates it, and that collection's default id is a
    fresh ``urn:uuid:``; reading it would publish an address nobody routes
    to.
    """
    activity = parse_activity(
        {
            "type": "Announce",
            "id": "https://example.org/activities/1",
            "published": "2026-01-01T00:00:00Z",
            "actor": {
                "type": "Person",
                "id": ACTOR_ID,
                field_name: {"type": "OrderedCollection"},
            },
            "object": "https://example.org/objects/1",
        }
    )

    assert getattr(activity.actor, field_name) == f"{ACTOR_ID}/{field_name}"


@pytest.mark.spec("ARCH-23-003")
def test_serialized_endpoints_carry_only_address_type_and_items():
    """An endpoint serializes as an address, type and items — nothing else.

    Pins the wire form byte-for-byte on the fields this area owns.  In
    particular ``current`` is gone: it serialized as ``0``, but AS2's
    ``current`` is a reference to a page, not an integer (ISSUE-3563).  Nor
    is there a ``published``/``updated``: an endpoint built around a URI is an
    address, not an object this process authored, so it is not stamped with
    the local clock (#3732) — an earlier revision of this test had to pop
    both keys before it could make the "nothing else" claim.
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
        assert dumped[field_name] == {
            "@context": "https://www.w3.org/ns/activitystreams",
            "id": f"{ACTOR_ID}/{field_name}",
            "type": "OrderedCollection",
            "items": [],
        }


@pytest.mark.parametrize("actor_cls", _ACTOR_CLASSES)
@pytest.mark.parametrize("field_name", _ENDPOINTS)
@pytest.mark.parametrize("shape", _SHAPES)
def test_endpoint_without_arrived_stamp_carries_no_clock_stamp(
    actor_cls, field_name, shape
):
    """An endpoint is an address, so no arrival shape gets a clock stamp.

    ``as_Object`` mints ``published`` and ``updated`` from ``now_utc()`` on
    every construction.  An endpoint — derived from a bare URI or the actor's
    own ``id_``, or arriving as a collection dict with no stamps of its own —
    is not an object this process authored, and a clock value minted there
    can never round-trip: ``CoreActor`` keeps only the URI (ARCH-12-006), so
    an actor stored and read back through the datalayer compared unequal to
    itself whenever a second boundary fell between the write and the read
    (#3732, #3726), and an addressed dict that ``to_json()`` had dumped
    without its ``None`` stamps was re-minted on re-validation.
    """
    data = {"id": ACTOR_ID, **_arrival_shapes(field_name)[shape]}

    collection = getattr(actor_cls.model_validate(data), field_name)

    assert collection.published is None
    assert collection.updated is None


@pytest.mark.parametrize("field_name", _ENDPOINTS)
def test_constructed_actor_endpoints_carry_no_clock_stamp(field_name):
    """The endpoints ``set_collections`` derives for a new actor are unstamped.

    This is the shape ``as_Person(name=...)`` stores, and the one that must
    equal what the datalayer hands back (#3732, #3726).
    """
    collection = getattr(as_Service(id_=ACTOR_ID, name="Alice"), field_name)

    assert collection.id_ == f"{ACTOR_ID}/{field_name}"
    assert collection.published is None
    assert collection.updated is None


@pytest.mark.parametrize("with_id", [True, False], ids=["addressed", "idless"])
@pytest.mark.parametrize("field_name", _ENDPOINTS)
def test_endpoint_collection_keeps_the_time_it_arrived_with(
    field_name, with_id
):
    """Not stamping a derived address never means discarding a stated time.

    A collection that arrives carrying ``published``/``updated`` keeps them as
    received — with or without an ``id`` of its own — because that value is
    the sender's claim, not this process's clock (ADR-0103).
    """
    collection: dict[str, Any] = {
        "type": "OrderedCollection",
        "published": _ARRIVED_AT.isoformat(),
        "updated": _ARRIVED_AT.isoformat(),
    }
    if with_id:
        collection["id"] = f"{ACTOR_ID}/{field_name}"

    endpoint = getattr(
        as_Service.model_validate({"id": ACTOR_ID, field_name: collection}),
        field_name,
    )

    assert endpoint.id_ == f"{ACTOR_ID}/{field_name}"
    assert endpoint.published == _ARRIVED_AT
    assert endpoint.updated == _ARRIVED_AT


def _as_uri_endpoints(actor: as_Actor) -> dict[str, Any]:
    """The datalayer path in miniature: each endpoint reduced to its URI.

    ``CoreActor`` keeps only the URI (ARCH-12-006), and the AS2 form is
    rebuilt from that URI on read.
    """
    as_stored = actor.model_dump(by_alias=True)
    for field_name in _ENDPOINTS:
        as_stored[field_name] = as_stored[field_name]["id"]
    return as_stored


def _as_wire_json(actor: as_Actor) -> dict[str, Any]:
    """The wire path: ``to_json()`` drops the ``None`` stamps with ``exclude_none``."""
    dumped: dict[str, Any] = json.loads(actor.to_json())
    return dumped


@pytest.mark.parametrize(
    "dump",
    [_as_uri_endpoints, _as_wire_json],
    ids=["uri-endpoints", "to_json"],
)
@pytest.mark.parametrize("actor_cls", _ALL_WIRE_ACTOR_CLASSES)
def test_actor_round_trips_across_a_clock_tick(actor_cls, dump, monkeypatch):
    """AS2 actor → stored/wire form → AS2 actor is equal whatever the clock.

    The rebuild happens an hour later here, so any clock stamp minted on the
    way back would show up as an inequality (#3732, #3726).  Every wire actor
    class shares ``as_Actor``'s coercion, so every one is checked, on both the
    URI-only form the datalayer hands back and the ``to_json()`` form a peer
    receives.
    """
    actor = actor_cls(id_=ACTOR_ID, name="Alice")
    as_stored = dump(actor)
    monkeypatch.setattr(
        _helpers,
        "datetime",
        SteppingClock(now_utc() + timedelta(hours=1), step=timedelta(0)),
    )

    assert actor_cls.model_validate(as_stored) == actor


@pytest.mark.parametrize("with_id", [True, False], ids=["addressed", "idless"])
@pytest.mark.parametrize("field_name", _ENDPOINTS)
def test_inbound_rule_reaches_an_item_nested_in_an_endpoint_dict(
    field_name, with_id
):
    """The inbound context survives the endpoint coercion into nested items.

    ``_coerce_uri_to_collection`` validates a collection dict itself, so it
    must hand Pydantic the caller's context: under ``INBOUND_CONTEXT_KEY`` an
    inline item's absent ``published`` stays ``None`` (ADR-0103) rather than
    being fabricated from the local clock — at every depth, as
    ``carry_absent_times_on_inbound`` promises.
    """
    collection: dict[str, Any] = {
        "type": "OrderedCollection",
        "items": [{"type": "Note", "id": "https://example.org/notes/1"}],
    }
    if with_id:
        collection["id"] = f"{ACTOR_ID}/{field_name}"

    actor = as_Service.model_validate(
        {"id": ACTOR_ID, field_name: collection},
        context={INBOUND_CONTEXT_KEY: True},
    )

    (item,) = getattr(actor, field_name).items
    assert item.published is None
    assert item.updated is None


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
