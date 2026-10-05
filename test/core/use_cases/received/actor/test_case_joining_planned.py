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
"""Planned CASE_MANAGER handling of stub- and full-case-Invite replies.

Strict-``xfail`` tests for the case-joining requirements of ADR-0114 and
ADR-0070, planned under #4006; each test names the issue that implements
it.  Every test starts where CM-11-006 leaves the
case: the invitee already holds an *inert* participant record at RM
``RECEIVED`` (VF ``v`` for a vendor), created when the stub Invite was sent.

- CM-11-007 — ``Reject`` of the stub Invite closes and keeps the record.
- CM-11-008 — ``Accept`` of the stub Invite seeds the case, then replays.
- CM-11-009 — any stub reply from a vendor sets VF ``V``.
- CM-11-010 — the CASE_MANAGER follows up with the full-case Invite.
- CM-11-003 — a stub-Invite reply resolves the case the stub names
  (passing: implemented by #4045).
- CM-11-011 — the three full-case replies are R → V, R → I and R → C.
- CM-11-012 — a full-case reply is checked against the Invite's floor.
- CM-11-002, CM-11-004 — ``Join``/``Ignore`` engage or defer; joining alone
  is not RM.ACCEPTED (passing markers: already true today).
- RMB-14-005 — ``Leave`` from RM.VALID is recorded as V → D → C
  (passing: implemented by #4044).

Replies are routed the way the inbox routes them — semantic extraction then
``use_case_map()`` — so a test keeps working when the implementation adds new
semantics for a message.  See ``notes/case-joining.md``.
"""

import inspect
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock

import pytest

