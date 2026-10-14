"""The what and the why of an embargo termination (ADR-0122, #4293)."""

from datetime import timedelta

import pytest
from pydantic import ValidationError

from test.support.embargo_register import activate, propose, terminate
from vultron.core.models._helpers import now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_register import (
    EmbargoRegisterEntry,
    termination_changes,
)
from vultron.core.models.embargo_termination import (
    EmbargoTermination,
    TerminationCauseKind,
    ThreatSignal,
    ThreatSignalCause,
    ThreatSignalTermination,
    end_time_violations,
    threat_signals_of,
)
from vultron.core.states.cs import CS_pxa
from vultron.core.states.embargo_register import (
    EmbargoRegisterStatus,
    TerminationReason,
    termination_reason_from_content,
)

S = EmbargoRegisterStatus
A = "https://example.org/embargoes/a"
B = "https://example.org/embargoes/b"


# ---------------------------------------------------------------------------
# The shape
# ---------------------------------------------------------------------------


@pytest.mark.spec("EMB-13-004")
def test_the_wire_what_has_exactly_two_values() -> None:
    assert [r.value for r in TerminationReason] == [
        "END_TIME_REACHED",
        "EARLY",
    ]


@pytest.mark.spec("EMB-13-004")
@pytest.mark.parametrize("content", [None, "", "THREAT_SIGNAL", "early", 1])
def test_content_that_is_not_a_reason_is_refused(content) -> None:
    with pytest.raises(ValueError, match="END_TIME_REACHED"):
        termination_reason_from_content(content)


def test_a_threat_cause_names_its_signals_in_order() -> None:
    termination = EmbargoTermination.threat([ThreatSignal.P, ThreatSignal.A])
    assert termination.reason is TerminationReason.EARLY
    assert termination.cause == ThreatSignalCause(
        signals=[ThreatSignal.P, ThreatSignal.A]
    )
    assert termination.cause is not None
    assert termination.cause.kind is TerminationCauseKind.THREAT_SIGNAL


@pytest.mark.parametrize(
    "signals",
    [[], [ThreatSignal.A, ThreatSignal.P], [ThreatSignal.P, ThreatSignal.P]],
)
def test_a_threat_cause_refuses_empty_repeated_or_unordered_signals(
    signals,
) -> None:
    with pytest.raises(ValidationError):
        ThreatSignalCause(signals=signals)


def test_a_threat_cause_cannot_end_an_embargo_at_its_end_time() -> None:
    with pytest.raises(ValidationError, match="cannot have"):
        EmbargoTermination(
            reason=TerminationReason.END_TIME_REACHED,
            cause=ThreatSignalCause(signals=[ThreatSignal.P]),
        )


def test_the_termination_round_trips_through_its_wire_spelling() -> None:
    termination = EmbargoTermination.threat([ThreatSignal.X])
    dumped = termination.model_dump(mode="json", by_alias=True)
    assert dumped == {
        "reason": "EARLY",
        "cause": {"kind": "THREAT_SIGNAL", "signals": ["X"]},
    }
    assert EmbargoTermination.model_validate(dumped) == termination


@pytest.mark.parametrize(
    ("pxa", "signals"),
    [
        (CS_pxa.pxa, []),
        (CS_pxa.Pxa, [ThreatSignal.P]),
        (CS_pxa.pXA, [ThreatSignal.X, ThreatSignal.A]),
        (CS_pxa.PXA, [ThreatSignal.P, ThreatSignal.X, ThreatSignal.A]),
    ],
)
def test_threat_signals_are_read_off_the_pxa_state(pxa, signals) -> None:
    assert threat_signals_of(pxa) == signals


def test_a_threat_request_resolves_against_the_case_when_unspecified() -> None:
    resolved = ThreatSignalTermination().resolve(CS_pxa.PXa)
    assert resolved == EmbargoTermination.threat(
        [ThreatSignal.P, ThreatSignal.X]
    )
    given = ThreatSignalTermination(signals=[ThreatSignal.A])
    assert given.resolve(CS_pxa.pxa) == EmbargoTermination.threat(
        [ThreatSignal.A]
    )


