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

Each demo starts from an initialized case (report submitted and validated,
case created, finder participant added) so that the transfer workflow can
be demonstrated in isolation.

This corresponds to the workflow documented in:
    docs/howto/activitypub/activities/transfer_ownership.md

When run as a script, this module will:
1. Check if the API server is available
2. Reset the data layer to a clean state
3. Discover actors (finder, vendor, coordinator) via the API
4. Run both demo workflows (accept and reject)
5. Verify side effects in the data layer

Note on direct inbox communication:
This demo uses direct inbox-to-inbox communication between actors, per the
Vultron prototype design. Actors post activities directly to each other's
inboxes.
"""

# Standard library imports
import logging
import sys
from typing import Callable, Optional, Sequence, Tuple

# Vultron imports
from vultron.wire.as2.vocab.activities.case import (
    AcceptCaseOwnershipTransferActivity,
    AddReportToCaseActivity,
    CreateCaseActivity,
    OfferCaseOwnershipTransferActivity,
    RejectCaseOwnershipTransferActivity,
)
from vultron.wire.as2.vocab.activities.case_participant import (
    AddParticipantToCaseActivity,
)
from vultron.wire.as2.vocab.activities.report import (
    RmSubmitReportActivity,
    RmValidateReportActivity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Create
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.case_participant import (
    FinderReporterParticipant,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)
from vultron.demo.utils import (
    DataLayerClient,
    check_server_availability,
    demo_check,
    demo_step,
    demo_environment,
    get_offer_from_datalayer,
    log_case_state,
    logfmt,
    post_to_inbox_and_wait,
    verify_object_stored,
)

logger = logging.getLogger(__name__)


def _setup_initialized_case(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
) -> VulnerabilityCase:
    """
    Set up an initialized case as a precondition for the transfer workflow.

    Mirrors the setup helper in invite_actor_demo but returns the
    VulnerabilityCase so subsequent steps can reference it.
    """
    report = VulnerabilityReport(
        attributed_to=finder.id_,
        content="A remote code execution vulnerability in the web framework.",
        name="Remote Code Execution Vulnerability",
    )
    report_offer = RmSubmitReportActivity(
        actor=finder.id_,
        object_=report,
        to=[vendor.id_],
    )
    post_to_inbox_and_wait(client, vendor.id_, report_offer)
    verify_object_stored(client, report.id_)

    offer = get_offer_from_datalayer(client, vendor.id_, report_offer.id_)
    validate_activity = RmValidateReportActivity(
        actor=vendor.id_,
        object_=offer.id_,
        content="Confirmed — remote code execution via unsanitized input.",
    )
    post_to_inbox_and_wait(client, vendor.id_, validate_activity)

    case = VulnerabilityCase(
        attributed_to=vendor.id_,
        name="RCE Case — Web Framework",
        content="Tracking the RCE vulnerability in the web framework.",
    )
    create_case_activity = CreateCaseActivity(
        actor=vendor.id_,
        object_=case,
    )
    post_to_inbox_and_wait(client, vendor.id_, create_case_activity)
    verify_object_stored(client, case.id_)

    add_report_activity = AddReportToCaseActivity(
        actor=vendor.id_,
        object_=report.id_,
        target=case.id_,
    )
    post_to_inbox_and_wait(client, vendor.id_, add_report_activity)

    participant = FinderReporterParticipant(
        attributed_to=finder.id_,
        context=case.id_,
    )
    create_participant_activity = as_Create(
        actor=vendor.id_,
        object_=participant,
        context=case.id_,
    )
    post_to_inbox_and_wait(client, vendor.id_, create_participant_activity)
    verify_object_stored(client, participant.id_)

    add_participant_activity = AddParticipantToCaseActivity(
        actor=vendor.id_,
        object_=participant.id_,
        target=case.id_,
    )
    post_to_inbox_and_wait(client, vendor.id_, add_participant_activity)

    log_case_state(client, case.id_, "after setup")
    logger.info("✓ Setup: Case initialized with report and finder participant")
    return case


def demo_transfer_ownership_accept(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor,
) -> None:
    """
    Demonstrates the accept path of the transfer-ownership workflow.

    Steps:
    1. Setup: initialize case (report submitted + validated, case created,
       finder participant added)
    2. Vendor offers case ownership to coordinator
       (OfferCaseOwnershipTransferActivity → coordinator inbox)
    3. Coordinator accepts (AcceptCaseOwnershipTransferActivity → vendor inbox)
    4. Verify case.attributed_to is updated to coordinator

    This follows the accept branch in
    docs/howto/activitypub/activities/transfer_ownership.md.
    """
    logger.info("=" * 80)
    logger.info("DEMO: Transfer Ownership — Accept Path")
    logger.info("=" * 80)

    case = _setup_initialized_case(client, finder, vendor)

    # Confirm initial owner is vendor
    initial_case = log_case_state(client, case.id_, "initial")
    if initial_case is None:
        raise ValueError("Could not retrieve initial case state")
    logger.info(f"Initial owner: {initial_case.attributed_to}")

    with demo_step("Step 2: Vendor offers case ownership to coordinator"):
        offer = OfferCaseOwnershipTransferActivity(
            actor=vendor.id_,
            object_=case.id_,
            to=[coordinator.id_],
            content=(f"Offering to transfer ownership of {case.name} to you."),
        )
        logger.info(f"Sending offer: {logfmt(offer)}")
        post_to_inbox_and_wait(client, coordinator.id_, offer)
        with demo_check("Ownership offer stored in data layer"):
            verify_object_stored(client, offer.id_)

    with demo_step("Step 3: Coordinator accepts ownership transfer"):
        accept = AcceptCaseOwnershipTransferActivity(
            actor=coordinator.id_,
            object_=offer.id_,
            to=[vendor.id_],
            content=(f"Accepting ownership of {case.name}."),
        )
        logger.info(f"Sending accept: {logfmt(accept)}")
        post_to_inbox_and_wait(client, vendor.id_, accept)

    with demo_step("Step 4: Verify case ownership transferred to coordinator"):
        with demo_check("Case attributed_to updated to coordinator"):
            final_case = log_case_state(client, case.id_, "after accept")
            if final_case is None:
                raise ValueError("Could not retrieve case after accept")
            new_owner = final_case.attributed_to
            coord_segment = coordinator.id_.split("/")[-1]
            if coord_segment not in str(new_owner):
                raise ValueError(
                    f"Expected case owner to be coordinator '{coordinator.id_}', "
                    f"got: {new_owner}"
                )
        logger.info(f"Case ownership transferred — new owner: {new_owner}")

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
    1. Setup: initialize case (report submitted + validated, case created,
       finder participant added)
    2. Vendor offers case ownership to coordinator
       (OfferCaseOwnershipTransferActivity → coordinator inbox)
    3. Coordinator rejects (RejectCaseOwnershipTransferActivity → vendor inbox)
    4. Verify case.attributed_to remains with vendor

    This follows the reject branch in
    docs/howto/activitypub/activities/transfer_ownership.md.
    """
    logger.info("=" * 80)
    logger.info("DEMO: Transfer Ownership — Reject Path")
    logger.info("=" * 80)

    case = _setup_initialized_case(client, finder, vendor)

    initial_case = log_case_state(client, case.id_, "initial")
    if initial_case is None:
        raise ValueError("Could not retrieve initial case state")
    original_owner = initial_case.attributed_to
    logger.info(f"Initial owner: {original_owner}")

    with demo_step("Step 2: Vendor offers case ownership to coordinator"):
        offer = OfferCaseOwnershipTransferActivity(
            actor=vendor.id_,
            object_=case.id_,
            to=[coordinator.id_],
            content=(f"Offering to transfer ownership of {case.name} to you."),
        )
        logger.info(f"Sending offer: {logfmt(offer)}")
        post_to_inbox_and_wait(client, coordinator.id_, offer)
        with demo_check("Ownership offer stored in data layer"):
            verify_object_stored(client, offer.id_)

    with demo_step("Step 3: Coordinator rejects ownership transfer"):
        reject = RejectCaseOwnershipTransferActivity(
            actor=coordinator.id_,
            object_=offer.id_,
            to=[vendor.id_],
            content=(f"Declining ownership of {case.name}."),
        )
        logger.info(f"Sending reject: {logfmt(reject)}")
        post_to_inbox_and_wait(client, vendor.id_, reject)

    with demo_step("Step 4: Verify case ownership unchanged"):
        with demo_check("Case attributed_to still vendor"):
            final_case = log_case_state(client, case.id_, "after reject")
            if final_case is None:
                raise ValueError("Could not retrieve case after reject")
            if final_case.attributed_to != original_owner:
                raise ValueError(
                    f"Expected case owner to remain '{original_owner}' after reject, "
                    f"got: {final_case.attributed_to}"
                )
        logger.info(
            f"Ownership unchanged — still with: {final_case.attributed_to}"
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
    """
    Main entry point for the transfer_ownership demo script.

    Args:
        skip_health_check: Skip server availability check (useful for testing)
        demos: Optional sequence of demo functions to run. Defaults to all.
    """
    client = DataLayerClient()

    if not skip_health_check and not check_server_availability(client):
        logger.error("=" * 80)
        logger.error("ERROR: API server is not available")
        logger.error("=" * 80)
        logger.error(f"Cannot connect to: {client.base_url}")
        logger.error("")
        logger.error("Please ensure the Vultron API server is running:")
        logger.error(
            "  uv run uvicorn vultron.api.main:app --host localhost --port 7999"
        )
        logger.error("=" * 80)
        sys.exit(1)

    selected = (
        _ALL_DEMOS
        if demos is None
        else [(name, fn) for name, fn in _ALL_DEMOS if fn in demos]
    )
    total = len(selected)
    errors = []

    for demo_name, demo_fn in selected:
        try:
            with demo_environment(client) as (finder, vendor, coordinator):
                demo_fn(client, finder, vendor, coordinator)
        except Exception as e:
            logger.error(f"{demo_name} failed: {e}", exc_info=True)
            errors.append((demo_name, str(e)))

    logger.info("=" * 80)
    logger.info("ALL DEMOS COMPLETE")
    logger.info("=" * 80)

    if errors:
        logger.error("")
        logger.error("=" * 80)
        logger.error("ERROR SUMMARY")
        logger.error("=" * 80)
        logger.error(f"Total demos: {total}")
        logger.error(f"Failed demos: {len(errors)}")
        logger.error(f"Successful demos: {total - len(errors)}")
        logger.error("")
        for demo_name, error in errors:
            logger.error(f"{demo_name}:")
            logger.error(f"  {error}")
            logger.error("")
        logger.error("=" * 80)
    else:
        logger.info("")
        logger.info(f"✓ All {total} demos completed successfully!")
        logger.info("")


def _setup_logging():
    """Configure console logging for standalone script execution."""
    logging.getLogger("requests").setLevel(logging.WARNING)
    logger_ = logging.getLogger()
    hdlr = logging.StreamHandler(sys.stdout)
    import logging as _logging

    formatter = _logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    hdlr.setFormatter(formatter)
    logger_.addHandler(hdlr)
    logger_.setLevel(logging.DEBUG)


if __name__ == "__main__":
    _setup_logging()
    main()
