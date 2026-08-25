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

"""
Report validation behavior tree composition.

:func:`create_validate_report_subtree` is the **single** definition of the
validate-report workflow.  Both the trigger-side tree
(:func:`create_validate_report_tree`) and the received-side tree
(``received_report_trees.create_validate_report_received_tree``) are built from
it; there is no hand-mirrored copy to keep in sync (ARCH-15-004, ISSUE-2548).

Structure:

    ValidateReportBT (Selector, memory=False)
    ├─ CheckRMStateValid                     # idempotent early exit (ID-04-004)
    └─ ValidationFlow (Sequence, memory=False)
       ├─ CheckRMStateReceivedOrInvalid      # RM precondition
       ├─ EvaluateReportCredibility          # call-out point
       ├─ EvaluateReportValidity             # call-out point
       ├─ RequireCaseForReport               # case must be in *this* store
       ├─ EnsureEmbargoExists                # embargo present (DUR-07-004)
       └─ ValidationActions (Sequence, memory=False)
          ├─ MaybeEmitValidateReport         # only when emit=True
          └─ TransitionRMtoValid             # case participant, then RM latch

Why the guards precede the actions
----------------------------------
``RM.VALID`` is case-scoped: DUR-07-004 requires an established embargo, and
engage-case reads the participant's case-scoped RM state.  Both live on the
``VulnerabilityCase``, which reaches a non-CaseActor participant only as a
``Create(VulnerabilityCase)`` replica (ADR-0041, ADR-0072, PCR-01-003).  Every
precondition that depends on that replica is therefore checked *before* the
first write, so a tick that runs ahead of the replica does nothing at all rather
than half of the transition (ID-04-005, ISSUE-2548).

Previously the root had two branches — ``EmitAndValidate`` and a structurally
duplicated ``ValidationOrShortcutFallback`` — and ``TransitionRMtoValid`` ran
before ``EnsureEmbargoExists``.  When the case was absent, the first branch
wrote the report-phase ``RM.VALID`` latch and then failed on the embargo check;
the root Selector fell through to the duplicate branch, whose
``CheckRMStateValid`` read the latch the failed branch had just written and
returned SUCCESS.  The tree reported success, the participant stayed at
``RECEIVED``, and the latch made every subsequent ``validate-report`` short-
circuit — so the two halves could never reconverge.

Per ADR-0015, case and participant creation occurs at RM.RECEIVED (in
``SubmitReportReceivedUseCase`` via ``create_receive_report_case_tree``).
``ValidationActions`` only transitions state and emits; it never creates a case.

``validate-report`` advances RM to VALID only.  The engage/defer decision
(RM → ACCEPTED or RM → DEFERRED) is a distinct, explicit protocol step driven by
a separate ``engage-case`` or ``defer-case`` trigger.  These are intentionally
separate: a receiver may validate a report and still choose to defer it without
ever engaging.

Phase 1 simplifications:
- No invalidation fallback (validation always succeeds)
- No information gathering loop (no data collection)
- Deterministic call-out points (always SUCCESS)

Future enhancements (Phase 2+):
- Add InvalidateReport fallback sequence
- Implement real policy evaluation logic
- Wire ``call_out.gather_info_factory`` into an EnoughInfoOrGather Selector

Per specs/behavior-tree-integration.yaml BT-06 requirements.
"""

import logging
from typing import TYPE_CHECKING

import py_trees

from vultron.core.behaviors.case.nodes.case_lookup import RequireCaseForReport
from vultron.core.behaviors.report.nodes import (
    CheckRMStateReceivedOrInvalid,
    CheckRMStateValid,
    EnsureEmbargoExists,
    TransitionRMtoValid,
)
from vultron.core.behaviors.report.nodes.emit import EmitValidateReportActivity

if TYPE_CHECKING:
    from vultron.core.behaviors.call_out.bundles.validation import (
        ValidationCallOutBundle,
    )

logger = logging.getLogger(__name__)


