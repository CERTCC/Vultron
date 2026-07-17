"""Tests for SvcProposeEmbargoUseCase."""

from datetime import datetime, timezone, timedelta

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.states.em import EM
from vultron.core.use_cases.triggers.embargo import SvcProposeEmbargoUseCase
from vultron.core.use_cases.triggers.requests import (
    ProposeEmbargoTriggerRequest,
)
from vultron.errors import VultronInvalidStateTransitionError
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

from .conftest import (
    _build_exited_case,
    _build_no_embargo_case_with_case_manager,
)


def test_propose_embargo_invalid_state_does_not_persist_embargo(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Invalid embargo proposals must not leave behind persisted embargoes."""
    finder, finder_dl = finder_actor_and_dl
    case = _build_exited_case(finder_dl, finder.id_)

    before = len(list(finder_dl.list_objects("EmbargoEvent")))
    request = ProposeEmbargoTriggerRequest(
        actor_id=finder.id_,
        case_id=case.id_,
        end_time=datetime.now(tz=timezone.utc) + timedelta(days=1),
    )

    with pytest.raises(VultronInvalidStateTransitionError):
        SvcProposeEmbargoUseCase(
            finder_dl,
            request,
            trigger_activity=TriggerActivityAdapter(finder_dl),
        ).execute()

    after = len(list(finder_dl.list_objects("EmbargoEvent")))
    assert after == before


def test_propose_embargo_updates_case_state_via_bt_path(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """ProposeEmbargo transitions EM.NONE → EM.PROPOSED and queues activity."""
    from typing import cast

    finder, finder_dl = finder_actor_and_dl
    case = _build_no_embargo_case_with_case_manager(finder_dl, finder.id_)
    request = ProposeEmbargoTriggerRequest(
        actor_id=finder.id_,
        case_id=case.id_,
        end_time=datetime.now(tz=timezone.utc) + timedelta(days=7),
    )

    result = SvcProposeEmbargoUseCase(
        finder_dl, request, trigger_activity=TriggerActivityAdapter(finder_dl)
    ).execute()

    assert "activity" in result
    updated_case = cast(as_VulnerabilityCase, finder_dl.read(case.id_))
    assert updated_case.current_status.em_state == EM.PROPOSED
    assert len(updated_case.proposed_embargoes) == 1
