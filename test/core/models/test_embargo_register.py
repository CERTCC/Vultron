"""Tests for embargo register steps and the case's register views (ADR-0122).

AC-1 and AC-2 of #4290: the register is append-only, applies its triggers by
step, and refuses every step that breaks a rule or an invariant.  AC-4 and
AC-5: rejecting one of two proposals keeps EM negotiating, activation records
what it replaced, and a threat signal cancels proposals rather than rejecting
them.
"""

from datetime import timedelta
from typing import Any

import pytest

from test.support.embargo_register import (
    activate,
    cancel_on_threat,
    propose,
    reject,
    terminate,
)
from vultron.core.models._helpers import now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.dimensions import EmDimension
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.embargo_register import (
    EmbargoRegisterEntry,
    RegisterChange,
    apply_register_step,
    carry_embargo_inline,
)
from vultron.core.states.em import EM
from vultron.core.states.embargo_register import (
    EmbargoRegisterStatus,
    RegisterTrigger,
    TerminationReason,
)
from vultron.errors import (
    VultronInvalidStateTransitionError,
    VultronValidationError,
)

S = EmbargoRegisterStatus
T = RegisterTrigger
OWNER = "https://example.org/actors/owner"
CASE_ID = "https://example.org/cases/c1"
A, B, C = (f"https://example.org/embargoes/{n}" for n in "abc")


def _entry(embargo_id: str, status: S, **kw: str) -> EmbargoRegisterEntry:
    return EmbargoRegisterEntry(embargo=embargo_id, status=status, **kw)


def _change(embargo_id: str, trigger: T, **kw: Any) -> RegisterChange:
    return RegisterChange(embargo_id=embargo_id, trigger=trigger, **kw)


def _terminate(embargo_id: str) -> RegisterChange:
    return _change(embargo_id, T.TERMINATE, reason=TerminationReason.EARLY)


def _statuses(entries: list[EmbargoRegisterEntry]) -> dict[str, S]:
    return {e.embargo_id: e.status for e in entries}


def _case(**kw: Any) -> VulnerabilityCase:
    return VulnerabilityCase(id_=CASE_ID, attributed_to=OWNER, **kw)


# ---------------------------------------------------------------------------
# Steps the register accepts
# ---------------------------------------------------------------------------


def test_propose_appends_a_proposed_entry() -> None:
    after = apply_register_step([], [_change(A, T.PROPOSE)])
    assert _statuses(after) == {A: S.PROPOSED}


def test_activation_supersedes_and_records_what_it_replaced() -> None:
    """AC-5: ACTIVATE and SUPERSEDE are one step, and ``replaces`` is set."""
    before = [_entry(A, S.ACTIVE), _entry(B, S.PROPOSED)]
    after = apply_register_step(
        before, [_change(B, T.ACTIVATE), _change(A, T.SUPERSEDE)]
    )
    assert _statuses(after) == {A: S.SUPERSEDED, B: S.ACTIVE}
    assert after[1].replaces == A
    assert after[0].replaces is None


def test_termination_cancels_every_open_proposal_in_the_same_step() -> None:
    before = [
        _entry(A, S.ACTIVE),
        _entry(B, S.PROPOSED),
        _entry(C, S.PROPOSED),
    ]
    after = apply_register_step(
        before,
        [_terminate(A), _change(B, T.CANCEL), _change(C, T.CANCEL)],
    )
    assert _statuses(after) == {
        A: S.TERMINATED,
        B: S.CANCELLED,
        C: S.CANCELLED,
    }


def test_threat_signal_cancels_proposals_while_none_is_active() -> None:
    after = apply_register_step(
        [_entry(A, S.PROPOSED)], [_change(A, T.CANCEL)], threat_signal=True
    )
    assert _statuses(after) == {A: S.CANCELLED}


def test_entries_are_never_removed() -> None:
    before = [_entry(A, S.PROPOSED), _entry(B, S.PROPOSED)]
    after = apply_register_step(before, [_change(A, T.REJECT)])
    assert [e.embargo_id for e in after] == [A, B]
    assert _statuses(after) == {A: S.REJECTED, B: S.PROPOSED}


def test_a_step_leaves_its_input_untouched() -> None:
    before = [_entry(A, S.PROPOSED)]
    apply_register_step(before, [_change(A, T.ACTIVATE)])
    assert before == [_entry(A, S.PROPOSED)]


# ---------------------------------------------------------------------------
# Steps the register refuses (AC-2: each refused combination)
# ---------------------------------------------------------------------------

