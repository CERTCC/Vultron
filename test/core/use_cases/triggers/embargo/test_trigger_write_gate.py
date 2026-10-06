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
"""A trigger writes shared EM state only as the CASE_MANAGER (EP-09-008).

A participant that does not hold ``CVDRole.CASE_MANAGER`` emits its proposal to
the manager, records it in the pending-assertion store, and writes no EM state;
its replica moves when the manager's commit is announced (#3962; Concern #3918,
ADR-0113).
"""

from datetime import UTC, datetime, timedelta
from typing import cast

import pytest

from test.support.ledger import committed_event_types
from test.support.trigger_results import activity_of
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.models.activity import VultronActivity
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.pending_assertion import get_pending_assertion_store
from vultron.core.states.em import EM
from vultron.core.use_cases.triggers.embargo import (
    SvcAcceptEmbargoUseCase,
    SvcProposeEmbargoRevisionUseCase,
    SvcProposeEmbargoUseCase,
    SvcRejectEmbargoUseCase,
    SvcTerminateEmbargoUseCase,
)
from vultron.core.use_cases.triggers.requests import (
    AcceptEmbargoTriggerRequest,
    ProposeEmbargoRevisionTriggerRequest,
    ProposeEmbargoTriggerRequest,
    RejectEmbargoTriggerRequest,
    TerminateEmbargoTriggerRequest,
)
from vultron.enums.roles import CVDRole
from vultron.errors import VultronError, VultronInvalidStateTransitionError
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import (
    FinderParticipant,
    VendorParticipant,
)

from .conftest import (
    _assert_asked_case_manager,
    _build_active_embargo_case,
    _persist_actor,
)

MANAGER = "https://example.org/actors/case-actor"


def _case_managed_by_someone_else(
    dl: SqliteDataLayer, finder_id: str
) -> VulnerabilityCase:
    """Case at ``EM.NONE`` whose CASE_MANAGER is not the finder."""
    case = VulnerabilityCase(name="Gated trigger case", attributed_to=MANAGER)
    manager = VendorParticipant(
        attributed_to=MANAGER,
        context=case.id_,
    )
    manager.add_role(CVDRole.CASE_MANAGER)
    finder = FinderParticipant(
        attributed_to=finder_id,
        context=case.id_,
    )
    case.case_participants = [manager.id_, finder.id_]
    case.actor_participant_index = {
        MANAGER: manager.id_,
        finder_id: finder.id_,
    }
    case.append_case_status(em_state=EM.NONE)
    case.active_embargo = None
    dl.create(case)
    dl.create(manager)
    dl.create(finder)
    return case


