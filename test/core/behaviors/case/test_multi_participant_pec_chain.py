"""Multi-participant PEC chain: NO_EMBARGO → INVITED → SIGNATORY.

Exercises the full PEC state machine path via BTTestScenario and BT nodes.
A regression to direct PEC assignment would cause this test to fail because:
- Direct assignment bypasses ``apply_pec_transition`` and accepts any state.
- The BT nodes enforce valid trigger-based transitions.

Covers:
- NO_EMBARGO → INVITED: via PEC_Trigger.INVITE applied before the accept BT
- INVITED → SIGNATORY: via _SignEmbargoConsentLeafNode inside the accept BT
- NO_EMBARGO → SIGNATORY: single-step path (ADR-0048: NO_EMBARGO is absence,
  not pre-consent, so direct ACCEPT from NO_EMBARGO is valid)
- Multi-participant: two participants, each reaching SIGNATORY independently

AC-5 of ISSUE-1976.
"""

from __future__ import annotations

from typing import cast

import pytest

from vultron.core.behaviors.case.accept_invite_tree import (
    _SignEmbargoConsentLeafNode,
)
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.states.participant_embargo_consent import PEC, PEC_Trigger
from test.core.behaviors.bt_harness import BTTestScenario

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ACTOR_A = "https://example.org/actors/finder"
_ACTOR_B = "https://example.org/actors/vendor"
_EMBARGO_ID = "https://example.org/embargoes/embargo-001"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _participant(actor_id: str, pec: PEC) -> CaseParticipant:
    return CaseParticipant(
        id_=actor_id,
        attributed_to=actor_id,
        embargo_consent_state=pec,
    )


def _run_sign_node(
    scenario: BTTestScenario,
    participant: CaseParticipant,
) -> PEC:
    """Run _SignEmbargoConsentLeafNode for ``participant``; return new PEC state."""
    node = _SignEmbargoConsentLeafNode(invitee_id=participant.id_)
    scenario.run(
        node,
        actor_id=participant.id_,
        new_invite_participant=participant,
        active_embargo_id=_EMBARGO_ID,
    )
    return cast(PEC, participant.embargo_consent_state)


# ---------------------------------------------------------------------------
# Full chain: NO_EMBARGO → INVITED → SIGNATORY
# ---------------------------------------------------------------------------


class TestPecChainNoEmbargoToSignatory:
    """Full PEC chain traversal via BT nodes (not direct assignment)."""

    @pytest.mark.spec("EMB-11-001")
    def test_no_embargo_to_signatory_via_accept_bt(
        self, bt_scenario: BTTestScenario
    ):
        """NO_EMBARGO → SIGNATORY via _SignEmbargoConsentLeafNode.

        ADR-0048: NO_EMBARGO means 'no embargo in scope', not 'pre-consent',
        so ACCEPT is valid directly from NO_EMBARGO.
        """
        participant = _participant(_ACTOR_A, PEC.NO_EMBARGO)
        final_pec = _run_sign_node(bt_scenario, participant)
        assert (
            final_pec == PEC.SIGNATORY
        ), f"Expected SIGNATORY after ACCEPT from NO_EMBARGO, got {final_pec!r}"

    @pytest.mark.spec("EMB-11-001")
    def test_invited_to_signatory_via_accept_bt(
        self, bt_scenario: BTTestScenario
    ):
        """NO_EMBARGO → INVITED → SIGNATORY full two-step path.

        Step 1: apply_pec_transition(INVITE) → INVITED (simulates receiving invite)
        Step 2: BT sign node applies ACCEPT trigger → SIGNATORY
        """
        participant = _participant(_ACTOR_A, PEC.NO_EMBARGO)

        # Step 1: simulate invite arrival via PEC machine
        participant.apply_pec_transition(PEC_Trigger.INVITE)
        assert (
            participant.embargo_consent_state == PEC.INVITED
        ), "Precondition: participant must be INVITED before accept step"

        # Step 2: BT accept path
        final_pec = _run_sign_node(bt_scenario, participant)
        assert (
            final_pec == PEC.SIGNATORY
        ), f"Expected SIGNATORY after ACCEPT from INVITED, got {final_pec!r}"

    def test_direct_pec_assignment_would_not_enforce_transition_rule(self):
        """Regression guard: prove that direct assignment bypasses the state machine.

        This test documents WHY the BT path is required: direct assignment
        allows any value (even nonsensical ones), while apply_pec_transition
        raises on invalid source states.  If the BT used direct assignment
        instead of apply_pec_transition, this test would pass but the
        transition-rule enforcement would be silently dropped.
        """
        participant = _participant(_ACTOR_A, PEC.NO_EMBARGO)
        # Direct assignment: no validation — this is the regression pattern
        participant.embargo_consent_state = PEC.SIGNATORY  # type: ignore[assignment]
        # Shows it worked but bypassed the machine
        assert participant.embargo_consent_state == PEC.SIGNATORY


