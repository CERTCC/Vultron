"""
Unit tests for RM/vf/d/EM/pxa ratchet predicates and state-group tuples.

Spec coverage:
- LST-04-001: RM and vf/d ratchets and EM and pxa ratchets are modeled as
  state-group tuples and is_*() predicates, extending the existing helpers.
"""

import pytest

from vultron.core.states.cs import (
    CS_d,
    CS_pxa,
    CS_vf,
    D_FIX_DEPLOYED,
    PXA_ATTACKS_OBSERVED,
    PXA_EXPLOIT_PUBLIC,
    PXA_PUBLIC_AWARE,
    VF_FIX_READY,
    VF_VENDOR_AWARE,
    is_d_fix_deployed,
    is_pxa_attacks_observed,
    is_pxa_exploit_public,
    is_pxa_public_aware,
    is_vf_fix_ready,
    is_vf_vendor_aware,
)
from vultron.core.states.em import (
    EM,
    EM_EMBARGO_ACTIVE,
    is_em_embargo_active,
    is_em_exited,
)
from vultron.core.states.rm import RM, RM_VALIDATED, is_rm_validated

# ---------------------------------------------------------------------------
# RM ratchet
# ---------------------------------------------------------------------------


class TestRmValidated:
    def test_rm_validated_tuple_contents(self):
        assert isinstance(RM_VALIDATED, tuple)
        assert set(RM_VALIDATED) == {RM.VALID, RM.DEFERRED, RM.ACCEPTED}

    @pytest.mark.parametrize("state", [RM.VALID, RM.DEFERRED, RM.ACCEPTED])
    def test_is_rm_validated_true(self, state):
        assert is_rm_validated(state) is True

    @pytest.mark.parametrize(
        "state", [RM.START, RM.RECEIVED, RM.INVALID, RM.CLOSED]
    )
    def test_is_rm_validated_false(self, state):
        assert is_rm_validated(state) is False

    def test_closed_excluded(self):
        """CLOSED is reachable from INVALID without passing through VALID."""
        assert is_rm_validated(RM.CLOSED) is False

    def test_invalid_excluded(self):
        assert is_rm_validated(RM.INVALID) is False


# ---------------------------------------------------------------------------
# vf milestone groups and predicates
# ---------------------------------------------------------------------------


class TestVfVendorAware:
    def test_tuple_contents(self):
        assert isinstance(VF_VENDOR_AWARE, tuple)
        assert set(VF_VENDOR_AWARE) == {CS_vf.Vf, CS_vf.VF}

    @pytest.mark.parametrize("state", [CS_vf.Vf, CS_vf.VF])
    def test_true(self, state):
        assert is_vf_vendor_aware(state) is True

    def test_false_vf(self):
        assert is_vf_vendor_aware(CS_vf.vf) is False


class TestVfFixReady:
    def test_tuple_contents(self):
        assert isinstance(VF_FIX_READY, tuple)
        assert set(VF_FIX_READY) == {CS_vf.VF}

    def test_true(self):
        assert is_vf_fix_ready(CS_vf.VF) is True

    @pytest.mark.parametrize("state", [CS_vf.vf, CS_vf.Vf])
    def test_false(self, state):
        assert is_vf_fix_ready(state) is False


class TestDFixDeployed:
    def test_tuple_contents(self):
        assert isinstance(D_FIX_DEPLOYED, tuple)
        assert set(D_FIX_DEPLOYED) == {CS_d.D}

    def test_true(self):
        assert is_d_fix_deployed(CS_d.D) is True

    def test_false(self):
        assert is_d_fix_deployed(CS_d.d) is False


class TestVfMilestoneImplication:
    """Fix ready implies vendor aware (VF dimension)."""

    def test_ready_implies_vendor_aware(self):
        for s in VF_FIX_READY:
            assert is_vf_vendor_aware(s)


# ---------------------------------------------------------------------------
# EM active/negotiating
# ---------------------------------------------------------------------------


