"""Tests for SvcRejectEmbargoUseCase."""

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
from vultron.core.use_cases.triggers.embargo import SvcRejectEmbargoUseCase
from vultron.core.use_cases.triggers.requests import (
    RejectEmbargoTriggerRequest,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant

from .conftest import (
    _assert_asked_case_manager,
    _build_active_embargo_case,
    _case_owned_by_non_manager,
    _case_with_open_proposal,
    _open_revision,
    _persist_actor,
)


@pytest.mark.spec("EP-09-008")
def test_non_manager_reject_embargo_asks_the_case_manager(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A participant's reject asks the CASE_MANAGER and unwinds nothing."""
    finder, finder_dl = finder_actor_and_dl
    owner = _persist_actor(finder_dl, "Vendor Co")
    case, _, participant_id = _build_active_embargo_case(
        finder_dl, owner.id_, finder.id_
    )
    proposal, revision_id = _open_revision(
        finder_dl, case.id_, owner.id_, participant_id
    )

    request = RejectEmbargoTriggerRequest(
        actor_id=finder.id_,
        case_id=case.id_,
        proposal_id=proposal.id_,
    )

    result = SvcRejectEmbargoUseCase(
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
    # Not the CASE_MANAGER: the refusal is asked for, not recorded here; the
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
        activity_type="Reject",
        event_type=MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE.value,
    )


@pytest.mark.spec("EP-09-008")
@pytest.mark.spec("EP-09-007")
def test_manager_reject_embargo_commits_the_decision(
    owner_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """The owner-manager's reject is Reject(EmbargoEvent, target=Case).

    It rejects the proposal and is committed as the owner's decision
    (ADR-0122, #4085), never as a consent answer to the Invite.  Every
    replica learns it from the committed entry, so the ``Reject`` itself is
    addressed to nobody (CLP-10-001).
    """
    owner, dl = owner_actor_and_dl
    case, proposal_id = _case_with_open_proposal(dl, owner.id_)
    embargo_id = case.proposed_embargo_ids[0]

    result = SvcRejectEmbargoUseCase(
        dl,
        RejectEmbargoTriggerRequest(
            actor_id=owner.id_, case_id=case.id_, proposal_id=proposal_id
        ),
        trigger_activity=TriggerActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
        sync_port=SyncActivityAdapter(dl),
    ).execute()

    activity = activity_of(result)
    assert activity["type"] == "Reject"
    assert activity["object"]["id"] == embargo_id
    assert activity["target"] == case.id_
    updated = cast(VulnerabilityCase, dl.read(case.id_))
    assert updated.current_status.em.state == EM.NONE
    assert updated.proposed_embargo_ids == []
    committed = committed_event_types(dl, case.id_)
    assert MessageSemantics.REJECT_EMBARGO_PROPOSAL_ON_CASE.value in committed
    assert (
        MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE.value
        not in committed
    )
    assert not activity.get("to")


@pytest.mark.spec("EP-09-008")
def test_non_manager_owner_reject_asks_the_manager_to_reject(
    owner_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """An owner that is not the CASE_MANAGER sends its rejection to it.

    The queued activity is Reject(EmbargoEvent, target=Case), recorded as a
    pending ``reject_embargo_proposal_on_case`` assertion; nothing moves on
    the owner's replica, its own consent row included (ADR-0122).
    """
    owner, dl = owner_actor_and_dl
    manager = _persist_actor(dl, "Case Manager")
    case, proposal_id, embargo_id, owner_pid = _case_owned_by_non_manager(
        dl, owner.id_, manager.id_
    )

    result = SvcRejectEmbargoUseCase(
        dl,
        RejectEmbargoTriggerRequest(
            actor_id=owner.id_, case_id=case.id_, proposal_id=proposal_id
        ),
        trigger_activity=TriggerActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
        sync_port=SyncActivityAdapter(dl),
    ).execute()

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
        activity_type="Reject",
        event_type=MessageSemantics.REJECT_EMBARGO_PROPOSAL_ON_CASE.value,
    )


@pytest.mark.spec("MSM-07-004")
def test_non_owner_manager_reject_is_consent_and_moves_no_register_entry(
    owner_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A CASE_MANAGER that is not the owner declines the Invite, nothing more.

    Its reject is Reject(Invite(EmbargoEvent)), committed as its consent;
    the proposal stays open and EM stays PROPOSED (ADR-0122).
    """
    manager, dl = owner_actor_and_dl
    owner = _persist_actor(dl, "Vendor Co")
    case, proposal_id, embargo_id, _ = _case_owned_by_non_manager(
        dl, owner.id_, manager.id_
    )

    result = SvcRejectEmbargoUseCase(
        dl,
        RejectEmbargoTriggerRequest(
            actor_id=manager.id_, case_id=case.id_, proposal_id=proposal_id
        ),
        trigger_activity=TriggerActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
        sync_port=SyncActivityAdapter(dl),
    ).execute()

    activity = activity_of(result)
    assert activity["type"] == "Reject"
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
        == EmbargoConsentState.DECLINED
    )
    committed = committed_event_types(dl, case.id_)
    assert MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE.value in committed
    assert (
        MessageSemantics.REJECT_EMBARGO_PROPOSAL_ON_CASE.value not in committed
    )
