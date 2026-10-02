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
"""Ledger fan-out and replay apply the CM-10-004 embargo content gate (CM-10-005).

A participant that has not accepted the active embargo is sent no
``Announce(CaseLedgerEntry)`` -- neither by fan-out nor by a Reject-driven
replay -- and its stream is paused from the first entry withheld, so that the
backfill which admits it starts there (CM-10-006). Embargo Invites are not
ledger fan-out and still reach it (CM-10-005).
"""

from typing import cast
from unittest.mock import MagicMock

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.sync.nodes.conftest import (
    CASE_ID,
    _make_entry,
)
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.embargo.nodes import (
    CollectEmbargoInviteRecipientsNode,
)
from vultron.core.behaviors.sync.nodes import SendMissingEntriesNode
from vultron.core.behaviors.sync.nodes.embargo_pause import (
    embargo_paused_from_index,
)
from vultron.core.behaviors.sync.nodes.fanout import (
    CollectLogEntryRecipientsNode,
    CollectNonClosedLogEntryRecipientsNode,
    FanOutLogEntryExcludingClosedNode,
)
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
    close,
    collect_recipients,
    fan_out,
    manager_datalayer,
    paused_from,
    replay,
    seed_case,
    seed_ledger,
    sends,
)


@pytest.fixture
def datalayer():
    """The CASE_MANAGER's store, shadowing the package's participant store."""
    return manager_datalayer()


_COLLECTORS = pytest.mark.parametrize(
    "node_cls",
    [CollectLogEntryRecipientsNode, CollectNonClosedLogEntryRecipientsNode],
)


@pytest.mark.spec("CM-10-005")
@_COLLECTORS
def test_fanout_includes_non_signatory_without_active_embargo(
    bridge, datalayer, node_cls: type
) -> None:
    """Control: with no active embargo, the gate withholds nothing."""
    seed_case(datalayer, embargo_active=False)

    recipients = collect_recipients(bridge, node_cls)

    assert SIGNATORY_ID in recipients
    assert NON_SIGNATORY_ID in recipients


@pytest.mark.spec("CM-10-005")
@_COLLECTORS
def test_fanout_withholds_entries_from_non_signatory(
    bridge, datalayer, node_cls: type
) -> None:
    seed_case(datalayer, embargo_active=True)

    recipients = collect_recipients(bridge, node_cls)

    assert SIGNATORY_ID in recipients
    assert NON_SIGNATORY_ID not in recipients
    withheld = py_trees.blackboard.Blackboard.storage["/fanout_withheld"]
    assert list(withheld) == [NON_SIGNATORY_ID]


@pytest.mark.spec("CM-10-005")
def test_replay_sends_nothing_to_non_signatory(bridge, datalayer) -> None:
    """A paused participant's Reject must not replay the withheld entries."""
    seed_case(datalayer, embargo_active=True)
    first = _make_entry(0)
    second = _make_entry(1, first.entry_hash)
    sync_port = MagicMock(spec=SyncActivityPort)

    result = bridge.execute_with_setup(
        tree=SendMissingEntriesNode(name="SendMissingEntries"),
        actor_id=MANAGER_ID,
        sync_port=sync_port,
        case_actor_id=MANAGER_ID,
        replay_entry=second,
        replay_peer_id=NON_SIGNATORY_ID,
        replay_case_ledger_entries=[first, second],
        replay_from_index=0,
    )

    assert result.status == Status.SUCCESS
    sync_port.send_announce_log_entry.assert_not_called()
    assert (
        embargo_paused_from_index(
            datalayer, case_id=CASE_ID, peer_id=NON_SIGNATORY_ID
        )
        == 1
    )


@pytest.mark.spec("CM-10-005")
@pytest.mark.spec("CM-10-006")
def test_fanout_pauses_a_withheld_peer_at_the_first_entry_withheld(
    bridge, datalayer
) -> None:
    """A later withheld entry keeps the pause at the first one."""
    seed_case(datalayer, embargo_active=True)
    entries = seed_ledger(datalayer, 3)
    sync_port = MagicMock(spec=SyncActivityPort)

    fan_out(bridge, entries[1], sync_port)
    fan_out(bridge, entries[2], sync_port)

    assert all(NON_SIGNATORY_ID not in to for _, to in sends(sync_port))
    assert (
        embargo_paused_from_index(
            datalayer, case_id=CASE_ID, peer_id=NON_SIGNATORY_ID
        )
        == 1
    )


@pytest.mark.spec("CM-10-006")
def test_fanout_backfills_an_admitted_peer_before_the_new_entry(
    bridge, datalayer
) -> None:
    """Once admitted, the peer gets every withheld entry in order, then the new one.

    The fan-out admission point: the state change precedes the commit whose
    fan-out notices it. Signatories get the new entry once, and the manager
    never mails itself.
    """
    seed_case(datalayer, embargo_active=True)
    entries = seed_ledger(datalayer, 4)
    sync_port = MagicMock(spec=SyncActivityPort)
    fan_out(bridge, entries[1], sync_port)
    fan_out(bridge, entries[2], sync_port)
    sync_port.reset_mock()

    accept_embargo(datalayer, NON_SIGNATORY_ID)
    fan_out(bridge, entries[3], sync_port)

    to_peer = [
        index for index, to in sends(sync_port) if to == [NON_SIGNATORY_ID]
    ]
    assert to_peer == [1, 2, 3]
    to_signatory = [
        index for index, to in sends(sync_port) if SIGNATORY_ID in to
    ]
    assert to_signatory == [3]
    assert all(MANAGER_ID not in to for _, to in sends(sync_port))
    assert paused_from(datalayer) is None


