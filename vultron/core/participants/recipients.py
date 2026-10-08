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
"""The shared recipient selection for messages about a case (CM-10-007).

Every send that addresses a case's participants picks its recipients here,
so the entitlement check cannot be forgotten at a send site.  Two audiences
exist, and they differ on purpose (ADR-0114 § "Inert and active"):

- :func:`case_content_recipients` — *case content*: ledger entries, case
  announcements, status broadcasts, embargo announcements.  Only **active**
  participants (:meth:`VulnerabilityCase.is_active_participant`, CM-10-004).
  ``skip_closed=True`` also leaves out participants at RM ``CLOSED``, for
  the fan-out that names CM-23-004.
- :func:`inactive_joined_participants` — the joined participants that are
  not active, whose ledger streams are paused and backfilled on admission
  (CM-10-005, CM-10-006): the active embargo withholds them, or they were
  removed (CM-31-001).
- :func:`invitation_recipients` — an Invite addressed to a participant *so
  that* it can consent (the relayed embargo Invite, EP-09-002).  Every
  participant whose RM is not ``CLOSED``, inert ones included (CM-10-007).
- :func:`embargo_ending_notice_recipients` — the bound signatories the
  ledger fan-out no longer reaches, owed a direct notice when their embargo
  ends or shortens (CM-31-009).  Not case content (CM-10-007).

Each reads the roster (``actor_participant_index``) and resolves each entry to
its participant record.  A roster entry whose record cannot be read is not
provably entitled, so it is left out and logged at WARNING: leaking case
content to an actor the case cannot vouch for is the failure CM-10-004
exists to prevent.

Roster order is kept, and an unresolvable entry is named, which is why this
walks the index itself rather than :func:`iter_case_participants` (that yields
records only, in no fixed order, and skips what it cannot read silently).
Record precedence matches it: the stored record first, an inline copy only as
the fallback.

The report-flow ``Create(Case)`` does not come here:
``case_creation._collect_create_case_addressees`` builds its addressees from
the actor, the report and the offer rather than the roster, and every one of
them is seated at case initialization.

This module is the one place in ``vultron/core/`` that lists roster actor
IDs for addressing; ``test/architecture/test_active_participant_recipient_selection.py``
holds every other module to that.
"""

import logging
from collections.abc import Callable, Collection, Iterator

from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.ports.case_persistence import CasePersistence

logger = logging.getLogger(__name__)


def _resolve_record(
    case: VulnerabilityCase, dl: CasePersistence, participant_id: str
) -> CaseParticipant | None:
    """Return the record *participant_id* names, or ``None`` if none resolves.

    The stored record wins over an inline copy the case carries, the same
    precedence as :func:`iter_case_participants`: the consent cascades and
    every other participant write save the stored record, so an inline copy
    can be stale.  The inline copy is the fallback for a case whose records
    are not stored yet (bootstrap).
    """
    stored = dl.read(participant_id)
    if isinstance(stored, CaseParticipant):
        return stored
    for entry in case.case_participants:
        if isinstance(entry, CaseParticipant) and entry.id_ == participant_id:
            return entry
    return None


def _roster_records(
    case: VulnerabilityCase, dl: CasePersistence
) -> Iterator[tuple[str, CaseParticipant | None]]:
    """Yield ``(actor_id, record)`` for every roster entry of *case*."""
    for actor_id, participant_id in case.actor_participant_index.items():
        yield actor_id, _resolve_record(case, dl, participant_id)


def _select(
    case: VulnerabilityCase,
    dl: CasePersistence,
    excluding: Collection[str],
    entitled: Callable[[CaseParticipant], bool],
    audience: str,
) -> list[tuple[str, CaseParticipant]]:
    recipients: list[tuple[str, CaseParticipant]] = []
    for actor_id, record in _roster_records(case, dl):
        if actor_id in excluding:
            continue
        if record is None:
            logger.warning(
                "case '%s': no participant record for roster actor '%s'"
                " — left out of the %s recipients (CM-10-004)",
                case.id_,
                actor_id,
                audience,
            )
            continue
        if entitled(record):
            recipients.append((actor_id, record))
        else:
            logger.debug(
                "case '%s': '%s' is not among the %s recipients (ADR-0114)",
                case.id_,
                actor_id,
                audience,
            )
    return recipients


def case_content_participants(
    case: VulnerabilityCase,
    dl: CasePersistence,
    *,
    excluding: Collection[str] = (),
    skip_closed: bool = False,
) -> list[tuple[str, CaseParticipant]]:
    """Return ``(actor_id, record)`` for *case*'s active participants.

    The same selection as :func:`case_content_recipients`, with the record
    each actor ID resolved to, for a caller that narrows the recipients
    further by a record field (a role, say).  Reading the record again
    would lose an inline-only record this selection already resolved.
    """
    if skip_closed:
        return _select(
            case,
            dl,
            excluding,
            lambda p: case.is_active_participant(p) and not p.rm_closed,
            "open case-content",
        )
    return _select(
        case, dl, excluding, case.is_active_participant, "case-content"
    )


