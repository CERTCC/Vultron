"""Tests for SvcAcceptEmbargoUseCase."""

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
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.use_cases.triggers.embargo import (
    SvcAcceptEmbargoUseCase,
    _is_case_owner,
)
from vultron.core.use_cases.triggers.requests import (
    AcceptEmbargoTriggerRequest,
)
from vultron.errors import VultronNotFoundError
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

from .conftest import (
    _assert_asked_case_manager,
    _build_active_embargo_case,
    _build_proposed_embargo_case_no_owner_attribution,
    _build_unbound_case_with_case_manager,
    _case_with_open_proposal,
    _open_revision,
    _persist_actor,
)


@pytest.mark.spec("EP-09-008")
def test_non_manager_accept_embargo_asks_the_case_manager(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A participant's accept asks the CASE_MANAGER and writes nothing."""
    finder, finder_dl = finder_actor_and_dl
    owner = _persist_actor(finder_dl, "Vendor Co")
    case, _, participant_id = _build_active_embargo_case(
        finder_dl, owner.id_, finder.id_
    )
    proposal, revision_id = _open_revision(
        finder_dl, case.id_, owner.id_, participant_id
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
    assert updated_case.current_status.em.state == EM.REVISE
    assert updated_case.active_embargo == case.active_embargo
    assert updated_case.proposed_embargo_ids == [revision_id]
    # Not the CASE_MANAGER: the consent is asked for, not recorded here; the
    # replica moves when the manager's commit is announced (EP-09-008).
    assert (
        updated_participant.consent_for(revision_id)
        == EmbargoConsentState.INVITED
    )
    _assert_asked_case_manager(
        finder_dl,
        actor_id=finder.id_,
        case_id=case.id_,
        manager_id=owner.id_,
        activity_type="Accept",
        event_type=MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE.value,
    )


@pytest.mark.xfail(
    strict=True,
    raises=VultronNotFoundError,
    reason=(
        "EP-09-012: the trigger resolves only open proposals, so the "
        "embargo in force cannot be answered by Invite id. Tracked by #4373."
    ),
)
@pytest.mark.spec("EP-09-012")
def test_accept_embargo_answers_the_embargo_in_force_by_invite_id(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """An ``INVITED`` row on the active embargo is answerable by Invite id."""
    finder, finder_dl = finder_actor_and_dl
    owner = _persist_actor(finder_dl, "Vendor Co")
    case, invite, _ = _build_active_embargo_case(
        finder_dl, owner.id_, finder.id_
    )

    result = SvcAcceptEmbargoUseCase(
        finder_dl,
        AcceptEmbargoTriggerRequest(
            actor_id=finder.id_, case_id=case.id_, proposal_id=invite.id_
        ),
        trigger_activity=TriggerActivityAdapter(finder_dl),
        sync_port=SyncActivityAdapter(finder_dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()

    assert result.activity is not None


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
    assert (
        updated_participant.consent_for(case.proposed_embargo_ids[0])
        == EmbargoConsentState.INVITED
    )


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
    # As the CASE_MANAGER the decision is a canonical entry every replica
    # replays (#4085), so the Accept itself is addressed to nobody.
    assert (
        MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE.value
        in committed_event_types(dl, case.id_)
    )
    assert not activity_of(result).get("to")


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
