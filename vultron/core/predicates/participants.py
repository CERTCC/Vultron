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

"""Pure predicate functions over :class:`~vultron.core.models.case_participant.CaseParticipant` lists.

These functions contain no I/O and no HTTP/DataLayer dependencies, making them
independently testable with in-memory objects.  Demo helpers that need to check
convergence state over a live container should fetch participants first, then
delegate to these predicates.
"""

from typing import TYPE_CHECKING

from vultron.core.models.case_participant import CaseParticipant
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole

if TYPE_CHECKING:
    from vultron.core.states.cs import CS_vf


def vendor_vf_invariant_ok(
    roles: list[CVDRole],
    vf_state: "CS_vf | None",
) -> bool:
    """Return True when (roles, vf_state) satisfies the Vendor-implies-V invariant.

    A participant holding ``CVDRole.VENDOR`` is by definition aware of the case;
    their VF state MUST NOT be ``CS_vf.vf`` (vendor-unaware).  ``None`` means
    no VF assertion is being made and is always valid.  Non-vendor roles are
    unconstrained by this rule.

    Per ADR-0084, PRM-06-002.
    """
    if vf_state is None:
        return True
    if CVDRole.VENDOR not in roles:
        return True
    from vultron.core.states.cs import CS_vf  # avoid circular at module level

    return vf_state != CS_vf.vf


def some_vendor_at_vf(participants: list[CaseParticipant]) -> bool:
    """Return ``True`` iff any participant holds ``CVDRole.VENDOR`` with ``vf.state=VF``.

    Pure function; no I/O.  Used as the causal-gate predicate for the
    DEPLOYER-only d→D transition (CSB-15-004): a deployer may only advance
    fix-deployed when at least one vendor has produced a fix.

    A participant with no status record, or whose ``vf`` dimension is ``None``,
    does not satisfy the gate.
    """
    from vultron.core.states.cs import CS_vf  # avoid circular at module level

    for participant in participants:
        if CVDRole.VENDOR not in (participant.case_roles or []):
            continue
        status = participant.participant_status
        if status is None:
            continue
        if status.vf is not None and status.vf.state == CS_vf.VF:
            return True
    return False


def all_participants_rm_closed(
    participants: list[CaseParticipant],
) -> bool:
    """Return ``True`` when every participant is ``RM.CLOSED``.

    Participants with no status records cause the function to return ``False``
    immediately — their convergence state is unknown and must be treated as
    incomplete.

    The CASE_MANAGER is included, not exempt.  It has a full RM lifecycle
    (ADR-0051, CM-23-005) and CM-23-010 makes ``RM.CLOSED`` mean "the Case Owner
    has left and the case is fully closed" for its participant record
    specifically, so a terminal-state check that skipped it would report a case
    closed while its authority still read ``RM.ACCEPTED``.  That is exactly what
    this predicate did, and it is why the demo never noticed ISSUE-2505.
    :class:`~vultron.core.behaviors.status.nodes.conditions
    .AllParticipantsRMClosedConditionNode` dropped the same skip for the same
    reason; this is the surviving copy.

    Args:
        participants: List of :class:`~vultron.core.models.case_participant.CaseParticipant`
            objects to check.  The list may be empty, in which case the
            function returns ``True`` (vacuous convergence).

    Returns:
        ``True`` if all participants have reached ``RM.CLOSED``; ``False``
        otherwise.
    """
    for participant in participants:
        latest = participant.participant_status
        if latest is None:
            return False
        if latest.rm.state != RM.CLOSED:
            return False
    return True
