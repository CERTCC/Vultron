#!/usr/bin/env python
#  Copyright (c) 2023 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""
This module provides common Behavior Tree nodes for the Vultron package.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import List, Type

import networkx as nx

from vultron.bt.base.bt_node import ActionNode, ConditionCheck
from vultron.bt.base.composites import FallbackNode
from vultron.bt.base.factory import fallback, sequence
from vultron.bt.base.node_status import NodeStatus

logger = logging.getLogger(__name__)


@dataclass
class EnumStateTransition:
    """
    Represents a transition between two states in an enum-based state machine
    """

    start_states: List[Enum]
    end_state: Enum


def condition_check(
    name: str, desc: str, check_func: callable
) -> Type[ConditionCheck]:
    """Factory method that returns a ConditionCheck object with the given name, description, and function"""

    # name, bases, dict
    cls = type(name, (ConditionCheck,), {})
    cls.__doc__ = desc
    cls.func = check_func
    return cls


def state_in(
    key: str, state: Enum, exc=Type[Exception]
) -> Type[ConditionCheck]:
    def func(self):
        return getattr(self.bb, key) == state

    cls = condition_check(
        f"{key}_in_{state.value}",
        f"""ConditionCheck that returns SUCCESS if the node's blackboard[{key}] == {state}""",
        func,
    )
    return cls


class StateIn(ConditionCheck):
    """ConditionCheck that returns SUCCESS if the node's blackboard[key] == state
    Used as a base class for other StateIn classes like EMinState
    """

    key = None
    state = None

    def func(self):
        return getattr(self.bb, self.key) == self.state


def to_end_state_factory(key: str, state: Enum) -> Type[ActionNode]:
    """Factory method that returns an ActionNode class that updates key to state."""

    class TransitionTo(ActionNode):
        def __init__(self):
            super().__init__()
            self.name = f"{self.__class__.__name__}_{key}_to_{state}"

        def _tick(self, depth=0):
            # remember where we were so we can log the change
            before = getattr(self.bb, key)

            setattr(self.bb, key, state)

            # record this bb in history
            histkey = f"{key}_history"
            history = list(getattr(self.bb, histkey))
            if len(history) == 0 or (history[-1] != state):
                history.append(state)
            setattr(self.bb, histkey, history)

            indent = "  " * (depth)
            logger.debug(f"++{indent}{before} -> {state}")
            return NodeStatus.SUCCESS

    return TransitionTo


def make_check_state(_key: str, _state) -> Type[StateIn]:
    """Factory method that returns a ConditionCheck object which returns SUCCESS if the node's blackboard[key] == state"""

    class CheckState(StateIn):
        f"""ConditionCheck that returns SUCCESS if the node's blackboard[{_key}] == {_state}"""
        key = _key
        state = _state

        def __init__(self):
            super().__init__()
            self.name = f"{self.__class__.__name__}_{_key}_in_{_state}"

    return CheckState


def make_state_change(
    key: str, transition: EnumStateTransition
) -> Type[FallbackNode]:
    """Factory method that returns a FallbackNode object that returns SUCCESS when the blackboard[key]
    starts in one of start_states and changes to end_state, and FAILURE otherwise
    """
    start_states = transition.start_states
    end_state = transition.end_state

    start_state_checks = fallback(
        f"StartStateChecks_{key}_{end_state}",
        f"""SUCCESS when the current {key} is in one of {(s.name for s in start_states)}. FAILURE otherwise.""",
        *[make_check_state(key, state) for state in start_states],
    )

    sc_seq = sequence(
        f"ScSeq_{key}_{end_state}",
        f"""Check for a valid start state in {(s.name for s in start_states)} and transition to {end_state}""",
        start_state_checks,
        to_end_state_factory(key, end_state),
    )

    state_change = fallback(
        f"StateChange_{key}_{end_state}",
        f"""Transition from (one of) {(s.name for s in start_states)} to {end_state}""",
        make_check_state(key, end_state),
        sc_seq,
    )

    return state_change


def show_graph(node_cls):
    nx.write_network_text(node_cls().to_graph())
