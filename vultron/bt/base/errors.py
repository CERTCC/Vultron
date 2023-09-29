#!/usr/bin/env python
"""file: errors
author: adh
created_at: 5/20/22 12:59 PM
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
#
#  See LICENSE for details

from vultron.errors import VultronError


class BehaviorTreeError(VultronError):
    """Raised when a BehaviorTree encounters an error"""


class BehaviorTreeFuzzerError(BehaviorTreeError):
    """Raised when a BehaviorTreeFuzzer encounters an error"""


class LeafNodeError(BehaviorTreeError):
    """Raised when a leaf node encounters an error"""


class ActionNodeError(LeafNodeError):
    """Raised when an action node encounters an error"""


class ConditionCheckError(LeafNodeError):
    """Raised when a condition check encounters an error"""
