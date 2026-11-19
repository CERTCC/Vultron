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
"""Hindsight marks: each step a case took, graded by the advice before it (#6672).

:func:`hindsight_mark` reads the states the case had reached just before an
entry and just after it, finds the move of the advice open before the entry
that makes the same change, and grades that move by its band and layer:

* **best**: layer 1 of the first band, harm-free then trade-off, that holds
  any move, so a trade-off move is best when no harm-free move is open;
* **good**: harm-free, not best;
* **sub-optimal**: trade-off, not best, saying so when a harm-free move
  dominated it;
* **neutral**: unhelpful with every part of its shift zero, and a move that
  keeps every state, which is advice, not a step;
* **bad**: unhelpful with some vendor's part negative.

Two marks grade nothing.  **Chance** marks an event no participant chooses:
an exploit made public or attacks observed (X, A), and the public becoming
aware of the vul, unless an embargo ended on its own terms before it.  **Not a move** marks
every other entry: one that changes no state the advice weighs, such as a
note or a consent answer (PEC moves are not advised yet), one whose change no
advised move makes, one whose move has no band, and an entry with no advice
before it.

The case public state P means the public is aware the vul exists, not that
anyone published: a public exploit forces it, and so may a leak.  The ledger
records only that the case became public, never whether a participant
published, so the vul becoming public is chance, with one exception: when the
case's embargo had ended on its own terms at or before it, the entry is
graded as the advice's public-awareness move, a participant's publication
(:data:`~.shifts.CHANCE_EVENTS` holds publication as a move).  Only the first
publication makes the case public; a later one changes no state and grades
nothing.  Telling a publication from a leak is #6732.

An entry is one step, so it gets one mark.  When it changes several machines,
the first machine in this order decides: the public state, a fix path, the
embargo, report management.  A case-state event drives the others, as a
publication ends an embargo, never the reverse.  Only a move of that machine
is the step: a change no single move makes, such as report management
passing two states in one entry, grades nothing, and is never passed over
for a later machine's change.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from enum import IntEnum, StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from vultron.core.models.embargo_register import em_triggers_of
from vultron.core.states.cs import (
    AttackObservation,
    ExploitPublication,
    PublicAwareness,
)
from vultron.core.states.cs_invariants import (
    CS_EVENT_TO_PXA_TRIGGER,
    CSEvent,
    cs_dimensions,
)
from vultron.core.states.em import EM, EM_Trigger
from vultron.core.states.embargo_register import (
    EmbargoRegisterStatus,
    RegisterTrigger,
    register_trigger_between,
)
from vultron.errors import VultronInvalidStateTransitionError
from vultron.measure.advice.bands import BAND_ORDER, Band
from vultron.measure.advice.case import (
    CHANCE_EVENT,
    KEEPS_EVERY_STATE,
    AdvisedMove,
    AllowedMove,
    CaseAdvice,
    UnbandedMove,
)
from vultron.measure.baselines import EmbargoEnd
from vultron.measure.history import (
    CaseEventHistory,
    EventKind as HistoryKind,
    ReachedParticipant,
    ReachedState,
)
from vultron.measure.standing import CSMove, EMMove, RMMove, embargo_end
from vultron.primitives import NonEmptyString


class HindsightMark(StrEnum):
    """How good the step an entry took was, by the advice open before it."""

    BEST = "best"
    GOOD = "good"
    SUB_OPTIMAL = "sub-optimal"
    NEUTRAL = "neutral"
    BAD = "bad"
    #: Not graded: an event no participant chooses.
    CHANCE = "chance"
    #: Not graded: an act that is not a move of the advice.
    NOT_A_MOVE = "not a move"


#: The case-state events that move the case's public state.
PUBLIC_EVENTS: frozenset[CSEvent] = frozenset(CS_EVENT_TO_PXA_TRIGGER)

#: The marks that grade a move of the advice; the others grade nothing.
GRADED: frozenset[HindsightMark] = frozenset(
    {
        HindsightMark.BEST,
        HindsightMark.GOOD,
        HindsightMark.SUB_OPTIMAL,
        HindsightMark.NEUTRAL,
        HindsightMark.BAD,
    }
)

#: The marks of a move in a shaded band, which take the band's shade.
SHADED: frozenset[HindsightMark] = frozenset(
    {HindsightMark.BEST, HindsightMark.GOOD, HindsightMark.SUB_OPTIMAL}
)

DID_AS_WELL = "A harm-free move did as well."
"""What a sub-optimal mark adds when a harm-free move dominated its move."""

NO_ADVICE = "No move advice is open before the case's first entry."
"""Why the first entry grades nothing."""

ADVICE_GAP = (
    "The ledger before this entry has a hole, so no move advice is open."
)
"""Why an entry after a hole grades nothing."""

NO_STATE_CHANGE = "The entry changes no state the move advice weighs."
"""Why a note, an invitation or a consent answer grades nothing."""

NO_ADVISED_MOVE = (
    "No move the advice before this entry lists makes its change."
)
"""Why an entry whose change no single advised move makes grades nothing."""

FORCED_BY_EXPLOIT = (
    "The exploit was already public, which makes the public aware of the"
    " vul: no participant chose this."
)
"""Why public awareness that follows a public exploit grades nothing."""

NO_KNOWN_PUBLISHER = (
    "Neither a public exploit nor an embargo that ended on its own terms"
    " comes before the vul became public, so the ledger cannot tell a"
    " publication from a leak (#6732)."
)
"""Why the public becoming aware of the vul is chance unless an embargo
ended on its own terms at or before it."""

UNLISTED_CHANCE = "No participant chooses this event."
"""Why an X or A change the advice lists no move for grades nothing."""

REGISTER_PROBLEM = (
    "The embargo register this entry leaves gives no EM state, so no EM move"
    " makes its change."
)
"""Why an entry that breaks the embargo register grades nothing."""


def no_band(reason: str) -> str:
    """Why an entry whose move has no band grades nothing."""
    return f"The move has no band: {reason}"


class NarrativeMark(BaseModel):
    """The hindsight mark of one case narrative line.

    Fields:
        log_index: The line's entry's log index.
        mark: The mark.
        move: The move of the advice before the entry that the entry made;
            ``None`` when it made none.
        band: The move's band, for a move that has one.
        layer: The move's layer, in a harm-free or trade-off band.
        deepest_layer: The deepest layer of the advice the move was graded
            by, so a page shades the mark as that advice's band legend
            shades the layer.
        note: What the mark adds: that a harm-free move did as well, for a
            sub-optimal move a harm-free move dominated, or why a line is
            not graded.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    log_index: int = Field(ge=0)
    mark: HindsightMark
    move: AllowedMove | None = None
    band: Band | None = None
    layer: int | None = Field(default=None, ge=1)
    deepest_layer: int | None = Field(default=None, ge=1)
    note: NonEmptyString | None = None

    @model_validator(mode="after")
    def _fits_its_mark(self) -> NarrativeMark:
        problems: list[str] = []
        shaded = self.mark in SHADED
        if self.mark in GRADED and self.move is None:
            problems.append(f"a {self.mark} mark grades a move")
        if shaded != (self.layer is not None):
            problems.append(
                "only a best, good or sub-optimal mark has a layer"
            )
        if (self.layer is None) != (self.deepest_layer is None):
            problems.append("a layer comes with its advice's deepest layer")
        if (
            self.layer is not None
            and self.deepest_layer is not None
            and self.layer > self.deepest_layer
        ):
            problems.append("the layer is deeper than its advice's deepest")
        if shaded and self.band not in (Band.HARM_FREE, Band.TRADE_OFF):
            problems.append(
                "a best, good or sub-optimal mark is in the harm-free or"
                " trade-off band"
            )
        if self.mark not in GRADED and self.note is None:
            problems.append("a line that is not graded says why")
        if problems:
            raise ValueError("; ".join(problems))
        return self