from test.core.use_cases.received.actor.test_invite import (
    _add_participant_result,
    _seed_ledger_entry,
)
from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import RmDimension, VfDimension
from vultron.core.models.participant_status import (
    ParticipantStatus,
    participant_status_rm_state,
    participant_status_vf_state,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.states.cs import CS_vf
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.semantic_registry import (
    extract_event,
    find_matching_semantics,
    use_case_map,
)
from vultron.wire.as2.factories import (
    rm_accept_invite_to_case_activity,
    rm_invite_to_case_activity,
    rm_reject_invite_to_case_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Invite,
)
from vultron.wire.as2.vocab.base.objects.actors import (
    as_Organization,
    as_Service,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)


@dataclass
class _JoiningCase:
    """A CASE_MANAGER store holding a case and one inert, invited vendor."""

    dl: SqliteDataLayer
    case: as_VulnerabilityCase
    case_actor_id: str
    invitee_id: str
    stub_invite: as_Invite
    sync_port: MagicMock = field(default_factory=MagicMock)
    trigger_activity: MagicMock = field(default_factory=MagicMock)

    def participant(self) -> CaseParticipant:
        case = self.dl.read(self.case.id_)
        assert isinstance(case, as_VulnerabilityCase)
        participant_id = case.actor_participant_index.get(self.invitee_id)
        assert participant_id is not None, (
            "the invitee's participant record must be kept"
        )
        participant = self.dl.read(participant_id)
        assert isinstance(participant, CaseParticipant)
        return participant

    def route(self, activity: as_Activity) -> HandlerResult:
        """Dispatch *activity* to the CASE_MANAGER as the inbox would."""
        return route_received(
            self.dl,
            activity,
            receiving_actor_id=self.case_actor_id,
            sync_port=self.sync_port,
            trigger_activity=self.trigger_activity,
        )


def route_received(
    dl: SqliteDataLayer,
    activity: as_Activity,
    *,
    receiving_actor_id: str,
    sync_port: Any = None,
    trigger_activity: Any = None,
) -> HandlerResult:
    """Route *activity* as the inbox does: match semantics, run its use case.

    Looks the use case up by matched semantics through ``use_case_map()``, so a
    caller keeps working when the implementation adds a new message type.
    Ports a use case does not declare are not passed.
    """
    event = extract_event(activity).model_copy(
        update={"receiving_actor_id": receiving_actor_id}
    )
    use_case_class = use_case_map()[find_matching_semantics(activity)]
    ports: dict[str, Any] = {
        "sync_port": sync_port if sync_port is not None else MagicMock(),
        "trigger_activity": trigger_activity,
        "wire_render_port": As2WireRenderAdapter(),
    }
    accepted = inspect.signature(use_case_class).parameters
    result = use_case_class(
        dl, event, **{k: v for k, v in ports.items() if k in accepted}
    ).execute()
    assert isinstance(result, HandlerResult)
    return result


@pytest.fixture
def joining_case() -> Any:
    """Seed the CASE_MANAGER's store as CM-11-006 leaves it.

    The case has a two-entry ledger, the CASE_MANAGER participant, and an
    inert VENDOR participant for the invitee at RM ``RECEIVED`` / VF ``v``,
    plus the stub Invite the CASE_MANAGER sent it.
    """
    case_actor_id = "https://example.org/actors/case-actor-join"
    invitee_id = "https://example.org/actors/vendor-join"
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=case_actor_id)
    case = as_VulnerabilityCase(
        id_="https://example.org/cases/case-join-1",
        name="CASE-JOINING",
        stub_summary="Case for joining test",
        attributed_to=case_actor_id,
    )
    invitee = as_Organization(id_=invitee_id)
    dl.create(invitee)
    dl.create(as_Service(id_=case_actor_id, context=case.id_))
    seed_case_manager_participant(dl, case, case_actor_id)

    inert = CaseParticipant(
        id_=f"{case.id_}/participants/vendor-join",
        attributed_to=invitee_id,
        context=case.id_,
        case_roles=[CVDRole.VENDOR],
        participant_statuses=[
            ParticipantStatus(
                context=case.id_,
                attributed_to=invitee_id,
                rm=RmDimension(state=RM.RECEIVED),
                vf=VfDimension(state=CS_vf.vf),
                cvd_role=[CVDRole.VENDOR],
            )
        ],
    )
    dl.create(inert)
    case.case_participants.append(inert.id_)
    case.actor_participant_index[invitee_id] = inert.id_
    dl.create(case)

    stub_invite = rm_invite_to_case_activity(
        invitee,
        target=case,
        actor=case_actor_id,
        roles=[CVDRole.VENDOR],
        id_=f"{case.id_}/invitations/stub-1",
    )
    dl.create(stub_invite)
    for index, event_type in enumerate(
        ("submit_report", "add_participant_status")
    ):
        _seed_ledger_entry(
            dl,
            case_id=case.id_,
            object_id=f"{case.id_}/events/{index}",
            event_type=event_type,
            actor_id=case_actor_id,
            payload_snapshot={"index": index},
        )

    joining = _JoiningCase(
        dl=dl,
        case=case,
        case_actor_id=case_actor_id,
        invitee_id=invitee_id,
        stub_invite=stub_invite,
    )
    joining.trigger_activity.announce_vulnerability_case.return_value = (
        f"{case.id_}/announce/1"
    )
    joining.trigger_activity.add_participant_to_case.return_value = (
        _add_participant_result(case, case_actor_id, invitee_id)
    )
    yield joining
    dl.close()


@pytest.mark.xfail(
    strict=True,
    reason=(
        "CM-11-007: Reject of a stub Invite moves the kept participant"
        " record to RM CLOSED. Tracked by #4048."
    ),
)
@pytest.mark.spec("CM-11-007")
def test_stub_invite_reject_closes_and_keeps_the_record(joining_case) -> None:
    """A hard no to joining is ``R → C`` on the record the Invite created.

    The record stays (it is the history that the actor was told and
    declined) and stays inert.  Today the Reject only commits a ledger entry
    and leaves the participant at ``RECEIVED``.
    """
    result = joining_case.route(
        rm_reject_invite_to_case_activity(
            joining_case.stub_invite, actor=joining_case.invitee_id
        )
    )

    assert result.disposition is HandlerDisposition.APPLIED
    latest = joining_case.participant().participant_statuses[-1]
    assert participant_status_rm_state(latest) == RM.CLOSED