@pytest.mark.spec("EP-09-008")
def test_non_manager_trigger_asks_and_writes_no_em_state(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Emit to the manager, record the ask, write nothing, declare nothing."""
    finder, finder_dl = finder_actor_and_dl
    case = _case_managed_by_someone_else(finder_dl, finder.id_)
    request = ProposeEmbargoTriggerRequest(
        actor_id=finder.id_,
        case_id=case.id_,
        end_time=datetime.now(tz=UTC) + timedelta(days=7),
    )

    result = SvcProposeEmbargoUseCase(
        finder_dl, request, trigger_activity=TriggerActivityAdapter(finder_dl)
    ).execute()

    updated = cast(VulnerabilityCase, finder_dl.read(case.id_))
    assert updated.current_status.em.state == EM.NONE

    queued = [
        cast(VultronActivity, finder_dl.read(i))
        for i in finder_dl.outbox_list()
    ]
    invites = [a for a in queued if a.type_ == "Invite"]
    assert len(invites) == 1
    assert invites[0].to == [MANAGER]
    # A declaration would be a ledger commit, not an outbox item (AC-3).
    assert committed_event_types(finder_dl, case.id_) == [], (
        "a non-manager must not declare an EM state it has not been given"
    )

    assert result.activity is not None
    activity_id = activity_of(result)["id"]
    store = get_pending_assertion_store(finder.id_)
    assert store.is_suppressed(
        case.id_, MessageSemantics.INVITE_TO_EMBARGO_ON_CASE.value, activity_id
    )


def _propose(
    dl: SqliteDataLayer, actor_id: str, case_id: str, end_time: datetime
):
    return SvcProposeEmbargoUseCase(
        dl,
        ProposeEmbargoTriggerRequest(
            actor_id=actor_id, case_id=case_id, end_time=end_time
        ),
        trigger_activity=TriggerActivityAdapter(dl),
    ).execute()


@pytest.mark.spec("SYNC-11-002")
def test_repeated_non_manager_proposal_is_suppressed(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """The same terms asked again inside the window are not re-emitted."""
    finder, finder_dl = finder_actor_and_dl
    case = _case_managed_by_someone_else(finder_dl, finder.id_)
    end_time = datetime.now(tz=UTC) + timedelta(days=7)

    first = _propose(finder_dl, finder.id_, case.id_, end_time)
    outbox_after_first = list(finder_dl.outbox_list())
    second = _propose(finder_dl, finder.id_, case.id_, end_time)

    assert first.activity is not None
    assert second.activity is None
    assert list(finder_dl.outbox_list()) == outbox_after_first

    # Different terms are a different assertion, so they are sent.
    third = _propose(
        finder_dl, finder.id_, case.id_, end_time + timedelta(days=1)
    )
    assert third.activity is not None


def _answer_or_teardown(
    kind: str,
    dl: SqliteDataLayer,
    actor_id: str,
    case_id: str,
    proposal_id: str,
):
    """Run the non-manager *kind* trigger once against the stored case."""
    factory = TriggerActivityAdapter(dl)
    render = As2WireRenderAdapter()
    if kind == "accept":
        return SvcAcceptEmbargoUseCase(
            dl,
            AcceptEmbargoTriggerRequest(
                actor_id=actor_id, case_id=case_id, proposal_id=proposal_id
            ),
            trigger_activity=factory,
            wire_render_port=render,
        ).execute()
    if kind == "reject":
        return SvcRejectEmbargoUseCase(
            dl,
            RejectEmbargoTriggerRequest(
                actor_id=actor_id, case_id=case_id, proposal_id=proposal_id
            ),
            trigger_activity=factory,
            wire_render_port=render,
        ).execute()
    return SvcTerminateEmbargoUseCase(
        dl,
        TerminateEmbargoTriggerRequest(actor_id=actor_id, case_id=case_id),
        trigger_activity=factory,
        wire_render_port=render,
    ).execute()


@pytest.mark.spec("SYNC-11-002")
@pytest.mark.parametrize("kind", ["accept", "reject", "terminate"])
def test_repeated_non_manager_answer_or_teardown_is_suppressed(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer], kind: str
) -> None:
    """The same answer or teardown asked again inside the window is not
    re-emitted: its subject (the proposal, the embargo) is still pending."""
    finder, finder_dl = finder_actor_and_dl
    owner = _persist_actor(finder_dl, "Vendor Co")
    case, proposal, _ = _build_active_embargo_case(
        finder_dl, owner.id_, finder.id_
    )

    first = _answer_or_teardown(
        kind, finder_dl, finder.id_, case.id_, proposal.id_
    )
    outbox_after_first = list(finder_dl.outbox_list())
    second = _answer_or_teardown(
        kind, finder_dl, finder.id_, case.id_, proposal.id_
    )

    assert first.activity is not None
    assert second.activity is None
    assert list(finder_dl.outbox_list()) == outbox_after_first


@pytest.mark.spec("EP-09-008")
def test_non_manager_revision_asks_and_writes_no_em_state(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A participant's revision goes to the CASE_MANAGER; EM stays ACTIVE."""
    finder, finder_dl = finder_actor_and_dl
    owner = _persist_actor(finder_dl, "Vendor Co")
    case, _, _ = _build_active_embargo_case(finder_dl, owner.id_, finder.id_)

    SvcProposeEmbargoRevisionUseCase(
        finder_dl,
        ProposeEmbargoRevisionTriggerRequest(
            actor_id=finder.id_,
            case_id=case.id_,
            end_time=datetime.now(tz=UTC) + timedelta(days=30),
        ),
        trigger_activity=TriggerActivityAdapter(finder_dl),
    ).execute()

    updated = cast(VulnerabilityCase, finder_dl.read(case.id_))
    assert updated.current_status.em.state == EM.ACTIVE
    assert updated.active_embargo == case.active_embargo
    assert updated.proposed_embargoes == case.proposed_embargoes
    assert committed_event_types(finder_dl, case.id_) == []
    _assert_asked_case_manager(
        finder_dl,
        actor_id=finder.id_,
        case_id=case.id_,
        manager_id=owner.id_,
        activity_type="Invite",
        event_type=MessageSemantics.INVITE_TO_EMBARGO_ON_CASE.value,
    )


@pytest.mark.spec("EP-09-001")
@pytest.mark.spec("EP-09-008")
def test_non_manager_propose_on_exited_case_is_refused_locally(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """An ``EXITED`` case admits no proposal, so nothing is asked or recorded.

    The non-manager arm runs no ``STRICT`` check, and the CASE_MANAGER's
    admission guard refuses without a ``Reject``; the read-only guard ahead
    of the arms keeps the ask from leaving a pending assertion behind.
    """
    finder, finder_dl = finder_actor_and_dl
    case = _case_managed_by_someone_else(finder_dl, finder.id_)
    case.append_case_status(em_state=EM.EXITED)
    finder_dl.save(case)
    request = ProposeEmbargoTriggerRequest(
        actor_id=finder.id_,
        case_id=case.id_,
        end_time=datetime.now(tz=UTC) + timedelta(days=7),
    )

    with pytest.raises(VultronInvalidStateTransitionError):
        SvcProposeEmbargoUseCase(
            finder_dl,
            request,
            trigger_activity=TriggerActivityAdapter(finder_dl),
        ).execute()

    assert finder_dl.outbox_list() == []
    assert finder_dl.list_objects("EmbargoEvent") == []
    store = get_pending_assertion_store(finder.id_)
    assert (
        store.pending_for_subject(
            case.id_,
            MessageSemantics.INVITE_TO_EMBARGO_ON_CASE.value,
            request.end_time.isoformat(),
        )
        is None
    )


@pytest.mark.spec("BT-19-001")
@pytest.mark.spec("EP-09-008")
def test_non_manager_propose_resolves_the_manager_before_storing_terms(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A failed routing guard leaves no orphan ``EmbargoEvent`` behind."""
    finder, finder_dl = finder_actor_and_dl
    case = _case_managed_by_someone_else(finder_dl, finder.id_)
    manager = finder_dl.read(case.actor_participant_index[MANAGER])
    assert isinstance(manager, CaseParticipant)
    manager.case_roles = [
        r for r in manager.case_roles if r != CVDRole.CASE_MANAGER
    ]
    finder_dl.save(manager)
    request = ProposeEmbargoTriggerRequest(
        actor_id=finder.id_,
        case_id=case.id_,
        end_time=datetime.now(tz=UTC) + timedelta(days=7),
    )

    with pytest.raises(VultronError):
        SvcProposeEmbargoUseCase(
            finder_dl,
            request,
            trigger_activity=TriggerActivityAdapter(finder_dl),
        ).execute()

    assert finder_dl.list_objects("EmbargoEvent") == []
    assert finder_dl.outbox_list() == []
