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


"""RM transition nodes for the report behavior tree.

Two shapes of RM transition live here, and the difference between them is the
whole point of the module layout:

**Report-phase transitions** (:class:`TransitionRMtoValid`,
:class:`TransitionRMtoInvalid`, :class:`TransitionRMtoClosed`) record the
current RM state on the report's ``VultronReportCaseLink`` record
(BTND-10-006, ADR-0089).  That field is the idempotency source read by
``CheckRMStateValid`` / ``CheckRMStateReceivedOrInvalid``.

**Case-scoped transitions** advance the actor's RM state on
its ``CaseParticipant`` inside a ``VulnerabilityCase``.

``RM.VALID`` is *both*: DUR-07-004 requires an established embargo for an
embargo-eligible case (EP-04-008 exempts one with P, X or A set), the embargo
and the P/X/A state exist only on a case, and engage-case reads the
participant's case-scoped state.  So
``TransitionRMtoValid`` requires the case and performs the case-scoped half
*before* updating the ReportCaseLink field (ID-04-005).  ``RM.INVALID`` and
``RM.CLOSED`` in report phase do not: a receiver may declare a bare report
invalid or closed without ever promoting it to a case.

Every node that *requires* the case reads ``/case_id`` from the blackboard
rather than looking the case up itself; the single lookup site is
:class:`~vultron.core.behaviors.case.nodes.case_lookup.RequireCaseForReport`
(ARCH-15-004).

Split by shape (CS-18-005): ``report_phase`` holds the report-phase
transitions and their base class, and ``valid`` the RM.VALID transition.
"""

from vultron.core.behaviors.report.nodes.rm_transitions.report_phase import (
    TransitionRMtoClosed,
    TransitionRMtoInvalid,
)
from vultron.core.behaviors.report.nodes.rm_transitions.valid import (
    TransitionRMtoValid,
)

__all__ = [
    "TransitionRMtoClosed",
    "TransitionRMtoInvalid",
    "TransitionRMtoValid",
]
