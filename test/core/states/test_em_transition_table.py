"""The embargo register moves EM only along the EM transitions (ADR-0130).

EM is computed from the register (ADR-0122), under the EM state machine: every
register step names an EM trigger, and EM before and after the step must be
one of that trigger's transitions.
"""

from collections.abc import Iterator, Sequence

import pytest

from vultron.core.models import embargo_register as embargo_register_module
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_register import (
    _EM_TRIGGER_OF,
    EmbargoRegisterEntry,
    RegisterChange,
    activation_changes,
    apply_register_step,
    em_move_violations,
    proposal_changes,
    register_step_em_trigger,
    rejection_changes,
    termination_changes,
)
from vultron.core.states import em as em_module
from vultron.core.states.em import (
    EM,
    EM_TRANSITIONS,
    EM_Trigger,
    create_em_machine,
    em_transition_rows,
    is_em_transition,
)
from vultron.core.states.embargo_register import (
    EmbargoRegisterStatus,
    RegisterTrigger,
    TerminationReason,
    derive_em,
)
from vultron.errors import VultronInvalidStateTransitionError

S = EmbargoRegisterStatus

# ADR-0130's table as the ADR writes it: trigger -> {(source, destination)}.
# Only EMB-18-006 reads it, to pin the production table to the ADR; every
# other test reads ``vultron.core.states.em.EM_TRANSITIONS``.
ADR_0130_TABLE: dict[str, frozenset[tuple[EM, EM]]] = {
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
Step = tuple[EM_Trigger, list[RegisterChange], bool]


def _em(register: Sequence[EmbargoRegisterEntry]) -> EM:
    return derive_em(entry.status for entry in register)


def _ids(register: Register, status: S) -> list[str]:
    return [e.embargo_id for e in register if e.status == status]


def _steps(register: Register) -> Iterator[Step]:
    """Every register step the lifecycle can take, with its EM trigger."""
    if _ids(register, S.TERMINATED):
        return  # invariant 4: a terminated register takes no further step
    if len(register) < len(_IDS):
        yield EM_Trigger.PROPOSE, proposal_changes(_IDS[len(register)]), False
    for embargo_id in _ids(register, S.PROPOSED):
        yield (
            EM_Trigger.ACCEPT,
            activation_changes(register, embargo_id),
            False,
        )
        yield EM_Trigger.REJECT, rejection_changes(embargo_id), False
    if _ids(register, S.ACTIVE):
        yield (
            EM_Trigger.TERMINATE,
            termination_changes(register, TerminationReason.EARLY),
            False,
        )
    elif _ids(register, S.PROPOSED):
        # A threat signal with no embargo in force abandons the named open
        # proposals (EMB-16-001), which is an ER: the EM trigger is
        # ``reject``.  It may name every open proposal or only some of them.
        cancel = termination_changes(register, TerminationReason.EARLY)
        yield EM_Trigger.REJECT, cancel, True
        if len(cancel) > 1:
            for embargo_id in _ids(register, S.PROPOSED):
                one = RegisterChange(
                    embargo_id=embargo_id, trigger=RegisterTrigger.CANCEL
                )
                yield EM_Trigger.REJECT, [one], True


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
    moves_seen: set[tuple[EM_Trigger, EM, EM]] = set()
    for register in _reachable():
        for trigger, changes, threat in _steps(register):
            assert register_step_em_trigger(changes) is trigger
            after = apply_register_step(
                register, changes, threat_signal=threat
            )
            move = (_em(register), _em(after))
            assert is_em_transition(trigger, *move), (
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


@pytest.mark.spec("EMB-18-006")
def test_em_transition_table_is_declared_and_enforced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert {
        str(trigger): frozenset(moves)
        for trigger, moves in EM_TRANSITIONS.items()
    } == ADR_0130_TABLE

    # With ``propose: NONE -> PROPOSED`` withdrawn, the register refuses the
    # first proposal: the step is checked against the table, not just tested.
    # This relies on the register step reading ``em.EM_TRANSITIONS`` at call
    # time, not binding the name at import.
    narrowed = {
        trigger: frozenset(m for m in moves if m != (EM.NONE, EM.PROPOSED))
        for trigger, moves in EM_TRANSITIONS.items()
    }
    monkeypatch.setattr(em_module, "EM_TRANSITIONS", narrowed)
    with pytest.raises(
        VultronInvalidStateTransitionError, match="not an EM transition"
    ):
        apply_register_step([], proposal_changes("urn:em:e1"))


@pytest.mark.spec("EMB-18-005")
@pytest.mark.parametrize(
    ("trigger", "source", "dest", "legal"),
    [
        (EM_Trigger.PROPOSE, EM.NONE, EM.PROPOSED, True),
        (EM_Trigger.ACCEPT, EM.PROPOSED, EM.REVISE, True),
        (EM_Trigger.REJECT, EM.REVISE, EM.REVISE, True),
        (EM_Trigger.TERMINATE, EM.REVISE, EM.EXITED, True),
        (EM_Trigger.REJECT, EM.ACTIVE, EM.NONE, False),
        (EM_Trigger.TERMINATE, EM.PROPOSED, EM.EXITED, False),
        (EM_Trigger.ACCEPT, EM.NONE, EM.ACTIVE, False),
        (EM_Trigger.PROPOSE, EM.EXITED, EM.PROPOSED, False),
    ],
)
def test_is_em_transition_answers_from_the_table(
    trigger: EM_Trigger, source: EM, dest: EM, legal: bool
) -> None:
    assert is_em_transition(trigger, source, dest) is legal


@pytest.mark.spec("EMB-18-005")
@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        (proposal_changes("a"), EM_Trigger.PROPOSE),
        (
            [
                RegisterChange(
                    embargo_id="b", trigger=RegisterTrigger.ACTIVATE
                ),
                RegisterChange(
                    embargo_id="a", trigger=RegisterTrigger.SUPERSEDE
                ),
            ],
            EM_Trigger.ACCEPT,
        ),
        (rejection_changes("a"), EM_Trigger.REJECT),
        (
            [
                RegisterChange(
                    embargo_id="a",
                    trigger=RegisterTrigger.TERMINATE,
                    reason=TerminationReason.EARLY,
                ),
                RegisterChange(embargo_id="b", trigger=RegisterTrigger.CANCEL),
            ],
            EM_Trigger.TERMINATE,
        ),
        (
            [RegisterChange(embargo_id="b", trigger=RegisterTrigger.CANCEL)],
            EM_Trigger.REJECT,
        ),
    ],
)
def test_each_register_step_names_its_em_trigger(
    changes: list[RegisterChange], expected: EM_Trigger
) -> None:
    assert register_step_em_trigger(changes) is expected


