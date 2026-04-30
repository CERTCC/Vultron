"""Regression tests for embargo trigger use cases."""

from collections.abc import Generator
from typing import cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.use_cases.triggers.embargo import (
    SvcAcceptEmbargoUseCase,
    SvcRejectEmbargoUseCase,
)
from vultron.core.use_cases.triggers.requests import (
    AcceptEmbargoTriggerRequest,
    RejectEmbargoTriggerRequest,
)
from vultron.wire.as2.factories import em_propose_embargo_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Invite
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import (
    CaseParticipant,
    FinderParticipant,
    VendorParticipant,
)
from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase


def _persist_actor(dl: SqliteDataLayer, name: str) -> as_Service:
    actor = as_Service(name=name)
    dl.create(actor)
    return actor


def _build_active_embargo_case(
    dl: SqliteDataLayer, owner_id: str, participant_id: str
) -> tuple[VulnerabilityCase, as_Invite, str]:
    case = VulnerabilityCase(
        name="Embargo regression case",
        attributed_to=owner_id,
    )
    embargo = EmbargoEvent(context=case.id_)
    proposal = em_propose_embargo_activity(
        embargo, context=case.id_, actor=owner_id
    )

    owner_participant = VendorParticipant(
        attributed_to=owner_id,
        context=case.id_,
        embargo_consent_state=PEC.SIGNATORY.value,
        accepted_embargo_ids=[embargo.id_],
    )
    participant = FinderParticipant(
        attributed_to=participant_id,
        context=case.id_,
        embargo_consent_state=PEC.INVITED.value,
    )

    case.case_participants = [owner_participant.id_, participant.id_]
    case.actor_participant_index = {
        owner_id: owner_participant.id_,
        participant_id: participant.id_,
    }
    case.current_status.em_state = EM.ACTIVE
    case.proposed_embargoes.append(embargo.id_)
    case.set_embargo(embargo.id_)

    dl.create(case)
    dl.create(embargo)
    dl.create(proposal)
    dl.create(owner_participant)
    dl.create(participant)

    return case, proposal, participant.id_


@pytest.fixture
def finder_actor_and_dl() -> (
    Generator[tuple[as_Service, SqliteDataLayer], None, None]
):
    finder_actor = as_Service(name="Finder Co")
    reset_datalayer(finder_actor.id_)
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=finder_actor.id_)
    dl.clear_all()
    dl.create(finder_actor)
    try:
        yield finder_actor, dl
    finally:
        dl.close()
        reset_datalayer(finder_actor.id_)


def test_non_owner_accept_embargo_on_active_case_updates_participant_only(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A later participant accept must not re-drive the shared case EM state."""
    finder, finder_dl = finder_actor_and_dl
    owner = _persist_actor(finder_dl, "Vendor Co")
    case, proposal, participant_id = _build_active_embargo_case(
        finder_dl, owner.id_, finder.id_
    )

    request = AcceptEmbargoTriggerRequest(
        actor_id=finder.id_,
        case_id=case.id_,
        proposal_id=proposal.id_,
    )

    result = SvcAcceptEmbargoUseCase(finder_dl, request).execute()

    assert "activity" in result

    updated_case = finder_dl.read(case.id_)
    updated_participant = finder_dl.read(participant_id)

    assert updated_case is not None
    assert updated_participant is not None
    updated_case = cast(VulnerabilityCase, updated_case)
    updated_participant = cast(CaseParticipant, updated_participant)
    assert updated_case.current_status.em_state == EM.ACTIVE
    assert updated_case.active_embargo == case.active_embargo
    assert updated_participant.embargo_consent_state == PEC.SIGNATORY.value
    assert case.active_embargo in updated_participant.accepted_embargo_ids


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

    result = SvcRejectEmbargoUseCase(finder_dl, request).execute()

    assert "activity" in result

    updated_case = finder_dl.read(case.id_)
    updated_participant = finder_dl.read(participant_id)

    assert updated_case is not None
    assert updated_participant is not None
    updated_case = cast(VulnerabilityCase, updated_case)
    updated_participant = cast(CaseParticipant, updated_participant)
    assert updated_case.current_status.em_state == EM.ACTIVE
    assert updated_case.active_embargo == case.active_embargo
    assert updated_participant.embargo_consent_state == PEC.DECLINED.value
