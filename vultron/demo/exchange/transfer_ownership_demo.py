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

1. Accept path: current owner (vendor) offers case to coordinator, with a
   deadline to answer (TRIG-11-007) → the CaseActor's Offer carries it →
   coordinator accepts in time → case.attributed_to is updated to coordinator
2. Reject path: current owner (vendor) offers case to coordinator → coordinator
   rejects → case.attributed_to remains with vendor
3. Withdraw path: current owner (vendor) offers case to coordinator → vendor
   withdraws the offer before it is answered → case.attributed_to remains
   with vendor

Each demo starts from a canonical, CaseActor-owned case (report submitted and
validated, ``Create(CaseProposal)`` delivered, CaseActor creates the case) so
that the transfer workflow can be demonstrated in isolation.

This corresponds to the workflow documented in:
    docs/topics/case_lifecycle/ownership_transfer.md

When run as a script, this module will:
1. Check if the API server is available
2. Reset the data layer to a clean state
3. Discover actors (reporter, vendor, coordinator) via the API
4. Run the demo workflows (accept, reject and withdraw)
5. Verify side effects in the data layer

Routing model (ADR-0053, ADR-0148):
The vendor's proposal, ``Offer(Offer(VulnerabilityCase))``, the response to the
Offer and the proposal's withdrawal are addressed to the **CaseActor's** inbox,
never to the transferee or the offerer directly (CM-21-005, CM-21-006,
CM-21-010, CM-21-015).  The CaseActor records the proposal, makes the one
``Offer(VulnerabilityCase)`` of the transfer under its own id, sends it to the
transferee and ledgers it, broadcasting each ``Announce(CaseLedgerEntry)`` to
every participant — which is how actors outside the negotiation, such as the
reporter, learn a transfer is pending.  The demo therefore discovers the
CaseActor's Offer by its properties rather than by the proposal's id
(EDF-06-004).
"""

# Standard library imports
import logging
from collections.abc import Callable, Sequence

from vultron.demo.actor_session import ActorSession
from vultron.demo.exchange.transfer_ownership_steps import (
    ANSWER_WINDOW,
    check_offer_carries_deadline,
    check_owner_unchanged,
    initial_owner,
    setup_transfer_precondition,
    vendor_offers_ownership,
)
from vultron.demo.helpers.polling import (
    wait_for_case_attributed_to,
    wait_for_semantic_type_in_ledger,
)
from vultron.demo.helpers.runner import run_exchange_demos
from vultron.demo.helpers.verification import recipient_ids
from vultron.demo.helpers.workflow import (
    await_ownership_transfer_offer,
)
from vultron.demo.utils import (
    DataLayerClient,
    demo_check,
    demo_gate,
    demo_step,
    log_case_state,
    logfmt,
    setup_demo_logging,
)
from vultron.demo.wall_clock import from_now

# Vultron imports
from vultron.wire.as2.vocab.base.objects.actors import as_Actor

logger = logging.getLogger(__name__)


def demo_transfer_ownership_accept(
    client: DataLayerClient,
    reporter: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor,
) -> None:
    """
    Demonstrates the accept path of the transfer-ownership workflow.

    Steps:
    1. Setup: canonical CaseActor-owned case, coordinator added as participant
    2. Vendor offers case ownership to coordinator, with a deadline to
       answer (OfferCaseOwnershipTransferActivity → **CaseActor** inbox,
       CM-21-005, TRIG-11-007)
    3. CaseActor makes the Offer from the proposal and sends it to the
       coordinator, carrying the deadline; the demo discovers it
    4. Coordinator accepts through its ``accept-case-ownership-transfer``
       trigger (AcceptCaseOwnershipTransferActivity → **CaseActor** inbox,
       CM-21-006, TRIG-11-002)
    5. Verify case.attributed_to is updated to coordinator

    This follows the accept branch in
    docs/topics/case_lifecycle/ownership_transfer.md.
    """
    logger.info("=" * 80)
    logger.info("DEMO: Transfer Ownership — Accept Path")
    logger.info("=" * 80)

    case, case_actor_id = setup_transfer_precondition(
        client, reporter, vendor, coordinator
    )

    # Confirm initial owner is vendor
    initial_owner(client, case, case_actor_id)

    deadline = from_now(ANSWER_WINDOW)
    with demo_step(
        "Step 2: Vendor offers case ownership to coordinator via the"
        " CaseActor, with a deadline to answer"
    ):
        vendor_offers_ownership(
            client, case, vendor, coordinator, case_actor_id, end_time=deadline
        )

    with demo_gate(
        "Step 3: CaseActor sent its Offer to the coordinator (CM-21-005)"
    ):
        offer_id = await_ownership_transfer_offer(
            client, case=case, transferee=coordinator
        )
        logger.info("CaseActor's offer id: %s", offer_id)
        check_offer_carries_deadline(client, coordinator, offer_id, deadline)

        with demo_step("Step 4: Coordinator accepts ownership transfer"):
            # Through the coordinator's own trigger (DEMOMA-05-001,
            # TRIG-11-002), naming the CaseActor's Offer, not the vendor's
            # proposal: only that Offer exists on the coordinator's replica
            # (CM-21-005, ADR-0148).
            accept = (
                ActorSession(client=client, actor=coordinator)
                .quiet()
                .accept_case_ownership_transfer(offer_id=offer_id)
                .activity
            )
            logger.info("Coordinator sent accept: %s", logfmt(accept))

        with demo_step(
            "Step 5: Verify case ownership transferred to coordinator"
        ):
            with demo_check("Case attributed_to updated to coordinator"):
                # Poll rather than read once: the Accept reaches the CaseActor
                # through the coordinator's outbox, and the CaseActor commits
                # the receipt, fans out Announce(CaseLedgerEntry) and applies
                # the role change in a background task, so a single read races it.
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
    reporter: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor,
) -> None:
    """
    Demonstrates the reject path of the transfer-ownership workflow.

    Steps:
    1. Setup: canonical CaseActor-owned case, coordinator added as participant
    2. Vendor offers case ownership to coordinator
       (OfferCaseOwnershipTransferActivity → **CaseActor** inbox, CM-21-005)
    3. CaseActor makes the Offer and sends it to the coordinator; the demo
       discovers it
    4. Coordinator rejects through its ``reject-case-ownership-transfer``
       trigger (RejectCaseOwnershipTransferActivity → **CaseActor** inbox,
       CM-21-010, TRIG-11-005)
    5. Once the CaseActor has ledgered the Reject (CM-21-012), verify
       case.attributed_to remains with vendor

    This follows the reject branch in
    docs/topics/case_lifecycle/ownership_transfer.md.
    """
    logger.info("=" * 80)
    logger.info("DEMO: Transfer Ownership — Reject Path")
    logger.info("=" * 80)

    case, case_actor_id = setup_transfer_precondition(
        client, reporter, vendor, coordinator
    )

    original_owner = initial_owner(client, case, case_actor_id)

    with demo_step(
        "Step 2: Vendor offers case ownership to coordinator via the CaseActor"
    ):
        vendor_offers_ownership(
            client, case, vendor, coordinator, case_actor_id
        )

    with demo_gate(
        "Step 3: CaseActor sent its Offer to the coordinator (CM-21-005)"
    ):
        offer_id = await_ownership_transfer_offer(
            client, case=case, transferee=coordinator
        )
        logger.info("CaseActor's offer id: %s", offer_id)

        with demo_step("Step 4: Coordinator rejects ownership transfer"):
            # Through the coordinator's own trigger (DEMOMA-05-001,
            # TRIG-11-005), naming the CaseActor's Offer: only that Offer
            # exists on the coordinator's replica (CM-21-005).
            reject_result = (
                ActorSession(client=client, actor=coordinator)
                .quiet()
                .reject_case_ownership_transfer(offer_id=offer_id)
            )
            reject = reject_result.activity
            logger.info("Coordinator sent reject: %s", logfmt(reject))
            with demo_check(
                "Reject addressed to the CaseActor, not the offerer (CM-21-010)"
            ):
                recipients = recipient_ids(reject.to)
                if recipients != [case_actor_id]:
                    raise ValueError(
                        f"Expected the Reject addressed to '{case_actor_id}',"
                        f" got: {recipients}"
                    )

    # Gate on the cause (EDF-06): the CaseActor ledgers the decline and
    # broadcasts it (CM-21-032), so its entry is the observable that the
    # Reject was processed.  Only then is "owner unchanged" a statement about
    # a processed decline rather than about a Reject not yet read.
    with demo_gate(
        "CaseActor committed reject_case_ownership_transfer (CM-21-012)"
    ):
        wait_for_semantic_type_in_ledger(
            client=client,
            case_id=case.id_,
            semantic_type="reject_case_ownership_transfer",
            dl_actor_id=case_actor_id,
        )

        with demo_step("Step 5: Verify case ownership unchanged"):
            check_owner_unchanged(
                client, case, case_actor_id, original_owner, "reject"
            )

    logger.info(
        "✅ DEMO COMPLETE (reject path): Ownership transfer rejected gracefully."
    )


def demo_transfer_ownership_withdraw(
    client: DataLayerClient,
    reporter: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor,
) -> None:
    """
    Demonstrates the withdrawal path of the transfer-ownership workflow.

    Steps:
    1. Setup: canonical CaseActor-owned case, coordinator added as participant
    2. Vendor offers case ownership to coordinator
       (OfferCaseOwnershipTransferActivity → **CaseActor** inbox, CM-21-005)
    3. CaseActor makes the Offer and sends it to the coordinator; the demo
       discovers it
    4. Before the coordinator answers, the vendor withdraws the Offer through
       its ``withdraw-case-ownership-transfer`` trigger
       (UndoCaseOwnershipTransferActivity → **CaseActor** inbox, CM-21-036,
       TRIG-11-006)
    5. Once the CaseActor has ledgered the withdrawal, verify
       case.attributed_to remains with vendor

    This follows the withdrawal branch in
    docs/topics/case_lifecycle/ownership_transfer.md.
    """
    logger.info("=" * 80)
    logger.info("DEMO: Transfer Ownership — Withdraw Path")
    logger.info("=" * 80)

    case, case_actor_id = setup_transfer_precondition(
        client, reporter, vendor, coordinator
    )
    original_owner = initial_owner(client, case, case_actor_id)

    # The withdrawal names the proposal this step makes, so steps 3 and 4 nest
    # inside it rather than reading an empty-string sentinel after it
    # (ADR-0058, #3038).
    with demo_step(
        "Step 2: Vendor offers case ownership to coordinator via the CaseActor"
    ):
        proposal_id = vendor_offers_ownership(
            client, case, vendor, coordinator, case_actor_id
        )

        with demo_gate(
            "Step 3: CaseActor sent its Offer to the coordinator (CM-21-005)"
        ):
            offer_id = await_ownership_transfer_offer(
                client, case=case, transferee=coordinator
            )
            logger.info("CaseActor's offer id: %s", offer_id)

            with demo_step(
                "Step 4: Vendor withdraws the ownership transfer offer"
            ):
                # Through the vendor's own trigger (DEMOMA-05-001,
                # TRIG-11-006), naming the vendor's own proposal: the one its
                # store holds, from which the CaseActor made the Offer it
                # withdraws (ADR-0148).
                undo = (
                    ActorSession(client=client, actor=vendor)
                    .quiet()
                    .withdraw_case_ownership_transfer(offer_id=proposal_id)
                    .activity
                )
                logger.info("Vendor sent withdrawal: %s", logfmt(undo))
                with demo_check(
                    "Withdrawal addressed to the CaseActor (CM-21-036)"
                ):
                    recipients = recipient_ids(undo.to)
                    if recipients != [case_actor_id]:
                        raise ValueError(
                            "Expected the Undo addressed to"
                            f" '{case_actor_id}', got: {recipients}"
                        )

    # Gate on the cause (EDF-06): the CaseActor ledgers the withdrawal and
    # broadcasts it (CM-21-015, CM-21-038); that entry is what closes the Offer.
    with demo_gate(
        "CaseActor committed undo_case_ownership_transfer (CM-21-015)"
    ):
        wait_for_semantic_type_in_ledger(
            client=client,
            case_id=case.id_,
            semantic_type="undo_case_ownership_transfer",
            dl_actor_id=case_actor_id,
        )

        with demo_step("Step 5: Verify case ownership unchanged"):
            check_owner_unchanged(
                client, case, case_actor_id, original_owner, "withdrawal"
            )

    logger.info(
        "✅ DEMO COMPLETE (withdraw path): Ownership transfer offer withdrawn."
    )


_ALL_DEMOS: Sequence[tuple[str, Callable[..., None]]] = [
    ("Demo: Transfer Ownership — Accept Path", demo_transfer_ownership_accept),
    ("Demo: Transfer Ownership — Reject Path", demo_transfer_ownership_reject),
    (
        "Demo: Transfer Ownership — Withdraw Path",
        demo_transfer_ownership_withdraw,
    ),
]


def main(
    skip_health_check: bool = False,
    demos: Sequence | None = None,
) -> None:
    """Main entry point for the transfer_ownership demo script."""
    run_exchange_demos(
        _ALL_DEMOS, skip_health_check=skip_health_check, demos=demos
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
