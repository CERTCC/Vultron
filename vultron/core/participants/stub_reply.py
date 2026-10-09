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

"""The effects of an invitee's reply to the stub Invite, on its participant record.

The ledger holds the wire messages exchanged (ADR-0114).  The invitee sends
``Accept(Invite(stub))`` or ``Reject(Invite(stub))`` to the CASE_MANAGER, and the
entry for that message (``accept_invite_actor_to_case`` or
``reject_invite_actor_to_case``) carries it verbatim: the replying actor, the
stub Invite and the reply's ``published``.  The CASE_MANAGER applies the reply's
effects to the invitee's record when it receives it, and a replica applies the
same effects when it receives the entry, through the functions in this module:

- an Accept signs the invitee's consent to the embargo in force
  (:meth:`CaseParticipant.sign_embargo`, CM-18-005) and marks the record joined;
- a Reject moves the consent row to ``DECLINED`` when an embargo is in force.

A vendor's VF status and the reject's closing status are not here: a status is a
CASE_MANAGER-written object with its own id and times, so it has its own
``add_participant_status_to_participant`` entry.

No id is made and no clock is read: the record's ``updated`` is the reply's
``published`` as received (ADR-0103, CLP-15-007).  Every move is forward only: a
consent row changes only by a legal move (CM-18-003) and ``joined`` is only set,
so a stale entry replayed over a seed that is already ahead changes nothing.
"""

from datetime import datetime

from vultron.core.models._helpers import as_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.states.participant_embargo_consent import PEC_Trigger


def parse_published(value: object) -> datetime:
    """The ``published`` a reply carries, as a UTC datetime.

    Raises ``ValueError`` when it is absent or unreadable: a time the reply does
    not carry is never replaced by the local clock (CLP-15-006).
    """
    stamp: datetime | None = None
    if isinstance(value, datetime):
        stamp = as_utc(value)
    elif isinstance(value, str) and value:
        stamp = as_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    if stamp is None:
        raise ValueError("the reply carries no readable 'published'")
    return stamp


def reply_published(activity: object) -> datetime:
    """The ``published`` of the reply the CASE_MANAGER received.

    *activity* is the received event; its carried activity holds the sender's
    ``published``, the time a replica reads from the same reply's entry.
    """
    carried = getattr(activity, "activity", None)
    return parse_published(getattr(carried, "published", None))


def _later(a: datetime | None, b: datetime) -> datetime:
    return b if a is None else max(a, b)


def mark_joined(record: CaseParticipant, published: datetime) -> bool:
    """Mark *record* joined at the Accept's *published*; False if it was."""
    if record.joined:
        return False
    record.joined = True
    record.updated = _later(record.updated, published)
    return True


def decline_embargo_in_force(
    case: VulnerabilityCase, record: CaseParticipant
) -> bool:
    """Move *record*'s consent row for the embargo in force to ``DECLINED``.

    Applies where the move is legal (CM-18-003, CM-18-005); a case with no
    embargo in force changes nothing.  The caller persists the record.
    """
    embargo_id = case.active_embargo_id
    if not embargo_id:
        return False
    return record.apply_pec_transition_if_legal(
        embargo_id,
        PEC_Trigger.DECLINE,
        entry_status=case.embargo_register_status(embargo_id),
    )


def apply_stub_accept(
    case: VulnerabilityCase, record: CaseParticipant, published: datetime
) -> bool:
    """A replica's application of an ``accept_invite_actor_to_case`` entry.

    The same two writes the CASE_MANAGER's accept tree makes: consent signed to
    the embargo in force through :meth:`CaseParticipant.sign_embargo`, then
    ``joined``.  Returns True when anything changed; the caller saves *record*.
    """
    signed = False
    embargo_id = case.active_embargo_id
    if embargo_id:
        before = record.consent_for(embargo_id)
        record.sign_embargo(embargo_id)
        signed = record.consent_for(embargo_id) != before
    joined = mark_joined(record, published)
    if signed or joined:
        record.updated = _later(record.updated, published)
    return signed or joined


def apply_stub_reject(
    case: VulnerabilityCase, record: CaseParticipant, published: datetime
) -> bool:
    """A replica's application of a ``reject_invite_actor_to_case`` entry.

    The CASE_MANAGER's consent write at a reject: ``DECLINED`` on the embargo in
    force.  The closing RM status is its own entry.  Returns True when the row
    moved; the caller saves *record*.
    """
    moved = decline_embargo_in_force(case, record)
    if moved:
        record.updated = _later(record.updated, published)
    return moved