@pytest.mark.xfail(
    strict=True,
    reason=(
        "CM-11-009: any stub-Invite reply from a VENDOR invitee sets VF V."
        " Tracked by #4048."
    ),
)
@pytest.mark.spec("CM-11-009")
@pytest.mark.parametrize("reply", ["accept", "reject"])
def test_stub_invite_reply_marks_vendor_aware(joining_case, reply) -> None:
    """Replying to the stub Invite is evidence the vendor knows of the case."""
    build = {
        "accept": rm_accept_invite_to_case_activity,
        "reject": rm_reject_invite_to_case_activity,
    }[reply]
    joining_case.route(
        build(joining_case.stub_invite, actor=joining_case.invitee_id)
    )

    latest = joining_case.participant().participant_statuses[-1]
    assert participant_status_vf_state(latest) in {CS_vf.Vf, CS_vf.VF}


@pytest.mark.xfail(
    strict=True,
    reason=(
        "CM-11-008: accepting the stub Invite seeds the case with"
        " Announce(VulnerabilityCase) before any ledger entry reaches the"
        " participant. Tracked by #4050."
    ),
)
@pytest.mark.spec("CM-11-008")
def test_stub_invite_accept_seeds_case_then_replays_ledger(
    joining_case,
) -> None:
    """The Accept is the readiness signal: Announce the case, then replay.

    The invitee's record already exists (CM-11-006), so the Accept is what
    makes it active.  The CASE_MANAGER must send ``Announce(VulnerabilityCase)``
    exactly once and only then replay the whole ledger to it.  Today, with a
    pre-existing record, the commit fan-out reaches the still-inert invitee
    before (and instead of) the case seed.
    """
    manager = MagicMock()
    manager.attach_mock(joining_case.trigger_activity, "trigger")
    manager.attach_mock(joining_case.sync_port, "sync")

    joining_case.route(
        rm_accept_invite_to_case_activity(
            joining_case.stub_invite, actor=joining_case.invitee_id
        )
    )

    invitee_id = joining_case.invitee_id
    ordered = [
        name
        for name, _args, kwargs in manager.mock_calls
        if name == "trigger.announce_vulnerability_case"
        or (
            name == "sync.send_announce_log_entry"
            and invitee_id in kwargs.get("to", [])
        )
    ]
    assert ordered, "nothing reached the invitee"
    assert ordered[0] == "trigger.announce_vulnerability_case", ordered
    assert ordered.count("trigger.announce_vulnerability_case") == 1
    replayed = [
        kwargs["entry"].log_index
        for _, kwargs in joining_case.sync_port.send_announce_log_entry.call_args_list
        if invitee_id in kwargs.get("to", [])
    ]
    assert {0, 1} <= set(replayed), replayed


def _full_case_invites_to(joining: _JoiningCase) -> list[str]:
    """Every full-case Invite to the invitee the CASE_MANAGER produced.

    Looks in both places an outbound Invite can surface: the store (where
    the real trigger adapter persists it) and the trigger port (mocked here).
    """
    found: list[str] = []
    for obj in joining.dl.list_objects("Invite"):
        if (
            not isinstance(obj, as_Invite)
            or obj.id_ == joining.stub_invite.id_
        ):
            continue
        target = obj.target
        target_type = getattr(target, "type_", None)
        invitee = getattr(obj.object_, "id_", obj.object_)
        if (
            invitee == joining.invitee_id
            and str(getattr(target_type, "value", target_type))
            == "VulnerabilityCase"
            and getattr(target, "id_", target) == joining.case.id_
        ):
            found.append(obj.id_)
    for name, args, kwargs in joining.trigger_activity.mock_calls:
        if "invite" in name.lower() and joining.invitee_id in (
            list(args) + list(kwargs.values())
        ):
            found.append(f"trigger.{name}")
    return found


