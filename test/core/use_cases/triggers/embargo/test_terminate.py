"""Tests for SvcTerminateEmbargoUseCase."""

import pytest
from typing import cast

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.use_cases.triggers.embargo import SvcTerminateEmbargoUseCase
from vultron.core.use_cases.triggers.requests import (
    TerminateEmbargoTriggerRequest,
)
from vultron.errors import VultronInvalidStateTransitionError
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant

from .conftest import (
    _build_active_embargo_case,
    _build_unbound_case_with_case_manager,
    _persist_actor,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter


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
        wire_render_port=As2WireRenderAdapter(),
    ).execute()

    assert "activity" in result
    updated_case = cast(VulnerabilityCase, owner_dl.read(case.id_))
    updated_participant = cast(
        as_CaseParticipant, owner_dl.read(participant_id)
    )
    assert updated_case.current_status.em.state == EM.EXITED
    assert updated_case.active_embargo is None
    assert updated_participant.embargo_consent_state == PEC.UNBOUND.value


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
        wire_render_port=As2WireRenderAdapter(),
    ).execute()

    updated_case = cast(VulnerabilityCase, owner_dl.read(case.id_))
    assert updated_case.current_status.em.state == EM.EXITED
    assert updated_case.proposed_embargoes == []
    assert updated_case.pending_embargo_proposal_index == {}
