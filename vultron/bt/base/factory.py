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

from typing import Type

from vultron.bt.base.bt_node import BtNode
from vultron.bt.base.composites import FallbackNode, SequenceNode
from vultron.bt.base.decorators import Invert


def node_factory(
    nodetype: Type[BtNode],
    name: str,
    docstr: str,
    *child_classes: Type[BtNode],
) -> Type[BtNode]:
    """
    Convenience function to create a node with a docstring.

    Args:
        nodetype: a BtNode class
        name: the name of the node class
        docstr: the docstring for the node
        *child_classes: the child classes for the node (if any)

    Returns:
        A node class with the given docstring and children
    """

    cls = type(name, (nodetype,), {})
    cls.__doc__ = docstr

    if len(child_classes) > 0:
        cls._children = child_classes

    return cls


def sequence(
    name: str, docstr: str, *child_classes: Type[BtNode]
) -> Type[SequenceNode]:
    """
    Convenience function to create a SequenceNode with a docstring.

    Args:
        name: the name of the SequenceNode class
        docstr: the docstring for the SequenceNode
        *child_classes: the child classes for the SequenceNode

    Returns:
        A SequenceNode class with the given docstring and children
    """
    return node_factory(SequenceNode, name, docstr, *child_classes)


def fallback(
    name: str, docstr: str, *child_classes: Type[BtNode]
) -> Type[FallbackNode]:
    """
    Convenience function to create a FallbackNode with a docstring.

    Args:
        name: the name of the FallbackNode class
        docstr: the docstring for the FallbackNode
        *child_classes: the child classes for the FallbackNode

    Returns:
        A FallbackNode class with the given docstring and children
    """
    return node_factory(FallbackNode, name, docstr, *child_classes)


def invert(
    name: str, docstr: str, *child_classes: Type[BtNode]
) -> Type[Invert]:
    """
    Convenience function to create an Invert decorator with a docstring.

    Args:
        name: the name of the Invert decorator class
        docstr: the docstring for the Invert decorator
        *child_classes: the child class for the Invert decorator

    Returns:
        An Invert decorator class with the given docstring and children
    """
    return node_factory(Invert, name, docstr, *child_classes)
