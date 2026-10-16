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

:func:`embargo_admission_backfill_nodes` sends what the ledger fan-out
withheld once the embargo gate admits a participant, then re-issues the stub
Invites that carry stale terms.  A received tree runs them behind the
CASE_MANAGER gate it takes from the factory: the ``Add(EmbargoEvent)`` and
``Remove(EmbargoEvent)`` trees in their ``manager_effects``, and the Invite
Accept tree in its late-Accept honour diversion (CLP-10-026).
"""

import py_trees

from vultron.config.actor import ActorConfig
from vultron.core.behaviors.case.nodes.stub_reissue import (
    ReissueStubInvitesNode,
)
from vultron.core.behaviors.sync.nodes.embargo_backfill import (
    BackfillAdmittedParticipantsNode,
)


def embargo_admission_backfill_nodes(
    case_id: str,
    actor_config: ActorConfig | None = None,
) -> list[py_trees.behaviour.Behaviour]:
    """The backfill, then the stub re-issue (CM-10-006, CM-11-016).

    The admitting entry was committed and fanned out before the effect ran,
    so the fan-out withheld it; the backfill sends it, and everything else
    withheld.  The same effect may have changed the embargo in force, so the
    stub Invites still outstanding with the old terms are re-issued; a no-op
    when none are.  The caller runs them behind the CASE_MANAGER gate
    (BT-17-001, BT-17-008): the pause records, the canonical ledger and the
    stub Invites live in its store.  *actor_config* sets the replacements'
    RSVP window; ``None`` applies the ``ActorConfig`` defaults.
    """
    return [
        BackfillAdmittedParticipantsNode(case_id=case_id),
        ReissueStubInvitesNode(case_id=case_id, actor_config=actor_config),
    ]


__all__ = ["embargo_admission_backfill_nodes"]