REFUSED: dict[str, tuple[list[EmbargoRegisterEntry], list[RegisterChange]]] = {
    "re-proposing an entry": (
        [_entry(A, S.PROPOSED)],
        [_change(A, T.PROPOSE)],
    ),
    "a trigger on an unknown entry": ([], [_change(A, T.ACTIVATE)]),
    "a trigger on a final entry": (
        [_entry(A, S.REJECTED)],
        [_change(A, T.ACTIVATE)],
    ),
    "activating beside an ACTIVE entry (invariant 1)": (
        [_entry(A, S.ACTIVE), _entry(B, S.PROPOSED)],
        [_change(B, T.ACTIVATE)],
    ),
    "two activations in one step (invariant 1)": (
        [_entry(A, S.PROPOSED), _entry(B, S.PROPOSED)],
        [_change(A, T.ACTIVATE), _change(B, T.ACTIVATE)],
    ),
    "SUPERSEDE with no ACTIVATE": (
        [_entry(A, S.ACTIVE)],
        [_change(A, T.SUPERSEDE)],
    ),
    "terminating with a proposal left open (invariant 3)": (
        [_entry(A, S.ACTIVE), _entry(B, S.PROPOSED)],
        [_terminate(A)],
    ),
    "CANCEL with no TERMINATE and no threat signal": (
        [_entry(A, S.PROPOSED)],
        [_change(A, T.CANCEL)],
    ),
    "any change after TERMINATED (invariant 4)": (
        [_entry(A, S.TERMINATED)],
        [_change(B, T.PROPOSE)],
    ),
    "one entry changed twice in a step": (
        [_entry(A, S.PROPOSED)],
        [_change(A, T.ACTIVATE), _change(A, T.REJECT)],
    ),
    "SUPERSEDE beside a REJECT, not an ACTIVATE": (
        [_entry(A, S.ACTIVE), _entry(B, S.PROPOSED)],
        [_change(B, T.REJECT), _change(A, T.SUPERSEDE)],
    ),
}


@pytest.mark.parametrize("case", list(REFUSED), ids=list(REFUSED))
def test_refused_step_raises(case: str) -> None:
    before, changes = REFUSED[case]
    with pytest.raises(VultronInvalidStateTransitionError):
        apply_register_step(before, changes)


def test_threat_cancel_is_refused_while_an_embargo_is_active() -> None:
    with pytest.raises(VultronInvalidStateTransitionError, match="CANCEL"):
        apply_register_step(
            [_entry(A, S.ACTIVE), _entry(B, S.PROPOSED)],
            [_change(B, T.CANCEL)],
            threat_signal=True,
        )


def test_a_refusal_names_every_rule_the_step_breaks() -> None:
    """EH-07-001: SUPERSEDE without ACTIVATE and CANCEL without TERMINATE."""
    with pytest.raises(VultronInvalidStateTransitionError) as excinfo:
        apply_register_step(
            [_entry(A, S.ACTIVE), _entry(B, S.PROPOSED)],
            [_change(A, T.SUPERSEDE), _change(B, T.CANCEL)],
        )
    message = str(excinfo.value)
    assert "SUPERSEDE is legal only" in message
    assert "CANCEL is legal only" in message


@pytest.mark.parametrize(
    "kw",
    [
        {"trigger": T.TERMINATE},
        {"trigger": T.CANCEL, "reason": TerminationReason.EARLY},
    ],
)
def test_a_reason_belongs_to_terminate_alone(kw: dict) -> None:
    with pytest.raises(ValueError, match="reason"):
        RegisterChange(embargo_id=A, **kw)


@pytest.mark.parametrize(
    ("status", "replaces"),
    [(S.PROPOSED, B), (S.REJECTED, B), (S.CANCELLED, B), (S.ACTIVE, A)],
)
def test_an_entry_refuses_a_replaces_its_status_cannot_carry(
    status: S, replaces: str
) -> None:
    with pytest.raises(ValueError, match="replace"):
        _entry(A, status, replaces=replaces)


# ---------------------------------------------------------------------------
# The case: views, derived EM and its stamped copy
# ---------------------------------------------------------------------------


def test_a_new_case_has_an_empty_register_and_em_none() -> None:
    case = _case()
    assert case.embargo_register == []
    assert case.em_state is EM.NONE
    assert case.active_embargo is None
    assert case.proposed_embargo_ids == []


def test_case_views_read_the_register() -> None:
    case = _case()
    propose(case, A)
    assert (case.em_state, case.proposed_embargo_ids) == (EM.PROPOSED, [A])
    activate(case, A)
    assert (case.em_state, case.active_embargo_id) == (EM.ACTIVE, A)
    propose(case, B)
    assert (case.em_state, case.proposed_embargo_ids) == (EM.REVISE, [B])
    activate(case, B)
    assert case.em_state is EM.ACTIVE
    assert case.embargo_register_entry(B).replaces == A  # type: ignore[union-attr]
    terminate(case)
    assert case.em_state is EM.EXITED
    assert case.active_embargo is None
    assert _statuses(case.embargo_register) == {
        A: S.SUPERSEDED,
        B: S.TERMINATED,
    }


@pytest.mark.parametrize("in_force", [False, True])
def test_rejecting_one_of_two_proposals_keeps_em_negotiating(
    in_force: bool,
) -> None:
    """AC-4: the other proposal is still open, so EM does not leave negotiation."""
    case = _case()
    if in_force:
        propose(case, A)
        activate(case, A)
    propose(case, B)
    propose(case, C)

    reject(case, B)

    assert case.em_state is (EM.REVISE if in_force else EM.PROPOSED)
    assert case.proposed_embargo_ids == [C]


