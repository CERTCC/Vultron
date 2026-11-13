#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""The moves the state machines allow from a standing (ADR-0190)."""

import pytest
from pydantic import ValidationError

from vultron.core.states.cs import CS, CS_d, CS_pxa, CS_vf
from vultron.core.states.cs_invariants import (
    CSEvent,
    cs_transition_event,
    next_cs_states,
)
from vultron.core.states.em import (
    EM,
    EM_TRANSITIONS,
    EM_Trigger,
)
from vultron.core.states.rm import RM, RM_Trigger, is_valid_rm_transition
from vultron.errors import VultronInvalidStateTransitionError
from vultron.measure.scoring import score_prefix
from vultron.measure.standing import (
    CSMove,
    EMMove,
    RMMove,
    cs_moves,
    em_moves,
    rm_moves,
)
from vultron.measure.standing.moves import CS_TRIGGERS
from vultron.wire.as2.enums import (
    as_IntransitiveActivityType,
    as_ObjectType,
    as_TransitiveActivityType,
)

_T = EM_Trigger
_P = "https://example.org/actors/vendor"


@pytest.mark.parametrize("rm", list(RM))
def test_with_no_case_state_the_rm_moves_are_the_rm_table(rm):
    assert [m.destination for m in rm_moves(_P, rm, None, None)] == [
        dest for dest in RM if is_valid_rm_transition(rm, dest)
    ]


@pytest.mark.spec("CSB-18-001")
def test_an_rm_move_that_would_leave_a_ready_fix_unaccepted_is_not_allowed():
    """A ready fix needs the report Accepted, Deferred or Closed."""
    assert [
        m.destination for m in rm_moves(_P, RM.RECEIVED, CS_vf.VF, CS_d.d)
    ] == [RM.CLOSED]
    assert rm_moves(_P, RM.START, CS_vf.Vf, CS_d.d) == (
        RMMove(participant=_P, source=RM.START, destination=RM.RECEIVED),
    )


@pytest.mark.parametrize("state", list(CS))
def test_with_an_accepted_report_the_cs_moves_are_the_cs_machines(state):
    assert [m.destination for m in cs_moves(_P, state, RM.ACCEPTED)] == sorted(
        next_cs_states(state),
        key=lambda dest: list(CSEvent).index(cs_transition_event(state, dest)),
    )


@pytest.mark.spec("CSB-18-001")
def test_a_fix_is_not_allowed_ready_before_the_report_is_accepted():
    assert [m.event for m in cs_moves(_P, CS.Vfdpxa, RM.RECEIVED)] == [
        CSEvent.P,
        CSEvent.X,
        CSEvent.A,
    ]
    assert [m.event for m in cs_moves(_P, CS.Vfdpxa, RM.ACCEPTED)] == [
        CSEvent.F,
        CSEvent.P,
        CSEvent.X,
        CSEvent.A,
    ]


@pytest.mark.spec("CSB-17-009")
@pytest.mark.spec("CSB-17-012")
def test_an_ephemeral_state_allows_only_its_forced_event():
    assert [m.event for m in cs_moves(_P, CS.vfdPxa, RM.START)] == [CSEvent.V]
    assert [m.event for m in cs_moves(_P, CS.VfdpXa, RM.ACCEPTED)] == [
        CSEvent.P
    ]


def test_a_complete_history_allows_no_cs_move():
    assert cs_moves(_P, CS.VFDPXA, RM.CLOSED) == ()


@pytest.mark.spec("EMB-18-006")
@pytest.mark.parametrize("em", list(EM))
def test_with_the_public_unaware_the_em_moves_are_the_em_table(em):
    assert {(m.trigger, m.destination) for m in em_moves(em, CS_pxa.pxa)} == {
        (trigger, dest)
        for trigger, steps in EM_TRANSITIONS.items()
        for source, dest in steps
        if source is em
    }


@pytest.mark.spec("CSB-18-002")
def test_no_embargo_goes_into_force_beside_public_awareness():
    assert [
        (m.trigger, m.destination) for m in em_moves(EM.ACTIVE, CS_pxa.Pxa)
    ] == [(_T.TERMINATE, EM.EXITED)]
    assert [
        (m.trigger, m.destination) for m in em_moves(EM.PROPOSED, CS_pxa.pXa)
    ] == [
        (_T.PROPOSE, EM.PROPOSED),
        (_T.REJECT, EM.NONE),
        (_T.REJECT, EM.PROPOSED),
    ]


