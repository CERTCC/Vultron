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
"""Core capability declarations for ``report_management.report_to_others.injection``.

Each class declares one named capability's blackboard contract as typed
ports (BT-18-012).  Its simulation node, in
``vultron.demo.fuzzer.report_management.report_to_others.injection``,
subclasses the declaration rather than restating it (BT-18-021).
"""

from __future__ import annotations

from vultron.core.behaviors.call_out.capability import (
    ActuatorCapability,
)


class InjectParticipantCapability(ActuatorCapability):
    """Add a new participant to the case (generic form).

    Blackboard contract (BT-18-001):
      Input keys:  (none — trigger only; participant context from construction time)
      Output keys: (none — side effect: add participant to case management system)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """


__all__ = [
    "InjectParticipantCapability",
]
