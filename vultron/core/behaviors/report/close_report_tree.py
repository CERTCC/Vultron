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
``OtherCloseCriteriaMet`` call-out point as an injection seam for a future
Close Readiness Monitoring Sentinel (see epic #1147 / #1143 Sentinel agent
type).

**Design note — no autonomous close path**

Case closure in Vultron is always Case Owner-triggered: the Case Owner (or
Case Manager acting on their behalf) issues a ``Leave(VulnerabilityCase)``
activity, which flows through :func:`create_close_report_trigger_tree`.
There is no autonomous close path because:

- Standard simulator closure criteria (CS.DEPLOYED, RM.DEFERRED, RM.INVALID)
  are necessary but not sufficient — the Case Owner judges when to close.
- ``CS.P`` already triggers embargo teardown; wiring ``EM.EXITED + CS.P`` as
  an auto-close signal would close every case on public disclosure.

This tree is therefore a **seam-only stub**, not called by any use case.
Its intended future use is: a Sentinel backend injected via
``other_close_criteria_factory`` that observes case state, detects that
objective close conditions are met, and posts an observational note to the
Case Owner.  The Case Owner then issues the ``Leave`` voluntarily.

``PreCloseAction`` (the pre-close Actuator) belongs in
:func:`create_close_report_trigger_tree`, wired between the
``CheckReportNotClosed`` guard and ``TransitionRMtoClosed`` (issue #1253 T1).

Nodes hosted here
-----------------
- ``OtherCloseCriteriaMet`` — Evaluator seam; DETERMINISTIC default =
  ``AlwaysFail`` (correct: seam fires only when a real Sentinel is injected)

References
----------
- IDEA-1253: planning rationale for this design
- ADR-0025: ``docs/adr/0025-call-out-point-abstraction-layer.md``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-18-004
- Notes: ``notes/bt-fuzzer-rm-closure.md`` § "Design Rationale"
"""

import logging
from typing import TYPE_CHECKING

import py_trees

if TYPE_CHECKING:
    from vultron.core.behaviors.call_out.bundles.close_report import (
        CloseReportCallOutBundle,
    )

logger = logging.getLogger(__name__)


def create_close_report_tree(
    case_id: str,
    call_out: "CloseReportCallOutBundle | None" = None,
) -> py_trees.behaviour.Behaviour:
    """Build the Close Readiness Monitoring seam tree.

    Exposes the ``OtherCloseCriteriaMet`` Evaluator call-out point as the
    injection seam for a future Close Readiness Monitoring Sentinel.  The
    DETERMINISTIC default (``AlwaysFail``) is correct: this tree should not
    fire unless a real Sentinel backend is injected — case closure is always
    Case Owner-triggered via :func:`create_close_report_trigger_tree`.

    The ``pre_close_action_factory`` bundle field is not wired here;
    ``PreCloseAction`` belongs in :func:`create_close_report_trigger_tree`
    (see IDEA-1253 T1 and ``notes/bt-fuzzer-rm-closure.md``).

    Args:
        case_id: ID of VulnerabilityCase being processed.
        call_out: Bundle of call-out backend factories for this domain.
            Defaults to
            :data:`~vultron.core.behaviors.call_out.bundles.close_report.CLOSE_REPORT_DETERMINISTIC`
            (BT-23-003, BT-23-005).

    Returns:
        Root node of the close readiness monitoring seam tree.
    """
    from vultron.core.behaviors.call_out.bundles.close_report import (
        CLOSE_REPORT_DETERMINISTIC,
    )

    bundle = call_out if call_out is not None else CLOSE_REPORT_DETERMINISTIC
    root = bundle.other_close_criteria_factory("OtherCloseCriteriaMet")
    logger.info("Created CloseReadinessMonitoringBT for case=%s", case_id)
    return root
