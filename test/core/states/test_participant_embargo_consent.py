"""Tests for the per-embargo consent row-state table (ADR-0120, CM-18-003)."""

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

# The complete transition table: (source, trigger) -> destination.  A source of
# ``None`` is "no row yet" (never asked).
LEGAL: dict[tuple[S | None, T], S] = {
    (None, T.INVITE): S.INVITED,
    (S.DECLINED, T.INVITE): S.INVITED,
    (S.EXPIRED, T.INVITE): S.INVITED,
    (None, T.ACCEPT): S.ACCEPTED,
    (S.INVITED, T.ACCEPT): S.ACCEPTED,
    (S.EXPIRED, T.ACCEPT): S.ACCEPTED,
    (None, T.DECLINE): S.DECLINED,
    (S.INVITED, T.DECLINE): S.DECLINED,
    (S.ACCEPTED, T.DECLINE): S.DECLINED,
    (S.EXPIRED, T.DECLINE): S.DECLINED,
    (S.INVITED, T.EXPIRE): S.EXPIRED,
}

SOURCES: list[S | None] = [None, *S]
ALL_PAIRS = [(src, trig) for src in SOURCES for trig in T]
ILLEGAL = [pair for pair in ALL_PAIRS if pair not in LEGAL]


def _id(pair: tuple[S | None, T]) -> str:
    src, trig = pair
    return f"{src.value if src else 'NO_ROW'}-{trig.name}"


class TestEnums:
    @pytest.mark.spec("SM-08-001")
    def test_row_states_are_strings(self) -> None:
        for member in S:
            assert isinstance(member, str)

    def test_all_row_states_exist(self) -> None:
        assert {m.name for m in S} == {
            "INVITED",
            "ACCEPTED",
            "DECLINED",
            "EXPIRED",
        }

    def test_all_triggers_exist(self) -> None:
        assert {m.name for m in T} == {
            "INVITE",
            "ACCEPT",
            "DECLINE",
            "EXPIRE",
        }

    def test_retired_mechanisms_are_gone(self) -> None:
        import vultron.core.states.participant_embargo_consent as module

        for name in (
            "PEC",
            "PEC_TERMINAL_STATES",
            "create_pec_machine",
            "PECTransition",
        ):
            assert not hasattr(module, name), name
        assert not hasattr(T, "REVISE")
        assert not hasattr(T, "EXIT")


class TestTransitionTable:
    def test_table_covers_every_pair_exactly_once(self) -> None:
        assert len(ALL_PAIRS) == 5 * 4
        assert len(LEGAL) + len(ILLEGAL) == len(ALL_PAIRS)

    @pytest.mark.spec("CM-18-003")
    @pytest.mark.parametrize("pair", list(LEGAL), ids=_id)
    def test_legal_pair_moves_to_destination(
        self, pair: tuple[S | None, T]
    ) -> None:
        src, trig = pair
        assert consent_trigger_is_legal(src, trig) is True
        assert consent_after(src, trig) is LEGAL[pair]

    @pytest.mark.spec("CM-18-003")
    @pytest.mark.parametrize("pair", ILLEGAL, ids=_id)
    def test_illegal_pair_is_refused(self, pair: tuple[S | None, T]) -> None:
        src, trig = pair
        assert consent_trigger_is_legal(src, trig) is False
        with pytest.raises(VultronInvalidStateTransitionError):
            consent_after(src, trig)

    @pytest.mark.spec("CM-18-003")
    def test_refusal_names_the_trigger(self) -> None:
        with pytest.raises(VultronInvalidStateTransitionError) as exc:
            consent_after(S.ACCEPTED, T.INVITE)
        assert "invite" in str(exc.value).lower()

    @pytest.mark.spec("CM-18-003")
    def test_declined_is_not_accepted_without_a_new_invite(self) -> None:
        assert not consent_trigger_is_legal(S.DECLINED, T.ACCEPT)
        reinvited = consent_after(S.DECLINED, T.INVITE)
        assert consent_after(reinvited, T.ACCEPT) is S.ACCEPTED

    @pytest.mark.spec("CM-18-003")
    def test_only_an_invited_row_can_expire(self) -> None:
        legal_sources = [
            s for s in SOURCES if consent_trigger_is_legal(s, T.EXPIRE)
        ]
        assert legal_sources == [S.INVITED]

    @pytest.mark.spec("CM-18-003")
    def test_accepted_is_idempotent_only_by_the_caller(self) -> None:
        """A second ACCEPT from ACCEPTED is illegal here; callers guard it."""
        assert not consent_trigger_is_legal(S.ACCEPTED, T.ACCEPT)
