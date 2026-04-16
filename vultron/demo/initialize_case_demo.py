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
from typing import Callable, Optional, Sequence, Tuple

# Vultron imports
from vultron.wire.as2.vocab.activities.case import (
    AddReportToCaseActivity,
    CreateCaseActivity,
)
from vultron.wire.as2.vocab.activities.case_participant import (
    AddParticipantToCaseActivity,
)
from vultron.wire.as2.vocab.activities.report import (
    RmSubmitReportActivity,
    RmValidateReportActivity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Create
from vultron.wire.as2.vocab.objects.case_participant import (
    FinderReporterParticipant,
    VendorParticipant,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.demo.utils import (  # noqa: F401 — BASE_URL needed for test monkeypatching
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
    ref_id,
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
    2. Vendor validates the report (RmValidateReportActivity)
    3. Vendor explicitly creates a VulnerabilityCase (CreateCaseActivity)
    4. Vendor adds themselves as VendorParticipant (case creator/owner)
    5. Vendor adds the report to the case (AddReportToCaseActivity)
    6. Vendor creates a FinderReporterParticipant for the finder
    7. Vendor adds the finder participant to the case (AddParticipantToCaseActivity)
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
            attributed_to=finder.id_,
            content="A remote code execution vulnerability in the web framework.",
            name="Remote Code Execution Vulnerability",
        )
        logger.info(f"Created report: {logfmt(report)}")
        report_offer = RmSubmitReportActivity(
            actor=finder.id_,
            object_=report,
            to=[vendor.id_],
        )
        post_to_inbox_and_wait(client, vendor.id_, report_offer)
        with demo_check("Report stored in data layer"):
            verify_object_stored(client, report.id_)

    with demo_step("Step 2: Vendor validates report"):
        offer = get_offer_from_datalayer(client, vendor.id_, report_offer.id_)
        validate_activity = RmValidateReportActivity(
            actor=vendor.id_,
            object_=offer.id_,
            content="Confirmed — remote code execution via unsanitized input.",
        )
        post_to_inbox_and_wait(client, vendor.id_, validate_activity)

    with demo_step("Step 3: Vendor creates vulnerability case"):
        case = VulnerabilityCase(
            attributed_to=vendor.id_,
            name="RCE Case — Web Framework",
            content="Tracking the RCE vulnerability in the web framework.",
        )
        logger.info(f"Created case object: {logfmt(case)}")
        create_case_activity = CreateCaseActivity(
            actor=vendor.id_,
            object_=case,
        )
        post_to_inbox_and_wait(client, vendor.id_, create_case_activity)
        with demo_check("Case stored in data layer"):
            verify_object_stored(client, case.id_)
        with demo_check("Case state after CreateCaseActivity"):
            log_case_state(client, case.id_, "after CreateCaseActivity")

    with demo_step("Step 4: Vendor adds themselves as case participant"):
        vendor_participant = VendorParticipant(
            attributed_to=vendor.id_,
            context=case.id_,
        )
        logger.info(
            f"Created vendor participant: {logfmt(vendor_participant)}"
        )
        create_vendor_participant_activity = as_Create(
            actor=vendor.id_,
            object_=vendor_participant,
            context=case.id_,
        )
        post_to_inbox_and_wait(
            client, vendor.id_, create_vendor_participant_activity
        )
        with demo_check("Vendor participant stored"):
            verify_object_stored(client, vendor_participant.id_)

        add_vendor_participant_activity = AddParticipantToCaseActivity(
            actor=vendor.id_,
            object_=vendor_participant,
            target=case.id_,
        )
        post_to_inbox_and_wait(
            client, vendor.id_, add_vendor_participant_activity
        )
        with demo_check("Vendor added to case participant list"):
            vendor_case = log_case_state(
                client, case.id_, "after vendor AddParticipantToCaseActivity"
            )
            if vendor_case and vendor_participant.id_ not in [
                (ref_id(p) or str(p)) for p in vendor_case.case_participants
            ]:
                raise ValueError(
                    f"Vendor participant '{vendor_participant.id_}' not found in"
                    " case after AddParticipantToCaseActivity"
                )
        logger.info("Vendor added as participant to case")

    with demo_step("Step 5: Vendor links report to case"):
        add_report_activity = AddReportToCaseActivity(
            actor=vendor.id_,
            object_=report,
            target=case.id_,
        )
        post_to_inbox_and_wait(client, vendor.id_, add_report_activity)
        with demo_check("Report linked to case"):
            updated_case = log_case_state(
                client, case.id_, "after AddReportToCaseActivity"
            )
            if updated_case and report.id_ not in [
                (ref_id(r) or str(r))
                for r in updated_case.vulnerability_reports
            ]:
                raise ValueError(
                    f"Report '{report.id_}' not found in case after AddReportToCaseActivity"
                )

    with demo_step("Step 6: Vendor creates finder participant"):
        participant = FinderReporterParticipant(
            attributed_to=finder.id_,
            context=case.id_,
        )
        logger.info(f"Created participant: {logfmt(participant)}")
        create_participant_activity = as_Create(
            actor=vendor.id_,
            object_=participant,
            context=case.id_,
        )
        post_to_inbox_and_wait(client, vendor.id_, create_participant_activity)
        with demo_check("Finder participant stored"):
            verify_object_stored(client, participant.id_)

    with demo_step("Step 7: Vendor adds finder participant to case"):
        add_participant_activity = AddParticipantToCaseActivity(
            actor=vendor.id_,
            object_=participant,
            target=case.id_,
        )
        post_to_inbox_and_wait(client, vendor.id_, add_participant_activity)
        with demo_check("Finder participant in case participant list"):
            final_case = log_case_state(
                client, case.id_, "after AddParticipantToCaseActivity"
            )
            if final_case and participant.id_ not in [
                (ref_id(p) or str(p)) for p in final_case.case_participants
            ]:
                raise ValueError(
                    f"Participant '{participant.id_}' not found in case "
                    "after AddParticipantToCaseActivity"
                )

    logger.info(
        "✅ DEMO COMPLETE: Case initialized with vendor and finder participants."
    )


_ALL_DEMOS: Sequence[Tuple[str, Callable[..., None]]] = [
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
