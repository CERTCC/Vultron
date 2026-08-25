"""Tests for the Participant Embargo Consent (PEC) state machine."""

import pytest

from vultron.core.models.dimensions import PecDimension
from vultron.core.states.participant_embargo_consent import (
    PEC,
    PEC_Trigger,
    create_pec_machine,
)
from vultron.errors import VultronInvalidStateTransitionError


class TestPECEnum:
    @pytest.mark.spec("SM-08-001")
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


class TestPecDimensionTransition:
    # --- INVITE transitions ---
    @pytest.mark.spec("SDO-02-001")
    def test_invite_from_no_embargo(self) -> None:
        result = PecDimension(state=PEC.NO_EMBARGO).transition(
            PEC_Trigger.INVITE
        )
        assert result.state == PEC.INVITED

    @pytest.mark.spec("SDO-02-001")
    def test_invite_from_lapsed(self) -> None:
        result = PecDimension(state=PEC.LAPSED).transition(PEC_Trigger.INVITE)
        assert result.state == PEC.INVITED

    @pytest.mark.spec("SDO-02-001")
    def test_invite_from_declined(self) -> None:
        result = PecDimension(state=PEC.DECLINED).transition(
            PEC_Trigger.INVITE
        )
        assert result.state == PEC.INVITED

    # --- ACCEPT transitions ---
    @pytest.mark.spec("SDO-02-001")
    def test_accept_from_invited(self) -> None:
        result = PecDimension(state=PEC.INVITED).transition(PEC_Trigger.ACCEPT)
        assert result.state == PEC.SIGNATORY

    @pytest.mark.spec("SDO-02-001")
    def test_accept_from_lapsed(self) -> None:
        result = PecDimension(state=PEC.LAPSED).transition(PEC_Trigger.ACCEPT)
        assert result.state == PEC.SIGNATORY

    # --- DECLINE transitions ---
    @pytest.mark.spec("SDO-02-001")
    def test_decline_from_invited(self) -> None:
        result = PecDimension(state=PEC.INVITED).transition(
            PEC_Trigger.DECLINE
        )
        assert result.state == PEC.DECLINED

    @pytest.mark.spec("SDO-02-001")
    def test_decline_from_lapsed(self) -> None:
        result = PecDimension(state=PEC.LAPSED).transition(PEC_Trigger.DECLINE)
        assert result.state == PEC.DECLINED

    # --- REVISE transition ---
    @pytest.mark.spec("SDO-02-001")
    def test_revise_from_signatory(self) -> None:
        result = PecDimension(state=PEC.SIGNATORY).transition(
            PEC_Trigger.REVISE
        )
        assert result.state == PEC.LAPSED

    # --- RESET transitions (wildcard) ---
    @pytest.mark.spec("SDO-02-001")
    @pytest.mark.parametrize(
        "state",
        [PEC.NO_EMBARGO, PEC.INVITED, PEC.SIGNATORY, PEC.DECLINED, PEC.LAPSED],
    )
    def test_reset_from_any_state(self, state: PEC) -> None:
        result = PecDimension(state=state).transition(PEC_Trigger.RESET)
        assert result.state == PEC.NO_EMBARGO

    # --- ADR-0048: ACCEPT and DECLINE directly from NO_EMBARGO ---
    @pytest.mark.spec("SDO-02-001")
    def test_accept_from_no_embargo(self) -> None:
        result = PecDimension(state=PEC.NO_EMBARGO).transition(
            PEC_Trigger.ACCEPT
        )
        assert result.state == PEC.SIGNATORY

    @pytest.mark.spec("SDO-02-001")
    def test_decline_from_no_embargo(self) -> None:
        result = PecDimension(state=PEC.NO_EMBARGO).transition(
            PEC_Trigger.DECLINE
        )
        assert result.state == PEC.DECLINED

    # --- CM-18-004: SIGNATORY → INVITED must remain invalid ---
    @pytest.mark.spec("SDO-02-002")
    def test_invite_from_signatory_raises(self) -> None:
        with pytest.raises(VultronInvalidStateTransitionError):
            PecDimension(state=PEC.SIGNATORY).transition(PEC_Trigger.INVITE)

    # --- Other invalid transitions raise VultronInvalidStateTransitionError ---
    @pytest.mark.spec("SDO-02-002")
    def test_accept_from_declined_raises(self) -> None:
        with pytest.raises(VultronInvalidStateTransitionError):
            PecDimension(state=PEC.DECLINED).transition(PEC_Trigger.ACCEPT)

    @pytest.mark.spec("SDO-02-002")
    def test_decline_from_declined_raises(self) -> None:
        with pytest.raises(VultronInvalidStateTransitionError):
            PecDimension(state=PEC.DECLINED).transition(PEC_Trigger.DECLINE)

    @pytest.mark.spec("SDO-02-002")
    def test_revise_from_invited_raises(self) -> None:
        with pytest.raises(VultronInvalidStateTransitionError):
            PecDimension(state=PEC.INVITED).transition(PEC_Trigger.REVISE)

    @pytest.mark.spec("SDO-02-002")
    def test_revise_from_no_embargo_raises(self) -> None:
        with pytest.raises(VultronInvalidStateTransitionError):
            PecDimension(state=PEC.NO_EMBARGO).transition(PEC_Trigger.REVISE)