@pytest.mark.xfail(
    strict=True,
    reason=(
        "CM-11-010: after the stub Accept the CASE_MANAGER sends the"
        " full-case Invite(Actor, VulnerabilityCase). Tracked by #4050."
    ),
)
@pytest.mark.spec("CM-11-010")
def test_stub_invite_accept_is_followed_by_full_case_invite(
    joining_case,
) -> None:
    """The full-case Invite asks the question the stub Accept did not.

    Today the CASE_MANAGER sends no second Invite: the participant is left at
    RM ``RECEIVED`` with nothing to reply to.
    """
    joining_case.route(
        rm_accept_invite_to_case_activity(
            joining_case.stub_invite, actor=joining_case.invitee_id
        )
    )

    assert _full_case_invites_to(joining_case), (
        "no Invite(Actor, VulnerabilityCase) was sent to the participant"
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "CM-11-012: a full-case Invite reply that carries no ledger"
        " position at or beyond the Invite's is refused. Tracked by #4050."
    ),
)
@pytest.mark.spec("CM-11-012")
def test_full_case_invite_reply_without_floor_position_is_refused(
    joining_case,
) -> None:
    """A reply that does not show it reached the Invite's floor is refused.

    The full-case Invite carries the CASE_MANAGER's ledger tail; a reply
    must carry the replier's own position at or beyond it (CM-11-011).  An
    ``Accept`` carrying no position at all is behind every floor, so the
    CASE_MANAGER refuses it and the participant's RM state does not move.
    Today no pattern recognises the full-case Accept, so it cannot be judged.
    """
    full_invite = as_Invite(
        id_=f"{joining_case.case.id_}/invitations/full-1",
        actor=joining_case.case_actor_id,
        object_=as_Organization(id_=joining_case.invitee_id),
        target=joining_case.case,
        to=[joining_case.invitee_id],
    )
    joining_case.dl.create(full_invite)

    result = _route_full_case_reply(
        joining_case,
        as_Accept(
            actor=joining_case.invitee_id,
            object_=full_invite,
            in_reply_to=full_invite.id_,
        ),
    )

    assert result.disposition is HandlerDisposition.REFUSED
    latest = joining_case.participant().participant_statuses[-1]
    assert participant_status_rm_state(latest) == RM.RECEIVED


def _ledger_tail(joining: _JoiningCase) -> list[Any]:
    """The CASE_MANAGER's ledger entries for the case, in ``log_index`` order."""
    from vultron.core.models.case_ledger_entry import CaseLedgerEntry

    return sorted(
        (
            entry
            for entry in joining.dl.list_objects("CaseLedgerEntry")
            if isinstance(entry, CaseLedgerEntry)
            and entry.case_id == joining.case.id_
        ),
        key=lambda entry: entry.log_index,
    )


def _position(log_index: int, entry_hash: str) -> dict[str, Any]:
    """The wire fields carrying a ledger position (CM-11-010, CM-11-011).

    The implementation fixes their names; ``log_index``/``entry_hash`` are the
    names the requirements use.  This is the one place that spells them.
    """
    return {"log_index": log_index, "entry_hash": entry_hash}


def _full_case_invite_at(
    joining: _JoiningCase, *, log_index: int, entry_hash: str
) -> as_Invite:
    """Store a full-case Invite whose ledger-position floor is the given entry."""
    invite = as_Invite(
        id_=f"{joining.case.id_}/invitations/full-floor-{log_index}",
        actor=joining.case_actor_id,
        object_=as_Organization(id_=joining.invitee_id),
        target=joining.case,
        to=[joining.invitee_id],
        **_position(log_index, entry_hash),
    )
    joining.dl.create(invite)
    return invite


def _full_case_reply_at(
    kind: str, joining: _JoiningCase, invite: as_Invite, *, position: Any
) -> as_Activity:
    """A reply to *invite* carrying the replier's ledger position (CM-11-011)."""
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Reject,
        as_TentativeReject,
    )

    reply_class = {
        "accept": as_Accept,
        "tentative_reject": as_TentativeReject,
        "reject": as_Reject,
    }[kind]
    return reply_class(
        actor=joining.invitee_id,
        object_=invite,
        in_reply_to=invite.id_,
        **_position(position.log_index, position.entry_hash),
    )


