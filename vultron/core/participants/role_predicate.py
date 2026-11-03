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

"""The one sanctioned way to ask whether an actor holds a role in a case.

:func:`has_role` is that question (ADR-0153).  A role belongs to an
``(actor, case)`` pair: an actor can manage one case and be a plain
participant in another, and roles change while a case runs, so the answer is
read from the roster for each message rather than fixed at actor startup
(CM-02-011).

It wraps :meth:`~vultron.core.models.case_participant.CaseParticipant.has_role`
and does not replace it: the method answers about one participant record, and
this answers about an actor in a case, by finding that actor's record in the
case's roster first.

The module sits in the neutral participants layer, below ``behaviors`` and
``use_cases`` and depending only on ``models``, ``ports`` and ``enums``, for
the same reason
:func:`~vultron.core.participants.authority.resolve_case_manager_id` does
(ARCH-24-002).  Authority is the ``CVDRole.CASE_MANAGER`` role, so asking
whether *this* actor is the case's authority is
``has_role(actor_id, case_id, CVDRole.CASE_MANAGER, dl)`` — never a name, a
URL shape or a hosting location (CM-02-011, CM-02-013, ARCH-24-004).
"""

from vultron.core.models._helpers import _as_id
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.participants._lookup import iter_case_participants
from vultron.core.ports.case_persistence import CasePersistence
from vultron.enums.roles import CVDRole
from vultron.primitives import same_actor_id

__all__ = ["has_role"]


def has_role(
    actor_id: str,
    case_id: str,
    role: CVDRole,
    dl: CasePersistence,
) -> bool:
    """True when *actor_id* holds *role* in *case_id*, read fresh (ADR-0153).

    The case is read from *dl*, the actor's own store, on every call: a role
    granted or removed mid-case is answered from the roster as it stands now
    (CM-02-011).  The read is the same cheap one
    :class:`~vultron.core.behaviors.case.nodes.conditions.CheckIsCaseManagerNode`
    already makes per message.

    ``False``, never an error, when the store holds no replica of *case_id*:
    an actor that does not hold the case holds no role in it.  Role stacking
    is a union over the actor's participant records (CM-26-001), so any
    record of *actor_id* that holds *role* answers ``True``.

    Args:
        actor_id: The actor whose roles are in question, usually the
            receiving actor.
        case_id: The case the roles belong to.
        role: The role asked about.
        dl: The store to read the case from — the actor's own replica.

    Returns:
        ``True`` when the case's roster records *actor_id* holding *role*.
    """
    case = dl.read_case(case_id)
    if case is None:
        return False
    for participant in iter_case_participants(case, dl):
        if not isinstance(participant, CaseParticipant):
            continue
        attributed = _as_id(getattr(participant, "attributed_to", None))
        if not attributed or not same_actor_id(attributed, actor_id):
            continue
        if participant.has_role(role):
            return True
    return False
