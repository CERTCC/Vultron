"""Tests for SvcRejectEmbargoUseCase."""

from typing import cast

import pytest

from test.support.ledger import committed_event_types
from test.support.trigger_results import activity_of
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.events.base import MessageSemantics
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.use_cases.triggers.embargo import SvcRejectEmbargoUseCase
from vultron.core.use_cases.triggers.requests import (
    RejectEmbargoTriggerRequest,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant

from .conftest import (
    _assert_asked_case_manager,
    _build_active_embargo_case,
    _case_with_open_proposal,
    _persist_actor,
)


@pytest.mark.spec("EP-09-008")
def test_non_manager_reject_embargo_asks_the_case_manager(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A participant's reject asks the CASE_MANAGER and unwinds nothing."""
    finder, finder_dl = finder_actor_and_dl
    owner = _persist_actor(finder_dl, "Vendor Co")
    case, proposal, participant_id = _build_active_embargo_case(
        finder_dl, owner.id_, finder.id_
    )

    request = RejectEmbargoTriggerRequest(
        actor_id=finder.id_,
        case_id=case.id_,
        proposal_id=proposal.id_,
    )

    result = SvcRejectEmbargoUseCase(
        finder_dl,
        request,
        trigger_activity=TriggerActivityAdapter(finder_dl),
        sync_port=SyncActivityAdapter(finder_dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()

    assert result.activity is not None

    updated_case = finder_dl.read(case.id_)
    updated_participant = finder_dl.read(participant_id)

    assert updated_case is not None
    assert updated_participant is not None
    updated_case = cast(VulnerabilityCase, updated_case)
    updated_participant = cast(as_CaseParticipant, updated_participant)
    assert updated_case.current_status.em.state == EM.ACTIVE
    assert updated_case.active_embargo == case.active_embargo
    # Not the CASE_MANAGER: the refusal is asked for, not recorded here; the
    # replica moves when the manager's commit is announced (EP-09-008).
    assert updated_participant.embargo_consent_state == PEC.INVITED.value
    _assert_asked_case_manager(
        finder_dl,
        actor_id=finder.id_,
        case_id=case.id_,
        manager_id=owner.id_,
        activity_type="Reject",
        event_type=MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE.value,
    )


@pytest.mark.spec("EP-09-008")
@pytest.mark.spec("EP-09-007")
def test_manager_reject_embargo_commits_the_decision(
    owner_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """The CASE_MANAGER's reject unwinds the proposal and commits it (#4085).

    Every replica learns the decision from the committed entry, so the
    ``Reject`` itself is addressed to nobody (CLP-10-001).
    """
    owner, dl = owner_actor_and_dl
    case, proposal_id = _case_with_open_proposal(dl, owner.id_)

    result = SvcRejectEmbargoUseCase(
        dl,
        RejectEmbargoTriggerRequest(
            actor_id=owner.id_, case_id=case.id_, proposal_id=proposal_id
        ),
        trigger_activity=TriggerActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
        sync_port=SyncActivityAdapter(dl),
    ).execute()

    updated = cast(VulnerabilityCase, dl.read(case.id_))
    assert updated.current_status.em.state == EM.NONE
    assert updated.proposed_embargoes == []
    assert (
        MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE.value
        in committed_event_types(dl, case.id_)
    )
    assert not activity_of(result).get("to")