def _route_full_case_reply(
    joining: _JoiningCase, activity: as_Activity
) -> HandlerResult:
    """Route a full-case reply, failing first if no pattern recognises it.

    A reply no pattern matches is refused as unroutable, which would satisfy
    a "refused" assertion for the wrong reason: since #4045 the stub-Invite
    patterns no longer match a full-case reply, and no full-case pattern
    exists until #4050.
    """
    semantics = find_matching_semantics(activity)
    assert semantics.name not in {"UNKNOWN", "UNKNOWN_UNRESOLVABLE_OBJECT"}, (
        "the full-case Invite reply matches no pattern"
    )
    return joining.route(activity)


def _rm_history(joining: _JoiningCase) -> list[RM]:
    return [
        participant_status_rm_state(status)
        for status in joining.participant().participant_statuses
    ]


@pytest.mark.xfail(
    strict=True,
    reason=(
        "CM-11-011: the CASE_MANAGER records RV/RI/RC replies to the full-case"
        " Invite as R → V / R → I / R → C. Tracked by #4050."
    ),
)
@pytest.mark.spec("CM-11-011")
@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        ("accept", RM.VALID),
        ("tentative_reject", RM.INVALID),
        ("reject", RM.CLOSED),
    ],
)
def test_full_case_invite_reply_moves_rm_from_received(
    joining_case, reply: str, expected: RM
) -> None:
    """Each full-case reply at the Invite's floor is one RM transition.

    Today none of the three matches a pattern: the stub-Invite patterns
    recognise only a ``VulnerabilityCaseStub`` target (#4045).
    """
    tail = _ledger_tail(joining_case)[-1]
    invite = _full_case_invite_at(
        joining_case, log_index=tail.log_index, entry_hash=tail.entry_hash
    )
    activity = _full_case_reply_at(reply, joining_case, invite, position=tail)
    semantics = find_matching_semantics(activity)
    assert semantics.name not in {"UNKNOWN", "UNKNOWN_UNRESOLVABLE_OBJECT"}, (
        f"{reply} of the full-case Invite matches no pattern"
    )

    result = joining_case.route(activity)

    assert result.disposition is HandlerDisposition.APPLIED, result.reason
    assert _rm_history(joining_case)[-2:] == [RM.RECEIVED, expected]


@pytest.mark.xfail(
    strict=True,
    reason=(
        "CM-11-012: a full-case Invite reply behind the floor, or naming an"
        " entry the ledger does not hold, is refused; one beyond the floor is"
        " accepted. Tracked by #4050."
    ),
)
@pytest.mark.spec("CM-11-012")
@pytest.mark.parametrize(
    ("floor", "reply_at", "forge_hash", "refused"),
    [
        (1, 0, False, True),
        (1, 1, True, True),
        (0, 1, False, False),
    ],
    ids=["behind-the-floor", "unknown-entry", "beyond-the-floor"],
)
def test_full_case_invite_reply_position_is_checked_against_the_floor(
    joining_case, floor: int, reply_at: int, forge_hash: bool, refused: bool
) -> None:
    """The Invite's position is a floor, not a pin (ADR-0070).

    A reply behind it is refused, as is one naming a hash the CASE_MANAGER's
    ledger does not hold at that index; a reply beyond it is better informed
    and accepted (RM ``RECEIVED → VALID``).  Today no pattern recognises the
    full-case Accept, so its position is never judged.
    """
    entries = _ledger_tail(joining_case)
    assert [e.log_index for e in entries][:2] == [0, 1]
    invite = _full_case_invite_at(
        joining_case,
        log_index=entries[floor].log_index,
        entry_hash=entries[floor].entry_hash,
    )
    position = entries[reply_at]
    if forge_hash:
        position = position.model_copy(update={"entry_hash": "0" * 64})

    result = _route_full_case_reply(
        joining_case,
        _full_case_reply_at("accept", joining_case, invite, position=position),
    )

    if refused:
        assert result.disposition is HandlerDisposition.REFUSED
        assert _rm_history(joining_case)[-1] == RM.RECEIVED
    else:
        assert result.disposition is HandlerDisposition.APPLIED, result.reason
        assert _rm_history(joining_case)[-1] == RM.VALID


