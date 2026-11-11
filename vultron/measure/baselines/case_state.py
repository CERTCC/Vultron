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

"""The indifference walk over the six-event case-state model (ADR-0182).

The model is the CS transition rules of CSB-17 as
:mod:`vultron.core.states.cs_invariants` states them: from ``vfdpxa``, each
event that :func:`~vultron.core.states.cs_invariants.next_cs_states` allows
next is equally likely, and the walk ends at ``VFDPXA``.  It has no cycle, so
it has exactly the 70 valid histories, and a history's probability is the
product of ``1 / (number of allowed events)`` along it.

Two kinds of reader use it:

* the twelve original desiderata take their chance frequency from it through
  :func:`vultron.measure.baselines.walk.frequency`, the same computation the
  joint models use (:data:`CASE_STATE_MODEL`);
* a scorer of an incomplete sequence weights each completion by the walk's
  probability from where the case stands (ADR-0182, on scoring an
  incomplete sequence through its completions), which is
  :func:`completion_probabilities`.
"""

from collections.abc import Sequence
from fractions import Fraction

from vultron.core.states.cs import CS
from vultron.core.states.cs_invariants import (
    CSEvent,
    apply_cs_event,
    cs_transition_event,
    ensure_valid_cs_history,
    next_cs_states,
    replay_cs_history,
)
from vultron.measure.baselines.walk import Step

START = CS.vfdpxa
"""The state every case-state history starts in."""


class CaseStateModel:
    """The six-event CS model as a :class:`~vultron.measure.baselines.walk.ChanceModel`."""

    @property
    def initial(self) -> CS:
        return START

    def steps(self, state: CS) -> tuple[Step[CS, CSEvent], ...]:
        found = []
        for dest in next_cs_states(state):
            event = cs_transition_event(state, dest)
            # next_cs_states only returns one-event moves.
            assert event is not None
            found.append(Step(event, dest))
        return tuple(found)


CASE_STATE_MODEL = CaseStateModel()
"""The one instance every reader shares; the model holds no state of its own."""


def step_probability(state: CS, event: CSEvent | str) -> Fraction:
    """The probability the walk takes *event* from *state*.

    Raises:
        VultronInvalidStateTransitionError: *event* is not allowed from
            *state*.
    """
    apply_cs_event(state, event)
    return Fraction(1, len(next_cs_states(state)))


def history_probability(events: Sequence[CSEvent | str]) -> Fraction:
    """The probability the walk produces the complete history *events*.

    Raises:
        VultronValidationError, VultronInvalidStateTransitionError: *events*
            is not one of the 70 valid histories.
    """
    ensure_valid_cs_history(events)
    return prefix_probability(events)


def prefix_probability(events: Sequence[CSEvent | str]) -> Fraction:
    """The probability that a walk's history starts with *events*.

    The empty prefix has probability 1.

    Raises:
        VultronValidationError, VultronInvalidStateTransitionError: *events*
            is not a valid history prefix.
    """
    replay_cs_history(events)
    probability = Fraction(1)
    state = START
    for event in events:
        probability *= step_probability(state, event)
        state = apply_cs_event(state, event)
    return probability


def completion_probabilities(
    prefix: Sequence[CSEvent | str] = (),
) -> dict[tuple[CSEvent, ...], Fraction]:
    """Every complete history that extends *prefix*, with its probability given *prefix*.

    The keys are whole histories (prefix included), and the values sum to 1:
    each is the walk's probability of the completion from the state *prefix*
    reaches.  A complete *prefix* has itself as its only completion.

    Raises:
        VultronValidationError, VultronInvalidStateTransitionError: *prefix*
            is not a valid history prefix.
    """
    state = replay_cs_history(prefix)
    start = tuple(CSEvent(e) for e in prefix)
    found: dict[tuple[CSEvent, ...], Fraction] = {}
    pending: list[tuple[CS, tuple[CSEvent, ...], Fraction]] = [
        (state, start, Fraction(1))
    ]
    while pending:
        here, history, probability = pending.pop()
        steps = CASE_STATE_MODEL.steps(here)
        if not steps:
            found[history] = probability
            continue
        share = probability / len(steps)
        for step in steps:
            pending.append((step.state, (*history, step.event), share))
    return found
