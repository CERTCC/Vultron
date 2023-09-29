#!/usr/bin/env python
"""file: common
author: adh
created_at: 4/5/22 10:01 AM
"""
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
#  U.S. Patent and Trademark Office by Carnegie Mellon Universityand Contributors.
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
#
#  See LICENSE for details

import logging
from dataclasses import dataclass
from enum import Enum
from typing import List

from vultron.bt.base.bt_node import ActionNode, ConditionCheck
from vultron.bt.base.composites import FallbackNode, SequenceNode
from vultron.bt.base.node_status import NodeStatus

logger = logging.getLogger(__name__)


@dataclass
class EnumStateTransition:
    """
    Represents a transition between two states in an enum-based state machine
    """

    start_states: List[Enum]
    end_state: Enum


class StateIn(ConditionCheck):
    """ConditionCheck that returns SUCCESS if the node's blackboard[key] == state
    Used as a base class for other StateIn classes like EMinState
    """

    key = None
    states = None
    state = None

    def func(self):
        return getattr(self.bb, self.key) == self.state


def to_end_state_factory(key: str, state: Enum) -> ActionNode:
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


def make_check_state(_key: str, _state) -> StateIn:
    """Factory method that returns a ConditionCheck object which returns SUCCESS if the node's blackboard[key] == state"""

    class CheckState(StateIn):
        key = _key
        state = _state

        def __init__(self):
            super().__init__()
            self.name = f"{self.__class__.__name__}_{_key}_in_{_state}"

    return CheckState


def make_state_change(key: str, transition: EnumStateTransition) -> FallbackNode:
    """Factory method that returns a FallbackNode object that returns SUCCESS when the blackboard[key]
    starts in one of start_states and changes to end_state, and FAILURE otherwise
    """

    # todo make this method accept an EnumTransition object instead of start_states and end_state
    start_states = transition.start_states
    end_state = transition.end_state

    class StartStateChecks(FallbackNode):
"""Check that the current {key} is in one of {(s.name for s in start_states)}"""
        _children = tuple([make_check_state(key, state) for state in start_states])

    to_end_state = to_end_state_factory(key, end_state)

    class ScSeq(SequenceNode):
        f"""
        Check for a valid start state in {(s.name for s in start_states)} and transition to {end_state}
        """
        _children = (StartStateChecks, to_end_state)

    in_end_state = make_check_state(key, end_state)

    class StateChange(FallbackNode):
        f"""
        Transition from (one of) {(s.name for s in start_states)} to {end_state}
        """
        name_pfx = "+"
        _children = (in_end_state, ScSeq)

        def __init__(self):
            super().__init__()
            self.name = f"{self.__class__.__name__}_{key}_to_{end_state}"

    return StateChange


def make_flag_state_change(key: str, end_state) -> ActionNode:
    """Factory method that returns an ActionNode class that updates key to include end_state.
    Assumes that blackboard[key] is a bit flag enumeration
    """

    class FlagStateChange(ActionNode):
"""Transition to {end_state}"""
        name_pfx = "+"

        def __init__(self):
            super().__init__()
            self.name = f"{self.__class__.__name__}_{key}_to_{end_state}"

        def _tick(self, depth=0):
            indent = "  " * (depth)
            before = getattr(self.bb, key)

            try:
                after = before | end_state
            except TypeError as e:
                logger.warning(f"Incomparable enums: {e}")
                return NodeStatus.FAILURE

            # if you got here, alles gute!
            setattr(self.bb, key, after)

            histkey = f"{key}_history"
            history = list(getattr(self.bb, histkey))
            history.append(after)
            setattr(self.bb, histkey, history)

            logger.debug(f"++{indent}{before} -> {after}")

            return NodeStatus.SUCCESS

    return FlagStateChange
