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

"""The CASE_MANAGER verdicts a handler still applies to the runner's result.

A received handler builds its tree and runs it through
:func:`~vultron.core.behaviors.case.received_run.run_received_tree`, which
reads the verdict from what the tree's nodes recorded (ADR-0195).  What is
left here reads the DataLayer around the run, so it cannot live in the
runner: :func:`case_manager_verdict` turns a CASE_MANAGER gate's skip into
the refusal HP-01-005 owes, and :func:`unheld_case_refusal` refuses an act
naming a case the receiver does not hold (ADR-0165).  #6394 moves both into
the tree and deletes this package.
"""

from vultron.core.use_cases.received._bt_verdict.case_manager import (
    case_manager_absence_refusal,
    case_manager_verdict,
    not_case_manager,
    not_case_manager_refusal,
    unheld_case_refusal,
)

__all__ = [
    "case_manager_absence_refusal",
    "case_manager_verdict",
    "not_case_manager",
    "not_case_manager_refusal",
    "unheld_case_refusal",
]
