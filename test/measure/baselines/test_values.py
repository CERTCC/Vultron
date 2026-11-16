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

"""Each vendor's desiderata values from any point of a joint walk (#6449)."""

from fractions import Fraction

import pytest

from vultron.core.states.em import EM
from vultron.errors import VultronInvalidStateTransitionError
from vultron.measure.baselines import (
    EXTENDED,
    ONE_VENDOR_MODEL,
    ORIGINAL,
    TWO_VENDOR_MODEL,
    Desideratum,
    Event,
    EventKind,
    JointModel,
    Step,
    VendorDesideratum,
    WalkPrefix,
    baseline,
    desiderata_values,
    expected_change,
    expected_outcomes,
    outcome_change,
    replay,
    scope_chances,
    take_step,
    vendor_desiderata,
)
from vultron.measure.baselines.desiderata import (
    JOINT_TO_CS,
    ModelName,
    joint_values,
)
from vultron.measure.baselines.joint import JointState
from vultron.measure.baselines.walk import difference

_K = EventKind


def _desideratum(notation: str) -> Desideratum:
    (found,) = [d for d in (*ORIGINAL, *EXTENDED) if d.notation == notation]
    return found


_F_BEFORE_P = _desideratum(r"$\evF_i \prec \evP$")
_V_BEFORE_F_J = _desideratum(r"$\evV_i \prec \evF_j$")
_V_BEFORE_P = _desideratum(r"$\evV \prec \evP$")
_E_BEFORE_P = _desideratum(r"$\evE \prec \evP$")


def _active_start(
    model: JointModel, state: JointState
) -> Step[JointState, Event]:
    """Accepting the pending proposal, the embargo starting as ``ACTIVE``."""
    (step,) = [
        s
        for s in model.steps(state)
        if s.event == Event(_K.EMBARGO_START) and s.state.em is EM.ACTIVE
    ]
    return step


def _walk(
    model: JointModel, events: list[Event]
) -> WalkPrefix[JointState, Event]:
    """The prefix *events* reach, an embargo starting as ``ACTIVE``."""
    prefix: WalkPrefix[JointState, Event] = WalkPrefix(model.initial)
    for event in events:
        move: Event | Step[JointState, Event] = event
        if event.kind is _K.EMBARGO_START:
            move = _active_start(model, prefix.state)
        prefix = prefix.then(take_step(model, prefix.state, move))
    return prefix


# Vendor 1 has fixed and deployed; vendor 2 accepted and closed its report
# with no fix; the embargo ended on its own terms; nothing is public.
_MID_CASE = [
    Event(_K.V, 1),
    Event(_K.V, 2),
    Event(_K.EMBARGO_PROPOSED),
    Event(_K.EMBARGO_START),
    Event(_K.VALIDATED, 1),
    Event(_K.ACCEPTED, 1),
    Event(_K.F, 1),
    Event(_K.D, 1),
    Event(_K.VALIDATED, 2),
    Event(_K.ACCEPTED, 2),
    Event(_K.CLOSED, 2),
    Event(_K.EXIT_OWN_TERMS),
]


def test_every_value_at_the_start_is_the_baseline():
    values = desiderata_values(WalkPrefix(TWO_VENDOR_MODEL.initial))
    assert set(values) == set(vendor_desiderata(2))
    for key, value in values.items():
        assert value == baseline(key.desideratum), key


def test_a_two_vendor_mid_case_value_by_hand():
    prefix = _walk(TWO_VENDOR_MODEL, _MID_CASE)
    values = desiderata_values(prefix)
    # Vendor 2 (Closed, Vf, d; pxa; embargo exited) can take F, P, X or A
    # next, each 1/4; D waits for F, and X forces P next.  F first meets
    # F_2 ≺ P; P or X first breaks it; A first leaves F, P and X, each 1/3,
    # of which only F meets it.  So 1/4 + 1/4 · 1/3 = 1/3.
    assert values[VendorDesideratum(_F_BEFORE_P, 2)] == Fraction(1, 3)
    # Vendor 1 fixed before anything public: met, whatever comes next.
    assert values[VendorDesideratum(_F_BEFORE_P, 1)] == 1
    # Each vendor learned of the vul before the other's fix (vendor 2 has
    # none, and vendor 1's came after V_2).
    assert values[VendorDesideratum(_V_BEFORE_F_J, 1, 2)] == 1
    assert values[VendorDesideratum(_V_BEFORE_F_J, 2, 1)] == 1


def test_a_moves_expected_change_is_after_minus_before_for_each_vendor():
    prefix = _walk(TWO_VENDOR_MODEL, _MID_CASE)
    fix = expected_change(prefix, Event(_K.F, 2))
    assert fix[VendorDesideratum(_F_BEFORE_P, 2)] == 1 - Fraction(1, 3)
    # Vendor 2's fix is no move in vendor 1's one-vendor projection.
    assert fix[VendorDesideratum(_F_BEFORE_P, 1)] == 0
    public = expected_change(prefix, Event(_K.P))
    assert public[VendorDesideratum(_F_BEFORE_P, 2)] == -Fraction(1, 3)
    assert public[VendorDesideratum(_F_BEFORE_P, 1)] == 0


