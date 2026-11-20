"""The what and the why of an embargo termination (ADR-0122, #4293)."""

from datetime import timedelta

import pytest
from pydantic import ValidationError

from test.support.embargo_register import (
    activate,
    propose,
    stand_in,
    terminate,
)
from test.support.objects import make, with_times
from vultron.core.models._helpers import now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.embargo_register import termination_changes
from vultron.core.models.embargo_termination import (
    EmbargoTermination,
    EndTimeReachedCause,
    FixDeployedCause,
    OtherCause,
    TerminationCause,
    TerminationCauseKind,
    ThreatSignal,
    ThreatSignalCause,
    ThreatSignalTermination,
    end_time_violations,
    threat_signals_of,
)
from vultron.core.states.cs import CS_pxa
from vultron.core.states.embargo_register import EmbargoRegisterStatus

S = EmbargoRegisterStatus
A = "https://example.org/embargoes/a"
B = "https://example.org/embargoes/b"


# ---------------------------------------------------------------------------
# The shape
# ---------------------------------------------------------------------------


@pytest.mark.spec("EMB-13-010")
def test_end_time_reached_is_a_cause_kind_like_the_others() -> None:
    assert [k.value for k in TerminationCauseKind] == [
        "END_TIME_REACHED",
        "THREAT_SIGNAL",
        "FIX_READY",
        "FIX_DEPLOYED",
        "OTHER",
    ]
    termination = EmbargoTermination.end_time_reached()
    assert termination.cause == EndTimeReachedCause()
    assert termination.is_end_time_reached


@pytest.mark.spec("EMB-13-010")
def test_a_termination_declares_no_separate_reason() -> None:
    """The END_TIME_REACHED/EARLY what is folded into the cause (ADR-0203).

    Beside the cause it holds only the causing act and the human reason
    (ADR-0202).
    """
    assert set(EmbargoTermination.model_fields) == {
        "cause",
        "caused_by",
        "summary",
    }
    with pytest.raises(ValidationError, match="reason"):
        EmbargoTermination.model_validate(
            {"reason": "EARLY", "cause": {"kind": "OTHER"}}
        )


@pytest.mark.parametrize(
    "termination",
    [
        EmbargoTermination.other(),
        EmbargoTermination(cause=FixDeployedCause()),
        EmbargoTermination.threat([ThreatSignal.P]),
    ],
    ids=["no-cause", "fix-deployed", "threat"],
)
def test_every_other_termination_ends_the_embargo_early(termination) -> None:
    assert not termination.is_end_time_reached


def test_a_threat_cause_names_its_signals_in_order() -> None:
    termination = EmbargoTermination.threat([ThreatSignal.P, ThreatSignal.A])
    assert not termination.is_end_time_reached
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


@pytest.mark.parametrize(
    ("termination", "dumped"),
    [
        (
            EmbargoTermination.threat([ThreatSignal.X]),
            {
                "cause": {"kind": "THREAT_SIGNAL", "signals": ["X"]},
                "causedBy": None,
                "summary": None,
            },
        ),
        (
            EmbargoTermination.end_time_reached(),
            {
                "cause": {"kind": "END_TIME_REACHED"},
                "causedBy": None,
                "summary": None,
            },
        ),
        (
            EmbargoTermination(
                cause=OtherCause(),
                caused_by="https://example.org/acts/1",
                summary="The vendor shipped early.",
            ),
            {
                "cause": {"kind": "OTHER"},
                "causedBy": "https://example.org/acts/1",
                "summary": "The vendor shipped early.",
            },
        ),
    ],
    ids=["threat", "end-time", "other-with-act-and-reason"],
)
def test_the_termination_round_trips_through_its_wire_spelling(
    termination, dumped
) -> None:
    assert termination.model_dump(mode="json", by_alias=True) == dumped
    assert EmbargoTermination.model_validate(dumped) == termination


@pytest.mark.spec("EMB-13-010")
def test_a_stored_termination_requires_its_cause() -> None:
    """The stored termination always names its cause kind (ADR-0202)."""
    with pytest.raises(ValidationError, match="cause"):
        EmbargoTermination.model_validate({})
    with pytest.raises(ValidationError, match="cause"):
        EmbargoTermination.model_validate({"cause": None})


@pytest.mark.spec("EMB-13-011")
def test_a_remove_naming_no_cause_records_other() -> None:
    assert EmbargoTermination.from_cause(None) == EmbargoTermination.other()
    cause = FixDeployedCause()
    assert EmbargoTermination.from_cause(cause).cause == cause


@pytest.mark.parametrize("field", ["causedBy", "summary"])
def test_a_termination_refuses_a_blank_act_or_reason(field: str) -> None:
    with pytest.raises(ValidationError):
        EmbargoTermination.model_validate(
            {"cause": {"kind": "OTHER"}, field: ""}
        )


def test_an_end_time_cause_carries_no_detail() -> None:
    cause: TerminationCause = EndTimeReachedCause()
    assert cause.model_dump(mode="json", by_alias=True) == {
        "kind": "END_TIME_REACHED"
    }
    with pytest.raises(ValidationError):
        EndTimeReachedCause.model_validate(
            {"kind": "END_TIME_REACHED", "signals": ["P"]}
        )


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
        EmbargoTermination.other(),
        EmbargoTermination.end_time_reached(),
        EmbargoTermination.threat([ThreatSignal.P]),
    ],
)
def test_the_terminated_entry_records_the_termination(termination) -> None:
    case = make(
        VulnerabilityCase, name="c", attributed_to="https://example.org/o"
    )
    activate(case, A)
    propose(case, B)

    terminate(case, termination)

    entry = case.registered_embargo(A)
    assert entry is not None and entry.status is S.TERMINATED
    assert entry.termination == termination
    assert case.embargo_termination == termination
    assert case.embargo_register_status(B) is S.CANCELLED
    restored = VulnerabilityCase.model_validate(
        with_times(
            VulnerabilityCase, case.model_dump(mode="json", by_alias=True)
        )
    )
    assert restored.embargo_termination == termination


def test_only_a_terminated_embargo_carries_a_termination() -> None:
    embargo = stand_in(A).model_dump()
    with pytest.raises(ValidationError, match="termination is required"):
        EmbargoEvent.model_validate({**embargo, "status": S.TERMINATED})
    with pytest.raises(ValidationError, match="refused otherwise"):
        EmbargoEvent.model_validate(
            {
                **embargo,
                "status": S.ACTIVE,
                "termination": EmbargoTermination.other(),
            }
        )


def test_the_termination_step_carries_the_termination() -> None:
    case = make(
        VulnerabilityCase, name="c", attributed_to="https://example.org/o"
    )
    activate(case, A)
    (change,) = termination_changes(
        case.embargo_register, EmbargoTermination.end_time_reached()
    )
    assert change.termination == EmbargoTermination.end_time_reached()


def test_a_case_with_no_ended_embargo_records_no_termination() -> None:
    case = make(
        VulnerabilityCase, name="c", attributed_to="https://example.org/o"
    )
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
            EmbargoTermination.other(), end_time=now_utc(), at=None
        )
        == []
    )


@pytest.mark.parametrize(
    "signals", [[], [ThreatSignal.X, ThreatSignal.P], [ThreatSignal.A] * 2]
)
def test_given_threat_signals_are_checked_when_built(signals) -> None:
    with pytest.raises(ValidationError):
        ThreatSignalTermination(signals=signals)


def test_a_resolved_threat_termination_ends_the_embargo_early() -> None:
    resolved = ThreatSignalTermination().resolve(CS_pxa.Pxa)
    assert not resolved.is_end_time_reached
