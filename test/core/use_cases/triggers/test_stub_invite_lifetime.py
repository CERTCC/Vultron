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
active embargo changes) and ASK-03-008 (expiry is stale: a late reply is honoured).  The
trigger-side tests for the same requirements are in
``test_case_joining_trigger.py``.
"""

from datetime import datetime, timedelta
from typing import Any

import pytest

from test.core.use_cases.received.actor.test_case_joining_replies import (
    route_received,
)
from test.core.use_cases.received.conftest import (
    seed_store_owner_as_case_manager,
)
from test.core.use_cases.triggers.embargo.conftest import (
    _build_active_embargo_case,
)
from test.core.use_cases.triggers.test_case_joining_trigger import (
    _case_with_invitee_record,
    _hold_case_owner,
    _invites_to,
    _participant_of,
    _send_stub_invite,
)
from test.support.clock_decisions import run_end_time_check
from test.support.embargo_register import (
    activate,
    propose,
    reject,
    terminate as terminate_register,
    write_consent_rows,
)
from test.support.ledger import ledger_entries
from test.support.trigger_results import activity_of
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.config.actor import ActorConfig
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
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.protocol_pair import (
    INVITE_ACTOR_TO_CASE_EXPIRY,
    INVITE_ACTOR_TO_CASE_REPLY_TYPES,
    AskExpiry,
)
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.em import EM
from vultron.core.states.embargo_register import TerminationReason
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
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Invite,
    as_Reject,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

_EMIT_NOW_MODULE = "vultron.core.behaviors.case.nodes.stub_reissue.now_utc"


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
        reply(
            actor=invitee_id,
            to=[manager_id],
            object_=invite,
            in_reply_to=invite_id,
        ),
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
@pytest.mark.spec("CM-17-002")
def test_a_revise_stub_deadline_is_capped_by_the_embargo_in_force(
    actor_store,
) -> None:
    """In EM REVISE the stub's embargo in force caps its deadline.

    The open revision is not the stub's embargo (CM-17-002), so its later end
    plays no part in the cap.
    """
    manager, dl = actor_store("CaseManager")
    invitee, _ = actor_store("Vendor")
    dl.create(invitee)
    case = VulnerabilityCase(
        attributed_to=manager.id_,
        name="Revised embargo",
        content="Content",
        stub_summary="Revised embargo summary",
    )
    in_force = as_EmbargoEvent(
        id_=f"{case.id_}/embargo/e1",
        content="Embargo in force",
        context=case.id_,
        end_time=days_from_now_utc(2),
    )
    revision = as_EmbargoEvent(
        id_=f"{case.id_}/embargo/e2",
        content="Revision",
        context=case.id_,
        end_time=days_from_now_utc(30),
    )
    dl.create(in_force)
    dl.create(revision)
    activate(case, in_force.id_)
    propose(case, revision.id_)
    assert case.em_state == EM.REVISE
    seed_store_owner_as_case_manager(dl, case)
    dl.create(case)

    invite = _send_stub_invite(dl, manager.id_, case.id_, invitee.id_)

    assert invite["target"]["activeEmbargo"]["id"] == in_force.id_
    assert _deadline(invite) == in_force.end_time


@pytest.mark.spec("ASK-03-008")
def test_stub_invite_is_a_stale_expiry_ask_closed_by_accept_and_reject() -> (
    None
):
    """The ask kind is declared next to the embargo one (ASK-03-001/002)."""
    assert INVITE_ACTOR_TO_CASE_EXPIRY is AskExpiry.STALE
    assert {
        "accept_invite_actor_to_case",
        "reject_invite_actor_to_case",
    } == INVITE_ACTOR_TO_CASE_REPLY_TYPES


def _expire_then_terminate(
    dl: Any,
    monkeypatch: pytest.MonkeyPatch,
    invite: dict[str, Any],
    owner_id: str,
    case_id: str,
    after_deadline: timedelta,
) -> None:
    """Move the clock to *after_deadline* past the stub's deadline, end the embargo."""
    instant = _deadline(invite) + after_deadline
    monkeypatch.setattr(_EMIT_NOW_MODULE, lambda: instant)
    _terminate(dl, owner_id, case_id)


