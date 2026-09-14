"""Shared participant-iteration helper for the neutral participants layer.

Provides :func:`iter_case_participants`, the single canonical two-phase scan
over a case's ``actor_participant_index`` and ``case_participants`` list.  Both
``vultron.core.participants.authority`` and
``vultron.core.behaviors.case.nodes.participant.roles`` delegate to it so that
any fix to the loop invariant (deduplication, bootstrap-phase handling) lands
in one place (ARCH-24-001, issue #3218).
"""

from collections.abc import Iterator

from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.ports.case_persistence import CasePersistence


def iter_case_participants(
    case: VulnerabilityCase,
    dl: CasePersistence,
) -> Iterator[CaseParticipant]:
    """Yield each :class:`~vultron.core.models.case_participant.CaseParticipant` reachable from *case*, deduped.

    Two-phase scan:

    1. **Fast path** — ``actor_participant_index`` values: the set of
       participant IDs that have already been indexed.  Each is read from the
       DataLayer and yielded if it is a ``CaseParticipant``.
    2. **Bootstrap fallback** — ``case_participants``: inline
       ``CaseParticipant`` objects and string ID references that are *not*
       already in the indexed set.  Used during bootstrap, where inline
       participant objects may not yet be indexed.

    Participants are deduped by participant ID so that an inline object that
    also appears in the index is not yielded twice.
    """
    indexed_ids = set(case.actor_participant_index.values())
    # Track IDs actually yielded by the fast path so the fallback knows which
    # indexed participants the DataLayer could not supply yet (e.g. during
    # bootstrap before ledger sync completes). Using `indexed_ids` alone for
    # dedup would drop an inline participant whose DataLayer read returned None.
    yielded_ids: set[str] = set()

    for p_id in indexed_ids:
        p = dl.read(p_id)
        if isinstance(p, CaseParticipant):
            yielded_ids.add(p.id_)
            yield p

    for p_ref in case.case_participants:
        if not isinstance(p_ref, str):
            if (
                isinstance(p_ref, CaseParticipant)
                and p_ref.id_ not in yielded_ids
            ):
                yield p_ref
        elif p_ref not in yielded_ids:
            p = dl.read(p_ref)
            if isinstance(p, CaseParticipant):
                yield p
