"""Multi-participant consent chain: UNINVITED -> INVITED -> AGREED.

Exercises the consent-row path via BTTestScenario and BT nodes (ADR-0122).
A regression to direct row assignment would cause this test to fail because:
- Direct assignment bypasses ``apply_pec_transition`` and accepts any state.
- The BT nodes enforce valid trigger-based transitions.

Covers:
- UNINVITED -> INVITED: via PEC_Trigger.INVITE applied before the accept BT
- INVITED -> AGREED: via _SignEmbargoConsentLeafNode inside the accept BT
- UNINVITED -> AGREED: single-step path (a participant never asked about the
  embargo may still accept it)
- Multi-participant: two participants, each becoming a signatory independently
- A participant that accepted an earlier embargo has lapsed from the embargo
  in force (derived) and is a signatory again once it signs it

AC-5 of ISSUE-1976.
"""

from __future__ import annotations

import pytest

from test.core.behaviors.bt_harness import BTTestScenario
from vultron.core.behaviors.case.nodes.invite_embargo_consent import (
    _SignEmbargoConsentLeafNode,
)
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.embargo_register import EmbargoRegisterEntry
from vultron.core.states.embargo_register import EmbargoRegisterStatus
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
    PEC_Trigger,
)
from vultron.errors import VultronInvalidStateTransitionError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ACTOR_A = "https://example.org/actors/finder"
_ACTOR_B = "https://example.org/actors/vendor"
_EMBARGO_ID = "https://example.org/embargoes/embargo-001"
_EARLIER_EMBARGO_ID = "https://example.org/embargoes/embargo-000"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _participant(
    actor_id: str,
    state: EmbargoConsentState = EmbargoConsentState.UNINVITED,
    *,
    embargo_id: str = _EMBARGO_ID,
) -> CaseParticipant:
    """A participant with a *state* row for *embargo_id*.

    Every other embargo of the case (the active one, the earlier one) gets
    the ``UNINVITED`` row each register entry writes (ADR-0122).
    """
    participant = CaseParticipant(
        id_=actor_id,
        attributed_to=actor_id,
        embargo_consents=[EmbargoConsent(embargo_id=embargo_id, state=state)],
    )
    participant.write_uninvited_rows([_EARLIER_EMBARGO_ID, _EMBARGO_ID])
    return participant


#: ``_EMBARGO_ID`` is the embargo in force; it replaced ``_EARLIER_EMBARGO_ID``.
_REGISTER = [
    EmbargoRegisterEntry(
        embargo=_EARLIER_EMBARGO_ID, status=EmbargoRegisterStatus.SUPERSEDED
    ),
    EmbargoRegisterEntry(
        embargo=_EMBARGO_ID,
        status=EmbargoRegisterStatus.ACTIVE,
        replaces=_EARLIER_EMBARGO_ID,
    ),
]


def _run_sign_node(
    scenario: BTTestScenario,
    participant: CaseParticipant,
) -> EmbargoConsentState | None:
    """Run _SignEmbargoConsentLeafNode for ``participant``; return its row."""
    node = _SignEmbargoConsentLeafNode(invitee_id=participant.id_)
    scenario.run(
        node,
        actor_id=participant.id_,
        new_invite_participant=participant,
        active_embargo_id=_EMBARGO_ID,
    )
    return participant.consent_for(_EMBARGO_ID)


# ---------------------------------------------------------------------------
# Full chain: UNINVITED -> INVITED -> AGREED
# ---------------------------------------------------------------------------


class TestConsentChainNoRowToSignatory:
    """Full consent-row traversal via BT nodes (not direct assignment)."""

    @pytest.mark.spec("EMB-11-001")
    def test_no_row_to_signatory_via_accept_bt(
        self, bt_scenario: BTTestScenario
    ):
        """UNINVITED -> AGREED via _SignEmbargoConsentLeafNode.

        ADR-0048: ``UNINVITED`` means 'never asked', not 'pre-consent', so
        AGREE is valid directly from it.
        """
        participant = _participant(_ACTOR_A)
        final = _run_sign_node(bt_scenario, participant)
        assert final == EmbargoConsentState.AGREED, (
            f"Expected AGREED after AGREE from UNINVITED, got {final!r}"
        )
        assert participant.is_signatory(_EMBARGO_ID)

    @pytest.mark.spec("EMB-11-001")
    def test_invited_to_signatory_via_accept_bt(
        self, bt_scenario: BTTestScenario
    ):
        """UNINVITED -> INVITED -> AGREED full two-step path.

        Step 1: apply_pec_transition(INVITE) -> INVITED (simulates receiving invite)
        Step 2: BT sign node applies AGREE trigger -> AGREED
        """
        participant = _participant(_ACTOR_A)

        # Step 1: simulate invite arrival via the consent table
        participant.apply_pec_transition(
            _EMBARGO_ID,
            PEC_Trigger.INVITE,
            entry_status=EmbargoRegisterStatus.ACTIVE,
        )
        assert (
            participant.consent_for(_EMBARGO_ID) == EmbargoConsentState.INVITED
        ), "Precondition: participant must be INVITED before accept step"
        assert not participant.is_signatory(_EMBARGO_ID)

        # Step 2: BT accept path
        final = _run_sign_node(bt_scenario, participant)
        assert final == EmbargoConsentState.AGREED, (
            f"Expected AGREED after AGREE from INVITED, got {final!r}"
        )
        assert participant.is_signatory(_EMBARGO_ID)

    def test_illegal_trigger_is_refused_by_the_consent_table(self):
        """Regression guard: the row is only written through the table.

        ``apply_pec_transition`` raises on a trigger that is not legal from
        the current row (an AGREED row is never re-INVITED), where a direct
        write would record it silently.  If the BT bypassed the table, this
        transition-rule enforcement would be silently dropped.
        """
        participant = _participant(_ACTOR_A, EmbargoConsentState.AGREED)
        with pytest.raises(VultronInvalidStateTransitionError):
            participant.apply_pec_transition(
                _EMBARGO_ID,
                PEC_Trigger.INVITE,
                entry_status=EmbargoRegisterStatus.ACTIVE,
            )
        assert (
            participant.consent_for(_EMBARGO_ID) == EmbargoConsentState.AGREED
        )

    @pytest.mark.spec("EMB-11-001")
    def test_declined_participant_is_not_signed_by_the_bt(
        self, bt_scenario: BTTestScenario
    ):
        """A participant that declined the embargo stays DECLINED."""
        participant = _participant(_ACTOR_A, EmbargoConsentState.DECLINED)
        final = _run_sign_node(bt_scenario, participant)
        assert final == EmbargoConsentState.DECLINED
        assert not participant.is_signatory(_EMBARGO_ID)


