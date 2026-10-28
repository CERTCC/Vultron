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
"""A case activity states its sender's ledger position (SYNC-18, ADR-0156).

Each test has a participant or the CASE_MANAGER send an ``Add(Note)``,
built by the sender's own trigger adapter as its outbox would send it.  The
position travels as the activity's ``ledgerPosition``; the CASE_MANAGER
records a lag, answers it as it answers a ``Read(CaseLedgerEntry)``, never
refuses on it, and repairs a position its ledger does not hold.  The tests
for behavior not built yet are strict ``xfail``: the implementing change
replaces each with a passing test.  A check that holds today for the wrong
reason (nothing sent, nothing recorded) shares a test with one that fails,
so the strict ``xfail`` cannot pass early.
"""

import json
import logging
from typing import Any, cast

import pytest

from test.support.ledger import ledger_entries
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.models.replication_state import VultronReplicationState
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.sync_helpers import ledger_tail_position
from vultron.wire.as2.errors import VultronParseValidationError
from vultron.wire.as2.vocab.base.objects.object_types import as_Note

from ._ledger_network import BYSTANDER, MANAGER, OWNER, LedgerNetwork

CASE_ID = "https://example.org/cases/case-ledger-tail"
_NOT_JUDGED = (
    "SYNC-18: the CASE_MANAGER does not read ledgerPosition yet. "
    "Tracked by #5110."
)


def _sent_note_body(
    dl: SqliteDataLayer, note_id: str, *, actor: str, to: str
) -> dict[str, Any]:
    """The sealed body *actor*'s adapter builds for a new note on the case."""
    if dl.read(note_id) is None:
        dl.create(as_Note(id_=note_id, content="stamped", context=CASE_ID))
    _activity_id, body = TriggerActivityAdapter(dl).add_note_to_case(
        note_id=note_id, case_id=CASE_ID, actor=actor, to=[to]
    )
    return cast(dict[str, Any], json.loads(body))


def _add_note_body(
    note_id: str,
    *,
    net: LedgerNetwork,
    actor: str = OWNER,
    to: str = MANAGER,
    **extra: Any,
) -> dict[str, Any]:
    """The body *actor*'s outbox delivers for a new note, with *extra* keys."""
    body = _sent_note_body(net.stores[actor], note_id, actor=actor, to=to)
    return {**body, **extra}


def _wire(position: LedgerPosition) -> dict[str, Any]:
    return position.model_dump(by_alias=True)


def _note_entries(net: LedgerNetwork) -> list[CaseLedgerEntry]:
    return [
        entry
        for entry in ledger_entries(net.stores[MANAGER], CASE_ID)
        if entry.semantic_type == "add_note_to_case"
    ]


def _manager_tail(net: LedgerNetwork) -> LedgerPosition:
    return ledger_tail_position(CASE_ID, net.stores[MANAGER])


def _advance(net: LedgerNetwork, note_id: str) -> LedgerPosition:
    """Commit one note at the CASE_MANAGER and return its tail before it."""
    before = _manager_tail(net)
    body = _add_note_body(note_id, net=net, ledgerPosition=_wire(before))
    verdict = net.receive(MANAGER, body)
    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason
    assert _manager_tail(net).log_index > before.log_index
    return before


def _withdraw_consent(net: LedgerNetwork, actor: str) -> None:
    """Decline *actor*'s consent, so it is no longer an active participant."""
    dl = net.stores[MANAGER]
    participant_id = net.case(MANAGER).actor_participant_index[actor]
    participant = cast(CaseParticipant, dl.read(participant_id))
    dl.save(
        participant.model_copy(
            update={
                "embargo_consents": [
                    EmbargoConsent(
                        embargo_id=net.initial_embargo_id,
                        state=EmbargoConsentState.DECLINED,
                    )
                ]
            }
        )
    )


def _replication_state(
    net: LedgerNetwork, peer: str
) -> list[VultronReplicationState]:
    return [
        cast(VultronReplicationState, state)
        for state in net.stores[MANAGER].list_objects(
            "VultronReplicationState"
        )
        if cast(VultronReplicationState, state).peer_id == peer
    ]


