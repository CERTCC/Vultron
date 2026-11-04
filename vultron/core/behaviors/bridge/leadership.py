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

"""Default leadership guard for single-node deployments (SYNC-09-003)."""


def _default_is_leader() -> bool:
    """Default leadership guard for single-node deployments.

    Always returns ``True`` — the single-node CaseActor is permanently the
    replication leader.  In a future multi-node deployment this function is
    replaced by an actual Raft leader check.

    Per SYNC-09-003, SYNC-06-003.
    """
    return True
