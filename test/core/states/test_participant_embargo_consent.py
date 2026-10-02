"""Tests for the Participant Embargo Consent (PEC) state machine."""

import pytest

from vultron.core.models.dimensions import PecDimension
from vultron.core.states.participant_embargo_consent import (
    PEC,
    PEC_TERMINAL_STATES,
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
            "UNBOUND",
            "INVITED",
            "SIGNATORY",
            "DECLINED",
            "LAPSED",
            "EXPIRED",
            "UNBOUND_EXITED",
        }


class TestPECTriggerEnum:
    def test_all_triggers_exist(self) -> None:
        names = {m.name for m in PEC_Trigger}
        assert names == {
            "INVITE",
            "ACCEPT",
            "DECLINE",
            "REVISE",
            "EXPIRE",
            "EXIT",
        }


class TestPECMachineCreation:
    def test_create_returns_machine(self) -> None:
        from transitions import Machine

        machine = create_pec_machine()
        assert isinstance(machine, Machine)


class TestPecDimensionTransition:
    # --- INVITE transitions ---
    @pytest.mark.spec("SDO-02-001")
    def test_invite_from_unbound(self) -> None:
        result = PecDimension(state=PEC.UNBOUND).transition(PEC_Trigger.INVITE)
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

    # --- EXIT transitions (ADR-0118): every non-terminal state ---
    @pytest.mark.spec("SDO-02-001", "CM-18-003")
    @pytest.mark.parametrize(
        "state", [s for s in PEC if s not in PEC_TERMINAL_STATES]
    )
    def test_exit_from_every_non_terminal_state(self, state: PEC) -> None:
        result = PecDimension(state=state).transition(PEC_Trigger.EXIT)
        assert result.state == PEC.UNBOUND_EXITED

    # --- UNBOUND_EXITED is terminal (ADR-0118) ---
    @pytest.mark.spec("SDO-02-002", "CM-18-003")
    @pytest.mark.parametrize("trigger", list(PEC_Trigger))
    def test_unbound_exited_refuses_every_trigger(
        self, trigger: PEC_Trigger
    ) -> None:
        with pytest.raises(VultronInvalidStateTransitionError):
            PecDimension(state=PEC.UNBOUND_EXITED).transition(trigger)

    def test_terminal_states_are_exactly_unbound_exited(self) -> None:
        assert frozenset({PEC.UNBOUND_EXITED}) == PEC_TERMINAL_STATES

    # --- EXPIRE and the EXPIRED state (ADR-0118) ---
    @pytest.mark.spec("SDO-02-001", "CM-18-002")
    def test_expire_from_invited(self) -> None:
        result = PecDimension(state=PEC.INVITED).transition(PEC_Trigger.EXPIRE)
        assert result.state == PEC.EXPIRED

    @pytest.mark.spec("SDO-02-002", "CM-18-002")
    @pytest.mark.parametrize("state", [s for s in PEC if s is not PEC.INVITED])
    def test_expire_only_from_invited(self, state: PEC) -> None:
        with pytest.raises(VultronInvalidStateTransitionError):
            PecDimension(state=state).transition(PEC_Trigger.EXPIRE)

    @pytest.mark.spec("SDO-02-001", "EMB-17-003")
    def test_invite_from_expired(self) -> None:
        result = PecDimension(state=PEC.EXPIRED).transition(PEC_Trigger.INVITE)
        assert result.state == PEC.INVITED

    @pytest.mark.spec("SDO-02-001", "EMB-17-002")
    def test_accept_from_expired(self) -> None:
        result = PecDimension(state=PEC.EXPIRED).transition(PEC_Trigger.ACCEPT)
        assert result.state == PEC.SIGNATORY

    @pytest.mark.spec("SDO-02-001")
    def test_decline_from_expired(self) -> None:
        """A late explicit Reject is an answer and records DECLINED."""
        result = PecDimension(state=PEC.EXPIRED).transition(
            PEC_Trigger.DECLINE
        )
        assert result.state == PEC.DECLINED

    @pytest.mark.spec("SDO-02-002")
    def test_revise_from_expired_raises(self) -> None:
        with pytest.raises(VultronInvalidStateTransitionError):
            PecDimension(state=PEC.EXPIRED).transition(PEC_Trigger.REVISE)

    @pytest.mark.spec("CM-18-002")
    def test_timer_expiry_is_not_a_decline(self) -> None:
        """The timer path lands on EXPIRED, never on DECLINED (ADR-0118)."""
        expired = PecDimension(state=PEC.INVITED).transition(
            PEC_Trigger.EXPIRE
        )
        declined = PecDimension(state=PEC.INVITED).transition(
            PEC_Trigger.DECLINE
        )
        assert expired.state is PEC.EXPIRED
        assert expired.state != declined.state
        assert not expired.is_declined()

    # --- ADR-0048: ACCEPT and DECLINE directly from UNBOUND ---
    @pytest.mark.spec("SDO-02-001")
    def test_accept_from_unbound(self) -> None:
        result = PecDimension(state=PEC.UNBOUND).transition(PEC_Trigger.ACCEPT)
        assert result.state == PEC.SIGNATORY

    @pytest.mark.spec("SDO-02-001")
    def test_decline_from_unbound(self) -> None:
        result = PecDimension(state=PEC.UNBOUND).transition(
            PEC_Trigger.DECLINE
        )
        assert result.state == PEC.DECLINED

    # --- ADR-0093: SIGNATORY → DECLINED via DECLINE trigger ---
    @pytest.mark.spec("SDO-02-001")
    def test_decline_from_signatory(self) -> None:
        result = PecDimension(state=PEC.SIGNATORY).transition(
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
    def test_revise_from_unbound_raises(self) -> None:
        with pytest.raises(VultronInvalidStateTransitionError):
            PecDimension(state=PEC.UNBOUND).transition(PEC_Trigger.REVISE)
