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

- an Accept writes the invitee's agreement to the embargo in force, the row
  it states, through the one apply function (:func:`stub_accept_consent`,
  CM-18-005, ADR-0124), and marks the record joined;
- a Reject writes the invitee's refusal of the embargo in force, the row it
  states, through the same apply function (:func:`stub_reject_consent`).

A vendor's VF status and the reject's closing status are not here: a status is a
CASE_MANAGER-written object with its own id and times, so it has its own
``add_participant_status_to_participant`` entry.

No id is made and no clock is read: the record's ``updated`` is the reply's
``published`` as received (ADR-0103, CLP-15-007).  Every move is forward only: a
consent row changes only by a legal move (CM-18-003) and ``joined`` is only set,
so a stale entry replayed over a seed that is already ahead changes nothing.
"""

from collections.abc import Callable
from datetime import datetime

from vultron.core.models._helpers import as_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_apply import (
    ConsentRowChange,
    EmbargoCaseFile,
    apply_embargo_change,
)
from vultron.core.models.embargo_consent_move import (
    joiner_agreement,
    joiner_decline,
)


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


def settle_stub_accept(
    stored: CaseParticipant | None,
    record: CaseParticipant,
    published: datetime,
) -> bool:
    """The CASE_MANAGER's write of the record its accept tree left.

    *record* is *stored* as the tree left it: signed to the embargo in force
    (:func:`stub_accept_consent`), when there is one.  This marks it joined
    and stamps ``updated`` when the Accept moved anything, as
    :func:`apply_stub_accept` does on a replica.  A record that was already
    joined still keeps a consent row the Accept moved.  Returns whether
    *record* must be saved.
    """
    joined = mark_joined(record, published)
    if not joined and record == stored:
        return False
    record.updated = _later(record.updated, published)
    return True


def stub_accept_consent(
    case: VulnerabilityCase, record: CaseParticipant
) -> CaseParticipant:
    """*record* as the consent its ``Accept`` of the stub Invite states leaves it.

    The Accept is the invitee's agreement to the embargo in force
    (CM-10-001), and its own entry is the entry for that row (CLP-07-013):
    the row the Accept states
    (:func:`~vultron.core.models.embargo_consent_move.joiner_agreement`) is
    written through the one apply function (ADR-0124), on the CASE_MANAGER
    and on every replica alike, so both write the same row.  Returns *record*
    itself when the Accept moves no row (no embargo in force, a row that
    already agrees or declined, or a record attributed to no actor);
    otherwise a changed copy.

    Raises:
        VultronEntryRefusedError: the case's participant index does not name
            *record* for its actor, so the row has no record to land on.
    """
    return _stated_consent(case, record, joiner_agreement)


def stub_reject_consent(
    case: VulnerabilityCase, record: CaseParticipant
) -> CaseParticipant:
    """*record* as the consent its ``Reject`` of the stub Invite states leaves it.

    The Reject is the invitee's refusal of the embargo in force (CM-11-007),
    and its own entry is the entry for that row (CLP-07-013): the row the
    Reject states (:func:`~vultron.core.models.embargo_consent_move
    .joiner_decline`) is written through the one apply function (ADR-0124),
    on the CASE_MANAGER and on every replica alike.  Returns *record* itself
    when the Reject moves no row (no embargo in force, a row that already
    declined, or a record attributed to no actor); otherwise a changed copy.

    Raises:
        VultronEntryRefusedError: the case's participant index does not name
            *record* for its actor, so the row has no record to land on.
    """
    return _stated_consent(case, record, joiner_decline)


def _stated_consent(
    case: VulnerabilityCase,
    record: CaseParticipant,
    stated: Callable[[EmbargoCaseFile, str], ConsentRowChange | None],
) -> CaseParticipant:
    """*record* with the row a stub reply states, written by copying it."""
    actor_id = record.attributed_to
    if actor_id is None:
        return record
    case_file = EmbargoCaseFile(case=case, participants={actor_id: record})
    change = stated(case_file, actor_id)
    if change is None:
        return record
    return apply_embargo_change(case_file, change).participants[actor_id]


def apply_stub_accept(
    case: VulnerabilityCase, record: CaseParticipant, published: datetime
) -> CaseParticipant | None:
    """A replica's application of an ``accept_invite_actor_to_case`` entry.

    The same two writes the CASE_MANAGER's accept tree makes: the consent the
    Accept states (:func:`stub_accept_consent`), then ``joined``.  Returns
    the changed record for the caller to save, or ``None`` when nothing
    changed.
    """
    signed = stub_accept_consent(case, record)
    updated = signed if signed is not record else record.model_copy(deep=True)
    joined = mark_joined(updated, published)
    if signed is record and not joined:
        return None
    updated.updated = _later(updated.updated, published)
    return updated


def apply_stub_reject(
    case: VulnerabilityCase, record: CaseParticipant, published: datetime
) -> CaseParticipant | None:
    """A replica's application of a ``reject_invite_actor_to_case`` entry.

    The CASE_MANAGER's consent write at a reject: the row the Reject states
    (:func:`stub_reject_consent`).  The closing RM status is its own entry.
    Returns the changed record for the caller to save, or ``None`` when the
    row did not move.
    """
    declined = stub_reject_consent(case, record)
    if declined is record:
        return None
    declined.updated = _later(declined.updated, published)
    return declined
