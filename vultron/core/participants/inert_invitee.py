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

"""The one builder of an invitee's inert participant record (CM-11-006).

When the CASE_MANAGER sends a stub Invite it records the invitee in the same
step: RM ``RECEIVED``, VF ``vf`` for a vendor, PEC ``INVITED`` when an embargo
is active, ``joined=False`` (inert, CM-10-004).  A replica applying the stub
Invite's ledger entry builds the same record (CM-11-006, CM-31-012).  Both
call :func:`build_inert_invitee_participant`, so the two cannot drift: a
replica makes no choice of its own, it derives the record from the entry and
from its own case at that ledger position.
"""

from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import RmDimension, VfDimension
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.states.cs import CS_vf
from vultron.core.states.participant_embargo_consent import PEC_Trigger
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole


def inert_invitee_participant_id(case_id: str, invitee_id: str) -> str:
    """The id of the invitee's participant record in *case_id*."""
    return f"{case_id}/participants/{invitee_id.rsplit('/', maxsplit=1)[-1]}"


def build_inert_invitee_participant(
    case: VulnerabilityCase, invitee_id: str, roles: list[CVDRole]
) -> CaseParticipant:
    """Build the inert record for *invitee_id* in *case* (not yet stored).

    The birth status is a single RM ``RECEIVED`` status (PRM-06-001), with VF
    ``vf`` when *roles* holds ``VENDOR`` (CM-11-009).  When *case* has an
    active embargo the record's consent row for it moves to ``INVITED``
    (CM-11-006).  Raises ``ValueError`` when *roles* is empty: an Invite names
    the invitee's roles (CM-11-019).
    """
    if not roles:
        raise ValueError(
            f"no roles for invitee '{invitee_id}' — an Invite must name them"
            " (CM-11-019)"
        )
    vf = VfDimension(state=CS_vf.vf) if CVDRole.VENDOR in roles else None
    status = ParticipantStatus(
        context=case.id_,
        attributed_to=invitee_id,
        rm=RmDimension(state=RM.RECEIVED),
        vf=vf,
        cvd_role=roles,
    )
    participant = CaseParticipant(
        id_=inert_invitee_participant_id(case.id_, invitee_id),
        attributed_to=invitee_id,
        context=case.id_,
        case_roles=roles,
        participant_statuses=[status],
        joined=False,
    )
    active_embargo_id = _as_id(case.active_embargo)
    if active_embargo_id and participant.accepts_pec_trigger(
        active_embargo_id, PEC_Trigger.INVITE
    ):
        participant.apply_pec_transition(active_embargo_id, PEC_Trigger.INVITE)
    return participant
