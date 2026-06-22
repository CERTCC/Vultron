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
from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driving.fastapi.deps import (
    get_canonical_actor_dl,
    get_trigger_dl,
    get_trigger_service,
)
from vultron.adapters.driving.fastapi.routers import actors as actors_router
from vultron.adapters.driving.fastapi.routers import (
    datalayer as datalayer_router,
)
from vultron.adapters.driving.fastapi.routers import (
    trigger_embargo as trigger_embargo_router,
)
from vultron.core.models.actor import CoreActor
from vultron.core.states.em import EM
from vultron.core.states.roles import CVDRole
from vultron.core.use_cases.triggers.service import TriggerService
from vultron.adapters.utils import make_id
from vultron.wire.as2.factories import em_propose_embargo_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Offer
from vultron.wire.as2.vocab.base.objects.actors import (
    as_Organization,
    as_Person,
    as_Service,
    as_Application,
    as_Group,
)
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)


@pytest.fixture
def actor_and_dl():
    """Create actor + per-actor DataLayer together (avoids chicken-and-egg).

    The actor object is created first (no DataLayer needed), then a
    DataLayer is instantiated scoped to that actor's ID (ADR-0012 Option B).
    The actor is then persisted into its own DataLayer.  Callers should
    unpack via the ``actor`` and ``dl`` fixtures below.
    """
    actor_obj = as_Service(name="Vendor Co")
    actor_id = actor_obj.id_
    reset_datalayer(actor_id)
    actor_dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)
    actor_dl.clear_all()
    actor_dl.create(actor_obj)
    yield actor_obj, actor_dl
    actor_dl.close()
    reset_datalayer(actor_id)


@pytest.fixture
def actor(actor_and_dl):
    actor_obj, _ = actor_and_dl
    return actor_obj


@pytest.fixture
def dl(actor_and_dl):
    _, actor_dl = actor_and_dl
    return actor_dl


# TestClient for datalayer router
@pytest.fixture
def client_datalayer(datalayer):
    from vultron.adapters.driven.datalayer import get_datalayer

    app = FastAPI()
    app.include_router(datalayer_router.router)
    # Override get_datalayer dependency to use test's datalayer instance
    app.dependency_overrides[get_datalayer] = lambda: datalayer
    client = TestClient(app)
    yield client
    app.dependency_overrides = {}


# TestClient for actors router
@pytest.fixture
def client_actors(datalayer):
    from vultron.adapters.driven.datalayer import get_datalayer

    app = FastAPI()
    app.include_router(actors_router.router)
    # Override get_datalayer dependency to use test's datalayer instance
    app.dependency_overrides[get_datalayer] = lambda: datalayer
    client = TestClient(app)
    yield client
    app.dependency_overrides = {}


# Provide list of actor classes used in actor router tests
_actor_classes = [
    CoreActor,
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
def created_actors(datalayer, actor_classes):
    actors = []
    for actor_cls in actor_classes:
        # CoreActor stores inbox/outbox as URI strings; provide them explicitly
        # so profile-discovery tests can assert inbox/outbox are present.
        if issubclass(actor_cls, CoreActor):
            actor = actor_cls(
                name="Test Actor for List",
                inbox=make_id("inbox"),
                outbox=make_id("outbox"),
            )
        else:
            actor = actor_cls(name="Test Actor for List")
        datalayer.create(object_to_record(actor))
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


# ---------------------------------------------------------------------------
# Shared embargo test helpers and fixtures
# ---------------------------------------------------------------------------


def _add_case_manager(case: VulnerabilityCase, dl) -> as_Service:
    """Add a CASE_MANAGER participant to *case* and return the case actor."""
    case_actor = as_Service(name=f"Case Actor for {case.name}")
    dl.create(case_actor)
    cm_participant = CaseParticipant(
        attributed_to=case_actor.id_,
        context=case.id_,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    dl.create(cm_participant)
    case.actor_participant_index[case_actor.id_] = cm_participant.id_
    dl.save(case)
    return case_actor


@pytest.fixture
def client_triggers(dl):
    """TestClient wired to the trigger_embargo router with overridden deps."""
    app = FastAPI()
    app.include_router(trigger_embargo_router.router)
    app.dependency_overrides[get_trigger_service] = lambda: TriggerService(
        dl, trigger_activity=TriggerActivityAdapter(dl)
    )
    app.dependency_overrides[get_trigger_dl] = lambda: dl
    app.dependency_overrides[get_canonical_actor_dl] = lambda: dl
    client = TestClient(app)
    yield client
    app.dependency_overrides = {}


@pytest.fixture
def case_without_participant(dl):
    """A VulnerabilityCase with a Case Manager but no participant for the actor."""
    case_obj = VulnerabilityCase(name="TEST-CASE-NO-PARTICIPANT")
    dl.create(case_obj)
    _add_case_manager(case_obj, dl)
    return case_obj


@pytest.fixture
def case_with_embargo(dl, actor):
    """A VulnerabilityCase with an active EmbargoEvent."""
    case_obj = VulnerabilityCase(name="EMBARGO-CASE-001")
    embargo = EmbargoEvent(context=case_obj.id_)
    dl.create(embargo)
    case_obj.set_embargo(embargo.id_)
    case_obj.current_status.em_state = EM.ACTIVE
    dl.create(case_obj)
    _add_case_manager(case_obj, dl)
    return case_obj, embargo


@pytest.fixture
def case_with_proposal(dl, actor):
    """A VulnerabilityCase with a pending EmProposeEmbargoActivity in EM.PROPOSED state."""
    case_obj = VulnerabilityCase(
        name="PROPOSAL-CASE-001",
        attributed_to=actor.id_,
    )
    embargo = EmbargoEvent(context=case_obj.id_)
    dl.create(embargo)
    proposal = em_propose_embargo_activity(
        embargo, context=case_obj.id_, actor=actor.id_
    )
    dl.create(proposal)
    case_obj.current_status.em_state = EM.PROPOSED
    case_obj.proposed_embargoes.append(embargo.id_)
    dl.create(case_obj)
    _add_case_manager(case_obj, dl)
    return case_obj, proposal, embargo
