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

"""
Behavior tree factories for received-side report use cases.

Each factory produces a ``py_trees.composites.Sequence`` that implements the
inbound protocol handling (intake records each received activity once its
doors admit it, CLP-10-017) for one of the report-lifecycle activities:

- ``CreateReport`` — store VulnerabilityReport
- ``AckReport``    — check the acknowledgement's sender
- ``InvalidateReport`` — record the *sender's* RM → INVALID

with ``ValidateReport`` (the sender's RM → VALID) alongside, and
``CloseReport``, which no receiver applies: its tree only refuses it
(CM-23-019).
Every RM write
here is about the sender of the activity, never the receiving actor whose store
the tree runs in (RSH-08-001), and is adjudicated by the received-side RM
acceptance rule shared with ``Add(ParticipantStatus)`` (RSH-06-006) — see
:mod:`vultron.core.behaviors.report.rm_declaration_tree`.

Trees are run via ``BTBridge.execute_with_setup()`` in the corresponding use
case.

Per issue #759 AC-1 through AC-4.

The factories live in submodules grouped by concern (CS-18-005):

- ``receipt``: ``CreateReport`` and ``AckReport``.
- ``validate``: ``ValidateReport``.
- ``verdicts``: ``CloseReport`` and ``InvalidateReport``.

``create_report_received_tree`` is looked up here by its use case, so a test
can replace it on this package.
"""

from vultron.core.behaviors.report.received_report_trees.receipt import (
    create_ack_report_received_tree,
    create_report_received_tree,
)
from vultron.core.behaviors.report.received_report_trees.validate import (
    create_validate_report_received_tree,
)
from vultron.core.behaviors.report.received_report_trees.verdicts import (
    create_close_report_received_tree,
    create_invalidate_report_received_tree,
)

__all__ = [
    "create_ack_report_received_tree",
    "create_close_report_received_tree",
    "create_invalidate_report_received_tree",
    "create_report_received_tree",
    "create_validate_report_received_tree",
]
