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
"""A message missing a slot its meaning requires is refused at the parse edge.

Each slot a received ``execute()`` used to test for (#6493) is a required
slot of its message's event subtype (``VultronEvent.required_slots``), so
the extractor's construction of the event fails with a reason naming the
slot, and no use case sees the message (ARCH-10-001, ADR-0032).

Each row of :data:`CASES` is one such slot: a builder of the complete
message, the wire field the test cuts to leave the slot empty, and whether
the semantic pattern still matches the cut message.  Most patterns already
require the field, so the cut message is classified unknown and never
reaches its event; the event still refuses it, which the forced extraction
pins (defence in depth).  Where the pattern still matches, the inbox's own
extraction raises.
"""

from typing import cast

import pytest
from pydantic import ValidationError

from test.support.required_slots import (
    CASES,
    MESSAGES,
    SlotCase,
    complete,
    slot_reason,
    without_slot,
)
from vultron.core.models.events.base import VultronEvent
from vultron.core.models.events.case import CreateCaseReceivedEvent
from vultron.semantic_registry import (
    SEMANTIC_REGISTRY,
    extract_event,
    find_matching_semantics,
    lookup_entry,
)
from vultron.wire.as2.extractor import extract_intent


@pytest.mark.spec("ARCH-10-001")
@pytest.mark.parametrize("message", MESSAGES)
def test_a_complete_message_extracts_to_its_event(message: str) -> None:
    """The slots are present on every complete message, so nothing changes."""
    activity = complete(message)
    semantics = find_matching_semantics(activity)
    event = extract_event(activity)
    assert isinstance(event, lookup_entry(semantics).event_class)
    for slot in cast(VultronEvent, event).required_slots:
        assert getattr(event, slot)


@pytest.mark.spec("ARCH-10-001")
@pytest.mark.parametrize("case", CASES, ids=lambda case: case.id)
def test_the_event_refuses_a_message_missing_the_slot(case: SlotCase) -> None:
    """The extractor's construction of the event names the missing slot.

    Forced to the semantics the complete message matches, so the row also
    pins the event for a message whose pattern refuses the cut first.
    """
    assert find_matching_semantics(complete(case.message)) is case.semantics
    entry = lookup_entry(case.semantics)
    assert case.slot in entry.event_class.required_slots

    with pytest.raises(ValidationError) as caught:
        extract_intent(
            without_slot(case),
            semantics=case.semantics,
            event_class=entry.event_class,
            include_activity=entry.include_activity,
        )

    assert slot_reason(case) in str(caught.value)


@pytest.mark.spec("ARCH-10-001")
@pytest.mark.parametrize("case", CASES, ids=lambda case: case.id)
def test_the_inbox_extraction_never_dispatches_a_message_missing_the_slot(
    case: SlotCase,
) -> None:
    """The message never reaches a use case as its own semantics.

    Where the pattern still matches, the inbox's extraction raises naming
    the slot.  Elsewhere the pattern itself refuses the cut message, which
    is classified unknown; a ``Reject(EmbargoEvent)`` with no object is the
    genesis-replay ``Reject`` of a ledger entry (SYNC-16-027), a different
    message.
    """
    activity = without_slot(case)
    assert find_matching_semantics(activity) is case.cut_matches
    if case.cut_matches is case.semantics:
        with pytest.raises(ValidationError) as caught:
            extract_event(activity)
        assert slot_reason(case) in str(caught.value)
    else:
        assert extract_event(activity).semantic_type is case.cut_matches


#: Declared slots no row cuts, each with why no message can lack it alone.
NO_ROW: dict[tuple[type[VultronEvent], str], str] = {
    (CreateCaseReceivedEvent, "case_id"): (
        "the id of the inline case, which every case object carries; a"
        " Create with no case is the ``case`` row"
    ),
}


def _declared_slots() -> set[tuple[type[VultronEvent], str]]:
    return {
        (entry.event_class, slot)
        for entry in SEMANTIC_REGISTRY
        for slot in entry.event_class.required_slots
    }


def test_every_declared_slot_is_a_property() -> None:
    """A name in ``required_slots`` that is a plain attribute would read a
    value, never through ``_required``, so it would never refuse."""
    for event_class, slot in _declared_slots():
        assert isinstance(getattr(event_class, slot), property), (
            event_class,
            slot,
        )


def test_every_declared_slot_has_a_row() -> None:
    """A slot declared later with no row is never tested missing."""
    rows = {
        (lookup_entry(case.semantics).event_class, case.slot) for case in CASES
    }
    assert _declared_slots() - set(NO_ROW) == rows
