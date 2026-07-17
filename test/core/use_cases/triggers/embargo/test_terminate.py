"""Tests for SvcTerminateEmbargoUseCase."""

import pytest
from typing import cast

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.use_cases.triggers.embargo import SvcTerminateEmbargoUseCase
from vultron.core.use_cases.triggers.requests import (
    TerminateEmbargoTriggerRequest,
)
from vultron.errors import VultronInvalidStateTransitionError
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

from .conftest import (
    _build_active_embargo_case,
    _build_no_embargo_case_with_case_manager,
    _persist_actor,
)


def test_terminate_embargo_transitions_case_to_exited_via_bt_path(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """TerminateEmbargo transitions ACTIVE → EXITED and clears active_embargo."""
    finder, finder_dl = finder_actor_and_dl
    owner = _persist_actor(finder_dl, "Vendor Co")
    case, _, participant_id = _build_active_embargo_case(
        finder_dl, owner.id_, finder.id_
    )
    request = TerminateEmbargoTriggerRequest(
        actor_id=owner.id_,
        case_id=case.id_,
    )

    result = SvcTerminateEmbargoUseCase(
        finder_dl, request, trigger_activity=TriggerActivityAdapter(finder_dl)
    ).execute()

    assert "activity" in result
    updated_case = cast(as_VulnerabilityCase, finder_dl.read(case.id_))
    updated_participant = cast(
        as_CaseParticipant, finder_dl.read(participant_id)
    )
    assert updated_case.current_status.em_state == EM.EXITED
    assert updated_case.active_embargo is None
    assert updated_participant.embargo_consent_state == PEC.NO_EMBARGO.value


def test_terminate_embargo_no_active_embargo_raises_via_bt_node(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """HasActiveEmbargoNode raises VultronInvalidStateTransitionError when no active embargo.

    Verifies that the guard previously in _prepare() is now enforced by the BT
    node (AC-5 / LST-05): the use-case layer no longer checks case state inline.
    """
    _, finder_dl = finder_actor_and_dl
    owner = _persist_actor(finder_dl, "Vendor Co")
    case = _build_no_embargo_case_with_case_manager(finder_dl, owner.id_)
    request = TerminateEmbargoTriggerRequest(
        actor_id=owner.id_,
        case_id=case.id_,
    )

    with pytest.raises(VultronInvalidStateTransitionError):
        SvcTerminateEmbargoUseCase(
            finder_dl,
            request,
            trigger_activity=TriggerActivityAdapter(finder_dl),
        ).execute()
