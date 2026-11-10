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

"""The CASE_MANAGER's answers to an ``Accept`` of an embargo not available.

What decides the answer to an ``Accept(Invite(EmbargoEvent))`` is whether
the embargo it names is still available, not whether the Accept arrived
before its RSVP deadline (EMB-17-001, MSM-07-012).  The one test is
:func:`~vultron.core.services.embargo_availability.embargo_availability`.
An available embargo is honoured: the Accept is recorded, on time or late
(EMB-17-002, MSM-07-003).  The other two answers are diversions of the
Accept tree (CLP-10-026), which declares the CASE_MANAGER path alone, so
they run only there (HP-01-038)::

    NeverHeldEmbargoFault (DiversionStage)
    ├─ EmbargoAvailabilityIs(NEVER_HELD)
    └─ EmitEmbargoAcceptFaultNode        # Create(ProcessingFault), MSM-07-039

    UnavailableEmbargoRefusal (DiversionStage)
    ├─ EmbargoAvailabilityIs(UNAVAILABLE)
    └─ UnavailableEmbargoRefusalAct (ActTransaction)
       ├─ EmitRefusalNoticeNode           # Reject(Accept), CLP-05-001
       └─ ReinviteWhereTermsHeld (Selector)
          ├─ Inverter(CaseHoldsAvailableTerms)   # no terms: notice alone
          └─ ReinviteRefusedAccepterNode  # EMB-17-003, committed (EMB-17-013)

A never-held embargo means the sender's view of the case is wrong, so the
Accept is not understood rather than declined: it gets a processing fault and
no refusal notice, and nothing is ledgered (MSM-05-001, ASK-07-008).  An
embargo the register holds but that is no longer available makes the Accept
moot: it is refused uncommitted with the refusal notice, and the accepter is
asked about the case's current terms when it holds any.  The notice and the
re-invite are one act, so a failed re-invite sends no notice either
(CLP-07-016).  The refusal refuses the Accept, never the accepter's
participation (EMB-17-006, EMB-17-008).
"""

from typing import TYPE_CHECKING

import py_trees

from vultron.core.behaviors.act_transaction import ActTransaction
from vultron.core.behaviors.case.nodes.diversion_stage import Diversion
from vultron.core.behaviors.case.nodes.refusal_notice import (
    EmitRefusalNoticeNode,
)
from vultron.core.behaviors.embargo.nodes.accept_availability import (
    CaseHoldsAvailableTermsNode,
    EmbargoAvailabilityIsNode,
)
from vultron.core.behaviors.embargo.nodes.invite_fault import (
    EmitEmbargoAcceptFaultNode,
)
from vultron.core.behaviors.embargo.nodes.reinvite import (
    ReinviteRefusedAccepterNode,
)
from vultron.core.models.fault_classes import (
    VULTRON_FAILURE_ACCEPT_OF_EMBARGO_NEVER_HELD,
)
from vultron.core.services.embargo_availability import EmbargoAvailability

if TYPE_CHECKING:
    from datetime import datetime

    from vultron.config.actor import ActorConfig

__all__ = [
    "NEVER_HELD_EMBARGO_FAULT",
    "UNAVAILABLE_EMBARGO_REFUSAL",
    "never_held_embargo_fault",
    "unavailable_embargo_refusal",
]

#: The diversion that answers an Accept of an embargo never held.
NEVER_HELD_EMBARGO_FAULT = "NeverHeldEmbargoFault"

#: The diversion that refuses an Accept of an embargo no longer available.
UNAVAILABLE_EMBARGO_REFUSAL = "UnavailableEmbargoRefusal"


def never_held_embargo_fault(
    *, case_id: str, embargo_id: str, now: "datetime"
) -> Diversion:
    """Answer an Accept of an embargo the register never held (MSM-07-039).

    The Accept tree passes it first among its precondition guards: an Accept
    naming no embargo of the case has no consent row to repeat and no
    Invite of the case to refuse, so no later guard can judge it.

    Args:
        case_id: The case the Accept names.
        embargo_id: The embargo the Accept names.
        now: The CASE_MANAGER's clock.
    """
    return Diversion(
        name=NEVER_HELD_EMBARGO_FAULT,
        condition=EmbargoAvailabilityIsNode(
            case_id=case_id,
            embargo_id=embargo_id,
            availability=EmbargoAvailability.NEVER_HELD,
            now=now,
        ),
        effects=(
            EmitEmbargoAcceptFaultNode(
                failure_class=VULTRON_FAILURE_ACCEPT_OF_EMBARGO_NEVER_HELD,
                case_id=case_id,
            ),
        ),
    )


def unavailable_embargo_refusal(
    *,
    case_id: str,
    embargo_id: str,
    accepting_actor_id: str,
    answers: str | None,
    now: "datetime",
    actor_config: "ActorConfig | None" = None,
) -> Diversion:
    """Refuse an Accept of an embargo held but no longer available (MSM-07-012).

    The Accept tree passes it after its repeat guard and its P/X/A refusal:
    a repeat of an Accept already recorded changes nothing and is not
    refused (CM-13-005), and with P/X/A set the Accept is answered with a
    ``Reject`` of its Invite instead (EMB-02-004).

    Args:
        case_id: The case the Accept names.
        embargo_id: The embargo the Accept names.
        accepting_actor_id: The Accept's sender, whom the notice answers and
            the re-invite asks.
        answers: The Accept's id; the re-invite's id derives from it, so a
            redelivery rebuilds the same Invite (OX-06-002).
        now: The CASE_MANAGER's clock, against which end times are read.
        actor_config: The CASE_MANAGER's configuration (RSVP window).
    """
    condition = EmbargoAvailabilityIsNode(
        case_id=case_id,
        embargo_id=embargo_id,
        availability=EmbargoAvailability.UNAVAILABLE,
        now=now,
    )
    reinvite_where_terms_held = py_trees.composites.Selector(
        name="ReinviteWhereTermsHeld",
        memory=False,
        children=[
            py_trees.decorators.Inverter(
                name="NoAvailableTerms",
                child=CaseHoldsAvailableTermsNode(case_id=case_id, now=now),
            ),
            ReinviteRefusedAccepterNode(
                case_id=case_id,
                invitee_id=accepting_actor_id,
                now=now,
                actor_config=actor_config,
                answers=answers,
            ),
        ],
    )
    return Diversion(
        name=UNAVAILABLE_EMBARGO_REFUSAL,
        condition=condition,
        effects=(
            ActTransaction(
                name="UnavailableEmbargoRefusalAct",
                children=[
                    EmitRefusalNoticeNode(
                        case_id=case_id,
                        name="EmitRefusalNotice",
                        reason_from=condition,
                    ),
                    reinvite_where_terms_held,
                ],
            ),
        ),
    )
