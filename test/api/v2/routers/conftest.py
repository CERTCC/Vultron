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

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from vultron.api.v2.data.actor_io import init_actor_io
from vultron.api.v2.datalayer.db_record import object_to_record
from vultron.api.v2.routers import actors as actors_router
from vultron.api.v2.routers import datalayer as datalayer_router
from vultron.as_vocab.base.objects.activities.transitive import as_Offer
from vultron.as_vocab.base.objects.actors import (
    as_Actor,
    as_Organization,
    as_Person,
    as_Service,
    as_Application,
    as_Group,
)
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport


# adapter: reuse top-level datalayer fixture for tests that ask for `dl`
@pytest.fixture
def dl(datalayer):
    return datalayer


# TestClient for datalayer router
@pytest.fixture
def client_datalayer():
    app = FastAPI()
    app.include_router(datalayer_router.router)
    client = TestClient(app)
    yield client


# TestClient for actors router
@pytest.fixture
def client_actors():
    app = FastAPI()
    app.include_router(actors_router.router)
    client = TestClient(app)
    yield client


# Provide list of actor classes used in actor router tests
_actor_classes = [
    as_Actor,
    as_Organization,
    as_Person,
    as_Service,
    as_Application,
    as_Group,
]


@pytest.fixture
def actor_classes():
    return _actor_classes


# Create and persist a set of actors, and initialize their actor_io stores
@pytest.fixture
def created_actors(dl, actor_classes):
    actors = []
    for actor_cls in actor_classes:
        actor = actor_cls(name="Test Actor for List")
        dl.create(object_to_record(actor))
        init_actor_io(actor.as_id)
        actors.append(actor)
    return actors


# Lightweight VulnerabilityReport fixture
@pytest.fixture
def report():
    return VulnerabilityReport()


# Lightweight Offer fixture tied to the report
@pytest.fixture
def offer(report):
    # keep the original parameter names (as_object) used in legacy tests
    return as_Offer(actor="urn:uuid:test-actor", as_object=report)
