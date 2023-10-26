#!/usr/bin/env python
"""
Provides Vulnerability ID assignment behaviors.
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

from vultron.bt.base.factory import fallback, sequence
from vultron.bt.report_management.fuzzer.assign_vul_id import (
    AssignId,
    IdAssignable,
    IdAssigned,
    InScope,
    IsIDAssignmentAuthority,
    RequestId,
)


_AssignIdIfPossible = sequence(
    "_AssignIdIfPossible",
    """This node attempts to assign an ID to the vulnerability if possible.
    Steps:
    1. Check whether we are an ID assignment authority
    2. Check whether the vulnerability is ID assignable per the ID assignment authority rules
    3. Assign an ID to the vulnerability
    If all of these steps succeed, the vulnerability is assigned an ID.
    If any of these steps fail, the vulnerability is not assigned an ID.
    """,
    IsIDAssignmentAuthority,
    IdAssignable,
    AssignId,
)


_AssignOrRequestId = fallback(
    "_AssignOrRequestId",
    """This node attempts to assign an ID to the vulnerability or request an ID from the ID assignment authority.
    Steps:
    1. Attempt to assign an ID to the vulnerability
    2. Request an ID from the ID assignment authority
    If either of these steps succeed, the vulnerability is assigned an ID.
    If both of these steps fail, the vulnerability is not assigned an ID.
    """,
    _AssignIdIfPossible,
    RequestId,
)


_AssignIdIfInScope = sequence(
    "_AssignIdIfInScope",
    """This node attempts to assign a vulnerability ID to the vulnerability if it is in scope.
    Steps:
    1. Check whether the vulnerability is in scope for ID assignment
    2. Attempt to assign an ID to the vulnerability or request an ID from the ID assignment authority
    If both of these steps succeed, the vulnerability is assigned an ID.
    If any of these steps fail, the vulnerability is not assigned an ID.
    """,
    InScope,
    _AssignOrRequestId,
)


AssignVulID = fallback(
    "AssignVulID",
    """This node attempts to assign a vulnerability ID to the vulnerability.
    Steps:
    1. Check whether the vulnerability is already assigned an ID
    2. Check whether the vulnerability is in scope and assign an ID if possible
    If any of these steps succeed, the vulnerability is assigned an ID.
    If all of these steps fail, the vulnerability is not assigned an ID.
    """,
    IdAssigned,
    _AssignIdIfInScope,
)
