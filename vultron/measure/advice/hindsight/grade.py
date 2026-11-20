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

"""Grading the move an entry took by its band and layer: the entry's
hindsight mark (#6672).
"""

from __future__ import annotations

from collections.abc import Callable

from vultron.measure.advice.bands import BAND_ORDER, Band, deepest_layer
from vultron.measure.advice.case import (
    CHANCE_EVENT,
    KEEPS_EVERY_STATE,
    AdvisedMove,
    CaseAdvice,
    UnbandedMove,
)
from vultron.measure.advice.hindsight.chance import (
    made_chance,
    unchosen_publicity,
)
from vultron.measure.advice.hindsight.mark import (
    ADVICE_GAP,
    DID_AS_WELL,
    NO_ADVICE,
    NO_ADVISED_MOVE,
    NO_STATE_CHANGE,
    REGISTER_PROBLEM,
    UNLISTED_CHANCE,
    HindsightMark,
    NarrativeMark,
    no_band,
)
from vultron.measure.advice.hindsight.taken import (
    Machine,
    first_changed,
    reached_em,
    taken_move,
)
from vultron.measure.history import ReachedState


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
        deepest_layer=deepest_layer(m.layer for m in advice.moves),
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
            terms at or before the entry (:func:`~.chance.embargo_ended_on_own_terms`):
            the one case in which the vul becoming public, with no public
            exploit before it, is graded as a participant's publication.
    """

    def not_graded(mark: HindsightMark, note: str) -> NarrativeMark:
        return NarrativeMark(log_index=log_index, mark=mark, note=note)

    machine = first_changed(before, after)
    if machine is None:
        return not_graded(HindsightMark.NOT_A_MOVE, NO_STATE_CHANGE)
    public = machine is Machine.PUBLIC
    unchosen = (
        unchosen_publicity(before, after, ended_on_own_terms)
        if public
        else None
    )
    if unchosen is not None:
        return not_graded(HindsightMark.CHANCE, unchosen)
    # X or A is chance whatever the advice; the advice only names its move.
    chance = public and made_chance(before, after)
    advice = advice_before()
    if advice is None or advice.gap is not None:
        if chance:
            return not_graded(HindsightMark.CHANCE, UNLISTED_CHANCE)
        return not_graded(
            HindsightMark.NOT_A_MOVE,
            NO_ADVICE if advice is None else ADVICE_GAP,
        )
    if machine is Machine.EMBARGO and reached_em(after) is None:
        return not_graded(HindsightMark.NOT_A_MOVE, REGISTER_PROBLEM)
    taken = taken_move(advice, before, after, actor)
    if isinstance(taken, AdvisedMove):
        return _graded(log_index, taken, advice)
    if isinstance(taken, UnbandedMove):
        return _unbanded(log_index, taken)
    if chance:
        return not_graded(HindsightMark.CHANCE, UNLISTED_CHANCE)
    return not_graded(HindsightMark.NOT_A_MOVE, NO_ADVISED_MOVE)


__all__ = [
    "hindsight_mark",
]