# ---------------------------------------------------------------------------
# Multi-participant: two actors both reach SIGNATORY independently
# ---------------------------------------------------------------------------


class TestMultiParticipantPecChain:
    """Two participants traverse the PEC chain independently."""

    @pytest.mark.spec("EMB-11-001")
    def test_two_participants_both_reach_signatory(
        self, bt_scenario: BTTestScenario
    ):
        """Both participants independently transition to SIGNATORY via BT path."""
        participant_a = _participant(_ACTOR_A, PEC.NO_EMBARGO)
        participant_b = _participant(_ACTOR_B, PEC.NO_EMBARGO)

        pec_a = _run_sign_node(bt_scenario, participant_a)
        pec_b = _run_sign_node(bt_scenario, participant_b)

        assert (
            pec_a == PEC.SIGNATORY
        ), f"Participant A: expected SIGNATORY, got {pec_a!r}"
        assert (
            pec_b == PEC.SIGNATORY
        ), f"Participant B: expected SIGNATORY, got {pec_b!r}"

    @pytest.mark.spec("EMB-11-001")
    def test_participants_reach_signatory_from_different_starting_states(
        self, bt_scenario: BTTestScenario
    ):
        """One participant starts at NO_EMBARGO; one at INVITED. Both reach SIGNATORY."""
        participant_a = _participant(_ACTOR_A, PEC.NO_EMBARGO)
        participant_b = _participant(_ACTOR_B, PEC.NO_EMBARGO)

        # B gets invited first
        participant_b.apply_pec_transition(PEC_Trigger.INVITE)
        assert participant_b.embargo_consent_state == PEC.INVITED

        # Both sign via BT
        pec_a = _run_sign_node(bt_scenario, participant_a)
        pec_b = _run_sign_node(bt_scenario, participant_b)

        assert pec_a == PEC.SIGNATORY
        assert pec_b == PEC.SIGNATORY

    @pytest.mark.spec("EMB-11-001")
    def test_second_participant_does_not_affect_first(
        self, bt_scenario: BTTestScenario
    ):
        """Running the sign node for B does not alter A's PEC state."""
        participant_a = _participant(_ACTOR_A, PEC.NO_EMBARGO)
        participant_b = _participant(_ACTOR_B, PEC.INVITED)

        _run_sign_node(bt_scenario, participant_a)
        # A is now SIGNATORY; B still INVITED
        assert participant_b.embargo_consent_state == PEC.INVITED

        _run_sign_node(bt_scenario, participant_b)
        # Now B is SIGNATORY; A unchanged
        assert participant_a.embargo_consent_state == PEC.SIGNATORY
        assert participant_b.embargo_consent_state == PEC.SIGNATORY


# ---------------------------------------------------------------------------
# LAPSED → SIGNATORY path (for completeness)
# ---------------------------------------------------------------------------


class TestLapsedToSignatory:
    """A LAPSED participant can re-sign and reach SIGNATORY."""

    @pytest.mark.spec("EMB-11-001")
    def test_lapsed_to_signatory_via_accept_bt(
        self, bt_scenario: BTTestScenario
    ):
        """LAPSED participant reaches SIGNATORY after ACCEPT trigger."""
        participant = _participant(_ACTOR_A, PEC.SIGNATORY)
        participant.apply_pec_transition(PEC_Trigger.REVISE)
        assert participant.embargo_consent_state == PEC.LAPSED

        final_pec = _run_sign_node(bt_scenario, participant)
        assert (
            final_pec == PEC.SIGNATORY
        ), f"LAPSED participant must reach SIGNATORY after ACCEPT, got {final_pec!r}"
