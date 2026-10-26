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
    OWNER_ACTOR_ID,
    PARTICIPANT_ACTOR_ID,
    _make_entry,
    _make_event,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.sync.nodes.ledger_entry_fault import (
    EmitLedgerEntryFaultNode,
    emit_ledger_entry_fault,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.fault_classes import (
    VULTRON_FAILURE_LEDGER_ENTRY_REFUSED_HASH_MISMATCH,
)
from vultron.core.ports.trigger_activity import TriggerActivityPort
from vultron.enums.roles import CVDRole
from vultron.errors import (
    VultronBTInternalError,
    VultronValidationError,
    VultronWiringError,
)

_CASE_MANAGER = "https://example.org/actors/case-actor"
_STRANGER = "https://example.org/actors/stranger"
_CLASS = VULTRON_FAILURE_LEDGER_ENTRY_REFUSED_HASH_MISMATCH


@pytest.fixture
def managed(datalayer: SqliteDataLayer) -> SqliteDataLayer:
    """The replica's store, holding the case and its CASE_MANAGER's record."""
    manager = CaseParticipant(
        id_=f"{CASE_ID}/participants/case-manager",
        attributed_to=_CASE_MANAGER,
        context=CASE_ID,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    datalayer.create(manager)
    datalayer.save(
        VulnerabilityCase(
            id_=CASE_ID,
            attributed_to=OWNER_ACTOR_ID,
            case_participants=[manager.id_],
            actor_participant_index={_CASE_MANAGER: manager.id_},
        )
    )
    return datalayer


def _node(
    dl: SqliteDataLayer, trigger: TriggerActivityPort | None
) -> EmitLedgerEntryFaultNode:
    """A node as the bridge leaves it, without running a tree."""
    node = EmitLedgerEntryFaultNode(_CLASS, name="EmitFault")
    node.datalayer = dl
    node.actor_id = PARTICIPANT_ACTOR_ID
    node.trigger_activity_factory = trigger
    return node


@pytest.mark.spec("SYNC-03-007")
@pytest.mark.spec("ASK-07-004")
def test_the_fault_names_the_announce_and_goes_to_the_case_manager(managed):
    """The node emits once, to the CASE_MANAGER, and still fails."""
    trigger = MagicMock(spec=TriggerActivityPort)
    event = _make_event(_make_entry(0), actor_id=_CASE_MANAGER)

    result = BTBridge(
        datalayer=managed, trigger_activity=trigger
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
@pytest.mark.spec("ASK-07-002")
@pytest.mark.parametrize("seeded", [True, False], ids=["stranger", "no-case"])
def test_a_sender_that_is_not_the_case_manager_is_not_answered(
    datalayer, managed, seeded, caplog
):
    """Nothing goes to a sender this store cannot verify as the CASE_MANAGER.

    Either the case names another CASE_MANAGER, or this store holds no case
    and no bootstrap record naming one, the window in which the announce
    tree's sender guard lets the ``Announce`` through.
    """
    dl = (
        managed
        if seeded
        else SqliteDataLayer(
            "sqlite:///:memory:", actor_id=PARTICIPANT_ACTOR_ID
        )
    )
    trigger = MagicMock(spec=TriggerActivityPort)
    event = _make_event(_make_entry(0), actor_id=_STRANGER)

    with caplog.at_level("WARNING", logger="vultron"):
        emit_ledger_entry_fault(_node(dl, trigger), event, _CLASS)

    trigger.emit_processing_fault.assert_not_called()
    assert any(
        r.levelname == "WARNING" and "ASK-07-002" in r.getMessage()
        for r in caplog.records
    ), caplog.text


@pytest.mark.spec("SYNC-03-007")
@pytest.mark.parametrize(
    "missing", ["datalayer", "actor_id", "trigger_activity_factory"]
)
def test_a_missing_injection_is_a_wiring_fault(managed, missing):
    trigger = MagicMock(spec=TriggerActivityPort)
    node = _node(managed, trigger)
    setattr(node, missing, None)
    event = _make_event(_make_entry(0), actor_id=_CASE_MANAGER)

    with pytest.raises(VultronWiringError):
        emit_ledger_entry_fault(node, event, _CLASS)

    trigger.emit_processing_fault.assert_not_called()


@pytest.mark.spec("SYNC-03-007")
def test_the_node_without_a_trigger_port_is_an_internal_error(managed):
    """The bridge reports the wiring fault as internal, not a refusal."""
    event = _make_event(_make_entry(0), actor_id=_CASE_MANAGER)

    result = BTBridge(datalayer=managed).execute_with_setup(
        tree=EmitLedgerEntryFaultNode(_CLASS, name="EmitFault"),
        actor_id=PARTICIPANT_ACTOR_ID,
        activity=event,
    )

    assert result.internal_error is True


@pytest.mark.spec("SYNC-03-007")
def test_an_event_naming_no_activity_is_a_wiring_fault(managed):
    trigger = MagicMock(spec=TriggerActivityPort)
    event = _make_event(_make_entry(0), actor_id=_CASE_MANAGER).model_copy(
        update={"activity_id": ""}
    )

    with pytest.raises(VultronWiringError):
        emit_ledger_entry_fault(_node(managed, trigger), event, _CLASS)

    trigger.emit_processing_fault.assert_not_called()


@pytest.mark.spec("SYNC-03-007")
def test_a_port_that_fails_to_queue_the_fault_is_an_internal_error(managed):
    """A lost fault is not reported as a handled refusal."""
    trigger = MagicMock(spec=TriggerActivityPort)
    trigger.emit_processing_fault.side_effect = VultronValidationError("boom")
    event = _make_event(_make_entry(0), actor_id=_CASE_MANAGER)

    with pytest.raises(VultronBTInternalError):
        emit_ledger_entry_fault(_node(managed, trigger), event, _CLASS)
