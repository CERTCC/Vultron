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

"""Hindsight marks that grade nothing because no participant chose the
step: chance (#6672).

An exploit made public or attacks observed (X, A) are chance whatever the
advice, and so is the public becoming aware of the vul (P), unless the
embargo ended on its own terms at or before that entry (the user's rulings
D10 and D18).  Only the first publication makes the case public; a later one
changes no state (D1).
"""

import pytest

from test.measure.advice.hindsight_cases import (
    _BEFORE,
    _EXPLOIT,
    _OWNER,
    _PUBLIC,
    _PUBLISH,
    _TOP_HARM_FREE,
    _VENDOR,
    _advice,
    _advised,
    _mark,
    _no_advice_wanted,
    _state,
)
from test.measure.history.builders import (
    CM,
    OWNER,
    VENDOR,
    Ledger,
    exit_embargo,
    participant,
    publish,
    seat_vendor,
    status,
)
from vultron.core.states.cs import CS_pxa
from vultron.core.states.cs_invariants import CSEvent
from vultron.measure.advice import (
    CHANCE_EVENT,
    CaseAdvice,
    HindsightMark,
    NarrativeMark,
    case_advice,
    hindsight_mark,
)
from vultron.measure.advice.case import UnbandedMove
from vultron.measure.advice.hindsight import (
    FORCED_BY_EXPLOIT,
    GRADED,
    NO_KNOWN_PUBLISHER,
    NO_STATE_CHANGE,
    UNLISTED_CHANCE,
    embargo_ended_on_own_terms,
)
from vultron.measure.history import (
    derive_case_steps,
)
from vultron.measure.standing import (
    CSMove,
    StandingGap,
    case_standing,
)


def test_an_exploit_made_public_is_chance():
    advice = _advice(
        _TOP_HARM_FREE,
        unbanded=[UnbandedMove(move=_EXPLOIT, reason=CHANCE_EVENT)],
    )
    mark = _mark(_state(pxa=CS_pxa.pXa), advice)
    assert mark.mark is HindsightMark.CHANCE
    assert mark.move == _EXPLOIT


def test_attacks_the_advice_lists_no_move_for_are_still_chance():
    mark = _mark(_state(pxa=CS_pxa.pxA), _advice(_TOP_HARM_FREE))
    assert mark.mark is HindsightMark.CHANCE
    assert mark.note == UNLISTED_CHANCE


def test_making_the_vul_public_is_graded_as_the_move_it_is():
    """After an embargo that ended on its own terms, the vul becoming public
    is a participant's publication: the case manager adopting the public
    state is graded by the advice's move."""
    advised = _advised(_PUBLISH, [(1, 0), (1, 0)], layer=1, top=True)
    case_managers = UnbandedMove(
        move=_PUBLISH.model_copy(update={"participant": _OWNER}),
        reason="rm.close by the owner moves no vendor's state",
    )
    advice = _advice(advised, unbanded=[case_managers])
    mark = _mark(_PUBLIC, advice, actor=_OWNER, ended_on_own_terms=True)
    assert mark.mark is HindsightMark.BEST
    assert mark.move == _PUBLISH


@pytest.mark.parametrize(
    ("before", "after"),
    [(CS_pxa.pXa, CS_pxa.PXa), (CS_pxa.pXA, CS_pxa.PXA)],
    ids=["after an exploit", "after an exploit and attacks"],
)
def test_public_awareness_a_public_exploit_forced_is_chance(before, after):
    """X forces P: the public is aware the vul exists, and no participant
    chose it, even where the advice lists a public-awareness move."""

    no_advice_wanted = _no_advice_wanted("a forced event reads no advice")
    mark = hindsight_mark(
        3, _state(pxa=before), _state(pxa=after), no_advice_wanted
    )
    assert (mark.mark, mark.note) == (HindsightMark.CHANCE, FORCED_BY_EXPLOIT)
    assert mark.move is None


def test_the_vul_becoming_public_with_no_known_publisher_is_chance():
    """With no public exploit and no embargo that ended on its own terms
    before it, the ledger cannot tell a publication from a leak (#6732)."""

    no_advice_wanted = _no_advice_wanted("a chance event reads no advice")
    mark = hindsight_mark(3, _BEFORE, _PUBLIC, no_advice_wanted)
    assert (mark.mark, mark.note) == (
        HindsightMark.CHANCE,
        NO_KNOWN_PUBLISHER,
    )


# -- the embargo's end before the vul became public, over real ledgers ---


def _vendor_case(*, with_embargo: bool = True) -> Ledger:
    ledger = Ledger()
    if with_embargo:
        ledger.standard_genesis()
    else:
        ledger.genesis(
            [
                participant(
                    OWNER,
                    [status("owner-r", OWNER, "RECEIVED")],
                    roles=("CASE_OWNER",),
                )
            ],
            with_embargo=False,
        )
    seat_vendor(ledger, VENDOR, "Vf")
    return ledger


