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

"""Run a received tree and read its verdict from its nodes (ADR-0195).

A received use case only builds its tree and runs it through
:func:`run_received_tree`, which runs it once as the receiver and reads the
``HandlerResult`` from what the tree's nodes recorded:

- :mod:`.reading` — the generic reading: doors, the sequence stage, a
  node-declared repeat (``ReportsIdempotentRepeat``), no-change
  (``ReportsNoChange``) or refusal (``ReportsRefusal``), and the general
  refusal.
- :mod:`.readers` — handler-specific readings, each an
  :data:`OutcomeReader` that receives only the finished run.
- :mod:`.doors`, :mod:`.sequence` — the door and sequence-stage verdicts.
- :mod:`.lookup` — finding nodes in a finished run.

Tree tests read outcomes here without importing ``use_cases``.
"""

from vultron.core.behaviors.case.received_run.doors import (
    addressee_refusal,
    door_refusal,
    guard_refusal,
    incomplete_activity_refusal,
    path_refusal,
    post_close_refusal,
    seen_before_verdict,
)
from vultron.core.behaviors.case.received_run.lookup import (
    door_guards_admitted,
    failure_reason,
    find_named,
    find_node,
    named_node_status,
    node_failed,
    node_succeeded,
    received_path,
    taken_diversion,
)
from vultron.core.behaviors.case.received_run.readers import (
    closed_sender_reader,
    first_reading,
    pxa_refusal_reader,
)
from vultron.core.behaviors.case.received_run.reading import (
    OutcomeReader,
    ReceivedOutcome,
    read_outcome,
)
from vultron.core.behaviors.case.received_run.runner import run_received_tree
from vultron.core.behaviors.case.received_run.sequence import (
    sender_sequence_verdict,
)

__all__ = [
    "OutcomeReader",
    "ReceivedOutcome",
    "addressee_refusal",
    "closed_sender_reader",
    "door_guards_admitted",
    "door_refusal",
    "failure_reason",
    "find_named",
    "find_node",
    "first_reading",
    "guard_refusal",
    "incomplete_activity_refusal",
    "named_node_status",
    "node_failed",
    "node_succeeded",
    "path_refusal",
    "post_close_refusal",
    "pxa_refusal_reader",
    "read_outcome",
    "received_path",
    "run_received_tree",
    "seen_before_verdict",
    "sender_sequence_verdict",
    "taken_diversion",
]
