#!/usr/bin/env python

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

"""
Demonstrates the workflow for transferring case ownership via the Vultron API.

This demo script showcases two ownership transfer paths:

1. Accept path: current owner (vendor) offers case to coordinator → coordinator
   accepts → case.attributed_to is updated to coordinator
2. Reject path: current owner (vendor) offers case to coordinator → coordinator
   rejects → case.attributed_to remains with vendor

Each demo starts from a canonical, CaseActor-owned case (report submitted and
validated, ``Create(CaseProposal)`` delivered, CaseActor creates the case) so
that the transfer workflow can be demonstrated in isolation.

This corresponds to the workflow documented in:
    docs/howto/activitypub/activities/transfer_ownership.md

When run as a script, this module will:
1. Check if the API server is available
2. Reset the data layer to a clean state
3. Discover actors (finder, vendor, coordinator) via the API
4. Run both demo workflows (accept and reject)
5. Verify side effects in the data layer

Routing model (ADR-0053):
Both the ``Offer(VulnerabilityCase)`` and the response to it are addressed to
the **CaseActor's** inbox, never to the transferee or the offerer directly
(CM-21-005, CM-21-006).  The CaseActor records the Offer, commits a
``CaseLedgerEntry``, broadcasts ``Announce(CaseLedgerEntry)`` to every
participant — which is how actors outside the negotiation, such as the finder,
learn a transfer is pending — and only then forwards a **new** Offer of its own
to the transferee.  The demo therefore discovers the forwarded Offer by its
properties rather than by the original offer's id (EDF-06-004).
"""

# Standard library imports
import logging
from typing import Callable, Optional, Sequence, Tuple

# Vultron imports
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Offer
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.demo.helpers.polling import wait_for_case_attributed_to
from vultron.demo.helpers.runner import run_exchange_demos
from vultron.demo.helpers.workflow import (
    await_forwarded_ownership_transfer_offer,
    case_actor_invites_actor_to_case,
    setup_canonical_case,
)
from vultron.demo.utils import (
    DataLayerClient,
    demo_check,
    demo_gate,
    demo_step,
    log_case_state,
    logfmt,
    post_to_inbox_and_wait,
    seed_peer,
    verify_object_stored,
    setup_demo_logging,
)
from vultron.wire.as2.factories import (
    accept_case_ownership_transfer_activity,
    offer_case_ownership_transfer_activity,
    reject_case_ownership_transfer_activity,
)

logger = logging.getLogger(__name__)

_REPORT_NAME = "Remote Code Execution Vulnerability"
_REPORT_CONTENT = "A remote code execution vulnerability in the web framework."
_VALIDATION_CONTENT = (
    "Confirmed — remote code execution via unsanitized input."
)


def _setup_transfer_precondition(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor,
) -> Tuple[as_VulnerabilityCase, str]:
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
        finder,
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
    case_actor_invites_actor_to_case(
        client,
        case=case,
        inviter=vendor,
        invitee=coordinator,
        case_actor_id=case_actor_id,
        roles=[CVDRole.COORDINATOR.value],
    )
    return case, case_actor_id


def _vendor_offers_ownership(
    client: DataLayerClient,
    case: as_VulnerabilityCase,
    vendor: as_Actor,
    coordinator: as_Actor,
    case_actor_id: str,
) -> as_Offer:
    """Send the vendor's ownership-transfer Offer to the CaseActor's inbox.

    ``actor`` is the CaseActor and ``attributed_to`` the vendor: the CaseActor
    is the sender of record for a delegated case message, and the vendor is the
    participant whose intent it carries (CM-24-001, CM-24-002).  Addressing it
    to the vendor instead is what made receivers reject the Offer in #2142.

    Returns:
        The Offer that was sent.
    """
    offer = offer_case_ownership_transfer_activity(
        case,
        actor=case_actor_id,
        attributed_to=vendor.id_,
        # Inline actor object, not a bare URI: the ledger entry's
        # payloadSnapshot.target must be resolvable without a second lookup,
        # and CommitCaseLedgerEntryNode rejects a bare id string.
        target=coordinator,
        to=[case_actor_id],
        content=f"Offering to transfer ownership of {case.name} to you.",
    )
    logger.info(f"Sending offer to the CaseActor: {logfmt(offer)}")
    post_to_inbox_and_wait(client, case_actor_id, offer)
    with demo_check("Ownership offer recorded by the CaseActor (CM-21-005)"):
        # The CaseActor's store, not the vendor's: the Offer is addressed to
        # the CaseActor, so that is the replica that records it (ADR-0073).
        verify_object_stored(client, offer.id_, actor_id=case_actor_id)
    return offer


