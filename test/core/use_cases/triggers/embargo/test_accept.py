"""Tests for SvcAcceptEmbargoUseCase."""

from typing import cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.use_cases.triggers.embargo import (
    SvcAcceptEmbargoUseCase,
    _is_case_owner,
)
from vultron.core.use_cases.triggers.requests import (
    AcceptEmbargoTriggerRequest,
)
from vultron.errors import VultronNotFoundError
from vultron.wire.as2.factories import em_propose_embargo_activity
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

from .conftest import (
    _build_active_embargo_case,
    _build_proposed_embargo_case_no_owner_attribution,
    _build_unbound_case_with_case_manager,
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
    assert case.current_status.em.state == EM.PROPOSED

    request = AcceptEmbargoTriggerRequest(
        actor_id=finder.id_,
        case_id=case.id_,
        proposal_id=proposal.id_,
    )

    result = SvcAcceptEmbargoUseCase(
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

    assert updated_case.current_status.em.state == EM.PROPOSED
    assert updated_participant.embargo_consent_state == PEC.SIGNATORY.value


# ---------------------------------------------------------------------------
# Ported from the retired ``TriggerService`` suite (#3833): the owner-side
# accept activates the embargo, and the proposal lookups fail closed.
# ---------------------------------------------------------------------------


def _owner_accept(dl: SqliteDataLayer, request: AcceptEmbargoTriggerRequest):
    return SvcAcceptEmbargoUseCase(
        dl,
        request,
        trigger_activity=TriggerActivityAdapter(dl),
        sync_port=SyncActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()


def _case_with_open_proposal(
    dl: SqliteDataLayer, owner_id: str
) -> tuple[VulnerabilityCase, str]:
    """A case at EM.PROPOSED whose only open proposal is the owner's."""
    case = _build_unbound_case_with_case_manager(dl, owner_id)
    embargo = as_EmbargoEvent(context=case.id_, end_time=days_from_now_utc(45))
    proposal = em_propose_embargo_activity(
        embargo, context=case.id_, actor=owner_id
    )
    dl.create(embargo)
    dl.create(proposal)
    case.append_case_status(em_state=EM.PROPOSED)
    case.proposed_embargoes.append(embargo.id_)
    case.pending_embargo_proposal_index[embargo.id_] = proposal.id_
    dl.save(case)
    return case, proposal.id_


@pytest.mark.spec("EP-08-002")
def test_accept_embargo_activates_the_proposed_embargo(
    owner_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """PROPOSED → ACTIVE, and the case now names the embargo as active."""
    owner, dl = owner_actor_and_dl
    case, proposal_id = _case_with_open_proposal(dl, owner.id_)

    result = _owner_accept(
        dl,
        AcceptEmbargoTriggerRequest(
            actor_id=owner.id_, case_id=case.id_, proposal_id=proposal_id
        ),
    )

    assert result.activity is not None
    updated = cast(VulnerabilityCase, dl.read(case.id_))
    assert updated.current_status.em.state == EM.ACTIVE
    assert updated.active_embargo is not None


@pytest.mark.spec("EP-08-002")
def test_accept_embargo_without_proposal_id_resolves_the_open_proposal(
    owner_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """``proposal_id`` omitted: the one open proposal is the one accepted."""
    owner, dl = owner_actor_and_dl
    case, _ = _case_with_open_proposal(dl, owner.id_)

    result = _owner_accept(
        dl, AcceptEmbargoTriggerRequest(actor_id=owner.id_, case_id=case.id_)
    )

    assert result.activity is not None
    updated = cast(VulnerabilityCase, dl.read(case.id_))
    assert updated.current_status.em.state == EM.ACTIVE


def test_accept_embargo_with_no_open_proposal_raises_not_found(
    owner_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    owner, dl = owner_actor_and_dl
    case = _build_unbound_case_with_case_manager(dl, owner.id_)

    with pytest.raises(VultronNotFoundError):
        _owner_accept(
            dl,
            AcceptEmbargoTriggerRequest(actor_id=owner.id_, case_id=case.id_),
        )


def test_accept_embargo_with_unknown_proposal_id_raises_not_found(
    owner_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    owner, dl = owner_actor_and_dl
    case = _build_unbound_case_with_case_manager(dl, owner.id_)

    with pytest.raises(VultronNotFoundError):
        _owner_accept(
            dl,
            AcceptEmbargoTriggerRequest(
                actor_id=owner.id_,
                case_id=case.id_,
                proposal_id="urn:uuid:no-such-proposal",
            ),
        )
