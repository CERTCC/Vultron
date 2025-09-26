#!/usr/bin/env python
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
"""
This module provides the base class for all nodes in the Behavior Tree.

It also provides a number of core node types that can be used to build a Behavior Tree.
"""

import logging
from copy import deepcopy
from typing import Iterable

import networkx as nx

from vultron.bt.base.errors import (
    ActionNodeError,
    ConditionCheckError,
    LeafNodeError,
)
from vultron.bt.base.node_status import NodeStatus

logger = logging.getLogger(__name__)


def _indent(depth=0):
    """Convenience method for indenting printed output."""
    return " | " * depth


class BtNode:
    """BtNode is the base class for all nodes in the Behavior Tree."""

    indent_level: int = 0
    name_pfx: str | None = None
    _node_shape: str = "box"
    _children: Iterable | None = None
    _objcount: int = 0

    def __init__(self):
        BtNode._objcount += 1

        pfx = ""
        if self.name_pfx is not None:
            pfx = f"{self.name_pfx}_"

        # freeze object count into a string at instantiation time
        self.name_sfx = f"_{BtNode._objcount}"

        self.name = f"{pfx}{self.__class__.__name__}{self.name_sfx}"

        self.parent = None
        self.children = []

        self.status = None
        self.bb = None

        self._setup_complete = False

        self.add_children()

    def __enter__(self):
        self.setup()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def setup(self) -> None:
        """Sets up the node and its children.

        Returns:
            None
        """
        if self.parent is not None:
            self.bb = self.parent.bb
        for child in self.children:
            child.setup()

        self._setup_complete = True

    def add_child(self, child: "BtNode") -> "BtNode":
        """Adds a child to the node.

        Args:
            child: the child node to add

        Returns:
            the child node
        """
        self.children.append(child)
        child.indent_level = self.indent_level + 1
        child.parent = self
        child.bb = self.bb
        return child

    def add_children(self) -> None:
        """
        Adds children to the node. Loops through the _children list and creates a new instance of each child class.
        """
        if self._children is None:
            return

        for child_class in self._children:
            # instantiate the child class and add it to this node's children
            child = child_class()
            self.add_child(child)

    @property
    def _pfx(self) -> str:
        if self.name_pfx is not None:
            return f"({self.name_pfx})"
        return ""

    def _pre_tick(self, depth: int = 0) -> None:
        """Called before the node is ticked.
         Override this method in your subclass if you need to do something before the node is ticked.
         Does nothing by default.

        Args:
            depth: the node's depth in the tree
        """

    def tick(self, depth: int = 0) -> NodeStatus:
        """Ticks the node.
        Performs the following actions:

        - calls `_pre_tick()`
        - calls `_tick()`
        - calls `_post_tick()`
        - sets the node's status based on the return value of `_tick()`

        Args:
            depth: the node's depth in the tree

        Returns:
            the node's status (as a NodeStatus enum)
        """
        if self.name is not None:
            logger.debug(_indent(depth) + f"{self._pfx} {self.name}")

        with self:
            self._pre_tick(depth=depth)
            status = self._tick(depth)
            self.status = status
            self._post_tick(depth=depth)

        if self.name is not None:
            logger.debug(_indent(depth + 1) + f"= {self.status}")

        return status

    def _post_tick(self, depth: int = 0) -> None:
        """Called after the node is ticked.
        Override this method in your subclass if you need to do something after the node is ticked.
        Does nothing by default.

        Args:
            depth
        """
        pass

    def _tick(self, depth: int = 0) -> NodeStatus:
        """Called by tick().
        Implement this method in your subclass.

        Args:
            depth

        Returns:
            the node's status (as a NodeStatus enum)
        """
        raise NotImplementedError

    @property
    def _node_label(self) -> str:
        if self.name_pfx is not None:
            return f"{self.name_pfx} {self.name}"

        return str(self.name)

    @property
    def _is_leaf_node(self) -> bool:
        """Returns True if the node is a leaf node, False otherwise."""
        if not hasattr(self, "_children"):
            return True
        if self._children is None:
            return True
        # Efficiently check if _children is empty
        children = self._children
        if hasattr(children, "__len__"):
            if len(children) == 0:
                return True
        else:
            if next(iter(children), None) is None:
                return True
        return False

    def _namestr(self, depth=0) -> str:
        """Returns a string representation of the node's name."""
        return _indent(depth) + f"{self._pfx} {self.name}"

    def to_str(self, depth=0) -> str:
        """Returns a string representation of the tree rooted at this node."""

        namestring = self._namestr(depth) + "\n"

        if self._is_leaf_node:
            # this is a leaf node
            return namestring

        # recurse through children and return a string representation of the tree
        parts = [
            namestring,
        ]
        for child in self.children:
            parts.append(child.to_str(depth + 1))
        return "".join(parts)

    def to_graph(self) -> nx.DiGraph:
        G = nx.DiGraph()

        # add a self node
        # see note *** below
        G.add_node(self.name, shape=self._node_shape)

        # walk the children
        for child in self.children:
            # add an edge from this node to the child node
            G.add_edge(self.name, child.name)
            # the child node will add itself to the graph with its shape because ***
            # create a graph for the child node and add it to this graph
            G = nx.compose(G, child.to_graph())

        return G

    def to_mermaid(self, depth=0, topdown=True) -> str:
        """Returns a string representation of the tree rooted at this node in mermaid format."""

        import re

        if self._is_leaf_node:
            # this is a leaf node, we aren't doing anything with it
            return ""

        parts = []
        if depth == 0:
            # add preamble
            parts.append("```mermaid")
            if topdown:
                parts.append("graph TD")
            else:
                parts.append("graph LR")

        def fixname(nstr: str) -> str:
            # TODO these should be subclass attributes
            nstr = re.sub(r"^>_", "&rarr; ", nstr)
            nstr = re.sub(r"^\^_", "#8645; ", nstr)
            nstr = re.sub(r"^z_", "#127922; ", nstr)
            nstr = re.sub(r"^a_", "#9648; ", nstr)
            nstr = re.sub(r"^c_", "#11052; ", nstr)
            nstr = re.sub(r"^\?_", "? ", nstr)
            nstr = re.sub(r"_\d+$", "", nstr)

            return nstr

        name = fixname(self.name)
        sname = f"{self.__class__.__name__}{self.name_sfx}"
        if depth == 0:
            parts.append(f'  {sname}["{name}"]')

        for child in self.children:
            cname = f"{child.__class__.__name__}{child.name_sfx}"
            parts.append(f'  {cname}["{fixname(child.name)}"]')

            parts.append(f"  {sname} --> {cname}")
            # recurse through children and return a string representation of the tree below this node
            parts.append(child.to_mermaid(depth + 1))

        if depth == 0:
            # add postamble
            parts.append("```")

        parts = [p for p in parts if p != ""]

        return "\n".join(parts)


