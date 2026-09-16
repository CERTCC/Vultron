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

"""Unit tests for resolve_pxa_threat_state (threat_termination.py)."""

from vultron.core.behaviors.status.nodes.threat_termination import (
    resolve_pxa_threat_state,
)
from vultron.core.states.cs import CS_pxa


class _PxaState:
    """Minimal PXA state object with a .state attribute."""

    def __init__(self, state: CS_pxa):
        self.state = state


class _CaseStatusWithPxa:
    def __init__(self, pxa_val):
        self.pxa = pxa_val


class TestResolvePxaThreatState:
    """Unit tests for resolve_pxa_threat_state()."""

    def test_returns_none_when_case_status_is_none(self):
        """Returns None when case_status is None."""
        assert resolve_pxa_threat_state(None) is None

    def test_returns_none_when_no_pxa_attribute(self):
        """Returns None when case_status has no pxa or pxa_state attribute."""

        class _NoPxa:
            pass

        assert resolve_pxa_threat_state(_NoPxa()) is None

    def test_returns_none_when_pxa_state_is_pxa_lowercase(self):
        """Returns None when pxa state is CS_pxa.pxa (no P, X, or A set)."""
        cs = _CaseStatusWithPxa(_PxaState(CS_pxa.pxa))
        assert resolve_pxa_threat_state(cs) is None

    def test_returns_state_when_pxa_state_is_threat(self):
        """Returns the CS_pxa state when at least one of P, X, A is set."""
        cs = _CaseStatusWithPxa(_PxaState(CS_pxa.Pxa))
        result = resolve_pxa_threat_state(cs)
        assert result == CS_pxa.Pxa

    def test_returns_none_when_pxa_attr_is_none(self):
        """Returns None (no AttributeError) when case_status.pxa is None (issue #2877).

        A CaseStatus whose pxa attribute is set to None represents a participant
        that has not yet provided PXA information.  The function must treat this
        as 'no threat' and return None rather than raising AttributeError.
        """
        cs = _CaseStatusWithPxa(None)
        result = resolve_pxa_threat_state(cs)
        assert result is None