type _Candidate = AdvisedMove | UnbandedMove


def _owner(state: ReachedState, participant: str) -> ReachedParticipant:
    return state.for_participant(participant) or ReachedParticipant(
        participant=participant
    )


def _em(state: ReachedState) -> EM | None:
    try:
        return state.em()
    except VultronInvalidStateTransitionError:
        return None


def register_trigger(
    before: Mapping[str, EmbargoRegisterStatus],
    after: Mapping[str, EmbargoRegisterStatus],
) -> EM_Trigger | None:
    """The EM trigger of the register step from *before* to *after*, read
    through the register's own mapping (:func:`em_triggers_of`, ADR-0130).

    ``None`` when the register did not change, or when its change is no one
    EM trigger's step.
    """
    triggers: list[RegisterTrigger] = []
    for embargo, status in after.items():
        was = before.get(embargo)
        if was is status:
            continue
        trigger = register_trigger_between(was, status)
        if trigger is None:
            return None
        triggers.append(trigger)
    if not triggers:
        return None
    em_triggers = em_triggers_of(triggers)
    return em_triggers.pop() if len(em_triggers) == 1 else None


def _pxa_made(move: CSMove, before: ReachedState, after: ReachedState) -> bool:
    _, _, source = cs_dimensions(move.source)
    _, _, destination = cs_dimensions(move.destination)
    return (
        source != destination
        and before.pxa is source
        and after.pxa is destination
    )


