#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""A received ``Leave(EmbargoEvent)``, and the Reject that never withdraws.

The CASE_MANAGER applies a signatory's withdrawal from the embargo in force
(MSM-07-010): the sender's ``AGREED`` row for the active embargo and every
open proposal's row it had agreed to become ``DECLINED``, the withdrawal is
committed to the ledger, and no register entry moves.  Every refusal is
decided before the commit, so nothing is ledgered for it (CLP-10-009,
SYNC-12-001).  A ``Reject(Invite(EmbargoEvent))`` of the active embargo from
an ``AGREED`` row is refused the same way (MSM-07-004).
"""

from typing import Any, cast

import pytest

from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
    seed_case_owner_participant,
    seed_case_participant,
)
from test.support.embargo_register import activate, propose
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState as ECS,
)
from vultron.core.use_cases.received.embargo import (
    RejectInviteToEmbargoOnCaseReceivedUseCase,
    WithdrawFromEmbargoOnCaseReceivedUseCase,
)
from vultron.wire.as2.factories import (
    em_propose_embargo_activity,
    em_reject_embargo_activity,
    withdraw_from_embargo_activity,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

_CASE_ID = "https://example.org/cases/withdrawal"
_MANAGER = "https://example.org/users/coord"
_OWNER = "https://example.org/users/vendor"
_FINDER = "https://example.org/users/finder"
_ACTIVE = f"{_CASE_ID}/embargo_events/active"
_AGREED_REVISION = f"{_CASE_ID}/embargo_events/agreed-revision"
_INVITED_REVISION = f"{_CASE_ID}/embargo_events/invited-revision"
_WITHDRAW = MessageSemantics.WITHDRAW_FROM_EMBARGO_ON_CASE.value


def _embargo(embargo_id: str, days: int) -> as_EmbargoEvent:
    return as_EmbargoEvent(
        id_=embargo_id, context=_CASE_ID, end_time=days_from_now_utc(days)
    )


def _set_rows(
    dl: SqliteDataLayer, participant: CaseParticipant, rows: dict[str, ECS]
) -> None:
    """Seed the participant's starting rows directly (test setup only)."""
    kept = [
        r for r in participant.embargo_consents if r.embargo_id not in rows
    ]
    participant.embargo_consents = [
        *kept,
        *(EmbargoConsent(embargo_id=e, state=s) for e, s in rows.items()),
    ]
    dl.save(participant)


def _store(
    *, receiver: str = _MANAGER, in_force: bool = True
) -> SqliteDataLayer:
    """*receiver*'s store: the vendor owns the case, the coordinator manages it.

    With *in_force* the embargo ``_ACTIVE`` is in force and two revisions are
    open; the finder is ``AGREED`` on the embargo in force and on one
    revision, and only ``INVITED`` to the other.  Without it the case has one
    open proposal, which the finder agreed to.
    """
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=receiver)
    case = VulnerabilityCase(
        id_=_CASE_ID, name="Withdrawal", attributed_to=_OWNER
    )
    for embargo_id, days in (
        (_ACTIVE, 60),
        (_AGREED_REVISION, 30),
        (_INVITED_REVISION, 45),
    ):
        dl.create(_embargo(embargo_id, days))
    if in_force:
        activate(case, _ACTIVE)
        propose(case, _AGREED_REVISION, _INVITED_REVISION)
    else:
        propose(case, _AGREED_REVISION)
    seed_case_manager_participant(dl, case, _MANAGER)
    owner = seed_case_owner_participant(dl, case, _OWNER)
    finder = seed_case_participant(dl, case, _FINDER)
    dl.create(case)
    if in_force:
        _set_rows(dl, owner, {_ACTIVE: ECS.AGREED})
        _set_rows(
            dl,
            finder,
            {
                _ACTIVE: ECS.AGREED,
                _AGREED_REVISION: ECS.AGREED,
                _INVITED_REVISION: ECS.INVITED,
            },
        )
    else:
        _set_rows(dl, finder, {_AGREED_REVISION: ECS.AGREED})
    return dl


