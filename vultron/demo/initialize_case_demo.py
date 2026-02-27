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
Demonstrates the workflow for initializing a vulnerability case via the Vultron API.

This demo script showcases the case initialization process:

1. Setup: submit a vulnerability report (precondition for case creation)
2. Create Case: vendor explicitly creates a VulnerabilityCase
3. Add Vendor as Participant: vendor adds themselves as case creator/owner
4. Add Report to Case: vendor links the submitted report to the case
5. Create Participant: vendor creates a CaseParticipant for the finder
6. Add Participant to Case: vendor adds the finder participant to the case
7. Show final case state

This corresponds to the workflow documented in:
    docs/howto/activitypub/activities/initialize_case.md

When run as a script, this module will:
1. Check if the API server is available
2. Reset the data layer to a clean state
3. Discover actors (finder, vendor, coordinator) via the API
4. Run the initialize_case demo workflow
5. Verify side effects in the data layer

Note on direct inbox communication:
This demo uses direct inbox-to-inbox communication between actors, per the Vultron
prototype design. Actors post activities directly to each other's inboxes.
"""

# Standard library imports
import logging
import sys
from typing import Optional, Sequence, Tuple

# Vultron imports
from vultron.as_vocab.activities.case import AddReportToCase, CreateCase
from vultron.as_vocab.activities.case_participant import AddParticipantToCase
from vultron.as_vocab.activities.report import RmSubmitReport, RmValidateReport
from vultron.as_vocab.base.objects.activities.transitive import as_Create
from vultron.as_vocab.objects.case_participant import (
    FinderReporterParticipant,
    VendorParticipant,
)
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport
from vultron.as_vocab.base.objects.actors import as_Actor
from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.demo.utils import (
    BASE_URL,
    DataLayerClient,
    check_server_availability,
    demo_check,
    demo_step,
    discover_actors,
    get_offer_from_datalayer,
    init_actor_ios,
    log_case_state,
    logfmt,
    demo_environment,
    post_to_inbox_and_wait,
    verify_object_stored,
)

logger = logging.getLogger(__name__)


def demo_initialize_case(
    client: DataLayerClient, finder: as_Actor, vendor: as_Actor
):
    """
    Demonstrates the full case initialization workflow.

    Steps:
    1. Finder submits a vulnerability report to vendor inbox
    2. Vendor validates the report (RmValidateReport)
    3. Vendor explicitly creates a VulnerabilityCase (CreateCase)
    4. Vendor adds themselves as VendorParticipant (case creator/owner)
    5. Vendor adds the report to the case (AddReportToCase)
    6. Vendor creates a FinderReporterParticipant for the finder
    7. Vendor adds the finder participant to the case (AddParticipantToCase)
    8. Final case state is logged

    This follows the workflow in docs/howto/activitypub/activities/initialize_case.md.
    The case creator (vendor) must be added as a participant before any other
    participants, as they need to be a case participant to act on the case.
    The vendor is also the case owner, indicated by attributed_to on the case.
    """
    logger.info("=" * 80)
    logger.info("DEMO: Initialize Case")
    logger.info("=" * 80)

    with demo_step("Step 1: Finder submits vulnerability report to vendor"):
        report = VulnerabilityReport(
            attributed_to=finder.as_id,
            content="A remote code execution vulnerability in the web framework.",
            name="Remote Code Execution Vulnerability",
        )
        logger.info(f"Created report: {logfmt(report)}")
        report_offer = RmSubmitReport(
            actor=finder.as_id,
            as_object=report,
            to=[vendor.as_id],
        )
        post_to_inbox_and_wait(client, vendor.as_id, report_offer)
        with demo_check("Report stored in data layer"):
            verify_object_stored(client, report.as_id)

    with demo_step("Step 2: Vendor validates report"):
        offer = get_offer_from_datalayer(
            client, vendor.as_id, report_offer.as_id
        )
        validate_activity = RmValidateReport(
            actor=vendor.as_id,
            object=offer.as_id,
            content="Confirmed — remote code execution via unsanitized input.",
        )
        post_to_inbox_and_wait(client, vendor.as_id, validate_activity)

    with demo_step("Step 3: Vendor creates vulnerability case"):
        case = VulnerabilityCase(
            attributed_to=vendor.as_id,
            name="RCE Case — Web Framework",
            content="Tracking the RCE vulnerability in the web framework.",
        )
        logger.info(f"Created case object: {logfmt(case)}")
        create_case_activity = CreateCase(
            actor=vendor.as_id,
            as_object=case,
        )
        post_to_inbox_and_wait(client, vendor.as_id, create_case_activity)
        with demo_check("Case stored in data layer"):
            verify_object_stored(client, case.as_id)
        with demo_check("Case state after CreateCase"):
            log_case_state(client, case.as_id, "after CreateCase")

    with demo_step("Step 4: Vendor adds themselves as case participant"):
        vendor_participant = VendorParticipant(
            attributed_to=vendor.as_id,
            context=case.as_id,
        )
        logger.info(
            f"Created vendor participant: {logfmt(vendor_participant)}"
        )
        create_vendor_participant_activity = as_Create(
            actor=vendor.as_id,
            as_object=vendor_participant,
            context=case.as_id,
        )
        post_to_inbox_and_wait(
            client, vendor.as_id, create_vendor_participant_activity
        )
        with demo_check("Vendor participant stored"):
            verify_object_stored(client, vendor_participant.as_id)

        add_vendor_participant_activity = AddParticipantToCase(
            actor=vendor.as_id,
            as_object=vendor_participant.as_id,
            target=case.as_id,
        )
        post_to_inbox_and_wait(
            client, vendor.as_id, add_vendor_participant_activity
        )
        with demo_check("Vendor added to case participant list"):
            vendor_case = log_case_state(
                client, case.as_id, "after vendor AddParticipantToCase"
            )
            if vendor_case and vendor_participant.as_id not in [
                (p.as_id if hasattr(p, "as_id") else p)
                for p in vendor_case.case_participants
            ]:
                raise ValueError(
                    f"Vendor participant '{vendor_participant.as_id}' not found in"
                    " case after AddParticipantToCase"
                )
        logger.info("Vendor added as participant to case")

    with demo_step("Step 5: Vendor links report to case"):
        add_report_activity = AddReportToCase(
            actor=vendor.as_id,
            as_object=report.as_id,
            target=case.as_id,
        )
        post_to_inbox_and_wait(client, vendor.as_id, add_report_activity)
        with demo_check("Report linked to case"):
            updated_case = log_case_state(
                client, case.as_id, "after AddReportToCase"
            )
            if updated_case and report.as_id not in [
                (r.as_id if hasattr(r, "as_id") else r)
                for r in updated_case.vulnerability_reports
            ]:
                raise ValueError(
                    f"Report '{report.as_id}' not found in case after AddReportToCase"
                )

    with demo_step("Step 6: Vendor creates finder participant"):
        participant = FinderReporterParticipant(
            attributed_to=finder.as_id,
            context=case.as_id,
        )
        logger.info(f"Created participant: {logfmt(participant)}")
        create_participant_activity = as_Create(
            actor=vendor.as_id,
            as_object=participant,
            context=case.as_id,
        )
        post_to_inbox_and_wait(
            client, vendor.as_id, create_participant_activity
        )
        with demo_check("Finder participant stored"):
            verify_object_stored(client, participant.as_id)

    with demo_step("Step 7: Vendor adds finder participant to case"):
        add_participant_activity = AddParticipantToCase(
            actor=vendor.as_id,
            as_object=participant.as_id,
            target=case.as_id,
        )
        post_to_inbox_and_wait(client, vendor.as_id, add_participant_activity)
        with demo_check("Finder participant in case participant list"):
            final_case = log_case_state(
                client, case.as_id, "after AddParticipantToCase"
            )
            if final_case and participant.as_id not in [
                (p.as_id if hasattr(p, "as_id") else p)
                for p in final_case.case_participants
            ]:
                raise ValueError(
                    f"Participant '{participant.as_id}' not found in case "
                    "after AddParticipantToCase"
                )

    logger.info(
        "✅ DEMO COMPLETE: Case initialized with vendor and finder participants."
    )


_ALL_DEMOS: Sequence[Tuple[str, object]] = [
    ("Demo: Initialize Case", demo_initialize_case),
]


def main(
    skip_health_check: bool = False,
    demos: Optional[Sequence] = None,
):
    """
    Main entry point for the initialize_case demo script.

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
                demo_fn(client, finder, vendor)
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