@pytest.mark.spec("CM-11-014")
def test_expiry_writes_nothing_and_a_late_accept_still_joins(
    actor_store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Expiry only stops the wait: the record is untouched and a late Accept joins."""
    owner, dl = actor_store("Vendor Owner")
    finder, _ = actor_store("Finder")
    invitee, _ = actor_store("Vendor Two")
    dl.create(finder)
    dl.create(invitee)
    case, _, _ = _build_active_embargo_case(dl, owner.id_, finder.id_)
    invite = _send_stub_invite(dl, owner.id_, case.id_, invitee.id_)
    before = _participant_of(dl, case.id_, invitee.id_)
    assert before.joined is False

    _expire_then_terminate(
        dl, monkeypatch, invite, owner.id_, case.id_, timedelta(seconds=1)
    )

    after = _participant_of(dl, case.id_, invitee.id_)
    assert after.model_dump() == before.model_dump()
    assert [row.state for row in after.embargo_consents] == [
        EmbargoConsentState.INVITED
    ]
    assert [i.id_ for i in _invites_to(dl, invitee.id_)] == [invite["id"]]

    late = _answer(
        dl,
        as_Accept,
        manager_id=owner.id_,
        invitee_id=invitee.id_,
        invite_id=invite["id"],
    )
    assert late.disposition is HandlerDisposition.APPLIED, late.reason
    assert _participant_of(dl, case.id_, invitee.id_).joined is True


@pytest.mark.spec("CM-11-014")
def test_a_late_reject_closes_the_record_as_a_live_one_would(
    actor_store,
) -> None:
    manager, dl = actor_store("CaseManager")
    invitee, _ = actor_store("Vendor")
    dl.create(invitee)
    case = _plain_case(dl, manager.id_)
    invite = _send_stub_invite(dl, manager.id_, case.id_, invitee.id_)

    late = _answer(
        dl,
        as_Reject,
        manager_id=manager.id_,
        invitee_id=invitee.id_,
        invite_id=invite["id"],
    )

    assert late.disposition is HandlerDisposition.APPLIED, late.reason
    assert _participant_of(dl, case.id_, invitee.id_).rm_closed


@pytest.mark.spec("CM-11-014")
@pytest.mark.parametrize(
    "offset,reissued",
    [(timedelta(0), False), (-timedelta(microseconds=1), True)],
    ids=["at-the-deadline-is-expired", "one-instant-before-is-live"],
)
def test_the_deadline_itself_is_expired(
    actor_store,
    monkeypatch: pytest.MonkeyPatch,
    offset: timedelta,
    reissued: bool,
) -> None:
    """The embargo Invite's boundary: ``now == end_time`` has expired.

    An expired stub is not outstanding, so the embargo change re-issues
    nothing; one an instant before the deadline is still outstanding.
    """
    owner, dl = actor_store("Vendor Owner")
    finder, _ = actor_store("Finder")
    invitee, _ = actor_store("Vendor Two")
    dl.create(finder)
    dl.create(invitee)
    case, _, _ = _build_active_embargo_case(dl, owner.id_, finder.id_)
    invite = _send_stub_invite(dl, owner.id_, case.id_, invitee.id_)

    _expire_then_terminate(
        dl, monkeypatch, invite, owner.id_, case.id_, offset
    )

    assert (len(_invites_to(dl, invitee.id_)) == 2) is reissued


@pytest.mark.spec("CM-11-015")
def test_reinvite_replaces_the_earlier_stub_on_the_same_record(
    actor_store,
) -> None:
    """The fresh Invite names the earlier one; only the fresh one can be accepted."""
    manager, dl = actor_store("CaseManager")
    invitee, _ = actor_store("Vendor")
    dl.create(invitee)
    case = _plain_case(dl, manager.id_)
    first = _send_stub_invite(dl, manager.id_, case.id_, invitee.id_)
    assert first.get("inReplyTo") is None
    record_id = _participant_of(dl, case.id_, invitee.id_).id_

    second = _send_stub_invite(dl, manager.id_, case.id_, invitee.id_)

    assert second["id"] != first["id"]
    assert second["inReplyTo"] == first["id"]
    assert _participant_of(dl, case.id_, invitee.id_).id_ == record_id
    assert _deadline(second) >= _deadline(first)
    after = dl.read_case(case.id_)
    assert after is not None
    assert list(after.case_participants).count(record_id) == 1
    old = _answer(
        dl,
        as_Accept,
        manager_id=manager.id_,
        invitee_id=invitee.id_,
        invite_id=first["id"],
    )
    assert old.disposition is HandlerDisposition.REFUSED
    assert old.reason is not None and second["id"] in old.reason
    new = _answer(
        dl,
        as_Accept,
        manager_id=manager.id_,
        invitee_id=invitee.id_,
        invite_id=second["id"],
    )
    assert new.disposition is HandlerDisposition.APPLIED


@pytest.mark.spec("CM-11-015")
@pytest.mark.spec("CM-11-016")
def test_in_reply_to_on_a_stub_invite_survives_parse_and_extraction(
    actor_store,
) -> None:
    """``inReplyTo`` is the standard AS2 property: the wire parser keeps it, the
    sealed body carries it, the Invite is still matched as a stub Invite, and
    the extracted event carries the superseded Invite's id."""
    manager, dl = actor_store("CaseManager")
    invitee, _ = actor_store("Vendor")
    dl.create(invitee)
    case = _plain_case(dl, manager.id_)
    first = _send_stub_invite(dl, manager.id_, case.id_, invitee.id_)
    second = _send_stub_invite(dl, manager.id_, case.id_, invitee.id_)

    parsed = parse_activity(second)
    event = extract_event(parsed)

    assert parsed.in_reply_to == first["id"]
    assert event.semantic_type is MessageSemantics.INVITE_ACTOR_TO_CASE
    assert event.in_reply_to == first["id"]
    stored = dl.read(second["id"])
    assert isinstance(stored, as_Invite)
    assert stored.in_reply_to == first["id"]


@pytest.mark.spec("CM-11-015")
def test_a_reject_of_the_replaced_stub_is_honoured(actor_store) -> None:
    manager, dl = actor_store("CaseManager")
    invitee, _ = actor_store("Vendor")
    dl.create(invitee)
    case = _plain_case(dl, manager.id_)
    first = _send_stub_invite(dl, manager.id_, case.id_, invitee.id_)
    _send_stub_invite(dl, manager.id_, case.id_, invitee.id_)

    old = _answer(
        dl,
        as_Reject,
        manager_id=manager.id_,
        invitee_id=invitee.id_,
        invite_id=first["id"],
    )

    assert old.disposition is HandlerDisposition.APPLIED, old.reason
    assert _participant_of(dl, case.id_, invitee.id_).rm_closed


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
        "vultron.core.behaviors.case.nodes.stub_reissue.now_utc",
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

    # Joining sent the invitee its full-case Invite (CM-11-010); no stub
    # Invite was re-issued.
    stub_invites = [
        i
        for i in _invites_to(dl, invitee.id_)
        if getattr(i.target, "type_", None) != "VulnerabilityCase"
    ]
    assert [i.id_ for i in stub_invites] == [original["id"]]


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
    assert replacement.in_reply_to == original["id"]
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
@pytest.mark.spec("OX-06-002")
def test_a_replacement_whose_commit_failed_is_recorded_once_by_the_next_run(
    actor_store,
) -> None:
    """A replacement is queued, then committed; a failed commit is finished.

    The replacement's id derives from the stub it replaces, and the next run
    of the re-issue node records the replacement it already sent, under the
    same id: one queued Invite, one entry (ADR-0119, OX-06-002).
    """
    from test.support.ledger import fail_commits
    from vultron.core.behaviors.bridge import BTBridge
    from vultron.core.behaviors.case.nodes.stub_reissue import (
        ReissueStubInvitesNode,
    )
    from vultron.core.behaviors.sync import commit_tree
    from vultron.core.models.case_ledger_entry import CaseLedgerEntry
    from vultron.errors import VultronBTInternalError

    owner, dl = actor_store("Vendor Owner")
    finder, _ = actor_store("Finder")
    invitee, _ = actor_store("Vendor Two")
    dl.create(finder)
    dl.create(invitee)
    case, _, _ = _build_active_embargo_case(dl, owner.id_, finder.id_)
    original = _send_stub_invite(dl, owner.id_, case.id_, invitee.id_)

    with pytest.MonkeyPatch.context() as mp:
        failed = fail_commits(
            mp,
            commit_tree,
            when=lambda kw: kw["event_type"] == "invite_actor_to_case",
        )
        with pytest.raises(VultronBTInternalError, match="commit failed"):
            _terminate(dl, owner.id_, case.id_)
    (replacement_id,) = failed
    assert dl.outbox_list().count(replacement_id) == 1

    def _recorded() -> list[str]:
        return [
            e.log_object_id
            for e in dl.list_objects("CaseLedgerEntry")
            if isinstance(e, CaseLedgerEntry)
            and e.log_object_id == replacement_id
        ]

    assert _recorded() == []

    result = BTBridge(
        datalayer=dl,
        trigger_activity=TriggerActivityAdapter(dl),
        sync_port=SyncActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute_with_setup(
        tree=ReissueStubInvitesNode(case_id=case.id_), actor_id=owner.id_
    )

    assert result.status.name == "SUCCESS", result
    assert dl.outbox_list().count(replacement_id) == 1
    assert _recorded() == [replacement_id]
    replacements = [
        i for i in _invites_to(dl, invitee.id_) if i.id_ != original["id"]
    ]
    assert [i.id_ for i in replacements] == [replacement_id]


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
            reason=TerminationReason.EARLY,
        ),
        receiving_actor_id=owner.id_,
        trigger_activity=TriggerActivityAdapter(dl),
    )

    assert result.disposition is HandlerDisposition.APPLIED, result.reason
    (replacement,) = [
        i for i in _invites_to(dl, invitee.id_) if i.id_ != original["id"]
    ]
    assert replacement.in_reply_to == original["id"]