def _case_copies(net: LedgerNetwork, to: str) -> list[Any]:
    return [
        activity
        for activity in net.queued(MANAGER, to=to, type_="Announce")
        if getattr(activity.object_, "type_", None) == "VulnerabilityCase"
    ]


@pytest.mark.spec("SYNC-18-001")
def test_a_participant_case_activity_carries_its_ledger_position():
    net = LedgerNetwork(CASE_ID)
    _advance(net, "https://example.org/notes/tail-1a")

    body = _add_note_body("https://example.org/notes/tail-1b", net=net)

    assert "ledgerPosition" in body
    # An entry already states its own position, so its Announce carries none.
    [entry_announce, *_] = [
        activity
        for activity in net.queued(MANAGER, to=OWNER, type_="Announce")
        if getattr(activity.object_, "type_", None) == "CaseLedgerEntry"
    ]
    announced = read_sealed_body_dict(net.stores[MANAGER], entry_announce.id_)
    assert announced is not None
    assert "ledgerPosition" not in announced


@pytest.mark.spec("SYNC-18-001")
def test_a_case_manager_case_activity_carries_its_ledger_position():
    net = LedgerNetwork(CASE_ID)

    body = _add_note_body(
        "https://example.org/notes/tail-1c", net=net, actor=MANAGER, to=OWNER
    )

    assert body.get("ledgerPosition") == _wire(_manager_tail(net))


@pytest.mark.spec("SYNC-18-001")
def test_a_sender_that_holds_no_ledger_for_the_case_states_none():
    LedgerNetwork(CASE_ID)
    stranger = "https://example.org/users/stranger"
    store = SqliteDataLayer("sqlite:///:memory:", actor_id=stranger)

    body = _sent_note_body(
        store, "https://example.org/notes/tail-1d", actor=stranger, to=MANAGER
    )

    assert "ledgerPosition" not in body


@pytest.mark.spec("SYNC-18-002")
def test_the_stamp_is_the_senders_tail_when_it_built_the_activity():
    net = LedgerNetwork(CASE_ID)
    _advance(net, "https://example.org/notes/tail-2a")
    net.deliver(MANAGER, to=OWNER, type_="Announce")
    expected = ledger_tail_position(CASE_ID, net.stores[OWNER])
    assert expected.log_index >= 0, "the sender's ledger is still at genesis"

    body = _add_note_body("https://example.org/notes/tail-2b", net=net)

    assert body.get("ledgerPosition") == _wire(expected)


@pytest.mark.spec("SYNC-18-002")
def test_a_rebuilt_activity_keeps_the_position_it_was_first_sent_with():
    net = LedgerNetwork(CASE_ID)
    note_id = "https://example.org/notes/tail-2c"
    first = _add_note_body(note_id, net=net)
    _advance(net, "https://example.org/notes/tail-2d")
    net.deliver(MANAGER, to=OWNER, type_="Announce")
    assert ledger_tail_position(CASE_ID, net.stores[OWNER]) != (
        LedgerPosition.model_validate(first["ledgerPosition"])
    ), "the sender's tail did not move"

    again = _add_note_body(note_id, net=net)

    assert again["ledgerPosition"] == first["ledgerPosition"]


@pytest.mark.spec("SYNC-18-003")
def test_an_unstamped_case_activity_is_refused_and_writes_nothing():
    net = LedgerNetwork(CASE_ID)
    body = _add_note_body("https://example.org/notes/tail-3", net=net)
    body.pop("ledgerPosition")

    with pytest.raises(VultronParseValidationError) as refusal:
        net.receive(MANAGER, body, as_sent=True)

    assert body["id"] in str(refusal.value)
    assert "ledgerPosition" in str(refusal.value)
    assert _note_entries(net) == []


@pytest.mark.spec("SYNC-18-003")
def test_a_malformed_ledger_position_is_refused_and_writes_nothing():
    net = LedgerNetwork(CASE_ID)
    body = _add_note_body(
        "https://example.org/notes/tail-3b",
        net=net,
        ledgerPosition={"logIndex": "first", "entryHash": ""},
    )

    with pytest.raises(VultronParseValidationError) as refusal:
        net.receive(MANAGER, body)

    assert body["id"] in str(refusal.value)
    assert "ledgerPosition" in str(refusal.value)
    assert _note_entries(net) == []


