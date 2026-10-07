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
"""The full-case Invite: emission order, position content, and the floor check.

Builds on the ``joining_case`` fixture (CM-11-006 state) of
``test_case_joining_planned``; see ``notes/case-joining.md``.
"""

import json
from unittest.mock import MagicMock

import pytest

from test.core.use_cases.received.actor.test_case_joining_planned import (  # noqa: F401
    _full_case_invite_at,
    _full_case_reply_at,
    _ledger_tail,
    _rm_history,
    joining_case,
    route_received,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.events.actor import (
    InviteActorToFullCaseReceivedEvent,
)
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.models.pending_case_inbox import VultronPendingCaseInbox
from vultron.core.models.protocol_pair import (
    INVITE_ACTOR_TO_FULL_CASE_REPLY_TYPES,
)
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.rm import RM
from vultron.core.sync_helpers import (
    ledger_position_refusal,
    ledger_tail_position,
)
from vultron.errors import VultronWiringError  # noqa: F401
from vultron.semantic_registry import extract_event, find_matching_semantics
from vultron.wire.as2.errors import VultronParseValidationError
from vultron.wire.as2.factories import (
    ledger_position_content,
    rm_accept_invite_to_case_activity,
    rm_invite_to_full_case_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Accept
from vultron.wire.as2.vocab.base.objects.actors import as_Organization
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_HASH = "ab" * 32


@pytest.mark.spec("CM-11-010")
def test_stub_accept_sends_announce_then_replay_then_full_case_invite(
    joining_case,  # noqa: F811
) -> None:
    """Announce, then the ledger replay, then the Invite carrying the tail."""
    manager = MagicMock()
    manager.attach_mock(joining_case.trigger_activity, "trigger")
    manager.attach_mock(joining_case.sync_port, "sync")
    invitee_id = joining_case.invitee_id

    joining_case.route(
        rm_accept_invite_to_case_activity(
            joining_case.stub_invite, actor=invitee_id
        )
    )

    ordered = [
        (name, kwargs)
        for name, _args, kwargs in manager.mock_calls
        if name
        in {
            "trigger.announce_vulnerability_case",
            "trigger.invite_actor_to_full_case",
        }
        or (
            name == "sync.send_announce_log_entry"
            and invitee_id in kwargs.get("to", [])
        )
    ]
    names = [name for name, _ in ordered]
    assert names[0] == "trigger.announce_vulnerability_case", names
    assert names.count("trigger.invite_actor_to_full_case") == 1
    invite_at = names.index("trigger.invite_actor_to_full_case")
    # Everything replayed before the Invite is the history it follows; the one
    # send after it is the fan-out of the Invite's own ledger entry.
    assert names[:invite_at].count("sync.send_announce_log_entry") >= 2, names
    assert names[invite_at + 1 :] == ["sync.send_announce_log_entry"], names

    entries = _ledger_tail(joining_case)
    invite_entry = next(
        e for e in entries if e.event_type == "invite_actor_to_full_case"
    )
    floor_entry = entries[invite_entry.log_index - 1]
    invite_kwargs = ordered[invite_at][1]
    assert invite_kwargs["ledger_log_index"] == floor_entry.log_index
    assert invite_kwargs["ledger_entry_hash"] == floor_entry.entry_hash


@pytest.mark.spec("CM-11-010")
def test_a_resumed_join_does_not_send_a_second_full_case_invite(
    joining_case,  # noqa: F811
) -> None:
    accept = rm_accept_invite_to_case_activity(
        joining_case.stub_invite, actor=joining_case.invitee_id
    )
    joining_case.route(accept)
    joining_case.route(accept)

    assert (
        joining_case.trigger_activity.invite_actor_to_full_case.call_count == 1
    )


@pytest.mark.spec("CM-11-011")
def test_full_case_invite_and_reply_carry_the_position_json_in_content() -> (
    None
):
    """``content`` is the ``LedgerPosition`` model's own wire-alias JSON dump."""
    position = LedgerPosition(log_index=3, entry_hash=_HASH)
    invite = rm_invite_to_full_case_activity(
        as_Organization(id_="https://example.org/actors/a"),
        "https://example.org/cases/c",
        position,
        actor="https://example.org/actors/m",
    )

    content = invite.content
    assert isinstance(content, str)
    assert invite.target == "https://example.org/cases/c"
    assert json.loads(content) == {"logIndex": 3, "entryHash": _HASH}
    assert content == ledger_position_content(position)
    assert LedgerPosition.model_validate_json(content) == position
    event = extract_event(invite)
    assert isinstance(event, InviteActorToFullCaseReceivedEvent)
    assert event.ledger_tail == position


@pytest.mark.spec("CM-11-012")
def test_reply_position_check_against_the_floor(joining_case) -> None:  # noqa: F811
    entries = _ledger_tail(joining_case)
    dl = joining_case.dl
    case_id = joining_case.case.id_
    floor = LedgerPosition(
        log_index=entries[1].log_index, entry_hash=entries[1].entry_hash
    )

    def refusal(position: LedgerPosition):
        return ledger_position_refusal(
            case_id, dl, position=position, floor=floor
        )

    assert refusal(floor) is None
    assert refusal(ledger_tail_position(case_id, dl)) is None
    assert "behind" in (
        refusal(
            LedgerPosition(
                log_index=entries[0].log_index,
                entry_hash=entries[0].entry_hash,
            )
        )
        or ""
    )
    assert "does not hold" in (
        refusal(LedgerPosition(log_index=entries[1].log_index, entry_hash="x"))
        or ""
    )
    assert "does not hold" in (
        refusal(LedgerPosition(log_index=999, entry_hash=_HASH)) or ""
    )


@pytest.mark.spec("CLP-08-004")
def test_empty_ledger_position_is_minus_one_and_the_genesis_hash() -> None:
    owner = "https://example.org/actors/empty-ledger-owner"
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=owner)
    case = as_VulnerabilityCase(
        id_="https://example.org/cases/empty-ledger",
        name="EMPTY",
        attributed_to=owner,
    )
    dl.create(case)

    position = ledger_tail_position(case.id_, dl)

    assert position == LedgerPosition(
        log_index=-1, entry_hash=case.genesis_hash
    )
    assert (
        ledger_position_refusal(
            case.id_, dl, position=position, floor=position
        )
        is None
    )
    dl.close()


@pytest.mark.spec("CM-11-012")
def test_reply_from_an_actor_the_invite_did_not_ask_is_refused(
    joining_case,  # noqa: F811
) -> None:
    tail = _ledger_tail(joining_case)[-1]
    invite = _full_case_invite_at(
        joining_case, log_index=tail.log_index, entry_hash=tail.entry_hash
    )
    reply = _full_case_reply_at(
        "accept", joining_case, invite, position=tail
    ).model_copy(update={"actor": "https://example.org/actors/someone-else"})

    result = joining_case.route(reply)

    assert result.disposition is HandlerDisposition.REFUSED
    assert _rm_history(joining_case)[-1] == RM.RECEIVED


@pytest.mark.spec("CM-11-012")
@pytest.mark.parametrize("kind", ["accept", "tentative_reject", "reject"])
def test_a_reply_from_a_participant_that_has_not_joined_is_refused(
    joining_case,  # noqa: F811
    kind: str,
) -> None:
    """Only a joined participant judges the case; the refusal writes nothing."""
    tail = _ledger_tail(joining_case)[-1]
    invite = _full_case_invite_at(
        joining_case,
        log_index=tail.log_index,
        entry_hash=tail.entry_hash,
        joined=False,
    )
    assert joining_case.participant().joined is False
    entries_before = len(_ledger_tail(joining_case))

    result = joining_case.route(
        _full_case_reply_at(kind, joining_case, invite, position=tail)
    )

    assert result.disposition is HandlerDisposition.REFUSED
    assert "has not joined" in (result.reason or "")
    assert _rm_history(joining_case)[-1] == RM.RECEIVED
    assert len(_ledger_tail(joining_case)) == entries_before


@pytest.mark.spec("CM-11-012")
def test_a_refused_reply_writes_no_ledger_entry(joining_case) -> None:  # noqa: F811
    entries = _ledger_tail(joining_case)
    invite = _full_case_invite_at(
        joining_case,
        log_index=entries[1].log_index,
        entry_hash=entries[1].entry_hash,
    )
    before = len(_ledger_tail(joining_case))

    result = joining_case.route(
        _full_case_reply_at(
            "accept", joining_case, invite, position=entries[0]
        )
    )

    assert result.disposition is HandlerDisposition.REFUSED
    assert len(_ledger_tail(joining_case)) == before


@pytest.mark.spec("CM-11-011")
def test_a_reply_is_recorded_in_the_ledger_with_its_position(
    joining_case,  # noqa: F811
) -> None:
    tail = _ledger_tail(joining_case)[-1]
    invite = _full_case_invite_at(
        joining_case, log_index=tail.log_index, entry_hash=tail.entry_hash
    )
    joining_case.route(
        _full_case_reply_at("accept", joining_case, invite, position=tail)
    )

    recorded = [
        e
        for e in _ledger_tail(joining_case)
        if e.event_type == "accept_invite_actor_to_full_case"
    ]
    assert len(recorded) == 1
    assert (
        json.loads(recorded[0].payload_snapshot["content"])["logIndex"]
        == tail.log_index
    )


@pytest.mark.spec("CM-11-007")
def test_replies_to_the_full_case_invite_are_distinct_semantics(
    joining_case,  # noqa: F811
) -> None:
    tail = _ledger_tail(joining_case)[-1]
    invite = _full_case_invite_at(
        joining_case, log_index=tail.log_index, entry_hash=tail.entry_hash
    )
    names = {
        find_matching_semantics(
            _full_case_reply_at(kind, joining_case, invite, position=tail)
        ).name.lower()
        for kind in ("accept", "tentative_reject", "reject")
    }
    assert names == INVITE_ACTOR_TO_FULL_CASE_REPLY_TYPES


@pytest.mark.spec("VAM-04-012")
def test_a_reply_with_unparseable_content_is_refused_at_the_edge(
    joining_case,  # noqa: F811
) -> None:
    tail = _ledger_tail(joining_case)[-1]
    invite = _full_case_invite_at(
        joining_case, log_index=tail.log_index, entry_hash=tail.entry_hash
    )
    reply = as_Accept(
        actor=joining_case.invitee_id, object_=invite, content="{}"
    )
    with pytest.raises(VultronParseValidationError, match="unparseable"):
        extract_event(reply)


@pytest.mark.spec("CM-11-011")
@pytest.mark.parametrize("second", ["accept", "reject"])
def test_a_second_reply_is_refused_and_writes_no_ledger_entry(
    joining_case,  # noqa: F811
    second: str,
) -> None:
    """A duplicate or contradictory reply is refused before any receipt."""
    tail = _ledger_tail(joining_case)[-1]
    invite = _full_case_invite_at(
        joining_case, log_index=tail.log_index, entry_hash=tail.entry_hash
    )
    first = joining_case.route(
        _full_case_reply_at("accept", joining_case, invite, position=tail)
    )
    assert first.disposition is not HandlerDisposition.REFUSED
    assert _rm_history(joining_case)[-1] == RM.VALID
    tail = _ledger_tail(joining_case)[-1]
    before = len(_ledger_tail(joining_case))

    result = joining_case.route(
        _full_case_reply_at(second, joining_case, invite, position=tail)
    )

    assert result.disposition is HandlerDisposition.REFUSED
    assert "cannot move" in (result.reason or "")
    assert _rm_history(joining_case)[-1] == RM.VALID
    assert len(_ledger_tail(joining_case)) == before


@pytest.mark.spec("CM-11-010")
def test_stored_invite_floor_is_none_for_unparseable_content() -> None:
    from vultron.core.behaviors.case.nodes.full_case_invite import (
        stored_invite_floor,
    )

    good = LedgerPosition(log_index=2, entry_hash=_HASH)
    assert (
        stored_invite_floor(MagicMock(content=ledger_position_content(good)))
        == good
    )
    for content in ("{}", "not json", "", "  ", None):
        assert stored_invite_floor(MagicMock(content=content)) is None


@pytest.mark.spec("CM-11-010")
def test_an_invite_for_another_case_or_invitee_does_not_suppress_the_invite(
    joining_case,  # noqa: F811
) -> None:
    """Once per participant per case: other Invites are not this one."""
    position = LedgerPosition(log_index=0, entry_hash=_HASH)
    other = "https://example.org/actors/someone-else"
    for n, (case_id, invitee) in enumerate(
        [
            (
                "https://example.org/cases/another-case",
                joining_case.invitee_id,
            ),
            (joining_case.case.id_, other),
        ]
    ):
        joining_case.dl.create(
            rm_invite_to_full_case_activity(
                as_Organization(id_=invitee),
                case_id,
                position,
                id_=f"https://example.org/invitations/unrelated-{n}",
                actor=joining_case.case_actor_id,
                to=[invitee],
            )
        )

    joining_case.route(
        rm_accept_invite_to_case_activity(
            joining_case.stub_invite, actor=joining_case.invitee_id
        )
    )

    assert (
        joining_case.trigger_activity.invite_actor_to_full_case.call_count == 1
    )


_INVITEE_STORE_ID = "https://example.org/actors/vendor-join"
_IMPOSTOR_ID = "https://example.org/actors/impostor"


def _full_case_invite_from(joining, sender: str, suffix: str):
    """A full-case Invite to the invitee, claiming to come from *sender*."""
    return rm_invite_to_full_case_activity(
        as_Organization(id_=joining.invitee_id),
        joining.case.id_,
        LedgerPosition(log_index=0, entry_hash=_HASH),
        id_=f"{joining.case.id_}/invitations/full-{suffix}",
        actor=sender,
        to=[joining.invitee_id],
    )


def _receive_as_invitee(dl, joining, invite):
    return route_received(dl, invite, receiving_actor_id=joining.invitee_id)


@pytest.fixture
def invitee_with_replica(joining_case):  # noqa: F811
    """The invitee's own store, holding the case replica the Announce seeded."""
    dl = SqliteDataLayer(
        "sqlite:///:memory:", actor_id=joining_case.invitee_id
    )
    case = joining_case.dl.read(joining_case.case.id_)
    for participant_id in case.actor_participant_index.values():
        dl.save(joining_case.dl.read(participant_id))
    dl.save(case)
    return dl


@pytest.mark.spec("CM-11-010")
@pytest.mark.spec("HP-01-006")
def test_a_full_case_invite_from_the_case_manager_is_accepted(
    joining_case,  # noqa: F811
    invitee_with_replica,
) -> None:
    """The case's CASE_MANAGER is the one sender the invitee accepts."""
    invite = _full_case_invite_from(
        joining_case, joining_case.case_actor_id, "cm"
    )

    result = _receive_as_invitee(invitee_with_replica, joining_case, invite)

    assert result.disposition is not HandlerDisposition.REFUSED


@pytest.mark.spec("CM-11-010")
@pytest.mark.spec("HP-01-006")
def test_a_full_case_invite_from_another_actor_is_refused_and_writes_nothing(
    joining_case,  # noqa: F811
    invitee_with_replica,
) -> None:
    """Any sender other than the CASE_MANAGER is refused past intake."""
    invite = _full_case_invite_from(joining_case, _IMPOSTOR_ID, "forged")
    case_before = invitee_with_replica.read(joining_case.case.id_)
    ledger_before = len(invitee_with_replica.list_objects("CaseLedgerEntry"))

    result = _receive_as_invitee(invitee_with_replica, joining_case, invite)

    assert result.disposition is HandlerDisposition.REFUSED
    assert (
        len(invitee_with_replica.list_objects("CaseLedgerEntry"))
        == ledger_before
    )
    assert invitee_with_replica.read(joining_case.case.id_) == case_before
    assert invitee_with_replica.outbox_list() == []


@pytest.fixture
def invitee_without_replica(joining_case):  # noqa: F811
    """An invitee store that has the stub Invite's trust anchor but no case yet."""
    dl = SqliteDataLayer(
        "sqlite:///:memory:", actor_id=joining_case.invitee_id
    )
    dl.save(
        VultronPendingCaseInbox(
            case_id=joining_case.case.id_,
            case_actor_id=joining_case.case_actor_id,
        )
    )
    return dl


@pytest.mark.spec("CM-11-010")
@pytest.mark.spec("PCR-03-004")
@pytest.mark.spec("HP-01-006")
def test_before_the_announce_the_recorded_trust_anchor_is_the_case_manager(
    joining_case,  # noqa: F811
    invitee_without_replica,
) -> None:
    """With no replica yet, the CASE_MANAGER recorded from the stub Invite decides."""
    accepted = _receive_as_invitee(
        invitee_without_replica,
        joining_case,
        _full_case_invite_from(joining_case, joining_case.case_actor_id, "a"),
    )
    refused = _receive_as_invitee(
        invitee_without_replica,
        joining_case,
        _full_case_invite_from(joining_case, _IMPOSTOR_ID, "b"),
    )

    assert accepted.disposition is not HandlerDisposition.REFUSED
    assert refused.disposition is HandlerDisposition.REFUSED


@pytest.mark.spec("CM-11-010")
@pytest.mark.spec("PCR-03-004")
@pytest.mark.spec("HP-01-006")
def test_with_no_replica_and_no_trust_anchor_a_full_case_invite_is_refused(
    joining_case,  # noqa: F811
) -> None:
    """No CASE_MANAGER known to match the sender: fail closed, never admit."""
    bare = SqliteDataLayer(
        "sqlite:///:memory:", actor_id=joining_case.invitee_id
    )

    result = _receive_as_invitee(
        bare,
        joining_case,
        _full_case_invite_from(joining_case, joining_case.case_actor_id, "c"),
    )

    assert result.disposition is HandlerDisposition.REFUSED
