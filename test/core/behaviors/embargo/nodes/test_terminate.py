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

"""Typed-Ports isolation tests for SendTerminateEmbargoActivityNode (AC-4, #1885).

Covers BTND-03-011: required port reads raise NoDataAvailable when the
blackboard key is absent.
"""

import pytest
from py_trees.ports import NoDataAvailable

from vultron.core.behaviors.embargo.nodes.terminate import (
    SendTerminateEmbargoActivityNode,
)
from test.core.behaviors.bt_harness import BTTestScenario

ACTOR_ID = "https://example.org/actors/vendor"
CASE_ID = "https://example.org/cases/case-001"


class TestSendTerminateEmbargoActivityNodePorts:
    def test_missing_datalayer_raises_no_data_available(self) -> None:
        node = SendTerminateEmbargoActivityNode(case_id=CASE_ID)
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("datalayer")

    def test_missing_embargo_id_raises_no_data_available(self) -> None:
        node = SendTerminateEmbargoActivityNode(case_id=CASE_ID)
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("embargo_id")

    def test_missing_case_manager_id_raises_no_data_available(self) -> None:
        node = SendTerminateEmbargoActivityNode(case_id=CASE_ID)
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("case_manager_id")

    def test_failure_when_factory_unavailable(
        self, bt_scenario: BTTestScenario
    ) -> None:
        result = bt_scenario.run(
            SendTerminateEmbargoActivityNode(case_id=CASE_ID),
            actor_id=ACTOR_ID,
        )
        bt_scenario.assert_failure(result)