def _publication_mark(ledger: Ledger) -> NarrativeMark:
    """The mark of the CASE_MANAGER making *ledger*'s case public next,
    graded by the real advice before it."""
    advice = case_advice(case_standing(ledger.case_ledger()))
    log_index = publish(ledger, "Pxa")
    history, steps = derive_case_steps(ledger.case_ledger())
    return hindsight_mark(
        log_index,
        steps[-2],
        steps[-1],
        lambda: advice,
        CM,
        ended_on_own_terms=embargo_ended_on_own_terms(history, log_index),
    )


@pytest.mark.parametrize(
    ("content", "cause"),
    [("END_TIME_REACHED", None), ("EARLY", {"kind": "FIX_READY"})],
    ids=["its end time", "a fix ready"],
)
def test_publication_after_an_embargo_ended_on_its_own_terms_is_graded(
    content, cause
):
    """ExOwn before P: the publication is the advice's move, graded."""
    ledger = _vendor_case()
    exit_embargo(ledger, content=content, cause=cause)
    mark = _publication_mark(ledger)
    assert mark.mark in GRADED
    assert isinstance(mark.move, CSMove) and mark.move.event is CSEvent.P


def test_an_embargo_ended_on_its_own_terms_counts_from_its_own_entry():
    """ExOwn counts at the entry that ends the embargo, not before it, so
    an entry at that log index is at or after it."""
    ledger = _vendor_case()
    ended = exit_embargo(ledger, content="END_TIME_REACHED")
    history = ledger.history()
    assert embargo_ended_on_own_terms(history, ended)
    assert not embargo_ended_on_own_terms(history, ended - 1)


def test_publication_with_no_embargo_is_chance():
    mark = _publication_mark(_vendor_case(with_embargo=False))
    assert (mark.mark, mark.note) == (
        HindsightMark.CHANCE,
        NO_KNOWN_PUBLISHER,
    )


@pytest.mark.parametrize(
    "cause",
    [None, {"kind": "THREAT_SIGNAL", "signals": ["X"]}, {"kind": "OTHER"}],
    ids=["no cause", "a threat signal", "another cause"],
)
def test_publication_after_an_early_terminated_embargo_is_chance(cause):
    ledger = _vendor_case()
    exit_embargo(ledger, content="EARLY", cause=cause)
    mark = _publication_mark(ledger)
    assert (mark.mark, mark.note) == (
        HindsightMark.CHANCE,
        NO_KNOWN_PUBLISHER,
    )


_GAPPED = CaseAdvice(
    case_id="urn:uuid:case-1",
    end_confirmed=False,
    gap=StandingGap(missing_log_indices=[2]),
)


@pytest.mark.parametrize(
    "advice",
    [
        _advice(_advised(_PUBLISH, [(1, 0), (1, 0)], layer=1, top=True)),
        None,
        _GAPPED,
    ],
    ids=["open advice", "no advice", "after a hole"],
)
@pytest.mark.parametrize(
    "after",
    [CS_pxa.PXa, CS_pxa.pXa, CS_pxa.pxA],
    ids=["exploit and public awareness at once", "an exploit", "attacks"],
)
def test_chance_is_chance_whatever_advice_is_open(advice, after):
    """D10: an exploit made public or attacks observed are chance, and so is
    the public becoming aware in the entry that makes the exploit public,
    even beside an advised publication; with no advice open, or none after
    a hole, they are still chance, not unadvised acts."""
    mark = _mark(_state(pxa=after), advice)
    assert (mark.mark, mark.note) == (HindsightMark.CHANCE, UNLISTED_CHANCE)
    assert mark.move is None


@pytest.mark.parametrize(
    ("content", "graded"),
    [("END_TIME_REACHED", True), ("EARLY", False)],
    ids=["ended on its own terms", "ended early"],
)
def test_the_vul_becoming_public_where_the_embargo_ended_is_graded_so(
    content, graded
):
    """D18's fourth case: the embargo ends on its own terms in the very
    entry that makes the case public, so that entry is graded as the
    publication move; an early end there leaves it chance."""
    ledger = _vendor_case()
    ended = exit_embargo(ledger, content=content)
    advice = _advice(_advised(_PUBLISH, [(1, 0), (1, 0)], layer=1, top=True))
    mark = hindsight_mark(
        ended,
        _BEFORE,
        _PUBLIC,
        lambda: advice,
        _VENDOR,
        ended_on_own_terms=embargo_ended_on_own_terms(ledger.history(), ended),
    )
    if graded:
        assert (mark.mark, mark.move) == (HindsightMark.BEST, _PUBLISH)
    else:
        assert (mark.mark, mark.note) == (
            HindsightMark.CHANCE,
            NO_KNOWN_PUBLISHER,
        )


def test_a_later_publication_changes_no_state_and_is_not_a_move():
    """D1: publishing is any publication, but only the first makes the case
    public; a later one changes no state, so its line grades nothing."""
    ledger = _vendor_case()
    exit_embargo(ledger, content="END_TIME_REACHED")
    first = _publication_mark(ledger)
    again = _publication_mark(ledger)
    assert first.mark in GRADED
    assert (again.mark, again.note) == (
        HindsightMark.NOT_A_MOVE,
        NO_STATE_CHANGE,
    )