def test_a_shared_event_moves_every_vendors_values():
    start = WalkPrefix(TWO_VENDOR_MODEL.initial)
    proposal = expected_change(start, Event(_K.EMBARGO_PROPOSED))
    shifts = {
        proposal[VendorDesideratum(_E_BEFORE_P, vendor)] for vendor in (1, 2)
    }
    assert len(shifts) == 1
    shift = shifts.pop()
    assert shift is not None and shift > 0


def test_notifying_a_vendor_raises_its_own_awareness_value():
    start = WalkPrefix(TWO_VENDOR_MODEL.initial)
    notify = expected_change(start, Event(_K.V, 2))
    assert notify[VendorDesideratum(_V_BEFORE_P, 2)] == 1 - Fraction(1, 3)
    assert notify[VendorDesideratum(_V_BEFORE_P, 1)] == 0


# The vendor invalidates and closes the report, everything goes public, and
# only then is the fix ready and deployed: no step is left.
_UNVALIDATED_TO_THE_END = [
    Event(_K.V, 1),
    Event(_K.INVALIDATED, 1),
    Event(_K.CLOSED, 1),
    Event(_K.P),
    Event(_K.X),
    Event(_K.A),
    Event(_K.F, 1),
    Event(_K.D, 1),
]


def test_an_ended_case_has_its_own_outcomes():
    prefix = _walk(ONE_VENDOR_MODEL, _UNVALIDATED_TO_THE_END)
    assert not ONE_VENDOR_MODEL.steps(prefix.state)
    values = desiderata_values(prefix)
    assert values[VendorDesideratum(_V_BEFORE_P, 1)] == 1
    assert values[VendorDesideratum(_F_BEFORE_P, 1)] == 0
    # Scoped to vendors whose report reaches Valid, which this one never did.
    accepted_first = _desideratum(r"$\evAc_i \prec \evP$")
    assert values[VendorDesideratum(accepted_first, 1)] is None
    assert set(values.values()) <= {0, 1, None}


def test_a_change_is_none_where_the_scope_can_no_longer_be_met():
    prefix = _walk(ONE_VENDOR_MODEL, _UNVALIDATED_TO_THE_END[:-1])
    change = expected_change(prefix, Event(_K.D, 1))
    accepted_first = _desideratum(r"$\evAc_i \prec \evP$")
    assert change[VendorDesideratum(accepted_first, 1)] is None


def test_a_step_the_case_does_not_allow_is_refused():
    with pytest.raises(
        VultronInvalidStateTransitionError, match="not allowed"
    ):
        expected_change(WalkPrefix(TWO_VENDOR_MODEL.initial), Event(_K.F, 1))


def test_each_vendor_has_every_desideratum_and_one_pair_per_other_vendor():
    keys = vendor_desiderata(3)
    for vendor in (1, 2, 3):
        mine = [k for k in keys if k.vendor == vendor]
        pairs = sorted(k.other for k in mine if k.other is not None)
        assert pairs == [v for v in (1, 2, 3) if v != vendor]
        assert len(mine) == len(ORIGINAL) + len(EXTENDED) - 1 + 2


def test_a_one_vendor_case_has_no_two_vendor_desideratum():
    assert all(k.other is None for k in vendor_desiderata(1))
    assert len(vendor_desiderata(1)) == len(ORIGINAL) + len(EXTENDED) - 1


def test_a_case_needs_a_vendor():
    with pytest.raises(ValueError, match="at least one vendor"):
        vendor_desiderata(0)


def test_a_three_vendor_case_takes_each_value_from_its_own_model():
    model = JointModel(3)
    prefix = WalkPrefix(model.initial)
    values = desiderata_values(prefix)
    assert set(values) == set(vendor_desiderata(3))
    for key, value in values.items():
        assert value == baseline(key.desideratum), key
    notify = expected_change(prefix, Event(_K.V, 3))
    assert notify[VendorDesideratum(_V_BEFORE_P, 3)] == 1 - Fraction(1, 3)
    # V_3 has occurred and F_1 has not: met, whatever comes next.
    assert notify[VendorDesideratum(_V_BEFORE_F_J, 3, 1)] == 1 - baseline(
        _V_BEFORE_F_J
    )
    # Vendor 3's step is no step in the projections that leave it out.
    for untouched in (
        VendorDesideratum(_V_BEFORE_F_J, 1, 2),
        VendorDesideratum(_V_BEFORE_F_J, 2, 1),
        VendorDesideratum(_V_BEFORE_P, 1),
        VendorDesideratum(_V_BEFORE_P, 2),
    ):
        assert notify[untouched] == 0, untouched


def test_the_six_event_model_has_no_joint_table():
    with pytest.raises(ValueError, match="not a joint model"):
        joint_values(ModelName.CASE_STATE, _V_BEFORE_P.query)