def case_content_recipients(
    case: VulnerabilityCase,
    dl: CasePersistence,
    *,
    excluding: Collection[str] = (),
    skip_closed: bool = False,
) -> list[str]:
    """Return the actor IDs of *case*'s active participants (CM-10-004).

    The recipients of every case-content send — ledger fan-out, case
    announcements, case-update broadcasts and embargo announcements — minus
    *excluding* (typically the sender).  Roster order is kept.

    With *skip_closed*, a participant that has recorded RM ``CLOSED`` is
    left out as well (CM-23-004).  The default keeps it: a closed
    participant's replica still learns how the case ended (CM-23-002).
    """
    return [
        actor_id
        for actor_id, _record in case_content_participants(
            case, dl, excluding=excluding, skip_closed=skip_closed
        )
    ]


def inert_participants(
    case: VulnerabilityCase, dl: CasePersistence
) -> set[str]:
    """Return the roster actor IDs of *case* that are not active.

    The complement of :func:`case_content_recipients` over the roster, for a
    caller that reports whom a send withheld content from.
    """
    active = set(case_content_recipients(case, dl))
    return set(case.actor_participant_index) - active


def inactive_joined_participants(
    case: VulnerabilityCase,
    dl: CasePersistence,
    *,
    excluding: Collection[str] = (),
    skip_closed: bool = False,
) -> list[str]:
    """Return the actor IDs of the joined participants that are not active.

    A joined participant that is not active: it is not a signatory to the
    active embargo (CM-10-004), or it carries the removal fact (CM-31-001).
    These are the participants whose ledger stream is paused and backfilled
    on admission (CM-10-005, CM-10-006); a removed participant is admitted
    when the fact is cleared (CM-31-011).  A participant that has not joined
    is left out: it is inert whatever the embargo, and its case copy and
    ledger arrive through the join path (ADR-0114).  A roster entry whose
    record cannot be read is left out too; :func:`case_content_recipients`
    already names it.  Roster order is kept; *excluding* and *skip_closed*
    narrow the roster as they do there.
    """
    withheld: list[str] = []
    for actor_id, record in _roster_records(case, dl):
        if actor_id in excluding or record is None or not record.joined:
            continue
        if skip_closed and record.rm_closed:
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
    *excluding* (EP-09-002, CM-10-007).  An Invite asks the participant to
    consent; an inert participant is exactly the one that needs asking, so
    the active check does not apply.  A participant that never joined is
    included: it is not ``CLOSED``.
    """
    return [
        actor_id
        for actor_id, _record in _select(
            case, dl, excluding, lambda p: not p.rm_closed, "invitation"
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

    A joined participant that is ``SIGNATORY`` to *embargo_id* — its row
    for it is ``ACCEPTED`` — and that the ledger fan-out no longer reaches:
    removed (CM-31-001), or at RM ``CLOSED`` (CM-23-004).  Such a
    participant stays bound (CM-31-008) and cannot learn from the ledger
    that the embargo was terminated or shortened, so the CASE_MANAGER tells
    it directly (CM-31-009).  A participant that declined, or an invitee
    that never joined, is not bound and is not sent anything.

    *embargo_id* is the embargo that is ending: the one terminated, or the
    one a shorter revision replaces.  Consent rows outlive both moves
    (MSM-07-006, EP-05-001), so the selection is the same before and after
    the EM write.  The notice is not case content (CM-10-007), so the active
    check does not apply.  Roster order is kept, minus *excluding*.
    """
    return [
        actor_id
        for actor_id, _record in _select(
            case,
            dl,
            excluding,
            lambda p: (
                p.joined and p.is_signatory(embargo_id) and _beyond_fan_out(p)
            ),
            "embargo-ending notice",
        )
    ]


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


def is_case_content_recipient(
    case: VulnerabilityCase, dl: CasePersistence, actor_id: str
) -> bool:
    """True when *actor_id* is an active participant of *case* (CM-10-004).

    For a send addressed to one actor named by the triggering message rather
    than chosen from the roster: the ledger replay a
    ``Reject(CaseLedgerEntry)`` asks for and the genesis case seed (#4042).
    The joiner's case copy and ledger backfill (#4048) gate on it too once
    that lands.
    """
    participant_id = case.actor_participant_index.get(actor_id)
    if participant_id is None:
        return False
    record = _resolve_record(case, dl, participant_id)
    return record is not None and case.is_active_participant(record)
