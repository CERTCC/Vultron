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

"""The one place an invitee's inert participant record is born and joins (CM-11-006).

When the CASE_MANAGER sends a stub Invite it records the invitee in the same
step: RM ``RECEIVED``, VF ``vf`` for a vendor, PEC ``INVITED`` when an embargo
is active, ``joined=False`` (inert, CM-10-004).  When the invitee accepts, the
CASE_MANAGER consents the invitee to the embargo in force, marks the record
joined and advances a vendor's VF to ``Vf``.  A replica applying the stub
Invite's ledger entry, and later the ``Accept(Invite)`` entry, makes the same
changes (CM-11-006, CM-31-012).  Both sides call the functions in this module,
so the two cannot drift: a replica makes no choice of its own, it derives the
record from the entry and from its own case at that ledger position.

Nothing here reads a clock or mints a random id (ADR-0124, ADR-0103).  Every id
and time is derived from the activity that causes the change: a status id is a
``uuid5`` of the causing activity's id and the invitee (as the creation-time
embargo's id is derived from its case, EP-04-012), and ``published`` and
``updated`` are the causing activity's ``published``.
"""

import uuid
from datetime import datetime

from vultron.core.models._helpers import as_utc
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


def parse_stamp(value: object) -> datetime:
    """Read the ``published`` an entry's snapshot carries as a UTC datetime.

    Raises ``ValueError`` when it is absent or unreadable: a time the entry does
    not carry is never replaced by the local clock (CLP-15-006, ADR-0103).
    """
    if isinstance(value, datetime):
        stamp: datetime | None = as_utc(value)
    elif isinstance(value, str) and value:
        stamp = as_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    else:
        stamp = None
    if stamp is None:
        raise ValueError("the activity carries no readable 'published'")
    return stamp


def derived_status_id(activity_id: str, invitee_id: str, step: str) -> str:
    """The id of the status *activity_id* causes for *invitee_id* at *step*.

    A pure function of the causing activity, so the CASE_MANAGER and every
    replica name the same status (ADR-0124).
    """
    name = f"{activity_id}#participant-status/{step}/{invitee_id}"
    return f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, name)}"


def build_inert_invitee_participant(
    case: VulnerabilityCase,
    invitee_id: str,
    roles: list[CVDRole],
    *,
    invite_id: str,
    published: datetime,
) -> CaseParticipant:
    """Build the inert record for *invitee_id* in *case* (not yet stored).

    The birth status is a single RM ``RECEIVED`` status (PRM-06-001), with VF
    ``vf`` only when *roles* holds ``VENDOR`` (CM-11-009): VF is a vendor-only
    status, and any other invitee's status carries none.  When *case* has an
    active embargo the record's consent row for it moves to ``INVITED``
    (CM-11-006).  *invite_id* and *published* are the stub Invite's, from which
    the status id and every time on the record are derived.  Raises
    ``ValueError`` when *roles* is empty: an Invite names the invitee's roles
    (CM-11-019).
    """
    if not roles:
        raise ValueError(
            f"no roles for invitee '{invitee_id}' — an Invite must name them"
            " (CM-11-019)"
        )
    vf = VfDimension(state=CS_vf.vf) if CVDRole.VENDOR in roles else None
    status = ParticipantStatus(
        id_=derived_status_id(invite_id, invitee_id, "invited"),
        context=case.id_,
        attributed_to=invitee_id,
        rm=RmDimension(state=RM.RECEIVED),
        vf=vf,
        cvd_role=roles,
        published=published,
        updated=published,
    )
    participant = CaseParticipant(
        id_=inert_invitee_participant_id(case.id_, invitee_id),
        attributed_to=invitee_id,
        context=case.id_,
        case_roles=roles,
        participant_statuses=[status],
        joined=False,
        published=published,
        updated=published,
    )
    # The record gets an UNINVITED row for every register entry before it is
    # first stored, then INVITE on the embargo in force (ADR-0122, CM-11-006).
    participant.write_uninvited_rows(case.register_embargo_ids)
    embargo_id = embargo_in_force_id(case)
    if embargo_id:
        participant.apply_pec_transition_if_legal(
            embargo_id,
            PEC_Trigger.INVITE,
            entry_status=case.embargo_register_status(embargo_id),
        )
    return participant


def embargo_in_force_id(case: VulnerabilityCase) -> str | None:
    """The id of the embargo in force in *case*, or ``None``.

    In force means EM ``ACTIVE``, or ``REVISE`` while the prior terms still
    hold; a joiner signs the terms in force, never an open revision (CM-10-001).
    """
    return case.active_embargo_id


def sign_embargo_in_force(
    case: VulnerabilityCase, record: CaseParticipant
) -> bool:
    """Consent *record* to the embargo in force; True when now AGREED.

    The one consent write at the stub Accept, through
    :meth:`CaseParticipant.sign_embargo` (CM-18-005).  It applies to every role.
    A case with no embargo in force changes nothing.
    """
    embargo_id = embargo_in_force_id(case)
    return embargo_id is not None and record.sign_embargo(embargo_id)


def mark_joined(record: CaseParticipant, published: datetime) -> bool:
    """Mark *record* joined at the Accept's *published*; False if it was."""
    if record.joined:
        return False
    record.joined = True
    record.updated = published
    return True


def advance_vf_to_vendor_aware(
    record: CaseParticipant, accept_id: str, published: datetime
) -> bool:
    """Record VF ``Vf`` on a VENDOR *record* still at ``vf``; False otherwise.

    VF is a vendor-only status (CM-11-009): a record without the VENDOR role is
    never given one.  The new status copies the latest and moves only VF.
    """
    if CVDRole.VENDOR not in record.case_roles:
        return False
    if not record.participant_statuses:
        return False
    latest = record.participant_statuses[-1]
    if latest.vf is None or latest.vf.state != CS_vf.vf:
        return False
    record.add_participant_status(
        ParticipantStatus(
            id_=derived_status_id(
                accept_id, latest.attributed_to or "", "vendor-aware"
            ),
            context=latest.context,
            attributed_to=latest.attributed_to,
            rm=latest.rm.model_copy(),
            vf=VfDimension(state=CS_vf.Vf),
            d=latest.d.model_copy() if latest.d is not None else None,
            cvd_role=list(latest.cvd_role),
            published=published,
            updated=published,
        )
    )
    record.updated = published
    return True


def apply_stub_accept(
    case: VulnerabilityCase,
    record: CaseParticipant,
    accept_id: str,
    published: datetime,
) -> bool:
    """Apply the CASE_MANAGER's effects of the stub Accept to *record*.

    Consent to the embargo in force, then ``joined``, then a vendor's VF to
    ``Vf``: the order the CASE_MANAGER's accept tree runs them.  A joined record
    is left as it is (a replay).  Returns True when anything changed; the
    caller saves the record.
    """
    if record.joined:
        return False
    sign_embargo_in_force(case, record)
    mark_joined(record, published)
    advance_vf_to_vendor_aware(record, accept_id, published)
    return True


def accept_activity_stamp(activity: object) -> tuple[str, datetime]:
    """The id and ``published`` of the received ``Accept`` the CASE_MANAGER holds.

    *activity* is the received event; its carried activity holds the sender's
    ``published``, the time a replica reads from the same Accept's ledger entry.
    Raises ``ValueError`` when either is absent (CLP-15-006).
    """
    accept_id = getattr(activity, "activity_id", None)
    carried = getattr(activity, "activity", None)
    published = getattr(carried, "published", None)
    if not isinstance(accept_id, str) or not accept_id:
        raise ValueError("the Accept carries no activity id")
    return accept_id, parse_stamp(published)
