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

"""CVD lifecycle milestone verification helpers.

Each function verifies the observable system state that corresponds to a named
milestone in the VFDPxa lifecycle.  Functions are named after the domain event
they confirm (e.g. ``verify_case_active``, ``verify_fix_ready``) rather than
opaque milestone numbers (m1–m7).

Submodules
----------
- :mod:`.lifecycle` — case active, fix ready, the VFd ceiling, fix deployed
  and public disclosure milestones.
- :mod:`.closure` — case closure: every participant RM.CLOSED and the
  CASE_MANAGER's ledger recording the closure in order.

Specs: DEMOMA-06-002, DEMOMA-06-003.
"""

from vultron.demo.helpers.milestones.closure import (
    case_closure_violations,
    case_manager_ledger,
    own_closure_tail_index,
    verify_case_closed,
    verify_case_closure_recorded,
    wait_for_case_fully_closed,
)
from vultron.demo.helpers.milestones.lifecycle import (
    verify_case_active,
    verify_fix_deployed,
    verify_fix_ready,
    verify_publicly_disclosed,
    verify_stops_at_fix_ready,
)

__all__ = [
    "case_closure_violations",
    "case_manager_ledger",
    "own_closure_tail_index",
    "verify_case_active",
    "verify_case_closed",
    "verify_case_closure_recorded",
    "verify_fix_deployed",
    "verify_fix_ready",
    "verify_publicly_disclosed",
    "verify_stops_at_fix_ready",
    "wait_for_case_fully_closed",
]
