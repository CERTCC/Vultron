"""Tests for the withdraw-embargo trigger (EP-09-013).

A signatory leaves the embargo in force by sending ``Leave(EmbargoEvent)`` to
the CASE_MANAGER (MSM-07-010).  The trigger resolves the embargo from the
case's active embargo and needs no Invite; the reject trigger never
withdraws (MSM-07-004).
"""

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
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.models.use_case_result import ActivityResult
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState as ECS,
)
from vultron.core.use_cases.triggers import embargo as embargo_triggers
from vultron.core.use_cases.triggers.embargo import (
    SvcRejectEmbargoUseCase,
    SvcWithdrawEmbargoUseCase,
)
from vultron.core.use_cases.triggers.requests import (
    RejectEmbargoTriggerRequest,
    WithdrawEmbargoTriggerRequest,
)
from vultron.enums.roles import CVDRole
from vultron.errors import VultronInvalidStateTransitionError
from vultron.wire.as2.vocab.base.objects.actors import as_Service

from .conftest import (
    _add_participant,
    _assert_asked_case_manager,
    _build_active_embargo_case,
    _case_with_open_proposal,
    _open_revision,
    _persist_actor,
)

_WITHDRAW = MessageSemantics.WITHDRAW_FROM_EMBARGO_ON_CASE.value