@pytest.mark.spec("EMB-18-005")
@pytest.mark.parametrize(
    ("open_proposals", "changes", "threat_signal"),
    [
        ((), [], False),
        (("a",), [*proposal_changes("b"), *rejection_changes("a")], False),
        # Every other step rule admits this on a threat signal with no
        # embargo in force; only its two EM triggers refuse it.
        (
            ("a", "b"),
            [
                RegisterChange(
                    embargo_id="a", trigger=RegisterTrigger.ACTIVATE
                ),
                RegisterChange(embargo_id="b", trigger=RegisterTrigger.CANCEL),
            ],
            True,
        ),
    ],
    ids=["empty", "propose-and-reject", "activate-and-cancel"],
)
def test_a_step_naming_no_single_em_trigger_is_refused(
    open_proposals: tuple[str, ...],
    changes: list[RegisterChange],
    threat_signal: bool,
) -> None:
    register = _register_after(*(f"propose:{i}" for i in open_proposals))
    with pytest.raises(
        VultronInvalidStateTransitionError, match="exactly one EM trigger"
    ):
        register_step_em_trigger(changes)
    with pytest.raises(
        VultronInvalidStateTransitionError, match="exactly one EM trigger"
    ):
        apply_register_step(register, changes, threat_signal=threat_signal)


