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

from test.support.embargo_register import activate, propose
from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.adapters.driven.db_record import object_to_record
from vultron.adapters.driving.fastapi.deps import get_trigger_dl
from vultron.adapters.driving.fastapi.routers import (
    actors as actors_router,
    datalayer as datalayer_router,
    trigger_embargo as trigger_embargo_router,
)
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.actor import CoreActor
from vultron.core.models.case import VulnerabilityCase
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import em_propose_embargo_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Offer
from vultron.wire.as2.vocab.base.objects.actors import (
    as_Application,
    as_Group,
    as_Organization,
    as_Person,
    as_Service,
)
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (  # noqa: F401
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
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


def _in_memory_actor_dl_override():
    """A ``get_actor_dl`` override that still routes per actor.

    Overriding with one fixed DataLayer defeats the routing these tests exercise:
    ``get_actor_dl`` resolves the path segment to a canonical URI and opens *that*
    actor's store (ADR-0073), so a single-store override makes every actor id
    resolve to the same rows.  Only the backing URL needs replacing — the
    configured ``db_url`` is a file and tests must stay in memory.
    """
    from fastapi import Path as FastAPIPath

    from vultron.adapters.driven.actor_hosts import canonical_actor_uri
    from vultron.adapters.driven.datalayer_sqlite import get_datalayer

    def _override(actor_id: str = FastAPIPath(...)):
        return get_datalayer(
            canonical_actor_uri(actor_id), db_url="sqlite:///:memory:"
        )

    return _override


@pytest.fixture
def client_datalayer(datalayer):
    from vultron.adapters.driving.fastapi.deps import get_actor_dl

    app = FastAPI()
    app.include_router(datalayer_router.router)
    app.include_router(datalayer_router.admin_router)
    app.dependency_overrides[get_actor_dl] = _in_memory_actor_dl_override()
    client = TestClient(app)
    yield client
    app.dependency_overrides = {}


# TestClient for actors router
@pytest.fixture
def client_actors(datalayer):
    from vultron.adapters.driving.fastapi.deps import get_actor_dl

    app = FastAPI()
    app.include_router(actors_router.router)
    app.dependency_overrides[get_actor_dl] = _in_memory_actor_dl_override()
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
def created_actors(actor_classes):
    """Host one actor per class, each in its own store.

    ``GET /actors/`` enumerates the actors this node *hosts*, and hosting means
    holding that actor's store (ADR-0073) — for an in-memory URL, the in-process
    registry that ``get_datalayer`` populates. Writing six actor rows into one
    store would therefore report **one** host, not six.

    Ids are canonical under the node's ``base_url`` because the actor routes
    resolve a path segment to an actor URI by computation, so a generated ``urn:``
    id could not be addressed on this node at all.
    """
    from vultron.adapters.driven.actor_hosts import canonical_actor_uri
    from vultron.adapters.driven.datalayer_sqlite import get_datalayer

    actors = []
    for actor_cls in actor_classes:
        actor_id = canonical_actor_uri(f"list-{actor_cls.__name__.lower()}")
        # CoreActor stores inbox/outbox as URI strings; provide them explicitly
        # so profile-discovery tests can assert inbox/outbox are present.
        if issubclass(actor_cls, CoreActor):
            actor = actor_cls(
                id_=actor_id,
                name="Test Actor for List",
                inbox=f"{actor_id}/inbox",
                outbox=f"{actor_id}/outbox",
            )
        else:
            actor = actor_cls(id_=actor_id, name="Test Actor for List")
        dl = get_datalayer(actor_id, db_url="sqlite:///:memory:")
        dl.create(object_to_record(actor))
        actors.append(actor)
    return actors


# Lightweight as_VulnerabilityReport fixture
@pytest.fixture
def report():
    return as_VulnerabilityReport()


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
    cm_participant = as_CaseParticipant(
        attributed_to=case_actor.id_,
        context=case.id_,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    # Attached first: attaching writes its consent rows (ADR-0122).
    case.add_participant(cm_participant)
    dl.create(cm_participant)
    dl.save(case)
    return case_actor


def make_case_manager(case_id: str, actor_id: str, dl) -> None:
    """Make *actor_id* the case's sole CASE_MANAGER (CM-24-006).

    A trigger writes shared EM state only as the role holder (EP-09-008), so
    a test of the state an endpoint writes runs as it; the fixtures' separate
    case actor gives up the role and stays a participant.
    """
    case = dl.read(case_id)
    for participant_id in list(case.actor_participant_index.values()):
        participant = dl.read(participant_id)
        if CVDRole.CASE_MANAGER in participant.case_roles:
            participant.case_roles = [
                r for r in participant.case_roles if r != CVDRole.CASE_MANAGER
            ]
            dl.save(participant)
    existing_id = case.actor_participant_index.get(actor_id)
    if existing_id is not None:
        # The actor keeps its one participant record and gains the role.
        existing = dl.read(existing_id)
        existing.case_roles = [*existing.case_roles, CVDRole.CASE_MANAGER]
        dl.save(existing)
        return
    manager = as_CaseParticipant(
        attributed_to=actor_id,
        context=case_id,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    case.add_participant(manager)
    dl.create(manager)
    dl.save(case)


@pytest.fixture
def client_triggers(dl):
    """TestClient wired to the trigger_embargo router over the ``dl`` store.

    ``get_trigger_dispatcher`` resolves its store through ``get_trigger_dl``,
    so overriding that one seam runs the real registry-backed dispatcher over
    the in-memory store (TRIG-06-002; ``vultron/core/ports/AGENTS.md``).
    """
    app = FastAPI()
    app.include_router(trigger_embargo_router.router)
    app.dependency_overrides[get_trigger_dl] = lambda: dl
    client = TestClient(app)
    yield client
    app.dependency_overrides = {}


@pytest.fixture
def case_without_participant(dl, actor):
    """A VulnerabilityCase with a Case Manager but no participant for the actor."""
    case_obj = VulnerabilityCase(
        name="TEST-CASE-NO-PARTICIPANT", attributed_to=actor.id_
    )
    dl.create(case_obj)
    _add_case_manager(case_obj, dl)
    return case_obj


@pytest.fixture
def case_with_embargo(dl, actor):
    """A VulnerabilityCase with an active as_EmbargoEvent."""
    case_obj = VulnerabilityCase(
        name="EMBARGO-CASE-001", attributed_to=actor.id_
    )
    embargo = as_EmbargoEvent(
        context=case_obj.id_, end_time=days_from_now_utc(45)
    )
    dl.create(embargo)
    activate(case_obj, embargo.id_)
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
    embargo = as_EmbargoEvent(
        context=case_obj.id_, end_time=days_from_now_utc(45)
    )
    dl.create(embargo)
    proposal = em_propose_embargo_activity(
        embargo, context=case_obj.id_, actor=actor.id_
    )
    dl.create(proposal)
    propose(case_obj, embargo.id_)
    case_obj.pending_embargo_proposal_index[embargo.id_] = proposal.id_
    dl.create(case_obj)
    _add_case_manager(case_obj, dl)
    return case_obj, proposal, embargo
