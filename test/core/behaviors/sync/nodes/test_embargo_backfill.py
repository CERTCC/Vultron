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
the admission backfill nodes on their gated and port-less paths, the
fan-out send refusing when it cannot decide the gate, and the genesis pre-seed
for a peer the gate admits.
"""

from datetime import UTC, datetime
from typing import cast
from unittest.mock import MagicMock

import pytest
from py_trees.common import Status

from test.core.behaviors.sync.nodes.conftest import CASE_ID
from test.support.act_runner import run_tree
from test.support.objects import authored_at, with_times
from test.support.received import received_event
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.role_gates import (
    create_case_manager_gated_tree,
)
from vultron.core.behaviors.embargo.admission_backfill_tree import (
    embargo_admission_backfill_nodes,
)
from vultron.core.behaviors.sync.nodes.embargo_pause import (
    record_embargo_pause,
)
from vultron.core.behaviors.sync.nodes.fanout import SendLogEntryToEachNode
from vultron.core.behaviors.sync.nodes.replay_guard import (
    read_replication_state,
)
from vultron.core.behaviors.sync.reject_tree import (
    create_reject_log_entry_tree,
)
from vultron.core.models.events.sync import RejectLogEntryReceivedEvent
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.ports.trigger_activity import TriggerActivityPort
from vultron.core.use_cases.received.sync import (
    RejectLedgerEntryReceivedUseCase,
)
from vultron.errors import VultronMissingActInstantError
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


def embargo_admission_backfill_tree(case_id: str):
    """The backfill nodes behind the CASE_MANAGER gate, as a received tree's
    ``manager_effects`` or the late-Accept honour arm run them (CM-10-006)."""
    return create_case_manager_gated_tree(
        name="EmbargoAdmissionBackfill",
        case_id=case_id,
        children=embargo_admission_backfill_nodes(case_id),
    )


def _admitted_paused_finder(datalayer) -> None:
    """A case whose finder was paused from entry 1 and has since accepted."""
    seed_case(datalayer, embargo_active=True)
    seed_ledger(datalayer, 3)
    record_embargo_pause(
        datalayer,
        case_id=CASE_ID,
        peer_id=NON_SIGNATORY_ID,
        from_index=1,
        at=datetime.now(UTC),
    )
    accept_embargo(datalayer, NON_SIGNATORY_ID)


@pytest.mark.spec("CM-10-006")
def test_admission_backfill_sends_the_withheld_suffix_as_case_manager(
    bridge, datalayer
) -> None:
    """Control for the two tests below: the manager with a port backfills."""
    _admitted_paused_finder(datalayer)
    sync_port = MagicMock(spec=SyncActivityPort)

    result = run_tree(
        bridge,
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

    run_tree(
        bridge,
        tree=embargo_admission_backfill_tree(CASE_ID),
        actor_id=SIGNATORY_ID,
        sync_port=sync_port,
    )

    sync_port.send_announce_log_entry.assert_not_called()
    assert paused_from(datalayer) == 1


@pytest.mark.spec("CM-10-006")
@pytest.mark.spec("SYNC-02-003")
@pytest.mark.spec("BT-14-001")
def test_admission_backfill_without_a_sync_port_is_a_wiring_fault(
    bridge, datalayer
) -> None:
    """No port fails loudly and keeps the pause, never a silent SUCCESS (#4126)."""
    _admitted_paused_finder(datalayer)

    result = run_tree(
        bridge,
        tree=embargo_admission_backfill_tree(CASE_ID),
        actor_id=MANAGER_ID,
    )

    assert result.status == Status.FAILURE
    assert result.internal_error is True
    assert "sync_port" in result.feedback_message
    assert paused_from(datalayer) == 1


@pytest.mark.spec("CM-10-005")
def test_fanout_send_fails_without_sending_when_the_case_is_missing(
    bridge, datalayer
) -> None:
    """Without the case the gate cannot be decided, so the entry goes nowhere."""
    (entry,) = seed_ledger(datalayer, 1)
    sync_port = MagicMock(spec=SyncActivityPort)

    result = run_tree(
        bridge,
        tree=SendLogEntryToEachNode(name="SendLogEntryToEach"),
        actor_id=MANAGER_ID,
        log_entry=entry,
        fanout_recipients=[SIGNATORY_ID],
        fanout_withheld=[NON_SIGNATORY_ID],
        sync_port=sync_port,
    )

    assert result.status == Status.FAILURE
    sync_port.send_announce_log_entry.assert_not_called()


def _fan_out_withheld(bridge, datalayer, **kwargs):
    """Fan an entry out to the signatory while withholding the finder."""
    seed_case(datalayer, embargo_active=True)
    (entry,) = seed_ledger(datalayer, 1)
    return run_tree(
        bridge,
        tree=SendLogEntryToEachNode(name="SendLogEntryToEach"),
        actor_id=MANAGER_ID,
        log_entry=entry,
        fanout_recipients=[SIGNATORY_ID],
        fanout_withheld=[NON_SIGNATORY_ID],
        sync_port=MagicMock(spec=SyncActivityPort),
        **kwargs,
    )


@pytest.mark.spec("CM-10-005")
@pytest.mark.spec("CS-13-002")
def test_fanout_stamps_a_withheld_peers_pause_with_the_acts_instant(
    bridge, datalayer
) -> None:
    at = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)

    result = _fan_out_withheld(bridge, datalayer, at=at)

    assert result.status == Status.SUCCESS, result.feedback_message
    state = read_replication_state(
        datalayer, case_id=CASE_ID, peer_id=NON_SIGNATORY_ID
    )
    assert state is not None
    assert state.embargo_paused_from_index == 0
    assert state.updated_at == at