def _withdraw(dl: SqliteDataLayer, actor_id: str, case_id: str):
    return SvcWithdrawEmbargoUseCase(
        dl,
        WithdrawEmbargoTriggerRequest(actor_id=actor_id, case_id=case_id),
        trigger_activity=TriggerActivityAdapter(dl),
        sync_port=SyncActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()


def _set_row(
    dl: SqliteDataLayer, participant_id: str, embargo_id: str, state: ECS
) -> None:
    """Seed the participant's starting row directly (test setup only)."""
    participant = cast(CaseParticipant, dl.read(participant_id))
    participant.embargo_consents = [
        *(
            r
            for r in participant.embargo_consents
            if r.embargo_id != embargo_id
        ),
        EmbargoConsent(embargo_id=embargo_id, state=state),
    ]
    dl.save(participant)


def _row(dl: SqliteDataLayer, participant_id: str, embargo_id: str) -> ECS:
    return cast(CaseParticipant, dl.read(participant_id)).consent_for(
        embargo_id
    )


def _seeded_signatory(
    dl: SqliteDataLayer, finder_id: str
) -> tuple[VulnerabilityCase, str, str, str]:
    """The finder is a signatory to the embargo in force with no Invite.

    As a reporter is when the case is created (CM-14-005): its row is
    ``AGREED`` and it holds no received ``Invite(EmbargoEvent)``.  Returns
    the case, the manager's id, the finder's participant id and the embargo.
    """
    owner = _persist_actor(dl, "Vendor Co")
    case, _, participant_id = _build_active_embargo_case(
        dl, owner.id_, finder_id
    )
    embargo_id = case.active_embargo_id
    assert embargo_id is not None
    _set_row(dl, participant_id, embargo_id, ECS.AGREED)
    # It received no Invite(EmbargoEvent) to answer or name (EP-09-013).
    assert not [
        r
        for r in dl.list_objects("ReceivedActivityRecord")
        if isinstance(r, ReceivedActivityRecord)
    ]
    return case, owner.id_, participant_id, embargo_id


def _move_case_manager_role(
    dl: SqliteDataLayer,
    case_id: str,
    from_actor_id: str,
    to_participant_id: str,
) -> None:
    """Make *to_participant_id* the CASE_MANAGER in place of *from_actor_id*."""
    case = cast(VulnerabilityCase, dl.read(case_id))
    old = cast(
        CaseParticipant, dl.read(case.actor_participant_index[from_actor_id])
    )
    old.case_roles = [
        r for r in old.case_roles if r is not CVDRole.CASE_MANAGER
    ]
    dl.save(old)
    new = cast(CaseParticipant, dl.read(to_participant_id))
    new.case_roles = [*new.case_roles, CVDRole.CASE_MANAGER]
    dl.save(new)


@pytest.mark.spec("EP-09-013")
def test_a_withdraw_embargo_trigger_exists() -> None:
    """A signatory has a trigger, separate from reject, that withdraws it."""
    assert hasattr(embargo_triggers, "SvcWithdrawEmbargoUseCase")


@pytest.mark.spec("EP-09-013")
@pytest.mark.spec("MSM-07-010")
@pytest.mark.spec("PCR-08-001")
def test_a_seeded_signatory_withdraws_with_no_invite(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """The Leave names the embargo in force and goes to the CASE_MANAGER."""
    finder, dl = finder_actor_and_dl
    case, manager_id, participant_id, embargo_id = _seeded_signatory(
        dl, finder.id_
    )

    result = _withdraw(dl, finder.id_, case.id_)

    activity = activity_of(result)
    assert activity["type"] == "Leave"
    assert activity["object"]["id"] == embargo_id
    assert activity["object"]["type"] == "EmbargoEvent"
    assert activity["context"] == case.id_
    _assert_asked_case_manager(
        dl,
        actor_id=finder.id_,
        case_id=case.id_,
        manager_id=manager_id,
        activity_type="Leave",
        event_type=_WITHDRAW,
    )
    # Not the CASE_MANAGER: the replica's row moves when the manager's commit
    # is announced, not here (EP-09-008).
    assert _row(dl, participant_id, embargo_id) is ECS.AGREED


@pytest.mark.spec("EP-09-013")
@pytest.mark.spec("SYNC-11-002")
def test_a_repeat_withdrawal_inside_the_window_is_suppressed(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    finder, dl = finder_actor_and_dl
    case, _manager_id, _pid, _embargo_id = _seeded_signatory(dl, finder.id_)
    _withdraw(dl, finder.id_, case.id_)
    queued = list(dl.outbox_list())

    repeat = _withdraw(dl, finder.id_, case.id_)

    assert isinstance(repeat, ActivityResult)
    assert repeat.activity is None
    assert list(dl.outbox_list()) == queued


@pytest.mark.spec("EP-09-013")
@pytest.mark.spec("MSM-07-010")
def test_a_case_manager_signatory_records_and_commits_its_own_withdrawal(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """A CASE_MANAGER that is not the case owner withdraws in its own store."""
    finder, dl = finder_actor_and_dl
    case, manager_id, participant_id, embargo_id = _seeded_signatory(
        dl, finder.id_
    )
    _move_case_manager_role(dl, case.id_, manager_id, participant_id)

    result = _withdraw(dl, finder.id_, case.id_)

    assert activity_of(result)["type"] == "Leave"
    assert _row(dl, participant_id, embargo_id) is ECS.DECLINED
    assert _WITHDRAW in committed_event_types(dl, case.id_)
    after = cast(VulnerabilityCase, dl.read(case.id_))
    assert after.active_embargo_id == embargo_id


@pytest.mark.spec("EP-09-013")
def test_withdrawal_with_no_embargo_in_force_is_refused(
    owner_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    owner, dl = owner_actor_and_dl
    finder = _persist_actor(dl, "Finder Co")
    case, _proposal_id = _case_with_open_proposal(dl, owner.id_)
    _add_participant(dl, case.id_, finder.id_)

    with pytest.raises(
        VultronInvalidStateTransitionError, match="No embargo is in force"
    ):
        _withdraw(dl, finder.id_, case.id_)
    assert dl.outbox_list() == []


@pytest.mark.spec("EP-09-013")
@pytest.mark.parametrize("row", [ECS.INVITED, ECS.TIMED_OUT, ECS.DECLINED])
def test_withdrawal_from_a_row_that_is_not_agreed_is_refused(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer], row: ECS
) -> None:
    finder, dl = finder_actor_and_dl
    case, _manager_id, participant_id, embargo_id = _seeded_signatory(
        dl, finder.id_
    )
    _set_row(dl, participant_id, embargo_id, row)

    with pytest.raises(VultronInvalidStateTransitionError, match="not AGREED"):
        _withdraw(dl, finder.id_, case.id_)
    assert dl.outbox_list() == []


@pytest.mark.spec("EP-09-013")
@pytest.mark.spec("CM-02-005")
def test_the_case_owner_cannot_withdraw(
    owner_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """The owner ends an embargo with terminate-embargo instead."""
    owner, dl = owner_actor_and_dl
    finder = _persist_actor(dl, "Finder Co")
    case, _, _ = _build_active_embargo_case(dl, owner.id_, finder.id_)

    with pytest.raises(VultronInvalidStateTransitionError, match="case owner"):
        _withdraw(dl, owner.id_, case.id_)
    assert dl.outbox_list() == []


def _reject_no_name(dl: SqliteDataLayer, actor_id: str, case_id: str):
    return SvcRejectEmbargoUseCase(
        dl,
        RejectEmbargoTriggerRequest(actor_id=actor_id, case_id=case_id),
        trigger_activity=TriggerActivityAdapter(dl),
        sync_port=SyncActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()


@pytest.mark.spec("EP-09-013")
@pytest.mark.spec("MSM-07-004")
@pytest.mark.spec("EP-08-002")
def test_a_no_name_reject_refuses_the_revision_and_never_withdraws(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """With a revision open, a no-name reject names the revision, not the
    embargo in force, and the signatory stays bound by it."""
    finder, dl = finder_actor_and_dl
    case, manager_id, participant_id, embargo_id = _seeded_signatory(
        dl, finder.id_
    )
    proposal, revision_id = _open_revision(
        dl, case.id_, manager_id, participant_id
    )

    result = _reject_no_name(dl, finder.id_, case.id_)

    activity = activity_of(result)
    assert activity["type"] == "Reject"
    assert activity["object"]["id"] == proposal.id_
    assert activity["object"]["object"]["id"] == revision_id
    assert _row(dl, participant_id, embargo_id) is ECS.AGREED


@pytest.mark.spec("EP-09-013")
@pytest.mark.spec("MSM-07-004")
def test_a_case_manager_signatorys_no_name_reject_keeps_it_bound(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """As the CASE_MANAGER the reject writes: the revision's row only."""
    finder, dl = finder_actor_and_dl
    case, manager_id, participant_id, embargo_id = _seeded_signatory(
        dl, finder.id_
    )
    _proposal, revision_id = _open_revision(
        dl, case.id_, manager_id, participant_id
    )
    _move_case_manager_role(dl, case.id_, manager_id, participant_id)

    _reject_no_name(dl, finder.id_, case.id_)

    assert _row(dl, participant_id, revision_id) is ECS.DECLINED
    assert _row(dl, participant_id, embargo_id) is ECS.AGREED
