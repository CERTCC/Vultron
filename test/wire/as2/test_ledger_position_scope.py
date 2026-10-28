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
"""Which received activities must state a ledger position (SYNC-18-001, -003).

A received event class requires ``ledger_position`` by subclassing
``LedgerPositionedEvent``, and the parse edge refuses an activity of such a
class that states none.  Every other received semantic is listed here with
the reason SYNC-18-001 leaves it out, so a new message type is either stamped
and required or out of scope by an explicit decision.
"""

from typing import cast, get_args

import pytest

from test.support.received import TEST_SENDER_POSITION, stamped
from vultron.core.models.events import AnyReceivedEvent, MessageSemantics
from vultron.core.models.events.base import (
    LedgerPositionedEvent,
    VultronEvent,
)
from vultron.core.models.events.sync import RejectLogEntryReceivedEvent
from vultron.semantic_registry import extract_event
from vultron.wire.as2.errors import VultronParseValidationError
from vultron.wire.as2.factories import (
    add_note_to_case_activity,
    rm_create_report_activity,
)
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

_NO_LEDGER_YET = "its sender holds no ledger for the case when it sends it"
_STATES_ITS_OWN = "its object states its own ledger position"

#: Received semantics outside SYNC-18-001's scope, with the reason.
OUT_OF_SCOPE: dict[MessageSemantics, str] = {
    MessageSemantics.CREATE_REPORT: _NO_LEDGER_YET,
    MessageSemantics.SUBMIT_REPORT: _NO_LEDGER_YET,
    MessageSemantics.VALIDATE_REPORT: _NO_LEDGER_YET,
    MessageSemantics.INVALIDATE_REPORT: _NO_LEDGER_YET,
    MessageSemantics.ACK_REPORT: _NO_LEDGER_YET,
    MessageSemantics.CLOSE_REPORT: _NO_LEDGER_YET,
    MessageSemantics.CREATE_CASE_PROPOSAL: _NO_LEDGER_YET,
    MessageSemantics.ACCEPT_CASE_PROPOSAL: _NO_LEDGER_YET,
    MessageSemantics.REJECT_CASE_PROPOSAL: _NO_LEDGER_YET,
    MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE: _NO_LEDGER_YET,
    MessageSemantics.REJECT_INVITE_ACTOR_TO_CASE: _NO_LEDGER_YET,
    MessageSemantics.CREATE_CASE: _STATES_ITS_OWN,
    MessageSemantics.ANNOUNCE_VULNERABILITY_CASE: _STATES_ITS_OWN,
    MessageSemantics.ANNOUNCE_CASE_LEDGER_ENTRY: _STATES_ITS_OWN,
    MessageSemantics.UPDATE_CASE_OWNER: (
        "a CASE_MANAGER ledger record no received use case handles"
        " (ADR-0140); its object is the case copy"
    ),
    MessageSemantics.CREATE_PROCESSING_FAULT: (
        "any receiver sends one about any activity, and it names no case"
        " (ASK-07-001, ASK-07-004)"
    ),
    MessageSemantics.REJECT_CASE_LEDGER_ENTRY: (
        "a peer that does not hold the case yet sends one with no position;"
        " one that does states its tail, which is parsed when present"
    ),
    MessageSemantics.UNKNOWN: "nothing is known about it",
    MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT: "nothing is known about it",
}


def _received_event_classes() -> list[type[VultronEvent]]:
    return list(get_args(AnyReceivedEvent))


def _semantics_of(event_class: type[VultronEvent]) -> MessageSemantics:
    return cast(
        MessageSemantics, event_class.model_fields["semantic_type"].default
    )


@pytest.mark.spec("SYNC-18-001")
@pytest.mark.spec("SYNC-18-003")
@pytest.mark.parametrize(
    "event_class", _received_event_classes(), ids=lambda cls: cls.__name__
)
def test_every_received_class_requires_a_position_or_is_out_of_scope(
    event_class: type[VultronEvent],
) -> None:
    semantics = _semantics_of(event_class)
    required = issubclass(event_class, LedgerPositionedEvent)

    assert required != (semantics in OUT_OF_SCOPE), (
        f"{event_class.__name__} ({semantics}) must either subclass"
        " LedgerPositionedEvent or be listed in OUT_OF_SCOPE with a reason"
    )
    if required:
        assert event_class.model_fields["ledger_position"].is_required()


@pytest.mark.spec("SYNC-18-003")
def test_the_scope_table_names_only_received_semantics() -> None:
    received = {_semantics_of(cls) for cls in _received_event_classes()}

    assert set(OUT_OF_SCOPE) <= received


@pytest.mark.spec("SYNC-18-003")
def test_a_reject_of_an_entry_may_state_no_position() -> None:
    field = RejectLogEntryReceivedEvent.model_fields["ledger_position"]

    assert not field.is_required()


def _note_on_case():
    case_id = "https://example.org/cases/scope"
    return add_note_to_case_activity(
        as_Note(id_=f"{case_id}/notes/1", content="scope", context=case_id),
        target=case_id,
        actor="https://example.org/users/vendor",
    )


@pytest.mark.spec("SYNC-18-003")
def test_an_in_scope_activity_without_a_position_is_refused_by_name() -> None:
    note = _note_on_case()

    with pytest.raises(VultronParseValidationError, match=note.id_):
        extract_event(note)


@pytest.mark.spec("SYNC-18-003")
def test_an_in_scope_activity_extracts_the_position_it_states() -> None:
    event = extract_event(stamped(_note_on_case()))

    assert isinstance(event, LedgerPositionedEvent)
    assert event.ledger_position == TEST_SENDER_POSITION


@pytest.mark.spec("SYNC-18-001")
def test_an_out_of_scope_activity_needs_no_position() -> None:
    report = as_VulnerabilityReport(
        id_="https://example.org/reports/scope", content="a vul"
    )
    offer = rm_create_report_activity(
        report, actor="https://example.org/users/finder"
    )

    event = extract_event(offer)

    assert event.semantic_type is MessageSemantics.CREATE_REPORT
