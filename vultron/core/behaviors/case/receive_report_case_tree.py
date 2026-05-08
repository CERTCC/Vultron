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
Receive-report case-creation behavior tree composition.

This module composes the workflow for creating a ``VulnerabilityCase`` at
report receipt (RM.RECEIVED), as mandated by ADR-0015.  It is intended to
replace the inline case-creation sequence currently embedded in the
``ValidateReportBT`` (validate_tree.py) and to be invoked by
``SubmitReportReceivedUseCase`` as soon as the vendor receives the report.

The tree is structurally similar to the ValidationActions subsequence of
``ValidateReportBT`` but differs in two important ways:

1. No ``TransitionRMtoValid`` — this tree runs at RM.RECEIVED, not RM.VALID.
2. The vendor (receiver) participant is seeded at ``RM.RECEIVED``
   (``initial_rm_state=RM.RECEIVED``) rather than ``RM.VALID``.

Structure (CM-14 canonical order):

    ReceiveReportCaseBT (Selector)
    ├─ CheckCaseExistsForReport          # Early exit if case already created
    └─ ReceiveReportCaseFlow (Sequence)
       ├─ CreateCaseNode                 # Create VulnerabilityCase; write case_id
       ├─ CreateCaseOwnerParticipant     # Receiver participant (RM.RECEIVED)
       ├─ InitializeDefaultEmbargoNode   # Create default embargo; seed owner SIGNATORY
       ├─ CreateCaseActivity             # Queue Create(Case) BEFORE reporter add
       ├─ UpdateActorOutbox              # Flush Create(Case) to outbox
       ├─ CreateCaseParticipantNode      # Reporter participant (RM.ACCEPTED); seed SIGNATORY
       ├─ CreateCaseActorNode            # Spawn Case Actor; write case_actor_id
       ├─ SendOfferCaseManagerRoleNode   # Offer CASE_MANAGER role to Case Actor
       ├─ UpdateActorOutbox (Offer)      # Flush Offer to outbox
       └─ CommitCaseLogEntryNode         # Log entry → Announce fan-out (SYNC-02-002)

Note: ``CreateCaseActivity`` and ``UpdateActorOutbox`` are intentionally placed
*before* ``CreateCaseParticipantNode``.  This ensures that the reporter
receives the ``Create(Case)`` notification before the ``Add(CaseParticipant)``
notification.  If the two activities were queued in the opposite order, the
reporter would receive an ``Add(CaseParticipant)`` for a case it has not yet
seen, triggering "case not found" warnings on the reporter side.

Note: ``CreateCaseOwnerParticipant`` MUST run before
``InitializeDefaultEmbargoNode`` (CM-14-002): the embargo requires at least
one participant (the owner) to exist in the case before it is activated.
``InitializeDefaultEmbargoNode`` seeds the owner participant as
``PEC.SIGNATORY`` (CM-14-003).  ``CreateCaseParticipantNode`` seeds any
subsequently added participant as ``PEC.SIGNATORY`` when an active embargo
already exists (CM-14-005).

