"""Tests for the Participant Embargo Consent (PEC) state machine."""

import pytest

from vultron.core.states.participant_embargo_consent import (
    PEC,
    PEC_Trigger,
    apply_pec_trigger,
    create_pec_machine,
)


class TestPECEnum:
    def test_values_are_strings(self) -> None:
        for member in PEC:
            assert isinstance(member, str)

    def test_all_states_exist(self) -> None:
        names = {m.name for m in PEC}
        assert names == {
            "NO_EMBARGO",
            "INVITED",
            "SIGNATORY",
            "DECLINED",
            "LAPSED",
        }


class TestPECTriggerEnum:
    def test_all_triggers_exist(self) -> None:
        names = {m.name for m in PEC_Trigger}
        assert names == {"INVITE", "ACCEPT", "DECLINE", "REVISE", "RESET"}


class TestPECMachineCreation:
    def test_create_returns_machine(self) -> None:
        from transitions import Machine

        machine = create_pec_machine()
        assert isinstance(machine, Machine)


class TestApplyPecTrigger:
    # --- INVITE transitions ---
    def test_invite_from_no_embargo(self) -> None:
        result = apply_pec_trigger(PEC.NO_EMBARGO, PEC_Trigger.INVITE)
        assert result == PEC.INVITED

    def test_invite_from_lapsed(self) -> None:
        result = apply_pec_trigger(PEC.LAPSED, PEC_Trigger.INVITE)
        assert result == PEC.INVITED

    def test_invite_from_declined(self) -> None:
        result = apply_pec_trigger(PEC.DECLINED, PEC_Trigger.INVITE)
        assert result == PEC.INVITED

    # --- ACCEPT transitions ---
    def test_accept_from_invited(self) -> None:
        result = apply_pec_trigger(PEC.INVITED, PEC_Trigger.ACCEPT)
        assert result == PEC.SIGNATORY

    def test_accept_from_lapsed(self) -> None:
        result = apply_pec_trigger(PEC.LAPSED, PEC_Trigger.ACCEPT)
        assert result == PEC.SIGNATORY

    # --- DECLINE transitions ---
    def test_decline_from_invited(self) -> None:
        result = apply_pec_trigger(PEC.INVITED, PEC_Trigger.DECLINE)
        assert result == PEC.DECLINED

    def test_decline_from_lapsed(self) -> None:
        result = apply_pec_trigger(PEC.LAPSED, PEC_Trigger.DECLINE)
        assert result == PEC.DECLINED

    # --- REVISE transition ---
    def test_revise_from_signatory(self) -> None:
        result = apply_pec_trigger(PEC.SIGNATORY, PEC_Trigger.REVISE)
        assert result == PEC.LAPSED

    # --- RESET transitions (wildcard) ---
    @pytest.mark.parametrize(
        "state",
        [PEC.NO_EMBARGO, PEC.INVITED, PEC.SIGNATORY, PEC.DECLINED, PEC.LAPSED],
    )
    def test_reset_from_any_state(self, state: PEC) -> None:
        result = apply_pec_trigger(state, PEC_Trigger.RESET)
        assert result == PEC.NO_EMBARGO

    # --- Invalid transitions return current state (no raise) ---
    def test_invite_from_signatory_is_invalid(self) -> None:
        result = apply_pec_trigger(PEC.SIGNATORY, PEC_Trigger.INVITE)
        assert result == PEC.SIGNATORY  # unchanged

    def test_accept_from_no_embargo_is_invalid(self) -> None:
        result = apply_pec_trigger(PEC.NO_EMBARGO, PEC_Trigger.ACCEPT)
        assert result == PEC.NO_EMBARGO  # unchanged

    def test_accept_from_declined_is_invalid(self) -> None:
        result = apply_pec_trigger(PEC.DECLINED, PEC_Trigger.ACCEPT)
        assert result == PEC.DECLINED  # unchanged

    def test_decline_from_no_embargo_is_invalid(self) -> None:
        result = apply_pec_trigger(PEC.NO_EMBARGO, PEC_Trigger.DECLINE)
        assert result == PEC.NO_EMBARGO  # unchanged

    def test_revise_from_invited_is_invalid(self) -> None:
        result = apply_pec_trigger(PEC.INVITED, PEC_Trigger.REVISE)
        assert result == PEC.INVITED  # unchanged

    def test_revise_from_no_embargo_is_invalid(self) -> None:
        result = apply_pec_trigger(PEC.NO_EMBARGO, PEC_Trigger.REVISE)
        assert result == PEC.NO_EMBARGO  # unchanged