@pytest.mark.spec("ARCH-10-001")
def test_fanout_without_an_act_instant_is_an_internal_error(
    bridge, datalayer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing instant is a wiring fault, never an undecidable gate."""

    def _missing(_self: object) -> datetime:
        raise VultronMissingActInstantError("no act instant")

    monkeypatch.setattr(
        SendLogEntryToEachNode, "_require_act_instant", _missing
    )

    result = _fan_out_withheld(bridge, datalayer)

    assert result.status == Status.FAILURE
    assert result.internal_error
    assert paused_from(datalayer) is None


@pytest.mark.spec("CM-10-004")
@pytest.mark.spec("SYNC-15-015")
def test_genesis_reject_from_an_admitted_peer_seeds_the_case(
    datalayer,
) -> None:
    """Once the finder accepts, its genesis Reject gets the case, then the log."""
    seed_case(datalayer, embargo_active=True)
    accept_embargo(datalayer, NON_SIGNATORY_ID)
    (entry,) = seed_ledger(datalayer, 1)
    activity = reject_log_entry_activity(
        entry=WireCaseLedgerEntry.model_validate(
            with_times(WireCaseLedgerEntry, entry.model_dump(mode="json"))
        ),
        actor=NON_SIGNATORY_ID,
        to=[MANAGER_ID],
        in_reply_to="https://example.org/activities/prompting-announce",
        at=authored_at(),
    )
    event = cast(RejectLogEntryReceivedEvent, received_event(activity))
    sync_port = MagicMock(spec=SyncActivityPort)
    trigger_activity = MagicMock(spec=TriggerActivityPort)
    trigger_activity.announce_vulnerability_case.return_value = (
        f"{MANAGER_ID}/activities/announce-case"
    )

    result = run_tree(
        BTBridge(
            datalayer=datalayer,
            sync_port=sync_port,
            trigger_activity=trigger_activity,
        ),
        tree=create_reject_log_entry_tree(
            CASE_ID,
            sender_rule=RejectLedgerEntryReceivedUseCase.sender_entitlement,
        ),
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
