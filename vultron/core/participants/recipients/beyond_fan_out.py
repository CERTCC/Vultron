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

"""Participants the case-content fan-out does not reach, and what they are owed.

Inert and inactive joined participants (CM-10-005, CM-10-006), the
recipients of an Invite sent so that a participant can consent (EP-09-002),
and the bound signatories owed a direct notice when their embargo ends or
shortens (CM-31-009, CM-31-030).
"""

from collections.abc import Collection

from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.participants.recipients.case_content import (
    case_content_recipients,
)
from vultron.core.participants.recipients.roster import (
    _resolve_record,
    _roster_records,
    _select,
)
from vultron.core.ports.case_persistence import CasePersistence


def inert_participants(
    case: VulnerabilityCase, dl: CasePersistence
) -> set[str]:
    """Return the roster actor IDs of *case* that are sent no case content.

    The complement of :func:`case_content_recipients` over the roster, for a
    caller that reports whom a send withheld content from: the participants
    that are not active (CM-10-004) and those at RM ``CLOSED`` (CM-23-004).
    """
    active = set(case_content_recipients(case, dl))
    return set(case.actor_participant_index) - active


def inactive_joined_participants(
    case: VulnerabilityCase,
    dl: CasePersistence,
    *,
    excluding: Collection[str] = (),
) -> list[str]:
    """Return the actor IDs of the joined participants that are not active.

    A joined participant that is not active: it is not a signatory to the
    active embargo (CM-10-004), or it carries the removal fact (CM-31-001).
    These are the participants whose ledger stream is paused and backfilled
    on admission (CM-10-005, CM-10-006); a removed participant is admitted
    when the fact is cleared (CM-31-034).  A participant that has not joined
    is left out: it is inert whatever the embargo, and its case copy and
    ledger arrive through the join path (ADR-0114).  A participant at RM
    ``CLOSED`` is left out too: it has left, so it is sent nothing further
    and has no stream to pause or backfill (CM-23-004).  A roster entry
    whose record cannot be read is left out as well;
    :func:`case_content_recipients` already names it.  Roster order is
    kept, minus *excluding*.
    """
    withheld: list[str] = []
    for actor_id, record in _roster_records(case, dl):
        if actor_id in excluding or record is None or not record.joined:
            continue
        if record.rm_closed:
            continue
        if not case.is_active_participant(record):
            withheld.append(actor_id)
    return withheld


def invitation_recipients(
    case: VulnerabilityCase,
    dl: CasePersistence,
    *,
    excluding: Collection[str] = (),
) -> list[str]:
    """Return the actor IDs a consent Invite on *case* is addressed to.

    Every participant whose RM is not ``CLOSED``, active or inert, minus
    *excluding* (EP-09-002, CM-10-009).  An Invite asks the participant to
    consent; an inert participant is exactly the one that needs asking, so
    the active check does not apply.  A participant that never joined is
    included: it is not ``CLOSED``.  A removed participant is not: the Case
    Owner took it out, and asking it to vote on embargo terms would undo that
    decision (CM-31-013, ADR-0116).  The embargo-ending notices it is still
    owed (CM-31-009) are not Invites and do not come here.
    """
    return [
        actor_id
        for actor_id, _record in _select(
            case,
            dl,
            excluding,
            lambda p: not p.rm_closed and not p.removed,
            "invitation",
        )
    ]


def _beyond_fan_out(record: CaseParticipant) -> bool:
    """True when the ledger fan-out no longer reaches *record* (CM-31-009).

    It was removed (CM-31-001), or it left the case and CM-23-004 skips it
    at RM ``CLOSED``.
    """
    return record.removed or record.rm_closed


