"""Tests for SvcProposeEmbargoRevisionUseCase."""

from datetime import datetime, timezone, timedelta
from typing import cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.states.em import EM
from vultron.core.use_cases.triggers.embargo import (
    SvcProposeEmbargoRevisionUseCase,
)
from vultron.core.use_cases.triggers.requests import (
    ProposeEmbargoRevisionTriggerRequest,
)
from vultron.errors import VultronInvalidStateTransitionError
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase

from .conftest import (
    _build_active_embargo_case_with_case_manager,
    _build_no_embargo_case_with_case_manager,
)


def test_propose_embargo_revision_transitions_em_to_revise(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """SvcProposeEmbargoRevisionUseCase transitions EM.ACTIVE → EM.REVISE via BTBridge."""
    actor, dl = finder_actor_and_dl
    case = _build_active_embargo_case_with_case_manager(dl, actor.id_)

    request = ProposeEmbargoRevisionTriggerRequest(
        actor_id=actor.id_,
        case_id=case.id_,
        end_time=datetime.now(tz=timezone.utc) + timedelta(days=14),
    )

    result = SvcProposeEmbargoRevisionUseCase(
        dl, request, trigger_activity=TriggerActivityAdapter(dl)
    ).execute()

    assert "activity" in result
    updated_case = cast(VulnerabilityCase, dl.read(case.id_))
    assert updated_case.current_status.em_state == EM.REVISE
    assert len(updated_case.proposed_embargoes) == 2


def test_propose_embargo_revision_queues_outbox_activity(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """SvcProposeEmbargoRevisionUseCase enqueues a propose-embargo activity."""
    actor, dl = finder_actor_and_dl
    case = _build_active_embargo_case_with_case_manager(dl, actor.id_)

    outbox_before = dl.outbox_list_for_actor(actor.id_)

    request = ProposeEmbargoRevisionTriggerRequest(
        actor_id=actor.id_,
        case_id=case.id_,
        end_time=datetime.now(tz=timezone.utc) + timedelta(days=14),
    )

    SvcProposeEmbargoRevisionUseCase(
        dl, request, trigger_activity=TriggerActivityAdapter(dl)
    ).execute()

    outbox_after = dl.outbox_list_for_actor(actor.id_)
    assert len(outbox_after) > len(outbox_before)


def test_propose_embargo_revision_invalid_em_state_raises_error(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """SvcProposeEmbargoRevisionUseCase raises error when EM state is not ACTIVE/REVISE."""
    actor, dl = finder_actor_and_dl
    case = _build_no_embargo_case_with_case_manager(dl, actor.id_)

    request = ProposeEmbargoRevisionTriggerRequest(
        actor_id=actor.id_,
        case_id=case.id_,
        end_time=datetime.now(tz=timezone.utc) + timedelta(days=14),
    )

    with pytest.raises(VultronInvalidStateTransitionError):
        SvcProposeEmbargoRevisionUseCase(
            dl, request, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()


def test_propose_embargo_revision_invalid_state_does_not_persist_embargo(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Failed revision must not leave behind a persisted EmbargoEvent."""
    actor, dl = finder_actor_and_dl
    case = _build_no_embargo_case_with_case_manager(dl, actor.id_)

    before = len(list(dl.list_objects("EmbargoEvent")))

    request = ProposeEmbargoRevisionTriggerRequest(
        actor_id=actor.id_,
        case_id=case.id_,
        end_time=datetime.now(tz=timezone.utc) + timedelta(days=14),
    )

    with pytest.raises(VultronInvalidStateTransitionError):
        SvcProposeEmbargoRevisionUseCase(
            dl, request, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

    after = len(list(dl.list_objects("EmbargoEvent")))
    assert after == before


def test_propose_embargo_revision_in_revise_state_succeeds(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """SvcProposeEmbargoRevisionUseCase succeeds when EM is already REVISE.

    Guards against a regression where EM.REVISE → EM.REVISE counter-revision
    is incorrectly blocked.  Participant PEC states MUST NOT be reset on this
    path (only ACTIVE → REVISE triggers _cascade_pec_revise).
    """
    actor, dl = finder_actor_and_dl

    case = _build_active_embargo_case_with_case_manager(dl, actor.id_)
    case.current_status.em_state = EM.REVISE
    dl.save(case)

    participant_id = case.actor_participant_index[actor.id_]
    participant_before = cast(CaseParticipant, dl.read(participant_id))
    pec_before = participant_before.embargo_consent_state

    request = ProposeEmbargoRevisionTriggerRequest(
        actor_id=actor.id_,
        case_id=case.id_,
        end_time=datetime.now(tz=timezone.utc) + timedelta(days=21),
    )

    result = SvcProposeEmbargoRevisionUseCase(
        dl, request, trigger_activity=TriggerActivityAdapter(dl)
    ).execute()

    assert "activity" in result
    updated_case = cast(VulnerabilityCase, dl.read(case.id_))
    assert updated_case.current_status.em_state == EM.REVISE
    assert len(updated_case.proposed_embargoes) == 2

    participant_after = cast(CaseParticipant, dl.read(participant_id))
    assert participant_after.embargo_consent_state == pec_before
