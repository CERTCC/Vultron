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
Provides fuzzer leaf nodes for the report management workflow.
"""

from vultron.bt.base.factory import fuzzer
from vultron.bt.base.fuzzer import (
    AlwaysSucceed,
    OftenSucceed,
    ProbablySucceed,
    UsuallyFail,
    UsuallySucceed,
)

IdAssigned = fuzzer(
    UsuallyFail,
    "IdAssigned",
    """This condition is used to check if the vulnerability has already been assigned an identity, such as a CVE ID. In
    a real implementation, this would be a simple check to see if the vulnerability has already been assigned an
    identity. In our stub implementation, this condition fails in 3 out of 4 attempts because we are assuming that
    the ID assignment process is part of the workflow.
    """,
)

# check if the vulnerability has already been assigned an identity


InScope = fuzzer(
    UsuallySucceed,
    "InScope",
    """This condition is used to check if the vulnerability is in scope for an ID assignment This is not the same as
    checking whether the vulnerability is in scope for the organization's CVD process. In the case of CVE ID
    assignment, the scope is defined in the CNA rules. Other ID assignment processes may have different scope
    definitions. In a real implementation, this would probably be a prompt for a human to check the reported
    vulnerability against the scope definition, if applicable. Hint: An ID space which allows for rapid assignment of
    IDs may have a very broad scope and may not require this check. In our stub implementation, this condition
    succeeds in 3 out of 4 attempts.
    """,
)

# check if the vulnerability is in scope for an ID assignment


RequestId = fuzzer(
    UsuallySucceed,
    "RequestId",
    """This node represents the process of requesting a Vulnerability ID assignment. For example, in the case of CVE ID
    assignment, this would be the process of submitting a CVE ID request to the CVE Numbering Authority (CNA). In a
    real implementation, this could be automatable as an API call to the CNA, or it could be a prompt for a human to
    submit the request. In our stub implementation, this node succeeds in 3 out of 4 attempts so that we can exercise
    the rest of the workflow.
    """,
)

# submit an ID request to the ID assignment authority or prompt a human to do so


IsIDAssignmentAuthority = fuzzer(
    OftenSucceed,
    "IsIDAssignmentAuthority",
    """This condition is used to check if the organization is an ID assignment authority itself with the ability to
    assign IDs directly. We are using the CVE Numbering Authority (CNA) as an example of an ID assignment authority,
    but this is intended to be a generic condition and not specific to CVE ID assignment except as an example. In a
    real implementation, this would probably be a simple check against the organization's metadata. In our stub
    implementation, this condition succeeds in 7 out of 10 attempts.
    """,
)

# check if the organization is an ID assignment authority


IdAssignable = fuzzer(
    ProbablySucceed,
    "IdAssignable",
    """This condition checks to see if the vulnerability qualifies for an ID assignment by the entity evaluating this
    conditio, based on the ID assignment rules governing the ID space. For example, in the case of CVE ID assignment,
    this would be the process of checking the vulnerability against the CVE ID assignment rules. In a real
    implementation, this would probably be a prompt for a human to check the vulnerability against the ID assignment
    rules, if applicable. It may be possible to automate this check in some cases. Using the CVE ID assignment rules
    as an example, if the vulnerability is in scope for CVE ID assignment, but the individual or organization
    evaluating this condition is not the authoritatve CNA for the product, this condition would be expected to fail.
    In our stub implementation, this condition succeeds in 2 out of 3 attempts.
    """,
)

# check if the vulnerability qualifies for an ID assignment by the entity evaluating this condition


AssignId = fuzzer(
    AlwaysSucceed,
    "AssignId",
    """This node represents the process of assigning an ID to the vulnerability.
    For example, in the case of CVE ID assignment, this would be the process of assigning a CVE ID to the vulnerability.
    In a real implementation, this could be automatable as an API call to the ID assignment authority,
    an automated process to assign an ID from a pool of available IDs,
    or it could be a prompt for a human to assign the ID.
    In our stub implementation, this node always succeeds.
    """,
)

# assign an ID to the vulnerability or prompt a human to do so