def _fix_path_made(
    move: CSMove, before: ReachedState, after: ReachedState
) -> bool:
    vf, d, _ = cs_dimensions(move.source)
    to_vf, to_d, _ = cs_dimensions(move.destination)
    was, now = (_owner(state, move.participant) for state in (before, after))
    return (vf, d) != (to_vf, to_d) and (
        (was.vf, was.d, now.vf, now.d) == (vf, d, to_vf, to_d)
    )


def _em_made(move: EMMove, before: ReachedState, after: ReachedState) -> bool:
    was, now = _em(before), _em(after)
    trigger = register_trigger(before.embargo_register, after.embargo_register)
    if trigger is None:
        return False
    return (move.source, move.destination, move.trigger) == (
        was,
        now,
        trigger,
    )


def _rm_made(move: RMMove, before: ReachedState, after: ReachedState) -> bool:
    was, now = (_owner(state, move.participant) for state in (before, after))
    return (was.rm, now.rm) == (move.source, move.destination)


def owns_state(move: AllowedMove) -> bool:
    """Whether *move* moves the state of the participant it names: an RM
    move, or a case-state event on that participant's fix path.  A
    public-state move moves the case's state, and an EM move names only a
    participant who may make it."""
    return isinstance(move, RMMove) or (
        isinstance(move, CSMove) and move.event not in PUBLIC_EVENTS
    )


class _Machine(IntEnum):
    """The machines whose change decides an entry's mark, in the order they
    decide it."""

    PUBLIC = 0
    FIX_PATH = 1
    EMBARGO = 2
    REPORT = 3


def _machine(move: AllowedMove) -> _Machine:
    """The machine *move* changes."""
    if isinstance(move, CSMove):
        return (
            _Machine.PUBLIC
            if move.event in PUBLIC_EVENTS
            else _Machine.FIX_PATH
        )
    if isinstance(move, EMMove):
        return _Machine.EMBARGO
    return _Machine.REPORT


def _first_changed(
    before: ReachedState, after: ReachedState
) -> _Machine | None:
    """The first machine, in deciding order, whose state the entry from
    *before* to *after* changed; ``None`` when it changed none the move
    advice weighs."""
    pairs = [
        (_owner(before, now.participant), now) for now in after.participants
    ]
    if before.pxa is not after.pxa:
        return _Machine.PUBLIC
    if any((was.vf, was.d) != (now.vf, now.d) for was, now in pairs):
        return _Machine.FIX_PATH
    if before.embargo_register != after.embargo_register:
        return _Machine.EMBARGO
    if any(was.rm is not now.rm for was, now in pairs):
        return _Machine.REPORT
    return None


def _made(
    move: AllowedMove, before: ReachedState, after: ReachedState
) -> bool:
    """Whether the entry from *before* to *after* made *move*."""
    if isinstance(move, CSMove):
        if _machine(move) is _Machine.PUBLIC:
            return _pxa_made(move, before, after)
        return _fix_path_made(move, before, after)
    if isinstance(move, EMMove):
        return _em_made(move, before, after)
    return _rm_made(move, before, after)


def _candidates(advice: CaseAdvice) -> Iterator[_Candidate]:
    yield from advice.moves
    yield from advice.unbanded


