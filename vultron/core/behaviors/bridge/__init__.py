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

"""BT Bridge Layer - Handler-to-BehaviorTree execution interface.

``BTBridge`` sets up the py_trees execution context, runs a tree to
completion and classifies the result.  Grouped by concern:

- ``bt_bridge``: ``BTBridge`` and ``execute_with_setup`` (BT-05-001)
- ``tree_setup``: store and port reconciliation, blackboard setup
- ``tree_execution``: the tick loop and exception classification
- ``result``: ``BTExecutionResult``
- ``lock``: the one process-wide execution lock (``_BT_GLOBAL_LOCK``)
- ``act_instant``: an act's one clock read and the ``/at`` key that carries
  it through a tree run (ADR-0176)
- ``leadership``: the single-node leadership guard (SYNC-09-003)
"""

from vultron.core.behaviors.bridge.bt_bridge import BTBridge
from vultron.core.behaviors.bridge.result import BTExecutionResult

__all__ = ["BTBridge", "BTExecutionResult"]