class TestEmEmbargoActive:
    def test_tuple_contents(self):
        assert isinstance(EM_EMBARGO_ACTIVE, tuple)
        assert set(EM_EMBARGO_ACTIVE) == {EM.ACTIVE, EM.REVISE}

    @pytest.mark.parametrize("state", [EM.ACTIVE, EM.REVISE])
    def test_true(self, state):
        assert is_em_embargo_active(state) is True

    @pytest.mark.parametrize("state", [EM.NONE, EM.PROPOSED, EM.EXITED])
    def test_false(self, state):
        assert is_em_embargo_active(state) is False

    def test_proposed_excluded(self):
        """PROPOSED means negotiation only; embargo not yet in force."""
        assert is_em_embargo_active(EM.PROPOSED) is False

    def test_exited_excluded(self):
        assert is_em_embargo_active(EM.EXITED) is False


class TestEmExited:
    def test_true_for_exited(self):
        assert is_em_exited(EM.EXITED) is True

    @pytest.mark.parametrize(
        "state", [EM.NONE, EM.PROPOSED, EM.ACTIVE, EM.REVISE]
    )
    def test_false_for_non_exited(self, state):
        assert is_em_exited(state) is False

    def test_exhaustive(self):
        """Exactly one EM state satisfies is_em_exited."""
        exited_states = [s for s in EM if is_em_exited(s)]
        assert exited_states == [EM.EXITED]


# ---------------------------------------------------------------------------
# pxa public-state groups and predicates
# ---------------------------------------------------------------------------


class TestPxaPublicAware:
    def test_tuple_contents(self):
        assert isinstance(PXA_PUBLIC_AWARE, tuple)
        assert set(PXA_PUBLIC_AWARE) == {
            CS_pxa.Pxa,
            CS_pxa.PxA,
            CS_pxa.PXa,
            CS_pxa.PXA,
        }

    @pytest.mark.parametrize(
        "state", [CS_pxa.Pxa, CS_pxa.PxA, CS_pxa.PXa, CS_pxa.PXA]
    )
    def test_true(self, state):
        assert is_pxa_public_aware(state) is True

    @pytest.mark.parametrize(
        "state", [CS_pxa.pxa, CS_pxa.pxA, CS_pxa.pXa, CS_pxa.pXA]
    )
    def test_false(self, state):
        assert is_pxa_public_aware(state) is False


class TestPxaExploitPublic:
    def test_tuple_contents(self):
        assert isinstance(PXA_EXPLOIT_PUBLIC, tuple)
        assert set(PXA_EXPLOIT_PUBLIC) == {
            CS_pxa.pXa,
            CS_pxa.pXA,
            CS_pxa.PXa,
            CS_pxa.PXA,
        }

    @pytest.mark.parametrize(
        "state", [CS_pxa.pXa, CS_pxa.pXA, CS_pxa.PXa, CS_pxa.PXA]
    )
    def test_true(self, state):
        assert is_pxa_exploit_public(state) is True

    @pytest.mark.parametrize(
        "state", [CS_pxa.pxa, CS_pxa.Pxa, CS_pxa.pxA, CS_pxa.PxA]
    )
    def test_false(self, state):
        assert is_pxa_exploit_public(state) is False


class TestPxaAttacksObserved:
    def test_tuple_contents(self):
        assert isinstance(PXA_ATTACKS_OBSERVED, tuple)
        assert set(PXA_ATTACKS_OBSERVED) == {
            CS_pxa.pxA,
            CS_pxa.PxA,
            CS_pxa.pXA,
            CS_pxa.PXA,
        }

    @pytest.mark.parametrize(
        "state", [CS_pxa.pxA, CS_pxa.PxA, CS_pxa.pXA, CS_pxa.PXA]
    )
    def test_true(self, state):
        assert is_pxa_attacks_observed(state) is True

    @pytest.mark.parametrize(
        "state", [CS_pxa.pxa, CS_pxa.Pxa, CS_pxa.pXa, CS_pxa.PXa]
    )
    def test_false(self, state):
        assert is_pxa_attacks_observed(state) is False


class TestPxaExhaustive:
    """Every CS_pxa state is correctly classified across all three predicates."""

    ALL = list(CS_pxa)

    def test_public_aware_coverage(self):
        positive = {s for s in self.ALL if is_pxa_public_aware(s)}
        assert positive == set(PXA_PUBLIC_AWARE)

    def test_exploit_public_coverage(self):
        positive = {s for s in self.ALL if is_pxa_exploit_public(s)}
        assert positive == set(PXA_EXPLOIT_PUBLIC)

    def test_attacks_observed_coverage(self):
        positive = {s for s in self.ALL if is_pxa_attacks_observed(s)}
        assert positive == set(PXA_ATTACKS_OBSERVED)
