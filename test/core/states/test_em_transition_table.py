"""The embargo register moves EM only along the EM transitions (ADR-0130).

EM is computed from the register (ADR-0122), under the EM state machine: every
register step names an EM trigger, and EM before and after the step must be
one of that trigger's transitions.
"""

from collections.abc import Iterator, Sequence

import pytest

from vultron.core.models.embargo_register import (
    EmbargoRegisterEntry,
    RegisterChange,
    activation_changes,
    apply_register_step,
    proposal_changes,
    rejection_changes,
    termination_changes,
)
from vultron.core.states.em import EM
from vultron.core.states.embargo_register import (
    EmbargoRegisterStatus,
    TerminationReason,
    derive_em,
)

S = EmbargoRegisterStatus

# ADR-0130's table: trigger -> {(source, destination)}.  #4449 moves it into
# ``vultron.core.states.em``; this copy then gives way to the production one.
EM_TRANSITIONS: dict[str, frozenset[tuple[EM, EM]]] = {
    "propose": frozenset(
        {
            (EM.NONE, EM.PROPOSED),
            (EM.PROPOSED, EM.PROPOSED),
            (EM.ACTIVE, EM.REVISE),
            (EM.REVISE, EM.REVISE),
        }
    ),
    "reject": frozenset(
        {
            (EM.PROPOSED, EM.NONE),
            (EM.PROPOSED, EM.PROPOSED),
            (EM.REVISE, EM.ACTIVE),
            (EM.REVISE, EM.REVISE),
        }
    ),
    "accept": frozenset(
        {
            (EM.PROPOSED, EM.ACTIVE),
            (EM.PROPOSED, EM.REVISE),
            (EM.REVISE, EM.ACTIVE),
            (EM.REVISE, EM.REVISE),
        }
    ),
    "terminate": frozenset({(EM.ACTIVE, EM.EXITED), (EM.REVISE, EM.EXITED)}),
}

_IDS = ("urn:em:e1", "urn:em:e2", "urn:em:e3")

Register = tuple[EmbargoRegisterEntry, ...]
Step = tuple[str, list[RegisterChange], bool]


def _em(register: Sequence[EmbargoRegisterEntry]) -> EM:
    return derive_em(entry.status for entry in register)


def _ids(register: Register, status: S) -> list[str]:
    return [e.embargo_id for e in register if e.status == status]


def _steps(register: Register) -> Iterator[Step]:
    """Every register step the lifecycle can take, with its EM trigger."""
    if _ids(register, S.TERMINATED):
        return  # invariant 4: a terminated register takes no further step
    if len(register) < len(_IDS):
        yield "propose", proposal_changes(_IDS[len(register)]), False
    for embargo_id in _ids(register, S.PROPOSED):
        yield "accept", activation_changes(register, embargo_id), False
        yield "reject", rejection_changes(embargo_id), False
    if _ids(register, S.ACTIVE):
        yield (
            "terminate",
            termination_changes(register, TerminationReason.EARLY),
            False,
        )
    elif _ids(register, S.PROPOSED):
        # A threat signal with no embargo in force abandons every proposal
        # (EMB-16-001), which is an ER: the EM trigger is ``reject``.
        cancel = termination_changes(register, TerminationReason.EARLY)
        yield "reject", cancel, True


def _reachable() -> list[Register]:
    seen: list[Register] = [()]
    frontier: list[Register] = [()]
    while frontier:
        register = frontier.pop()
        for _, changes, threat in _steps(register):
            after = tuple(
                apply_register_step(register, changes, threat_signal=threat)
            )
            if after not in seen:
                seen.append(after)
                frontier.append(after)
    return seen


@pytest.mark.spec("EMB-18-005")
def test_every_register_step_moves_em_along_an_em_transition() -> None:
    moves_seen: set[tuple[str, EM, EM]] = set()
    for register in _reachable():
        for trigger, changes, threat in _steps(register):
            after = apply_register_step(
                register, changes, threat_signal=threat
            )
            move = (_em(register), _em(after))
            assert move in EM_TRANSITIONS[trigger], (
                f"{trigger}: {move[0]} -> {move[1]} is not an EM transition"
            )
            moves_seen.add((trigger, *move))
    # Every transition in the table is one the register actually makes.
    assert moves_seen == {
        (trigger, src, dst)
        for trigger, moves in EM_TRANSITIONS.items()
        for src, dst in moves
    }


def _register_after(*steps: str) -> list[EmbargoRegisterEntry]:
    register: list[EmbargoRegisterEntry] = []
    for step in steps:
        verb, embargo_id = step.split(":", 1)
        if verb == "propose":
            changes = proposal_changes(embargo_id)
        elif verb == "accept":
            changes = activation_changes(register, embargo_id)
        else:
            changes = rejection_changes(embargo_id)
        register = apply_register_step(register, changes)
    return register


@pytest.mark.spec("EMB-06-001")
def test_a_rejection_returns_em_to_none_only_with_the_last_proposal() -> None:
    two_open = _register_after("propose:a", "propose:b")
    one_rejected = apply_register_step(two_open, rejection_changes("a"))
    assert _em(one_rejected) is EM.PROPOSED
    both_rejected = apply_register_step(one_rejected, rejection_changes("b"))
    assert _em(both_rejected) is EM.NONE


@pytest.mark.spec("EMB-18-005")
def test_activating_one_proposal_leaves_the_others_open_as_revisions() -> None:
    register = _register_after("propose:a", "propose:b", "accept:a")
    assert _em(register) is EM.REVISE
    assert _ids(tuple(register), S.PROPOSED) == ["b"]


@pytest.mark.xfail(
    strict=True,
    reason=(
        "EMB-18-006: the EM transition table is not yet declared in"
        " vultron.core.states.em or checked by the register step."
        " Tracked by #4449."
    ),
)
@pytest.mark.spec("EMB-18-006")
def test_em_transition_table_is_declared_and_enforced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vultron.core.states import em as em_module
    from vultron.errors import VultronInvalidStateTransitionError

    # Read through ``vars`` so the not-yet-declared name type-checks (#4449).
    declared = vars(em_module)["EM_TRANSITIONS"]
    assert {
        str(trigger): frozenset(moves) for trigger, moves in declared.items()
    } == EM_TRANSITIONS

    # With ``propose: NONE -> PROPOSED`` withdrawn, the register refuses the
    # first proposal: the step is checked against the table, not just tested.
    narrowed = {
        trigger: frozenset(m for m in moves if m != (EM.NONE, EM.PROPOSED))
        for trigger, moves in declared.items()
    }
    monkeypatch.setattr(em_module, "EM_TRANSITIONS", narrowed)
    with pytest.raises(VultronInvalidStateTransitionError):
        apply_register_step([], proposal_changes("urn:em:e1"))
