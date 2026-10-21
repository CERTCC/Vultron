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

"""The join-time ledger backfill needs a sync port (SYNC-02-003, #4126)."""

import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.invite_ledger_backfill import (
    BackfillCanonicalLedgerToInviteeNode,
)

CASE_MANAGER_ID = "https://example.org/actors/case-manager"
CASE_ID = "https://example.org/cases/backfill-wiring"
INVITEE_ID = "https://example.org/actors/invitee"


@pytest.mark.spec("SYNC-02-003")
@pytest.mark.spec("BT-14-001")
def test_backfill_without_a_sync_port_is_a_wiring_fault():
    """The same wiring-fault type the fan-out raises, not a soft FAILURE."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=CASE_MANAGER_ID)
    bridge = BTBridge(datalayer=dl, wire_render_port=As2WireRenderAdapter())

    result = bridge.execute_with_setup(
        tree=BackfillCanonicalLedgerToInviteeNode(
            case_id=CASE_ID, invitee_id=INVITEE_ID
        ),
        actor_id=CASE_MANAGER_ID,
    )

    assert result.status == Status.FAILURE
    assert result.internal_error is True
    assert "sync_port" in result.feedback_message
    assert dl.outbox_list() == []


def _backfill(bridge, datalayer, invitee_id: str, sync_port):
    from test.core.behaviors.sync.nodes._embargo_gate_support import (
        MANAGER_ID,
    )
    from test.core.behaviors.sync.nodes.conftest import CASE_ID as GATE_CASE

    return bridge.execute_with_setup(
        tree=BackfillCanonicalLedgerToInviteeNode(
            case_id=GATE_CASE, invitee_id=invitee_id
        ),
        actor_id=MANAGER_ID,
        sync_port=sync_port,
    )


@pytest.mark.spec("CM-10-005")
@pytest.mark.spec("CLP-07-015")
def test_backfill_keeps_a_pause_the_same_act_recorded():
    """A seated non-signatory is paused by the Accept entry's fan-out.

    That fan-out runs earlier in the same act, so the backfill finds the
    pause state on record. It sends the whole prefix through the target
    and keeps the pause for the admission backfill (CM-10-006).
    """
    from unittest.mock import MagicMock

    from test.core.behaviors.sync.nodes._embargo_gate_support import (
        NON_SIGNATORY_ID,
        fan_out,
        manager_datalayer,
        paused_from,
        seed_case,
        seed_ledger,
        sends,
    )
    from test.core.behaviors.sync.nodes.conftest import CASE_ID as GATE_CASE
    from vultron.core.models.replication_state import VultronReplicationState
    from vultron.core.ports.sync_activity import SyncActivityPort

    dl = manager_datalayer()
    bridge = BTBridge(datalayer=dl)
    seed_case(dl, embargo_active=True)
    entries = seed_ledger(dl, 3)
    fan_out(bridge, entries[-1], MagicMock(spec=SyncActivityPort))
    assert paused_from(dl) == 2

    sync_port = MagicMock(spec=SyncActivityPort)
    result = _backfill(bridge, dl, NON_SIGNATORY_ID, sync_port)

    assert result.status == Status.SUCCESS
    assert sends(sync_port) == [
        (0, [NON_SIGNATORY_ID]),
        (1, [NON_SIGNATORY_ID]),
        (2, [NON_SIGNATORY_ID]),
    ]
    state = dl.read(
        VultronReplicationState(
            case_id=GATE_CASE, peer_id=NON_SIGNATORY_ID
        ).id_
    )
    assert isinstance(state, VultronReplicationState)
    assert state.embargo_paused_from_index == 2
    assert state.join_backfill_target_index == 2
    assert state.join_backfill_last_sent_index == 2
    assert state.join_backfill_complete is True


@pytest.mark.spec("CLP-07-015")
def test_backfill_of_an_empty_ledger_sends_nothing_and_is_complete():
    from unittest.mock import MagicMock

    from test.core.behaviors.sync.nodes._embargo_gate_support import (
        manager_datalayer,
    )
    from test.core.behaviors.sync.nodes.conftest import CASE_ID as GATE_CASE
    from vultron.core.models.replication_state import VultronReplicationState
    from vultron.core.ports.sync_activity import SyncActivityPort

    dl = manager_datalayer()
    bridge = BTBridge(datalayer=dl)
    sync_port = MagicMock(spec=SyncActivityPort)

    result = _backfill(bridge, dl, INVITEE_ID, sync_port)

    assert result.status == Status.SUCCESS
    sync_port.send_announce_log_entry.assert_not_called()
    state = dl.read(
        VultronReplicationState(case_id=GATE_CASE, peer_id=INVITEE_ID).id_
    )
    assert isinstance(state, VultronReplicationState)
    assert state.join_backfill_target_index == -1
    assert state.join_backfill_complete is True
