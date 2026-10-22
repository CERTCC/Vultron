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
"""Case copies that name a replica's own ledger position.

A case's wire form names the ledger position it is a projection of
(SYNC-16-005), and a replica that already holds the case judges the copy by
it (SYNC-16-006).  A test that builds a fresh copy gets the empty-ledger
position; these helpers give it the position the replica already holds, as a
current copy from the CASE_MANAGER would name.
"""

from vultron.core.models.case import VulnerabilityCase
from vultron.core.ports.case_persistence import CasePersistence


def copy_from(
    case: VulnerabilityCase, dl: CasePersistence
) -> VulnerabilityCase:
    """*case* as a copy at the ledger position *dl*'s case is at.

    A store that does not hold the case yet gets *case* unchanged, the copy
    a first seed takes (PCR-02-003).
    """
    held = dl.read_case(case.id_)
    if held is None:
        return case
    return case.model_copy(update={"ledger_position": held.ledger_position})
