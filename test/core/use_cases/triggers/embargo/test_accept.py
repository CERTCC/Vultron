"""Tests for SvcAcceptEmbargoUseCase."""

from typing import cast

import pytest

from test.support.act_runner import run_in_act
from test.support.ledger import committed_semantic_types
from test.support.trigger_results import activity_of
from vultron.adapters.driven.clock import SystemClock
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
)
from vultron.core.use_cases.triggers.requests import (
    AcceptEmbargoTriggerRequest,
)
from vultron.errors import VultronNotFoundError
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant

from .conftest import (
    _assert_asked_case_manager,
    _build_active_embargo_case,
    _build_unbound_case_with_case_manager,
    _case_owned_by_non_manager,
    _case_with_open_proposal,
    _open_revision,
    _persist_actor,
)


@pytest.mark.spec("EP-09-008")
@pytest.mark.spec("EP-09-017")
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

    result = run_in_act(
        SvcAcceptEmbargoUseCase(
            finder_dl,
            request,
            trigger_activity=TriggerActivityAdapter(finder_dl),
            sync_port=SyncActivityAdapter(finder_dl),
            wire_render_port=As2WireRenderAdapter(),
            clock=SystemClock(),
        )
    )

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
        semantic_type=MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE.value,
    )


# ---------------------------------------------------------------------------
# Ported from the retired ``TriggerService`` suite (#3833): the owner-side
# accept activates the embargo, and the proposal lookups fail closed.
# ---------------------------------------------------------------------------


def _owner_accept(dl: SqliteDataLayer, request: AcceptEmbargoTriggerRequest):
    return run_in_act(
        SvcAcceptEmbargoUseCase(
            dl,
            request,
            trigger_activity=TriggerActivityAdapter(dl),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            clock=SystemClock(),
        )
    )


