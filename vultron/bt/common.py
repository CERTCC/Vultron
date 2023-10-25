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

from vultron.bt.base.bt_node import ActionNode, BtNode, ConditionCheck
from vultron.bt.base.composites import FallbackNode
from vultron.bt.base.factory import (
    action_node,
    condition_check,
    fallback,
    sequence,
)

logger = logging.getLogger(__name__)


@dataclass
class EnumStateTransition:
    """
    Represents a transition between two states in an enum-based state machine
    """

    start_states: List[Enum]
    end_state: Enum


def state_in(
    key: str,
    state: Enum,
) -> Type[ConditionCheck]:
    """
    Factory method that returns a ConditionCheck class that checks if the blackboard[key] == state

    Args:
        key: the blackboard key to check
        state: the state to check for

    Returns:
        A ConditionCheck class that checks if the blackboard[key] == state
    """

    def func(obj: BtNode) -> bool:
        f"""True if the node's blackboard[{key}] == {state}"""
        return getattr(obj.bb, key) == state

    node_cls = condition_check(f"{key}_in_{state}", func)

    # add some attributes to the node_cls so we can test it later
    node_cls.key = key
    node_cls.state = state
    return node_cls


def to_end_state_factory(key: str, state: Enum) -> Type[ActionNode]:
    """Factory method that returns an ActionNode class that updates key to state."""

    def _func(obj: BtNode) -> bool:
        # remember where we were so we can log the change
        before = getattr(obj.bb, key)

        setattr(obj.bb, key, state)

        # record this bb in history
        histkey = f"{key}_history"
        history = list(getattr(obj.bb, histkey))
        if len(history) == 0 or (history[-1] != state):
            history.append(state)
        setattr(obj.bb, histkey, history)

        logger.debug(f"Transition {before} -> {state}")
        return True

    node_cls = action_node(
        f"{key}_to_{state}",
        _func,
    )

    return node_cls


def state_change(
    key: str, transition: EnumStateTransition
) -> Type[FallbackNode]:
    """Factory method that returns a FallbackNode object that returns SUCCESS when the blackboard[key]
    starts in one of start_states and changes to end_state, and FAILURE otherwise
    """
    start_states = transition.start_states
    end_state = transition.end_state

    # check that the end_state is in the start_states
    start_state_checks = fallback(
        f"allowed_start_states_for_{key}_{end_state}",
        f"""SUCCESS when the current {key} is in one of {(s.name for s in start_states)}. FAILURE otherwise.""",
        *[state_in(key, state) for state in start_states],
    )

    # transition to the end_state
    sc_seq = sequence(
        f"transition_to_{key}_{end_state}_if_allowed",
        f"""Check for a valid start state in {(s.name for s in start_states)} and transition to {end_state}""",
        start_state_checks,
        to_end_state_factory(key, end_state),
    )

    # ensure we wind up in the end_state
    _state_change = fallback(
        f"transition_{key}_to_{end_state}",
        f"""Transition from (one of) {(s.name for s in start_states)} to {end_state}""",
        state_in(key, end_state),
        sc_seq,
    )

    return _state_change


def show_graph(node_cls):
    """Show the graph for the given node_cls"""
    nx.write_network_text(node_cls().to_graph())
