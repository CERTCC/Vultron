"""The CM-10-004 embargo content gate, as one shared predicate (CM-10-007).

While a case has an active embargo, only a participant that has accepted that
embargo may receive case content. This module is the one answer to "who is
withheld?", so every case-content send — the case-update broadcast and the
ledger fan-out and replay (CM-10-005) — selects recipients through the same
rule rather than each send site carrying its own copy.

It lives below both ``vultron.core.behaviors`` and ``vultron.core.use_cases``
and depends only on ``models`` and ``ports``, like ``authority.py``.

The gate covers the embargo half of CM-10-004 only. The broader
active-participant check — an invitee that has not answered its stub Invite is
inert too — is tracked separately (#4046).
"""

from __future__ import annotations

import logging

from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.ports.case_persistence import CasePersistence

logger = logging.getLogger(__name__)


def embargo_withheld_actor_ids(
    case: VulnerabilityCase, dl: CasePersistence
) -> set[str]:
    """Return the actors the active embargo withholds case content from.

    An actor is withheld when the case has an active embargo and the actor's
    participant record does not list that embargo in ``accepted_embargo_ids``
    (CM-10-001, CM-10-004). With no active embargo nobody is withheld.

    An index entry whose participant cannot be read is not withheld: the gate
    decides on consent it can see, and the reader is told at WARNING. A record
    that is not a ``CaseParticipant`` is skipped the same way.
    """
    embargo_id = case.active_embargo_id
    if embargo_id is None:
        return set()

    withheld: set[str] = set()
    for actor_id, participant_id in case.actor_participant_index.items():
        participant = dl.read(participant_id)
        if participant is None:
            logger.warning(
                "embargo gate: could not read participant '%s' (actor '%s')"
                " for the embargo acceptance check on case '%s'",
                participant_id,
                actor_id,
                case.id_,
            )
            continue
        if not isinstance(participant, CaseParticipant):
            continue
        if embargo_id not in participant.accepted_embargo_ids:
            withheld.add(actor_id)
    return withheld
