#!/usr/bin/env python
"""file: bt_node
author: adh
created_at: 2/20/23 12:23 PM
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


import logging
from copy import deepcopy

from vultron.bt.base.errors import (
    ActionNodeError,
    ConditionCheckError,
    LeafNodeError,
)
from vultron.bt.base.node_status import NodeStatus

logger = logging.getLogger(__name__)
_objcount = 0


class BtNode:
    """BtNode is the base class for all nodes in the Behavior Tree."""

    indent_level = 0
    name_pfx = None
    _node_shape = "box"
    _children = None

    def __init__(self):
        global _objcount
        _objcount += 1

        pfx = ""
        if self.name_pfx is not None:
            pfx = f"{self.name_pfx}_"
        self.name_sfx = f"_{_objcount}"

        self.name = f"{pfx}{self.__class__.__name__}{self.name_sfx}"

        self.parent = None
        self.children = []

        self.status = None
        self.bb = None

        self.add_children()

    def setup(self) -> None:
        """Sets up the node and its children.

        Returns:
            None
        """
        if self.parent is not None:
            self.bb = self.parent.bb
        for child in self.children:
            child.setup()

    def add_child(self, child):
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
        """Adds children to the node. Loops through the _children list and creates a new instance of each child class.

        Returns:
            None
        """
        if self._children is None:
            return

        for child_class in self._children:
            # instantiate the child class and add it to this node's children
            child = child_class()
            self.add_child(child)

    def _indent(self, depth=0):
        """Convenience method for indenting printed output."""
        return " | " * depth

    @property
    def _pfx(self):
        if self.name_pfx is not None:
            return f"({self.name_pfx})"
        return ""

    def _pre_tick(self, depth=0):
        """Called before the node is ticked.

        Args:
            depth: the node's depth in the tree

        Returns:
            none
        """

    def tick(self, depth=0) -> NodeStatus:
        """Ticks the node.
        Performs the following actions:
        - calls _pre_tick()
        - calls _tick()
        - calls _post_tick()
        - sets the node's status based on the return value of _tick()

        Args:
            depth: the node's depth in the tree

        Returns:
            the node's status (as a NodeStatus enum)
        """
        if self.name is not None:
            logger.debug(self._indent(depth) + f"{self._pfx} {self.name}")

        self._pre_tick(depth=depth)
        status = self._tick(depth)
        self.status = status
        self._post_tick(depth=depth)

        if self.name is not None:
            logger.debug(self._indent(depth + 1) + f"= {self.status}")

        return status

    def _post_tick(self, depth=0):
        """Called after the node is ticked.

        Args:
            depth

        Returns:

        """
        pass

    def _tick(self, depth=0) -> NodeStatus:
        """Called by tick().
        Implement this method in your subclass.

        Args:
            depth

        Returns:
            the node's status (as a NodeStatus enum)
        """
        raise NotImplementedError
        pass

    @property
    def _node_label(self):
        if self.name_pfx is not None:
            return f"{self.name_pfx} {self.name}"

        return self.name

    # def graph(self, g=None):
    #     return to_dot(self)

    @property
    def _is_leaf_node(self):
        """Returns True if the node is a leaf node, False otherwise."""
        return self._children is None or len(self._children) == 0

    def _namestr(self, depth=0):
        """Returns a string representation of the node's name."""
        return self._indent(depth) + f"{self._pfx} {self.name}"

    def to_str(self, depth=0):
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

    def to_mermaid(self, depth=0):
        """Returns a string representation of the tree rooted at this node in mermaid format."""

        import re

        if self._is_leaf_node:
            # this is a leaf node, we aren't doing anything with it
            return ""

        parts = []
        if depth == 0:
            # add preamble
            parts.append("```mermaid")
            parts.append("graph TD")

        def fixname(name):
            # TODO these should be subclass attributes
            name = re.sub(r"^>_", "&rarr; ", name)
            name = re.sub(r"^\^_", "#8645; ", name)
            name = re.sub(r"^z_", "#127922; ", name)
            name = re.sub(r"^a_", "#9648; ", name)
            name = re.sub(r"^c_", "#11052; ", name)
            name = re.sub(r"^\?_", "? ", name)
            name = re.sub(r"_\d+$", "", name)

            return name

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

    def func(self):
        return self._func(self.bb)

    def _tick(self, depth=0):
        """Calls the node's func() method and returns the result.

        Args:
            depth

        Returns:

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
    """

    name_pfx = "c"
    _node_shape = "ellipse"
    Exc = ConditionCheckError

    def _tick(self, depth=0):
        if self.func():
            return NodeStatus.SUCCESS
        return NodeStatus.FAILURE

    def func(self):
        """Return True for success, False for failure"""
        raise NotImplementedError


class CountTicks(BtNode):
    """CountTicks is a decorator node that counts the number of times it is ticked."""

    start = 0

    def __init__(self):
        super().__init__()
        self.counter = self.start

    def _tick(self, depth=0):
        self.counter += 1
        return NodeStatus.SUCCESS


STATELOG = []


class SnapshotState(BtNode):
    """
    SnapshotState is a decorator node that takes a snapshot of the blackboard and appends it to the STATELOG list.
    """

    name = "Snapshot_state"

    def _tick(self, depth=0):
        global STATELOG
        snapshot = deepcopy(self.bb)
        STATELOG.append(snapshot)
        return NodeStatus.SUCCESS
