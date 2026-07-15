"""Tests for SvcAcceptEmbargoUseCase."""

from typing import cast

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.use_cases.triggers.embargo import (
    SvcAcceptEmbargoUseCase,
    _is_case_owner,
)
from vultron.core.use_cases.triggers.requests import (
    AcceptEmbargoTriggerRequest,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

from .conftest import (
    _build_active_embargo_case,
    _build_proposed_embargo_case_no_owner_attribution,
    _persist_actor,
)


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
    updated_case = cast(as_VulnerabilityCase, updated_case)
    updated_participant = cast(as_CaseParticipant, updated_participant)
    assert updated_case.current_status.em_state == EM.ACTIVE
    assert updated_case.active_embargo == case.active_embargo
    assert updated_participant.embargo_consent_state == PEC.SIGNATORY.value
    assert case.active_embargo in updated_participant.accepted_embargo_ids


def test_is_case_owner_fail_closed_when_attributed_to_is_none() -> None:
    """_is_case_owner must return False when case.attributed_to is None.

    This prevents any actor from being granted owner privileges on a case with
    missing owner attribution. The function must be fail-closed, not fail-open.
    """
    case = as_VulnerabilityCase(name="Orphan case")
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
    updated_case = cast(as_VulnerabilityCase, updated_case)
    updated_participant = cast(as_CaseParticipant, updated_participant)

    assert updated_case.current_status.em_state == EM.PROPOSED
    assert updated_participant.embargo_consent_state == PEC.SIGNATORY.value