def demo_transfer_ownership_accept(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor,
) -> None:
    """
    Demonstrates the accept path of the transfer-ownership workflow.

    Steps:
    1. Setup: canonical CaseActor-owned case, coordinator added as participant
    2. Vendor offers case ownership to coordinator
       (OfferCaseOwnershipTransferActivity → **CaseActor** inbox, CM-21-005)
    3. CaseActor forwards a new Offer to the coordinator; the demo discovers it
    4. Coordinator accepts (AcceptCaseOwnershipTransferActivity → **CaseActor**
       inbox, CM-21-006)
    5. Verify case.attributed_to is updated to coordinator

    This follows the accept branch in
    docs/howto/activitypub/activities/transfer_ownership.md.
    """
    logger.info("=" * 80)
    logger.info("DEMO: Transfer Ownership — Accept Path")
    logger.info("=" * 80)

    case, case_actor_id = _setup_transfer_precondition(
        client, finder, vendor, coordinator
    )

    # Confirm initial owner is vendor
    initial_case = log_case_state(
        client, case.id_, "initial", actor_id=case_actor_id
    )
    if initial_case is None:
        raise ValueError("Could not retrieve initial case state")
    logger.info(f"Initial owner: {initial_case.attributed_to}")

    with demo_step(
        "Step 2: Vendor offers case ownership to coordinator via the CaseActor"
    ):
        _vendor_offers_ownership(
            client, case, vendor, coordinator, case_actor_id
        )

    with demo_gate(
        "Step 3: CaseActor forwarded the Offer to the coordinator (CM-21-005)"
    ):
        forwarded_offer = await_forwarded_ownership_transfer_offer(
            client,
            case=case,
            transferee=coordinator,
            case_actor_id=case_actor_id,
        )
        logger.info("Forwarded offer id: %s", forwarded_offer.id_)

        with demo_step("Step 4: Coordinator accepts ownership transfer"):
            # The forwarded offer's id, not the vendor's original: the CaseActor
            # minted a new Offer, and only the forwarded one exists on the
            # coordinator's replica (CM-21-005).
            accept = accept_case_ownership_transfer_activity(
                forwarded_offer,
                actor=coordinator.id_,
                to=[case_actor_id],
                content=(f"Accepting ownership of {case.name}."),
            )
            logger.info(f"Sending accept to the CaseActor: {logfmt(accept)}")
            post_to_inbox_and_wait(client, case_actor_id, accept)

        with demo_step(
            "Step 5: Verify case ownership transferred to coordinator"
        ):
            with demo_check("Case attributed_to updated to coordinator"):
                # Poll rather than read once: the CaseActor commits the receipt,
                # fans out Announce(CaseLedgerEntry) to every participant and
                # applies the role change in a background task, so a single read
                # after post_to_inbox_and_wait's fixed 1 s sleep races it.
                wait_for_case_attributed_to(
                    client=client.model_copy(
                        update={"actor_id": case_actor_id}
                    ),
                    case_id=case.id_,
                    expected_attributed_to=coordinator.id_,
                )
            log_case_state(
                client, case.id_, "after accept", actor_id=case_actor_id
            )

    logger.info("✅ DEMO COMPLETE (accept path): Case ownership transferred.")


