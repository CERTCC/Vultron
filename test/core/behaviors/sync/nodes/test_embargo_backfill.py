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
"""Admission-backfill and fail-closed paths of the embargo gate (CM-10-005/006).

Covers what ``test_fanout_embargo_gate.py`` does not: the
``embargo_admission_backfill_tree`` on its gated and port-less paths, the
fan-out send refusing when it cannot decide the gate, and the genesis pre-seed
for a peer the gate admits.
"""

from typing import cast
from unittest.mock import MagicMock

import pytest
from py_trees.common import Status

from test.core.behaviors.sync.nodes.conftest import CASE_ID
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.embargo.announce_teardown_tree import (
    embargo_admission_backfill_tree,
)
from vultron.core.behaviors.sync.nodes.embargo_pause import (
    record_embargo_pause,
)
from vultron.core.behaviors.sync.nodes.fanout import SendLogEntryToEachNode
from vultron.core.behaviors.sync.reject_tree import (
    create_reject_log_entry_tree,
)
from vultron.core.models.events.sync import RejectLogEntryReceivedEvent
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.ports.trigger_activity import TriggerActivityPort
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import reject_log_entry_activity
from vultron.wire.as2.vocab.objects.case_ledger_entry import (
    as_CaseLedgerEntry as WireCaseLedgerEntry,
)

from ._embargo_gate_support import (
    MANAGER_ID,
    NON_SIGNATORY_ID,
    SIGNATORY_ID,
    accept_embargo,
    manager_datalayer,
    paused_from,
    seed_case,
    seed_ledger,
    sends,
)


@pytest.fixture
def datalayer():
    """The CASE_MANAGER's store, shadowing the package's participant store."""
    return manager_datalayer()


def _admitted_paused_finder(datalayer) -> None:
    """A case whose finder was paused from entry 1 and has since accepted."""
    seed_case(datalayer, embargo_active=True)
    seed_ledger(datalayer, 3)
    record_embargo_pause(
        datalayer, case_id=CASE_ID, peer_id=NON_SIGNATORY_ID, from_index=1
    )
    accept_embargo(datalayer, NON_SIGNATORY_ID)


@pytest.mark.spec("CM-10-006")
def test_admission_backfill_sends_the_withheld_suffix_as_case_manager(
    bridge, datalayer
) -> None:
    """Control for the two tests below: the manager with a port backfills."""
    _admitted_paused_finder(datalayer)
    sync_port = MagicMock(spec=SyncActivityPort)

    result = bridge.execute_with_setup(
        tree=embargo_admission_backfill_tree(CASE_ID),
        actor_id=MANAGER_ID,
        sync_port=sync_port,
    )

    assert result.status == Status.SUCCESS
    assert sends(sync_port) == [
        (1, [NON_SIGNATORY_ID]),
        (2, [NON_SIGNATORY_ID]),
    ]
    assert paused_from(datalayer) is None


@pytest.mark.spec("BT-17-005")
@pytest.mark.spec("CM-10-006")
def test_admission_backfill_does_nothing_for_a_non_case_manager(
    bridge, datalayer
) -> None:
    """The gate turns a non-manager away: nothing is sent, the pause stands."""
    _admitted_paused_finder(datalayer)
    sync_port = MagicMock(spec=SyncActivityPort)

    bridge.execute_with_setup(
        tree=embargo_admission_backfill_tree(CASE_ID),
        actor_id=SIGNATORY_ID,
        sync_port=sync_port,
    )

    sync_port.send_announce_log_entry.assert_not_called()
    assert paused_from(datalayer) == 1


@pytest.mark.spec("CM-10-006")
def test_admission_backfill_without_a_sync_port_keeps_the_pause(
    bridge, datalayer
) -> None:
    """With nothing to send through, the pause waits for a later admission point."""
    _admitted_paused_finder(datalayer)

    result = bridge.execute_with_setup(
        tree=embargo_admission_backfill_tree(CASE_ID),
        actor_id=MANAGER_ID,
    )

    assert result.status == Status.SUCCESS
    assert paused_from(datalayer) == 1


@pytest.mark.spec("CM-10-005")
def test_fanout_send_fails_without_sending_when_the_case_is_missing(
    bridge, datalayer
) -> None:
    """Without the case the gate cannot be decided, so the entry goes nowhere."""
    (entry,) = seed_ledger(datalayer, 1)
    sync_port = MagicMock(spec=SyncActivityPort)

    result = bridge.execute_with_setup(
        tree=SendLogEntryToEachNode(name="SendLogEntryToEach"),
        actor_id=MANAGER_ID,
        log_entry=entry,
        fanout_recipients=[SIGNATORY_ID],
        fanout_withheld=[NON_SIGNATORY_ID],
        sync_port=sync_port,
    )

    assert result.status == Status.FAILURE
    sync_port.send_announce_log_entry.assert_not_called()


@pytest.mark.spec("CM-10-004")
@pytest.mark.spec("SYNC-15-002")
def test_genesis_reject_from_an_admitted_peer_seeds_the_case(
    datalayer,
) -> None:
    """Once the finder accepts, its genesis Reject gets the case, then the log."""
    seed_case(datalayer, embargo_active=True)
    accept_embargo(datalayer, NON_SIGNATORY_ID)
    (entry,) = seed_ledger(datalayer, 1)
    activity = reject_log_entry_activity(
        entry=WireCaseLedgerEntry.model_validate(
            entry.model_dump(mode="json")
        ),
        context="",
        actor=NON_SIGNATORY_ID,
        to=[MANAGER_ID],
    )
    event = cast(RejectLogEntryReceivedEvent, extract_event(activity))
    sync_port = MagicMock(spec=SyncActivityPort)
    trigger_activity = MagicMock(spec=TriggerActivityPort)
    trigger_activity.announce_vulnerability_case.return_value = (
        f"{MANAGER_ID}/activities/announce-case"
    )

    result = BTBridge(
        datalayer=datalayer,
        sync_port=sync_port,
        trigger_activity=trigger_activity,
    ).execute_with_setup(
        tree=create_reject_log_entry_tree(),
        actor_id=MANAGER_ID,
        activity=event,
        sync_port=sync_port,
    )

    assert result.status == Status.SUCCESS
    trigger_activity.announce_vulnerability_case.assert_called_once()
    announce = trigger_activity.announce_vulnerability_case.call_args.kwargs
    assert announce["case_id"] == CASE_ID
    assert announce["to"] == [NON_SIGNATORY_ID]
    assert sends(sync_port) == [(0, [NON_SIGNATORY_ID])]
