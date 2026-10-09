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

"""Blackboard inputs for the Reporter's proposed embargo terms (EP-04-004).

The ``Create(CaseProposal)`` use case reads the Reporter's proposed
``EmbargoEvent`` from the received event (CP-01-008) and seeds two blackboard
keys for ``InitializeDefaultEmbargoNode``: the remaining duration, which the
shortest-wins comparison reads (EP-04-003), and the event itself, which
``CreateEmbargoEventNode`` keeps when the proposal wins.  Terms that are not a
proposal for *this* report — already run out, or stated about some other
subject — are logged and left off, so the case is still created under the
owner's default (receive side, Postel's maxim) rather than refused.
"""

import logging
from datetime import timedelta
from typing import Any

from vultron.core.models._helpers import now_utc
from vultron.core.models.events.case_proposal import (
    CreateCaseProposalReceivedEvent,
)

logger = logging.getLogger(__name__)


def sender_embargo_proposal_inputs(
    request: CreateCaseProposalReceivedEvent,
) -> dict[str, Any]:
    """Return the blackboard inputs for the Reporter's proposed terms, or ``{}``.

    The duration is measured from now because that is when the embargo it
    competes with would start.  A proposal whose ``context`` is not the
    proposal's report is not terms for this report (EP-04-009): the factory
    refuses it on the sending side, and the receiving side reads it as no
    proposal rather than adopting terms stated about something else.
    """
    proposal = request.proposed_embargo
    if proposal is None:
        return {}
    report_id = request.inner_object_id
    if proposal.context != report_id:
        logger.warning(
            "create_case_proposal_received: the Reporter's proposed embargo"
            " '%s' for proposal '%s' is about %r, not the proposal's report"
            " %r; creating the case without it (EP-04-009)",
            proposal.id_,
            request.proposal_id,
            proposal.context,
            report_id,
        )
        return {}
    remaining = proposal.end_time - now_utc()
    if remaining <= timedelta(0):
        logger.warning(
            "create_case_proposal_received: the Reporter's proposed"
            " embargo '%s' for proposal '%s' ends at %s, already in the"
            " past; creating the case without it (EP-04-004)",
            proposal.id_,
            request.proposal_id,
            proposal.end_time.isoformat(),
        )
        return {}
    return {
        "sender_proposed_embargo_duration": remaining,
        "sender_proposed_embargo": proposal,
    }