def embargo_ending_notice_recipients(
    case: VulnerabilityCase,
    dl: CasePersistence,
    embargo_id: str,
    *,
    excluding: Collection[str] = (),
) -> list[str]:
    """Return the actor IDs owed a direct notice that *embargo_id* ended.

    A joined participant that is a signatory to *embargo_id* — its row
    for it is ``AGREED`` — and that the ledger fan-out no longer reaches:
    removed (CM-31-001), or at RM ``CLOSED`` (CM-23-004).  Such a
    participant stays bound (CM-31-008) and cannot learn from the ledger
    that the embargo was terminated or shortened, so the CASE_MANAGER tells
    it directly (CM-31-009).  A participant that declined, or an invitee
    that never joined, is not bound and is not sent anything.

    *embargo_id* is the embargo that is ending: the one terminated, or the
    one a shorter revision replaces.  Consent rows outlive both moves
    (MSM-07-025, EP-05-003), so the selection is the same before and after
    the EM write.  The notice is not case content (CM-10-007), so the active
    check does not apply.  Roster order is kept, minus *excluding*.

    An *embargo_id* the register does not hold has no signatories to notify:
    every participant's rows cover the register's entries (ADR-0122), so
    ``is_signatory`` would have no row to read.  Return nothing rather than
    reading a row that cannot exist.
    """
    if case.embargo_register_entry(embargo_id) is None:
        return []
    return [
        actor_id
        for actor_id, _record in _select(
            case,
            dl,
            excluding,
            lambda p: _owed_ending_notice(p, embargo_id),
            "embargo-ending notice",
        )
    ]


def _owed_ending_notice(record: CaseParticipant, embargo_id: str) -> bool:
    """True when *record* is owed a CM-31-009 notice that *embargo_id* ended.

    Joined, a signatory to *embargo_id*, and beyond the ledger fan-out.
    The one rule both sides read: the CASE_MANAGER to pick the recipients,
    the paused replica to decide whether a notice is one it can be owed.
    """
    return (
        record.joined
        and record.is_signatory(embargo_id)
        and _beyond_fan_out(record)
    )


def awaits_embargo_ending_notice(
    case: VulnerabilityCase, dl: CasePersistence, actor_id: str
) -> bool:
    """True when *actor_id* can be owed a CM-31-009 notice on *case*.

    Read in the participant's own replica, about itself (CM-31-010): it is
    joined and a signatory of the embargo its replica has in force, and the
    ledger fan-out no longer reaches it (removed, or at RM ``CLOSED``).
    This is :func:`embargo_ending_notice_recipients` seen from the receiver,
    so a replica applies only a notice the CASE_MANAGER would send it.  A
    participant withheld under CM-10-005 is paused too
    (:func:`ledger_stream_paused`) but is never a signatory of the embargo
    in force, so no notice is owed to it: an ``Announce(EmbargoEvent)`` it
    receives is the teardown announcement, not a shorter revision.  An
    actor the case does not list, whose record does not resolve, or a case
    with no embargo in force, awaits nothing.
    """
    embargo_id = case.active_embargo_id
    participant_id = case.actor_participant_index.get(actor_id)
    if embargo_id is None or participant_id is None:
        return False
    record = _resolve_record(case, dl, participant_id)
    return record is not None and _owed_ending_notice(record, embargo_id)


def ledger_stream_paused(
    case: VulnerabilityCase, dl: CasePersistence, actor_id: str
) -> bool:
    """True when *actor_id*'s ledger stream on *case* is paused (CM-31-010).

    A participant is paused when it is not active (CM-10-005, CM-31-001) or
    when it is at RM ``CLOSED`` (CM-23-004): the ledger no longer brings it
    the case's changes.  Read in the participant's own replica, about
    itself, to decide whether a direct embargo-ending notice from the
    CASE_MANAGER is its only channel.  An actor the case does not list, or
    whose record does not resolve, is not a paused participant.
    """
    participant_id = case.actor_participant_index.get(actor_id)
    if participant_id is None:
        return False
    record = _resolve_record(case, dl, participant_id)
    if record is None:
        return False
    return record.rm_closed or not case.is_active_participant(record)
