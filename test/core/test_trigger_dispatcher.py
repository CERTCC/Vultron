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

"""``RegistryTriggerDispatcher``: one ``trigger()`` over the registry rows.

- Resolves the row from the request's *type*, constructs the use case as
  ``(dl, request, **ports)`` and returns its typed result (ADR-0110).
- Port injection is keyed on the row's ``bt_backed`` flag: a BT-backed use
  case receives ``trigger_activity``, ``wire_render_port`` and ``sync_port``;
  the non-BT-backed one receives ``trigger_activity`` alone.
- A request type with no row is a lookup failure, and a use case returning a
  type other than its row's ``result_type`` is a contract breach, not a
  result — both raise.
- The result type resolves statically from the request with no cast
  (UCORG-05-006), through the ``TriggerDispatcher`` Protocol the class
  conforms to.

The stub rows here use test-local request models bound to real result types;
the end-to-end case runs the real registry against a real in-memory store.
"""

from typing import assert_type

import py_trees.behaviour
import pytest

from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import RmDimension, VfDimension
from vultron.core.models.use_case_result import (
    OfferResult,
    RoleOfferResult,
    StatusResult,
)
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.ports.trigger_activity import TriggerActivityPort
from vultron.core.ports.trigger_dispatcher import TriggerDispatcher
from vultron.core.ports.wire_render import WireRenderPort
from vultron.core.states.cs import CS_vf
from vultron.core.states.rm import RM
from vultron.core.trigger_dispatcher import RegistryTriggerDispatcher
from vultron.core.use_cases.triggers._base import SvcBTTriggerBase
from vultron.core.use_cases.triggers.request_bodies import CaseTriggerRequest
from vultron.core.use_cases.triggers.requests import (
    AddOnBehalfStatusTriggerRequest,
    EngageCaseTriggerRequest,
    TriggerRequest,
)
from vultron.enums.roles import CVDRole
from vultron.errors import VultronApiHandlerNotFoundError
from vultron.trigger_registry import TriggerEntry, TriggerExposure, entries
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import (
    as_CaseParticipant,
    as_ParticipantStatus,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_CASE = "https://example.org/cases/c1"


# ---------------------------------------------------------------------------
# Stub rows: what the dispatcher hands each kind of use case
# ---------------------------------------------------------------------------


class _StatusStubRequest(TriggerRequest[StatusResult], CaseTriggerRequest):
    pass


class _RoleStubRequest(TriggerRequest[RoleOfferResult], CaseTriggerRequest):
    pass


class _WrongStubRequest(TriggerRequest[StatusResult], CaseTriggerRequest):
    pass


class _SvcBtStubUseCase(SvcBTTriggerBase[StatusResult]):
    """Records its constructor ports; never runs a tree."""

    built: list["_SvcBtStubUseCase"] = []

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: object,
        trigger_activity: TriggerActivityPort | None = None,
        wire_render_port: WireRenderPort | None = None,
        sync_port: SyncActivityPort | None = None,
    ) -> None:
        super().__init__(
            dl,
            request,
            trigger_activity=trigger_activity,
            wire_render_port=wire_render_port,
            sync_port=sync_port,
        )
        self.ports = {
            "trigger_activity": trigger_activity,
            "wire_render_port": wire_render_port,
            "sync_port": sync_port,
        }
        _SvcBtStubUseCase.built.append(self)

    def execute(self) -> StatusResult:
        return StatusResult(activity_id="urn:uuid:a", status_id="urn:uuid:s")

    def _prepare(self) -> None:  # pragma: no cover - template not run
        raise AssertionError

    def _build_tree(self) -> py_trees.behaviour.Behaviour:  # pragma: no cover
        raise AssertionError

    def _handle_result(self) -> None:  # pragma: no cover
        raise AssertionError

    def _build_result(self) -> StatusResult:  # pragma: no cover
        raise AssertionError


class _SvcPlainStubUseCase:
    built: list["_SvcPlainStubUseCase"] = []

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: object,
        trigger_activity: TriggerActivityPort | None = None,
    ) -> None:
        self.trigger_activity = trigger_activity
        _SvcPlainStubUseCase.built.append(self)

    def execute(self) -> RoleOfferResult:
        return RoleOfferResult(
            activity_id="urn:uuid:r", activity={"type": "Offer"}
        )


class _SvcWrongResultStubUseCase(_SvcBtStubUseCase):
    def execute(self) -> StatusResult:
        return OfferResult(offer=None)  # type: ignore[return-value]


def _stub_rows() -> list[TriggerEntry]:
    return [
        TriggerEntry(
            verb="stub-status",
            request_model=_StatusStubRequest,
            use_case_class=_SvcBtStubUseCase,
            result_type=StatusResult,
            exposure=TriggerExposure.DEMO_ONLY,
            bt_backed=True,
            spec_ids=("TRIG-12-004",),
        ),
        TriggerEntry(
            verb="stub-role",
            request_model=_RoleStubRequest,
            use_case_class=_SvcPlainStubUseCase,
            result_type=RoleOfferResult,
            exposure=TriggerExposure.GENERAL_PURPOSE,
            bt_backed=False,
            spec_ids=("TRIG-12-004",),
        ),
        TriggerEntry(
            verb="stub-wrong",
            request_model=_WrongStubRequest,
            use_case_class=_SvcWrongResultStubUseCase,
            result_type=StatusResult,
            exposure=TriggerExposure.DEMO_ONLY,
            bt_backed=True,
            spec_ids=("TRIG-12-004",),
        ),
    ]


@pytest.fixture
def actor_and_dl():
    actor = as_Service(name="Case Manager Co")
    reset_datalayer(actor.id_)
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor.id_)
    dl.clear_all()
    dl.create(actor)
    yield actor, dl
    dl.clear_all()
    reset_datalayer(actor.id_)


