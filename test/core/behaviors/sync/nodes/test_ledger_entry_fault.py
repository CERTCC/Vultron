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

"""The shared emission of a replica's fault about a refused ledger entry."""

from unittest.mock import MagicMock

import pytest
from py_trees.common import Status

from test.core.behaviors.sync.nodes.conftest import (
    CASE_ID,
    PARTICIPANT_ACTOR_ID,
    _make_entry,
    _make_event,
)
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.sync.nodes.ledger_entry_fault import (
    EmitLedgerEntryFaultNode,
    emit_ledger_entry_fault,
)
from vultron.core.models.fault_classes import (
    VULTRON_FAILURE_LEDGER_ENTRY_REFUSED_HASH_MISMATCH,
)
from vultron.core.ports.trigger_activity import TriggerActivityPort

_CASE_MANAGER = "https://example.org/actors/case-actor"
_CLASS = VULTRON_FAILURE_LEDGER_ENTRY_REFUSED_HASH_MISMATCH


def _node(trigger: TriggerActivityPort | None) -> EmitLedgerEntryFaultNode:
    """A node as the bridge leaves it, without running a tree."""
    node = EmitLedgerEntryFaultNode(_CLASS, name="EmitFault")
    node.actor_id = PARTICIPANT_ACTOR_ID
    node.trigger_activity_factory = trigger
    return node


@pytest.mark.spec("SYNC-03-007")
@pytest.mark.spec("ASK-07-004")
def test_the_fault_names_the_announce_and_goes_to_its_sender(datalayer):
    """The node emits once, to the announce's sender, and still fails."""
    trigger = MagicMock(spec=TriggerActivityPort)
    event = _make_event(_make_entry(0), actor_id=_CASE_MANAGER)

    result = BTBridge(
        datalayer=datalayer, trigger_activity=trigger
    ).execute_with_setup(
        tree=EmitLedgerEntryFaultNode(_CLASS, name="EmitFault"),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=event,
    )

    assert result.status == Status.FAILURE
    trigger.emit_processing_fault.assert_called_once_with(
        actor=PARTICIPANT_ACTOR_ID,
        failed_activity_id=event.activity_id,
        failure_class=_CLASS,
        to=[_CASE_MANAGER],
        case_id=CASE_ID,
    )


@pytest.mark.spec("SYNC-03-007")
def test_without_a_trigger_port_nothing_is_emitted(caplog):
    event = _make_event(_make_entry(0), actor_id=_CASE_MANAGER)

    with caplog.at_level("WARNING", logger="vultron"):
        emitted = emit_ledger_entry_fault(_node(None), event, _CLASS)

    assert emitted is False
    assert any(
        r.levelname == "WARNING" and "HashMismatch" in r.getMessage()
        for r in caplog.records
    ), caplog.text


@pytest.mark.spec("SYNC-03-007")
def test_an_announce_naming_no_sender_is_not_answered(caplog):
    """With no one to answer, the WARNING says so and nothing is built."""
    trigger = MagicMock(spec=TriggerActivityPort)
    event = _make_event(_make_entry(0), actor_id=_CASE_MANAGER).model_copy(
        update={"actor_id": ""}
    )

    with caplog.at_level("WARNING", logger="vultron"):
        emitted = emit_ledger_entry_fault(_node(trigger), event, _CLASS)

    assert emitted is False
    trigger.emit_processing_fault.assert_not_called()
    assert any(
        r.levelname == "WARNING" and "names no id or sender" in r.getMessage()
        for r in caplog.records
    ), caplog.text