def test_an_exited_embargo_allows_no_em_move():
    assert em_moves(EM.EXITED, CS_pxa.pxa) == ()


def test_a_move_its_table_does_not_hold_is_refused():
    with pytest.raises(ValidationError, match="not an RM transition"):
        RMMove(participant=_P, source=RM.START, destination=RM.CLOSED)
    with pytest.raises(ValidationError, match="not in the EM transition"):
        EMMove(trigger=_T.ACCEPT, source=EM.NONE, destination=EM.ACTIVE)
    with pytest.raises(ValidationError, match="not a CS transition"):
        CSMove(
            participant=_P,
            event=CSEvent.F,
            source=CS.vfdpxa,
            destination=CS.VFdpxa,
        )


def test_a_cs_move_must_name_the_event_it_takes():
    with pytest.raises(ValidationError, match="is not the event"):
        CSMove(
            participant=_P,
            event=CSEvent.P,
            source=CS.vfdpxa,
            destination=CS.Vfdpxa,
        )


def test_a_cs_move_serializes_its_states_by_notation():
    move = CSMove(
        participant=_P,
        event=CSEvent.V,
        source=CS.vfdpxa,
        destination=CS.Vfdpxa,
    )
    assert move.model_dump(mode="json") == {
        "participant": _P,
        "event": "V",
        "source": "vfdpxa",
        "destination": "Vfdpxa",
        "trigger": "vendor_becomes_aware",
        "name": "cs.vendor_becomes_aware",
    }


def test_a_cs_move_extends_a_prefix_into_one_a_measure_can_score():
    """What #6369 ranks: the history extended by one allowed move."""
    (move,) = [
        m for m in cs_moves(_P, CS.Vfdpxa, RM.ACCEPTED) if m.event == "F"
    ]
    extended = move.extend("V")
    assert extended == (CSEvent.V, CSEvent.F)
    assert score_prefix(extended).prefix == extended


def test_a_cs_move_refuses_a_prefix_that_does_not_reach_its_source():
    move = CSMove(
        participant=_P,
        event=CSEvent.F,
        source=CS.Vfdpxa,
        destination=CS.VFdpxa,
    )
    with pytest.raises(ValueError, match="not this move's source"):
        move.extend("VP")
    with pytest.raises(VultronInvalidStateTransitionError):
        move.extend("F")


def _every_move() -> list[RMMove | CSMove | EMMove]:
    moves: list[RMMove | CSMove | EMMove] = []
    for rm in RM:
        moves += rm_moves(_P, rm, None, None)
        for state in CS:
            moves += cs_moves(_P, state, rm)
    for em in EM:
        for pxa in CS_pxa:
            moves += em_moves(em, pxa)
    return moves


def test_every_move_is_named_by_its_machine_and_trigger():
    """AC-5 (#6368): a move's name is its machine's trigger."""
    for move in _every_move():
        machine, trigger = move.name.split(".")
        assert trigger == str(move.trigger)
        assert machine == type(move).__name__[:2].lower()


def test_no_move_is_named_by_an_as2_type():
    """AC-5 (#6368): never by a wire activity or object type."""
    as2_types = {
        str(member).lower()
        for enum in (
            as_ObjectType,
            as_IntransitiveActivityType,
            as_TransitiveActivityType,
        )
        for member in enum
    }
    names = {move.name for move in _every_move()}
    assert names == {
        *(f"rm.{t}" for t in RM_Trigger),
        *(f"cs.{t}" for t in CS_TRIGGERS.values()),
        *(f"em.{t}" for t in EM_Trigger),
    }
    assert {name.lower() for name in names}.isdisjoint(as2_types)


def test_an_rm_move_names_its_trigger():
    (move,) = rm_moves(_P, RM.START, None, None)
    assert (move.trigger, move.name) == (RM_Trigger.RECEIVE, "rm.receive")
    assert move.participant == _P
