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

from test.measure.advice.methods import METHODS
from test.measure.advice.pathologies import (
    ALL_CASES,
    PATHOLOGIES,
    Pathology,
    truth,
)

FAILS: dict[tuple[str, str], frozenset[str]] = {}
"""The cases each (method, pathology) fails; a pair not listed fails none."""


@pytest.mark.parametrize("pathology", PATHOLOGIES, ids=lambda p: p.name)
def test_each_pathology_has_a_case_that_tests_it(pathology: Pathology):
    assert any(pathology.witness(c, truth(c)) for c in ALL_CASES)


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
