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
state is structurally impossible, per CSB-17-001).
"""

from vultron.core.states.cs import CS_d, CS_vf


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
