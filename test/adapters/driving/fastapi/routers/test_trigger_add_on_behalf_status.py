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

"""``POST /actors/{actor_id}/trigger/add-on-behalf-status`` over HTTP.

The on-behalf assertions of ADR-0084 become reachable: a Case Manager records
a vendor's awareness (v→V, PRM-06-003) or a deployer's deployment (d→D,
PRM-06-004), and fix readiness (f→F) is refused with a structured error
(PRM-06-005).  The route is the first consumer of ``run_trigger`` over the
registry-backed ``TriggerDispatcher``: these tests run the real dispatcher
over an in-memory store and reach it through the ``get_trigger_dl`` override
seam (TRIG-06-002), exactly as deployment resolves it.
"""

from collections.abc import Iterator
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from vultron.adapters.driving.fastapi.deps import (
    get_canonical_actor_dl,
    get_trigger_dl,
)
from vultron.adapters.driving.fastapi.routers import (
    trigger_case as trigger_case_router,
)
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import RmDimension, VfDimension
from vultron.core.states.cs import CS_d, CS_vf
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.objects.case_participant import (
    as_CaseParticipant,
    as_ParticipantStatus,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from test.support.trigger_results import recipient_ids

_VENDOR_ID = "https://example.org/actors/vendor-co"
_DEPLOYER_ID = "https://example.org/actors/deployer-inc"
_PATH = "/actors/{actor}/trigger/add-on-behalf-status"

#: The route runs through ``run_trigger``, so the flush it schedules is the
#: helper's ``outbox_handler`` reference, not the router module's.
_FLUSH = "vultron.adapters.driving.fastapi.trigger_runner.outbox_handler"


@pytest.fixture(autouse=True)
def _no_outbox_delivery():
    with patch(_FLUSH, new_callable=AsyncMock) as flush:
        yield flush


@pytest.fixture
def client(dl) -> Iterator[TestClient]:
    """The case router alone; the dispatcher dependency chains through
    ``get_trigger_dl``, so overriding that seam is enough (TRIG-06-002)."""
    app = FastAPI()
    app.include_router(trigger_case_router.router)
    app.dependency_overrides[get_trigger_dl] = lambda: dl
    app.dependency_overrides[get_canonical_actor_dl] = lambda: dl
    yield TestClient(app)
    app.dependency_overrides = {}


@pytest.fixture
def managed_case(dl, actor) -> as_VulnerabilityCase:
    """A case the ``actor`` fixture manages; no vendor or deployer yet."""
    case = as_VulnerabilityCase(name="On-Behalf Case")
    cm = as_CaseParticipant(
        attributed_to=actor.id_,
        context=case.id_,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    case.actor_participant_index[actor.id_] = cm.id_
    case.case_participants.append(cm.id_)
    dl.create(case)
    dl.create(cm)
    return case


def _add_vendor_at_vf(dl, case: as_VulnerabilityCase) -> None:
    """A joined VENDOR at fix-ready, the causal precondition for d→D."""
    vendor = as_CaseParticipant(
        attributed_to=_VENDOR_ID,
        context=case.id_,
        case_roles=[CVDRole.VENDOR],
        participant_statuses=[
            as_ParticipantStatus(
                attributed_to=_VENDOR_ID,
                context=case.id_,
                vf=VfDimension(state=CS_vf.VF),
            )
        ],
    )
    case.actor_participant_index[_VENDOR_ID] = vendor.id_
    case.case_participants.append(vendor.id_)
    dl.create(vendor)
    dl.save(case)


def _add_joined_deployer(dl, case: as_VulnerabilityCase) -> None:
    """A DEPLOYER that accepted the case but has not reported deployment.

    ``D`` entails ``RM ∈ {ACCEPTED, DEFERRED, CLOSED}`` (the cross-machine
    entailment in ``rm_em_cs.md``), so an on-behalf d→D is only writable for
    a deployer whose RM has already advanced; a never-joined deployer sits at
    RM START and the write is refused.  PRM-06-004 calls the on-behalf d→D
    rare, and this is why.
    """
    deployer = as_CaseParticipant(
        attributed_to=_DEPLOYER_ID,
        context=case.id_,
        case_roles=[CVDRole.DEPLOYER],
        participant_statuses=[
            as_ParticipantStatus(
                attributed_to=_DEPLOYER_ID,
                context=case.id_,
                rm=RmDimension(state=RM.ACCEPTED),
            )
        ],
    )
    case.actor_participant_index[_DEPLOYER_ID] = deployer.id_
    case.case_participants.append(deployer.id_)
    dl.create(deployer)
    dl.save(case)


def _participant_for(dl, case_id: str, target_id: str) -> CaseParticipant:
    case = dl.read_case(case_id)
    assert case is not None
    participant = dl.read(case.actor_participant_index[target_id])
    assert isinstance(participant, CaseParticipant)
    return participant


# ---------------------------------------------------------------------------
# PRM-06-003: v→V on behalf of a Vendor
# ---------------------------------------------------------------------------


@pytest.mark.spec("PRM-06-003")
@pytest.mark.spec("TRIG-01-002")
def test_v_to_V_on_behalf_of_a_vendor(client, dl, actor, managed_case):
    resp = client.post(
        _PATH.format(actor=actor.id_),
        json={
            "case_id": managed_case.id_,
            "target_actor_id": _VENDOR_ID,
            "vf_state": "Vf",
        },
    )

    assert resp.status_code == status.HTTP_202_ACCEPTED, resp.text
    body = resp.json()
    assert set(body) == {"activity_id", "status_id"}
    assert body["activity_id"] and body["status_id"]
    participant = _participant_for(dl, managed_case.id_, _VENDOR_ID)
    assert participant.has_role(CVDRole.VENDOR)
    last = participant.participant_statuses[-1]
    assert last.vf is not None and last.vf.state == CS_vf.Vf
    assert last.id_ == body["status_id"]


@pytest.mark.spec("TRIG-07-001")
@pytest.mark.spec("PCR-08-001")
def test_v_to_V_queues_the_activity_to_the_case_manager_and_flushes(
    client, dl, actor, managed_case, _no_outbox_delivery
):
    before = set(dl.outbox_list())
    resp = client.post(
        _PATH.format(actor=actor.id_),
        json={
            "case_id": managed_case.id_,
            "target_actor_id": _VENDOR_ID,
            "vf_state": "Vf",
        },
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED, resp.text

    new_ids = set(dl.outbox_list()) - before
    assert new_ids == {resp.json()["activity_id"]}
    assert actor.id_ in recipient_ids(dl.read(next(iter(new_ids))))
    _no_outbox_delivery.assert_awaited_once()
    assert _no_outbox_delivery.await_args.args == (actor.id_, dl)


# ---------------------------------------------------------------------------
# PRM-06-004: d→D on behalf of a Deployer
# ---------------------------------------------------------------------------


@pytest.mark.spec("PRM-06-004")
def test_d_to_D_on_behalf_of_a_deployer(client, dl, actor, managed_case):
    _add_vendor_at_vf(dl, managed_case)
    _add_joined_deployer(dl, managed_case)

    resp = client.post(
        _PATH.format(actor=actor.id_),
        json={
            "case_id": managed_case.id_,
            "target_actor_id": _DEPLOYER_ID,
            "d_state": "D",
        },
    )

    assert resp.status_code == status.HTTP_202_ACCEPTED, resp.text
    assert set(resp.json()) == {"activity_id", "status_id"}
    participant = _participant_for(dl, managed_case.id_, _DEPLOYER_ID)
    assert participant.has_role(CVDRole.DEPLOYER)
    last = participant.participant_statuses[-1]
    assert last.d is not None and last.d.state == CS_d.D
    assert last.rm is not None and last.rm.state == RM.ACCEPTED


@pytest.mark.spec("PRM-06-004")
def test_d_to_D_for_a_never_joined_deployer_is_refused_by_entailment(
    client, dl, actor, managed_case
):
    """A deployer at RM START cannot have deployed a fix: the CS entailment
    refuses the write with the violation spelled out (EH-07-001)."""
    _add_vendor_at_vf(dl, managed_case)

    resp = client.post(
        _PATH.format(actor=actor.id_),
        json={
            "case_id": managed_case.id_,
            "target_actor_id": _DEPLOYER_ID,
            "d_state": "D",
        },
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    detail = resp.json()["detail"]
    assert detail["error"] == "ValidationError"
    assert detail["details"][0]["dimensions"] == ["rm", "d"]


@pytest.mark.spec("CSB-15-004")
def test_d_to_D_is_refused_when_no_vendor_has_a_fix(
    client, dl, actor, managed_case
):
    resp = client.post(
        _PATH.format(actor=actor.id_),
        json={
            "case_id": managed_case.id_,
            "target_actor_id": _DEPLOYER_ID,
            "d_state": "D",
        },
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert resp.json()["detail"]["error"] == "ValidationError"


# ---------------------------------------------------------------------------
# PRM-06-005: f→F is never asserted on behalf
# ---------------------------------------------------------------------------


@pytest.mark.spec("PRM-06-005")
@pytest.mark.spec("TRIG-01-003")
def test_f_to_F_is_refused_with_a_structured_error(
    client, dl, actor, managed_case, _no_outbox_delivery
):
    resp = client.post(
        _PATH.format(actor=actor.id_),
        json={
            "case_id": managed_case.id_,
            "target_actor_id": _VENDOR_ID,
            "vf_state": "VF",
        },
    )

    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    detail = resp.json()["detail"]
    assert isinstance(detail, list) and detail
    (violation,) = [d for d in detail if "vf_state" in d["loc"]]
    assert "PRM-06-005" in violation["msg"]
    # Refused at the body boundary: no participant, no status, no flush.
    case = dl.read_case(managed_case.id_)
    assert case is not None and _VENDOR_ID not in case.actor_participant_index
    _no_outbox_delivery.assert_not_awaited()


def test_neither_dimension_is_refused(client, actor, managed_case):
    resp = client.post(
        _PATH.format(actor=actor.id_),
        json={"case_id": managed_case.id_, "target_actor_id": _VENDOR_ID},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert any(
        "at least one" in d["msg"] for d in resp.json()["detail"]
    ), resp.text


# ---------------------------------------------------------------------------
# Authority and resolution errors (TRIG-01-003)
# ---------------------------------------------------------------------------


@pytest.mark.spec("PRM-06-003")
def test_non_manager_asserting_actor_is_refused(
    client, dl, actor, managed_case
):
    """The ``actor`` fixture is demoted to COORDINATOR: no on-behalf authority."""
    cm = dl.read(managed_case.actor_participant_index[actor.id_])
    assert isinstance(cm, CaseParticipant)
    cm.remove_role(CVDRole.CASE_MANAGER)
    cm.add_role(CVDRole.COORDINATOR)
    dl.save(cm)

    resp = client.post(
        _PATH.format(actor=actor.id_),
        json={
            "case_id": managed_case.id_,
            "target_actor_id": _VENDOR_ID,
            "vf_state": "Vf",
        },
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert resp.json()["detail"]["error"] == "ValidationError"


@pytest.mark.spec("TRIG-01-003")
def test_unknown_case_is_404(client, actor, _no_outbox_delivery):
    resp = client.post(
        _PATH.format(actor=actor.id_),
        json={
            "case_id": "https://example.org/cases/none",
            "target_actor_id": _VENDOR_ID,
            "vf_state": "Vf",
        },
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    assert resp.json()["detail"]["error"] == "NotFound"
    _no_outbox_delivery.assert_not_awaited()


@pytest.mark.spec("TRIG-01-003")
def test_unknown_actor_is_404(client, managed_case):
    resp = client.post(
        _PATH.format(actor="nonexistent-actor"),
        json={
            "case_id": managed_case.id_,
            "target_actor_id": _VENDOR_ID,
            "vf_state": "Vf",
        },
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    assert resp.json()["detail"]["error"] == "NotFound"


@pytest.mark.spec("TRIG-03-002")
def test_unknown_body_fields_are_ignored(client, actor, managed_case):
    resp = client.post(
        _PATH.format(actor=actor.id_),
        json={
            "case_id": managed_case.id_,
            "target_actor_id": _VENDOR_ID,
            "vf_state": "Vf",
            "unknown_xyz": 1,
        },
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED, resp.text
