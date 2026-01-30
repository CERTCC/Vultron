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
from vultron.as_vocab.base.objects.actors import as_Person
from vultron.api.v2.datalayer.db_record import object_to_record


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


def test_datalayer_get_nonexistent_actor(client):
    """Test retrieving an actor that does not exist"""
    response = client.get("/datalayer/Actors/nonexistent-actor")
    assert response.status_code == 404


def test_datalayer_get_existing_actor(client, datalayer):
    """Test retrieving an existing actor from the Actors endpoint"""
    actor = as_Person(
        name="Test Person",
    )
    datalayer.create(object_to_record(actor))

    response = client.get(f"/datalayer/Actors/{actor.as_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == actor.as_id
    assert data["name"] == actor.name

    assert as_Person.model_validate(data) == actor


def test_datalayer_get_existing_actor(client, datalayer):
    """Test retrieving an existing actor directly by ID"""
    actor = as_Person(
        name="Test Person",
    )
    datalayer.create(object_to_record(actor))

    response = client.get(f"/datalayer/{actor.as_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == actor.as_id
    assert data["name"] == actor.name

    assert as_Person.model_validate(data) == actor
