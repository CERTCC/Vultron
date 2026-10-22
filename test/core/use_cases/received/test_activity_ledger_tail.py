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

Each test has *OWNER* send an ``Add(Note)`` to the CASE_MANAGER.  The
position travels as the activity's ``ledgerTail``; the CASE_MANAGER records
a lag and never refuses on it, and repairs a position its ledger does not
hold.  The tests for behavior not built yet are strict ``xfail``: the
implementing change replaces each with a passing test.
"""

import json
import logging
from typing import Any

import pytest

from test.support.ledger import ledger_entries
from vultron.adapters.outbox_sealed_body import dump_outbound_body
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.sync_helpers import ledger_tail_position
from vultron.wire.as2.factories import add_note_to_case_activity
from vultron.wire.as2.vocab.base.objects.object_types import as_Note

from ._ledger_network import MANAGER, OWNER, LedgerNetwork

CASE_ID = "https://example.org/cases/case-ledger-tail"
_NOT_STAMPED = (
    "SYNC-18: case activities do not carry ledgerTail yet. Tracked by #5109."
)
_NOT_JUDGED = (
    "SYNC-18: the CASE_MANAGER does not read ledgerTail yet. Tracked by #5110."
)


def _add_note_body(note_id: str, **extra: Any) -> dict[str, Any]:
    """The body *OWNER*'s outbox delivers for a new note on the case."""
    activity = add_note_to_case_activity(
        as_Note(id_=note_id, content="stamped", context=CASE_ID),
        target=CASE_ID,
        actor=OWNER,
        to=[MANAGER],
    )
    return {**json.loads(dump_outbound_body(activity)), **extra}


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


@pytest.mark.xfail(strict=True, reason=_NOT_STAMPED)
@pytest.mark.spec("SYNC-18-001")
def test_a_participant_case_activity_carries_its_ledger_tail():
    LedgerNetwork(CASE_ID)

    body = _add_note_body("https://example.org/notes/tail-1")

    assert "ledgerTail" in body


@pytest.mark.xfail(strict=True, reason=_NOT_STAMPED)
@pytest.mark.spec("SYNC-18-002")
def test_the_stamp_is_the_senders_tail_when_it_built_the_activity():
    net = LedgerNetwork(CASE_ID)
    expected = ledger_tail_position(CASE_ID, net.stores[OWNER])

    body = _add_note_body("https://example.org/notes/tail-2")

    assert body.get("ledgerTail") == _wire(expected)


@pytest.mark.xfail(strict=True, reason=_NOT_STAMPED)
@pytest.mark.spec("SYNC-18-003")
def test_an_unstamped_case_activity_is_refused_and_writes_nothing():
    net = LedgerNetwork(CASE_ID)
    body = _add_note_body("https://example.org/notes/tail-3")
    body.pop("ledgerTail", None)

    try:
        verdict = net.receive(MANAGER, body)
    except Exception:  # noqa: BLE001 — a parse-edge refusal may raise
        verdict = None

    assert verdict is None or verdict.disposition is not (
        HandlerDisposition.APPLIED
    )
    assert _note_entries(net) == []


@pytest.mark.xfail(strict=True, reason=_NOT_JUDGED)
@pytest.mark.spec("SYNC-18-004")
def test_a_lagging_stamp_is_applied_and_the_lag_logged(caplog):
    net = LedgerNetwork(CASE_ID)
    before = _manager_tail(net)
    first = _add_note_body(
        "https://example.org/notes/tail-4a", ledgerTail=_wire(before)
    )
    assert (
        net.receive(MANAGER, first).disposition is HandlerDisposition.APPLIED
    )
    assert _manager_tail(net).log_index > before.log_index
    behind = _add_note_body(
        "https://example.org/notes/tail-4b", ledgerTail=_wire(before)
    )

    with caplog.at_level(logging.DEBUG):
        verdict = net.receive(MANAGER, behind)

    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason
    assert any(
        record.levelno == logging.DEBUG and "behind" in record.getMessage()
        for record in caplog.records
    )


@pytest.mark.xfail(strict=True, reason=_NOT_JUDGED)
@pytest.mark.spec("SYNC-18-005")
def test_a_split_stamp_is_applied_logged_and_the_sender_reseeded(caplog):
    net = LedgerNetwork(CASE_ID)
    tail = _manager_tail(net)
    split = LedgerPosition(log_index=tail.log_index, entry_hash="0" * 64)
    body = _add_note_body(
        "https://example.org/notes/tail-5", ledgerTail=_wire(split)
    )

    with caplog.at_level(logging.ERROR):
        verdict = net.receive(MANAGER, body)

    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason
    assert any(r.levelno == logging.ERROR for r in caplog.records)
    copies = [
        activity
        for activity in net.queued(MANAGER, to=OWNER, type_="Announce")
        if getattr(activity.object_, "type_", None) == "VulnerabilityCase"
    ]
    assert copies, "no case copy was queued to the sender"


@pytest.mark.spec("SYNC-18-006")
def test_the_entry_records_the_received_ledger_tail():
    net = LedgerNetwork(CASE_ID)
    stamp = _wire(_manager_tail(net))
    body = _add_note_body("https://example.org/notes/tail-6", ledgerTail=stamp)

    verdict = net.receive(MANAGER, body)

    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason
    [entry] = _note_entries(net)
    assert entry.payload_snapshot["ledgerTail"] == stamp
