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
"""Read a case ledger as a standing record (ADR-0190, level 1).

:func:`case_standing` composes the layers below it and adds no rule of its
own: the event history and the states reached come from one derivation
(:func:`~vultron.measure.history.derive_case`), the per-vendor sequences from
:func:`~vultron.measure.sequences.case_state_sequences`, and their scores
from :func:`~vultron.measure.scoring.score_case`.
"""

from __future__ import annotations

import logging

from vultron.errors import VultronInvalidStateTransitionError
from vultron.measure.history import (
    CaseEventHistory,
    ReachedParticipant,
    derive_case,
)
from vultron.measure.ledger import CaseLedger
from vultron.measure.scoring import CaseScoreSummary, score_case
from vultron.measure.sequences import (
    UnprojectableParticipant,
    UnprojectableReason,
    case_state_sequences,
)
from vultron.measure.standing.model import (
    CaseStanding,
    ParticipantStanding,
    StandingGap,
    StandingRecord,
)

logger = logging.getLogger(__name__)


def _gap(
    history: CaseEventHistory, register_problem: str | None
) -> StandingGap | None:
    """The holes in *history* that keep it from a reading, or ``None``."""
    if not (
        history.missing_log_indices
        or history.conflicting_log_indices
        or history.unusable_rows
        or history.unreadable_entries
        or register_problem
    ):
        return None
    return StandingGap(
        missing_log_indices=history.missing_log_indices,
        conflicting_log_indices=history.conflicting_log_indices,
        unusable_rows=history.unusable_rows,
        unreadable_entries=history.unreadable_entries,
        register_problem=register_problem,
    )


def _gapped(
    history: CaseEventHistory, register_problem: str | None
) -> StandingRecord:
    """The record of a ledger with a hole: the gap, and no reading."""
    gap = _gap(history, register_problem)
    assert gap is not None, "only a ledger with a hole is gapped"
    logger.warning(
        "Case %s: no standing record over a ledger with a hole: %s",
        history.case_id,
        gap.model_dump(exclude_defaults=True),
    )
    return StandingRecord(
        case_id=history.case_id, end_confirmed=history.end_confirmed, gap=gap
    )


def _unscored(
    participant: str, scores: CaseScoreSummary
) -> UnprojectableParticipant:
    """Why *participant* has no score.

    The projection names every participant with an event; one the ledger
    records with no event at all has none of its own case-state events.
    """
    for unprojectable in scores.unprojectable:
        if unprojectable.participant == participant:
            return unprojectable
    return UnprojectableParticipant(
        participant=participant,
        reason=UnprojectableReason.NO_CASE_STATE_EVENTS,
        detail="the participant has no event in the case event history",
    )


def _participant(
    reached: ReachedParticipant, scores: CaseScoreSummary
) -> ParticipantStanding:
    vendor = scores.for_participant(reached.participant)
    return ParticipantStanding(
        participant=reached.participant,
        roles=reached.roles,
        joined=reached.joined,
        rm=reached.rm,
        score=None if vendor is None else vendor.score,
        unscored=None
        if vendor is not None
        else _unscored(reached.participant, scores),
    )


def case_standing(ledger: CaseLedger) -> StandingRecord:
    """Where the case *ledger* records stands at its last entry.

    Args:
        ledger: One case's entries from the source a measure should trust,
            as :func:`vultron.measure.ledger.read_case_ledgers` selects it.

    Returns:
        Each participant's states, the desiderata each vendor's case has met,
        broken or left open, and the moves allowed from here.  A ledger with
        a hole yields only the :class:`StandingGap` that names it, never a
        reading that hides it.
    """
    history, reached = derive_case(ledger)
    try:
        em = reached.em()
    except VultronInvalidStateTransitionError as exc:
        return _gapped(history, str(exc))
    gap = _gap(history, None)
    if gap is not None:
        return _gapped(history, None)
    scores = score_case(case_state_sequences(history))
    return StandingRecord(
        case_id=history.case_id,
        end_confirmed=history.end_confirmed,
        case=CaseStanding(em=em, pxa=reached.pxa),
        participants=[_participant(p, scores) for p in reached.participants],
    )
