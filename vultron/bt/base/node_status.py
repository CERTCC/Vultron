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
This module defines a Behavior Tree Node Status object.
"""

from enum import Enum


class NodeStatus(Enum):
    """NodeStatus is the return value of a node's tick() method.
    Nodes can only return one of these values.

    Nodes return SUCCESS if they have completed their task successfully.
    Nodes return FAILURE if they have completed their task unsuccessfully.
    Nodes return RUNNING if they are still in the process of completing their task.
    """

    FAILURE = 0
    SUCCESS = 1
    RUNNING = 2

    def __str__(self):
        return self.name