def taken_move(
    advice: CaseAdvice,
    before: ReachedState,
    after: ReachedState,
    actor: str | None = None,
) -> _Candidate | None:
    """The move of *advice* that the entry from *before* to *after* made.

    The first machine the entry changed, in deciding order, decides
    (:func:`_first_changed`): only a move of that machine is the step, so a
    change no listed move makes is never passed over for a later machine's.
    Among the moves that make it, an open move comes before one with no
    band, then the acting *actor*'s own: a public-state or embargo change is
    the same joint step whichever participant's move it is, so its band is
    the same, but a participant that moves no vendor's state has no band
    for it.

    Returns:
        The move, or ``None`` when no move of *advice* makes the change the
        entry made in that machine.
    """
    machine = _first_changed(before, after)
    made = [
        m
        for m in _candidates(advice)
        if _machine(m.move) is machine and _made(m.move, before, after)
    ]
    if not made:
        return None
    return min(
        made,
        key=lambda m: (
            isinstance(m, UnbandedMove),
            m.move.participant != actor,
        ),
    )


def _forced_by_exploit(before: ReachedState, after: ReachedState) -> bool:
    """Whether the entry made the public aware of a vul whose exploit was
    already public: a public exploit forces public awareness next, so no
    participant chose it, whoever's entry records it."""
    was, now = before.pxa.value, after.pxa.value
    return (
        was.exploit_publication is ExploitPublication.EXPLOIT_PUBLIC
        and was.public_awareness is PublicAwareness.PUBLIC_UNAWARE
        and now.public_awareness is PublicAwareness.PUBLIC_AWARE
    )


def _made_public(before: ReachedState, after: ReachedState) -> bool:
    """Whether the entry made the public aware of the vul."""
    was, now = before.pxa.value, after.pxa.value
    return (
        was.public_awareness is PublicAwareness.PUBLIC_UNAWARE
        and now.public_awareness is PublicAwareness.PUBLIC_AWARE
    )


def _unchosen_publicity(
    before: ReachedState, after: ReachedState, ended_on_own_terms: bool
) -> str | None:
    """Why the public becoming aware of the vul at this entry is chance, or
    ``None`` when it is not: a public exploit forced it, or no embargo that
    ended on its own terms precedes it, so the ledger cannot say that a
    participant published.  An entry that also made an exploit public or
    attacks observed is left to the chance event it records."""
    if _forced_by_exploit(before, after):
        return FORCED_BY_EXPLOIT
    if (
        _made_public(before, after)
        and not _chance(before, after)
        and not ended_on_own_terms
    ):
        return NO_KNOWN_PUBLISHER
    return None


def embargo_ended_on_own_terms(
    history: CaseEventHistory, log_index: int
) -> bool:
    """Whether the case's embargo had ended on its own terms at or before
    the entry at *log_index*, with no embargo in force again since.

    It ended on its own terms when it reached its end time or a fix ended
    it (:func:`~vultron.measure.standing.embargo_end`), the joint model's
    own-terms exit.
    """
    events = [
        event
        for event in history.of_kind(
            HistoryKind.EMBARGO_START, HistoryKind.EMBARGO_EXIT
        )
        if event.log_index <= log_index
    ]
    if not events or events[-1].kind is not HistoryKind.EMBARGO_EXIT:
        return False
    return embargo_end(events[-1]) is EmbargoEnd.OWN_TERMS


def _chance(before: ReachedState, after: ReachedState) -> bool:
    """Whether the entry made an exploit public or attacks observed: the
    events no participant chooses (:data:`~.shifts.CHANCE_EVENTS`)."""
    was, now = before.pxa.value, after.pxa.value
    return (
        was.exploit_publication is ExploitPublication.NO_PUBLIC_EXPLOIT
        and now.exploit_publication is ExploitPublication.EXPLOIT_PUBLIC
    ) or (
        was.attack_observation is AttackObservation.NO_ATTACKS_OBSERVED
        and now.attack_observation is AttackObservation.ATTACKS_OBSERVED
    )


def _best_band(advice: CaseAdvice) -> Band | None:
    """The first shaded band, harm-free then trade-off, holding any move."""
    for band in BAND_ORDER:
        if band is not Band.UNHELPFUL and advice.band(band).moves:
            return band
    return None