class LeafNode(BtNode):
    """LeafNode is the base class for all leaf nodes in the Behavior Tree.
    Leaf nodes are nodes that do not have children.
    """

    Exc = LeafNodeError

    def __init__(self):
        """
        Raises a LeafNodeError if the node has children.
        """
        if self.__class__._children is not None:
            raise self.Exc("Behavior Tree Leaf Nodes cannot have children")
        super().__init__()

    def func(self) -> bool | None:
        """
        Override this method in your subclass.
        Return True for success, False for failure, and None for running.
        """

        raise NotImplementedError

    def _tick(self, depth: int = 0) -> NodeStatus:
        """
        Calls the node's func() method and returns the result.

        Args:
            depth

        Returns:
            the node's status (as a NodeStatus enum)
        """

        result = self.func()

        if result is None:
            return NodeStatus.RUNNING
        elif result:
            return NodeStatus.SUCCESS
        return NodeStatus.FAILURE


class ActionNode(LeafNode):
    """ActionNode is the base class for all action nodes in the Behavior Tree.
    Action nodes are leaf nodes that perform an action.
    An action node's func() method returns True for success, False for failure, and None for running.
    """

    name_pfx = "a"
    Exc = ActionNodeError


class ConditionCheck(LeafNode):
    """ConditionCheck is the base class for all condition check nodes in the Behavior Tree.
    Condition check nodes are leaf nodes that check a condition.
    A condition check node's func() method returns True for success, False for failure.
    Although it is possible to return None for running, this is not recommended.
    """

    name_pfx = "c"
    _node_shape = "ellipse"
    Exc = ConditionCheckError


class CountTicks(BtNode):
    """CountTicks is a decorator node that counts the number of times it is ticked."""

    start = 0

    def __init__(self):
        super().__init__()
        self.counter = self.start

    def _tick(self, depth: int = 0) -> NodeStatus:
        self.counter += 1
        return NodeStatus.SUCCESS


STATELOG = []


class SnapshotState(BtNode):
    """
    SnapshotState is a decorator node that takes a snapshot of the blackboard and appends it to the STATELOG list.
    """

    name = "Snapshot_state"

    def _tick(self, depth: int = 0) -> NodeStatus:
        snapshot = deepcopy(self.bb)
        STATELOG.append(snapshot)
        return NodeStatus.SUCCESS
