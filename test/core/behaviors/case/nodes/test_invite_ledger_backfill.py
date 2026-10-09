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
