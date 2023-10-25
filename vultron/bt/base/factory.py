#!/usr/bin/env python
"""
Provides common tools for constructing behavior trees
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
#  U.S. Patent and Trademark Office by Carnegie Mellon University

from typing import Callable, Type, TypeVar

from vultron.bt.base.bt_node import ActionNode, BtNode, ConditionCheck
from vultron.bt.base.composites import FallbackNode, SequenceNode
from vultron.bt.base.decorators import Invert
from vultron.bt.base.fuzzer import FuzzerNode

NodeType = TypeVar("NodeType", bound=Type[BtNode])


def node_factory(
    node_type: Type[NodeType],
    name: str,
    docstr: str,
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


def sequence(
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
    return node_factory(SequenceNode, name, description, *child_classes)


def fallback(
    name: str, description: str, *child_classes: Type[BtNode]
) -> Type[FallbackNode]:
    """
    Convenience function to create a FallbackNode with a docstring.

    Args:
        name: the name of the FallbackNode class
        description: the docstring for the FallbackNode
        *child_classes: the child classes for the FallbackNode

    Returns:
        A FallbackNode class with the given docstring and children
    """
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
    return node_factory(Invert, name, description, *child_classes)


def fuzzer(
    cls: Type[FuzzerNode], name: str, description: str
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
    node_cls.func = func
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
    node_cls.func = func
    return node_cls
