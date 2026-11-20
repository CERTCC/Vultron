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

"""Hindsight marks: each step graded by the advice open before it (#6672).

Each mark of the table, the edge-case rules, which move an entry took (the
machine order, the register trigger, the actor's own move) and the mark
model's refusals.  The chance marks are in ``test_hindsight_chance.py``.
"""

import pytest
from pydantic import ValidationError

from test.measure.advice.hindsight_cases import (
    _ACCEPT,
    _ACCEPTED,
    _BEFORE,
    _EMBARGO,
    _EMBARGO_2,
    _FIX,
    _OWNER,
    _PROPOSE_AGAIN,
    _PUBLISH,
    _START,
    _TOP_HARM_FREE,
    _VENDOR,
    _advice,
    _advised,
    _mark,
    _no_advice_wanted,
    _state,
)
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM, EM_Trigger
from vultron.core.states.embargo_register import EmbargoRegisterStatus
from vultron.core.states.rm import RM
from vultron.measure.advice import (
    KEEPS_EVERY_STATE,
    Band,
    CaseAdvice,
    HindsightMark,
    NarrativeMark,
    hindsight_mark,
)
from vultron.measure.advice.case import UnbandedMove
from vultron.measure.advice.hindsight import (
    ADVICE_GAP,
    DID_AS_WELL,
    NO_ADVICE,
    NO_ADVISED_MOVE,
    NO_STATE_CHANGE,
    REGISTER_PROBLEM,
    no_band,
    owns_state,
    register_trigger,
)
from vultron.measure.standing import (
    EMMove,
    StandingGap,
)


def test_a_layer_1_move_of_the_first_band_with_moves_is_best():
    advised = _advised(_ACCEPT, [(1, 0), (1, 0)], layer=1, top=True)
    mark = _mark(_ACCEPTED, _advice(advised, _TOP_HARM_FREE))
    assert mark.mark is HindsightMark.BEST
    assert (mark.move, mark.band, mark.layer) == (
        _ACCEPT,
        Band.HARM_FREE,
        1,
    )
    assert mark.log_index == 7
    assert mark.note is None


def test_a_harm_free_move_that_is_not_best_is_good():
    advised = _advised(_ACCEPT, [(1, 0), (0, 0)], layer=2)
    best = _advised(_FIX, [(2, 0), (1, 0)], layer=1, top=True)
    mark = _mark(_ACCEPTED, _advice(advised, best))
    assert mark.mark is HindsightMark.GOOD
    assert (mark.layer, mark.deepest_layer) == (2, 2)


def test_a_trade_off_move_with_no_harm_free_move_open_is_best():
    """The first edge-case rule: the trade-off band is then the first band
    holding any move, so its layer-1 moves are best."""
    advised = _advised(_ACCEPT, [(1, 0), (-1, 0)], layer=1, top=True)
    other = _advised(_FIX, [(-1, 0), (1, 0)], layer=1, top=True)
    advice = _advice(advised, other)
    assert not advice.band(Band.HARM_FREE).moves
    mark = _mark(_ACCEPTED, advice)
    assert mark.mark is HindsightMark.BEST
    assert mark.band is Band.TRADE_OFF


def test_a_layer_1_trade_off_move_beside_a_harm_free_one_is_sub_optimal():
    """No move dominates it, but the harm-free band holds moves: it is top,
    not best."""
    advised = _advised(_ACCEPT, [(2, 0), (-1, 0)], layer=1, top=True)
    mark = _mark(_ACCEPTED, _advice(advised, _TOP_HARM_FREE))
    assert mark.mark is HindsightMark.SUB_OPTIMAL
    assert mark.note is None


def test_a_sub_optimal_move_a_harm_free_move_dominated_says_one_did_as_well():
    """The second edge-case rule."""
    harm_free = _advised(_FIX, [(1, 0), (0, 0)], layer=1, top=True)
    advised = _advised(_ACCEPT, [(1, 0), (-1, 0)], layer=2, dominated=True)
    mark = _mark(_ACCEPTED, _advice(advised, harm_free))
    assert mark.mark is HindsightMark.SUB_OPTIMAL
    assert mark.note == DID_AS_WELL


def test_an_unhelpful_move_with_every_part_zero_is_neutral():
    advised = _advised(_ACCEPT, [(0, 0), (0, 0)], layer=None)
    mark = _mark(_ACCEPTED, _advice(advised, _TOP_HARM_FREE))
    assert mark.mark is HindsightMark.NEUTRAL
    assert (mark.band, mark.layer) == (Band.UNHELPFUL, None)


