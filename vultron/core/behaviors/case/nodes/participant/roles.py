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

"""Resolve a case's participant actors by the CVD role they hold.

Split out of ``common.py``, which had grown past the BTND-07-004 leaf-module
ceiling.  These belong together and apart from the rest: every function here
answers one question — *which actor holds this role on this case* — by reading
``CaseParticipant.case_roles`` rather than by comparing actor ids against
``VulnerabilityCase.attributed_to``.  That distinction is the whole point of the
module (CM-21-002), and it is easier to hold onto when the role lookups are not
interleaved with participant creation and status-transition helpers.
"""

from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.participants._lookup import iter_case_participants
from vultron.core.ports.case_persistence import CasePersistence
from vultron.enums.roles import CVDRole


def resolve_participant_actor_by_role(
    case: VulnerabilityCase,
    dl: CasePersistence,
    role: CVDRole,
) -> str | None:
    """Return the actor ID of the participant holding *role*, or None.

    Delegates to :func:`~vultron.core.participants._lookup.iter_case_participants`
    for the two-phase participant scan (fast path via ``actor_participant_index``,
    bootstrap fallback via ``case_participants``).
    """
    for p in iter_case_participants(case, dl):
        if role in p.roles:
            return _as_id(getattr(p, "attributed_to", None))
    return None


def resolve_case_owner_id(
    case: VulnerabilityCase,
    dl: CasePersistence,
) -> str | None:
    """Return the actor ID of the CASE_OWNER participant, or None.

    ``VulnerabilityCase.attributed_to`` is *not* a substitute here.  In the
    Case Owner's own store the two agree (CM-02-008), but in the CaseActor's
    store ``attributed_to`` names the **CaseActor** — it authored that case
    (CM-22-001, CP-05-003, ADR-0041/ADR-0023).  Reading ``attributed_to`` there
    and calling the result "the Case Owner" addresses the CaseActor's own
    messages to itself, which is how the fcvcv ADR-0026 chain stalled: the
    ``Offer(CaseParticipant)`` never reached the owner, so
    ``accept-actor-recommendation`` had nothing to accept and returned 422.

    Role membership is the authoritative record of ownership: CM-21-002 keeps
    ``attributed_to`` in sync with it precisely *because* role-gated nodes
    "determine case-owner authority by reading ``CaseParticipant.case_roles``,
    not by comparing actor IDs against ``attributed_to``".
    """
    return resolve_participant_actor_by_role(case, dl, CVDRole.CASE_OWNER)
