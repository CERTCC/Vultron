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
"""The lifetime of a stub Invite: deadline, expiry, re-invite, re-issue (#4049).

CM-11-014 (a deadline; expiry closes the Invite and writes no participant
state), CM-11-015 (re-invite on the same record), CM-11-016 (re-issue when the
active embargo changes) and ASK-03-002 (a late ``Accept`` is void).  The
planned-behaviour tests for the same requirements are in
``test_case_joining_planned.py``.
"""

from datetime import datetime, timedelta
from typing import Any

import pytest

from test.core.use_cases.received.actor.test_case_joining_planned import (
    route_received,
)
from test.core.use_cases.received.conftest import (
    seed_store_owner_as_case_manager,
)
from test.core.use_cases.triggers.embargo.conftest import (
    _build_active_embargo_case,
)
from test.core.use_cases.triggers.test_case_joining_planned import (
    _case_with_invitee_record,
    _hold_case_owner,
    _invites_to,
    _participant_of,
    _send_stub_invite,
)
from test.support.embargo_register import (
    activate,
    propose,
    terminate as terminate_register,
)
from test.support.trigger_results import activity_of
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.case.stub_invite_lifetime import (
    RecordedStubInvite,
    outstanding_stale_stubs,
    recorded_stub_invites,
    replacement_for,
    stub_invite_expired,
)
from vultron.core.models._helpers import days_from_now_utc, now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.events.actor import OfferActorToCaseReceivedEvent
from vultron.core.models.protocol_pair import (
    INVITE_ACTOR_TO_CASE_EXPIRY,
    INVITE_ACTOR_TO_CASE_REPLY_TYPES,
    AskExpiry,
)
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.states.rm import RM
from vultron.core.use_cases.received.actor.suggest import (
    OfferActorToCaseReceivedUseCase,
)
from vultron.core.use_cases.triggers.actor import SvcSuggestActorToCaseUseCase
from vultron.core.use_cases.triggers.embargo import SvcTerminateEmbargoUseCase
from vultron.core.use_cases.triggers.requests import (
    SuggestActorToCaseTriggerRequest,
    TerminateEmbargoTriggerRequest,
)
from vultron.enums.roles import CVDRole
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import remove_embargo_from_case_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Invite,
    as_Reject,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

_NOW_MODULE = "vultron.core.behaviors.case.nodes.stub_invite_lifetime.now_utc"


def _at(monkeypatch: pytest.MonkeyPatch, instant: datetime) -> None:
    """Make the CASE_MANAGER's guard read *instant* as the current time."""
    monkeypatch.setattr(_NOW_MODULE, lambda: instant)


def _deadline(invite: dict[str, Any]) -> datetime:
    assert invite.get("endTime") is not None, "stub Invite has no deadline"
    return datetime.fromisoformat(invite["endTime"])


def _answer(
    dl: Any,
    reply: type[as_Accept] | type[as_Reject],
    *,
    manager_id: str,
    invitee_id: str,
    invite_id: str,
):
    invite = dl.read(invite_id)
    assert isinstance(invite, as_Invite)
    return route_received(
        dl,
        reply(actor=invitee_id, object_=invite, in_reply_to=invite_id),
        receiving_actor_id=manager_id,
    )


def _plain_case(dl: Any, manager_id: str) -> VulnerabilityCase:
    case = VulnerabilityCase(
        attributed_to=manager_id,
        name="Lifetime",
        content="Content",
        stub_summary="Lifetime summary",
    )
    seed_store_owner_as_case_manager(dl, case)
    dl.create(case)
    return case