@pytest.mark.spec("EMB-18-006")
def test_a_refused_em_move_leaves_the_case_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A refused EM move writes nothing: not the register, not the stamped
    EM, not the relay index, not an inline participant's consent rows."""
    case_id = "https://example.org/cases/c1"
    owner = "https://example.org/actors/owner"
    participant = CaseParticipant(
        id_=f"{case_id}/participants/p1", attributed_to=owner, context=case_id
    )
    case = VulnerabilityCase(
        id_=case_id, attributed_to=owner, case_participants=[participant]
    )
    case.apply_embargo_register_step(proposal_changes("urn:em:a"))
    case.pending_embargo_proposal_index = {"urn:em:a": "urn:invite:a"}
    before = case.model_dump()
    narrowed = {
        trigger: frozenset(m for m in moves if m != (EM.PROPOSED, EM.ACTIVE))
        for trigger, moves in EM_TRANSITIONS.items()
    }
    monkeypatch.setattr(em_module, "EM_TRANSITIONS", narrowed)
    with pytest.raises(
        VultronInvalidStateTransitionError,
        match="EM PROPOSED → ACTIVE is not an EM transition for 'accept'",
    ):
        case.apply_embargo_register_step(
            activation_changes(case.embargo_register, "urn:em:a")
        )
    assert case.model_dump() == before
    assert case.em_state is EM.PROPOSED


@pytest.mark.spec("EMB-18-005")
def test_every_register_trigger_maps_to_an_em_trigger() -> None:
    """``CANCEL`` aside, every register trigger has an EM trigger, so a step
    never falls through the mapping (ADR-0130)."""
    assert set(_EM_TRIGGER_OF) | {RegisterTrigger.CANCEL} == set(
        RegisterTrigger
    )


@pytest.mark.spec("EMB-18-005")
def test_an_unmapped_register_trigger_is_a_domain_refusal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        embargo_register_module,
        "_EM_TRIGGER_OF",
        {
            t: e
            for t, e in _EM_TRIGGER_OF.items()
            if t is not RegisterTrigger.PROPOSE
        },
    )
    with pytest.raises(
        VultronInvalidStateTransitionError, match="no EM trigger is mapped"
    ):
        apply_register_step([], proposal_changes("urn:em:e1"))


@pytest.mark.spec("EMB-18-006")
def test_em_move_violations_names_the_illegal_move() -> None:
    active = _register_after("propose:a", "accept:a")
    assert em_move_violations([], active, EM_Trigger.ACCEPT) == [
        "EM NONE → ACTIVE is not an EM transition for 'accept' (ADR-0130)"
    ]
    assert (
        em_move_violations(
            _register_after("propose:a"), active, EM_Trigger.ACCEPT
        )
        == []
    )


@pytest.mark.spec("EMB-18-006")
def test_the_em_machine_is_built_from_the_table() -> None:
    rows = em_transition_rows()
    assert {(r["trigger"], r["source"], r["dest"]) for r in rows} == {
        (str(trigger), str(src), str(dst))
        for trigger, moves in EM_TRANSITIONS.items()
        for src, dst in moves
    }
    assert len(rows) == sum(len(m) for m in EM_TRANSITIONS.values())
    assert rows == em_transition_rows()  # deterministic order for exports

    machine = create_em_machine()
    assert machine.initial == str(EM.NONE)
    exported = {
        (trigger, t.source, t.dest)
        for trigger in machine.events
        for t in machine.get_transitions(trigger=trigger)
    }
    assert exported == {(r["trigger"], r["source"], r["dest"]) for r in rows}
