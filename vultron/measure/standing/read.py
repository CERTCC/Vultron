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
from vultron.measure.baselines import (
    Event,
    JointState,
    Step,
    outcome_change,
)
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
from vultron.measure.standing.joint import (
    CasePrefix,
    NoJointStep,
    case_prefix,
    joint_step,
    vendor_numbers,
)
from vultron.measure.standing.model import (
    CaseStanding,
    DesideratumChange,
    ParticipantStanding,
    ScoredMove,
    StandingGap,
    StandingRecord,
)
from vultron.measure.standing.moves import CSMove, EMMove, RMMove

logger = logging.getLogger(__name__)


def _gapped(history: CaseEventHistory, gap: StandingGap) -> StandingRecord:
    """The record of a ledger with a hole: the gap, and no reading."""
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
    reached: ReachedParticipant, case: CaseStanding, scores: CaseScoreSummary
) -> ParticipantStanding:
    vendor = scores.for_participant(reached.participant)
    return ParticipantStanding(
        participant=reached.participant,
        roles=reached.roles,
        joined=reached.joined,
        rm=reached.rm,
        case=case,
        score=None if vendor is None else vendor.score,
        unscored=None
        if vendor is not None
        else _unscored(reached.participant, scores),
    )


def _changes(
    prefix: CasePrefix,
    step: Step[JointState, Event],
    vendors: dict[int, str],
) -> tuple[DesideratumChange, ...]:
    """Each vendor's change in expected outcome from *step*
    (:func:`~vultron.measure.baselines.outcome_change`)."""
    return tuple(
        DesideratumChange(
            vendor=vendors[key.vendor],
            other_vendor=None if key.other is None else vendors[key.other],
            notation=key.desideratum.notation,
            change=change,
        )
        for key, change in outcome_change(prefix, step).items()
    )


def _scored(
    prefix: CasePrefix | None,
    numbers: dict[str, int],
    move: RMMove | CSMove | EMMove,
) -> ScoredMove:
    """*move* with each vendor's change in expected outcome, if it has one."""
    if move.source == move.destination:
        return ScoredMove(move=move)
    if prefix is None:
        return ScoredMove(
            move=move, unscored="the case has no vendor to score a move for"
        )
    try:
        step = joint_step(prefix, numbers, move)
    except NoJointStep as exc:
        return ScoredMove(move=move, unscored=str(exc))
    vendors = {n: participant for participant, n in numbers.items()}
    return ScoredMove(move=move, changes=_changes(prefix, step, vendors))


def _moves_of(
    standing: ParticipantStanding,
) -> tuple[RMMove | CSMove | EMMove, ...]:
    """Every move *standing* allows, RM first, then CS, then EM."""
    return (*standing.rm_moves, *standing.cs_moves, *standing.em_moves)


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
        register_gap = StandingGap.of(history, str(exc) or type(exc).__name__)
        assert register_gap is not None, "a register problem is a hole"
        return _gapped(history, register_gap)
    gap = StandingGap.of(history)
    if gap is not None:
        return _gapped(history, gap)
    sequences = case_state_sequences(history)
    scores = score_case(sequences)
    case = CaseStanding(em=em, pxa=reached.pxa)
    participants = [
        _participant(p, case, scores) for p in reached.participants
    ]
    rm_of = {p.participant: p.rm for p in reached.participants}
    prefix = case_prefix(history, sequences.sequences, rm_of, em)
    numbers = vendor_numbers(sequences.sequences)
    return StandingRecord(
        case_id=history.case_id,
        end_confirmed=history.end_confirmed,
        case=case,
        participants=participants,
        moves=[
            _scored(prefix, numbers, move)
            for p in participants
            for move in _moves_of(p)
        ],
    )
