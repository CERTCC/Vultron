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

"""Each vendor's scope and a move's outcome shift in it (#6450, ADR-0200)."""

from fractions import Fraction

import pytest

from test.measure.advice.cases import CASES, Case
from vultron.errors import VultronInvalidStateTransitionError
from vultron.measure.advice import (
    CHANCE_EVENTS,
    ScopeParts,
    chance_values,
    open_moves,
    outcome_shift,
)
from vultron.measure.advice.shifts import scope_desiderata
from vultron.measure.baselines import (
    EXTENDED,
    ORIGINAL,
    Event,
    EventKind,
    Group,
)

_K = EventKind
_ZERO = ScopeParts(Fraction(0), Fraction(0))


def _named(notation: str):
    (found,) = [d for d in (*ORIGINAL, *EXTENDED) if d.notation == notation]
    return found


def _case(name: str) -> Case:
    (found,) = [c for c in CASES if c.name == name]
    return found


def test_a_scope_holds_the_twelve_report_handling_and_embargo_desiderata():
    scope = scope_desiderata()
    assert set(ORIGINAL) <= scope
    assert {d for d in EXTENDED if d.group is Group.REPORT_HANDLING} <= scope
    assert not {d for d in scope if d.group is Group.MULTI_PARTY}


def test_a_scope_counts_each_group_of_equivalent_desiderata_once():
    scope = scope_desiderata()
    assert _named(r"$\evE \prec \evP$") in scope
    assert _named(r"$\evExOwn \prec \evP$") in scope
    assert _named(r"$\evF_i \prec \evExOwn$") in scope
    for dropped in (
        r"$\evE \prec \evX$",
        r"$\evE \prec \evA$",
        r"$\evExOwn \prec \evX$",
        r"$\evExOwn \prec \evA$",
    ):
        assert _named(dropped) not in scope


def test_no_open_move_is_a_chance_event():
    for case in CASES:
        kinds = {m.event.kind for m in open_moves(case.prefix)}
        assert not kinds & CHANCE_EVENTS
        assert _K.P in kinds


def test_a_shift_is_the_chance_value_after_the_move_less_the_one_before():
    case = _case("ready-unready embargo")
    move = case.move(_K.P)
    before = chance_values(case.prefix)
    after = chance_values(case.prefix.then(move))
    assert outcome_shift(case.prefix, move) == tuple(
        ScopeParts(a.end - b.end, a.embargo - b.embargo)
        for a, b in zip(after, before, strict=True)
    )


@pytest.mark.parametrize(
    "case", [c for c in CASES if "unaware" in c.readiness], ids=str
)
def test_notifying_a_vendor_raises_only_that_vendors_end_part(case: Case):
    vendor = case.readiness.index("unaware") + 1
    shift = outcome_shift(case.prefix, case.move(_K.V, vendor))
    assert shift[vendor - 1].end > 0
    assert all(p.end == 0 for i, p in enumerate(shift, 1) if i != vendor)


@pytest.mark.parametrize("case", CASES, ids=str)
def test_a_vendors_own_fix_changes_no_other_vendors_scope(case: Case):
    for move in case.moves:
        if move.event.kind not in (_K.F, _K.D):
            continue
        vendor = move.event.vendor
        assert vendor is not None
        shift = outcome_shift(case.prefix, move)
        assert shift[vendor - 1].end > 0
        others = [p for i, p in enumerate(shift, 1) if i != vendor]
        assert all(p == _ZERO for p in others), move.event


@pytest.mark.parametrize("case", [c for c in CASES if c.embargo], ids=str)
def test_the_chance_model_gives_an_embargo_revision_no_effect(case: Case):
    """The walk cannot see an embargo's protection (#6492)."""
    shift = outcome_shift(case.prefix, case.move(_K.REVISION_PROPOSED))
    assert all(p == _ZERO for p in shift)


def test_ending_an_embargo_on_its_terms_lowers_an_unready_vendors_embargo_part():
    """``F_i ≺ Ex_own`` breaks for a vendor with no fix, and outweighs the
    one ``Ex_own`` desideratum the scope counts."""
    case = _case("ready-unready embargo")
    ready, unready = outcome_shift(case.prefix, case.move(_K.EXIT_OWN_TERMS))
    assert ready.embargo > 0
    assert unready.embargo < 0
    assert ready.end == unready.end == 0


def test_a_move_the_case_does_not_allow_is_refused():
    case = _case("ready-unready embargo")
    with pytest.raises(VultronInvalidStateTransitionError):
        outcome_shift(case.prefix, Event(_K.F, 1))
