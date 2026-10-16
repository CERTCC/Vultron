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

from test.support.embargo_register import activate, propose
from vultron.core.models.case import VulnerabilityCase
from vultron.core.predicates.embargo import (
    pxa_is_embargo_eligible,
    rejection_ends_embargo,
)
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


_CASE = "https://example.org/cases/c1"
_ACTIVE = f"{_CASE}/embargo_events/active"
_REVISION = f"{_CASE}/embargo_events/revision"
_OTHER = f"{_CASE}/embargo_events/other"


def _case(
    *, active: bool = True, others: bool = False, pxa: CS_pxa = CS_pxa.Pxa
) -> VulnerabilityCase:
    case = VulnerabilityCase(
        id_=_CASE, attributed_to="https://example.org/users/owner"
    )
    case.append_case_status(pxa=pxa)
    if active:
        activate(case, _ACTIVE)
    propose(case, _REVISION)
    if others:
        propose(case, _OTHER)
    return case


@pytest.mark.spec("EMB-04-002")
class TestRejectionEndsEmbargo:
    def test_the_last_revision_after_disclosure_ends_the_embargo(self):
        assert rejection_ends_embargo(_case(), _REVISION) is True

    def test_no_public_info_returns_to_the_prior_terms(self):
        assert (
            rejection_ends_embargo(_case(pxa=CS_pxa.pxa), _REVISION) is False
        )

    def test_another_open_revision_keeps_the_negotiation_open(self):
        """EP-08-001: only the last open revision decides the revision."""
        assert rejection_ends_embargo(_case(others=True), _REVISION) is False

    def test_an_initial_proposal_has_no_prior_terms(self):
        assert rejection_ends_embargo(_case(active=False), _REVISION) is False

    def test_an_embargo_that_is_not_open_is_not_a_revision(self):
        assert rejection_ends_embargo(_case(), _ACTIVE) is False
