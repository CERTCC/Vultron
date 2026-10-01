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
- :func:`invitation_recipients` — an Invite addressed to a participant *so
  that* it can consent (the relayed embargo Invite, EP-09-002).  Every
  participant whose RM is not ``CLOSED``, inert ones included (CM-10-007).

Both read the roster (``actor_participant_index``) and resolve each entry to
its participant record.  A roster entry whose record cannot be read is not
provably entitled, so it is left out and logged at WARNING: leaking case
content to an actor the case cannot vouch for is the failure CM-10-004
exists to prevent.

Roster order is kept, and an unresolvable entry is named, which is why this
walks the index itself rather than :func:`iter_case_participants` (that yields
records only, in no fixed order, and skips what it cannot read silently).

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

    The inline :class:`CaseParticipant` the case carries wins over the stored
    one: it is the copy that travelled with this case.
    """
    for entry in case.case_participants:
        if isinstance(entry, CaseParticipant) and entry.id_ == participant_id:
            return entry
    stored = dl.read(participant_id)
    return stored if isinstance(stored, CaseParticipant) else None


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
) -> list[str]:
    recipients: list[str] = []
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
            recipients.append(actor_id)
        else:
            logger.debug(
                "case '%s': '%s' is not among the %s recipients (ADR-0114)",
                case.id_,
                actor_id,
                audience,
            )
    return recipients


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

    With *skip_closed*, a participant whose latest RM state is ``CLOSED`` is
    left out as well (CM-23-004).  The default keeps it: a closed
    participant's replica still learns how the case ended (CM-23-002).
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


def inert_participants(
    case: VulnerabilityCase, dl: CasePersistence
) -> set[str]:
    """Return the roster actor IDs of *case* that are not active.

    The complement of :func:`case_content_recipients` over the roster, for a
    caller that reports whom a send withheld content from.
    """
    active = set(case_content_recipients(case, dl))
    return {
        actor_id
        for actor_id, _record in _roster_records(case, dl)
        if actor_id not in active
    }


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
    return _select(
        case,
        dl,
        excluding,
        lambda p: not p.rm_closed,
        "invitation",
    )


def is_case_content_recipient(
    case: VulnerabilityCase, dl: CasePersistence, actor_id: str
) -> bool:
    """True when *actor_id* is an active participant of *case* (CM-10-004).

    For a send addressed to one actor named by the triggering message — the
    ledger replay a ``Reject(CaseLedgerEntry)`` asks for, or the case copy a
    joiner receives — rather than chosen from the roster.
    """
    participant_id = case.actor_participant_index.get(actor_id)
    if participant_id is None:
        return False
    record = _resolve_record(case, dl, participant_id)
    return record is not None and case.is_active_participant(record)
