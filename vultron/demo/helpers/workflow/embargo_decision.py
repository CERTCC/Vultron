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

"""The case owner's decision on a proposed embargo (ADR-0122, ADR-0180)."""

import logging

from vultron.demo.utils import (
    DataLayerClient,
    logfmt,
    post_to_inbox_and_wait,
)
from vultron.wire.as2.factories import (
    activate_embargo_activity,
    reject_embargo_proposal_activity,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

logger = logging.getLogger(__name__)


def _send_owner_embargo_decision(
    client: DataLayerClient,
    owner: as_Actor,
    case_manager_id: str,
    case: as_VulnerabilityCase,
    embargo: as_EmbargoEvent,
    proposal_id: str,
    *,
    accept: bool,
    summary: str,
) -> None:
    """Send the case owner's decision on a proposal to the CASE_MANAGER.

    The owner activates with ``Add`` and rejects with ``Reject`` of the
    ``EmbargoEvent`` itself, the case as ``target`` (ADR-0180) — never an
    answer to the Invite that proposed it, which is only the owner's own
    consent.  Both name that Invite, *proposal_id*, in ``inReplyTo``.
    """
    build = (
        activate_embargo_activity
        if accept
        else reject_embargo_proposal_activity
    )
    decision = build(
        embargo,
        in_reply_to=proposal_id,
        actor=owner.id_,
        target=case.id_,
        context=case.id_,
        to=[case_manager_id],
        summary=summary,
    )
    logger.info(
        "Sending the owner's %s: %s",
        "activation" if accept else "rejection",
        logfmt(decision),
    )
    post_to_inbox_and_wait(client, case_manager_id, decision)


def owner_activates_embargo(
    client: DataLayerClient,
    owner: as_Actor,
    case_manager_id: str,
    case: as_VulnerabilityCase,
    embargo: as_EmbargoEvent,
    proposal_id: str,
) -> None:
    """The case owner activates a proposed embargo (EA / EC, ADR-0180)."""
    _send_owner_embargo_decision(
        client,
        owner,
        case_manager_id,
        case,
        embargo,
        proposal_id,
        accept=True,
        summary=f"Activating the proposed embargo for {case.name}.",
    )


def owner_rejects_embargo_proposal(
    client: DataLayerClient,
    owner: as_Actor,
    case_manager_id: str,
    case: as_VulnerabilityCase,
    embargo: as_EmbargoEvent,
    proposal_id: str,
) -> None:
    """The case owner rejects a proposed embargo (ER / EJ, ADR-0122)."""
    _send_owner_embargo_decision(
        client,
        owner,
        case_manager_id,
        case,
        embargo,
        proposal_id,
        accept=False,
        summary=f"Rejecting the proposed embargo for {case.name}.",
    )