@pytest.mark.spec("CM-11-014")
def test_a_re_issued_stub_uses_the_managers_configured_rsvp_window(
    actor_store,
) -> None:
    """The replacement's deadline follows the configured window, not the default."""
    owner, dl = actor_store("Vendor Owner")
    finder, _ = actor_store("Finder")
    invitee, _ = actor_store("Vendor Two")
    dl.create(finder)
    dl.create(invitee)
    case, _, _ = _build_active_embargo_case(dl, owner.id_, finder.id_)
    original = _send_stub_invite(dl, owner.id_, case.id_, invitee.id_)
    embargo = dl.read(case.active_embargo_id)
    assert isinstance(embargo, as_EmbargoEvent)
    window = timedelta(days=2)
    config = ActorConfig(
        min_rsvp_window=timedelta(hours=1), default_rsvp_window=window
    )

    result = route_received(
        dl,
        remove_embargo_from_case_activity(
            embargo,
            origin=case.id_,
            context=case.id_,
            actor=owner.id_,
            to=[owner.id_],
            reason=TerminationReason.EARLY,
        ),
        receiving_actor_id=owner.id_,
        trigger_activity=TriggerActivityAdapter(dl),
        actor_config=config,
    )

    assert result.disposition is HandlerDisposition.APPLIED, result.reason
    (replacement,) = [
        i for i in _invites_to(dl, invitee.id_) if i.id_ != original["id"]
    ]
    assert replacement.published is not None
    assert replacement.end_time is not None
    assert replacement.end_time - replacement.published == window


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


