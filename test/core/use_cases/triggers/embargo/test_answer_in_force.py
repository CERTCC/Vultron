#!/usr/bin/env python

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

"""Answering the embargo in force by Invite id (EP-09-012).

Activation takes a proposal out of the open-proposal record (EP-08-003), so
a participant that never answered the relayed ``Invite(EmbargoEvent)`` — or
let its deadline pass — names that Invite, and the trigger resolves it from
the participant's own received copy.  No test here seeds the embargo in force
into ``pending_embargo_proposal_index``: the fixture asserts the record is
empty.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

import pytest

from test.support.received import archive_received, hold_deferred
from test.support.trigger_results import activity_of
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.use_case_result import ActivityResult
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.use_cases.triggers.embargo import (
    SvcAcceptEmbargoUseCase,
    SvcRejectEmbargoUseCase,
)
from vultron.core.use_cases.triggers.requests import (
    AcceptEmbargoTriggerRequest,
    RejectEmbargoTriggerRequest,
)
from vultron.enums.roles import CVDRole
from vultron.errors import VultronNotFoundError
from vultron.wire.as2.factories import em_propose_embargo_activity
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

from .conftest import (
    _assert_asked_case_manager,
    _build_active_embargo_case,
    _persist_actor,
)

_Answer = Callable[[SqliteDataLayer, str, str, str | None], ActivityResult]


def _answer_with(
    use_case: type[SvcAcceptEmbargoUseCase] | type[SvcRejectEmbargoUseCase],
    request: type[AcceptEmbargoTriggerRequest]
    | type[RejectEmbargoTriggerRequest],
) -> _Answer:
    """Return a caller that runs *use_case* for one actor, case and Invite."""

    def answer(
        dl: SqliteDataLayer,
        actor_id: str,
        case_id: str,
        invite_id: str | None,
    ) -> ActivityResult:
        return use_case(
            dl,
            request(actor_id=actor_id, case_id=case_id, proposal_id=invite_id),
            trigger_activity=TriggerActivityAdapter(dl),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

    return answer


_accept = _answer_with(SvcAcceptEmbargoUseCase, AcceptEmbargoTriggerRequest)
_reject = _answer_with(SvcRejectEmbargoUseCase, RejectEmbargoTriggerRequest)

_ANSWERS = [
    pytest.param(
        _accept,
        "Accept",
        MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE,
        id="accept",
    ),
    pytest.param(
        _reject,
        "Reject",
        MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE,
        id="reject",
    ),
]

_ANSWER_ONLY = [pytest.param(p.values[0], id=p.id) for p in _ANSWERS]


@dataclass
class _InForce:
    """A finder replica whose case has an embargo in force and no proposal."""

    dl: SqliteDataLayer
    finder_id: str
    manager_id: str
    case: VulnerabilityCase
    participant_id: str
    invite_id: str


def _store_received_invite(
    dl: SqliteDataLayer,
    embargo: as_EmbargoEvent,
    *,
    case_id: str,
    manager_id: str,
    invitee_id: str,
    to: list[str] | None = None,
    deferred: bool = False,
) -> str:
    """Store a relayed ``Invite(EmbargoEvent)`` as the invitee received it.

    Intake archives its body as a ``ReceivedActivityRecord``, and nothing holds it
    under the id its sender chose (DL-06-006).  With *deferred*, it is held
    instead as the inbox holds an Invite it defers until the case is known
    (``DeferredInboxActivity``), with no archive yet.  *to* overrides the
    single-invitee addressing.
    """
    invite = em_propose_embargo_activity(
        embargo,
        context=case_id,
        actor=manager_id,
        to=to if to is not None else [invitee_id],
    )
    if deferred:
        hold_deferred(dl, invite)
    else:
        archive_received(dl, invite)
    return invite.id_


def _set_row(
    dl: SqliteDataLayer,
    participant_id: str,
    embargo_id: str,
    state: EmbargoConsentState | None,
) -> None:
    """Set (or, with ``None``, drop) the participant's row for *embargo_id*.

    Seeds a starting state directly, as the conftest builders do: the state
    under test is the trigger's input, not a transition it makes.
    """
    participant = cast(CaseParticipant, dl.read(participant_id))
    rows = [
        r for r in participant.embargo_consents if r.embargo_id != embargo_id
    ]
    if state is not None:
        rows.append(EmbargoConsent(embargo_id=embargo_id, state=state))
    participant.embargo_consents = rows
    dl.save(participant)


@pytest.fixture
def in_force(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> _InForce:
    finder, dl = finder_actor_and_dl
    manager = _persist_actor(dl, "Vendor Co")
    case, _, participant_id = _build_active_embargo_case(
        dl, manager.id_, finder.id_
    )
    assert case.active_embargo_id is not None
    embargo = cast(as_EmbargoEvent, dl.read(case.active_embargo_id))
    invite_id = _store_received_invite(
        dl,
        embargo,
        case_id=case.id_,
        manager_id=manager.id_,
        invitee_id=finder.id_,
    )
    # The embargo in force has left the open-proposal record (EP-08-003).
    stored = cast(VulnerabilityCase, dl.read(case.id_))
    assert stored.pending_embargo_proposal_index == {}
    assert stored.proposed_embargo_ids == []
    return _InForce(
        dl=dl,
        finder_id=finder.id_,
        manager_id=manager.id_,
        case=stored,
        participant_id=participant_id,
        invite_id=invite_id,
    )


@pytest.mark.spec("EP-09-012", "MSM-07-003", "EMB-17-002")
@pytest.mark.parametrize(
    "row",
    [EmbargoConsentState.INVITED, EmbargoConsentState.TIMED_OUT],
    ids=["invited", "timed-out"],
)
@pytest.mark.parametrize(("answer", "verb", "semantics"), _ANSWERS)
def test_answers_the_embargo_in_force_by_invite_id(
    in_force: _InForce,
    answer: _Answer,
    verb: str,
    semantics: MessageSemantics,
    row: EmbargoConsentState,
) -> None:
    """An ``INVITED`` or ``TIMED_OUT`` row answers the embargo in force.

    The wire form is the one an answer to a proposal takes:
    ``Accept``/``Reject`` of the named Invite, asked of the CASE_MANAGER.
    """
    embargo_id = in_force.case.active_embargo_id
    assert embargo_id is not None
    _set_row(in_force.dl, in_force.participant_id, embargo_id, row)

    result = answer(
        in_force.dl,
        in_force.finder_id,
        in_force.case.id_,
        in_force.invite_id,
    )

    activity = activity_of(result)
    assert activity["type"] == verb
    assert activity["object"]["id"] == in_force.invite_id
    assert activity["object"]["type"] == "Invite"
    assert activity["object"]["object"]["id"] == embargo_id
    _assert_asked_case_manager(
        in_force.dl,
        actor_id=in_force.finder_id,
        case_id=in_force.case.id_,
        manager_id=in_force.manager_id,
        activity_type=verb,
        semantic_type=semantics.value,
    )
    # Not the CASE_MANAGER: the replica's row moves when the manager's commit
    # is announced, not here (EP-09-008).
    participant = cast(
        CaseParticipant, in_force.dl.read(in_force.participant_id)
    )
    assert participant.consent_for(embargo_id) == row


@pytest.mark.spec("EP-09-012")
@pytest.mark.parametrize(
    "row",
    [
        EmbargoConsentState.UNINVITED,
        EmbargoConsentState.AGREED,
        EmbargoConsentState.DECLINED,
        None,
    ],
    ids=["uninvited", "agreed", "declined", "missing"],
)
@pytest.mark.parametrize("answer", _ANSWER_ONLY)
def test_a_row_with_nothing_to_answer_is_not_found(
    in_force: _InForce,
    answer: _Answer,
    row: EmbargoConsentState | None,
) -> None:
    """An ``UNINVITED``, ``AGREED``, ``DECLINED`` or missing row is not found.

    An ``UNINVITED`` row was never asked.  Withdrawing from an ``AGREED``
    row is ``Leave(EmbargoEvent)``, not an answer (EP-09-013).
    """
    embargo_id = in_force.case.active_embargo_id
    assert embargo_id is not None
    _set_row(in_force.dl, in_force.participant_id, embargo_id, row)
    # A missing row is the record's own not-found; the others name the row.
    reason = "EmbargoConsent" if row is None else f"is {row.value}"

    with pytest.raises(VultronNotFoundError, match=reason):
        answer(
            in_force.dl,
            in_force.finder_id,
            in_force.case.id_,
            in_force.invite_id,
        )
    assert in_force.dl.outbox_list() == []


@pytest.mark.spec("EP-09-012")
@pytest.mark.parametrize("answer", _ANSWER_ONLY)
def test_an_invite_the_actor_does_not_hold_is_not_found(
    in_force: _InForce,
    answer: _Answer,
) -> None:
    """An unknown Invite id raises not-found, though the row is ``INVITED``."""
    with pytest.raises(VultronNotFoundError, match="no-such-invite"):
        answer(
            in_force.dl,
            in_force.finder_id,
            in_force.case.id_,
            "https://example.org/activities/no-such-invite",
        )
    assert in_force.dl.outbox_list() == []


@pytest.mark.spec("EP-09-012")
@pytest.mark.parametrize("answer", _ANSWER_ONLY)
def test_an_invite_addressed_to_another_actor_is_not_found(
    in_force: _InForce,
    answer: _Answer,
) -> None:
    """The Invite must be the one *this* actor received."""
    embargo_id = in_force.case.active_embargo_id
    assert embargo_id is not None
    embargo = cast(as_EmbargoEvent, in_force.dl.read(embargo_id))
    others_invite = _store_received_invite(
        in_force.dl,
        embargo,
        case_id=in_force.case.id_,
        manager_id=in_force.manager_id,
        invitee_id="https://example.org/actors/someone-else",
    )

    with pytest.raises(VultronNotFoundError, match="addressed to"):
        answer(
            in_force.dl, in_force.finder_id, in_force.case.id_, others_invite
        )
    assert in_force.dl.outbox_list() == []


@pytest.mark.spec("EP-09-012", "EP-09-010")
@pytest.mark.parametrize("answer", _ANSWER_ONLY)
def test_an_invite_naming_several_invitees_is_not_found(
    in_force: _InForce,
    answer: _Answer,
) -> None:
    """An Invite with two ``to`` recipients has no invitee (EP-09-010).

    The actor is one of them, but the CASE_MANAGER would refuse the answer,
    so the trigger does not send it.
    """
    embargo_id = in_force.case.active_embargo_id
    assert embargo_id is not None
    embargo = cast(as_EmbargoEvent, in_force.dl.read(embargo_id))
    shared_invite = _store_received_invite(
        in_force.dl,
        embargo,
        case_id=in_force.case.id_,
        manager_id=in_force.manager_id,
        invitee_id=in_force.finder_id,
        to=[in_force.finder_id, "https://example.org/actors/someone-else"],
    )

    with pytest.raises(VultronNotFoundError, match="addressed to"):
        answer(
            in_force.dl, in_force.finder_id, in_force.case.id_, shared_invite
        )
    assert in_force.dl.outbox_list() == []


@pytest.mark.spec("EP-09-012")
@pytest.mark.parametrize("answer", _ANSWER_ONLY)
def test_a_held_activity_that_is_not_an_invite_is_not_found(
    in_force: _InForce,
    answer: _Answer,
) -> None:
    """A held non-Invite naming the embargo in force is not an Invite to answer."""
    embargo_id = in_force.case.active_embargo_id
    assert embargo_id is not None
    embargo = cast(as_EmbargoEvent, in_force.dl.read(embargo_id))
    invite = em_propose_embargo_activity(
        embargo,
        context=in_force.case.id_,
        actor=in_force.manager_id,
        to=[in_force.finder_id],
    )
    data = invite.model_dump(
        mode="json", by_alias=True, exclude_none=True, serialize_as_any=True
    )
    data["type"] = "Offer"
    offer = parse_activity(data)
    archive_received(in_force.dl, offer)

    with pytest.raises(VultronNotFoundError, match=offer.id_):
        answer(in_force.dl, in_force.finder_id, in_force.case.id_, offer.id_)
    assert in_force.dl.outbox_list() == []


@pytest.mark.spec("EP-09-012")
@pytest.mark.parametrize(("answer", "verb", "semantics"), _ANSWERS)
def test_an_invite_the_inbox_still_defers_is_answered(
    in_force: _InForce,
    answer: _Answer,
    verb: str,
    semantics: MessageSemantics,
) -> None:
    """An Invite held only by the inbox, waiting on its case, still answers.

    The inbox holds its received body in a ``DeferredInboxActivity``, never
    under the Invite's own id (DL-06-006), and the answer loads that body.
    """
    embargo_id = in_force.case.active_embargo_id
    assert embargo_id is not None
    embargo = cast(as_EmbargoEvent, in_force.dl.read(embargo_id))
    deferred_invite = _store_received_invite(
        in_force.dl,
        embargo,
        case_id=in_force.case.id_,
        manager_id=in_force.manager_id,
        invitee_id=in_force.finder_id,
        deferred=True,
    )
    assert in_force.dl.read(deferred_invite) is None

    result = answer(
        in_force.dl, in_force.finder_id, in_force.case.id_, deferred_invite
    )

    activity = activity_of(result)
    assert activity["type"] == verb
    assert activity["object"]["id"] == deferred_invite
    _assert_asked_case_manager(
        in_force.dl,
        actor_id=in_force.finder_id,
        case_id=in_force.case.id_,
        manager_id=in_force.manager_id,
        activity_type=verb,
        semantic_type=semantics.value,
    )


@pytest.mark.spec("EP-09-012", "DL-06-006")
@pytest.mark.parametrize(("answer", "verb", "semantics"), _ANSWERS)
def test_an_invite_held_only_as_its_archive_record_is_answered(
    in_force: _InForce,
    answer: _Answer,
    verb: str,
    semantics: MessageSemantics,
) -> None:
    """The archive record alone answers: no copy under the sender's id.

    The answer wraps the Invite as intake archived it, so the store never
    needs a record readable by the id its sender chose (DL-06-006).
    """
    embargo_id = in_force.case.active_embargo_id
    assert embargo_id is not None
    embargo = cast(as_EmbargoEvent, in_force.dl.read(embargo_id))
    archived_invite = _store_received_invite(
        in_force.dl,
        embargo,
        case_id=in_force.case.id_,
        manager_id=in_force.manager_id,
        invitee_id=in_force.finder_id,
    )
    assert in_force.dl.read(archived_invite) is None

    result = answer(
        in_force.dl, in_force.finder_id, in_force.case.id_, archived_invite
    )

    activity = activity_of(result)
    assert activity["type"] == verb
    assert activity["object"]["id"] == archived_invite
    assert activity["object"]["object"]["id"] == embargo_id
    assert in_force.dl.read(archived_invite) is None
    _assert_asked_case_manager(
        in_force.dl,
        actor_id=in_force.finder_id,
        case_id=in_force.case.id_,
        manager_id=in_force.manager_id,
        activity_type=verb,
        semantic_type=semantics.value,
    )


@pytest.mark.spec("EP-09-012")
@pytest.mark.parametrize("answer", _ANSWER_ONLY)
def test_an_invite_to_an_embargo_not_in_force_is_not_found(
    in_force: _InForce,
    answer: _Answer,
) -> None:
    """A held Invite whose embargo is neither open nor in force is not found.

    The participant holds an ``INVITED`` row for that embargo too, so only the
    embargo-in-force check can refuse it.
    """
    other = as_EmbargoEvent(
        context=in_force.case.id_, end_time=days_from_now_utc(30)
    )
    in_force.dl.create(other)
    _set_row(
        in_force.dl,
        in_force.participant_id,
        other.id_,
        EmbargoConsentState.INVITED,
    )
    stale_invite = _store_received_invite(
        in_force.dl,
        other,
        case_id=in_force.case.id_,
        manager_id=in_force.manager_id,
        invitee_id=in_force.finder_id,
    )

    with pytest.raises(VultronNotFoundError, match="embargo in force"):
        answer(
            in_force.dl, in_force.finder_id, in_force.case.id_, stale_invite
        )
    assert in_force.dl.outbox_list() == []


@pytest.mark.spec("EP-09-012", "EP-08-002")
@pytest.mark.parametrize("answer", _ANSWER_ONLY)
def test_a_call_naming_no_invite_never_falls_back_to_the_embargo_in_force(
    in_force: _InForce,
    answer: _Answer,
) -> None:
    """No name and no open proposal raises not-found.

    The participant holds an ``INVITED`` row and the received Invite for the
    embargo in force, so a fallback would answer it and fail this test.
    """
    embargo_id = in_force.case.active_embargo_id
    assert embargo_id is not None
    participant = cast(
        CaseParticipant, in_force.dl.read(in_force.participant_id)
    )
    assert participant.consent_for(embargo_id) == EmbargoConsentState.INVITED

    with pytest.raises(VultronNotFoundError, match="EmbargoProposal"):
        answer(in_force.dl, in_force.finder_id, in_force.case.id_, None)
    assert in_force.dl.outbox_list() == []


@pytest.mark.spec("EP-09-012")
@pytest.mark.parametrize("answer", _ANSWER_ONLY)
def test_the_case_owner_cannot_answer_the_embargo_in_force(
    in_force: _InForce,
    answer: _Answer,
) -> None:
    """The owner's answer is its decision, and the embargo in force is decided.

    Even with an ``INVITED`` row and an Invite addressed to it, the owner
    would otherwise re-activate (or reject) the active embargo.
    """
    embargo_id = in_force.case.active_embargo_id
    assert embargo_id is not None
    case = cast(VulnerabilityCase, in_force.dl.read(in_force.case.id_))
    case.attributed_to = in_force.finder_id
    in_force.dl.save(case)

    with pytest.raises(VultronNotFoundError, match="case owner"):
        answer(
            in_force.dl,
            in_force.finder_id,
            in_force.case.id_,
            in_force.invite_id,
        )
    assert in_force.dl.outbox_list() == []


@pytest.mark.spec("EP-09-012", "EMB-17-002", "MSM-07-003")
@pytest.mark.parametrize(
    ("answer", "row_after"),
    [
        pytest.param(_accept, EmbargoConsentState.AGREED, id="accept"),
        pytest.param(_reject, EmbargoConsentState.DECLINED, id="reject"),
    ],
)
def test_a_case_manager_answering_records_its_own_row(
    in_force: _InForce,
    answer: _Answer,
    row_after: EmbargoConsentState,
) -> None:
    """A CASE_MANAGER that is not the owner records its answer itself.

    Its ``TIMED_OUT`` row for the embargo in force moves directly to the
    answer (``TIMED_OUT -> AGREED`` per EMB-17-002, or ``DECLINED``), and the
    register is untouched: the embargo stays in force.
    """
    embargo_id = in_force.case.active_embargo_id
    assert embargo_id is not None
    _set_row(
        in_force.dl,
        in_force.participant_id,
        embargo_id,
        EmbargoConsentState.TIMED_OUT,
    )
    case = cast(VulnerabilityCase, in_force.dl.read(in_force.case.id_))
    owner_pid = case.actor_participant_index[in_force.manager_id]
    owner = cast(CaseParticipant, in_force.dl.read(owner_pid))
    owner.remove_role(CVDRole.CASE_MANAGER)
    in_force.dl.save(owner)
    finder = cast(CaseParticipant, in_force.dl.read(in_force.participant_id))
    finder.add_role(CVDRole.CASE_MANAGER)
    in_force.dl.save(finder)

    result = answer(
        in_force.dl,
        in_force.finder_id,
        in_force.case.id_,
        in_force.invite_id,
    )

    if row_after is EmbargoConsentState.AGREED:
        assert activity_of(result)["object"]["id"] == in_force.invite_id
    else:
        # The CASE_MANAGER's own Reject is its row's Update(EmbargoConsent),
        # so no Reject is built, and the Update is what it reports
        # (MSM-07-004, ADR-0152, TRIG-04-001).
        activity = activity_of(result)
        assert activity["type"] == "Update"
        assert activity["object"]["state"] == row_after.value
    finder = cast(CaseParticipant, in_force.dl.read(in_force.participant_id))
    assert finder.consent_for(embargo_id) == row_after
    updated = cast(VulnerabilityCase, in_force.dl.read(in_force.case.id_))
    assert updated.active_embargo_id == embargo_id
