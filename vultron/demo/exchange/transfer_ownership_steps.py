"""Shared steps of the ownership-transfer exchange demo's three paths.

Each path of :mod:`vultron.demo.exchange.transfer_ownership_demo` starts from
the same canonical case and the same vendor offer, and two of them end on the
same unchanged-owner check; those steps live here so each path states only what
is particular to it (DEMOMA-17-001).
"""

#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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

import logging
from datetime import datetime, timedelta

from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers.polling import (
    wait_for_semantic_type_in_ledger,
)
from vultron.demo.helpers.workflow import (
    seat_participant_through_stub_invite,
    setup_canonical_case,
)
from vultron.demo.utils import (
    DataLayerClient,
    demo_check,
    demo_gate,
    log_case_state,
    logfmt,
    seed_peer,
    verify_received_activity_stored,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

#: These steps are part of the demo's run, so they log under its module name.
logger = logging.getLogger("vultron.demo.exchange.transfer_ownership_demo")

_REPORT_NAME = "Remote Code Execution Vulnerability"
_REPORT_CONTENT = "A remote code execution vulnerability in the web framework."
_VALIDATION_CONTENT = (
    "Confirmed — remote code execution via unsanitized input."
)


def setup_transfer_precondition(
    client: DataLayerClient,
    reporter: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor,
) -> tuple[as_VulnerabilityCase, str]:
    """Build the precondition both transfer paths share.

    A canonical CaseActor-owned case (so there *is* a CaseActor to route
    through — see :func:`setup_canonical_case`), with the coordinator joined via
    the CaseActor-routed Invite/Accept handshake so that the accept path can
    move ``CVDRole.CASE_OWNER`` onto an existing ``CaseParticipant`` record in
    the CaseActor's own store (CM-21-002).

    Returns:
        ``(case, case_actor_id)``.
    """
    case, case_actor_id = setup_canonical_case(
        client,
        reporter,
        vendor,
        report_name=_REPORT_NAME,
        report_content=_REPORT_CONTENT,
        validation_content=_VALIDATION_CONTENT,
    )
    # The CaseActor has to know the coordinator before it can ledger an
    # activity that names it: the ledger snapshot must carry `target` as an
    # inline object (CLP-07), and the snapshot builder can only inline what the
    # committing actor's own store already holds (ADR-0081).  A container in the
    # multi-actor topology gets this from its seed config; a single-container
    # exchange demo has to register the address-book entry itself.
    seed_peer(
        client,
        local_actor_id=case_actor_id,
        peer_id=coordinator.id_,
        name=coordinator.name or "Coordinator",
        actor_type="Organization",
    )
    # The CaseActor seats the coordinator when it accepts its stub Invite;
    # the CaseActor's copy is the one the ownership transfer later resolves
    # (ADR-0073, CM-21-002).
    seat_participant_through_stub_invite(
        client,
        case,
        owner=vendor,
        invitee=coordinator,
        role=CVDRole.COORDINATOR,
    )
    return case, case_actor_id


def vendor_offers_ownership(
    client: DataLayerClient,
    case: as_VulnerabilityCase,
    vendor: as_Actor,
    coordinator: as_Actor,
    case_actor_id: str,
    end_time: datetime | None = None,
) -> str:
    """The vendor offers ownership to the coordinator through its trigger.

    *end_time*, when given, is the Offer's deadline to answer (TRIG-11-007,
    CM-21-016).

    The ``offer-case-ownership-transfer`` trigger (TRIG-11-001, DEMOMA-05-001)
    sends the vendor's proposal to the CaseActor, which makes the Offer with
    ``attributed_to`` the vendor: the CaseActor is the sender of record for a
    delegated case message, and the vendor is the participant whose intent it
    carries (CM-24-001, CM-24-002, ADR-0148).  The demo gates on the
    CaseActor's ledger entry for that Offer, which it commits once the Offer
    is queued for the coordinator, so it is the cause the next step waits
    for (EDF-06).

    Returns:
        The id of the vendor's proposal, which it names to withdraw it.
    """
    offer = (
        ActorSession(client=client, actor=vendor)
        .with_case(case)
        .quiet()
        .offer_case_ownership_transfer(
            transferee_id=coordinator.id_,
            content=f"Offering to transfer ownership of {case.name} to you.",
            end_time=end_time,
        )
        .activity
    )
    logger.info("Vendor offered ownership: %s", logfmt(offer))
    with demo_gate("Ownership offer recorded by the CaseActor (CM-21-029)"):
        wait_for_semantic_type_in_ledger(
            client=client,
            case_id=case.id_,
            semantic_type="offer_case_ownership_transfer",
            dl_actor_id=case_actor_id,
        )
    return offer.id_


#: How long the accept path gives the coordinator to answer.  Generous, so
#: the demo answers in time; the refusal of a late answer is pinned by the
#: unit tests, not by waiting here (CM-21-016, CM-21-017).
ANSWER_WINDOW = timedelta(days=1)


def check_offer_carries_deadline(
    client: DataLayerClient,
    coordinator: as_Actor,
    offer_id: str,
    deadline: datetime,
) -> None:
    """Check the Offer the coordinator holds names the vendor's deadline.

    The coordinator answers the CaseActor's Offer, not the vendor's proposal
    (CM-21-005), so that Offer is what must tell it when it may no longer
    answer (CM-21-016).
    """
    with demo_check("The CaseActor's Offer carries the deadline to answer"):
        received = verify_received_activity_stored(
            client, offer_id, actor_id=coordinator.id_
        )
        end_time = received.get("endTime")
        if end_time is None or datetime.fromisoformat(end_time) != deadline:
            raise ValueError(
                f"Expected the CaseActor's Offer to carry endTime {deadline},"
                f" got: {end_time}"
            )
        logger.info("Offer answer deadline: %s", end_time)


def check_owner_unchanged(
    client: DataLayerClient,
    case: as_VulnerabilityCase,
    case_actor_id: str,
    original_owner: object,
    after: str,
) -> None:
    """Check the CaseActor's case is still attributed to *original_owner*.

    Shared by the paths that close the Offer without a transfer: the
    transferee's Reject and the vendor's withdrawal.  The caller gates on
    the closing ledger entry first (EDF-06).
    """
    with demo_check("Case attributed_to still vendor"):
        final_case = log_case_state(
            client, case.id_, f"after {after}", actor_id=case_actor_id
        )
        if final_case is None:
            raise ValueError(f"Could not retrieve case after {after}")
        if final_case.attributed_to != original_owner:
            raise ValueError(
                f"Expected case owner to remain '{original_owner}'"
                f" after {after}, got: {final_case.attributed_to}"
            )
        logger.info(
            "Ownership unchanged — still with: %s",
            final_case.attributed_to,
        )


def initial_owner(
    client: DataLayerClient, case: as_VulnerabilityCase, case_actor_id: str
) -> object:
    """Log the case's initial state and return its owner."""
    initial_case = log_case_state(
        client, case.id_, "initial", actor_id=case_actor_id
    )
    if initial_case is None:
        raise ValueError("Could not retrieve initial case state")
    logger.info("Initial owner: %s", initial_case.attributed_to)
    return initial_case.attributed_to
