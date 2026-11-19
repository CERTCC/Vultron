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

Each test builds the advice open before one entry by hand, with the states
the case reached just before and just after it, so each mark of the table
and each edge-case rule is pinned to the band and layer that sets it.
"""

from collections.abc import Sequence
from fractions import Fraction

import pytest
from pydantic import ValidationError

from vultron.core.states.cs import CS, CS_d, CS_pxa, CS_vf
from vultron.core.states.cs_invariants import CSEvent
from vultron.core.states.em import EM, EM_Trigger
from vultron.core.states.embargo_register import EmbargoRegisterStatus
from vultron.core.states.rm import RM
from vultron.measure.advice import (
    BAND_ORDER,
    CHANCE_EVENT,
    DOMINATED_BY_HARM_FREE,
    KEEPS_EVERY_STATE,
    AdvisedMove,
    Band,
    BandAdvice,
    CaseAdvice,
    HindsightMark,
    NarrativeMark,
    ScopeParts,
    VendorHarm,
    VendorShift,
    band,
    harms,
    hindsight_mark,
)
from vultron.measure.advice.case import AllowedMove, UnbandedMove
from vultron.measure.advice.hindsight import (
    ADVICE_GAP,
    DID_AS_WELL,
    NO_ADVICE,
    NO_ADVISED_MOVE,
    NO_STATE_CHANGE,
    UNOBSERVED_CHANCE,
    no_band,
    owns_state,
    register_trigger,
)
from vultron.measure.history import ReachedParticipant, ReachedState
from vultron.measure.standing import (
    CSMove,
    EMMove,
    RMMove,
    StandingGap,
)

_VENDOR = "https://example.org/actors/vendor"
_VENDOR_2 = "https://example.org/actors/vendor-2"
_OWNER = "https://example.org/actors/owner"
_EMBARGO = "urn:uuid:embargo-1"
_EMBARGO_2 = "urn:uuid:embargo-2"

_ACCEPT = RMMove(participant=_VENDOR, source=RM.VALID, destination=RM.ACCEPTED)
_FIX = CSMove(
    participant=_VENDOR,
    event=CSEvent.F,
    source=CS.Vfdpxa,
    destination=CS.VFdpxa,
)
_PUBLISH = CSMove(
    participant=_VENDOR,
    event=CSEvent.P,
    source=CS.Vfdpxa,
    destination=CS.VfdPxa,
)
_EXPLOIT = CSMove(
    participant=_VENDOR,
    event=CSEvent.X,
    source=CS.Vfdpxa,
    destination=CS.VfdpXa,
)
_START = EMMove(
    participant=_OWNER,
    trigger=EM_Trigger.ACCEPT,
    source=EM.PROPOSED,
    destination=EM.ACTIVE,
)
_PROPOSE_AGAIN = EMMove(
    participant=_VENDOR,
    trigger=EM_Trigger.PROPOSE,
    source=EM.PROPOSED,
    destination=EM.PROPOSED,
)

_Parts = tuple[int, int]


def _advised(
    move: AllowedMove,
    parts: Sequence[_Parts],
    layer: int | None,
    top: bool = False,
    dominated: bool = False,
) -> AdvisedMove:
    """*move*, with each vendor's (end, embargo) part, in the band its
    parts set."""
    shift = tuple(ScopeParts(Fraction(e), Fraction(m)) for e, m in parts)
    vendors = (_VENDOR, _VENDOR_2)
    return AdvisedMove(
        move=move,
        shift=tuple(
            VendorShift(vendor=v, end=p.end, embargo=p.embargo)
            for v, p in zip(vendors, shift, strict=True)
        ),
        band=band(shift),
        layer=layer,
        top=top,
        leading_among_yours=False,
        harms=tuple(
            VendorHarm(vendor=vendors[h.vendor - 1], part=h.part, size=h.size)
            for h in harms(shift)
        ),
        dominated_by_harm_free=DOMINATED_BY_HARM_FREE if dominated else None,
    )


def _advice(
    *moves: AdvisedMove, unbanded: Sequence[UnbandedMove] = ()
) -> CaseAdvice:
    return CaseAdvice(
        case_id="urn:uuid:case-1",
        end_confirmed=False,
        vendors=(_VENDOR, _VENDOR_2),
        bands=tuple(BandAdvice.of(b, moves) for b in BAND_ORDER),
        unbanded=tuple(unbanded),
    )


def _state(
    rm: RM = RM.VALID,
    vf: CS_vf = CS_vf.Vf,
    pxa: CS_pxa = CS_pxa.pxa,
    register: dict[str, EmbargoRegisterStatus] | None = None,
) -> ReachedState:
    return ReachedState(
        participants=[
            ReachedParticipant(participant=_VENDOR, rm=rm, vf=vf, d=CS_d.d),
            ReachedParticipant(participant=_OWNER),
        ],
        pxa=pxa,
        embargo_register=register
        or {_EMBARGO: EmbargoRegisterStatus.PROPOSED},
    )


_BEFORE = _state()
_ACCEPTED = _state(rm=RM.ACCEPTED)
_FIXED = _state(vf=CS_vf.VF)
_PUBLIC = _state(pxa=CS_pxa.Pxa)


def _mark(
    after: ReachedState,
    advice: CaseAdvice | None,
    before: ReachedState = _BEFORE,
    actor: str | None = _VENDOR,
) -> NarrativeMark:
    return hindsight_mark(7, before, after, lambda: advice, actor)


#: A harm-free move in layer 1, so harm-free is the first band with moves.
_TOP_HARM_FREE = _advised(_FIX, [(1, 0), (0, 0)], layer=1, top=True)


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
    assert mark.note == UNOBSERVED_CHANCE


def test_making_the_vul_public_is_graded_as_the_move_it_is():
    """Publication is a participant's move, not a chance event: the case
    manager adopting the public state is graded by the advice's move."""
    advised = _advised(_PUBLISH, [(1, 0), (1, 0)], layer=1, top=True)
    case_managers = UnbandedMove(
        move=_PUBLISH.model_copy(update={"participant": _OWNER}),
        reason="rm.close by the owner moves no vendor's state",
    )
    advice = _advice(advised, unbanded=[case_managers])
    mark = _mark(_PUBLIC, advice, actor=_OWNER)
    assert mark.mark is HindsightMark.BEST
    assert mark.move == _PUBLISH


def test_a_step_that_changes_no_state_is_not_a_move_and_reads_no_advice():
    def no_advice_wanted() -> CaseAdvice:
        raise AssertionError("an entry that changes nothing reads no advice")

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


def test_an_entry_that_changes_several_machines_is_graded_by_its_first():
    """A publication that also ends the embargo is graded as the
    publication: a case-state event drives the embargo, not the reverse."""
    publish = _advised(_PUBLISH, [(1, 0), (1, 0)], layer=1, top=True)
    start = _advised(_START, [(0, 0), (0, -1)], layer=None)
    after = _state(
        pxa=CS_pxa.Pxa,
        register={_EMBARGO: EmbargoRegisterStatus.ACTIVE},
    )
    mark = _mark(after, _advice(publish, start))
    assert mark.move == _PUBLISH
    assert mark.mark is HindsightMark.BEST


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
    ],
    ids=[
        "a best mark with no move",
        "a good mark with no layer",
        "a chance mark that does not say why",
        "a neutral mark with a layer",
        "a layer deeper than its advice's deepest",
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
