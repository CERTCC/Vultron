"""Tests for the embargo register's status table and derived EM (ADR-0122)."""

import itertools

import pytest

from vultron.core.states.em import EM
from vultron.core.states.embargo_register import (
    FINAL_REGISTER_STATUSES,
    EmbargoRegisterStatus,
    RegisterTrigger,
    derive_em,
    register_invariant_violations,
    register_status_after,
    register_trigger_is_legal,
)
from vultron.errors import VultronInvalidStateTransitionError

S = EmbargoRegisterStatus
T = RegisterTrigger

# The complete transition table: (source, trigger) -> destination.  A source of
# ``None`` is "no entry yet".
LEGAL: dict[tuple[S | None, T], S] = {
    (None, T.PROPOSE): S.PROPOSED,
    (S.PROPOSED, T.ACTIVATE): S.ACTIVE,
    (S.PROPOSED, T.REJECT): S.REJECTED,
    (S.ACTIVE, T.SUPERSEDE): S.SUPERSEDED,
    (S.ACTIVE, T.TERMINATE): S.TERMINATED,
    (S.PROPOSED, T.CANCEL): S.CANCELLED,
}

ALL_PAIRS = list(itertools.product([None, *S], T))


@pytest.mark.parametrize(("source", "trigger"), list(LEGAL))
def test_every_legal_transition_reaches_its_destination(
    source: S | None, trigger: T
) -> None:
    assert register_trigger_is_legal(source, trigger)
    assert register_status_after(source, trigger) is LEGAL[(source, trigger)]


@pytest.mark.parametrize(
    ("source", "trigger"), [p for p in ALL_PAIRS if p not in LEGAL]
)
def test_every_other_transition_is_refused(
    source: S | None, trigger: T
) -> None:
    assert not register_trigger_is_legal(source, trigger)
    with pytest.raises(VultronInvalidStateTransitionError):
        register_status_after(source, trigger)


@pytest.mark.parametrize("status", sorted(FINAL_REGISTER_STATUSES))
def test_final_statuses_accept_no_trigger(status: S) -> None:
    assert not any(register_trigger_is_legal(status, t) for t in T)


@pytest.mark.parametrize(
    ("statuses", "em"),
    [
        ([], EM.NONE),
        ([S.PROPOSED], EM.PROPOSED),
        ([S.PROPOSED, S.PROPOSED], EM.PROPOSED),
        ([S.ACTIVE], EM.ACTIVE),
        ([S.ACTIVE, S.PROPOSED], EM.REVISE),
        ([S.ACTIVE, S.PROPOSED, S.PROPOSED], EM.REVISE),
        ([S.TERMINATED], EM.EXITED),
        # Decided entries do not move EM.
        ([S.REJECTED], EM.NONE),
        ([S.CANCELLED, S.REJECTED], EM.NONE),
        ([S.REJECTED, S.PROPOSED], EM.PROPOSED),
        ([S.SUPERSEDED, S.ACTIVE], EM.ACTIVE),
        ([S.SUPERSEDED, S.ACTIVE, S.REJECTED, S.PROPOSED], EM.REVISE),
        ([S.SUPERSEDED, S.TERMINATED, S.CANCELLED], EM.EXITED),
    ],
)
def test_em_is_derived_from_the_register(statuses: list[S], em: EM) -> None:
    assert derive_em(statuses) is em


@pytest.mark.parametrize(
    ("statuses", "fragment"),
    [
        ([S.ACTIVE, S.ACTIVE], "2 entries are ACTIVE"),
        ([S.TERMINATED, S.TERMINATED], "2 entries are TERMINATED"),
        ([S.ACTIVE, S.TERMINATED], "ACTIVE and another is TERMINATED"),
        ([S.SUPERSEDED], "SUPERSEDED entry exists without"),
        ([S.SUPERSEDED, S.REJECTED], "SUPERSEDED entry exists without"),
        ([S.TERMINATED, S.PROPOSED], "PROPOSED while another is TERMINATED"),
    ],
)
def test_each_invariant_is_reported(statuses: list[S], fragment: str) -> None:
    violations = register_invariant_violations(statuses)
    assert any(fragment in v for v in violations), violations
    with pytest.raises(VultronInvalidStateTransitionError, match=fragment):
        derive_em(statuses)


def test_every_broken_invariant_is_reported_at_once() -> None:
    """EH-07-001: one refusal names every violation, not the first."""
    violations = register_invariant_violations(
        [S.ACTIVE, S.ACTIVE, S.TERMINATED, S.PROPOSED]
    )
    assert len(violations) == 3


@pytest.mark.parametrize(
    "statuses",
    [
        [],
        [S.PROPOSED, S.REJECTED, S.CANCELLED],
        [S.SUPERSEDED, S.SUPERSEDED, S.ACTIVE, S.PROPOSED],
        [S.SUPERSEDED, S.TERMINATED, S.CANCELLED, S.REJECTED],
    ],
)
def test_legal_registers_report_no_violation(statuses: list[S]) -> None:
    assert register_invariant_violations(statuses) == []