def demo_transfer_ownership_reject(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor,
) -> None:
    """
    Demonstrates the reject path of the transfer-ownership workflow.

    Steps:
    1. Setup: canonical CaseActor-owned case, coordinator added as participant
    2. Vendor offers case ownership to coordinator
       (OfferCaseOwnershipTransferActivity → **CaseActor** inbox, CM-21-005)
    3. CaseActor forwards a new Offer to the coordinator; the demo discovers it
    4. Coordinator rejects (RejectCaseOwnershipTransferActivity → **CaseActor**
       inbox — the reply goes back to the sender of the forwarded Offer)
    5. Verify case.attributed_to remains with vendor

    This follows the reject branch in
    docs/howto/activitypub/activities/transfer_ownership.md.
    """
    logger.info("=" * 80)
    logger.info("DEMO: Transfer Ownership — Reject Path")
    logger.info("=" * 80)

    case, case_actor_id = _setup_transfer_precondition(
        client, finder, vendor, coordinator
    )

    initial_case = log_case_state(
        client, case.id_, "initial", actor_id=case_actor_id
    )
    if initial_case is None:
        raise ValueError("Could not retrieve initial case state")
    original_owner = initial_case.attributed_to
    logger.info(f"Initial owner: {original_owner}")

    with demo_step(
        "Step 2: Vendor offers case ownership to coordinator via the CaseActor"
    ):
        _vendor_offers_ownership(
            client, case, vendor, coordinator, case_actor_id
        )

    with demo_gate(
        "Step 3: CaseActor forwarded the Offer to the coordinator (CM-21-005)"
    ):
        forwarded_offer = await_forwarded_ownership_transfer_offer(
            client,
            case=case,
            transferee=coordinator,
            case_actor_id=case_actor_id,
        )
        logger.info("Forwarded offer id: %s", forwarded_offer.id_)

        with demo_step("Step 4: Coordinator rejects ownership transfer"):
            reject = reject_case_ownership_transfer_activity(
                forwarded_offer,
                actor=coordinator.id_,
                to=[case_actor_id],
                content=(f"Declining ownership of {case.name}."),
            )
            logger.info(f"Sending reject to the CaseActor: {logfmt(reject)}")
            post_to_inbox_and_wait(client, case_actor_id, reject)

        with demo_step("Step 5: Verify case ownership unchanged"):
            # Temporal, deliberately (EDF-06-006): this asserts a *non*-change,
            # and there is nothing to poll for — a rejection commits no ledger
            # entry and mutates no state, so `RejectCaseOwnershipTransferReceived`
            # leaves no observable at all.  The check is therefore weaker than the
            # accept path's: it can pass because the Reject has not been processed
            # yet rather than because it was processed and declined.  Giving the
            # reject path an observable needs a spec decision on whether a
            # rejection is a ledgered event — CM-21 specifies routing for the
            # Offer and Accept but says nothing about the Reject.  See
            # plan/incoming/learnings/20260901-2789-reject-ownership-transfer-routing-unspecified.md
            with demo_check("Case attributed_to still vendor"):
                final_case = log_case_state(
                    client, case.id_, "after reject", actor_id=case_actor_id
                )
                if final_case is None:
                    raise ValueError("Could not retrieve case after reject")
                if final_case.attributed_to != original_owner:
                    raise ValueError(
                        f"Expected case owner to remain '{original_owner}'"
                        f" after reject, got: {final_case.attributed_to}"
                    )
                logger.info(
                    "Ownership unchanged — still with: %s",
                    final_case.attributed_to,
                )

    logger.info(
        "✅ DEMO COMPLETE (reject path): Ownership transfer rejected gracefully."
    )


_ALL_DEMOS: Sequence[Tuple[str, Callable[..., None]]] = [
    ("Demo: Transfer Ownership — Accept Path", demo_transfer_ownership_accept),
    ("Demo: Transfer Ownership — Reject Path", demo_transfer_ownership_reject),
]


def main(
    skip_health_check: bool = False,
    demos: Optional[Sequence] = None,
) -> None:
    """Main entry point for the transfer_ownership demo script."""
    run_exchange_demos(
        _ALL_DEMOS, skip_health_check=skip_health_check, demos=demos
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