def _leave(
    dl: SqliteDataLayer,
    *,
    sender: str = _FINDER,
    embargo_id: str = _ACTIVE,
    to: str = _MANAGER,
):
    return withdraw_from_embargo_activity(
        cast(as_EmbargoEvent, dl.read(embargo_id)),
        context=_CASE_ID,
        actor=sender,
        to=[to],
    )


def _run(dl: SqliteDataLayer, event: Any) -> HandlerResult:
    return WithdrawFromEmbargoOnCaseReceivedUseCase(
        dl,
        event,
        sync_port=SyncActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()


def _withdraw(
    dl: SqliteDataLayer,
    make_payload: Any,
    *,
    sender: str = _FINDER,
    embargo_id: str = _ACTIVE,
    receiver: str = _MANAGER,
    activity: Any = None,
):
    if activity is None:
        activity = _leave(
            dl, sender=sender, embargo_id=embargo_id, to=receiver
        )
    event = make_payload(activity, receiving_actor_id=receiver)
    assert (
        event.semantic_type is MessageSemantics.WITHDRAW_FROM_EMBARGO_ON_CASE
    )
    return _run(dl, event)


def _case(dl: SqliteDataLayer) -> VulnerabilityCase:
    return cast(VulnerabilityCase, dl.read(_CASE_ID))


def _rows(dl: SqliteDataLayer, actor_id: str) -> dict[str, str]:
    participant = dl.read(_case(dl).actor_participant_index[actor_id])
    assert isinstance(participant, CaseParticipant)
    return {r.embargo_id: r.state.value for r in participant.embargo_consents}


def _register(dl: SqliteDataLayer) -> list[tuple[str, str]]:
    return [(e.embargo_id, e.status.value) for e in _case(dl).embargo_register]


def _announced_to(dl: SqliteDataLayer) -> set[str]:
    """Every recipient of an ``Announce(CaseLedgerEntry)`` queued in *dl*."""
    recipients: set[str] = set()
    for activity_id in dl.outbox_list():
        activity = dl.read(activity_id)
        if getattr(activity, "type_", None) != "Announce":
            continue
        for recipient in getattr(activity, "to", None) or []:
            recipients.add(str(getattr(recipient, "id_", recipient)))
    return recipients


def _ledger(dl: SqliteDataLayer) -> list[str]:
    return [
        str(entry.event_type)
        for entry in dl.list_objects("CaseLedgerEntry")
        if isinstance(entry, CaseLedgerEntry)
    ]


@pytest.mark.spec("MSM-07-010")
@pytest.mark.spec("VP-13-017")
@pytest.mark.spec("VP-13-008")
def test_the_case_manager_applies_and_commits_a_withdrawal(make_payload):
    dl = _store()
    register_before = _register(dl)

    result = _withdraw(dl, make_payload)

    assert result.disposition is HandlerDisposition.APPLIED, result.reason
    assert _rows(dl, _FINDER) == {
        _ACTIVE: "DECLINED",
        _AGREED_REVISION: "DECLINED",
        _INVITED_REVISION: "INVITED",
    }
    # No register entry moves: the embargo stays in force for the others.
    assert _register(dl) == register_before
    assert _case(dl).active_embargo_id == _ACTIVE
    assert _rows(dl, _OWNER)[_ACTIVE] == "AGREED"
    assert _ledger(dl) == [_WITHDRAW]
    # The fan-out runs at the commit, before the effect makes the withdrawer
    # inactive, so its own replica is sent the entry it replays (EP-09-007).
    assert _FINDER in _announced_to(dl)


@pytest.mark.spec("MSM-07-010")
@pytest.mark.spec("CLP-10-009")
def test_a_leave_of_an_embargo_not_in_force_is_refused_uncommitted(
    make_payload,
):
    dl = _store()

    result = _withdraw(dl, make_payload, embargo_id=_AGREED_REVISION)

    assert result.disposition is HandlerDisposition.REFUSED
    assert "not the embargo in force" in (result.reason or "")
    assert _rows(dl, _FINDER)[_AGREED_REVISION] == "AGREED"
    assert _ledger(dl) == []


@pytest.mark.spec("MSM-07-010")
@pytest.mark.spec("CLP-10-009")
def test_a_leave_with_no_embargo_in_force_is_refused_uncommitted(
    make_payload,
):
    dl = _store(in_force=False)

    result = _withdraw(dl, make_payload, embargo_id=_AGREED_REVISION)

    assert result.disposition is HandlerDisposition.REFUSED
    assert "No embargo is in force" in (result.reason or "")
    assert _rows(dl, _FINDER)[_AGREED_REVISION] == "AGREED"
    assert _ledger(dl) == []


@pytest.mark.spec("MSM-07-010")
@pytest.mark.spec("CLP-10-009")
@pytest.mark.parametrize("row", [ECS.INVITED, ECS.TIMED_OUT, ECS.DECLINED])
def test_a_leave_from_a_row_that_is_not_agreed_is_refused_uncommitted(
    make_payload, row
):
    """A participant that is not a signatory has nothing to withdraw from."""
    dl = _store()
    finder = dl.read(_case(dl).actor_participant_index[_FINDER])
    assert isinstance(finder, CaseParticipant)
    _set_rows(dl, finder, {_ACTIVE: row})

    result = _withdraw(dl, make_payload)

    assert result.disposition is HandlerDisposition.REFUSED
    assert f"is {row.value}" in (result.reason or "")
    assert "not AGREED" in (result.reason or "")
    assert _rows(dl, _FINDER)[_AGREED_REVISION] == "AGREED"
    assert _ledger(dl) == []


@pytest.mark.spec("MSM-07-010")
@pytest.mark.spec("CM-02-005")
@pytest.mark.spec("CLP-10-009")
def test_a_leave_from_the_case_owner_is_refused_uncommitted(make_payload):
    """The case owner ends an embargo by terminating it (CM-02-005)."""
    dl = _store()

    result = _withdraw(dl, make_payload, sender=_OWNER)

    assert result.disposition is HandlerDisposition.REFUSED
    assert "case owner" in (result.reason or "")
    assert _rows(dl, _OWNER)[_ACTIVE] == "AGREED"
    assert _ledger(dl) == []


@pytest.mark.spec("MSM-07-010")
@pytest.mark.spec("BT-17-001")
@pytest.mark.spec("HP-01-005")
def test_a_replica_does_not_apply_a_withdrawal(make_payload):
    """Only the CASE_MANAGER records it; a replica learns it from the ledger."""
    dl = _store(receiver=_OWNER)

    result = _withdraw(dl, make_payload, receiver=_OWNER)

    assert result.disposition is HandlerDisposition.REFUSED
    assert result.reason
    assert _rows(dl, _FINDER)[_ACTIVE] == "AGREED"


def _reject(
    dl: SqliteDataLayer, make_payload: Any, embargo_id: str
) -> HandlerResult:
    """The finder rejects its relayed Invite to *embargo_id*."""
    invite = em_propose_embargo_activity(
        cast(as_EmbargoEvent, dl.read(embargo_id)),
        context=_CASE_ID,
        actor=_MANAGER,
        to=[_FINDER],
    )
    dl.create(invite)
    reject = em_reject_embargo_activity(
        invite, context=_CASE_ID, actor=_FINDER, to=[_MANAGER]
    )
    event = make_payload(reject, receiving_actor_id=_MANAGER)
    return RejectInviteToEmbargoOnCaseReceivedUseCase(
        dl,
        event,
        sync_port=SyncActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()


@pytest.mark.spec("MSM-07-004")
@pytest.mark.spec("CLP-10-009")
def test_a_reject_of_the_embargo_in_force_from_an_agreed_row_is_refused(
    make_payload,
):
    """A Reject never withdraws: withdrawal is ``Leave(EmbargoEvent)``."""
    dl = _store()

    result = _reject(dl, make_payload, _ACTIVE)

    assert result.disposition is HandlerDisposition.REFUSED
    assert "withdrawal is Leave(EmbargoEvent)" in (result.reason or "")
    assert _rows(dl, _FINDER) == {
        _ACTIVE: "AGREED",
        _AGREED_REVISION: "AGREED",
        _INVITED_REVISION: "INVITED",
    }
    assert _ledger(dl) == []


@pytest.mark.spec("MSM-07-004")
def test_a_signatorys_reject_of_a_revision_leaves_it_bound(make_payload):
    """Refusing a revision declines that row only; the active row stays."""
    dl = _store()

    result = _reject(dl, make_payload, _INVITED_REVISION)

    assert result.disposition is HandlerDisposition.APPLIED, result.reason
    assert _rows(dl, _FINDER) == {
        _ACTIVE: "AGREED",
        _AGREED_REVISION: "AGREED",
        _INVITED_REVISION: "DECLINED",
    }
    assert _ledger(dl) == [MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE]


@pytest.mark.spec("HP-01-003")
@pytest.mark.spec("MSM-07-010")
def test_a_redelivered_leave_is_skipped_and_changes_nothing(make_payload):
    """The same Leave again is a duplicate, not a refusal (HP-01-003)."""
    dl = _store()
    leave = _leave(dl)
    assert _withdraw(dl, make_payload, activity=leave).disposition is (
        HandlerDisposition.APPLIED
    )
    rows, ledger = _rows(dl, _FINDER), _ledger(dl)

    result = _withdraw(dl, make_payload, activity=leave)

    assert result.disposition is HandlerDisposition.SKIPPED, result.reason
    assert "redelivery" in (result.reason or "")
    assert _rows(dl, _FINDER) == rows
    assert _ledger(dl) == ledger


@pytest.mark.spec("MSM-07-010")
def test_a_new_leave_after_a_withdrawal_is_still_refused(make_payload):
    """Only the same activity is a redelivery; a new Leave meets the guard."""
    dl = _store()
    assert _withdraw(dl, make_payload).disposition is (
        HandlerDisposition.APPLIED
    )
    second = _leave(dl).model_copy(update={"id_": f"{_CASE_ID}/leaves/again"})

    result = _withdraw(dl, make_payload, activity=second)

    assert result.disposition is HandlerDisposition.REFUSED
    assert "not AGREED" in (result.reason or "")
    assert _ledger(dl) == [_WITHDRAW]


@pytest.mark.spec("CM-10-004")
@pytest.mark.spec("HP-01-006")
def test_a_leave_from_an_actor_not_in_the_case_is_refused_uncommitted(
    make_payload,
):
    dl = _store()

    result = _withdraw(
        dl, make_payload, sender="https://example.org/users/stranger"
    )

    assert result.disposition is HandlerDisposition.REFUSED
    assert result.reason
    assert _rows(dl, _FINDER)[_ACTIVE] == "AGREED"
    assert _ledger(dl) == []


@pytest.mark.spec("HP-01-005")
def test_an_unaddressed_copy_of_a_leave_is_refused_uncommitted(make_payload):
    """A store the Leave neither came from nor was sent to runs no tree."""
    dl = _store()
    leave = _leave(dl, to=_OWNER)
    event = make_payload(leave, receiving_actor_id=_MANAGER)

    result = _run(dl, event)

    assert result.disposition is HandlerDisposition.REFUSED
    assert "unaddressed copy" in (result.reason or "")
    assert _rows(dl, _FINDER)[_ACTIVE] == "AGREED"
    assert _ledger(dl) == []


@pytest.mark.spec("MSM-07-010")
def test_a_leave_naming_no_case_is_refused_uncommitted(make_payload):
    dl = _store()
    event = make_payload(_leave(dl), receiving_actor_id=_MANAGER)

    result = _run(dl, event.model_copy(update={"context": None}))

    assert result.disposition is HandlerDisposition.REFUSED
    assert "missing its embargo id or case id" in (result.reason or "")
    assert _ledger(dl) == []


@pytest.mark.spec("MSM-07-010")
def test_a_leave_from_a_record_with_no_row_is_refused_uncommitted(
    make_payload,
):
    """A missing row is a defect in the store; the guard refuses with it."""
    dl = _store()
    finder = dl.read(_case(dl).actor_participant_index[_FINDER])
    assert isinstance(finder, CaseParticipant)
    finder.embargo_consents = [
        r for r in finder.embargo_consents if r.embargo_id != _ACTIVE
    ]
    dl.save(finder)

    result = _withdraw(dl, make_payload)

    assert result.disposition is HandlerDisposition.REFUSED
    assert "EmbargoConsent" in (result.reason or "")
    assert _ledger(dl) == []