@pytest.fixture
def ports(actor_and_dl):
    _, dl = actor_and_dl
    return {
        "trigger_activity": TriggerActivityAdapter(dl),
        "wire_render_port": As2WireRenderAdapter(),
        "sync_port": SyncActivityAdapter(dl),
    }


@pytest.fixture(autouse=True)
def _reset_stub_records():
    _SvcBtStubUseCase.built.clear()
    _SvcPlainStubUseCase.built.clear()
    yield
    _SvcBtStubUseCase.built.clear()
    _SvcPlainStubUseCase.built.clear()


@pytest.mark.spec("TRIG-12-004")
def test_bt_backed_row_is_built_with_the_whole_port_bundle(
    actor_and_dl, ports
) -> None:
    actor, dl = actor_and_dl
    dispatcher = RegistryTriggerDispatcher(_stub_rows(), **ports)

    result = dispatcher.trigger(
        _StatusStubRequest(actor_id=actor.id_, case_id=_CASE), dl
    )

    assert_type(result, StatusResult)
    assert result.status_id == "urn:uuid:s"
    (built,) = _SvcBtStubUseCase.built
    assert built.ports == ports
    assert built._dl is dl


@pytest.mark.spec("TRIG-12-004")
def test_non_bt_backed_row_is_built_with_trigger_activity_alone(
    actor_and_dl, ports
) -> None:
    actor, dl = actor_and_dl
    dispatcher = RegistryTriggerDispatcher(_stub_rows(), **ports)

    result = dispatcher.trigger(
        _RoleStubRequest(actor_id=actor.id_, case_id=_CASE), dl
    )

    assert_type(result, RoleOfferResult)
    assert result.activity_id == "urn:uuid:r"
    (built,) = _SvcPlainStubUseCase.built
    assert built.trigger_activity is ports["trigger_activity"]


@pytest.mark.spec("TRIG-12-004")
def test_request_type_with_no_row_is_a_lookup_failure(
    actor_and_dl, ports
) -> None:
    actor, dl = actor_and_dl
    dispatcher = RegistryTriggerDispatcher(_stub_rows(), **ports)

    with pytest.raises(VultronApiHandlerNotFoundError, match="EngageCase"):
        dispatcher.trigger(
            EngageCaseTriggerRequest(actor_id=actor.id_, case_id=_CASE), dl
        )


@pytest.mark.spec("UCORG-05-007")
def test_result_of_the_wrong_type_is_a_contract_breach(
    actor_and_dl, ports
) -> None:
    actor, dl = actor_and_dl
    dispatcher = RegistryTriggerDispatcher(_stub_rows(), **ports)

    with pytest.raises(TypeError, match="OfferResult, not StatusResult"):
        dispatcher.trigger(
            _WrongStubRequest(actor_id=actor.id_, case_id=_CASE), dl
        )


@pytest.mark.spec("UCORG-05-006")
def test_conforms_to_the_trigger_dispatcher_port(actor_and_dl, ports) -> None:
    """Assignment to the Protocol type is the static conformance check; the
    call through the Protocol-typed name still resolves the bound subtype."""
    actor, dl = actor_and_dl
    dispatcher: TriggerDispatcher = RegistryTriggerDispatcher(
        _stub_rows(), **ports
    )
    result = dispatcher.trigger(
        _StatusStubRequest(actor_id=actor.id_, case_id=_CASE), dl
    )
    assert_type(result, StatusResult)
    assert result.activity_id == "urn:uuid:a"


# ---------------------------------------------------------------------------
# End to end over the real registry
# ---------------------------------------------------------------------------


@pytest.mark.spec("UCORG-05-006")
@pytest.mark.spec("PRM-06-003")
def test_real_registry_runs_add_on_behalf_status_to_a_status_result(
    actor_and_dl, ports
) -> None:
    """The real rows, a real store, a real BT: ``StatusResult`` comes back
    typed and the vendor's participant carries the asserted ``Vf``.

    The vendor is an existing invitee: an on-behalf assertion never creates
    a participant (PRM-06-006)."""
    actor, dl = actor_and_dl
    case = as_VulnerabilityCase(name="Dispatch Case")
    cm = as_CaseParticipant(
        attributed_to=actor.id_,
        context=case.id_,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    vendor_id = "https://example.org/actors/vendor-co"
    vendor = as_CaseParticipant(
        attributed_to=vendor_id,
        context=case.id_,
        case_roles=[CVDRole.VENDOR],
        participant_statuses=[
            as_ParticipantStatus(
                attributed_to=vendor_id,
                context=case.id_,
                rm=RmDimension(state=RM.RECEIVED),
                vf=VfDimension(state=CS_vf.vf),
            )
        ],
    )
    for actor_id, participant in ((actor.id_, cm), (vendor_id, vendor)):
        case.actor_participant_index[actor_id] = participant.id_
        case.case_participants.append(participant.id_)
        dl.create(participant)
    dl.create(case)

    dispatcher = RegistryTriggerDispatcher(entries(), **ports)
    result = dispatcher.trigger(
        AddOnBehalfStatusTriggerRequest(
            actor_id=actor.id_,
            case_id=case.id_,
            target_actor_id=vendor_id,
            vf_state=CS_vf.Vf,
        ),
        dl,
    )

    assert_type(result, StatusResult)
    assert result.status_id is not None and result.activity_id is not None
    updated = dl.read_case(case.id_)
    assert updated is not None
    participant = dl.read(updated.actor_participant_index[vendor_id])
    assert isinstance(participant, CaseParticipant)
    last = participant.participant_statuses[-1]
    assert last.vf is not None and last.vf.state == CS_vf.Vf