# ---------------------------------------------------------------------------
# Multi-participant: two actors both reach AGREED independently
# ---------------------------------------------------------------------------


class TestMultiParticipantConsentChain:
    """Two participants traverse the consent chain independently."""

    @pytest.mark.spec("EMB-11-001")
    def test_two_participants_both_reach_signatory(
        self, bt_scenario: BTTestScenario
    ):
        """Both participants independently become signatories via BT path."""
        participant_a = _participant(_ACTOR_A)
        participant_b = _participant(_ACTOR_B)

        state_a = _run_sign_node(bt_scenario, participant_a)
        state_b = _run_sign_node(bt_scenario, participant_b)

        assert state_a == EmbargoConsentState.AGREED, (
            f"Participant A: expected AGREED, got {state_a!r}"
        )
        assert state_b == EmbargoConsentState.AGREED, (
            f"Participant B: expected AGREED, got {state_b!r}"
        )

    @pytest.mark.spec("EMB-11-001")
    def test_participants_reach_signatory_from_different_starting_states(
        self, bt_scenario: BTTestScenario
    ):
        """One participant starts UNINVITED; one at INVITED. Both sign."""
        participant_a = _participant(_ACTOR_A)
        participant_b = _participant(_ACTOR_B)

        # B gets invited first
        participant_b.apply_pec_transition(
            _EMBARGO_ID,
            PEC_Trigger.INVITE,
            entry_status=EmbargoRegisterStatus.ACTIVE,
        )
        assert (
            participant_b.consent_for(_EMBARGO_ID)
            == EmbargoConsentState.INVITED
        )

        # Both sign via BT
        state_a = _run_sign_node(bt_scenario, participant_a)
        state_b = _run_sign_node(bt_scenario, participant_b)

        assert state_a == EmbargoConsentState.AGREED
        assert state_b == EmbargoConsentState.AGREED

    @pytest.mark.spec("EMB-11-001")
    def test_second_participant_does_not_affect_first(
        self, bt_scenario: BTTestScenario
    ):
        """Running the sign node for B does not alter A's consent row."""
        participant_a = _participant(_ACTOR_A)
        participant_b = _participant(_ACTOR_B, EmbargoConsentState.INVITED)

        _run_sign_node(bt_scenario, participant_a)
        # A is now a signatory; B still INVITED
        assert (
            participant_b.consent_for(_EMBARGO_ID)
            == EmbargoConsentState.INVITED
        )

        _run_sign_node(bt_scenario, participant_b)
        # Now B is a signatory; A unchanged
        assert participant_a.is_signatory(_EMBARGO_ID)
        assert participant_b.is_signatory(_EMBARGO_ID)


# ---------------------------------------------------------------------------
# Lapsed -> signatory path (lapse is derived, not stored)
# ---------------------------------------------------------------------------


class TestLapsedToSignatory:
    """A participant that lapsed from an earlier embargo can sign the new one."""

    @pytest.mark.spec("EMB-11-001")
    def test_lapsed_to_signatory_via_accept_bt(
        self, bt_scenario: BTTestScenario
    ):
        """A lapsed participant is a signatory after the sign node runs."""
        participant = _participant(
            _ACTOR_A,
            EmbargoConsentState.AGREED,
            embargo_id=_EARLIER_EMBARGO_ID,
        )
        assert participant.has_lapsed(_REGISTER)
        assert not participant.is_signatory(_EMBARGO_ID)

        final = _run_sign_node(bt_scenario, participant)
        assert final == EmbargoConsentState.AGREED, (
            f"A lapsed participant must reach AGREED, got {final!r}"
        )
        assert participant.is_signatory(_EMBARGO_ID)
        assert not participant.has_lapsed(_REGISTER)
        # Its row for the earlier embargo is kept, not overwritten.
        assert (
            participant.consent_for(_EARLIER_EMBARGO_ID)
            == EmbargoConsentState.AGREED
        )
