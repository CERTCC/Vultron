"""Tests for the per-embargo consent row-state table (ADR-0122, CM-18-003)."""

import pytest

from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
    PEC_Trigger,
    consent_after,
    consent_trigger_is_legal,
)
from vultron.errors import VultronInvalidStateTransitionError

S = EmbargoConsentState
T = PEC_Trigger

# The complete transition table of ADR-0122: (source, trigger) -> destination.
LEGAL: dict[tuple[S, T], S] = {
    (S.UNINVITED, T.INVITE): S.INVITED,
    (S.DECLINED, T.INVITE): S.INVITED,
    (S.TIMED_OUT, T.INVITE): S.INVITED,
    (S.UNINVITED, T.AGREE): S.AGREED,
    (S.INVITED, T.AGREE): S.AGREED,
    (S.TIMED_OUT, T.AGREE): S.AGREED,
    (S.UNINVITED, T.DECLINE): S.DECLINED,
    (S.INVITED, T.DECLINE): S.DECLINED,
    (S.AGREED, T.DECLINE): S.DECLINED,
    (S.TIMED_OUT, T.DECLINE): S.DECLINED,
    (S.INVITED, T.TIME_OUT): S.TIMED_OUT,
    (S.UNINVITED, T.CARRY_OVER): S.AGREED,
    (S.INVITED, T.CARRY_OVER): S.AGREED,
    (S.DECLINED, T.CARRY_OVER): S.AGREED,
    (S.TIMED_OUT, T.CARRY_OVER): S.AGREED,
}

ALL_PAIRS = [(src, trig) for src in S for trig in T]
ILLEGAL = [pair for pair in ALL_PAIRS if pair not in LEGAL]


def _id(pair: tuple[S, T]) -> str:
    src, trig = pair
    return f"{src.value}-{trig.name}"


class TestEnums:
    @pytest.mark.spec("SM-08-001")
    def test_row_states_are_strings(self) -> None:
        for member in S:
            assert isinstance(member, str)

    def test_all_row_states_exist(self) -> None:
        assert {m.name for m in S} == {
            "UNINVITED",
            "INVITED",
            "AGREED",
            "DECLINED",
            "TIMED_OUT",
        }

    def test_all_triggers_exist(self) -> None:
        assert {m.name for m in T} == {
            "INVITE",
            "AGREE",
            "DECLINE",
            "TIME_OUT",
            "CARRY_OVER",
        }

    def test_retired_names_are_gone(self) -> None:
        import vultron.core.states.participant_embargo_consent as module

        for name in (
            "PEC",
            "PEC_TERMINAL_STATES",
            "create_pec_machine",
            "PECTransition",
        ):
            assert not hasattr(module, name), name
        for state in ("ACCEPTED", "EXPIRED", "SIGNATORY", "UNBOUND"):
            assert not hasattr(S, state), state
        for trigger in ("ACCEPT", "EXPIRE", "REVISE", "EXIT"):
            assert not hasattr(T, trigger), trigger


class TestTransitionTable:
    def test_table_covers_every_pair_exactly_once(self) -> None:
        assert len(ALL_PAIRS) == 5 * 5
        assert len(LEGAL) + len(ILLEGAL) == len(ALL_PAIRS)

    @pytest.mark.spec("CM-18-003")
    @pytest.mark.parametrize("pair", list(LEGAL), ids=_id)
    def test_legal_pair_moves_to_destination(self, pair: tuple[S, T]) -> None:
        src, trig = pair
        assert consent_trigger_is_legal(src, trig) is True
        assert consent_after(src, trig) is LEGAL[pair]

    @pytest.mark.spec("CM-18-003")
    @pytest.mark.parametrize("pair", ILLEGAL, ids=_id)
    def test_illegal_pair_is_refused(self, pair: tuple[S, T]) -> None:
        src, trig = pair
        assert consent_trigger_is_legal(src, trig) is False
        with pytest.raises(VultronInvalidStateTransitionError):
            consent_after(src, trig)

    @pytest.mark.spec("CM-18-003")
    def test_refusal_names_the_trigger(self) -> None:
        with pytest.raises(VultronInvalidStateTransitionError) as exc:
            consent_after(S.AGREED, T.INVITE)
        assert "invite" in str(exc.value).lower()

    @pytest.mark.spec("CM-18-003")
    def test_declined_is_not_agreed_without_a_new_invite(self) -> None:
        assert not consent_trigger_is_legal(S.DECLINED, T.AGREE)
        reinvited = consent_after(S.DECLINED, T.INVITE)
        assert consent_after(reinvited, T.AGREE) is S.AGREED

    @pytest.mark.spec("CM-18-003")
    def test_carry_over_lifts_a_declined_row(self) -> None:
        """Agreeing to N days is agreeing to every shorter period (EP-05-001)."""
        assert consent_after(S.DECLINED, T.CARRY_OVER) is S.AGREED

    @pytest.mark.spec("CM-18-003")
    def test_carry_over_is_refused_from_agreed_only(self) -> None:
        refused = [
            s for s in S if not consent_trigger_is_legal(s, T.CARRY_OVER)
        ]
        assert refused == [S.AGREED]

    @pytest.mark.spec("CM-18-003")
    def test_only_an_invited_row_can_time_out(self) -> None:
        legal_sources = [
            s for s in S if consent_trigger_is_legal(s, T.TIME_OUT)
        ]
        assert legal_sources == [S.INVITED]

    @pytest.mark.spec("CM-18-003")
    def test_agreed_is_idempotent_only_by_the_caller(self) -> None:
        """A second AGREE from AGREED is illegal here; callers guard it."""
        assert not consent_trigger_is_legal(S.AGREED, T.AGREE)
