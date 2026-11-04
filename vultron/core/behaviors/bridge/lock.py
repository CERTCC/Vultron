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

"""The one lock that serialises BT executions across threads.

Every user imports this object; never define a second lock.
"""

import threading

# py_trees uses a process-global blackboard (Blackboard.storage).
# FastAPI runs synchronous BackgroundTask callables in a thread-pool
# executor, so two BT executions can run on different threads at the
# same time, corrupting each other's actor_id / datalayer entries.
# This lock serialises BT executions from *different* threads while
# allowing same-thread re-entrancy (e.g. lifecycle.py nodes that call
# execute_with_setup internally).  RLock is used instead of Lock to
# prevent deadlock in those re-entrant paths.
_BT_GLOBAL_LOCK = threading.RLock()
