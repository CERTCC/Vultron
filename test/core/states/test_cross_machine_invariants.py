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

"""Unit tests for `vultron.core.states.cross_machine_invariants`.

Covers violation_vf_d_entailment (#2893): d=D requires vf=VF (the *fD* compound
state is structurally impossible, per CSB-17-001), and the derivation of
RM_STATES_CONSISTENT_WITH_FIX from the RM transition graph (#3015).
"""

import pytest

from vultron.core.states.cs import CS_d, CS_vf
from vultron.core.states.rm import RM


class TestRmStatesConsistentWithFix:
    """The RM↔fix approximation is derived, not asserted (#3015).

    ``rm_em_cs.md`` states the rule as a *history* property: the F bit requires
    that the actor "passed through q^rm = Accepted at some point".  A
    ``ParticipantStatus`` carries only the current RM value, so the predicates
    approximate that history with a set of current values.  These tests pin the
    derivation, so nobody has to trust the comment.
    """

    @staticmethod
    def _reachable(start: RM, avoid: RM | None = None) -> set[RM]:
        """States reachable from *start*, optionally never entering *avoid*."""
        from vultron.core.states.rm import _transitions

        edges = [(t["source"], t["dest"]) for t in _transitions]
        seen = {start}
        stack = [start]
        while stack:
            src = stack.pop()
            for a, b in edges:
                if a == src and b not in seen and b != avoid:
                    seen.add(b)
                    stack.append(b)
        return seen

    @pytest.mark.spec("CSB-18-001")
    def test_consistent_with_fix_is_the_post_acceptance_reachable_set(self):
        """The set is exactly the states reachable from RM.ACCEPTED.

        That is what makes it *sound* for the history property: every state in
        it is one where "has passed through ACCEPTED" can be true, and every
        state outside it is one where it cannot. Deriving it from the transition
        graph means adding an RM transition cannot silently invalidate the
        approximation.
        """
        from vultron.core.states.cross_machine_invariants import (
            RM_STATES_CONSISTENT_WITH_FIX,
        )

        assert set(RM_STATES_CONSISTENT_WITH_FIX) == self._reachable(
            RM.ACCEPTED
        ), (
            "RM_STATES_CONSISTENT_WITH_FIX must be the post-ACCEPTED reachable"
            " set; a new RM transition out of ACCEPTED needs adding to it"
        )

    @pytest.mark.spec("CSB-18-001")
    def test_the_approximation_is_sound_but_not_complete(self):
        """DEFERRED and CLOSED are in the set yet do not *prove* acceptance.

        Both are also reachable without ever visiting ACCEPTED
        (``VALID → DEFERRED``, ``INVALID → CLOSED``), so a participant can hold
        one of them without having accepted the report. They are included
        anyway, deliberately: excluding them would refuse the legitimate batched
        update in which a peer advances through ACCEPTED and reports fix
        readiness in a single message, which the received path explicitly
        permits (CSB-16-001).

        This test exists so the incompleteness is a recorded decision rather than
        an oversight. Closing it needs the participant's RM *history*; no
        predicate over one snapshot can do it.
        """
        from vultron.core.states.cross_machine_invariants import (
            RM_STATES_CONSISTENT_WITH_FIX,
        )

        without_acceptance = self._reachable(RM.START, avoid=RM.ACCEPTED)
        ambiguous = set(RM_STATES_CONSISTENT_WITH_FIX) & without_acceptance

        assert ambiguous == {RM.DEFERRED, RM.CLOSED}, (
            "exactly DEFERRED and CLOSED are reachable both with and without"
            f" acceptance; got {ambiguous}"
        )
        assert (
            RM.ACCEPTED not in without_acceptance
        ), "ACCEPTED is the only member that proves the history property"

    @pytest.mark.spec("CSB-18-001")
    def test_states_off_the_acceptance_path_are_excluded(self):
        """No pre-acceptance state licenses the F bit."""
        from vultron.core.states.cross_machine_invariants import (
            RM_STATES_CONSISTENT_WITH_FIX,
        )

        for state in (RM.START, RM.RECEIVED, RM.INVALID, RM.VALID):
            assert state not in RM_STATES_CONSISTENT_WITH_FIX, (
                f"{state.name} precedes acceptance and must not license the"
                " F bit"
            )


class TestViolationVfDEntailment:
    """Unit tests for violation_vf_d_entailment() (#2893)."""

    def _check(self, vf, d):
        from vultron.core.states.cross_machine_invariants import (
            violation_vf_d_entailment,
        )

        return violation_vf_d_entailment(vf, d)

    # --- invalid combinations (D bit set, F bit not set) ---

    def test_vf_unaware_and_d_deployed_is_violation(self):
        """vf=vf (vendor unaware) + d=D (deployed) is structurally impossible."""
        result = self._check(CS_vf.vf, CS_d.D)
        assert result is not None
        assert "D" in result

    def test_vf_vendor_aware_not_ready_and_d_deployed_is_violation(self):
        """vf=Vf (aware, fix not ready) + d=D is structurally impossible."""
        result = self._check(CS_vf.Vf, CS_d.D)
        assert result is not None
        assert "D" in result

    # --- valid combinations ---

    def test_vf_fix_ready_and_d_deployed_is_valid(self):
        """vf=VF (fix ready) + d=D (deployed) is the valid deployment state."""
        assert self._check(CS_vf.VF, CS_d.D) is None

    def test_vf_fix_ready_and_d_not_deployed_is_valid(self):
        """vf=VF (fix ready) + d=d (not yet deployed) is valid."""
        assert self._check(CS_vf.VF, CS_d.d) is None

    def test_vf_aware_not_ready_and_d_not_deployed_is_valid(self):
        """vf=Vf (aware, not ready) + d=d (not deployed) is valid."""
        assert self._check(CS_vf.Vf, CS_d.d) is None

    def test_vf_unaware_and_d_not_deployed_is_valid(self):
        """vf=vf (unaware) + d=d (not deployed) is valid."""
        assert self._check(CS_vf.vf, CS_d.d) is None

    # --- None handling ---

    def test_none_vf_and_d_deployed_is_not_reported(self):
        """When vf=None, the VF↔D check cannot be applied (no VF information)."""
        assert self._check(None, CS_d.D) is None

    def test_vf_and_none_d_is_valid(self):
        """When d=None, no D-dimension constraint applies."""
        assert self._check(CS_vf.vf, None) is None

    def test_both_none_is_valid(self):
        """Both None — no constraint to check."""
        assert self._check(None, None) is None
