"""
Unit tests for RM/vfd/EM/pxa ratchet predicates and state-group tuples.

Spec coverage:
- LST-04-001: RM and vfd ratchets and EM and pxa ratchets are modeled as
  state-group tuples and is_*() predicates, extending the existing helpers.
"""

import pytest

from vultron.core.states.cs import (
    CS_pxa,
    CS_vfd,
    PXA_ATTACKS_OBSERVED,
    PXA_EXPLOIT_PUBLIC,
    PXA_PUBLIC_AWARE,
    VFD_FIX_DEPLOYED,
    VFD_FIX_READY,
    VFD_VENDOR_AWARE,
    is_pxa_attacks_observed,
    is_pxa_exploit_public,
    is_pxa_public_aware,
    is_vfd_fix_deployed,
    is_vfd_fix_ready,
    is_vfd_vendor_aware,
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
# vfd milestone groups and predicates
# ---------------------------------------------------------------------------


class TestVfdVendorAware:
    def test_tuple_contents(self):
        assert isinstance(VFD_VENDOR_AWARE, tuple)
        assert set(VFD_VENDOR_AWARE) == {CS_vfd.Vfd, CS_vfd.VFd, CS_vfd.VFD}

    @pytest.mark.parametrize("state", [CS_vfd.Vfd, CS_vfd.VFd, CS_vfd.VFD])
    def test_true(self, state):
        assert is_vfd_vendor_aware(state) is True

    def test_false_vfd(self):
        assert is_vfd_vendor_aware(CS_vfd.vfd) is False


class TestVfdFixReady:
    def test_tuple_contents(self):
        assert isinstance(VFD_FIX_READY, tuple)
        assert set(VFD_FIX_READY) == {CS_vfd.VFd, CS_vfd.VFD}

    @pytest.mark.parametrize("state", [CS_vfd.VFd, CS_vfd.VFD])
    def test_true(self, state):
        assert is_vfd_fix_ready(state) is True

    @pytest.mark.parametrize("state", [CS_vfd.vfd, CS_vfd.Vfd])
    def test_false(self, state):
        assert is_vfd_fix_ready(state) is False


class TestVfdFixDeployed:
    def test_tuple_contents(self):
        assert isinstance(VFD_FIX_DEPLOYED, tuple)
        assert set(VFD_FIX_DEPLOYED) == {CS_vfd.VFD}

    def test_true(self):
        assert is_vfd_fix_deployed(CS_vfd.VFD) is True

    @pytest.mark.parametrize("state", [CS_vfd.vfd, CS_vfd.Vfd, CS_vfd.VFd])
    def test_false(self, state):
        assert is_vfd_fix_deployed(state) is False


class TestVfdMilestoneImplication:
    """Fix deployed implies fix ready implies vendor aware."""

    def test_deployed_implies_ready(self):
        for s in VFD_FIX_DEPLOYED:
            assert is_vfd_fix_ready(s)

    def test_ready_implies_vendor_aware(self):
        for s in VFD_FIX_READY:
            assert is_vfd_vendor_aware(s)


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
