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
"""The CASE_MANAGER's own proposal of terms the case holds is refused (#5899).

EP-09-032 makes a proposal of a pending proposal's end time, or, with no
revision pending, of the embargo in force's, a duplicate whoever sends it.
The received tree treats one as a no-op; the CASE_MANAGER's own trigger
refuses it whole, as a trigger admits only valid steps (RSH-09).  During a
revision the in-force end time is still a counter-proposal (EP-09-020).
"""

from datetime import datetime
from typing import cast

import pytest

from test.support.ledger import committed_semantic_types
from vultron.adapters.driven.clock import SystemClock
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.embargo.nodes.proposal_repeat import (
    EmbargoTermsNotHeldNode,
)
from vultron.core.behaviors.embargo.nodes.relay_guards import (
    case_manager_admits_proposal_guard,
)
from vultron.core.behaviors.embargo.trigger_tree.proposal import (
    propose_embargo_trigger_bt,
)
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.states.em import EM
from vultron.core.use_cases.triggers.embargo import (
    SvcProposeEmbargoRevisionUseCase,
    SvcProposeEmbargoUseCase,
)
from vultron.core.use_cases.triggers.requests import (
    ProposeEmbargoRevisionTriggerRequest,
    ProposeEmbargoTriggerRequest,
)
from vultron.errors import VultronInvalidStateTransitionError
from vultron.wire.as2.vocab.base.objects.actors import as_Service

from .conftest import (
    _add_participant,
    _build_active_embargo_case_with_case_manager,
    _build_unbound_case_with_case_manager,
)

OTHER = "https://example.org/actors/other-vendor"


def _propose(dl: SqliteDataLayer, actor_id: str, case_id: str, end_time):
    return SvcProposeEmbargoUseCase(
        dl,
        ProposeEmbargoTriggerRequest(
            actor_id=actor_id, case_id=case_id, end_time=end_time
        ),
        trigger_activity=TriggerActivityAdapter(dl),
        sync_port=SyncActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
        clock=SystemClock(),
    ).execute()


def _revise(dl: SqliteDataLayer, actor_id: str, case_id: str, end_time):
    return SvcProposeEmbargoRevisionUseCase(
        dl,
        ProposeEmbargoRevisionTriggerRequest(
            actor_id=actor_id, case_id=case_id, end_time=end_time
        ),
        trigger_activity=TriggerActivityAdapter(dl),
        sync_port=SyncActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
        clock=SystemClock(),
    ).execute()


def _case(dl: SqliteDataLayer, case_id: str) -> VulnerabilityCase:
    return cast(VulnerabilityCase, dl.read(case_id))


def _active_end_time(dl: SqliteDataLayer, case_id: str) -> datetime:
    active_id = _case(dl, case_id).active_embargo_id
    assert active_id is not None
    return cast(EmbargoEvent, dl.read(active_id)).end_time


def _snapshot(dl: SqliteDataLayer, case_id: str) -> tuple:
    """What a refused proposal must leave untouched (EP-09-032)."""
    return (
        list(_case(dl, case_id).embargo_register),
        committed_semantic_types(dl, case_id),
        list(dl.outbox_list()),
        {e.id_ for e in dl.list_objects("EmbargoEvent")},
    )


@pytest.mark.spec("EP-09-032")
def test_a_manager_proposal_of_pending_terms_is_refused_whole(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Proposing a pending proposal's end time again registers nothing."""
    actor, dl = finder_actor_and_dl
    case = _build_unbound_case_with_case_manager(dl, actor.id_)
    _add_participant(dl, case.id_, OTHER)
    end_time = days_from_now_utc(30)
    _propose(dl, actor.id_, case.id_, end_time)
    before = _snapshot(dl, case.id_)

    with pytest.raises(VultronInvalidStateTransitionError, match="EP-09-032"):
        _propose(dl, actor.id_, case.id_, end_time)

    assert _snapshot(dl, case.id_) == before
    assert _case(dl, case.id_).current_status.em.state == EM.PROPOSED


@pytest.mark.spec("EP-09-032")
def test_a_manager_revision_of_the_embargo_in_force_is_refused_whole(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """With no revision pending, the in-force end time is a duplicate."""
    actor, dl = finder_actor_and_dl
    case = _build_active_embargo_case_with_case_manager(dl, actor.id_)
    _add_participant(dl, case.id_, OTHER)
    before = _snapshot(dl, case.id_)

    with pytest.raises(VultronInvalidStateTransitionError, match="EP-09-032"):
        _revise(dl, actor.id_, case.id_, _active_end_time(dl, case.id_))

    assert _snapshot(dl, case.id_) == before
    assert _case(dl, case.id_).current_status.em.state == EM.ACTIVE


@pytest.mark.spec("EP-09-032")
def test_a_manager_revision_of_pending_revision_terms_is_refused_whole(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A pending revision's end time, proposed again, registers nothing."""
    actor, dl = finder_actor_and_dl
    case = _build_active_embargo_case_with_case_manager(dl, actor.id_)
    _add_participant(dl, case.id_, OTHER)
    revision_end = days_from_now_utc(90)
    _revise(dl, actor.id_, case.id_, revision_end)
    before = _snapshot(dl, case.id_)

    with pytest.raises(VultronInvalidStateTransitionError, match="EP-09-032"):
        _revise(dl, actor.id_, case.id_, revision_end)

    assert _snapshot(dl, case.id_) == before


@pytest.mark.spec("EP-09-020")
def test_a_manager_counter_proposal_of_the_in_force_terms_is_committed(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """During a revision, the in-force end time is a counter-proposal."""
    actor, dl = finder_actor_and_dl
    case = _build_active_embargo_case_with_case_manager(dl, actor.id_)
    _add_participant(dl, case.id_, OTHER)
    _revise(dl, actor.id_, case.id_, days_from_now_utc(90))
    registered_before = len(_case(dl, case.id_).embargo_register)

    result = _revise(dl, actor.id_, case.id_, _active_end_time(dl, case.id_))

    assert result.activity is not None
    updated = _case(dl, case.id_)
    assert len(updated.embargo_register) == registered_before + 1
    assert len(updated.proposed_embargo_ids) == 2
    assert updated.current_status.em.state == EM.REVISE


def test_the_trigger_and_received_paths_share_one_terms_comparison() -> None:
    """Both paths compose ``EmbargoTermsNotHeldNode`` (AC-3, CS-22-001)."""
    case_id = "https://example.org/cases/c"
    embargo = EmbargoEvent(context=case_id, end_time=days_from_now_utc(30))
    result_out: dict[str, object] = {}
    trigger = propose_embargo_trigger_bt(
        case_id=case_id,
        actor_id="https://example.org/actors/a",
        embargo=embargo,
        result_out=result_out,
        activity_builder=lambda to: ("id", "{}"),
    )
    received = case_manager_admits_proposal_guard(
        case_id=case_id, embargo_id=embargo.id_, embargo=embargo
    )

    trigger_guards = [
        n for n in trigger.iterate() if isinstance(n, EmbargoTermsNotHeldNode)
    ]
    received_guards = [
        n for n in received.children if isinstance(n, EmbargoTermsNotHeldNode)
    ]

    assert len(trigger_guards) == 1
    assert len(received_guards) == 1
    # The trigger's copy refuses through the use case's result_out; the
    # received one has none, so a repeat stays a SKIPPED no-op there.
    assert trigger_guards[0]._result_out is result_out
    assert received_guards[0]._result_out is None