@pytest.mark.spec("CM-10-005")
@pytest.mark.spec("CM-10-006")
def test_closed_fanout_does_not_backfill_a_closed_withheld_peer(
    bridge, datalayer
) -> None:
    """A collector's RM.CLOSED filter must not read a withheld peer as admitted.

    The non-closed collector drops closed peers before it gates, so its
    withheld list never names one; the backfill decides the gate itself.
    """
    seed_case(datalayer, embargo_active=True)
    entries = seed_ledger(datalayer, 3)
    sync_port = MagicMock(spec=SyncActivityPort)
    fan_out(bridge, entries[1], sync_port)
    close(datalayer, NON_SIGNATORY_ID)
    sync_port.reset_mock()

    fan_out(
        bridge,
        entries[2],
        sync_port,
        tree_cls=FanOutLogEntryExcludingClosedNode,
    )

    assert all(NON_SIGNATORY_ID not in to for _, to in sends(sync_port))
    assert paused_from(datalayer) == 1


@pytest.mark.spec("CM-10-005")
def test_an_admitted_replay_covering_the_pause_clears_it(
    bridge, datalayer
) -> None:
    """Replay of the whole withheld suffix leaves nothing to backfill."""
    seed_case(datalayer, embargo_active=True)
    entries = seed_ledger(datalayer, 3)
    sync_port = MagicMock(spec=SyncActivityPort)
    fan_out(bridge, entries[1], sync_port)
    accept_embargo(datalayer, NON_SIGNATORY_ID)
    sync_port.reset_mock()

    result = bridge.execute_with_setup(
        tree=SendMissingEntriesNode(name="SendMissingEntries"),
        actor_id=MANAGER_ID,
        sync_port=sync_port,
        case_actor_id=MANAGER_ID,
        replay_entry=entries[2],
        replay_peer_id=NON_SIGNATORY_ID,
        replay_case_ledger_entries=entries,
        replay_from_index=0,
    )

    assert result.status == Status.SUCCESS
    assert [index for index, _ in sends(sync_port)] == [1, 2]
    assert (
        embargo_paused_from_index(
            datalayer, case_id=CASE_ID, peer_id=NON_SIGNATORY_ID
        )
        is None
    )


@pytest.mark.spec("CM-10-006")
def test_an_admitted_replay_past_the_pause_clears_it(
    bridge, datalayer
) -> None:
    """A Reject reports a contiguous prefix, so entries below it are already held.

    The replay sends only the suffix past that prefix, and nothing withheld is
    left for a later backfill to send.
    """
    seed_case(datalayer, embargo_active=True)
    entries = seed_ledger(datalayer, 3)
    sync_port = MagicMock(spec=SyncActivityPort)
    fan_out(bridge, entries[1], sync_port)
    accept_embargo(datalayer, NON_SIGNATORY_ID)
    sync_port.reset_mock()

    result = replay(
        bridge,
        entries,
        peer_id=NON_SIGNATORY_ID,
        from_index=1,
        sync_port=sync_port,
    )

    assert result.status == Status.SUCCESS
    assert sends(sync_port) == [(2, [NON_SIGNATORY_ID])]
    assert paused_from(datalayer) is None


@pytest.mark.spec("CM-10-005")
def test_replay_for_an_unknown_case_fails_without_sending(
    bridge, datalayer
) -> None:
    """Without the case the gate cannot be decided, so nothing is replayed."""
    entries = seed_ledger(datalayer, 2)
    sync_port = MagicMock(spec=SyncActivityPort)

    result = replay(
        bridge,
        entries,
        peer_id=NON_SIGNATORY_ID,
        from_index=0,
        sync_port=sync_port,
    )

    assert result.status == Status.FAILURE
    sync_port.send_announce_log_entry.assert_not_called()


@pytest.mark.spec("CM-10-004")
@pytest.mark.spec("CM-10-005")
def test_genesis_reject_from_non_signatory_seeds_no_case(datalayer) -> None:
    """The case object is case content: a withheld peer's genesis Reject gets nothing."""
    seed_case(datalayer, embargo_active=True)
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
    trigger_activity.announce_vulnerability_case.assert_not_called()
    sync_port.send_announce_log_entry.assert_not_called()


@pytest.mark.spec("CM-10-005")
def test_embargo_invite_still_reaches_non_signatory(datalayer) -> None:
    """Embargo meta-protocol is not case content: the relayed Invite goes out."""
    seed_case(datalayer, embargo_active=True)

    result = BTBridge(
        datalayer=datalayer,
        trigger_activity=MagicMock(spec=TriggerActivityPort),
    ).execute_with_setup(
        tree=CollectEmbargoInviteRecipientsNode(
            case_id=CASE_ID, proposer_id=SIGNATORY_ID
        ),
        actor_id=MANAGER_ID,
    )

    assert result.status == Status.SUCCESS
    recipients = py_trees.blackboard.Blackboard.storage[
        "/embargo_invite_recipients"
    ]
    assert NON_SIGNATORY_ID in recipients
