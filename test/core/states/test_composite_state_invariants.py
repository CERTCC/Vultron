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

"""Unit tests for `vultron.core.states.composite_state_invariants`.

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
        from vultron.core.states.composite_state_invariants import (
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
        from vultron.core.states.composite_state_invariants import (
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
        from vultron.core.states.composite_state_invariants import (
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
        from vultron.core.states.composite_state_invariants import (
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


class TestAdr0089EntailmentEnumeration:
    """ADR-0089 blast-radius claim: zero violations on legal data (AC-10, #3204).

    ADR-0089 converts five call sites that previously bypassed the shared
    evaluator.  The claim is that adding the full entailment check to those
    sites produces *no new violations* for legal state data — i.e. the
    entailments only fire for state combinations that were already corrupt.

    This class enumerates composite_state_violations() to pin that claim so it
    cannot silently stop being true as the state machine evolves.
    """

    @staticmethod
    def _violations(rm, vf, d):
        from vultron.core.states.composite_state_invariants import (
            composite_state_violations,
        )

        return composite_state_violations(rm, vf, d)

    # Sites 1–3: ACCEPTED, DEFERRED, CLOSED writers.
    # RM ∈ RM_STATES_CONSISTENT_WITH_FIX ⟹ RM-coupled rules never fire.
    @pytest.mark.parametrize("rm", [RM.ACCEPTED, RM.DEFERRED, RM.CLOSED])
    @pytest.mark.parametrize(
        "vf,d",
        [
            (None, None),
            (CS_vf.vf, None),
            (CS_vf.Vf, None),
            (CS_vf.VF, None),
            (CS_vf.VF, CS_d.D),
            (None, CS_d.d),
            (None, CS_d.D),
        ],
    )
    def test_safe_rm_states_produce_no_rm_coupled_violations(
        self, rm, vf, d
    ) -> None:
        """RM ∈ {ACCEPTED, DEFERRED, CLOSED}: RM-coupled entailments are silent.

        CSB-18-001 fires only when rm ∉ RM_STATES_CONSISTENT_WITH_FIX.  The
        three converted sites that write these RM values are therefore zero-cost
        from RM-coupled rules, regardless of the participant's vf/d state.
        """
        from vultron.core.states.composite_state_invariants import (
            RM_STATES_CONSISTENT_WITH_FIX,
        )

        assert rm in RM_STATES_CONSISTENT_WITH_FIX
        # RM-coupled violations have dimension "vf" or "d" and reference the
        # safe set in their message.  Rather than pattern-match message text
        # (brittle), we compare the full list against what the vf↔d check alone
        # could produce — if the count agrees, no RM-coupled rule fired.
        from vultron.core.states.composite_state_invariants import (
            violation_vf_d_entailment,
        )

        vf_d_only = (
            [violation_vf_d_entailment(vf, d)]
            if violation_vf_d_entailment(vf, d) is not None
            else []
        )
        assert (
            self._violations(rm, vf, d) == vf_d_only
        ), f"Unexpected RM-coupled violation for ({rm!r}, {vf!r}, {d!r})"

    # Site 4–5: vf=Vf / vf=VF writers (develop_fix.py).
    # They assert vf only; rm_state=None so current RM is used.
    # At fix-development time the actor's RM must be in the safe set.
    # Entailment check for (safe_rm, Vf/VF, None) must be zero.
    @pytest.mark.parametrize("rm", [RM.ACCEPTED, RM.DEFERRED, RM.CLOSED])
    @pytest.mark.parametrize("vf", [CS_vf.Vf, CS_vf.VF])
    def test_fix_development_sites_have_zero_violations(self, rm, vf) -> None:
        """develop_fix.py writes vf=Vf or vf=VF with d=None and safe RM."""
        assert (
            self._violations(rm, vf, None) == []
        ), f"Expected zero violations for develop_fix site ({rm!r}, {vf!r}, None)"

    # Site 6: d=D writer (deploy_fix.py).
    # At deployment time the fix is ready, so vf=VF.
    # Entailment check for (safe_rm, VF, D) must be zero.
    @pytest.mark.parametrize("rm", [RM.ACCEPTED, RM.DEFERRED, RM.CLOSED])
    def test_fix_deployment_site_has_zero_violations(self, rm) -> None:
        """deploy_fix.py writes d=D with vf=VF (fix ready) and safe RM."""
        assert (
            self._violations(rm, CS_vf.VF, CS_d.D) == []
        ), f"Expected zero violations for deploy_fix site ({rm!r}, VF, D)"

    # Confirm the rules DO fire for corrupt state, so the pass above is not
    # vacuous.
    @pytest.mark.parametrize(
        "rm", [RM.START, RM.RECEIVED, RM.VALID, RM.INVALID]
    )
    def test_rm_vf_entailment_fires_for_early_rm_with_fix_ready(
        self, rm
    ) -> None:
        """RM ∉ safe set + vf=VF: RM↔VF entailment fires (CSB-18-001).

        VF_FIX_READY = (CS_vf.VF,): only fix-ready triggers the rule.
        vf=Vf (vendor-aware, not ready) does not — it is reachable before
        ACCEPTED. These are corrupt states — fix-ready is unreachable without
        passing through ACCEPTED. The rule correctly refuses them.
        """
        violations = self._violations(rm, CS_vf.VF, None)
        assert any(
            v.dimension == "vf" for v in violations
        ), f"Expected RM↔VF violation for ({rm!r}, VF, None); got {violations}"

    @pytest.mark.parametrize(
        "rm", [RM.START, RM.RECEIVED, RM.VALID, RM.INVALID]
    )
    def test_rm_d_entailment_fires_for_early_rm_with_deployed(
        self, rm
    ) -> None:
        """RM ∉ safe set + d=D: RM↔D entailment fires (CSB-18-001).

        Deployed without having accepted is a corrupt state. The rule
        correctly refuses it.
        """
        violations = self._violations(rm, CS_vf.VF, CS_d.D)
        assert any(
            v.dimension == "d" for v in violations
        ), f"Expected RM↔D violation for ({rm!r}, VF, D); got {violations}"

    @pytest.mark.parametrize("vf", [CS_vf.vf, CS_vf.Vf])
    def test_vf_d_entailment_fires_for_deployed_without_fix_ready(
        self, vf
    ) -> None:
        """(vf ∉ {VF}, d=D) is a VF↔D violation regardless of RM (CSB-17-001).

        Deployed without fix-ready is structurally impossible. The rule is
        RM-independent: it fires at every RM state.
        """
        for rm in RM:
            violations = self._violations(rm, vf, CS_d.D)
            assert any(
                v.dimension == "d" for v in violations
            ), f"Expected VF↔D violation for ({rm!r}, {vf!r}, D); got {violations}"
