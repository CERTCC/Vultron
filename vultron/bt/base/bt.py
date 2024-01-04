#  Copyright (c) 2023-2024 Carnegie Mellon University and Contributors.
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
This module defines a Behavior Tree object.
"""

import logging
from typing import Type

from vultron.bt.base.blackboard import Blackboard
from vultron.bt.base.bt_node import BtNode
from vultron.bt.base.errors import (
    BehaviorTreeError,
)
from vultron.bt.base.node_status import NodeStatus

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class BehaviorTree:
    """BehaviorTree is the base class for all bt trees.
    It is responsible for setting up the tree and running the root node.

    Attributes:
        root: the root node of the tree
        bb: the blackboard object
    """

    bbclass = Blackboard

    def __init__(self, root: BtNode = None, bbclass: Type[Blackboard] = None):
        """
        Initialize the BehaviorTree object.

        Args:
            root: the root node of the tree
            bbclass: the blackboard class to use
        """
        self.root: BtNode = root
        if bbclass is not None:
            self.bbclass = bbclass

        self.bb: Blackboard = self.bbclass()
        self.status: NodeStatus = None

        # track whether we've done the pre-tick setup stuff
        self._setup: bool = False

    # runtime context
    def __enter__(self) -> "BehaviorTree":
        """
        Runtime context for the BehaviorTree object.

        Returns:
            self: the BehaviorTree object
        """
        self._ensure_setup()
        return self

    def __exit__(
        self, exc_type: Exception, exc_val: str, exc_tb: list
    ) -> bool:
        """
        Runtime context for the BehaviorTree object.

        Args:
            exc_type: the exception type
            exc_val: the exception value
            exc_tb: the exception traceback

        Returns:
            bool: True if the exception was handled, False otherwise
        """
        if exc_type is not None:
            # where were we in the tree?
            import inspect

            frm = inspect.trace()[-1]
            obj = frm[0].f_locals["self"]
            logger.debug(f"Exception in {obj.name}")
            print(obj.name)

            while obj.parent is not None:
                obj = obj.parent
                print(obj.name)
                logger.debug(f"parent: {obj.name}")

            # print(self.root.graph())
            return False

    def add_root(self, node: BtNode) -> None:
        """Adds a root node to the tree.

        Args:
            node: the root node to add

        Returns:
            None
        """
        self.root = node
        self.root.bb = self.bb

    def _ensure_setup(self) -> None:
        """Ensures that the tree has been set up.

        Args:
            None

        Returns:
            None

        Raises:
            BehaviorTreeError: if setup() fails
        """
        if self._setup:
            return

        self.setup()

        if not self._setup:
            raise BehaviorTreeError(f"{self.__class__.__name__} setup failed")

    def _pre_tick(self) -> None:
        """_pre_tick() is called before the root node's tick() method.

        Args:
            None

        Returns:
            None
        """
        self._ensure_setup()

    def tick(self) -> NodeStatus:
        """tick() is the main entry point for running the bt tree.
        It calls the root node's tick() method.
        Two callbacks are provided for subclasses to override:
        _pre_tick() and _post_tick().

        Returns:
            NodeStatus: the status of the root node after the tick

        """
        self._pre_tick()
        status = self.root.tick(depth=0)
        self._post_tick()
        self.status = status
        return status

    def _post_tick(self) -> None:
        """_post_tick() is called after the root node's tick() method.

        Returns:
            None
        """

    # def graph(self) -> :
    #     return self.root.graph()

    def setup(self) -> None:
        """Recursively calls the setup() method on all nodes in the tree starting at the root.

        Returns:
            None
        """
        self.root.bb = self.bb
        self.root.setup()
        self._setup = True


# def to_dot(node: BtNode, g=None):
#     if g is None:
#         g = graphviz.Digraph()
#
#     g.node(node.name, label=node._node_label, shape=node._node_shape)
#     for child in node.children:
#         to_dot(child, g)
#         g.edge(node.name, child.name)
#     return g