@pytest.mark.xfail(strict=True, reason=_NOT_JUDGED)
@pytest.mark.spec("SYNC-18-004")
def test_a_lagging_stamp_is_applied_and_the_lag_logged(caplog):
    net = LedgerNetwork(CASE_ID)
    before = _advance(net, "https://example.org/notes/tail-4a")
    behind = _add_note_body(
        "https://example.org/notes/tail-4b",
        net=net,
        ledgerPosition=_wire(before),
    )

    with caplog.at_level(logging.DEBUG):
        verdict = net.receive(MANAGER, behind)

    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason
    assert any(
        record.levelno == logging.DEBUG
        and "behind" in record.getMessage()
        and behind["id"] in record.getMessage()
        and OWNER in record.getMessage()
        for record in caplog.records
    )


@pytest.mark.xfail(strict=True, reason=_NOT_JUDGED)
@pytest.mark.spec("SYNC-18-005")
@pytest.mark.parametrize("past_tail", [False, True], ids=["hash", "index"])
def test_a_split_stamp_is_applied_logged_and_the_sender_reseeded(
    caplog, past_tail
):
    net = LedgerNetwork(CASE_ID)
    tail = _manager_tail(net)
    split = (
        LedgerPosition(log_index=tail.log_index + 5, entry_hash="0" * 64)
        if past_tail
        else LedgerPosition(log_index=tail.log_index, entry_hash="0" * 64)
    )
    body = _add_note_body(
        "https://example.org/notes/tail-5a",
        net=net,
        ledgerPosition=_wire(split),
    )

    with caplog.at_level(logging.ERROR):
        verdict = net.receive(MANAGER, body)

    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason
    assert any(r.levelno == logging.ERROR for r in caplog.records)
    assert _case_copies(net, OWNER), "no case copy was queued to the sender"
    # A sender that is not an active participant is never re-seeded.
    _withdraw_consent(net, BYSTANDER)
    net.receive(
        MANAGER,
        _add_note_body(
            "https://example.org/notes/tail-5b",
            net=net,
            actor=BYSTANDER,
            ledgerPosition=_wire(split),
        ),
    )
    assert _case_copies(net, BYSTANDER) == []


@pytest.mark.spec("SYNC-18-006")
def test_the_entry_records_the_received_ledger_position():
    net = LedgerNetwork(CASE_ID)
    stamp = _wire(_manager_tail(net))
    body = _add_note_body(
        "https://example.org/notes/tail-6", net=net, ledgerPosition=stamp
    )

    verdict = net.receive(MANAGER, body)

    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason
    [entry] = _note_entries(net)
    assert entry.payload_snapshot["ledgerPosition"] == stamp


@pytest.mark.xfail(strict=True, reason=_NOT_JUDGED)
@pytest.mark.spec("SYNC-18-007")
def test_a_lagging_stamp_is_answered_as_a_stated_position():
    net = LedgerNetwork(CASE_ID)
    before = _advance(net, "https://example.org/notes/tail-7a")
    queued_before = len(net.queued(MANAGER, to=OWNER, type_="Announce"))
    behind = _add_note_body(
        "https://example.org/notes/tail-7b",
        net=net,
        ledgerPosition=_wire(before),
    )

    verdict = net.receive(MANAGER, behind)

    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason
    [state] = _replication_state(net, OWNER)
    assert state.last_acknowledged_hash == before.entry_hash
    replayed = net.queued(MANAGER, to=OWNER, type_="Announce")
    # Two new entries for the second note's fan-out and at least one replay.
    assert len(replayed) > queued_before + 1
    # From a sender that is not an active participant: no record, no replay.
    _withdraw_consent(net, BYSTANDER)
    bystander_queued = len(net.queued(MANAGER, to=BYSTANDER))
    net.receive(
        MANAGER,
        _add_note_body(
            "https://example.org/notes/tail-7c",
            net=net,
            actor=BYSTANDER,
            ledgerPosition=_wire(before),
        ),
    )
    assert _replication_state(net, BYSTANDER) == []
    assert len(net.queued(MANAGER, to=BYSTANDER)) == bystander_queued
