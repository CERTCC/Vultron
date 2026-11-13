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
"""The moves the state machines allow from where a case stands (ADR-0190).

A move is allowed when its own machine's table holds it and the state it
reaches breaks none of the composite invariants that join the machines.
Every rule is read from :mod:`vultron.core.states`, never restated here:

* **RM** moves follow the RM transition table
  (:func:`~vultron.core.states.rm.is_valid_rm_transition`), and the reached
  report-management state must agree with the participant's fix path
  (:func:`~vultron.core.states.composite_state_invariants\
.composite_state_violations`, CSB-18-001).
* **CS** moves are one case-state event each, from the compound state
  (:func:`~vultron.core.states.cs_invariants.next_cs_states`, CSB-17), and
  the reached fix path must agree with the report-management state the same
  way.  A public-state move is allowed beside an embargo in force: it ends
  the embargo, it is not refused by it.
* **EM** moves follow the one EM table
  (:data:`~vultron.core.states.em.EM_TRANSITIONS`, EMB-18-006), except a
  move to an embargo in force while the public state rules one out
  (:func:`~vultron.core.states.composite_state_invariants\
.violation_pxa_em_entailment`, CSB-18-002 to CSB-18-004).

Each move is typed by its machine and refuses, at construction, a step its
machine's table does not hold.  A :class:`CSMove` names the case-state event
it appends, so a measure can score the history the move would extend
(:meth:`CSMove.extend`).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Annotated

from pydantic import BaseModel, ConfigDict, PlainSerializer, model_validator

from vultron.core.states.composite_state_invariants import (
    composite_state_violations,
    violation_pxa_em_entailment,
)
from vultron.core.states.cs import CS, CS_d, CS_pxa, CS_vf
from vultron.core.states.cs_invariants import (
    CSEvent,
    cs_dimensions,
    cs_transition_event,
    is_valid_cs_transition,
    next_cs_states,
    replay_cs_history,
)
from vultron.core.states.em import (
    EM,
    EM_TRANSITIONS,
    EM_Trigger,
    is_em_transition,
)
from vultron.core.states.rm import RM, is_valid_rm_transition

#: A compound case state, serialized by its ``vfdpxa`` notation (``CS``
#: values are tuples, which say nothing to a reader).
CSName = Annotated[
    CS, PlainSerializer(lambda state: state.name, return_type=str)
]


class RMMove(BaseModel):
    """One report-management move a participant can make from here.

    Fields:
        source: The participant's report-management state now.
        destination: The state the move reaches.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: RM
    destination: RM

    @model_validator(mode="after")
    def _is_an_rm_transition(self) -> RMMove:
        if not is_valid_rm_transition(self.source, self.destination):
            raise ValueError(
                f"RM {self.source} -> {self.destination} is not an RM"
                " transition"
            )
        return self


class CSMove(BaseModel):
    """One case-state event a participant's case can take next.

    Fields:
        event: The case-state event the move appends to the history.
        source: The participant's compound case state now.
        destination: The compound state the event reaches.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    event: CSEvent
    source: CSName
    destination: CSName

    @model_validator(mode="after")
    def _is_the_events_cs_transition(self) -> CSMove:
        problems: list[str] = []
        if not is_valid_cs_transition(self.source, self.destination):
            problems.append(
                f"CS {self.source.name} -> {self.destination.name} is not a"
                " CS transition"
            )
        if cs_transition_event(self.source, self.destination) != self.event:
            problems.append(
                f"{self.source.name} -> {self.destination.name} is not the"
                f" event {self.event}"
            )
        if problems:
            raise ValueError("; ".join(problems))
        return self

    def extend(self, prefix: Iterable[CSEvent | str]) -> tuple[CSEvent, ...]:
        """*prefix* with this move's event appended.

        Raises:
            ValueError: *prefix* does not replay to this move's source state,
                so the move is not one of its next events.
            VultronValidationError, VultronInvalidStateTransitionError:
                *prefix* is not a case-state history prefix.
        """
        events = tuple(CSEvent(event) for event in prefix)
        reached = replay_cs_history(events)
        if reached is not self.source:
            raise ValueError(
                f"{''.join(events)} reaches {reached.name}, not this move's"
                f" source {self.source.name}"
            )
        return (*events, self.event)


class EMMove(BaseModel):
    """One embargo-management move the case can make from here.

    Fields:
        trigger: The EM trigger of the register step.
        source: The case's EM state now.
        destination: The state the step reaches.  Where the table gives one
            trigger two destinations, which one a step reaches depends on
            the proposals left open (EMB-18-005); both are listed.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    trigger: EM_Trigger
    source: EM
    destination: EM

    @model_validator(mode="after")
    def _is_an_em_transition(self) -> EMMove:
        if not is_em_transition(self.trigger, self.source, self.destination):
            raise ValueError(
                f"EM {self.trigger}: {self.source} -> {self.destination} is"
                " not in the EM transition table"
            )
        return self


def rm_moves(rm: RM, vf: CS_vf | None, d: CS_d | None) -> tuple[RMMove, ...]:
    """The report-management moves allowed from *rm*, in RM order.

    *vf* and *d* are the participant's fix path, or ``None`` when it has no
    case state, which asserts nothing (``composite_state_violations``).
    """
    return tuple(
        RMMove(source=rm, destination=dest)
        for dest in RM
        if is_valid_rm_transition(rm, dest)
        and not composite_state_violations(dest, vf, d)
    )


def cs_moves(state: CS, rm: RM) -> tuple[CSMove, ...]:
    """The case-state events allowed from *state*, in event order."""
    found = []
    for dest in next_cs_states(state):
        vf, d, _ = cs_dimensions(dest)
        event = cs_transition_event(state, dest)
        if event is not None and not composite_state_violations(rm, vf, d):
            found.append(CSMove(event=event, source=state, destination=dest))
    order = list(CSEvent)
    return tuple(sorted(found, key=lambda move: order.index(move.event)))


def em_moves(em: EM, pxa: CS_pxa) -> tuple[EMMove, ...]:
    """The EM moves allowed from *em* beside the public state *pxa*.

    In table order, then by destination as :class:`EM` orders them.
    """
    order = list(EM)
    return tuple(
        EMMove(trigger=trigger, source=source, destination=dest)
        for trigger, steps in EM_TRANSITIONS.items()
        for source, dest in sorted(steps, key=lambda s: order.index(s[1]))
        if source is em and violation_pxa_em_entailment(pxa, dest) is None
    )
