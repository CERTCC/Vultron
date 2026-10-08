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

"""Reading and stamping the lifetime of a stub Invite (CM-11-014..016).

A stub ``Invite(Actor, CaseStub)`` is an ask with a deadline (ASK-03-004).  The
CASE_MANAGER stamps ``Invite.end_time`` the way it stamps an embargo Invite's
(CM-28-012, :func:`~vultron.core.behaviors.embargo.rsvp_stamp.stamp_rsvp_deadline`),
and every question about the Invite's life is answered from the CASE_MANAGER's
own recorded copy:

- **Expired** — ``now >= end_time``, the comparison an embargo Invite's expiry
  makes (``EmbargoLifecycle.assess_invite_expiry``).  Expiry closes the *ask*
  and writes no participant state (CM-11-014): the invitee's record stays
  inert at RM ``RECEIVED``.  Its consequence is *void* (ASK-03-002): a late
  ``Accept`` joins nobody, so the invitee has to be re-invited (CM-11-015).
- **Superseded** — a later stub Invite names it in ``supersedes`` after the
  active embargo changed (CM-11-016).  An ``Accept`` is refused naming the
  replacement; a ``Reject`` is honoured.
- **Outstanding** — the invitee's record is inert (``joined=False``) and not
  ``RM.CLOSED``, and the newest Invite to it has not expired.

Nothing here writes; the nodes in ``nodes/stub_invite_lifetime.py`` act on
what it reports.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.predicates.addressing import same_actor_id
from vultron.core.states.em import EM

#: EM states in which an embargo proposal is open and undecided.
_PENDING_EM_STATES = frozenset({EM.PROPOSED, EM.REVISE})

_EARLIEST = datetime.min.replace(tzinfo=UTC)


@dataclass(frozen=True)
class RecordedStubInvite:
    """The CASE_MANAGER's record of one stub Invite, as the lifetime rules read it.

    Attributes:
        invite_id: The Invite's id.
        invitee_id: The invited actor (the Invite's ``object``).
        case_id: The case the stub names.
        published: When the Invite was sent.
        end_time: The reply deadline, or ``None`` for an Invite sent before
            deadlines existed (such an Invite never expires).
        supersedes: The Invite this one replaces, if it replaces one.
        embargo_id: The embargo whose terms the stub carried, or ``None``
            when it carried none.
        roles: The roles the Invite offers the invitee.
        attributed_to: The participant on whose behalf it was sent, if any.
    """

    invite_id: str
    invitee_id: str
    case_id: str
    published: datetime
    end_time: datetime | None
    supersedes: str | None
    embargo_id: str | None
    roles: tuple[str, ...]
    attributed_to: str | None


def stub_invite_expired(invite: RecordedStubInvite, now: datetime) -> bool:
    """True when *invite*'s reply deadline has passed.

    The boundary is the embargo Invite's: the deadline having *arrived*
    (``now == end_time``) is expired, as in ``assess_invite_expiry``.
    """
    return invite.end_time is not None and now >= invite.end_time


def record_of(obj: Any) -> RecordedStubInvite | None:
    """Read *obj* as a stub Invite record, or ``None`` when it is not one.

    A stub Invite is told apart by its target: a stub names its case in
    ``case_id`` (CM-11-013).  Any other Invite, including the full-case Invite
    and an embargo Invite, is not one.
    """
    target = getattr(obj, "target", None)
    case_id = getattr(target, "case_id", None)
    invitee_id = _as_id(getattr(obj, "object_", None))
    invite_id = getattr(obj, "id_", None)
    if not isinstance(case_id, str) or not invitee_id or not invite_id:
        return None
    embargo = getattr(target, "active_embargo", None)
    return RecordedStubInvite(
        invite_id=invite_id,
        invitee_id=invitee_id,
        case_id=case_id,
        published=getattr(obj, "published", None) or _EARLIEST,
        end_time=getattr(obj, "end_time", None),
        supersedes=getattr(obj, "supersedes", None),
        embargo_id=_as_id(embargo) if embargo is not None else None,
        roles=tuple(getattr(obj, "roles", None) or ()),
        attributed_to=_as_id(getattr(obj, "attributed_to", None)),
    )


def recorded_stub_invites(
    dl: CasePersistence,
    case_id: str,
    issuer_id: str,
    invitee_id: str | None = None,
) -> list[RecordedStubInvite]:
    """Every stub Invite *issuer_id* recorded for *case_id*, oldest first.

    Args:
        dl: The issuer's own store.
        case_id: The case the stubs name.
        issuer_id: The CASE_MANAGER that issued them; Invites another actor
            issued are not its to answer for (CM-11-017).
        invitee_id: Restrict to one invitee.
    """
    found: list[RecordedStubInvite] = []
    for obj in dl.list_objects("Invite"):
        issuer = _as_id(getattr(obj, "actor", None))
        if issuer is None or not same_actor_id(issuer, issuer_id):
            continue
        record = record_of(obj)
        if record is None or record.case_id != case_id:
            continue
        if invitee_id is not None and not same_actor_id(
            record.invitee_id, invitee_id
        ):
            continue
        found.append(record)
    return sorted(found, key=lambda r: r.published)


def replacement_for(
    invite: RecordedStubInvite, siblings: list[RecordedStubInvite]
) -> RecordedStubInvite | None:
    """The stub Invite that supersedes *invite*, or ``None`` while it is current.

    A replacement supersedes *invite* when it names it, or names a stub sent
    no earlier than it (an older stub that stayed live after a re-invite is
    superseded by the replacement of the newer one: the terms it carried are
    gone too, CM-11-016).  The newest such replacement wins.
    """
    by_id = {s.invite_id: s for s in siblings}
    candidates = []
    for sibling in siblings:
        if sibling.supersedes is None or sibling.invite_id == invite.invite_id:
            continue
        named = by_id.get(sibling.supersedes)
        if sibling.supersedes == invite.invite_id or (
            named is not None and named.published >= invite.published
        ):
            candidates.append(sibling)
    return max(candidates, key=lambda r: r.published, default=None)


def unanswerable_reason(
    invite: RecordedStubInvite,
    siblings: list[RecordedStubInvite],
    now: datetime,
) -> str | None:
    """Why an ``Accept`` of *invite* must be refused, or ``None`` if it may stand.

    A superseded stub is refused naming its replacement (CM-11-016).  An
    expired stub is refused because a late ``Accept`` is void (CM-11-014,
    ASK-03-002): the invitee must be re-invited (CM-11-015).  A ``Reject`` is
    never refused on either ground, so callers ask this of an ``Accept`` only.
    """
    replacement = replacement_for(invite, siblings)
    if replacement is not None:
        return (
            f"Invite '{invite.invite_id}' was superseded by"
            f" '{replacement.invite_id}' after the embargo changed — Accept"
            f" '{replacement.invite_id}' instead (CM-11-016)"
        )
    if stub_invite_expired(invite, now):
        return (
            f"Invite '{invite.invite_id}' expired at {invite.end_time} — an"
            " Accept after the deadline joins nobody; the invitee must be"
            " re-invited (CM-11-014, ASK-03-002)"
        )
    return None


def current_stub_embargo_id(case: VulnerabilityCase) -> str | None:
    """The embargo whose terms a stub Invite sent now would carry.

    A stub carries the active embargo only while EM is ``ACTIVE`` (CM-17-002);
    otherwise it carries none.
    """
    if case.current_status.em.state != EM.ACTIVE:
        return None
    return case.active_embargo_id


def current_stub_embargo_end(
    dl: CasePersistence, case: VulnerabilityCase
) -> datetime | None:
    """The end of the embargo a stub sent now would carry; caps its deadline."""
    embargo_id = current_stub_embargo_id(case)
    if embargo_id is None:
        return None
    embargo = dl.read(embargo_id)
    return embargo.end_time if isinstance(embargo, EmbargoEvent) else None


def invitee_record(
    dl: CasePersistence, case: VulnerabilityCase, invitee_id: str
) -> CaseParticipant | None:
    """The invitee's participant record in *case*, or ``None``."""
    participant_id = case.actor_participant_index.get(invitee_id)
    if participant_id is None:
        return None
    record = dl.read(participant_id)
    return record if isinstance(record, CaseParticipant) else None


def awaiting_stub_reply(participant: CaseParticipant | None) -> bool:
    """True when *participant* is an invitee that has neither joined nor closed.

    This is the whole of "has not answered": an ``Accept`` sets ``joined`` and
    a ``Reject`` closes RM, and an expired Invite changes neither
    (CM-11-014).
    """
    return (
        participant is not None
        and not participant.joined
        and not participant.rm_closed
    )


def outstanding_stale_stubs(
    dl: CasePersistence,
    case: VulnerabilityCase,
    issuer_id: str,
    now: datetime,
) -> list[RecordedStubInvite]:
    """The stub Invites the active embargo's change has left carrying old terms.

    Nothing is stale while a proposal is open (EM ``PROPOSED`` or ``REVISE``):
    a proposal alone re-issues nothing.  Otherwise, one per invitee: its
    newest stub, when the invitee has not answered
    (:func:`awaiting_stub_reply`), that stub has not expired and is not
    already superseded, and the embargo it carried is not the one a stub sent
    now would carry (CM-11-016).  An expired, unanswered stub is not
    re-issued; the CASE_MANAGER re-invites it on request (CM-11-015).
    """
    if case.current_status.em.state in _PENDING_EM_STATES:
        # A proposal (or a revision of the embargo in force) is open.  It
        # changes no active embargo, so it re-issues nothing; the answer that
        # activates or ends it does (CM-11-016).
        return []
    wanted = current_stub_embargo_id(case)
    stale: list[RecordedStubInvite] = []
    by_invitee: dict[str, list[RecordedStubInvite]] = {}
    for stub in recorded_stub_invites(dl, case.id_, issuer_id):
        by_invitee.setdefault(stub.invitee_id, []).append(stub)
    for invitee_id, stubs in by_invitee.items():
        newest = stubs[-1]
        if not awaiting_stub_reply(invitee_record(dl, case, invitee_id)):
            continue
        if stub_invite_expired(newest, now):
            continue
        if replacement_for(newest, stubs) is not None:
            continue
        if newest.embargo_id != wanted:
            stale.append(newest)
    return stale