Per specs/case-management.yaml CM-12, CM-14 (ADR-0015) and
docs/adr/0015-create-case-at-report-receipt.md.
"""

import logging

import py_trees

from vultron.core.behaviors.case.nodes import (
    CheckCaseExistsForReport,
    CommitCaseLogEntryNode,
    CreateCaseActorNode,
    CreateCaseOwnerParticipant,
    CreateCaseParticipantNode,
    InitializeDefaultEmbargoNode,
    SendOfferCaseManagerRoleNode,
    UpdateActorOutbox,
)
from vultron.core.behaviors.report.nodes import (
    CreateCaseActivity,
    CreateCaseNode,
)
from vultron.core.models.actor_config import ActorConfig
from vultron.core.states.rm import RM
from vultron.core.states.roles import CVDRole

logger = logging.getLogger(__name__)


def create_receive_report_case_tree(
    report_id: str,
    offer_id: str,
    reporter_actor_id: str,
    actor_config: ActorConfig | None = None,
) -> py_trees.behaviour.Behaviour:
    """
    Create behavior tree for case creation at report receipt.

    Given a ``VulnerabilityReport`` ID, the ID of the ``Offer`` activity
    that delivered it, the reporter's actor ID, and an optional actor
    configuration, builds and returns a behavior tree that:

    - Creates a ``VulnerabilityCase`` linked to the report.
    - Creates a default embargo and attaches it to the case.
    - Creates a ``VultronParticipant`` for the receiving actor (case owner)
      at ``rm_state=RM.RECEIVED``, with roles from
      ``actor_config.default_case_roles`` plus ``CVDRole.CASE_OWNER``.
    - Creates a ``VultronParticipant`` for the reporting actor (reporter) at
      ``rm_state=RM.ACCEPTED`` (reusing the report-phase status if present).
    - Queues a ``Create(Case)`` activity to the actor's outbox so the reporter
      receives a copy of the case.
    - Queues an ``Add(CaseParticipant)`` activity for the reporter so
      downstream actors are notified with a fully typed object (satisfying
      MV-09-001).

    The root is a ``Selector`` so that if a fully-initialised case already
    exists for this report the tree succeeds immediately (idempotency).

    Args:
        report_id: ID of the ``VulnerabilityReport`` to link to the case.
        offer_id: ID of the ``Offer`` activity that delivered the report
                  (used to determine addressees for the Create(Case) activity).
        reporter_actor_id: Actor ID of the party who submitted the report.
            Passed as a constructor argument so the BT node is not coupled to
            the DataLayer offer lookup.
        actor_config: Optional actor configuration carrying CVD-role
                      defaults for the receiving actor.  When ``None`` the
                      case-owner participant receives only the
                      ``CVDRole.CASE_OWNER`` role (CFG-07-002, CFG-07-004).

    Returns:
        Root node of the receive-report case-creation behavior tree.

    Example:
        >>> tree = create_receive_report_case_tree(
        ...     report_id="https://example.org/reports/CVE-2024-001",
        ...     offer_id="https://example.org/activities/offer-123",
        ...     reporter_actor_id="https://example.org/actors/reporter",
        ... )
        >>> from vultron.core.behaviors.bridge import BTBridge
        >>> bridge = BTBridge()
        >>> result = bridge.execute_with_setup(
        ...     tree,
        ...     actor_id="https://example.org/actors/vendor",
        ... )
        >>> print(result.status)
        Status.SUCCESS
    """
    receive_report_case_flow = py_trees.composites.Sequence(
        name="ReceiveReportCaseFlow",
        memory=False,
        children=[
            CreateCaseNode(report_id=report_id),
            CreateCaseOwnerParticipant(
                report_id=report_id,
                initial_rm_state=RM.RECEIVED,
                actor_config=actor_config,
            ),
            InitializeDefaultEmbargoNode(),
            # Create(Case) MUST be queued before Add(CaseParticipant) so that
            # the reporter actor receives the case notification first
            # (D5-7-MSGORDER-1).
            CreateCaseActivity(report_id=report_id, offer_id=offer_id),
            UpdateActorOutbox(),
            CreateCaseParticipantNode(
                actor_id=reporter_actor_id,
                roles=[CVDRole.FINDER, CVDRole.REPORTER],
                report_id=report_id,
            ),
            # Spawn the Case Actor entity after all participants are registered
            # so the Offer can reference a complete case snapshot (DEMOMA-08-002).
            # CreateCaseActorNode reads case_id from the blackboard and writes
            # case_actor_id for SendOfferCaseManagerRoleNode.
            CreateCaseActorNode(),
            SendOfferCaseManagerRoleNode(),
            UpdateActorOutbox(name="UpdateActorOutboxOffer"),
            # case_id is not known at build time; CreateCaseNode writes it to
            # the blackboard so CommitCaseLogEntryNode can read it here.
            CommitCaseLogEntryNode(),
        ],
    )

    root = py_trees.composites.Selector(
        name="ReceiveReportCaseBT",
        memory=False,
        children=[
            CheckCaseExistsForReport(report_id=report_id),
            receive_report_case_flow,
        ],
    )

    logger.debug(
        "Created ReceiveReportCaseBT for report=%s, offer=%s, reporter=%s",
        report_id,
        offer_id,
        reporter_actor_id,
    )
    return root