def _send_stub_invite_during_revision(
    actor_store,
) -> tuple[Any, Any, Any, VulnerabilityCase, str, dict[str, Any]]:
    """Send a stub Invite while a revision of the embargo in force is open.

    Returns ``(owner, invitee, dl, case, revision_id, invite)`` with *case* the
    CASE_MANAGER's stored copy, in EM ``REVISE``.
    """
    owner, dl = actor_store("Vendor Owner")
    finder, _ = actor_store("Finder")
    invitee, _ = actor_store("Vendor Two")
    dl.create(finder)
    dl.create(invitee)
    built, _, _ = _build_active_embargo_case(dl, owner.id_, finder.id_)
    case = dl.read_case(built.id_)
    assert case is not None
    revision = as_EmbargoEvent(
        context=case.id_, end_time=days_from_now_utc(90)
    )
    dl.create(revision)
    propose(case, revision.id_)
    dl.save(case)
    write_consent_rows(dl, case)
    assert case.em_state == EM.REVISE
    in_force = case.active_embargo_id

    invite = _send_stub_invite(dl, owner.id_, case.id_, invitee.id_)

    # The stub carries the embargo in force, not the open revision (CM-17-002).
    assert invite["target"]["activeEmbargo"]["id"] == in_force
    stored = dl.read_case(case.id_)
    assert stored is not None
    return owner, invitee, dl, stored, revision.id_, invite