def test_a_threat_request_with_no_signal_anywhere_is_refused() -> None:
    with pytest.raises(ValueError, match="P, X or A"):
        ThreatSignalTermination().resolve(CS_pxa.pxa)


# ---------------------------------------------------------------------------
# The register records it (AC-2)
# ---------------------------------------------------------------------------


@pytest.mark.spec("EP-08-004")
@pytest.mark.parametrize(
    "termination",
    [
        EmbargoTermination.early(),
        EmbargoTermination.end_time_reached(),
        EmbargoTermination.threat([ThreatSignal.P]),
    ],
)
def test_the_terminated_entry_records_the_termination(termination) -> None:
    case = VulnerabilityCase(name="c", attributed_to="https://example.org/o")
    activate(case, A)
    propose(case, B)

    terminate(case, termination)

    entry = case.embargo_register_entry(A)
    assert entry is not None and entry.status is S.TERMINATED
    assert entry.termination == termination
    assert case.embargo_termination == termination
    assert case.embargo_register_status(B) is S.CANCELLED
    restored = VulnerabilityCase.model_validate(
        case.model_dump(mode="json", by_alias=True)
    )
    assert restored.embargo_termination == termination


def test_only_a_terminated_entry_carries_a_termination() -> None:
    with pytest.raises(ValidationError, match="termination is required"):
        EmbargoRegisterEntry(embargo=A, status=S.TERMINATED)
    with pytest.raises(ValidationError, match="refused otherwise"):
        EmbargoRegisterEntry(
            embargo=A,
            status=S.ACTIVE,
            termination=EmbargoTermination.early(),
        )


def test_the_termination_step_carries_the_termination() -> None:
    case = VulnerabilityCase(name="c", attributed_to="https://example.org/o")
    activate(case, A)
    (change,) = termination_changes(
        case.embargo_register, EmbargoTermination.end_time_reached()
    )
    assert change.termination == EmbargoTermination.end_time_reached()


def test_a_case_with_no_ended_embargo_records_no_termination() -> None:
    case = VulnerabilityCase(name="c", attributed_to="https://example.org/o")
    activate(case, A)
    assert case.embargo_termination is None


# ---------------------------------------------------------------------------
# The end-time rule (AC-2)
# ---------------------------------------------------------------------------


@pytest.mark.spec("EMB-13-003")
def test_end_time_reached_is_refused_before_the_end_time() -> None:
    end = now_utc()
    violations = end_time_violations(
        EmbargoTermination.end_time_reached(),
        end_time=end,
        at=end - timedelta(seconds=1),
    )
    assert violations and "before" in violations[0]


@pytest.mark.spec("EMB-13-003")
def test_end_time_reached_is_allowed_at_and_after_the_end_time() -> None:
    end = now_utc()
    for at in (end, end + timedelta(days=1)):
        assert (
            end_time_violations(
                EmbargoTermination.end_time_reached(), end_time=end, at=at
            )
            == []
        )


@pytest.mark.spec("EMB-13-003")
def test_end_time_reached_needs_the_time_it_was_claimed_at() -> None:
    assert end_time_violations(
        EmbargoTermination.end_time_reached(), end_time=now_utc(), at=None
    )


def test_an_early_termination_has_no_time_rule() -> None:
    assert (
        end_time_violations(
            EmbargoTermination.early(), end_time=now_utc(), at=None
        )
        == []
    )


@pytest.mark.parametrize(
    "signals", [[], [ThreatSignal.X, ThreatSignal.P], [ThreatSignal.A] * 2]
)
def test_given_threat_signals_are_checked_when_built(signals) -> None:
    with pytest.raises(ValidationError):
        ThreatSignalTermination(signals=signals)


def test_a_threat_request_is_an_early_termination_on_the_wire() -> None:
    assert ThreatSignalTermination().reason is TerminationReason.EARLY
