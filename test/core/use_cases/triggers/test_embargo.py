"""Regression tests for embargo trigger use cases."""

from datetime import datetime, timezone, timedelta
from collections.abc import Generator
from typing import cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.states.roles import CVDRole
from vultron.core.use_cases.triggers.embargo import (
    SvcAcceptEmbargoUseCase,
    SvcProposeEmbargoUseCase,
    SvcRejectEmbargoUseCase,
    _is_case_owner,
)
from vultron.core.use_cases.triggers.requests import (
    AcceptEmbargoTriggerRequest,
    ProposeEmbargoTriggerRequest,
    RejectEmbargoTriggerRequest,
)
from vultron.errors import VultronInvalidStateTransitionError
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
        embargo_consent_state=PEC.SIGNATORY,
        accepted_embargo_ids=[embargo.id_],
    )
    owner_participant.add_role(CVDRole.CASE_MANAGER)
    participant = FinderParticipant(
        attributed_to=participant_id,
        context=case.id_,
        embargo_consent_state=PEC.INVITED,
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


def _build_proposed_embargo_case_no_owner_attribution(
    dl: SqliteDataLayer,
    actor_id: str,
    case_manager_id: str,
) -> tuple[VulnerabilityCase, as_Invite, str]:
    """Build a PROPOSED embargo case with ``attributed_to=None``.

    Simulates the historical case where owner attribution was not consistently
    populated. The case has a CASE_MANAGER participant (so sender_side_bt can
    run) but ``attributed_to`` is unset on the case itself.
    """
    case = VulnerabilityCase(name="No-attribution proposed embargo case")
    # attributed_to intentionally NOT set — this is the bug state

    embargo = EmbargoEvent(context=case.id_)
    proposal = em_propose_embargo_activity(
        embargo, context=case.id_, actor=case_manager_id
    )

    case_manager_participant = VendorParticipant(
        attributed_to=case_manager_id,
        context=case.id_,
        embargo_consent_state=PEC.SIGNATORY,
        accepted_embargo_ids=[embargo.id_],
    )
    case_manager_participant.add_role(CVDRole.CASE_MANAGER)

    actor_participant = FinderParticipant(
        attributed_to=actor_id,
        context=case.id_,
        embargo_consent_state=PEC.INVITED,
    )

    case.case_participants = [
        case_manager_participant.id_,
        actor_participant.id_,
    ]
    case.actor_participant_index = {
        case_manager_id: case_manager_participant.id_,
        actor_id: actor_participant.id_,
    }
    case.current_status.em_state = EM.PROPOSED
    case.proposed_embargoes.append(embargo.id_)

    dl.create(case)
    dl.create(embargo)
    dl.create(proposal)
    dl.create(case_manager_participant)
    dl.create(actor_participant)

    return case, proposal, actor_participant.id_


def _build_exited_case(
    dl: SqliteDataLayer, owner_id: str
) -> VulnerabilityCase:
    case = VulnerabilityCase(
        name="Exited embargo case",
        attributed_to=owner_id,
    )
    case.current_status.em_state = EM.EXITED
    dl.create(case)
    return case


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

    result = SvcAcceptEmbargoUseCase(
        finder_dl, request, trigger_activity=TriggerActivityAdapter(finder_dl)
    ).execute()

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

    result = SvcRejectEmbargoUseCase(
        finder_dl, request, trigger_activity=TriggerActivityAdapter(finder_dl)
    ).execute()

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


def test_is_case_owner_fail_closed_when_attributed_to_is_none() -> None:
    """_is_case_owner must return False when case.attributed_to is None.

    This prevents any actor from being granted owner privileges on a case with
    missing owner attribution. The function must be fail-closed, not fail-open.
    """
    case = VulnerabilityCase(name="Orphan case")
    assert case.attributed_to is None

    assert _is_case_owner(case, "https://example.org/alice") is False
    assert _is_case_owner(case, "https://example.org/bob") is False


def test_accept_embargo_when_attributed_to_is_none_does_not_activate_em(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """_is_case_owner must fail-closed: attributed_to=None must not activate EM.

    Guards against the fail-open bug where an unset attributed_to caused any
    calling actor to be treated as the case owner, allowing a non-owner to
    drive EM from PROPOSED to ACTIVE.
    """
    finder, finder_dl = finder_actor_and_dl
    case_manager = _persist_actor(finder_dl, "Vendor Co")
    case, proposal, participant_id = (
        _build_proposed_embargo_case_no_owner_attribution(
            finder_dl, finder.id_, case_manager.id_
        )
    )

    assert case.attributed_to is None
    assert case.current_status.em_state == EM.PROPOSED

    request = AcceptEmbargoTriggerRequest(
        actor_id=finder.id_,
        case_id=case.id_,
        proposal_id=proposal.id_,
    )

    result = SvcAcceptEmbargoUseCase(
        finder_dl, request, trigger_activity=TriggerActivityAdapter(finder_dl)
    ).execute()

    assert "activity" in result

    updated_case = finder_dl.read(case.id_)
    updated_participant = finder_dl.read(participant_id)

    assert updated_case is not None
    assert updated_participant is not None
    updated_case = cast(VulnerabilityCase, updated_case)
    updated_participant = cast(CaseParticipant, updated_participant)

    # With fail-closed behavior, EM must stay PROPOSED — no actor qualifies as
    # owner when attributed_to is None.
    assert updated_case.current_status.em_state == EM.PROPOSED
    # Participant consent IS updated (they accepted as a non-owner participant).
    assert updated_participant.embargo_consent_state == PEC.SIGNATORY.value


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
