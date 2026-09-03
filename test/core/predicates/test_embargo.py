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

"""Tests for vultron.core.predicates.embargo."""

import pytest

from vultron.core.predicates.embargo import pxa_is_embargo_eligible
from vultron.core.states.cs import CS_pxa


class TestPxaIsEmbargoEligible:
    def test_pxa_baseline_is_eligible(self):
        """CS_pxa.pxa (all-lowercase) means no public info — eligible."""
        assert pxa_is_embargo_eligible(CS_pxa.pxa) is True

    def test_public_aware_is_not_eligible(self):
        """P bit set — public aware, embargo creation window closed."""
        assert pxa_is_embargo_eligible(CS_pxa.Pxa) is False

    def test_exploit_public_is_not_eligible(self):
        """X bit set — exploit published."""
        assert pxa_is_embargo_eligible(CS_pxa.pXa) is False

    def test_attacks_observed_is_not_eligible(self):
        """A bit set — attacks observed."""
        assert pxa_is_embargo_eligible(CS_pxa.pxA) is False

    def test_px_set_is_not_eligible(self):
        assert pxa_is_embargo_eligible(CS_pxa.PXa) is False

    def test_pa_set_is_not_eligible(self):
        assert pxa_is_embargo_eligible(CS_pxa.PxA) is False

    def test_xa_set_is_not_eligible(self):
        assert pxa_is_embargo_eligible(CS_pxa.pXA) is False

    def test_pxa_all_set_is_not_eligible(self):
        assert pxa_is_embargo_eligible(CS_pxa.PXA) is False

    @pytest.mark.parametrize("state", [s for s in CS_pxa if s != CS_pxa.pxa])
    def test_all_non_baseline_states_ineligible(self, state: CS_pxa):
        """Every state other than CS_pxa.pxa is embargo-ineligible."""
        assert pxa_is_embargo_eligible(state) is False

    def test_only_baseline_is_eligible(self):
        eligible = [s for s in CS_pxa if pxa_is_embargo_eligible(s)]
        assert eligible == [CS_pxa.pxa]
