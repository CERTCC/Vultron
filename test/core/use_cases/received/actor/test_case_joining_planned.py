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
ADR-0070, tracked by #4006.  Every test starts where CM-11-006 leaves the
case: the invitee already holds an *inert* participant record at RM
``RECEIVED`` (VF ``v`` for a vendor), created when the stub Invite was sent.

- CM-11-007 — ``Reject`` of the stub Invite closes and keeps the record.
- CM-11-008 — ``Accept`` of the stub Invite seeds the case, then replays.
- CM-11-009 — any stub reply from a vendor sets VF ``V``.
- CM-11-010 — the CASE_MANAGER follows up with the full-case Invite.
- CM-11-012 — a full-case reply without the floor position is refused.

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

_REASON_SUFFIX = "Tracked by #4006."


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
        f" record to RM CLOSED. {_REASON_SUFFIX}"
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
        f" {_REASON_SUFFIX}"
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
        f" participant. {_REASON_SUFFIX}"
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
        f" full-case Invite(Actor, VulnerabilityCase). {_REASON_SUFFIX}"
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
        f" position at or beyond the Invite's is refused. {_REASON_SUFFIX}"
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
    Today the Accept is handled as a stub-Invite Accept and is not refused.
    """
    full_invite = as_Invite(
        id_=f"{joining_case.case.id_}/invitations/full-1",
        actor=joining_case.case_actor_id,
        object_=as_Organization(id_=joining_case.invitee_id),
        target=joining_case.case,
        to=[joining_case.invitee_id],
    )
    joining_case.dl.create(full_invite)

    result = joining_case.route(
        as_Accept(
            actor=joining_case.invitee_id,
            object_=full_invite,
            in_reply_to=full_invite.id_,
        )
    )

    assert result.disposition is HandlerDisposition.REFUSED
    latest = joining_case.participant().participant_statuses[-1]
    assert participant_status_rm_state(latest) == RM.RECEIVED
