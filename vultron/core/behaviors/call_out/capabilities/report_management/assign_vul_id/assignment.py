#!/usr/bin/env python
#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""Core capability declarations for ``report_management.assign_vul_id.assignment``.

Each class declares one named capability's blackboard contract as typed
ports (BT-18-012).  Its simulation node, in
``vultron.demo.fuzzer.report_management.assign_vul_id.assignment``,
subclasses the declaration rather than restating it (BT-18-021).
"""

from __future__ import annotations

from py_trees.ports import PortInformation

from vultron.core.behaviors.call_out.capability import (
    ComposerCapability,
    EvaluatorCapability,
    RetrieverCapability,
)


class IdAssignedCapability(RetrieverCapability):
    """Check whether the vulnerability has already been assigned an identity.

    Blackboard contract (BT-18-001):
      Input keys:  (none — queries an external ID registry)
      Output keys: (none — binary result only, per BT-18-006)
      Refusal keys: call_out_refusal_reason: str  (no only)

    Store-held answer (BT-18-039): **cannot** — the case file has no field
    for an assigned identifier, so no read-first guard precedes it (see
    ``AssignCveIdCallOutBundle.id_assigned_factory``).
    """


class IdAssignableCapability(EvaluatorCapability):
    """Check whether the vulnerability qualifies for an ID assignment.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates vulnerability attributes from caller's DataLayer)
      Output keys: id_assignable_verdict: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """

    OUTPUT_PORTS = {
        "id_assignable_verdict": PortInformation(data_type=str, required=True),
    }


class RequestIdCapability(RetrieverCapability):
    """Request a Vulnerability ID assignment from an external authority.

    Blackboard contract (BT-18-001):
      Input keys:  (none — submits request to external ID authority)
      Output keys: assigned_id: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)

    Store-held answer (BT-18-039): **cannot** — it asks an outside
    authority for a new identifier, which nothing in the case file or the
    actor's store holds before the answer.
    """

    OUTPUT_PORTS = {
        "assigned_id": PortInformation(data_type=str, required=True),
    }


class AssignIdCapability(ComposerCapability):
    """Assign a Vulnerability ID directly to the vulnerability.

    Blackboard contract (BT-18-001):
      Input keys:  (none — reads case context from caller's DataLayer)
      Output keys: assigned_vul_id: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """

    OUTPUT_PORTS = {
        "assigned_vul_id": PortInformation(data_type=str, required=True),
    }


__all__ = [
    "AssignIdCapability",
    "IdAssignableCapability",
    "IdAssignedCapability",
    "RequestIdCapability",
]