def create_validate_report_subtree(
    report_id: str,
    offer_id: str,
    *,
    sender_actor_id: str | None = None,
    call_out: "ValidationCallOutBundle | None" = None,
    captured: dict | None = None,
    emit: bool = True,
    name: str = "ValidateReportBT",
) -> py_trees.behaviour.Behaviour:
    """Build the canonical validate-report subtree.

    This is the one definition of the workflow; callers differ only in the
    keyword arguments below.  Because a py_trees node may not have two parents,
    call this factory once per tree — each call yields independent instances.

    Args:
        report_id: ID of the VulnerabilityReport to validate.
        offer_id: ID of the Offer activity that carried the report.
        sender_actor_id: Actor whose RM state advances, when it is not the
            blackboard ``actor_id``.  Pass the message sender on the received
            side, where the tree runs under ``receiving_actor_id`` (ADR-0022).
        call_out: Bundle supplying the credibility / validity call-out points.
            Defaults to ``VALIDATION_DETERMINISTIC``.  The produced nodes must
            honour the blackboard contract of ``EvaluateReportCredibility`` /
            ``EvaluateReportValidity``.
        captured: Optional dict; ``captured["activity"]`` is set to the
            serialised emitted activity on success (DL-06-001, AC-1).
        emit: When ``True``, ``ValidationActions`` starts with a
            ``Read(Offer(Report))``-style emit to the Case Actor so its inbox
            can write the canonical ledger entry (ADR-0021 CLP-10-001).  Pass
            ``False`` on the received side: the activity being handled *is* that
            message, and re-emitting it would loop.
        name: Root node name.

    Returns:
        Root node of the validation subtree (a Selector).
    """
    from vultron.core.behaviors.call_out.bundles.validation import (
        VALIDATION_DETERMINISTIC,
    )

    bundle = call_out if call_out is not None else VALIDATION_DETERMINISTIC

    action_children: list[py_trees.behaviour.Behaviour] = []
    if emit:
        # The emit is masked by a Success fallback because emit failure was
        # already tolerated by design: ValidateCaseUseCase builds its BTBridge
        # without a TriggerActivityPort, and ADR-0066 gives the outbox its own
        # retry path.  Without the mask those callers would regress to FAILURE.
        action_children.append(
            py_trees.composites.Selector(
                name="MaybeEmitValidateReport",
                memory=False,
                children=[
                    EmitValidateReportActivity(
                        offer_id=offer_id,
                        report_id=report_id,
                        captured=captured,
                    ),
                    py_trees.behaviours.Success(name="NoEmitFallback"),
                ],
            )
        )
    action_children.append(
        TransitionRMtoValid(
            report_id=report_id,
            offer_id=offer_id,
            sender_actor_id=sender_actor_id,
        )
    )

    validation_actions = py_trees.composites.Sequence(
        name="ValidationActions",
        memory=False,
        children=action_children,
    )

    validation_flow = py_trees.composites.Sequence(
        name="ValidationFlow",
        memory=False,
        children=[
            CheckRMStateReceivedOrInvalid(
                report_id=report_id, sender_actor_id=sender_actor_id
            ),
            bundle.credibility_factory("EvaluateReportCredibility"),
            bundle.validity_factory("EvaluateReportValidity"),
            RequireCaseForReport(report_id=report_id),
            EnsureEmbargoExists(report_id=report_id),
            validation_actions,
        ],
    )

    root = py_trees.composites.Selector(
        name=name,
        memory=False,
        children=[
            CheckRMStateValid(
                report_id=report_id, sender_actor_id=sender_actor_id
            ),
            validation_flow,
        ],
    )
    logger.debug(
        "Created %s for report=%s offer=%s sender=%s emit=%s",
        name,
        report_id,
        offer_id,
        sender_actor_id,
        emit,
    )
    return root


def create_validate_report_tree(
    report_id: str,
    offer_id: str,
    captured: dict | None = None,
    call_out: "ValidationCallOutBundle | None" = None,
) -> py_trees.behaviour.Behaviour:
    """Create the trigger-side behavior tree for the report validation workflow.

    Thin wrapper over :func:`create_validate_report_subtree` with ``emit=True``:
    the operator triggered this, so the ``validate-report`` activity must be
    sent to the Case Actor (CASE_MANAGER participant) whose inbox executes the
    guarded commit (ADR-0021 CLP-10-001, CLP-10-002, CLP-10-003).

    Advances RM state to VALID only.  The engage/defer decision is a separate,
    explicit protocol step the operator must trigger via ``engage-case`` or
    ``defer-case``.

    Args:
        report_id: ID of VulnerabilityReport to validate.
        offer_id: ID of Offer activity containing the report.
        captured: Optional dict; ``captured["activity"]`` is set to the
            serialised activity dict on success (DL-06-001, AC-1).
        call_out: Bundle supplying the credibility / validity call-out points.

    Returns:
        Root node of the validation behavior tree (Selector).

    Example:
        >>> tree = create_validate_report_tree(
        ...     report_id="https://example.org/reports/CVE-2024-001",
        ...     offer_id="https://example.org/activities/offer-123"
        ... )
        >>> from vultron.core.behaviors.bridge import BTBridge
        >>> bridge = BTBridge()
        >>> result = bridge.execute_with_setup(
        ...     tree,
        ...     actor_id="https://example.org/actors/vendor",
        ...     datalayer=get_datalayer("https://example.org/actors/vendor")
        ... )
        >>> print(result.status)
        Status.SUCCESS
    """
    tree = create_validate_report_subtree(
        report_id=report_id,
        offer_id=offer_id,
        call_out=call_out,
        captured=captured,
        emit=True,
    )
    logger.info(
        "Created ValidateReportBT for report=%s, offer=%s", report_id, offer_id
    )
    return tree
