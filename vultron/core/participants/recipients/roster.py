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

"""Walk a case's roster and resolve each entry to its participant record.

Roster order is kept, and an entry whose record cannot be read is left out
and logged at WARNING (CM-10-004); the stored record comes first, an inline
copy only as the fallback.
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
    return _select_with_actor(
        case, dl, excluding, lambda _actor_id, p: entitled(p), audience
    )


def _select_with_actor(
    case: VulnerabilityCase,
    dl: CasePersistence,
    excluding: Collection[str],
    entitled: Callable[[str, CaseParticipant], bool],
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
        if entitled(actor_id, record):
            recipients.append((actor_id, record))
        else:
            logger.debug(
                "case '%s': '%s' is not among the %s recipients (ADR-0114)",
                case.id_,
                actor_id,
                audience,
            )
    return recipients


def _receives_case_content(
    case: VulnerabilityCase, record: CaseParticipant
) -> bool:
    """True when *record* is sent case content (CM-10-004, CM-23-004).

    Active, and its closure not recorded: a participant at RM ``CLOSED``
    has left and is sent nothing further.
    """
    return case.is_active_participant(record) and not record.rm_closed


def listed_participant_record(
    case: VulnerabilityCase, dl: CasePersistence, actor_id: str
) -> CaseParticipant | None:
    """The record *case*'s roster lists for *actor_id*, or ``None``.

    ``None`` when the roster does not list the actor or its record does not
    resolve (:func:`_resolve_record`: the stored record first, an inline copy
    as the fallback).  The one lookup behind :func:`may_act_on_case`, so a
    writer that must change the record an entitlement check admitted reads it
    here too (CM-21-022).
    """
    participant_id = case.actor_participant_index.get(actor_id)
    if participant_id is None:
        return None
    return _resolve_record(case, dl, participant_id)


def closure_recorded(
    case: VulnerabilityCase, dl: CasePersistence, actor_id: str
) -> bool:
    """True when *case* records the closure of *actor_id* (CM-23-018).

    The roster lists the actor and its record is at RM ``CLOSED``.  An act
    that would close such a participant again changes nothing: it is the
    repeat CM-23-049 reports ``SKIPPED``, whatever its activity id
    (ID-05-003).  An actor the case does not list, or whose record does not
    resolve, has no recorded closure.
    """
    record = listed_participant_record(case, dl, actor_id)
    return record is not None and record.rm_closed