def _graded(
    log_index: int, advised: AdvisedMove, advice: CaseAdvice
) -> NarrativeMark:
    if advised.band is Band.UNHELPFUL:
        return NarrativeMark(
            log_index=log_index,
            mark=HindsightMark.BAD if advised.harms else HindsightMark.NEUTRAL,
            move=advised.move,
            band=advised.band,
        )
    if advised.layer == 1 and advised.band is _best_band(advice):
        mark = HindsightMark.BEST
    elif advised.band is Band.HARM_FREE:
        mark = HindsightMark.GOOD
    else:
        mark = HindsightMark.SUB_OPTIMAL
    return NarrativeMark(
        log_index=log_index,
        mark=mark,
        move=advised.move,
        band=advised.band,
        layer=advised.layer,
        deepest_layer=advice.deepest_layer,
        note=DID_AS_WELL if advised.dominated_by_harm_free else None,
    )


def _unbanded(log_index: int, unbanded: UnbandedMove) -> NarrativeMark:
    if unbanded.reason == KEEPS_EVERY_STATE:
        mark, note = HindsightMark.NEUTRAL, None
    elif unbanded.reason == CHANCE_EVENT:
        mark, note = HindsightMark.CHANCE, CHANCE_EVENT
    else:
        mark, note = HindsightMark.NOT_A_MOVE, no_band(unbanded.reason)
    return NarrativeMark(
        log_index=log_index, mark=mark, move=unbanded.move, note=note
    )


def hindsight_mark(
    log_index: int,
    before: ReachedState,
    after: ReachedState,
    advice_before: Callable[[], CaseAdvice | None],
    actor: str | None = None,
    *,
    ended_on_own_terms: bool = False,
) -> NarrativeMark:
    """The hindsight mark of the entry at *log_index* (#6672).

    Args:
        log_index: The entry's log index.
        before: The states the case had reached just before the entry.
        after: The states it reached with the entry.
        advice_before: Gives the move advice open just before the entry
            (:func:`~vultron.shadow.analysis.prefix_advice`), or ``None``
            before the case's first entry.  It is called only for an entry
            that changes a state the advice weighs, since working out the
            advice costs far more than the mark of an entry that changes
            none.
        actor: The entry's acting actor, whose own move is preferred when
            several participants' moves make the same change.
        ended_on_own_terms: Whether the case's embargo had ended on its own
            terms at or before the entry (:func:`embargo_ended_on_own_terms`):
            the one case in which the vul becoming public, with no public
            exploit before it, is graded as a participant's publication.
    """

    def not_graded(mark: HindsightMark, note: str) -> NarrativeMark:
        return NarrativeMark(log_index=log_index, mark=mark, note=note)

    machine = _first_changed(before, after)
    if machine is None:
        return not_graded(HindsightMark.NOT_A_MOVE, NO_STATE_CHANGE)
    unchosen = (
        _unchosen_publicity(before, after, ended_on_own_terms)
        if machine is _Machine.PUBLIC
        else None
    )
    if unchosen is not None:
        return not_graded(HindsightMark.CHANCE, unchosen)
    advice = advice_before()
    if advice is None:
        return not_graded(HindsightMark.NOT_A_MOVE, NO_ADVICE)
    if advice.gap is not None:
        return not_graded(HindsightMark.NOT_A_MOVE, ADVICE_GAP)
    if machine is _Machine.EMBARGO and _em(after) is None:
        return not_graded(HindsightMark.NOT_A_MOVE, REGISTER_PROBLEM)
    taken = taken_move(advice, before, after, actor)
    if isinstance(taken, AdvisedMove):
        return _graded(log_index, taken, advice)
    if isinstance(taken, UnbandedMove):
        return _unbanded(log_index, taken)
    if machine is _Machine.PUBLIC and _chance(before, after):
        return not_graded(HindsightMark.CHANCE, UNLISTED_CHANCE)
    return not_graded(HindsightMark.NOT_A_MOVE, NO_ADVISED_MOVE)


__all__ = [
    "ADVICE_GAP",
    "DID_AS_WELL",
    "FORCED_BY_EXPLOIT",
    "GRADED",
    "NO_ADVICE",
    "NO_ADVISED_MOVE",
    "NO_KNOWN_PUBLISHER",
    "NO_STATE_CHANGE",
    "PUBLIC_EVENTS",
    "SHADED",
    "REGISTER_PROBLEM",
    "UNLISTED_CHANCE",
    "embargo_ended_on_own_terms",
    "HindsightMark",
    "NarrativeMark",
    "hindsight_mark",
    "no_band",
    "owns_state",
    "register_trigger",
    "taken_move",
]
