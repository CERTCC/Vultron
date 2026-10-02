"""Tests for SvcTerminateEmbargoUseCase."""

from typing import cast

import py_trees
import pytest
from py_trees.common import Status

from test.support.ledger import committed_event_types
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.bridge import BTBridge, BTExecutionResult
from vultron.core.behaviors.embargo.nodes import (
    EMBARGO_TEARDOWN_EVENT_TYPE,
    ask_case_manager_to_terminate_once,
)
from vultron.core.models.activity import VultronActivity
from vultron.core.models.case import VulnerabilityCase
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.use_cases.triggers.embargo import SvcTerminateEmbargoUseCase
from vultron.core.use_cases.triggers.requests import (
    TerminateEmbargoTriggerRequest,
)
from vultron.errors import (
    VultronInvalidStateTransitionError,
    VultronNotFoundError,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant

from .conftest import (
    _assert_asked_case_manager,
    _build_active_embargo_case,
    _build_unbound_case_with_case_manager,
    _persist_actor,
)


def test_terminate_embargo_transitions_case_to_exited_via_bt_path(
    owner_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """TerminateEmbargo transitions ACTIVE → EXITED and clears active_embargo.

    Runs in the *owner's* store, because the owner is the requesting actor and a
    trigger's BT reads and writes the executing actor's own store (ADR-0073).
    The finder is a peer here: its participant record lives in the owner's
    replica of the case, which is what the assertion below reads.
    """
    owner, owner_dl = owner_actor_and_dl
    finder = _persist_actor(owner_dl, "Finder Co")
    case, _, participant_id = _build_active_embargo_case(
        owner_dl, owner.id_, finder.id_
    )
    request = TerminateEmbargoTriggerRequest(
        actor_id=owner.id_,
        case_id=case.id_,
    )

    result = SvcTerminateEmbargoUseCase(
        owner_dl,
        request,
        trigger_activity=TriggerActivityAdapter(owner_dl),
        sync_port=SyncActivityAdapter(owner_dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()

    assert result.activity is not None
    updated_case = cast(VulnerabilityCase, owner_dl.read(case.id_))
    updated_participant = cast(
        as_CaseParticipant, owner_dl.read(participant_id)
    )
    assert updated_case.current_status.em.state == EM.EXITED
    assert updated_case.active_embargo is None
    assert (
        updated_participant.embargo_consent_state == PEC.UNBOUND_EXITED.value
    )
    assert EMBARGO_TEARDOWN_EVENT_TYPE in committed_event_types(
        owner_dl, case.id_
    )


def test_terminate_embargo_no_active_embargo_raises_via_bt_node(
    owner_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """HasActiveEmbargoNode raises VultronInvalidStateTransitionError when no active embargo.

    Verifies that the guard previously in _prepare() is now enforced by the BT
    node (AC-5 / LST-05): the use-case layer no longer checks case state inline.
    """
    owner, owner_dl = owner_actor_and_dl
    case = _build_unbound_case_with_case_manager(owner_dl, owner.id_)
    request = TerminateEmbargoTriggerRequest(
        actor_id=owner.id_,
        case_id=case.id_,
    )

    with pytest.raises(VultronInvalidStateTransitionError):
        SvcTerminateEmbargoUseCase(
            owner_dl,
            request,
            trigger_activity=TriggerActivityAdapter(owner_dl),
            sync_port=SyncActivityAdapter(owner_dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()


@pytest.mark.spec("EP-08-004")
def test_terminate_embargo_forgets_every_open_revision_via_bt_path(
    owner_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Termination through the trigger decides every open revision at once.

    Two revisions of the active embargo are open; after ET both records are
    empty, so the next default selection after ``EXITED → PROPOSED`` cannot
    pick a revision of an embargo that no longer exists (EP-08-004).
    """
    owner, owner_dl = owner_actor_and_dl
    finder = _persist_actor(owner_dl, "Finder Co")
    case, _, _participant_id = _build_active_embargo_case(
        owner_dl, owner.id_, finder.id_
    )
    case_obj = cast(VulnerabilityCase, owner_dl.read(case.id_))
    revision_a = f"{case.id_}/embargo_events/revision-a"
    revision_b = f"{case.id_}/embargo_events/revision-b"
    case_obj.proposed_embargoes = [
        *case_obj.proposed_embargoes,
        revision_a,
        revision_b,
    ]
    case_obj.pending_embargo_proposal_index = {
        **case_obj.pending_embargo_proposal_index,
        revision_a: f"{case.id_}/embargo_proposals/a",
        revision_b: f"{case.id_}/embargo_proposals/b",
    }
    owner_dl.save(case_obj)

    SvcTerminateEmbargoUseCase(
        owner_dl,
        TerminateEmbargoTriggerRequest(actor_id=owner.id_, case_id=case.id_),
        trigger_activity=TriggerActivityAdapter(owner_dl),
        sync_port=SyncActivityAdapter(owner_dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()

    updated_case = cast(VulnerabilityCase, owner_dl.read(case.id_))
    assert updated_case.current_status.em.state == EM.EXITED
    assert updated_case.proposed_embargoes == []
    assert updated_case.pending_embargo_proposal_index == {}


# ---------------------------------------------------------------------------
# Ported from the retired ``TriggerService`` suite (#3833)
# ---------------------------------------------------------------------------


@pytest.mark.spec("TRIG-07-001")
def test_terminate_embargo_queues_the_announce_in_the_outbox(
    owner_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    owner, dl = owner_actor_and_dl
    case, _, _ = _build_active_embargo_case(
        dl, owner.id_, _persist_actor(dl, "Finder Co").id_
    )
    before = set(dl.outbox_list())

    SvcTerminateEmbargoUseCase(
        dl,
        TerminateEmbargoTriggerRequest(actor_id=owner.id_, case_id=case.id_),
        trigger_activity=TriggerActivityAdapter(dl),
        sync_port=SyncActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()

    assert len(set(dl.outbox_list()) - before) >= 1


@pytest.mark.spec("EMB-19-001")
def test_manager_terminate_queues_nothing_addressed_to_itself(
    owner_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """The managing owner's ``Remove`` goes to the finder only (#4112).

    Addressed to itself, the manager would deliver its own teardown back to
    its inbox (CLP-10-001, ADR-0109).
    """
    owner, dl = owner_actor_and_dl
    finder = _persist_actor(dl, "Finder Co")
    case, _, _ = _build_active_embargo_case(dl, owner.id_, finder.id_)

    SvcTerminateEmbargoUseCase(
        dl,
        TerminateEmbargoTriggerRequest(actor_id=owner.id_, case_id=case.id_),
        trigger_activity=TriggerActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
        sync_port=SyncActivityAdapter(dl),
    ).execute()

    queued = [cast(VultronActivity, dl.read(i)) for i in dl.outbox_list()]
    assert [a.to for a in queued if a.type_ == "Remove"] == [[finder.id_]]
    assert not any(
        owner.id_ in [*(a.to or []), *(a.cc or [])] for a in queued
    ), "the CASE_MANAGER must not address its own outbox to itself"


@pytest.mark.spec("EP-09-008")
def test_non_manager_terminate_asks_the_case_manager(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A participant's terminate goes to the CASE_MANAGER; nothing exits."""
    finder, finder_dl = finder_actor_and_dl
    owner = _persist_actor(finder_dl, "Vendor Co")
    case, _, _ = _build_active_embargo_case(finder_dl, owner.id_, finder.id_)

    SvcTerminateEmbargoUseCase(
        finder_dl,
        TerminateEmbargoTriggerRequest(actor_id=finder.id_, case_id=case.id_),
        trigger_activity=TriggerActivityAdapter(finder_dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()

    updated = cast(VulnerabilityCase, finder_dl.read(case.id_))
    assert updated.current_status.em.state == EM.ACTIVE
    assert updated.active_embargo == case.active_embargo
    assert committed_event_types(finder_dl, case.id_) == []
    _assert_asked_case_manager(
        finder_dl,
        actor_id=finder.id_,
        case_id=case.id_,
        manager_id=owner.id_,
        activity_type="Remove",
        event_type=EMBARGO_TEARDOWN_EVENT_TYPE,
    )


def _run_cascade_ask(
    dl: SqliteDataLayer,
    actor_id: str,
    case: VulnerabilityCase,
    manager_id: str,
) -> BTExecutionResult:
    """Run the received P/X/A cascade's ask, as ThreatTerminationBranchNode
    does for a non-manager receiver."""
    py_trees.blackboard.Blackboard.storage["/embargo_id"] = case.active_embargo
    py_trees.blackboard.Blackboard.storage["/case_manager_id"] = manager_id
    return BTBridge(
        datalayer=dl,
        trigger_activity=TriggerActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute_with_setup(
        tree=ask_case_manager_to_terminate_once(case.id_), actor_id=actor_id
    )


def _terminate(dl: SqliteDataLayer, actor_id: str, case_id: str):
    return SvcTerminateEmbargoUseCase(
        dl,
        TerminateEmbargoTriggerRequest(actor_id=actor_id, case_id=case_id),
        trigger_activity=TriggerActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()


@pytest.mark.spec("SYNC-11-002")
def test_a_trigger_ask_suppresses_the_cascades_repeat(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """The trigger and the cascade key one store alike (#4147)."""
    finder, finder_dl = finder_actor_and_dl
    owner = _persist_actor(finder_dl, "Vendor Co")
    case, _, _ = _build_active_embargo_case(finder_dl, owner.id_, finder.id_)
    _terminate(finder_dl, finder.id_, case.id_)
    queued = finder_dl.outbox_list()
    assert len(queued) == 1

    result = _run_cascade_ask(finder_dl, finder.id_, case, owner.id_)

    # SUCCESS with nothing new queued is the suppression arm: the send arm
    # either queues an ask or fails the tree (BT-14-001).
    assert result.status == Status.SUCCESS
    assert not result.internal_error
    assert finder_dl.outbox_list() == queued


@pytest.mark.spec("SYNC-11-002")
def test_a_cascade_ask_suppresses_the_triggers_repeat(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    finder, finder_dl = finder_actor_and_dl
    owner = _persist_actor(finder_dl, "Vendor Co")
    case, _, _ = _build_active_embargo_case(finder_dl, owner.id_, finder.id_)
    first = _run_cascade_ask(finder_dl, finder.id_, case, owner.id_)
    assert first.status == Status.SUCCESS
    queued = finder_dl.outbox_list()
    assert len(queued) == 1

    result = _terminate(finder_dl, finder.id_, case.id_)

    assert result.activity is None
    assert finder_dl.outbox_list() == queued


def test_terminate_embargo_unknown_actor_raises_not_found(
    owner_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    owner, dl = owner_actor_and_dl
    case, _, _ = _build_active_embargo_case(
        dl, owner.id_, _persist_actor(dl, "Finder Co").id_
    )

    with pytest.raises(VultronNotFoundError):
        SvcTerminateEmbargoUseCase(
            dl,
            TerminateEmbargoTriggerRequest(
                actor_id="urn:uuid:no-such-actor", case_id=case.id_
            ),
            trigger_activity=TriggerActivityAdapter(dl),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()
