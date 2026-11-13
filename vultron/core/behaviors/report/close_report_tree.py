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
"""Close Readiness Monitoring seam tree.

This module provides :func:`create_close_report_tree`, which exposes the
``OtherCloseCriteriaMet`` call-out point as an injection seam for an Evaluator
capability that judges whether close conditions are met (epic #1147).

A Close Readiness Monitoring Sentinel (#1143) is not that capability.  A
Sentinel is a call-in pattern, not a capability shape: it watches case state on
its own initiative and acts through a trigger or a protocol message, so it is
never injected into a call-out factory (ADR-0097, BT-18-013).

**Design note — no autonomous close path**

Case closure in Vultron is always Case Owner-triggered: the Case Owner issues
a ``Leave(VulnerabilityCase)`` activity through the ``leave-case`` trigger
(:class:`~vultron.core.use_cases.triggers.case.leave.SvcLeaveCaseUseCase`,
TRIG-13-001), as does any participant leaving the case.  Calling that trigger
is the decision ``OtherCloseCriteriaMet`` used to ask for, so the call-out is
superseded (ADR-0145) and stays here unwired.
There is no autonomous close path because:

- Standard simulator closure criteria (CS.DEPLOYED, RM.DEFERRED, RM.INVALID)
  are necessary but not sufficient — the Case Owner judges when to close.
- ``CS.P`` already triggers embargo teardown; wiring ``EM.EXITED + CS.P`` as
  an auto-close signal would close every case on public disclosure.

This tree is therefore a **seam-only stub**, not called by any use case.
A deployment that wants close-readiness advice does not need it: a Sentinel
that observes case state, detects that objective close conditions are met and
posts an observational note to the Case Owner acts on its own, outside any
tree.  The Case Owner then issues the ``Leave`` voluntarily.

``PreCloseAction`` (the pre-close Actuator) is wired in
:func:`~vultron.core.behaviors.case.leave_case_trigger_tree.create_leave_case_trigger_tree`,
after its embargo guard and before the Leave is sent (TRIG-13-002).

Nodes hosted here
-----------------
- ``OtherCloseCriteriaMet`` — Evaluator seam; DETERMINISTIC default =
  ``AlwaysFail`` (correct: the seam answers yes only when a real Evaluator
  capability is injected)

References
----------
- IDEA-1253: planning rationale for this design
- ADR-0025: ``docs/adr/0025-call-out-point-abstraction-layer.md``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-18-004
- Catalog: ``docs/developer/reference/bt-fuzzer/rm-closure.md``
  § "Closure model"
"""

import logging
from typing import TYPE_CHECKING

import py_trees

from vultron.core.behaviors.call_out.bundles.close_report import (
    CLOSE_REPORT_DETERMINISTIC,
)

if TYPE_CHECKING:
    from vultron.core.behaviors.call_out.bundles.close_report import (
        CloseReportCallOutBundle,
    )

logger = logging.getLogger(__name__)


def create_close_report_tree(
    case_id: str,
    call_out: CloseReportCallOutBundle | None = None,
) -> py_trees.behaviour.Behaviour:
    """Build the Close Readiness Monitoring seam tree.

    Exposes the ``OtherCloseCriteriaMet`` Evaluator call-out point as an
    injection seam for an Evaluator capability.  The DETERMINISTIC default
    (``AlwaysFail``) is correct: this tree should not answer yes unless a real
    Evaluator backend is injected — case closure is always Case
    Owner-triggered, through the ``leave-case`` trigger (TRIG-13-001).

    The ``pre_close_action_factory`` bundle field is not wired here;
    ``PreCloseAction`` is wired in the ``leave-case`` trigger tree
    (TRIG-13-002).

    Args:
        case_id: ID of VulnerabilityCase being processed.
        call_out: Bundle of call-out backend factories for this domain.
            Defaults to
            :data:`~vultron.core.behaviors.call_out.bundles.close_report.CLOSE_REPORT_DETERMINISTIC`
            (BT-23-003, BT-23-005).

    Returns:
        Root node of the close readiness monitoring seam tree.
    """
    bundle = call_out if call_out is not None else CLOSE_REPORT_DETERMINISTIC
    root = bundle.other_close_criteria_factory("OtherCloseCriteriaMet")
    logger.info("Created CloseReadinessMonitoringBT for case=%s", case_id)
    return root
