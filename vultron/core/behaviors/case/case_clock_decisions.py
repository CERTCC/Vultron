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

"""The clock decisions every case tree takes, whatever its entry point.

Most clock decisions belong to one tree: an ownership Offer expires only
when an Offer or an answer to one arrives.  A decision about the case
itself is different: an overdue embargo is a fact about the case, so the
CASE_MANAGER takes it the next time it handles the case at all (EMB-13-003).
:func:`case_clock_decisions` lists those decisions.  The received-tree
factory runs them on every tree that has a case and a sender guard
(CLP-10-025), and ``SvcBTTriggerBase`` runs them ahead of every
case-scoped trigger's own tree, terminate excepted (ADR-0135).
"""

from datetime import datetime

import py_trees

from vultron.core.behaviors.embargo.end_time_tree import (
    end_time_clock_decision,
)
from vultron.core.models._helpers import now_utc

__all__ = ["case_clock_decisions"]


def case_clock_decisions(
    case_id: str, now: datetime | None = None
) -> list[py_trees.behaviour.Behaviour]:
    """The case-wide clock decisions for *case_id*, read against *now*.

    *now* defaults to the CASE_MANAGER's clock: a clock decision decides
    from its own clock, never from the received activity (CLP-10-025).
    Ungated: the caller composes them into the gated stage
    (:func:`~vultron.core.behaviors.case.nodes.clock_decision_stage.create_clock_decision_gate`).
    """
    at = now if now is not None else now_utc()
    return [end_time_clock_decision(case_id=case_id, now=at)]