def _run_reissue(dl: Any, case_id: str, owner_id: str) -> Any:
    """Run the CASE_MANAGER's re-issue node once; return the BT result."""
    from vultron.core.behaviors.bridge import BTBridge
    from vultron.core.behaviors.case.nodes.stub_reissue import (
        ReissueStubInvitesNode,
    )

    return BTBridge(
        datalayer=dl,
        trigger_activity=TriggerActivityAdapter(dl),
        sync_port=SyncActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute_with_setup(
        tree=ReissueStubInvitesNode(case_id=case_id), actor_id=owner_id
    )


@pytest.mark.spec("CM-11-016")
@pytest.mark.spec("CM-17-002")
def test_a_rejected_revision_does_not_reissue_a_stub_sent_in_revise(
    actor_store,
) -> None:
    """Rejecting the revision leaves the stub's terms in force.

    A stub sent in EM REVISE already carried the embargo in force, so when the
    owner rejects the revision nothing it carried changed: it is not stale and
    is not re-issued (CM-11-016).
    """
    owner, invitee, dl, case, revision_id, invite = (
        _send_stub_invite_during_revision(actor_store)
    )

    reject(case, revision_id)
    dl.save(case)
    assert case.em_state == EM.ACTIVE

    assert outstanding_stale_stubs(dl, case, owner.id_, now_utc()) == []
    assert _run_reissue(dl, case.id_, owner.id_).status.name == "SUCCESS"
    assert [i.id_ for i in _invites_to(dl, invitee.id_)] == [invite["id"]]


@pytest.mark.spec("CM-11-016")
@pytest.mark.spec("CM-17-002")
def test_an_activated_revision_reissues_a_stub_sent_in_revise(
    actor_store,
) -> None:
    """Activating the revision changes the embargo in force: re-issue the stub.

    The replacement names the stub it supersedes and carries the revision,
    now the embargo in force (CM-11-016).
    """
    owner, invitee, dl, case, revision_id, invite = (
        _send_stub_invite_during_revision(actor_store)
    )

    activate(case, revision_id)
    dl.save(case)
    assert case.em_state == EM.ACTIVE
    assert case.active_embargo_id == revision_id

    (stale,) = outstanding_stale_stubs(dl, case, owner.id_, now_utc())
    assert stale.invite_id == invite["id"]
    assert _run_reissue(dl, case.id_, owner.id_).status.name == "SUCCESS"
    (replacement,) = [
        i for i in _invites_to(dl, invitee.id_) if i.id_ != invite["id"]
    ]
    assert replacement.in_reply_to == invite["id"]
    carried = getattr(replacement.target, "active_embargo", None)
    assert getattr(carried, "id_", carried) == revision_id


@pytest.mark.spec("CM-11-016")
@pytest.mark.spec("OX-06-002")
def test_a_replacement_left_unrecorded_is_recorded_during_a_later_revision(
    actor_store,
) -> None:
    """A replacement whose commit failed is recorded by a run in EM REVISE.

    The replacement invites to the embargo in force; a revision opened before
    the next run leaves that embargo in force (EP-05-002), so the run records
    the replacement once, still carrying it (CM-11-016, CM-17-002).
    """
    from test.support.ledger import fail_commits
    from vultron.core.behaviors.sync import commit_tree
    from vultron.core.models.case_ledger_entry import CaseLedgerEntry

    owner, invitee, dl, case, revision_id, invite = (
        _send_stub_invite_during_revision(actor_store)
    )
    activate(case, revision_id)
    dl.save(case)
    with pytest.MonkeyPatch.context() as mp:
        failed = fail_commits(
            mp,
            commit_tree,
            when=lambda kw: kw["event_type"] == "invite_actor_to_case",
        )
        result = _run_reissue(dl, case.id_, owner.id_)
    assert result.internal_error, result
    (replacement_id,) = failed

    stored = dl.read_case(case.id_)
    assert stored is not None
    later = as_EmbargoEvent(context=case.id_, end_time=days_from_now_utc(120))
    dl.create(later)
    propose(stored, later.id_)
    dl.save(stored)
    write_consent_rows(dl, stored)
    assert stored.em_state == EM.REVISE
    assert stored.active_embargo_id == revision_id

    assert _run_reissue(dl, case.id_, owner.id_).status.name == "SUCCESS"

    recorded = [
        e.log_object_id
        for e in dl.list_objects("CaseLedgerEntry")
        if isinstance(e, CaseLedgerEntry) and e.log_object_id == replacement_id
    ]
    assert recorded == [replacement_id]
    assert dl.outbox_list().count(replacement_id) == 1
    (replacement,) = [
        i for i in _invites_to(dl, invitee.id_) if i.id_ != invite["id"]
    ]
    assert replacement.id_ == replacement_id
    carried = getattr(replacement.target, "active_embargo", None)
    assert getattr(carried, "id_", carried) == revision_id
    # The replacement invites to the embargo in force (CM-11-016, CM-28-013).
    row = _participant_of(dl, case.id_, invitee.id_).held_row(revision_id)
    assert row is not None
    assert row.state is EmbargoConsentState.INVITED
    assert row.rsvp_deadline == replacement.end_time


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
    in_reply_to: str | None = None,
    end_time: datetime | None = None,
) -> RecordedStubInvite:
    return RecordedStubInvite(
        invite_id=invite_id,
        invitee_id="https://example.org/actors/v",
        case_id="https://example.org/cases/c",
        published=now_utc().replace(year=2026, month=1, day=1)
        + timedelta(minutes=minutes),
        end_time=end_time,
        in_reply_to=in_reply_to,
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
        b = _stub("b", minutes=1, in_reply_to="a")
        assert replacement_for(a, [a, b]) == b
        assert replacement_for(b, [a, b]) is None

    def test_an_older_stub_left_live_by_a_reinvite_is_superseded_too(
        self,
    ) -> None:
        a = _stub("a", minutes=0)
        b = _stub("b", minutes=1)  # re-invite: names nothing
        c = _stub("c", minutes=2, in_reply_to="b")  # embargo change
        assert replacement_for(a, [a, b, c]) == c
        assert replacement_for(b, [a, b, c]) == c

    def test_the_newest_replacement_wins(self) -> None:
        a = _stub("a", minutes=0)
        b = _stub("b", minutes=1, in_reply_to="a")
        c = _stub("c", minutes=2, in_reply_to="b")
        assert replacement_for(a, [a, b, c]) == c


class TestExpired:
    def test_no_deadline_never_expires(self) -> None:
        assert not stub_invite_expired(_stub("a", minutes=0), now_utc())

    def test_deadline_is_expired_at_the_instant_it_arrives(self) -> None:
        deadline = now_utc()
        stub = _stub("a", minutes=0, end_time=deadline)
        assert stub_invite_expired(stub, deadline)
        assert not stub_invite_expired(stub, deadline - timedelta(seconds=1))


@pytest.mark.spec("CM-11-016")
@pytest.mark.spec("CLP-10-025")
def test_the_end_time_decision_commits_the_reissued_stub_invite_last(
    actor_store,
) -> None:
    """The end-time clock decision commits one CASE_MANAGER entry per AS2
    activity: the ``Remove``, the ``Add(CaseStatus)``, then the stub
    ``Invite`` re-issued with the ended embargo's terms gone."""
    owner, dl = actor_store("Vendor Owner")
    finder, _ = actor_store("Finder")
    invitee, _ = actor_store("Vendor Two")
    dl.create(finder)
    dl.create(invitee)
    case, _, _ = _build_active_embargo_case(dl, owner.id_, finder.id_)
    original = _send_stub_invite(dl, owner.id_, case.id_, invitee.id_)
    # The embargo's end time passes while the stub is still outstanding.
    case = dl.read_case(case.id_)
    assert case is not None and case.active_embargo_id is not None
    embargo = dl.read(case.active_embargo_id)
    assert isinstance(embargo, as_EmbargoEvent)
    dl.save(embargo.model_copy(update={"end_time": now_utc()}))
    before = {e.id_ for e in ledger_entries(dl, case.id_)}

    run_end_time_check(dl, case.id_, owner.id_)

    added = [e for e in ledger_entries(dl, case.id_) if e.id_ not in before]
    assert [e.payload_snapshot["type"] for e in added] == [
        "Remove",
        "Add",
        "Invite",
    ]
    assert all(e.payload_snapshot["actor"] == owner.id_ for e in added)
    assert added[-1].payload_snapshot["inReplyTo"] == original["id"]
