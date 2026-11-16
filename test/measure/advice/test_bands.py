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

"""Bands, dominance, layers and marks over synthetic shifts (ADR-0200)."""

from fractions import Fraction
from itertools import product

import pytest

from vultron.measure.advice import (
    BAND_ORDER,
    Band,
    Harm,
    MoveAdvice,
    Part,
    ScopeParts,
    ScopeShift,
    advise,
    band,
    deciding_parts,
    dominates,
    harms,
    layers,
)


def _shift(*parts: tuple[float, float]) -> ScopeShift:
    return tuple(
        ScopeParts(
            Fraction(e).limit_denominator(), Fraction(m).limit_denominator()
        )
        for e, m in parts
    )


_ZERO = _shift((0, 0), (0, 0))


@pytest.mark.parametrize(
    "shift, expected",
    [
        (_shift((1, 0), (0, 0)), Band.HARM_FREE),
        (_shift((1, -5), (0, 0)), Band.HARM_FREE),
        (_shift((1, 0), (-1, 0)), Band.TRADE_OFF),
        (_shift((-1, 5), (0, 0)), Band.UNHELPFUL),
        (_shift((0, 1), (0, 0)), Band.HARM_FREE),
        (_shift((0, 1), (0, -1)), Band.TRADE_OFF),
        (_shift((0, -1), (0, 0)), Band.UNHELPFUL),
        (_ZERO, Band.UNHELPFUL),
    ],
    ids=[
        "end gain",
        "end gain beside an embargo loss",
        "end gain and end loss",
        "end loss beside an embargo gain",
        "embargo gain alone",
        "embargo gain and loss",
        "embargo loss alone",
        "no change",
    ],
)
def test_a_band_comes_from_the_end_parts_first(shift, expected):
    assert band(shift) is expected


def test_the_deciding_parts_are_the_embargo_parts_only_when_every_end_is_zero():
    assert deciding_parts(_shift((0, 1), (0, -1))) == (
        Part.EMBARGO,
        (Fraction(1), Fraction(-1)),
    )
    assert deciding_parts(_shift((0, 1), (2, 0)))[0] is Part.END


def test_a_threshold_counts_small_parts_as_zero():
    shift = _shift((0.01, 0), (-2, 0))
    assert band(shift) is Band.TRADE_OFF
    assert band(shift, Fraction(1, 20)) is Band.UNHELPFUL
    # Once every end part is below it, the embargo parts decide.
    assert band(_shift((0.01, 1), (0, 0)), Fraction(1, 20)) is Band.HARM_FREE


def test_a_negative_threshold_is_refused():
    with pytest.raises(ValueError, match="negative"):
        band(_ZERO, Fraction(-1))


def test_dominance_takes_the_ends_first_then_the_embargo():
    end_gain = _shift((1, -9), (0, -9))
    embargo_gain = _shift((0, 9), (0, 9))
    assert dominates(end_gain, embargo_gain)
    assert not dominates(embargo_gain, end_gain)
    assert dominates(_shift((0, 2), (0, 1)), _shift((0, 1), (0, 1)))
    assert not dominates(_shift((0, 1), (0, 1)), _shift((0, 1), (0, 1)))


def test_two_moves_that_trade_off_do_not_dominate_each_other():
    x, y = _shift((1, 0), (-1, 0)), _shift((-1, 0), (1, 0))
    assert not dominates(x, y)
    assert not dominates(y, x)


def test_shifts_of_different_cases_do_not_compare():
    with pytest.raises(ValueError, match="do not compare"):
        dominates(_shift((1, 0)), _ZERO)


def test_a_layer_is_the_depth_in_the_dominance_order():
    shifts = {
        "a": _shift((2, 0), (2, 0)),
        "b": _shift((1, 0), (1, 0)),
        "c": _shift((3, 0), (-1, 0)),
        "d": _shift((0, 0), (0, 0)),
    }
    assert layers(shifts) == {"a": 1, "c": 1, "b": 2, "d": 3}


