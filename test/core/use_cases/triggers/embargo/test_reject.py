"""Tests for SvcRejectEmbargoUseCase."""

from typing import cast

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.use_cases.triggers.embargo import SvcRejectEmbargoUseCase
from vultron.core.use_cases.triggers.requests import (
    RejectEmbargoTriggerRequest,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

from .conftest import _build_active_embargo_case, _persist_actor


def test_non_owner_reject_embargo_on_active_case_updates_participant_only(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A later participant reject must not unwind an already-active case embargo."""
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
        finder_dl, request, trigger_activity=TriggerActivityAdapter(finder_dl)
    ).execute()

    assert "activity" in result

    updated_case = finder_dl.read(case.id_)
    updated_participant = finder_dl.read(participant_id)

    assert updated_case is not None
    assert updated_participant is not None
    updated_case = cast(as_VulnerabilityCase, updated_case)
    updated_participant = cast(as_CaseParticipant, updated_participant)
    assert updated_case.current_status.em_state == EM.ACTIVE
    assert updated_case.active_embargo == case.active_embargo
    assert updated_participant.embargo_consent_state == PEC.DECLINED.value
