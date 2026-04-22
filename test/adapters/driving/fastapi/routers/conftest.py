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

from vultron.adapters.driven.db_record import object_to_record
from vultron.adapters.driving.fastapi.routers import actors as actors_router
from vultron.adapters.driving.fastapi.routers import (
    datalayer as datalayer_router,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Offer
from vultron.wire.as2.vocab.base.objects.actors import (
    as_Actor,
    as_Organization,
    as_Person,
    as_Service,
    as_Application,
    as_Group,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)


# adapter: reuse top-level datalayer fixture for tests that ask for `dl`
@pytest.fixture
def dl(datalayer):
    return datalayer


# TestClient for datalayer router
@pytest.fixture
def client_datalayer(dl):
    from vultron.adapters.driven.datalayer import get_datalayer

    app = FastAPI()
    app.include_router(datalayer_router.router)
    # Override get_datalayer dependency to use test's datalayer instance
    app.dependency_overrides[get_datalayer] = lambda: dl
    client = TestClient(app)
    yield client
    app.dependency_overrides = {}


# TestClient for actors router
@pytest.fixture
def client_actors(dl):
    from vultron.adapters.driven.datalayer import get_datalayer

    app = FastAPI()
    app.include_router(actors_router.router)
    # Override get_datalayer dependency to use test's datalayer instance
    app.dependency_overrides[get_datalayer] = lambda: dl
    client = TestClient(app)
    yield client
    app.dependency_overrides = {}


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


@pytest.fixture
def created_actors(dl, actor_classes):
    actors = []
    for actor_cls in actor_classes:
        actor = actor_cls(name="Test Actor for List")
        dl.create(object_to_record(actor))
        actors.append(actor)
    return actors


# Lightweight VulnerabilityReport fixture
@pytest.fixture
def report():
    return VulnerabilityReport()


# Lightweight Offer fixture tied to the report
@pytest.fixture
def offer(report):
    # use current parameter name `object_` (legacy name was `as_object` / JSON `object`)
    return as_Offer(actor="urn:uuid:test-actor", object_=report)