def test_every_negative_part_is_a_harm_with_its_vendor_and_size():
    assert harms(_shift((1, -1), (-2, 0))) == (
        Harm(1, Part.EMBARGO, Fraction(-1)),
        Harm(2, Part.END, Fraction(-2)),
    )


def test_marks_go_only_to_harm_free_and_trade_off_moves():
    shifts = {
        "fix": _shift((1, 0), (0, 0)),
        "publish": _shift((2, 0), (-1, 0)),
        "dominated trade-off": _shift((0.5, 0), (-1, 0)),
        "nothing": _ZERO,
    }
    advice = advise(shifts, yours=lambda m: m != "fix")
    assert advice["fix"].top and advice["publish"].top
    assert not advice["dominated trade-off"].top
    assert advice["dominated trade-off"].layer == 2
    assert not advice["nothing"].top
    assert advice["nothing"].band is Band.UNHELPFUL
    assert advice["publish"].leading_among_yours
    assert not advice["fix"].leading_among_yours
    assert not advice["nothing"].leading_among_yours
    assert advice["publish"].harms == (Harm(2, Part.END, Fraction(-1)),)


def test_leading_among_yours_ignores_moves_that_are_not_yours():
    shifts = {
        "theirs": _shift((2, 0), (2, 0)),
        "yours": _shift((1, 0), (1, 0)),
    }
    advice = advise(shifts, yours=lambda m: m == "yours")
    assert not advice["yours"].top
    assert advice["yours"].leading_among_yours


def test_the_harm_free_band_can_be_empty():
    shifts = {"a": _shift((1, 0), (-1, 0)), "b": _ZERO}
    advice = advise(shifts, yours=lambda m: True)
    assert {a.band for a in advice.values()} == {
        Band.TRADE_OFF,
        Band.UNHELPFUL,
    }
    assert advice["a"].top


_VALUES = (-1.0, 0.0, 1.0)
_SMALL_SHIFTS = [
    _shift((e1, m1), (e2, m2)) for e1, m1, e2, m2 in product(_VALUES, repeat=4)
]
"""Every two-vendor shift with parts in -1, 0, 1."""


def test_a_move_that_dominates_a_harm_free_move_is_harm_free():
    """P4, over every small shift rather than the cases alone."""
    for x in _SMALL_SHIFTS:
        for y in _SMALL_SHIFTS:
            if dominates(x, y) and band(y) is Band.HARM_FREE:
                assert band(x) is Band.HARM_FREE, (x, y)


def test_dominance_is_a_strict_partial_order_over_small_shifts():
    for x in _SMALL_SHIFTS:
        assert not dominates(x, x)
        for y in _SMALL_SHIFTS:
            if dominates(x, y):
                assert not dominates(y, x)


def test_equal_ends_with_traded_embargo_parts_do_not_dominate():
    x, y = _shift((1, 1), (0, -1)), _shift((1, -1), (0, 1))
    assert not dominates(x, y)
    assert not dominates(y, x)
    assert layers({"x": x, "y": y}) == {"x": 1, "y": 1}


def test_the_advice_gives_no_combined_score():
    """SHD-03-002: a move's advice holds its shift by vendor and no case score."""
    assert set(MoveAdvice._fields) == {
        "move",
        "shift",
        "band",
        "layer",
        "top",
        "leading_among_yours",
        "harms",
    }


def test_a_higher_vendor_sum_does_not_put_a_move_first():
    """SHD-03-002: the harm-free move comes first though its sum is lower."""
    shifts = {
        "big sum": _shift((3, 0), (-1, 0)),
        "small sum": _shift((1, 0), (0, 0)),
    }
    advice = advise(shifts, yours=lambda m: True)
    assert advice["small sum"].band is Band.HARM_FREE
    assert advice["big sum"].band is Band.TRADE_OFF
    assert BAND_ORDER.index(advice["small sum"].band) < BAND_ORDER.index(
        advice["big sum"].band
    )
