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

"""Each advice method against each pathology case (#6450, ADR-0200).

The pathologies (:mod:`test.measure.advice.pathologies`) were written before
any method was scored.  :data:`FAILS` records, for each method and
pathology, the cases the method fails; the test asserts the recorded set
exactly, so a change in a method or in the chance model shows here.  The
research page ``docs/topics/measuring_cvd/move_bands.md`` reads the same
table.
"""

import pytest

from test.measure.advice.cases import NO_HARM_FREE
from test.measure.advice.methods import METHODS
from test.measure.advice.pathologies import (
    ALL_CASES,
    PATHOLOGIES,
    Pathology,
    truth,
)
from vultron.measure.advice import Band

_EVERY = frozenset(c.name for c in ALL_CASES)
_EMBARGO = frozenset(c.name for c in ALL_CASES if c.embargo)
_THREE = "ready-unready embargo, three coordinator moves"
_WITH_UNAWARE = frozenset(
    {
        "ready-unready-unaware embargo",
        "ready-unready-unaware no-embargo",
        "deployed-ready-unready-unaware embargo",
        "deployed-ready-unready-unaware no-embargo",
    }
)
_UNAWARE_NO_EMBARGO = frozenset(
    {
        "ready-unready-unaware no-embargo",
        "deployed-ready-unready-unaware no-embargo",
    }
)
_MEAN_LIKE = {
    # A notified vendor starts below the others' mean, so notifying it
    # lowers the mean of the notified vendors' scores.
    "P1": _WITH_UNAWARE,
    # One number names no vendor.
    "P3": _EVERY,
    "P5": _EMBARGO,
    # Notifying a vendor dominates the embargo proposal but scores lower.
    "P4": _UNAWARE_NO_EMBARGO,
    # The embargo revision changes nothing, so it is unhelpful, and it
    # still outscores every other coordinator move.
    "P6": frozenset({"unready-unready embargo", _THREE}),
    # Notifying a vendor scores below ending the embargo, even early.
    "P7": _WITH_UNAWARE,
}

FAILS: dict[tuple[str, str], frozenset[str]] = {
    # The chance model gives an embargo revision no effect (#6492).
    ("bands", "P2"): frozenset({"unready-unready embargo"}),
    **{
        (method, pathology): cases
        for method in ("mean", "median", "mean then spread")
        for pathology, cases in _MEAN_LIKE.items()
    },
    ("maximin", "P1"): _WITH_UNAWARE,
    ("maximin", "P3"): _EVERY,
    ("maximin", "P5"): _EMBARGO,
    # A fix or a notice for one vendor leaves the lowest vendor where it
    # was, so it does not beat an embargo move that raises them all.
    ("maximin", "P4"): frozenset(
        {
            "ready-unready no-embargo",
            "unready-unready no-embargo",
            *_UNAWARE_NO_EMBARGO,
        }
    ),
    ("maximin", "P6"): frozenset(
        {
            "ready-unready embargo",
            "unready-unready embargo",
            "ready-unready-unaware embargo",
            "deployed-ready-unready-unaware embargo",
            _THREE,
        }
    ),
    ("maximin", "P7"): frozenset(
        {
            "ready-unready no-embargo",
            "unready-unready no-embargo",
            *_WITH_UNAWARE,
        }
    ),
    ("Nash product", "P3"): _EVERY,
    ("Nash product", "P5"): _EMBARGO,
    ("Nash product", "P6"): frozenset({"unready-unready embargo", _THREE}),
    ("Nash product", "P7"): frozenset(
        {"deployed-ready-unready-unaware embargo"}
    ),
}
"""The cases each (method, pathology) fails; a pair not listed fails none."""


@pytest.mark.parametrize("pathology", PATHOLOGIES, ids=lambda p: p.name)
def test_each_pathology_has_a_case_that_tests_it(pathology: Pathology):
    assert any(pathology.witness(c, truth(c)) for c in ALL_CASES)


def test_a_case_has_an_empty_harm_free_band():
    """P6's second half: the harm-free band can be empty."""
    facts = truth(NO_HARM_FREE)
    assert NO_HARM_FREE.moves
    assert all(facts.band(m) is not Band.HARM_FREE for m in NO_HARM_FREE.moves)


@pytest.mark.parametrize("pathology", PATHOLOGIES, ids=lambda p: p.name)
@pytest.mark.parametrize("method", sorted(METHODS))
def test_each_method_fails_only_its_recorded_cases(
    method: str, pathology: Pathology
):
    advise = METHODS[method]
    failed = {
        case.name: lines
        for case in ALL_CASES
        if (lines := pathology.check(case, advise(case), truth(case)))
    }
    assert set(failed) == FAILS.get((method, pathology.name), set()), failed
