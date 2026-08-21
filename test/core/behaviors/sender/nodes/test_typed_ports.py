#!/usr/bin/env python

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

"""Typed-Ports isolation tests for sender domain nodes (AC-4, issue #1885).

Covers BTND-03-011 (NoDataAvailable on missing required port) and happy-path
execution via BTTestScenario for sender Type-B nodes.
"""

import pytest
from py_trees.ports import NoDataAvailable

from vultron.core.behaviors.sender.nodes.actions import QueueToOutboxNode
from test.core.behaviors.bt_harness import BTTestScenario

ACTOR_ID = "https://example.org/actors/vendor"


# ---------------------------------------------------------------------------
# actions.py — QueueToOutboxNode
# ---------------------------------------------------------------------------


class TestQueueToOutboxNodePorts:
    def test_missing_datalayer_raises_no_data_available(self) -> None:
        node = QueueToOutboxNode()
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("datalayer")

    def test_missing_activity_ids_raises_no_data_available(self) -> None:
        node = QueueToOutboxNode()
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("activity_ids")

    def test_failure_when_datalayer_absent(
        self, bt_scenario: BTTestScenario
    ) -> None:
        result = bt_scenario.run(QueueToOutboxNode(), actor_id=ACTOR_ID)
        bt_scenario.assert_failure(result)
