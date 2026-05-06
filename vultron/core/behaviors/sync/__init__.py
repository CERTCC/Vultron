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

"""Sync protocol behavior trees.

Provides BT nodes and tree factories for SYNC-2/SYNC-3 log-entry
replication flows:

- :func:`~vultron.core.behaviors.sync.announce_tree.create_announce_log_entry_tree`
  — handles inbound ``Announce(CaseLogEntry)``
- :func:`~vultron.core.behaviors.sync.reject_tree.create_reject_log_entry_tree`
  — handles inbound ``Reject(CaseLogEntry)``
- :func:`~vultron.core.behaviors.sync.commit_tree.create_commit_log_entry_tree`
  — commits a new log entry and fans it out to peers

Spec: SBT-01 through SBT-05.
"""

from vultron.core.behaviors.sync.announce_tree import (
    create_announce_log_entry_tree,
)
from vultron.core.behaviors.sync.commit_tree import (
    create_commit_log_entry_tree,
)
from vultron.core.behaviors.sync.reject_tree import (
    create_reject_log_entry_tree,
)

__all__ = [
    "create_announce_log_entry_tree",
    "create_commit_log_entry_tree",
    "create_reject_log_entry_tree",
]
