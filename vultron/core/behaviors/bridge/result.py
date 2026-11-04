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

"""The result a BT execution returns to its handler."""

from dataclasses import dataclass

from py_trees.common import Status


@dataclass
class BTExecutionResult:
    """Result of BT execution returned to handler.

    ``internal_error`` separates the two things a bare ``FAILURE`` used to
    conflate: a protocol outcome the tree is entitled to report, and a
    programming error that escaped a node. Callers that make a protocol
    decision from a failure — retry, re-buffer, log level — should consult it,
    because retrying a code bug never converges. See CONCERN-3019.

    Read the flag as *"an internal error reached the bridge"*, not *"no bug
    occurred"*. Two known gaps, both tracked in CONCERN-3019:

    - Node ``update()`` bodies catch broadly by convention, so a crash swallowed
      inside a node arrives here as an ordinary ``FAILURE`` (or even
      ``SUCCESS``) and is never flagged.
    - Nodes that run a sub-tree through their own ``BTBridge`` discard the inner
      result's flag and return a bare ``Status.FAILURE``, so a crash inside a
      nested subtree is not visible in the outer result.  The exception is
      ``CommitCaseLedgerEntryNode``, which raises ``VultronBTInternalError``
      when its nested commit reports one, so a missing sync port on a
      received commit is not read as a refusal (#4113).
    """

    status: Status
    feedback_message: str = ""
    errors: list[str] | None = None
    internal_error: bool = False
    # The tree never ran: this node is not the replication leader. A caller
    # reports that as "not my job", so it must not have to match the message.
    leader_skipped: bool = False