def _terminate(dl: Any, owner_id: str, case_id: str) -> None:
    SvcTerminateEmbargoUseCase(
        dl,
        TerminateEmbargoTriggerRequest(actor_id=owner_id, case_id=case_id),
        trigger_activity=TriggerActivityAdapter(dl),
        sync_port=SyncActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()


@pytest.mark.spec("ASK-03-008")
def test_stub_invite_is_a_void_expiry_ask_closed_by_accept_and_reject() -> (
    None
):
    """The ask kind is declared next to the embargo one (ASK-03-001/002)."""
    assert INVITE_ACTOR_TO_CASE_EXPIRY is AskExpiry.VOID
    assert {
        "accept_invite_actor_to_case",
        "reject_invite_actor_to_case",
    } == INVITE_ACTOR_TO_CASE_REPLY_TYPES


@pytest.mark.spec("CM-11-014")
def test_deadline_is_the_configured_window_after_published(
    actor_store,
) -> None:
    """With no embargo the deadline is ``published`` + ``default_rsvp_window``."""
    manager, dl = actor_store("CaseManager")
    invitee, _ = actor_store("Vendor")
    dl.create(invitee)
    case = _plain_case(dl, manager.id_)

    invite = _send_stub_invite(dl, manager.id_, case.id_, invitee.id_)

    published = datetime.fromisoformat(invite["published"])
    assert _deadline(invite) - published == timedelta(days=7)


@pytest.mark.spec("CM-11-014")
def test_deadline_is_capped_at_the_end_of_the_embargo_it_carries(
    actor_store,
) -> None:
    """An active embargo ending before the window caps the deadline (EP-07-006)."""
    manager, dl = actor_store("CaseManager")
    invitee, _ = actor_store("Vendor")
    dl.create(invitee)
    case = VulnerabilityCase(
        attributed_to=manager.id_,
        name="Short embargo",
        content="Content",
        stub_summary="Short embargo summary",
    )
    embargo = as_EmbargoEvent(
        id_=f"{case.id_}/embargo/e1",
        content="Active embargo",
        context=case.id_,
        end_time=days_from_now_utc(2),
    )
    dl.create(embargo)
    activate(case, embargo.id_)
    seed_store_owner_as_case_manager(dl, case)
    dl.create(case)

    invite = _send_stub_invite(dl, manager.id_, case.id_, invitee.id_)

    assert _deadline(invite) == embargo.end_time


@pytest.mark.spec("CM-11-014")
def test_expiry_closes_the_invite_and_leaves_the_record_unchanged(
    actor_store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A late ``Accept`` is void: refused, with RM, consent and ``joined`` as before."""
    manager, dl = actor_store("CaseManager")
    invitee, _ = actor_store("Vendor")
    dl.create(invitee)
    owner, _ = actor_store("Owner")
    case, _, _ = _build_active_embargo_case(dl, manager.id_, owner.id_)
    invite = _send_stub_invite(dl, manager.id_, case.id_, invitee.id_)
    before = _participant_of(dl, case.id_, invitee.id_)
    assert before.joined is False

    _at(monkeypatch, _deadline(invite) + timedelta(seconds=1))
    result = _answer(
        dl,
        as_Accept,
        manager_id=manager.id_,
        invitee_id=invitee.id_,
        invite_id=invite["id"],
    )

    assert result.disposition is HandlerDisposition.REFUSED
    assert result.reason is not None and "expired" in result.reason
    after = _participant_of(dl, case.id_, invitee.id_)
    assert after.model_dump() == before.model_dump()
    assert after.joined is False
    assert not after.rm_closed
    assert [row.state for row in after.embargo_consents] == [
        EmbargoConsentState.INVITED
    ]


@pytest.mark.spec("CM-11-014")
def test_the_deadline_itself_is_expired_and_one_instant_before_is_not(
    actor_store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The embargo Invite's boundary: ``now == end_time`` has expired."""
    manager, dl = actor_store("CaseManager")
    invitee, _ = actor_store("Vendor")
    dl.create(invitee)
    case = _plain_case(dl, manager.id_)
    invite = _send_stub_invite(dl, manager.id_, case.id_, invitee.id_)
    deadline = _deadline(invite)

    _at(monkeypatch, deadline)
    at_deadline = _answer(
        dl,
        as_Accept,
        manager_id=manager.id_,
        invitee_id=invitee.id_,
        invite_id=invite["id"],
    )
    assert at_deadline.disposition is HandlerDisposition.REFUSED

    _at(monkeypatch, deadline - timedelta(microseconds=1))
    before_deadline = _answer(
        dl,
        as_Accept,
        manager_id=manager.id_,
        invitee_id=invitee.id_,
        invite_id=invite["id"],
    )
    assert before_deadline.disposition is HandlerDisposition.APPLIED
    assert _participant_of(dl, case.id_, invitee.id_).joined is True


@pytest.mark.spec("CM-11-015")
def test_reinvite_after_expiry_is_fresh_on_the_same_record(
    actor_store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The invitee is invited again, accepts the new Invite and joins."""
    manager, dl = actor_store("CaseManager")
    invitee, _ = actor_store("Vendor")
    dl.create(invitee)
    case = _plain_case(dl, manager.id_)
    first = _send_stub_invite(dl, manager.id_, case.id_, invitee.id_)
    record_id = _participant_of(dl, case.id_, invitee.id_).id_
    expired_at = _deadline(first) + timedelta(seconds=1)

    second = _send_stub_invite(dl, manager.id_, case.id_, invitee.id_)

    assert second["id"] != first["id"]
    assert _participant_of(dl, case.id_, invitee.id_).id_ == record_id
    assert _deadline(second) >= _deadline(first)
    after = dl.read_case(case.id_)
    assert after is not None
    assert list(after.case_participants).count(record_id) == 1
    # The old Invite is dead after its own deadline; the fresh one still lives.
    _at(monkeypatch, expired_at)
    old = _answer(
        dl,
        as_Accept,
        manager_id=manager.id_,
        invitee_id=invitee.id_,
        invite_id=first["id"],
    )
    assert old.disposition is HandlerDisposition.REFUSED
    _at(monkeypatch, _deadline(second) - timedelta(seconds=1))
    new = _answer(
        dl,
        as_Accept,
        manager_id=manager.id_,
        invitee_id=invitee.id_,
        invite_id=second["id"],
    )
    assert new.disposition is HandlerDisposition.APPLIED


@pytest.mark.spec("CM-11-015")
def test_manager_refuses_a_reinvite_of_a_closed_participant(
    actor_store,
) -> None:
    """The CASE_MANAGER's own tree refuses it too, with nothing queued."""
    manager, dl = actor_store("CaseManager")
    invitee, _ = actor_store("Vendor")
    dl.create(invitee)
    case, _ = _case_with_invitee_record(
        dl, manager.id_, invitee.id_, RM.CLOSED
    )
    _hold_case_owner(dl, case.id_, manager.id_)
    offer = activity_of(
        SvcSuggestActorToCaseUseCase(
            dl,
            SuggestActorToCaseTriggerRequest(
                actor_id=manager.id_,
                case_id=case.id_,
                suggested_actor_id=invitee.id_,
                roles=[CVDRole.VENDOR],
            ),
            trigger_activity=TriggerActivityAdapter(dl),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()
    )
    stored = dl.read(offer["id"])
    event = extract_event(stored).model_copy(
        update={"receiving_actor_id": manager.id_}
    )
    assert isinstance(event, OfferActorToCaseReceivedEvent)
    before = set(dl.outbox_list())

    result = OfferActorToCaseReceivedUseCase(
        dl,
        event,
        trigger_activity=TriggerActivityAdapter(dl),
        sync_port=SyncActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()

    assert result.disposition is HandlerDisposition.REFUSED
    assert result.reason is not None and "RM.CLOSED" in result.reason
    assert set(dl.outbox_list()) == before


@pytest.mark.spec("CM-11-016")
def test_an_expired_unanswered_stub_is_not_reissued_on_an_embargo_change(
    actor_store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only an outstanding stub (unanswered, not expired) is re-issued."""
    owner, dl = actor_store("Vendor Owner")
    finder, _ = actor_store("Finder")
    invitee, _ = actor_store("Vendor Two")
    dl.create(finder)
    dl.create(invitee)
    case, _, _ = _build_active_embargo_case(dl, owner.id_, finder.id_)
    original = _send_stub_invite(dl, owner.id_, case.id_, invitee.id_)
    monkeypatch.setattr(
        "vultron.core.behaviors.case.nodes.invite_actor_emit.now_utc",
        lambda: _deadline(original) + timedelta(seconds=1),
    )

    _terminate(dl, owner.id_, case.id_)

    assert [i.id_ for i in _invites_to(dl, invitee.id_)] == [original["id"]]


@pytest.mark.spec("CM-11-016")
def test_a_joined_invitee_is_not_reissued_on_an_embargo_change(
    actor_store,
) -> None:
    """An invitee that accepted has answered; nothing is re-issued to it."""
    owner, dl = actor_store("Vendor Owner")
    finder, _ = actor_store("Finder")
    invitee, _ = actor_store("Vendor Two")
    dl.create(finder)
    dl.create(invitee)
    case, _, _ = _build_active_embargo_case(dl, owner.id_, finder.id_)
    original = _send_stub_invite(dl, owner.id_, case.id_, invitee.id_)
    accepted = _answer(
        dl,
        as_Accept,
        manager_id=owner.id_,
        invitee_id=invitee.id_,
        invite_id=original["id"],
    )
    assert accepted.disposition is HandlerDisposition.APPLIED

    _terminate(dl, owner.id_, case.id_)

    assert [i.id_ for i in _invites_to(dl, invitee.id_)] == [original["id"]]


@pytest.mark.spec("CM-11-016")
def test_a_replacement_carries_a_new_deadline_and_current_terms_and_roles(
    actor_store,
) -> None:
    """The replacement keeps the roles, restamps the deadline, names the old."""
    owner, dl = actor_store("Vendor Owner")
    finder, _ = actor_store("Finder")
    invitee, _ = actor_store("Vendor Two")
    dl.create(finder)
    dl.create(invitee)
    case, _, _ = _build_active_embargo_case(dl, owner.id_, finder.id_)
    original = _send_stub_invite(dl, owner.id_, case.id_, invitee.id_)
    assert original["target"].get("activeEmbargo") is not None
    roster_before = dl.read_case(case.id_)
    assert roster_before is not None

    _terminate(dl, owner.id_, case.id_)

    (replacement,) = [
        i for i in _invites_to(dl, invitee.id_) if i.id_ != original["id"]
    ]
    assert replacement.supersedes == original["id"]
    assert replacement.roles == original["roles"]
    assert replacement.end_time is not None
    assert replacement.end_time >= _deadline(original)
    assert getattr(replacement.target, "active_embargo", None) is None
    # One record throughout; the re-issue wrote no participant state.
    after = dl.read_case(case.id_)
    assert after is not None
    assert (
        after.actor_participant_index == roster_before.actor_participant_index
    )


@pytest.mark.spec("CM-11-016")
def test_a_received_embargo_removal_re_issues_the_outstanding_stub(
    actor_store,
) -> None:
    """The same re-issue runs when the owner's ``Remove(EmbargoEvent)`` arrives."""
    owner, dl = actor_store("Vendor Owner")
    finder, _ = actor_store("Finder")
    invitee, _ = actor_store("Vendor Two")
    dl.create(finder)
    dl.create(invitee)
    case, _, _ = _build_active_embargo_case(dl, owner.id_, finder.id_)
    original = _send_stub_invite(dl, owner.id_, case.id_, invitee.id_)
    embargo = dl.read(case.active_embargo_id)
    assert isinstance(embargo, as_EmbargoEvent)

    result = route_received(
        dl,
        remove_embargo_from_case_activity(
            embargo,
            origin=case.id_,
            context=case.id_,
            actor=owner.id_,
            to=[owner.id_],
        ),
        receiving_actor_id=owner.id_,
        trigger_activity=TriggerActivityAdapter(dl),
    )

    assert result.disposition is HandlerDisposition.APPLIED, result.reason
    (replacement,) = [
        i for i in _invites_to(dl, invitee.id_) if i.id_ != original["id"]
    ]
    assert replacement.supersedes == original["id"]


@pytest.mark.spec("CM-11-016")
def test_an_open_revision_proposal_re_issues_nothing(actor_store) -> None:
    """While EM is REVISE no stub is stale: only the answer that decides it is."""
    owner, dl = actor_store("Vendor Owner")
    finder, _ = actor_store("Finder")
    invitee, _ = actor_store("Vendor Two")
    dl.create(finder)
    dl.create(invitee)
    case, _, _ = _build_active_embargo_case(dl, owner.id_, finder.id_)
    _send_stub_invite(dl, owner.id_, case.id_, invitee.id_)
    stored = dl.read_case(case.id_)
    assert stored is not None
    assert outstanding_stale_stubs(dl, stored, owner.id_, now_utc()) == []

    propose(stored, f"{case.id_}/embargo/revision")
    assert stored.em_state == EM.REVISE
    assert outstanding_stale_stubs(dl, stored, owner.id_, now_utc()) == []

    terminate_register(stored)
    assert stored.em_state == EM.EXITED
    assert len(outstanding_stale_stubs(dl, stored, owner.id_, now_utc())) == 1


@pytest.mark.spec("CM-11-016")
def test_accept_of_a_superseded_stub_names_the_replacement_and_it_can_be_accepted(
    actor_store,
) -> None:
    """The old Invite is refused naming the new one; the new one joins."""
    owner, dl = actor_store("Vendor Owner")
    finder, _ = actor_store("Finder")
    invitee, _ = actor_store("Vendor Two")
    dl.create(finder)
    dl.create(invitee)
    case, _, _ = _build_active_embargo_case(dl, owner.id_, finder.id_)
    original = _send_stub_invite(dl, owner.id_, case.id_, invitee.id_)
    _terminate(dl, owner.id_, case.id_)
    (replacement,) = [
        i for i in _invites_to(dl, invitee.id_) if i.id_ != original["id"]
    ]

    refused = _answer(
        dl,
        as_Accept,
        manager_id=owner.id_,
        invitee_id=invitee.id_,
        invite_id=original["id"],
    )
    assert refused.disposition is HandlerDisposition.REFUSED
    assert refused.reason is not None and replacement.id_ in refused.reason

    accepted = _answer(
        dl,
        as_Accept,
        manager_id=owner.id_,
        invitee_id=invitee.id_,
        invite_id=replacement.id_,
    )
    assert accepted.disposition is HandlerDisposition.APPLIED


def test_recorded_stub_invites_lists_only_this_managers_stubs_for_the_case(
    actor_store,
) -> None:
    manager, dl = actor_store("CaseManager")
    invitee, _ = actor_store("Vendor")
    dl.create(invitee)
    case = _plain_case(dl, manager.id_)
    sent = _send_stub_invite(dl, manager.id_, case.id_, invitee.id_)

    mine = recorded_stub_invites(dl, case.id_, manager.id_)
    assert [s.invite_id for s in mine] == [sent["id"]]
    assert recorded_stub_invites(dl, case.id_, "https://example.org/x") == []
    assert (
        recorded_stub_invites(dl, "https://example.org/other", manager.id_)
        == []
    )


def _stub(
    invite_id: str,
    *,
    minutes: int,
    supersedes: str | None = None,
    end_time: datetime | None = None,
) -> RecordedStubInvite:
    return RecordedStubInvite(
        invite_id=invite_id,
        invitee_id="https://example.org/actors/v",
        case_id="https://example.org/cases/c",
        published=now_utc().replace(year=2026, month=1, day=1)
        + timedelta(minutes=minutes),
        end_time=end_time,
        supersedes=supersedes,
        embargo_id=None,
        roles=("VENDOR",),
        attributed_to=None,
    )


class TestReplacementFor:
    """Which stub supersedes which (CM-11-016)."""

    def test_current_stub_has_no_replacement(self) -> None:
        a = _stub("a", minutes=0)
        assert replacement_for(a, [a]) is None

    def test_replacement_that_names_the_stub_supersedes_it(self) -> None:
        a = _stub("a", minutes=0)
        b = _stub("b", minutes=1, supersedes="a")
        assert replacement_for(a, [a, b]) == b
        assert replacement_for(b, [a, b]) is None

    def test_an_older_stub_left_live_by_a_reinvite_is_superseded_too(
        self,
    ) -> None:
        a = _stub("a", minutes=0)
        b = _stub("b", minutes=1)  # re-invite: names nothing
        c = _stub("c", minutes=2, supersedes="b")  # embargo change
        assert replacement_for(a, [a, b, c]) == c
        assert replacement_for(b, [a, b, c]) == c

    def test_the_newest_replacement_wins(self) -> None:
        a = _stub("a", minutes=0)
        b = _stub("b", minutes=1, supersedes="a")
        c = _stub("c", minutes=2, supersedes="b")
        assert replacement_for(a, [a, b, c]) == c


class TestExpired:
    def test_no_deadline_never_expires(self) -> None:
        assert not stub_invite_expired(_stub("a", minutes=0), now_utc())

    def test_deadline_is_expired_at_the_instant_it_arrives(self) -> None:
        deadline = now_utc()
        stub = _stub("a", minutes=0, end_time=deadline)
        assert stub_invite_expired(stub, deadline)
        assert not stub_invite_expired(stub, deadline - timedelta(seconds=1))