@pytest.mark.parametrize(
    "parts",
    [[(-1, 0), (0, 0)], [(0, 0), (0, -1)]],
    ids=["an end part", "an embargo part"],
)
def test_an_unhelpful_move_with_a_vendors_part_negative_is_bad(parts):
    advised = _advised(_ACCEPT, parts, layer=None)
    mark = _mark(_ACCEPTED, _advice(advised, _TOP_HARM_FREE))
    assert mark.mark is HindsightMark.BAD
    assert mark.band is Band.UNHELPFUL


def test_a_move_that_keeps_every_state_is_neutral():
    """An advice-only move: a second proposal while one is open changes the
    register, not the EM state."""
    advice = _advice(
        _TOP_HARM_FREE,
        unbanded=[UnbandedMove(move=_PROPOSE_AGAIN, reason=KEEPS_EVERY_STATE)],
    )
    after = _state(
        register={
            _EMBARGO: EmbargoRegisterStatus.PROPOSED,
            _EMBARGO_2: EmbargoRegisterStatus.PROPOSED,
        }
    )
    mark = _mark(after, advice)
    assert mark.mark is HindsightMark.NEUTRAL
    assert mark.move == _PROPOSE_AGAIN
    assert mark.band is None


def test_a_step_that_changes_no_state_is_not_a_move_and_reads_no_advice():
    no_advice_wanted = _no_advice_wanted(
        "an entry that changes nothing reads no advice"
    )
    mark = hindsight_mark(3, _BEFORE, _BEFORE, no_advice_wanted)
    assert mark.mark is HindsightMark.NOT_A_MOVE
    assert mark.note == NO_STATE_CHANGE
    assert mark.move is None


def test_the_first_entry_has_no_advice_to_be_graded_by():
    assert _mark(_ACCEPTED, None).note == NO_ADVICE


def test_an_entry_after_a_hole_has_no_advice_to_be_graded_by():
    gapped = CaseAdvice(
        case_id="urn:uuid:case-1",
        end_confirmed=False,
        gap=StandingGap(missing_log_indices=[2]),
    )
    mark = _mark(_ACCEPTED, gapped)
    assert (mark.mark, mark.note) == (HindsightMark.NOT_A_MOVE, ADVICE_GAP)


def test_a_change_no_advised_move_makes_is_not_a_move():
    """Report management passing two states in one entry is no one move."""
    mark = _mark(_state(rm=RM.CLOSED), _advice(_TOP_HARM_FREE))
    assert (mark.mark, mark.note) == (
        HindsightMark.NOT_A_MOVE,
        NO_ADVISED_MOVE,
    )


def test_a_move_with_no_band_is_not_a_move_and_says_why():
    reason = "the case has no vendor to score a move for"
    advice = _advice(unbanded=[UnbandedMove(move=_ACCEPT, reason=reason)])
    mark = _mark(_ACCEPTED, advice)
    assert mark.mark is HindsightMark.NOT_A_MOVE
    assert (mark.move, mark.note) == (_ACCEPT, no_band(reason))


_TERMINATE = EMMove(
    participant=_OWNER,
    trigger=EM_Trigger.TERMINATE,
    source=EM.ACTIVE,
    destination=EM.EXITED,
)


def test_an_entry_that_changes_several_machines_is_graded_by_its_first():
    """A publication that also ends the embargo is graded as the
    publication: a case-state event drives the embargo, not the reverse."""
    publish = _advised(_PUBLISH, [(1, 0), (0, 0)], layer=2)
    terminate = _advised(_TERMINATE, [(2, 0), (1, 0)], layer=1, top=True)
    before = _state(register={_EMBARGO: EmbargoRegisterStatus.ACTIVE})
    after = _state(
        pxa=CS_pxa.Pxa,
        register={_EMBARGO: EmbargoRegisterStatus.TERMINATED},
    )
    mark = _mark(
        after,
        _advice(publish, terminate),
        before=before,
        ended_on_own_terms=True,
    )
    assert mark.move == _PUBLISH
    assert mark.mark is HindsightMark.GOOD


def test_a_first_change_no_move_makes_is_never_passed_over():
    """The case made public with no publication move listed, beside a
    report-management move that is listed: the public state decides, so
    the line is not graded as the later machine's move."""
    accept = _advised(_ACCEPT, [(1, 0), (1, 0)], layer=1, top=True)
    after = _state(rm=RM.ACCEPTED, pxa=CS_pxa.Pxa)
    mark = _mark(after, _advice(accept), ended_on_own_terms=True)
    assert (mark.mark, mark.note) == (
        HindsightMark.NOT_A_MOVE,
        NO_ADVISED_MOVE,
    )
    assert mark.move is None


