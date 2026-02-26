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
Demonstrates the workflow for initializing a CaseParticipant via the Vultron API.

This demo script showcases the standalone participant initialization process:

1. Setup: Create a case with vendor as owner/participant (precondition)
2. Create Coordinator Participant: vendor creates a CoordinatorParticipant
3. Add Coordinator to Case: vendor adds the coordinator participant to the case
4. Create Finder Participant: vendor creates a FinderReporterParticipant
5. Add Finder to Case: vendor adds the finder participant to the case
6. Show case participant list before and after each addition

This corresponds to the workflow documented in:
    docs/howto/activitypub/activities/initialize_participant.md

This workflow is standalone — it does not require a prior Invite.
Compare with invite_actor_demo.py, which demonstrates the invite-based path.

When run as a script, this module will:
1. Check if the API server is available
2. Reset the data layer to a clean state
3. Discover actors (finder, vendor, coordinator) via the API
4. Run the initialize_participant demo workflow
5. Verify side effects in the data layer
"""

# Standard library imports
import logging
import sys
from typing import Optional, Sequence, Tuple

# Vultron imports
from vultron.as_vocab.activities.case import AddReportToCase, CreateCase
from vultron.as_vocab.activities.case_participant import (
    AddParticipantToCase,
    CreateParticipant,
)
from vultron.as_vocab.activities.report import RmSubmitReport, RmValidateReport
from vultron.as_vocab.base.objects.actors import as_Actor
from vultron.as_vocab.objects.case_participant import (
    CoordinatorParticipant,
    FinderReporterParticipant,
    VendorParticipant,
)
from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport
from vultron.demo.utils import (
    BASE_URL,
    DataLayerClient,
    check_server_availability,
    demo_check,
    demo_step,
    get_offer_from_datalayer,
    log_case_state,
    logfmt,
    demo_environment,
    post_to_inbox_and_wait,
    verify_object_stored,
)

logger = logging.getLogger(__name__)


def setup_case_precondition(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
) -> Tuple[VulnerabilityReport, VulnerabilityCase]:
    """
    Sets up the precondition for the demo: a case owned by the vendor with
    a validated report and vendor as the only participant.

    Returns:
        Tuple of (report, case) for use in the demo workflow.
    """
    logger.info("Setting up case precondition...")

    report = VulnerabilityReport(
        attributed_to=finder.as_id,
        content="An integer overflow vulnerability in the network stack.",
        name="Integer Overflow in Network Stack",
    )
    report_offer = RmSubmitReport(
        actor=finder.as_id,
        as_object=report,
        to=[vendor.as_id],
    )
    post_to_inbox_and_wait(client, vendor.as_id, report_offer)

    offer = get_offer_from_datalayer(client, vendor.as_id, report_offer.as_id)
    validate_activity = RmValidateReport(
        actor=vendor.as_id,
        object=offer.as_id,
        content="Confirmed — integer overflow via crafted packet.",
    )
    post_to_inbox_and_wait(client, vendor.as_id, validate_activity)

    case = VulnerabilityCase(
        attributed_to=vendor.as_id,
        name="Integer Overflow Case — Network Stack",
        content="Tracking the integer overflow vulnerability in the network stack.",
    )
    create_case_activity = CreateCase(
        actor=vendor.as_id,
        as_object=case,
    )
    post_to_inbox_and_wait(client, vendor.as_id, create_case_activity)

    vendor_participant = VendorParticipant(
        attributed_to=vendor.as_id,
        context=case.as_id,
    )
    create_vendor_participant = CreateParticipant(
        actor=vendor.as_id,
        as_object=vendor_participant,
        context=case.as_id,
    )
    post_to_inbox_and_wait(client, vendor.as_id, create_vendor_participant)

    add_vendor_participant = AddParticipantToCase(
        actor=vendor.as_id,
        as_object=vendor_participant.as_id,
        target=case.as_id,
    )
    post_to_inbox_and_wait(client, vendor.as_id, add_vendor_participant)

    add_report_activity = AddReportToCase(
        actor=vendor.as_id,
        as_object=report.as_id,
        target=case.as_id,
    )
    post_to_inbox_and_wait(client, vendor.as_id, add_report_activity)

    logger.info("Case precondition setup complete.")
    return report, case


def demo_initialize_participant(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor,
):
    """
    Demonstrates the standalone CaseParticipant initialization workflow.

    Precondition: An existing VulnerabilityCase with vendor as the owner and
    sole participant is set up before the demo begins.

    Steps:
    1. Show case participant list (vendor only)
    2. Vendor creates a CoordinatorParticipant (standalone, no prior invite)
    3. Vendor adds the coordinator participant to the case
    4. Show updated participant list
    5. Vendor creates a FinderReporterParticipant (standalone)
    6. Vendor adds the finder participant to the case
    7. Show final participant list

    This follows the workflow in:
        docs/howto/activitypub/activities/initialize_participant.md
    """
    logger.info("=" * 80)
    logger.info("DEMO: Initialize Case Participant")
    logger.info("=" * 80)

    report, case = setup_case_precondition(client, finder, vendor)

    with demo_check("Initial case state: vendor is sole participant"):
        initial_case = log_case_state(client, case.as_id, "initial")
        if initial_case is None:
            raise ValueError("Could not fetch initial case state")
        logger.info(
            f"Initial participant count: {len(initial_case.case_participants)}"
        )

    with demo_step(
        "Step 1: Vendor creates coordinator participant (standalone)"
    ):
        coordinator_participant = CoordinatorParticipant(
            attributed_to=coordinator.as_id,
            context=case.as_id,
        )
        logger.info(
            f"Created coordinator participant: {logfmt(coordinator_participant)}"
        )
        create_coordinator_participant = CreateParticipant(
            actor=vendor.as_id,
            as_object=coordinator_participant,
            context=case.as_id,
        )
        post_to_inbox_and_wait(
            client, vendor.as_id, create_coordinator_participant
        )
        with demo_check("Coordinator participant stored in data layer"):
            verify_object_stored(client, coordinator_participant.as_id)

    with demo_step("Step 2: Vendor adds coordinator participant to case"):
        add_coordinator_participant = AddParticipantToCase(
            actor=vendor.as_id,
            as_object=coordinator_participant.as_id,
            target=case.as_id,
        )
        post_to_inbox_and_wait(
            client, vendor.as_id, add_coordinator_participant
        )
        with demo_check("Coordinator participant added to case"):
            updated_case = log_case_state(
                client, case.as_id, "after coordinator AddParticipantToCase"
            )
            if updated_case and coordinator_participant.as_id not in [
                (p.as_id if hasattr(p, "as_id") else p)
                for p in updated_case.case_participants
            ]:
                raise ValueError(
                    f"Coordinator participant '{coordinator_participant.as_id}'"
                    " not found in case after AddParticipantToCase"
                )
        logger.info("Coordinator added as participant to case")

    with demo_step(
        "Step 3: Vendor creates finder/reporter participant (standalone)"
    ):
        finder_participant = FinderReporterParticipant(
            attributed_to=finder.as_id,
            context=case.as_id,
        )
        logger.info(
            f"Created finder participant: {logfmt(finder_participant)}"
        )
        create_finder_participant = CreateParticipant(
            actor=vendor.as_id,
            as_object=finder_participant,
            context=case.as_id,
        )
        post_to_inbox_and_wait(client, vendor.as_id, create_finder_participant)
        with demo_check("Finder participant stored in data layer"):
            verify_object_stored(client, finder_participant.as_id)

    with demo_step("Step 4: Vendor adds finder participant to case"):
        add_finder_participant = AddParticipantToCase(
            actor=vendor.as_id,
            as_object=finder_participant.as_id,
            target=case.as_id,
        )
        post_to_inbox_and_wait(client, vendor.as_id, add_finder_participant)
        with demo_check("Finder participant added to case"):
            final_case = log_case_state(
                client, case.as_id, "after finder AddParticipantToCase"
            )
            if final_case and finder_participant.as_id not in [
                (p.as_id if hasattr(p, "as_id") else p)
                for p in final_case.case_participants
            ]:
                raise ValueError(
                    f"Finder participant '{finder_participant.as_id}' not found"
                    " in case after AddParticipantToCase"
                )
        logger.info("Finder added as participant to case")

    with demo_check("Final case has three participants"):
        final_case = log_case_state(client, case.as_id, "final")
        if final_case is None:
            raise ValueError("Could not fetch final case state")
        participant_count = len(final_case.case_participants)
        if participant_count != 3:
            raise ValueError(
                f"Expected 3 participants (vendor, coordinator, finder),"
                f" got {participant_count}"
            )
        logger.info(
            f"Final participant count: {participant_count} ✓"
            " (vendor + coordinator + finder)"
        )

    logger.info(
        "✅ DEMO COMPLETE: Case initialized with vendor, coordinator,"
        " and finder participants."
    )


_ALL_DEMOS: Sequence[Tuple[str, object]] = [
    ("Demo: Initialize Case Participant", demo_initialize_participant),
]


def main(
    skip_health_check: bool = False,
    demos: Optional[Sequence] = None,
):
    """
    Main entry point for the initialize_participant demo script.

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
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    hdlr.setFormatter(formatter)
    logger_.addHandler(hdlr)
    logger_.setLevel(logging.DEBUG)


if __name__ == "__main__":
    _setup_logging()
    main()
