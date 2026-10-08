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

"""The CASE_MANAGER's admission backfill after an embargo effect (CM-10-006).

:func:`embargo_admission_backfill_tree` is a standalone follow-on tree, not a
received-activity tree: it is given no activity and sends what the ledger
fan-out withheld once the embargo gate admits a participant.
``AcceptInviteToEmbargoOnCaseReceivedUseCase`` runs it on its own, and
``remove_embargo_from_case_tree`` nests it inside its active-teardown branch.
It lives outside the received-tree modules for the same reason the expiry
trees do: BT-17-008 binds received trees, which take their CASE_MANAGER gate
from ``create_receive_activity_tree``, and this tree has none of its own to
build (``test/architecture/test_received_tree_case_manager_gate.py``).
"""

import py_trees

from vultron.core.behaviors.case.nodes.role_gates import (
    create_case_manager_gated_tree,
)
from vultron.core.behaviors.sync.nodes.embargo_backfill import (
    BackfillAdmittedParticipantsNode,
)


def embargo_admission_backfill_tree(
    case_id: str,
) -> py_trees.behaviour.Behaviour:
    """Backfill the participants an embargo effect just admitted (CM-10-006).

    The admitting entry was committed and fanned out before the effect ran, so
    the fan-out withheld it; this sends it, and everything else withheld, once
    the gate admits the participant. CASE_MANAGER only (BT-17-001): the pause
    records and the canonical ledger live in its store.
    """
    return create_case_manager_gated_tree(
        name="EmbargoAdmissionBackfill",
        case_id=case_id,
        children=[BackfillAdmittedParticipantsNode(case_id=case_id)],
    )


__all__ = ["embargo_admission_backfill_tree"]