def test_threat_signal_with_no_embargo_in_force_cancels_proposals() -> None:
    """AC-5: the proposals are cancelled, not rejected (EMB-16-001)."""
    case = _case()
    propose(case, A)
    propose(case, B)
    cancel_on_threat(case, A, B)
    assert _statuses(case.embargo_register) == {
        A: S.CANCELLED,
        B: S.CANCELLED,
    }
    assert case.em_state is EM.NONE


def test_threat_signal_with_an_embargo_in_force_terminates_it() -> None:
    case = _case()
    propose(case, A)
    activate(case, A)
    propose(case, B)
    terminate(case, TerminationReason.THREAT_SIGNAL)
    assert _statuses(case.embargo_register) == {
        A: S.TERMINATED,
        B: S.CANCELLED,
    }
    assert case.em_state is EM.EXITED


def test_a_refused_step_leaves_the_case_untouched() -> None:
    case = _case()
    propose(case, A)
    activate(case, A)
    terminate(case)
    before = case.model_dump()
    with pytest.raises(VultronInvalidStateTransitionError):
        propose(case, B)
    assert case.model_dump() == before


def test_a_decided_proposal_leaves_the_relay_index() -> None:
    """EP-08-003: the relay record leaves with the proposal."""
    case = _case()
    propose(case, A)
    propose(case, B)
    case.pending_embargo_proposal_index = {
        A: "urn:invite:a",
        B: "urn:invite:b",
    }
    activate(case, A)
    assert case.pending_embargo_proposal_index == {B: "urn:invite:b"}


def test_every_register_step_stamps_the_current_status() -> None:
    case = _case()
    for step, em in [
        (lambda: propose(case, A), EM.PROPOSED),
        (lambda: activate(case, A), EM.ACTIVE),
        (lambda: propose(case, B), EM.REVISE),
        (lambda: reject(case, B), EM.ACTIVE),
        (lambda: terminate(case), EM.EXITED),
    ]:
        step()
        assert case.current_status.em.state is em


def test_an_appended_status_cannot_carry_another_em() -> None:
    case = _case()
    propose(case, A)
    case.add_case_status(
        CaseStatus(
            context=CASE_ID,
            attributed_to=OWNER,
            em=EmDimension(state=EM.EXITED),
            published=now_utc() + timedelta(seconds=1),
        )
    )
    assert case.current_status.em.state is EM.PROPOSED


def test_append_case_status_refuses_an_em_state() -> None:
    case = _case()
    with pytest.raises(VultronValidationError, match="register"):
        case.append_case_status(em_state=EM.ACTIVE)


def test_construction_stamps_the_register_em_onto_the_status() -> None:
    """A received or stored case's status copy never disagrees (ADR-0122)."""
    case = _case(
        embargo_register=[_entry(A, S.ACTIVE)],
        case_statuses=[
            CaseStatus(
                context=CASE_ID,
                attributed_to=OWNER,
                em=EmDimension(state=EM.NONE),
            )
        ],
    )
    assert case.current_status.em.state is EM.ACTIVE


@pytest.mark.parametrize(
    "entries",
    [
        [_entry(A, S.ACTIVE), _entry(B, S.ACTIVE)],
        [_entry(A, S.TERMINATED), _entry(B, S.PROPOSED)],
        [_entry(A, S.PROPOSED), _entry(A, S.PROPOSED)],
    ],
    ids=["two-active", "proposed-after-terminated", "repeated-id"],
)
def test_construction_refuses_an_impossible_register(
    entries: list[EmbargoRegisterEntry],
) -> None:
    with pytest.raises(ValueError, match="embargo register"):
        _case(embargo_register=entries)


def test_a_retired_stored_field_is_refused() -> None:
    with pytest.raises(ValueError):
        VulnerabilityCase.model_validate(
            {"id": CASE_ID, "attributedTo": OWNER, "activeEmbargo": A}
        )


def test_the_active_view_returns_an_inline_embargo_object() -> None:
    embargo = EmbargoEvent(
        id_=A, context=CASE_ID, end_time=now_utc() + timedelta(days=3)
    )
    case = _case()
    propose(case, embargo)
    activate(case, A)
    assert case.active_embargo == embargo
    assert case.active_embargo_id == A


def test_carry_embargo_inline_swaps_only_the_named_entry() -> None:
    embargo = EmbargoEvent(
        id_=A, context=CASE_ID, end_time=now_utc() + timedelta(days=3)
    )
    entries = [_entry(A, S.ACTIVE), _entry(B, S.PROPOSED)]
    carried = carry_embargo_inline(entries, embargo)
    assert carried[0].embargo == embargo
    assert carried[0].status is S.ACTIVE
    assert carried[1] == entries[1]


def test_the_register_round_trips_through_its_wire_spelling() -> None:
    case = _case()
    propose(case, A)
    activate(case, A)
    propose(case, B)
    activate(case, B)
    dumped = case.model_dump(mode="json", by_alias=True)
    assert dumped["embargoRegister"][1] == {
        "embargo": B,
        "status": "ACTIVE",
        "replaces": A,
    }
    restored = VulnerabilityCase.model_validate(dumped)
    assert restored.embargo_register == case.embargo_register
    assert restored.em_state is EM.ACTIVE
