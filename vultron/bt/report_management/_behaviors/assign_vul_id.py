#!/usr/bin/env python
"""file: assign_vul_id
author: adh
created_at: 6/23/22 2:39 PM
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


from vultron.bt.base.composites import FallbackNode, SequenceNode
from vultron.bt.report_management.fuzzer.assign_vul_id import (
    AssignId,
    IdAssignable,
    IdAssigned,
    InScope,
    IsIDAssignmentAuthority,
    RequestId,
)


class AssignIdIfPossible(SequenceNode):
    """This node attempts to assign an ID to the vulnerability if possible.
    Steps:
    1. Check whether we are an ID assignment authority
    2. Check whether the vulnerability is ID assignable per the ID assignment authority rules
    3. Assign an ID to the vulnerability
    If all of these steps succeed, the vulnerability is assigned an ID.
    If any of these steps fail, the vulnerability is not assigned an ID.
    """

    _children = (IsIDAssignmentAuthority, IdAssignable, AssignId)


class AssignOrRequestId(FallbackNode):
    """This node attempts to assign an ID to the vulnerability or request an ID from the ID assignment authority.
    Steps:
    1. Attempt to assign an ID to the vulnerability
    2. Request an ID from the ID assignment authority
    If either of these steps succeed, the vulnerability is assigned an ID.
    If both of these steps fail, the vulnerability is not assigned an ID.
    """

    _children = (AssignIdIfPossible, RequestId)


class AssignIdIfInScope(SequenceNode):
    """This node attempts to assign a vulnerability ID to the vulnerability if it is in scope.
    Steps:
    1. Check whether the vulnerability is in scope for ID assignment
    2. Attempt to assign an ID to the vulnerability or request an ID from the ID assignment authority
    If both of these steps succeed, the vulnerability is assigned an ID.
    If any of these steps fail, the vulnerability is not assigned an ID.
    """

    _children = (InScope, AssignOrRequestId)


class AssignVulID(FallbackNode):
    """This node attempts to assign a vulnerability ID to the vulnerability.
    Steps:
    1. Check whether the vulnerability is already assigned an ID
    2. Check whether the vulnerability is in scope and assign an ID if possible
    If any of these steps succeed, the vulnerability is assigned an ID.
    If all of these steps fail, the vulnerability is not assigned an ID.
    """

    _children = (IdAssigned, AssignIdIfInScope)
