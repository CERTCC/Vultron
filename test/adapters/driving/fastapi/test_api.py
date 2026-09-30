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
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

# Copyright

"""
Provides API v2 tests
"""

from datetime import timedelta

from test.support.clock import SteppingClock
from vultron.adapters.driven.db_record import object_to_record
from vultron.core.models import _helpers
from vultron.core.models._helpers import now_utc
from vultron.wire.as2.vocab.base.objects.actors import as_Person


def _pin_clock_past_a_second_boundary(monkeypatch) -> None:
    """Move ``now_utc()`` an hour ahead of the instant the actor was created.

    A stored actor must read back equal to itself however much wall-clock
    time separates the write from the read.  These tests used to fail only
    when a second boundary happened to fall between ``datalayer.create`` and
    the ``GET`` (#3732, #3726) — the read path rebuilt the actor's derived
    ``inbox``/``outbox`` collections stamped with the read-time clock — so the
    boundary is made certain here rather than left to scheduling luck.
    """
    monkeypatch.setattr(
        _helpers,
        "datetime",
        SteppingClock(now_utc() + timedelta(hours=1), step=timedelta(0)),
    )


def test_version(client):
    """Test the /version endpoint"""
    response = client.get("/version")
    assert response.status_code == 200
    data = response.json()
    assert "version" in data
    assert isinstance(data["version"], str)


def test_datalayer_empty(client):
    """Test the /actors endpoint when no actors exist"""
    response = client.get("/actors")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_datalayer_get_nonexistent_actor(client, dl_route_key):
    """Test retrieving an actor that does not exist"""
    response = client.get(
        f"/actors/{dl_route_key}/datalayer/Actors/nonexistent-actor"
    )
    assert response.status_code == 404


def test_datalayer_get_existing_actor(
    client, datalayer, dl_route_key, hosted_actor, monkeypatch
):
    """Test retrieving an existing actor from the Actors endpoint.

    The read lands in a later wall-clock second than the create, so the
    round-trip equality below is a claim about what was stored, not about
    timing (#3726).
    """
    actor = as_Person(
        name="Test Person",
    )
    datalayer.create(object_to_record(actor))
    _pin_clock_past_a_second_boundary(monkeypatch)

    response = client.get(
        f"/actors/{dl_route_key}/datalayer/Actors/{actor.id_}"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == actor.id_
    assert data["name"] == actor.name

    assert as_Person.model_validate(data) == actor


def test_datalayer_get_existing_actor_by_id(
    client, datalayer, dl_route_key, hosted_actor, monkeypatch
):
    """Test retrieving an existing actor directly by ID.

    Same clock pin as ``test_datalayer_get_existing_actor``: the read is in a
    later second than the create, deterministically (#3732).
    """
    actor = as_Person(
        name="Test Person",
    )
    datalayer.create(object_to_record(actor))
    _pin_clock_past_a_second_boundary(monkeypatch)

    response = client.get(f"/actors/{dl_route_key}/datalayer/{actor.id_}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == actor.id_
    assert data["name"] == actor.name

    assert as_Person.model_validate(data) == actor