def test_an_entry_that_breaks_the_embargo_register_says_so():
    """Two embargoes in force give no EM state, so no EM move is the step."""
    after = _state(
        register={
            _EMBARGO: EmbargoRegisterStatus.ACTIVE,
            _EMBARGO_2: EmbargoRegisterStatus.ACTIVE,
        }
    )
    before = _state(register={_EMBARGO: EmbargoRegisterStatus.ACTIVE})
    mark = _mark(after, _advice(_TOP_HARM_FREE), before=before)
    assert (mark.mark, mark.note) == (
        HindsightMark.NOT_A_MOVE,
        REGISTER_PROBLEM,
    )


def test_an_embargo_change_is_graded_as_the_move_its_register_step_names():
    advised = _advised(_START, [(1, 0), (1, 0)], layer=1, top=True)
    after = _state(register={_EMBARGO: EmbargoRegisterStatus.ACTIVE})
    mark = _mark(after, _advice(advised), actor=_OWNER)
    assert (mark.mark, mark.move) == (HindsightMark.BEST, _START)


@pytest.mark.parametrize(
    ("before", "after", "trigger"),
    [
        ({}, {_EMBARGO: "PROPOSED"}, EM_Trigger.PROPOSE),
        ({_EMBARGO: "PROPOSED"}, {_EMBARGO: "ACTIVE"}, EM_Trigger.ACCEPT),
        ({_EMBARGO: "PROPOSED"}, {_EMBARGO: "REJECTED"}, EM_Trigger.REJECT),
        ({_EMBARGO: "PROPOSED"}, {_EMBARGO: "CANCELLED"}, EM_Trigger.REJECT),
        (
            {_EMBARGO: "ACTIVE", _EMBARGO_2: "PROPOSED"},
            {_EMBARGO: "TERMINATED", _EMBARGO_2: "CANCELLED"},
            EM_Trigger.TERMINATE,
        ),
        (
            {_EMBARGO: "ACTIVE", _EMBARGO_2: "PROPOSED"},
            {_EMBARGO: "SUPERSEDED", _EMBARGO_2: "ACTIVE"},
            EM_Trigger.ACCEPT,
        ),
        ({_EMBARGO: "ACTIVE"}, {_EMBARGO: "ACTIVE"}, None),
    ],
)
def test_a_register_step_names_its_em_trigger(before, after, trigger):
    def statuses(register):
        return {k: EmbargoRegisterStatus(v) for k, v in register.items()}

    assert register_trigger(statuses(before), statuses(after)) is trigger


def test_only_rm_and_fix_path_moves_move_the_participant_they_name():
    assert owns_state(_ACCEPT) and owns_state(_FIX)
    assert not owns_state(_PUBLISH)
    assert not owns_state(_START)


@pytest.mark.parametrize(
    "fields",
    [
        {"mark": HindsightMark.BEST},
        {"mark": HindsightMark.GOOD, "move": _ACCEPT},
        {"mark": HindsightMark.CHANCE},
        {
            "mark": HindsightMark.NEUTRAL,
            "move": _ACCEPT,
            "layer": 1,
            "deepest_layer": 1,
        },
        {
            "mark": HindsightMark.GOOD,
            "move": _ACCEPT,
            "band": Band.HARM_FREE,
            "layer": 3,
            "deepest_layer": 2,
        },
        {
            "mark": HindsightMark.GOOD,
            "move": _ACCEPT,
            "band": Band.HARM_FREE,
            "layer": 1,
        },
        {
            "mark": HindsightMark.BEST,
            "move": _ACCEPT,
            "band": Band.UNHELPFUL,
            "layer": 1,
            "deepest_layer": 1,
        },
        {
            "mark": HindsightMark.BEST,
            "move": _ACCEPT,
            "layer": 1,
            "deepest_layer": 1,
        },
    ],
    ids=[
        "a best mark with no move",
        "a good mark with no layer",
        "a chance mark that does not say why",
        "a neutral mark with a layer",
        "a layer deeper than its advice's deepest",
        "a layer without its advice's deepest layer",
        "a best mark in the unhelpful band",
        "a best mark with no band",
    ],
)
def test_a_mark_that_does_not_fit_its_kind_is_refused(fields):
    with pytest.raises(ValidationError):
        NarrativeMark(log_index=0, **fields)


def test_of_two_moves_that_make_one_change_the_actors_own_is_graded():
    """An embargo step is the same joint step whoever may make it, so
    either move would do; the acting participant's own is the one named."""
    owners = _advised(_START, [(1, 0), (1, 0)], layer=1, top=True)
    vendors = _advised(
        _START.model_copy(update={"participant": _VENDOR}),
        [(1, 0), (1, 0)],
        layer=1,
        top=True,
    )
    after = _state(register={_EMBARGO: EmbargoRegisterStatus.ACTIVE})
    for actor, move in ((_OWNER, owners), (_VENDOR, vendors)):
        mark = _mark(after, _advice(owners, vendors), actor=actor)
        assert mark.move == move.move
