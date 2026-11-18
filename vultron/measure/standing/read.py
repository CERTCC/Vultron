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
from :func:`~vultron.measure.scoring.score_case`, and its path-preference
counts from :func:`~vultron.measure.preferences.path_preferences`.
"""

from __future__ import annotations

import logging

from vultron.core.states.cs_invariants import CSEvent
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.errors import VultronInvalidStateTransitionError
from vultron.measure.baselines import (
    ordered_cs_events,
    outcome_change,
)
from vultron.measure.baselines.values import Outcomes
from vultron.measure.history import (
    CaseEventHistory,
    ReachedParticipant,
    ReachedState,
    derive_case,
)
from vultron.measure.ledger import CaseLedger
from vultron.measure.preferences import path_preferences
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
    outcomes: Outcomes, vendors: dict[int, str]
) -> tuple[DesideratumChange, ...]:
    """Each vendor's change in expected outcome, as *outcomes* holds it
    (:func:`~vultron.measure.baselines.outcome_change`)."""
    return tuple(
        DesideratumChange(
            vendor=vendors[key.vendor],
            other_vendor=None if key.other is None else vendors[key.other],
            notation=key.desideratum.notation,
            change=change,
        )
        for key, change in outcomes.items()
    )


def _unobservable_reason(
    move: RMMove | CSMove | EMMove,
    outcomes: Outcomes,
    unobservable: frozenset[CSEvent],
) -> str | None:
    """Why *move*'s change in expected outcome rests on an event the source
    cannot observe; ``None`` when it does not (CRD-02-005).

    It does when the move is such an event, which may already have happened,
    or when it changes the expected outcome of a desideratum that orders
    one, whose status the case cannot say.
    """
    if isinstance(move, CSMove) and move.event in unobservable:
        return (
            f"the source cannot observe {move.event.value} events, so this"
            " one may already have happened"
        )
    changed = {
        event
        for key, change in outcomes.items()
        if change
        for event in ordered_cs_events(key.desideratum) & unobservable
    }
    if not changed:
        return None
    names = ", ".join(event.value for event in CSEvent if event in changed)
    return (
        f"the move changes the expected outcome of desiderata over {names},"
        " which the source cannot observe"
    )


def _scored(
    prefix: CasePrefix | None,
    numbers: dict[str, int],
    move: RMMove | CSMove | EMMove,
    unobservable: frozenset[CSEvent] = frozenset(),
) -> ScoredMove:
    """*move* with each vendor's change in expected outcome, if it has one.

    A move whose change rests on an event in *unobservable* carries the
    reason instead of a number (:func:`_unobservable_reason`).
    """
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
    outcomes = outcome_change(prefix, step)
    reason = _unobservable_reason(move, outcomes, unobservable)
    if reason is not None:
        return ScoredMove(move=move, unscored=reason)
    vendors = {n: participant for participant, n in numbers.items()}
    return ScoredMove(move=move, changes=_changes(outcomes, vendors))


def _moves_of(
    standing: ParticipantStanding,
) -> tuple[RMMove | CSMove | EMMove, ...]:
    """Every move *standing* allows, RM first, then CS, then EM."""
    return (*standing.rm_moves, *standing.cs_moves, *standing.em_moves)


def _unaware_vendors(participants: list[ParticipantStanding]) -> list[str]:
    """The vendors not yet notified: the Vendor role, RM Start, no score."""
    return [
        p.participant
        for p in participants
        if CVDRole.VENDOR in p.cvd_roles
        and p.rm is RM.START
        and p.score is None
    ]


def case_standing(
    ledger: CaseLedger,
    unobservable: frozenset[CSEvent] = frozenset(),
    *,
    derived: tuple[CaseEventHistory, ReachedState] | None = None,
) -> StandingRecord:
    """Where the case *ledger* records stands at its last entry.

    Args:
        ledger: One case's entries from the source a measure should trust,
            as :func:`vultron.measure.ledger.read_case_ledgers` selects it.
        unobservable: The case-state events the ledger's source cannot
            observe.  Each desideratum that orders one is unknown, and each
            move whose change in expected outcome rests on one carries the
            reason instead of a number (CRD-02-005).
        derived: :func:`~vultron.measure.history.derive_case` of *ledger*,
            when the caller has walked it already; walked here otherwise.

    Returns:
        Each participant's states, the desiderata each vendor's case has met,
        broken, left open or cannot know, and the moves allowed from here.
        A ledger with a hole yields only the :class:`StandingGap` that names
        it, never a reading that hides it.
    """
    history, reached = derived if derived is not None else derive_case(ledger)
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
    scores = score_case(history)
    case = CaseStanding(em=em, pxa=reached.pxa, unobservable=unobservable)
    participants = [
        _participant(p, case, scores) for p in reached.participants
    ]
    rm_of = {p.participant: p.rm for p in reached.participants}
    unaware = _unaware_vendors(participants)
    prefix = case_prefix(
        history, sequences.sequences, rm_of, em, unaware, reached.pxa
    )
    numbers = vendor_numbers(sequences.sequences, unaware)
    return StandingRecord(
        case_id=history.case_id,
        end_confirmed=history.end_confirmed,
        case=case,
        participants=participants,
        vendors=list(numbers),
        moves=[
            _scored(prefix, numbers, move, unobservable)
            for p in participants
            for move in _moves_of(p)
        ],
        path_preferences=path_preferences(history),
    )
