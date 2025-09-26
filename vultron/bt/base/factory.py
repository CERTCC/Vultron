#!/usr/bin/env python
"""
Provides common tools for constructing behavior trees
"""
#  Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
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

from typing import Callable, Type, TypeVar

from vultron.bt.base.bt_node import ActionNode, BtNode, ConditionCheck
from vultron.bt.base.composites import FallbackNode, ParallelNode, SequenceNode
from vultron.bt.base.decorators import Invert, RepeatUntilFail
from vultron.bt.base.fuzzer import FuzzerNode

NodeType = TypeVar("NodeType", bound=BtNode)


def _set_func(node_cls: Type[BtNode], func: Callable[[BtNode], bool]) -> None:
    """
    Sets the func attribute of a node_cls to the given function.

    Args:
        node_cls: a BtNode class
        func: the function to set as the node_cls's func attribute. Expects a BtNode as an argument and returns a bool

    Returns:

    """
    if hasattr(node_cls, "func"):
        # settattr instead of direct assignment to avoid mypy error
        setattr(node_cls, "func", func)


def node_factory(
    node_type: Type[NodeType],
    name: str,
    docstr: str | None,
    *child_classes: Type[BtNode],
) -> Type[NodeType]:
    """
    Convenience function to create a node_cls with a docstring.

    Args:
        node_type: a BtNode class
        name: the name of the node_cls
        docstr: the docstring for the node_cls
        *child_classes: the child classes for the node_cls (if any)

    Returns:
        A node_cls class with the given docstring and children
    """

    node_cls = type(name, (node_type,), {})
    node_cls.__doc__ = docstr

    if len(child_classes) > 0:
        node_cls._children = child_classes

    return node_cls


def sequence_node(
    name: str, description: str, *child_classes: Type[BtNode]
) -> Type[SequenceNode]:
    """
    Convenience function to create a SequenceNode with a docstring.

    Args:
        name: the name of the SequenceNode class
        description: the docstring for the SequenceNode
        *child_classes: the child classes for the SequenceNode

    Returns:
        A SequenceNode class with the given docstring and children
    """

    if len(child_classes) < 2:
        raise ValueError("SequenceNode should have at least two children")

    return node_factory(SequenceNode, name, description, *child_classes)


def fallback_node(
    name: str, description: str, *child_classes: Type[BtNode]
) -> Type[FallbackNode]:
    """
    Convenience function to create a FallbackNode with a docstring.

    Args:
        name: the name of the FallbackNode class
        description: the docstring for the FallbackNode
        *child_classes: the child classes for the FallbackNode

    Returns:
        object:
        A FallbackNode class with the given docstring and children
    """
    if len(child_classes) < 1:
        raise ValueError(
            "FallbackNode should have at least one child (preferably 2)"
        )

    return node_factory(FallbackNode, name, description, *child_classes)


def invert(
    name: str, description: str, *child_classes: Type[BtNode]
) -> Type[Invert]:
    """
    Convenience function to create an Invert decorator with a docstring.

    Args:
        name: the name of the Invert decorator class
        description: the docstring for the Invert decorator
        *child_classes: the child class for the Invert decorator

    Returns:
        An Invert decorator class with the given docstring and children
    """
    if len(child_classes) != 1:
        raise ValueError("Invert decorator can only take one child")

    return node_factory(Invert, name, description, *child_classes)


def fuzzer(
    cls: Type[FuzzerNode],
    name: str,
    description: str | None,
) -> Type[FuzzerNode]:
    """
    Convenience function to create a WeightedSuccess fuzzer with a docstring.

    Args:
        cls: the WeightedSuccess class to serve as the base class
        name: the name of the WeightedSuccess class
        description: the docstring for the WeightedSuccess class

    Returns:
        A WeightedSuccess class with the given docstring

    """
    return node_factory(cls, name, description)


def condition_check(
    name: str,
    func: Callable[
        [
            BtNode,
        ],
        bool,
    ],
) -> Type[ConditionCheck]:
    """
    Convenience function to create a ConditionCheck node with a docstring.
    The function's docstring will be used as the ConditionCheck's docstring.

    Args:
        name: the name of the ConditionCheck class
        func: the function to be used as the ConditionCheck's condition. Expects a BtNode as an argument and returns a bool

    Returns:
        A ConditionCheck class with the given docstring and condition function

    """
    node_cls = node_factory(ConditionCheck, name, func.__doc__)
    _set_func(node_cls, func)
    return node_cls


def action_node(
    name: str,
    func: Callable[
        [
            BtNode,
        ],
        bool,
    ],
) -> Type[ActionNode]:
    """
    Convenience function to create an ActionNode with a docstring.
    The function's docstring will be used as the ActionNode's docstring.

    Args:
        name: the name of the ActionNode class
        func: the function to be used as the ActionNode's action. Expects a BtNode as an argument and returns a bool

    Returns:
        An ActionNode class with the given docstring and action function
    """
    node_cls = node_factory(ActionNode, name, func.__doc__)
    _set_func(node_cls, func)
    return node_cls


def repeat_until_fail(
    name: str, description: str, *child_classes: Type[BtNode]
) -> Type[RepeatUntilFail]:
    """
    Convenience function to create a RepeatUntilFail node with a docstring.

    Args:
        name: the name of the RepeatUntilFail class
        description: the docstring for the RepeatUntilFail class
        *child_classes: the child class to repeat

    Returns:

    """
    if len(child_classes) != 1:
        raise ValueError("RepeatUntilFail can only take one child")

    return node_factory(RepeatUntilFail, name, description, *child_classes)


def parallel_node(
    name: str, description: str, min_success: int, *child_classes: type[BtNode]
) -> type[ParallelNode]:
    # make sure min_success is a positive integer
    if (
        not isinstance(min_success, int)
        or min_success < 1
        or min_success > len(child_classes)
    ):
        raise ValueError(
            "min_success must be a positive integer less than or equal to the number of children"
        )

    # make sure child_classes is not empty
    if len(child_classes) < 2:
        raise ValueError("ParallelNode should have at least two children")

    node_cls = node_factory(ParallelNode, name, description, *child_classes)
    if hasattr(node_cls, "min_success"):
        node_cls.min_success = min_success

    return node_cls
