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
   deadline to answer (TRIG-11-007) → the forwarded Offer carries it →
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

Routing model (ADR-0053):
The ``Offer(VulnerabilityCase)``, the response to it and its withdrawal are
addressed to the **CaseActor's** inbox, never to the transferee or the offerer
directly (CM-21-005, CM-21-006, CM-21-010, CM-21-015).  The CaseActor records
the Offer, commits a ``CaseLedgerEntry``, broadcasts ``Announce(CaseLedgerEntry)`` to every
participant — which is how actors outside the negotiation, such as the reporter,
learn a transfer is pending — and only then forwards a **new** Offer of its own
to the transferee.  The demo therefore discovers the forwarded Offer by its
properties rather than by the original offer's id (EDF-06-004).
"""

# Standard library imports
import logging
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta

from vultron.core.models._helpers import from_now_utc
from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers.polling import (
    wait_for_case_attributed_to,
    wait_for_semantic_type_in_ledger,
)
from vultron.demo.helpers.runner import run_exchange_demos
from vultron.demo.helpers.verification import recipient_ids
from vultron.demo.helpers.workflow import (
    await_forwarded_ownership_transfer_offer,
    seat_participant_through_stub_invite,
    setup_canonical_case,
)
from vultron.demo.utils import (
    DataLayerClient,
    demo_check,
    demo_gate,
    demo_step,
    log_case_state,
    logfmt,
    seed_peer,
    setup_demo_logging,
    verify_received_activity_stored,
)

# Vultron imports
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

logger = logging.getLogger(__name__)

_REPORT_NAME = "Remote Code Execution Vulnerability"
_REPORT_CONTENT = "A remote code execution vulnerability in the web framework."
_VALIDATION_CONTENT = (
    "Confirmed — remote code execution via unsanitized input."
)


def _setup_transfer_precondition(
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


def _vendor_offers_ownership(
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
    has the CaseActor send the Offer with ``attributed_to`` the vendor: the
    CaseActor is the sender of record for a delegated case message, and the
    vendor is the participant whose intent it carries (CM-24-001, CM-24-002).
    Addressing it to the vendor instead is what made receivers reject the
    Offer in #2142.  The demo gates on the CaseActor's ledger entry for it,
    the cause of the forward the next step waits for (EDF-06).

    Returns:
        The id of the Offer the vendor made, which it names to withdraw it.
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
    with demo_gate("Ownership offer recorded by the CaseActor (CM-21-005)"):
        wait_for_semantic_type_in_ledger(
            client=client,
            case_id=case.id_,
            semantic_type="offer_case_ownership_transfer",
            dl_actor_id=case_actor_id,
        )
    return offer.id_


#: How long the accept path gives the coordinator to answer.  Generous, so
#: the demo answers in time; the refusal of a late answer and the expiry
#: record are pinned by the unit tests, not by waiting here (CM-21-016,
#: CM-21-017).
_ANSWER_WINDOW = timedelta(days=1)


def _check_forward_carries_deadline(
    client: DataLayerClient,
    coordinator: as_Actor,
    forwarded_offer_id: str,
    deadline: datetime,
) -> None:
    """Check the Offer the coordinator holds names the vendor's deadline.

    The coordinator answers the CaseActor's forward, not the vendor's Offer
    (CM-21-005), so the forward is what must tell it when it may no longer
    answer (CM-21-016).
    """
    with demo_check("Forwarded Offer carries the deadline to answer"):
        forwarded = verify_received_activity_stored(
            client, forwarded_offer_id, actor_id=coordinator.id_
        )
        end_time = forwarded.get("endTime")
        if end_time is None or datetime.fromisoformat(end_time) != deadline:
            raise ValueError(
                f"Expected the forwarded Offer to carry endTime {deadline},"
                f" got: {end_time}"
            )
        logger.info("Forwarded Offer answer deadline: %s", end_time)


def _check_owner_unchanged(
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


def _initial_owner(
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
    3. CaseActor forwards a new Offer to the coordinator, carrying the
       deadline; the demo discovers it
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

    case, case_actor_id = _setup_transfer_precondition(
        client, reporter, vendor, coordinator
    )

    # Confirm initial owner is vendor
    _initial_owner(client, case, case_actor_id)

    deadline = from_now_utc(_ANSWER_WINDOW)
    with demo_step(
        "Step 2: Vendor offers case ownership to coordinator via the"
        " CaseActor, with a deadline to answer"
    ):
        _vendor_offers_ownership(
            client, case, vendor, coordinator, case_actor_id, end_time=deadline
        )

    with demo_gate(
        "Step 3: CaseActor forwarded the Offer to the coordinator (CM-21-005)"
    ):
        forwarded_offer_id = await_forwarded_ownership_transfer_offer(
            client, case=case, transferee=coordinator
        )
        logger.info("Forwarded offer id: %s", forwarded_offer_id)
        _check_forward_carries_deadline(
            client, coordinator, forwarded_offer_id, deadline
        )

        with demo_step("Step 4: Coordinator accepts ownership transfer"):
            # Through the coordinator's own trigger (DEMOMA-05-001,
            # TRIG-11-002), naming the forwarded offer's id, not the vendor's
            # original: the CaseActor minted a new Offer, and only the
            # forwarded one exists on the coordinator's replica (CM-21-005).
            accept = (
                ActorSession(client=client, actor=coordinator)
                .quiet()
                .accept_case_ownership_transfer(offer_id=forwarded_offer_id)
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
    3. CaseActor forwards a new Offer to the coordinator; the demo discovers it
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

    case, case_actor_id = _setup_transfer_precondition(
        client, reporter, vendor, coordinator
    )

    original_owner = _initial_owner(client, case, case_actor_id)

    with demo_step(
        "Step 2: Vendor offers case ownership to coordinator via the CaseActor"
    ):
        _vendor_offers_ownership(
            client, case, vendor, coordinator, case_actor_id
        )

    with demo_gate(
        "Step 3: CaseActor forwarded the Offer to the coordinator (CM-21-005)"
    ):
        forwarded_offer_id = await_forwarded_ownership_transfer_offer(
            client, case=case, transferee=coordinator
        )
        logger.info("Forwarded offer id: %s", forwarded_offer_id)

        with demo_step("Step 4: Coordinator rejects ownership transfer"):
            # Through the coordinator's own trigger (DEMOMA-05-001,
            # TRIG-11-005), naming the forwarded offer's id: only the
            # forward exists on the coordinator's replica (CM-21-005).
            reject_result = (
                ActorSession(client=client, actor=coordinator)
                .quiet()
                .reject_case_ownership_transfer(offer_id=forwarded_offer_id)
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
    # broadcasts it (CM-21-012), so its entry is the observable that the
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
            _check_owner_unchanged(
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
    3. CaseActor forwards a new Offer to the coordinator; the demo discovers it
    4. Before the coordinator answers, the vendor withdraws the Offer through
       its ``withdraw-case-ownership-transfer`` trigger
       (UndoCaseOwnershipTransferActivity → **CaseActor** inbox, CM-21-015,
       TRIG-11-006)
    5. Once the CaseActor has ledgered the withdrawal, verify
       case.attributed_to remains with vendor

    This follows the withdrawal branch in
    docs/topics/case_lifecycle/ownership_transfer.md.
    """
    logger.info("=" * 80)
    logger.info("DEMO: Transfer Ownership — Withdraw Path")
    logger.info("=" * 80)

    case, case_actor_id = _setup_transfer_precondition(
        client, reporter, vendor, coordinator
    )
    original_owner = _initial_owner(client, case, case_actor_id)

    # Bound before the step (#2308): a failed step leaves no unbound name.
    offer_id = ""
    with demo_step(
        "Step 2: Vendor offers case ownership to coordinator via the CaseActor"
    ):
        offer_id = _vendor_offers_ownership(
            client, case, vendor, coordinator, case_actor_id
        )

    with demo_gate(
        "Step 3: CaseActor forwarded the Offer to the coordinator (CM-21-005)"
    ):
        forwarded_offer_id = await_forwarded_ownership_transfer_offer(
            client, case=case, transferee=coordinator
        )
        logger.info("Forwarded offer id: %s", forwarded_offer_id)

        with demo_step(
            "Step 4: Vendor withdraws the ownership transfer offer"
        ):
            # Through the vendor's own trigger (DEMOMA-05-001, TRIG-11-006),
            # naming the Offer the vendor made: that is the one the CaseActor
            # ledgered, and the one the vendor's store holds.
            undo = (
                ActorSession(client=client, actor=vendor)
                .quiet()
                .withdraw_case_ownership_transfer(offer_id=offer_id)
                .activity
            )
            logger.info("Vendor sent withdrawal: %s", logfmt(undo))
            with demo_check(
                "Withdrawal addressed to the CaseActor (CM-21-015)"
            ):
                recipients = recipient_ids(undo.to)
                if recipients != [case_actor_id]:
                    raise ValueError(
                        f"Expected the Undo addressed to '{case_actor_id}',"
                        f" got: {recipients}"
                    )

    # Gate on the cause (EDF-06): the CaseActor ledgers the withdrawal and
    # broadcasts it (CM-21-015); that entry is what closes the Offer.
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
            _check_owner_unchanged(
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
