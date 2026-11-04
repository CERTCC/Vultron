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

"""Received-side BTs for ``CreateReport`` and ``AckReport``.

``CreateReport`` stores the VulnerabilityReport; ``AckReport`` checks the
acknowledgement's sender.  Intake archives each received activity first
(CLP-10-017).
"""

import logging

import py_trees

from vultron.core.behaviors.case.nodes.received_path import (
    ReceivedPath,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.report.nodes.storage import (
    StoreReportNode,
)
from vultron.core.behaviors.sender_entitlement import SenderRule
from vultron.core.behaviors.sender_guard import (
    ReportOfferRequest,
    SenderCheckContext,
)
from vultron.core.models.events.report import (
    AckReportReceivedEvent,
    CreateReportReceivedEvent,
)

logger = logging.getLogger(__name__)


def create_report_received_tree(
    request: CreateReportReceivedEvent,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for the CreateReportReceived workflow.

    Handles receipt of a ``Create(VulnerabilityReport)`` activity.

    Steps (Sequence via :func:`create_receive_activity_tree`):
    1. Intake archives the ``Create`` as received (CLP-10-036), so a refused
       delivery still leaves its record (CLP-10-018).
    2. Store VulnerabilityReport idempotently.

    No ledger commit: the tree carries no case context (``case_id=None``).

    Args:
        request: The parsed inbound domain event.

    Returns:
        Root node of the ``CreateReportReceivedBT`` Sequence.
    """
    report_id = request.report_id or ""
    activity_id = request.activity_id or ""

    root = create_receive_activity_tree(
        name="CreateReportReceivedBT",
        case_id=None,
        # A report precedes any case, so its receiver holds none when the
        # stage asks (HP-01-041, HP-01-038).
        paths={ReceivedPath.NO_CASE},
        precondition_guards=[],
        replica_effects=[
            StoreReportNode(
                report_id=report_id,
                report_obj=request.report,
            ),
        ],
    )
    logger.debug(
        "Created CreateReportReceivedBT for report=%s activity=%s",
        report_id,
        activity_id,
    )
    return root


def create_ack_report_received_tree(
    request: AckReportReceivedEvent,
    *,
    sender_rule: SenderRule,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for the AckReportReceived workflow.

    Handles receipt of a ``Read(Offer(VulnerabilityReport))`` (AckReport, RK).  RK goes
    from an actor the ``Offer(VulnerabilityReport)`` was addressed to, to the
    reporter, and never to the CASE_MANAGER (RMB-08-005), so the tree has no
    case context, no ledger commit and nothing to emit.

    Steps (Sequence via :func:`create_receive_activity_tree`):

    1. Intake archives the ``Read`` as received (CLP-10-036), so a refused
       acknowledgement still leaves its record (CLP-10-018).
    2. The sender guard the factory composes from *sender_rule* refuses a
       sender that is not an addressee of the Offer this store recorded
       (``SenderIsOfferAddresseeNode``; RMB-08-004, HP-01-006).

    An acknowledgement changes no state (RMB-08-001), so an admitted RK
    writes nothing past intake.

    Args:
        request: The parsed inbound domain event.
        sender_rule: The use case's declared sender rule (HP-01-008).

    Returns:
        Root node of the ``AckReportReceivedBT`` Sequence.
    """
    root = create_receive_activity_tree(
        name="AckReportReceivedBT",
        case_id=None,
        # The acknowledgement goes to the reporter and never to the
        # CASE_MANAGER, and the tree carries no case context, so its
        # receiver holds no case for it (RMB-08-005, HP-01-038, HP-01-041).
        paths={ReceivedPath.NO_CASE},
        precondition_guards=[],
        sender_rule=sender_rule,
        sender_context=SenderCheckContext(
            sender_id=request.actor_id,
            request=ReportOfferRequest(offer_id=request.offer_id),
        ),
    )
    logger.debug(
        "Created AckReportReceivedBT for activity=%s offer=%s",
        request.activity_id,
        request.offer_id,
    )
    return root
