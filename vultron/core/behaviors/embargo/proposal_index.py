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

"""The embargo → proposal correlation of a case (ADR-0035 DL-06).

The accept/reject triggers correlate an embargo with the activity that
proposed it through ``VulnerabilityCase.pending_embargo_proposal_index``
rather than by re-reading the wire activity.  Five writers keep it: the
received Invite, the CASE_MANAGER's own propose or revise trigger tree
(``IndexOwnEmbargoProposalNode``), the replica replaying a proposal from the
ledger (EP-09-007), the proposer's replica replaying the Invite relayed on
its behalf, and the CASE_MANAGER's relay of the creation-time revision
(EP-04-011), which indexes its Invite only after sending it.  It records a
correlation and moves no EM state, so it is not an ``EmbargoLifecycle``
operation (BT-15-002).
"""

from vultron.core.ports.case_persistence import CasePersistence
from vultron.errors import VultronNotFoundError


def record_embargo_proposal_index(
    dl: CasePersistence,
    case_id: str,
    embargo_id: str,
    proposal_id: str,
    *,
    overwrite: bool = True,
) -> bool:
    """Record *embargo_id* → *proposal_id* on the case.

    With *overwrite* ``False`` an existing entry is kept: a replica replaying
    a proposal from the ledger must not displace the Invite actually
    addressed to it (EP-09-007).

    Returns:
        ``True`` when the index changed and the case was saved.

    Raises:
        VultronNotFoundError: If *case_id* does not resolve to a case.
    """
    case = dl.read_case(case_id)
    if case is None:
        raise VultronNotFoundError("VulnerabilityCase", case_id)
    current = case.pending_embargo_proposal_index.get(embargo_id)
    if current == proposal_id or (current is not None and not overwrite):
        return False
    # Validated assignment; the register step prunes it (EP-08-003).
    case.pending_embargo_proposal_index = {
        **case.pending_embargo_proposal_index,
        embargo_id: proposal_id,
    }
    dl.save(case)
    return True


__all__ = ["record_embargo_proposal_index"]