@pytest.mark.spec("EP-08-002")
@pytest.mark.spec("EP-09-008")
@pytest.mark.spec("RF-08-001")
@pytest.mark.spec("VAM-05-008")
def test_accept_embargo_activates_the_proposed_embargo(
    owner_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """The owner-manager's accept is Add(EmbargoEvent)[target=VulnerabilityCase].

    PROPOSED → ACTIVE, the owner's row becomes ACCEPTED, and the decision is
    committed as the owner's activation (ADR-0180), never as a consent
    answer to the Invite.
    """
    owner, dl = owner_actor_and_dl
    case, proposal_id = _case_with_open_proposal(dl, owner.id_)
    embargo_id = case.proposed_embargo_ids[0]

    result = _owner_accept(
        dl,
        AcceptEmbargoTriggerRequest(
            actor_id=owner.id_, case_id=case.id_, proposal_id=proposal_id
        ),
    )

    activity = activity_of(result)
    assert activity["type"] == "Add"
    assert activity["object"]["id"] == embargo_id
    assert activity["target"] == case.id_
    # The decision names the Invite the trigger resolved (ADR-0180).
    assert activity["inReplyTo"] == proposal_id
    updated = cast(VulnerabilityCase, dl.read(case.id_))
    assert updated.current_status.em.state == EM.ACTIVE
    assert updated.active_embargo_id == embargo_id
    owner_participant = cast(
        as_CaseParticipant,
        dl.read(updated.actor_participant_index[owner.id_]),
    )
    assert (
        owner_participant.consent_for(embargo_id) == EmbargoConsentState.AGREED
    )
    # As the CASE_MANAGER the decision is a canonical entry every replica
    # replays (#4085), so the Accept itself is addressed to nobody.
    committed = committed_semantic_types(dl, case.id_)
    assert MessageSemantics.ACTIVATE_EMBARGO_ON_CASE.value in committed
    assert (
        MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE.value
        not in committed
    )
    assert not activity.get("to")


@pytest.mark.spec("EP-09-008")
def test_non_manager_owner_accept_asks_the_manager_to_activate(
    owner_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """An owner that is not the CASE_MANAGER sends its activation to it.

    The queued activity is Add(EmbargoEvent)[target=VulnerabilityCase], recorded as a
    pending ``activate_embargo_on_case`` assertion; the owner's replica
    writes no EM state and no consent until the manager's commit arrives.
    """
    owner, dl = owner_actor_and_dl
    manager = _persist_actor(dl, "Case Manager")
    case, proposal_id, embargo_id, owner_pid = _case_owned_by_non_manager(
        dl, owner.id_, manager.id_
    )

    result = _owner_accept(
        dl,
        AcceptEmbargoTriggerRequest(
            actor_id=owner.id_, case_id=case.id_, proposal_id=proposal_id
        ),
    )

    activity = activity_of(result)
    assert activity["object"]["id"] == embargo_id
    assert activity["target"] == case.id_
    updated = cast(VulnerabilityCase, dl.read(case.id_))
    assert updated.current_status.em.state == EM.PROPOSED
    assert updated.proposed_embargo_ids == [embargo_id]
    owner_participant = cast(as_CaseParticipant, dl.read(owner_pid))
    assert (
        owner_participant.consent_for(embargo_id)
        == EmbargoConsentState.INVITED
    )
    _assert_asked_case_manager(
        dl,
        actor_id=owner.id_,
        case_id=case.id_,
        manager_id=manager.id_,
        activity_type="Add",
        semantic_type=MessageSemantics.ACTIVATE_EMBARGO_ON_CASE.value,
    )


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


@pytest.mark.spec("MSM-07-003")
@pytest.mark.spec("MSM-07-011")
def test_non_owner_manager_accept_is_consent_and_moves_no_register_entry(
    owner_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A CASE_MANAGER that is not the owner accepts the Invite, nothing more.

    Its accept is Accept(Invite(EmbargoEvent)), committed as its consent;
    the proposal stays open and EM stays PROPOSED (ADR-0122).
    """
    manager, dl = owner_actor_and_dl
    owner = _persist_actor(dl, "Vendor Co")
    case, proposal_id, embargo_id, _ = _case_owned_by_non_manager(
        dl, owner.id_, manager.id_
    )

    result = _owner_accept(
        dl,
        AcceptEmbargoTriggerRequest(
            actor_id=manager.id_, case_id=case.id_, proposal_id=proposal_id
        ),
    )

    activity = activity_of(result)
    assert activity["type"] == "Accept"
    assert activity["object"]["id"] == proposal_id
    updated = cast(VulnerabilityCase, dl.read(case.id_))
    assert updated.current_status.em.state == EM.PROPOSED
    assert updated.proposed_embargo_ids == [embargo_id]
    manager_participant = cast(
        as_CaseParticipant,
        dl.read(updated.actor_participant_index[manager.id_]),
    )
    assert (
        manager_participant.consent_for(embargo_id)
        == EmbargoConsentState.AGREED
    )
    committed = committed_semantic_types(dl, case.id_)
    assert MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE.value in committed
    assert MessageSemantics.ACTIVATE_EMBARGO_ON_CASE.value not in committed


def _decline_owner_row(
    dl: SqliteDataLayer, case_id: str, owner_id: str, embargo_id: str
) -> str:
    """Set the owner's row for *embargo_id* to DECLINED; return its id."""
    case = cast(VulnerabilityCase, dl.read(case_id))
    participant_id = case.actor_participant_index[owner_id]
    participant = cast(as_CaseParticipant, dl.read(participant_id))
    participant.embargo_consents = [
        row.model_copy(update={"state": EmbargoConsentState.DECLINED})
        if row.embargo_id == embargo_id
        else row
        for row in participant.embargo_consents
    ]
    dl.save(participant)
    return participant_id


@pytest.mark.spec("MSM-07-037")
@pytest.mark.spec("CM-18-003")
def test_a_declined_owner_managers_accept_changes_its_answer_then_activates(
    owner_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A declined owner's first accept is its Accept; its next one activates.

    The CASE_MANAGER refuses an activation from a DECLINED row (MSM-07-037),
    so the trigger sends what the refusal asks for: the
    Accept(Invite(EmbargoEvent)), which moves the row to AGREED and leaves
    the proposal open.  The owner's next accept is the Add (ADR-0180).
    """
    owner, dl = owner_actor_and_dl
    case, proposal_id = _case_with_open_proposal(dl, owner.id_)
    embargo_id = case.proposed_embargo_ids[0]
    owner_pid = _decline_owner_row(dl, case.id_, owner.id_, embargo_id)
    request = AcceptEmbargoTriggerRequest(
        actor_id=owner.id_, case_id=case.id_, proposal_id=proposal_id
    )

    first = activity_of(_owner_accept(dl, request))

    assert first["type"] == "Accept"
    accepted = first["object"]
    assert (accepted["id"] if isinstance(accepted, dict) else accepted) == (
        proposal_id
    )
    after_accept = cast(VulnerabilityCase, dl.read(case.id_))
    assert after_accept.current_status.em.state == EM.PROPOSED
    assert after_accept.proposed_embargo_ids == [embargo_id]
    owner_participant = cast(as_CaseParticipant, dl.read(owner_pid))
    assert (
        owner_participant.consent_for(embargo_id) == EmbargoConsentState.AGREED
    )

    second = activity_of(_owner_accept(dl, request))

    assert second["type"] == "Add"
    activated = cast(VulnerabilityCase, dl.read(case.id_))
    assert activated.current_status.em.state == EM.ACTIVE
    assert activated.active_embargo_id == embargo_id


@pytest.mark.spec("MSM-07-037")
def test_a_declined_non_manager_owners_accept_asks_with_an_accept(
    owner_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A declined owner asks the CASE_MANAGER with an Accept, not an Add."""
    owner, dl = owner_actor_and_dl
    manager = _persist_actor(dl, "Case Manager")
    case, proposal_id, embargo_id, _owner_pid = _case_owned_by_non_manager(
        dl, owner.id_, manager.id_
    )
    _decline_owner_row(dl, case.id_, owner.id_, embargo_id)

    _owner_accept(
        dl,
        AcceptEmbargoTriggerRequest(
            actor_id=owner.id_, case_id=case.id_, proposal_id=proposal_id
        ),
    )

    _assert_asked_case_manager(
        dl,
        actor_id=owner.id_,
        case_id=case.id_,
        manager_id=manager.id_,
        activity_type="Accept",
        semantic_type=MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE.value,
    )
