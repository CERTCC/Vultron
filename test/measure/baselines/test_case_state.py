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

"""The six-event walk reproduces the published baselines (#6067 AC-3).

It also gives the per-history and from-a-prefix probabilities that scoring an
incomplete sequence weights completions by (ADR-0182, on scoring an
incomplete sequence through its completions).
"""

from fractions import Fraction

import pytest

from vultron.core.states.cs_invariants import CSEvent, valid_cs_histories
from vultron.errors import (
    VultronInvalidStateTransitionError,
    VultronValidationError,
)
from vultron.measure.baselines import (
    CASE_STATE_MODEL,
    ORIGINAL,
    baseline,
    completion_probabilities,
    frequency,
    history_probability,
    ordering,
    prefix_probability,
    step_probability,
)
from vultron.measure.baselines.case_state import START

# docs/includes/tab_exp_freq.md, upper right: the published f_d to 3 places.
PUBLISHED = {
    "DP": 0.037,
    "FP": 0.111,
    "DX": 0.167,
    "DA": 0.187,
    "FX": 0.333,
    "VP": 0.333,
    "FA": 0.375,
    "PX": 0.500,
    "XA": 0.500,
    "PA": 0.667,
    "VX": 0.667,
    "VA": 0.750,
}

EXACT = {
    "DP": Fraction(1, 27),
    "FP": Fraction(1, 9),
    "DX": Fraction(1, 6),
    "DA": Fraction(3, 16),
    "FX": Fraction(1, 3),
    "VP": Fraction(1, 3),
    "FA": Fraction(3, 8),
    "PX": Fraction(1, 2),
    "XA": Fraction(1, 2),
    "PA": Fraction(2, 3),
    "VX": Fraction(2, 3),
    "VA": Fraction(3, 4),
}


def _key(desideratum) -> str:
    (o,) = desideratum.query.orderings
    return f"{o.before.kind.value}{o.after.kind.value}"


def test_the_catalog_holds_the_twelve_published_desiderata():
    assert [_key(d) for d in ORIGINAL] == list(PUBLISHED)


@pytest.mark.parametrize("desideratum", ORIGINAL, ids=_key)
def test_the_walk_reproduces_each_published_baseline(desideratum):
    exact = baseline(desideratum)
    assert exact == EXACT[_key(desideratum)]
    # The published table rounds (0.1875 is printed 0.187), so it is matched
    # to within half a unit of its last place.
    assert abs(float(exact) - PUBLISHED[_key(desideratum)]) <= 0.0005 + 1e-12


def test_the_walk_has_exactly_the_seventy_valid_histories():
    completions = completion_probabilities()
    assert set(completions) == set(valid_cs_histories())
    assert sum(completions.values()) == 1


def test_a_history_probability_is_the_product_of_its_steps():
    # random_walk.md's table: vfdpxa, Vfdpxa and VFdpxa each allow four
    # events, VFDpxa three, VFDPxa two and VFDPXa one.
    assert history_probability("VFDPXA") == Fraction(1, 4 * 4 * 4 * 3 * 2)


def test_completion_probabilities_are_conditional_on_the_prefix():
    prefix = (CSEvent.V, CSEvent.P)
    completions = completion_probabilities(prefix)
    assert sum(completions.values()) == 1
    for history, probability in completions.items():
        assert history[:2] == prefix
        assert probability == history_probability(
            history
        ) / prefix_probability(prefix)


def test_an_ephemeral_prefix_has_one_forced_next_event():
    # X forces P next, and P with the vendor unaware forces V next.
    completions = completion_probabilities("X")
    assert completions
    assert all(h[:3] == ("X", "P", "V") for h in completions)


def test_a_complete_prefix_is_its_own_only_completion():
    assert completion_probabilities("VFDPXA") == {
        tuple(CSEvent(e) for e in "VFDPXA"): Fraction(1)
    }


def test_the_frequency_equals_the_sum_over_histories():
    by_histories = sum(
        p
        for h, p in completion_probabilities().items()
        if h.index(CSEvent.F) < h.index(CSEvent.P)
    )
    assert by_histories == frequency(
        CASE_STATE_MODEL, ordering(CSEvent.F, CSEvent.P)
    )


@pytest.mark.parametrize("bad", ["F", "VV", "XA", "Q"])
def test_an_invalid_prefix_is_refused(bad):
    with pytest.raises(
        (VultronValidationError, VultronInvalidStateTransitionError)
    ):
        completion_probabilities(bad)


def test_an_incomplete_history_has_no_history_probability():
    with pytest.raises(
        (VultronValidationError, VultronInvalidStateTransitionError)
    ):
        history_probability("VF")


def test_a_step_probability_is_one_over_the_events_allowed():
    assert step_probability(START, "V") == Fraction(1, 4)


def test_a_step_the_state_does_not_allow_has_no_probability():
    with pytest.raises(VultronInvalidStateTransitionError):
        step_probability(START, "F")
