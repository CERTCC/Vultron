#!/usr/bin/env python

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

"""The received-side RM acceptance rule and the evaluator's DECLARATION rule.

``classify_rm_declaration`` is the rule both received paths share
(RSH-06-006); ``participant_transition_violations(rm_rule=DECLARATION)`` is
how a write node applies it at its own boundary (BTND-10-003).
"""

import pytest

from test.support.rm_declaration import RMDeclarationCase, all_cases
from vultron.core.states.cs import CS_pxa
from vultron.core.states.participant_transitions import (
    participant_transition_violations,
)
from vultron.core.states.rm import RM, RMRule, classify_rm_declaration


@pytest.mark.spec("RSH-06-001")
@pytest.mark.spec("RSH-06-002")
@pytest.mark.parametrize("case", all_cases())
def test_classification_matches_the_shared_table(case: RMDeclarationCase):
    assert classify_rm_declaration(case.current, case.declared) is case.verdict


@pytest.mark.spec("RSH-06-006")
@pytest.mark.spec("BTND-10-003")
@pytest.mark.parametrize("case", all_cases())
def test_declaration_rule_refuses_exactly_the_regressions(
    case: RMDeclarationCase,
):
    violations = participant_transition_violations(
        current_rm=case.current,
        current_vf=None,
        current_d=None,
        current_pxa=CS_pxa.pxa,
        requested_rm=case.declared,
        rm_rule=RMRule.DECLARATION,
    )
    rm_violations = [v for v in violations if "rm" in v.dimensions]
    assert bool(rm_violations) is (not case.accepted)


@pytest.mark.spec("CSB-16-001")
def test_transition_rule_still_refuses_a_gap():
    """The default rule is unchanged: a local write must be adjacent."""
    violations = participant_transition_violations(
        current_rm=RM.VALID,
        current_vf=None,
        current_d=None,
        current_pxa=CS_pxa.pxa,
        requested_rm=RM.CLOSED,
    )
    assert any("rm" in v.dimensions for v in violations)
