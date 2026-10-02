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

"""A replica follows the CASE_MANAGER's P/X/A abandonment (EMB-16-001, #4131).

Each actor has its own store (TB-06-007).  The CASE_MANAGER abandons every
open proposal and commits one ER per proposal; a participant that receives
nothing but the ``Announce(CaseLedgerEntry)`` fan-out drops each proposal
and reaches EM ``NONE`` with the last (EP-09-007, RSH-08-004).
"""

from typing import Any

import pytest
from py_trees.common import Status

from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.embargo.trigger_tree import (
    reject_proposed_embargo_bt,
)
from vultron.core.states.em import EM

from .test_embargo_relay_replay import (
    BYSTANDER,
    MANAGER,
    _Network,
    _propose,
    _replay_to_bystander,
)


def _abandon_as_manager(net: _Network) -> Status:
    """Run the P/X/A abandonment in the CASE_MANAGER's own store."""
    dl = net.stores[MANAGER]
    ports: dict[str, Any] = {
        "trigger_activity": TriggerActivityAdapter(dl),
        "sync_port": SyncActivityAdapter(dl),
        "wire_render_port": As2WireRenderAdapter(),
    }
    tree = reject_proposed_embargo_bt(case_id=net.case_id, result_out={})
    return (
        BTBridge(datalayer=dl, **ports)
        .execute_with_setup(tree, actor_id=MANAGER)
        .status
    )


@pytest.mark.spec("EMB-16-001")
@pytest.mark.spec("EP-09-007")
@pytest.mark.spec("EP-09-008")
@pytest.mark.spec("RSH-08-004")
@pytest.mark.spec("TB-06-007")
def test_a_replica_follows_the_managers_abandonment_of_every_proposal():
    """PROPOSED with two open → NONE in the manager's store and the
    replica's, from the ledger fan-out alone."""
    net = _Network(
        "https://example.org/cases/abandon-replay", em_state=EM.NONE
    )
    first = _propose(net, "first", 60)
    second = _propose(net, "second", 30)
    _replay_to_bystander(net)
    for actor_id in (MANAGER, BYSTANDER):
        case = net.case(actor_id)
        assert case.current_status.em.state == EM.PROPOSED, actor_id
        assert sorted(case.proposed_embargo_ids) == sorted([first, second]), (
            actor_id
        )

    assert _abandon_as_manager(net) == Status.SUCCESS
    # The manager mails itself nothing (CLP-10-001).
    assert net.queued(MANAGER, to=MANAGER) == []
    _replay_to_bystander(net)

    for actor_id in (MANAGER, BYSTANDER):
        case = net.case(actor_id)
        assert case.current_status.em.state == EM.NONE, actor_id
        assert case.proposed_embargo_ids == [], actor_id
        assert case.active_embargo_id is None, actor_id