def test_a_baseline_no_walk_can_scope_is_refused():
    never = _V_BEFORE_P._replace(
        model=ModelName.ONE_VENDOR,
        query=_V_BEFORE_P.query._replace(given=frozenset({Event(_K.V, 2)})),
    )
    with pytest.raises(ValueError, match="no walk on the"):
        baseline(never)


def test_the_event_map_cannot_be_changed():
    with pytest.raises(TypeError):
        JOINT_TO_CS[Event(_K.V, 1)] = JOINT_TO_CS[Event(_K.P)]  # type: ignore[index]


def test_a_pair_value_seats_the_vendor_first_and_the_other_second():
    # V_1 alone has occurred.  For vendor 2 against vendor 1 the ordering
    # V_2 ≺ F_1 is still open; it is the same question as V_1 ≺ F_2 after
    # V_2 alone, with the vendors' seats swapped.
    after_v1 = desiderata_values(replay(TWO_VENDOR_MODEL, [Event(_K.V, 1)]))
    after_v2 = desiderata_values(replay(TWO_VENDOR_MODEL, [Event(_K.V, 2)]))
    open_pair = after_v1[VendorDesideratum(_V_BEFORE_F_J, 2, 1)]
    assert open_pair == Fraction(93, 100)
    assert open_pair == after_v2[VendorDesideratum(_V_BEFORE_F_J, 1, 2)]
    three = desiderata_values(replay(JointModel(3), [Event(_K.V, 1)]))
    assert three[VendorDesideratum(_V_BEFORE_F_J, 2, 1)] == open_pair
    assert three[VendorDesideratum(_V_BEFORE_F_J, 3, 1)] == open_pair
    assert three[VendorDesideratum(_V_BEFORE_F_J, 2, 3)] == Fraction(393, 400)


def test_values_and_changes_need_a_vendor():
    empty = WalkPrefix(TWO_VENDOR_MODEL.initial._replace(vendors=()))
    with pytest.raises(ValueError, match="at least one vendor"):
        desiderata_values(empty)
    with pytest.raises(ValueError, match="at least one vendor"):
        expected_change(empty, Event(_K.P))


def test_accepting_an_embargo_is_valued_by_the_step_it_takes():
    proposed = replay(ONE_VENDOR_MODEL, [Event(_K.EMBARGO_PROPOSED)])
    with pytest.raises(VultronInvalidStateTransitionError, match="ambiguous"):
        expected_change(proposed, Event(_K.EMBARGO_START))
    accept = _active_start(ONE_VENDOR_MODEL, proposed.state)
    change = expected_change(proposed, accept)
    after = desiderata_values(proposed.then(accept))
    before = desiderata_values(proposed)
    assert change == {
        key: difference(after[key], before[key]) for key in before
    }
    assert any(value for value in change.values())


_VA_BEFORE_P = _desideratum(r"$\evVa_i \prec \evP$")
_INVALID = [Event(_K.V, 1), Event(_K.INVALIDATED, 1)]


def test_an_invalid_reports_scope_is_a_coin_toss_from_there() -> None:
    # From RM Invalid the vendor's report leaves only by Va or C, each 1/2
    # whenever the vendor moves; no case event blocks either.  So the
    # validation scope is entered with chance 1/2.
    prefix = replay(ONE_VENDOR_MODEL, _INVALID)
    key = VendorDesideratum(_VA_BEFORE_P, 1)
    value = desiderata_values(prefix)[key]
    assert value is not None
    assert scope_chances(prefix)[key] == Fraction(1, 2)
    assert expected_outcomes(prefix)[key] == Fraction(1, 2) + value / 2
    # An unscoped desideratum is entered for certain, its outcome its value.
    unscoped = VendorDesideratum(_F_BEFORE_P, 1)
    assert scope_chances(prefix)[unscoped] == 1
    assert (
        expected_outcomes(prefix)[unscoped]
        == (desiderata_values(prefix)[unscoped])
    )


def test_a_scope_no_walk_can_enter_counts_as_met() -> None:
    prefix = replay(ONE_VENDOR_MODEL, [*_INVALID, Event(_K.CLOSED, 1)])
    for key, value in desiderata_values(prefix).items():
        if value is None:
            assert scope_chances(prefix)[key] == 0, key
            assert expected_outcomes(prefix)[key] == 1, key
    assert (
        desiderata_values(prefix)[VendorDesideratum(_VA_BEFORE_P, 1)] is None
    )


def test_closing_an_invalid_report_moves_its_scoped_outcome_to_one() -> None:
    prefix = replay(ONE_VENDOR_MODEL, _INVALID)
    key = VendorDesideratum(_VA_BEFORE_P, 1)
    before = expected_outcomes(prefix)[key]
    change = outcome_change(prefix, Event(_K.CLOSED, 1))
    assert change[key] == 1 - before
    assert set(change) == set(expected_outcomes(prefix))
    # The conditional change is undefined there: the scope is now unreachable.
    assert expected_change(prefix, Event(_K.CLOSED, 1))[key] is None