@pytest.mark.spec("CM-11-003")
def test_stub_invite_reply_resolves_case_from_the_case_the_stub_names(
    joining_case,
) -> None:
    """The stub has its own ID (CM-11-013), so the case cannot come from it.

    The reply's top-level ``target`` is unset; the case is the one the nested
    Invite's stub names in its ``caseId``.  The stub carries its own ID
    (``<case-id>/stub``, #4045), so "derive the case from the stub's ID" and
    "resolve the named case" are told apart.
    """
    accept = rm_accept_invite_to_case_activity(
        joining_case.stub_invite, actor=joining_case.invitee_id
    )
    stub = joining_case.stub_invite.target
    assert accept.target is None

    assert getattr(stub, "id_", stub) != joining_case.case.id_, (
        "the stub must carry its own ID for this requirement to be observable"
    )
    assert getattr(extract_event(accept), "case_id", None) == (
        joining_case.case.id_
    )
    result = joining_case.route(accept)
    assert result.disposition is HandlerDisposition.APPLIED, result.reason


def _advance_invitee_to(joining: _JoiningCase, state: RM) -> None:
    """Record *state* on the invitee's participant, as a full-case reply would."""
    participant = joining.participant()
    participant.participant_statuses.append(
        ParticipantStatus(
            context=joining.case.id_,
            attributed_to=joining.invitee_id,
            rm=RmDimension(state=state),
            vf=VfDimension(state=CS_vf.Vf),
            cvd_role=[CVDRole.VENDOR],
        )
    )
    joining.dl.save(participant)


@pytest.mark.spec("CM-11-004")
def test_joined_participant_is_not_accepted_until_it_sends_join(
    joining_case,
) -> None:
    """Joining is not committing: only ``Join(VulnerabilityCase)`` is RM.ACCEPTED.

    The stub Accept leaves the record at ``RECEIVED``; once the participant
    has judged the case valid, its ``Join`` moves it to ``ACCEPTED``.
    """
    from vultron.wire.as2.factories import rm_engage_case_activity

    joining_case.route(
        rm_accept_invite_to_case_activity(
            joining_case.stub_invite, actor=joining_case.invitee_id
        )
    )
    assert RM.ACCEPTED not in _rm_history(joining_case)

    _advance_invitee_to(joining_case, RM.VALID)
    result = joining_case.route(
        rm_engage_case_activity(
            joining_case.case, actor=joining_case.invitee_id
        )
    )

    assert result.disposition is HandlerDisposition.APPLIED, result.reason
    assert _rm_history(joining_case)[-1] == RM.ACCEPTED


@pytest.mark.spec("CM-11-002")
@pytest.mark.parametrize(
    ("decision", "expected"),
    [("join", RM.ACCEPTED), ("ignore", RM.DEFERRED)],
)
def test_valid_participant_engages_or_defers_with_join_or_ignore(
    joining_case, decision: str, expected: RM
) -> None:
    """After judging the case valid, ``Join`` engages and ``Ignore`` defers."""
    from vultron.wire.as2.factories import (
        rm_defer_case_activity,
        rm_engage_case_activity,
    )

    build = {"join": rm_engage_case_activity, "ignore": rm_defer_case_activity}
    _advance_invitee_to(joining_case, RM.VALID)

    result = joining_case.route(
        build[decision](joining_case.case, actor=joining_case.invitee_id)
    )

    assert result.disposition is HandlerDisposition.APPLIED, result.reason
    assert _rm_history(joining_case)[-2:] == [RM.VALID, expected]


@pytest.mark.spec("RMB-14-005")
def test_leave_from_valid_is_recorded_through_deferred(joining_case) -> None:
    """``V → C`` is not in the RM table, so Leave from VALID passes through D."""
    from vultron.wire.as2.factories import rm_close_case_activity

    _advance_invitee_to(joining_case, RM.VALID)

    result = joining_case.route(
        rm_close_case_activity(
            joining_case.case, actor=joining_case.invitee_id
        )
    )

    assert result.disposition is HandlerDisposition.APPLIED, result.reason
    assert _rm_history(joining_case)[-3:] == [
        RM.VALID,
        RM.DEFERRED,
        RM.CLOSED,
    ]
