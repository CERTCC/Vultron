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
Demonstrates the case management workflow via the Vultron API.

This demo script showcases the Report Management (RM) process:

1. Engage Path: submit → validate → create_case → engage → close
2. Defer and Re-engage Path: submit → validate → create_case →
   defer → re-engage → close
3. Invalidate Path: submit → invalidate → close_report

The manage_case workflow corresponds to:
    docs/howto/activitypub/activities/manage_case.md

Key activities demonstrated:
- RmSubmitReport (as:Offer) — finder submits a report to vendor
- RmValidateReport (as:Accept) — vendor validates the report
- RmInvalidateReport (as:TentativeReject) — vendor invalidates the report
- CreateCase (as:Create) — vendor creates a VulnerabilityCase
- RmEngageCase (as:Join) — actor actively engages the case (RM → ACCEPTED)
- RmDeferCase (as:Ignore) — actor defers the case (RM → DEFERRED)
- RmCloseCase (as:Leave) — actor closes the case (RM → CLOSED)
- RmCloseReport (as:Reject) — vendor closes an invalid report

Note on re-engagement:
Per implementation notes, re-engaging a deferred case is done by sending
another RmEngageCase (as:Join) activity. There is no separate RmReEngageCase
activity; the RM state machine allows a direct DEFERRED → ACCEPTED transition.

When run as a script, this module will:
1. Check if the API server is available
2. Run three demo workflows, each resetting to a clean state:
   - demo_engage_path: submit → validate → create_case → engage → close
   - demo_defer_reengage_path: submit → validate → create_case →
     defer → re-engage → close
   - demo_invalidate_path: submit → invalidate → close_report
3. Verify side effects in the data layer for each workflow
"""

# Standard library imports
import logging
import sys
from typing import Optional, Sequence, Tuple

# Vultron imports
from vultron.as_vocab.activities.case import (
    AddReportToCase,
    CreateCase,
    RmCloseCase,
    RmDeferCase,
    RmEngageCase,
)
from vultron.as_vocab.activities.case_participant import AddParticipantToCase
from vultron.as_vocab.activities.report import (
    RmCloseReport,
    RmInvalidateReport,
    RmSubmitReport,
    RmValidateReport,
)
from vultron.as_vocab.base.objects.actors import as_Actor
from vultron.as_vocab.objects.case_participant import VendorParticipant
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
    post_to_inbox_and_wait,
    reset_datalayer,
    setup_clean_environment,
    verify_object_stored,
)

logger = logging.getLogger(__name__)


def setup_report_and_case(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    report_name: str,
    report_content: str,
    case_name: str,
    case_content: str,
) -> Tuple[VulnerabilityReport, VulnerabilityCase]:
    """
    Shared setup: submit and validate a report, create a case, and add the
    vendor as a participant with the report linked.

    Returns the created report and case objects.
    """
    report = VulnerabilityReport(
        attributed_to=finder.as_id,
        content=report_content,
        name=report_name,
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
        content="Confirmed — vulnerability verified.",
    )
    post_to_inbox_and_wait(client, vendor.as_id, validate_activity)

    case = VulnerabilityCase(
        attributed_to=vendor.as_id,
        name=case_name,
        content=case_content,
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
    from vultron.as_vocab.base.objects.activities.transitive import as_Create

    create_vendor_participant = as_Create(
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

    add_report = AddReportToCase(
        actor=vendor.as_id,
        as_object=report.as_id,
        target=case.as_id,
    )
    post_to_inbox_and_wait(client, vendor.as_id, add_report)

    return report, case


def demo_engage_path(
    client: DataLayerClient, finder: as_Actor, vendor: as_Actor
):
    """
    Demonstrates the full happy-path case management workflow:
    submit → validate → create_case → engage → close.

    Workflow steps:
    1. Finder submits report; vendor validates it
    2. Vendor creates VulnerabilityCase; adds vendor participant and report
    3. Vendor engages the case (RmEngageCase — RM → ACCEPTED)
    4. Vendor closes the case (RmCloseCase — RM → CLOSED)
    """
    logger.info("=" * 80)
    logger.info("DEMO 1: Engage Path (submit → validate → engage → close)")
    logger.info("=" * 80)

    with demo_step(
        "Steps 1–2: Submit report, validate, create case with vendor "
        "participant"
    ):
        report, case = setup_report_and_case(
            client=client,
            finder=finder,
            vendor=vendor,
            report_name="Buffer Overflow in Image Parser",
            report_content=(
                "A heap buffer overflow in the image parsing library allows "
                "remote code execution."
            ),
            case_name="Image Parser Buffer Overflow Case",
            case_content="Tracking the image parser heap buffer overflow.",
        )
        with demo_check("Case created and report linked"):
            updated_case = log_case_state(client, case.as_id, "after setup")
            if updated_case and report.as_id not in [
                (r.as_id if hasattr(r, "as_id") else r)
                for r in updated_case.vulnerability_reports
            ]:
                raise ValueError(
                    f"Report '{report.as_id}' not linked to case after setup"
                )

    with demo_step("Step 3: Vendor engages the case (RmEngageCase)"):
        engage = RmEngageCase(
            actor=vendor.as_id,
            as_object=case.as_id,
        )
        post_to_inbox_and_wait(client, vendor.as_id, engage)
        with demo_check("RmEngageCase activity stored"):
            verify_object_stored(client, engage.as_id)

    with demo_step("Step 4: Vendor closes the case (RmCloseCase)"):
        close = RmCloseCase(
            actor=vendor.as_id,
            as_object=case.as_id,
        )
        post_to_inbox_and_wait(client, vendor.as_id, close)
        with demo_check("RmCloseCase activity stored"):
            verify_object_stored(client, close.as_id)

    logger.info("✅ DEMO 1 COMPLETE: Case engaged then closed.")


def demo_defer_reengage_path(
    client: DataLayerClient, finder: as_Actor, vendor: as_Actor
):
    """
    Demonstrates the defer-and-re-engage path:
    submit → validate → create_case → defer → re-engage → close.

    Per implementation notes, re-engaging a deferred case uses another
    RmEngageCase (as:Join) — there is no separate RmReEngageCase activity.
    The RM state machine allows a direct DEFERRED → ACCEPTED transition.

    Workflow steps:
    1. Finder submits report; vendor validates it
    2. Vendor creates case with vendor participant and linked report
    3. Vendor defers the case (RmDeferCase — RM → DEFERRED)
    4. Vendor re-engages via RmEngageCase (RM → ACCEPTED)
    5. Vendor closes the case (RmCloseCase — RM → CLOSED)
    """
    logger.info("=" * 80)
    logger.info(
        "DEMO 2: Defer and Re-engage Path "
        "(submit → validate → defer → re-engage → close)"
    )
    logger.info("=" * 80)

    with demo_step(
        "Steps 1–2: Submit report, validate, create case with vendor "
        "participant"
    ):
        report, case = setup_report_and_case(
            client=client,
            finder=finder,
            vendor=vendor,
            report_name="SQL Injection in Login Form",
            report_content=(
                "An SQL injection vulnerability in the login form allows "
                "authentication bypass."
            ),
            case_name="Login Form SQL Injection Case",
            case_content="Tracking the login form SQL injection vulnerability.",
        )
        with demo_check("Case created and report linked"):
            log_case_state(client, case.as_id, "after setup")

    with demo_step("Step 3: Vendor defers the case (RmDeferCase)"):
        defer = RmDeferCase(
            actor=vendor.as_id,
            as_object=case.as_id,
        )
        post_to_inbox_and_wait(client, vendor.as_id, defer)
        with demo_check("RmDeferCase activity stored"):
            verify_object_stored(client, defer.as_id)
        logger.info("Case is now deferred (RM → DEFERRED).")

    with demo_step(
        "Step 4: Vendor re-engages the case (RmEngageCase from DEFERRED)"
    ):
        reengage = RmEngageCase(
            actor=vendor.as_id,
            as_object=case.as_id,
        )
        post_to_inbox_and_wait(client, vendor.as_id, reengage)
        with demo_check("RmEngageCase (re-engage) activity stored"):
            verify_object_stored(client, reengage.as_id)
        logger.info(
            "Case re-engaged via RmEngageCase (RM → ACCEPTED). "
            "Note: re-engagement uses the same RmEngageCase activity as initial "
            "engagement; there is no separate RmReEngageCase activity."
        )

    with demo_step("Step 5: Vendor closes the case (RmCloseCase)"):
        close = RmCloseCase(
            actor=vendor.as_id,
            as_object=case.as_id,
        )
        post_to_inbox_and_wait(client, vendor.as_id, close)
        with demo_check("RmCloseCase activity stored"):
            verify_object_stored(client, close.as_id)

    logger.info("✅ DEMO 2 COMPLETE: Case deferred, re-engaged, then closed.")


def demo_invalidate_path(
    client: DataLayerClient, finder: as_Actor, vendor: as_Actor
):
    """
    Demonstrates the invalidation path: submit → invalidate → close_report.

    When a report is invalid, a case is not created. Instead the vendor
    closes the report directly after invalidation.

    Workflow steps:
    1. Finder submits a report to the vendor
    2. Vendor invalidates the report (RmInvalidateReport — RM → INVALID)
    3. Vendor closes the report (RmCloseReport — RM → CLOSED)
    """
    logger.info("=" * 80)
    logger.info("DEMO 3: Invalidate Path (submit → invalidate → close_report)")
    logger.info("=" * 80)

    with demo_step("Step 1: Finder submits vulnerability report to vendor"):
        report = VulnerabilityReport(
            attributed_to=finder.as_id,
            content="The login page shows a different error for valid vs invalid "
            "usernames.",
            name="Alleged Username Enumeration",
        )
        logger.info(f"Created report: {logfmt(report)}")
        offer = RmSubmitReport(
            actor=finder.as_id,
            as_object=report,
            to=[vendor.as_id],
        )
        post_to_inbox_and_wait(client, vendor.as_id, offer)
        with demo_check("Report and offer stored"):
            verify_object_stored(client, report.as_id)
            verify_object_stored(client, offer.as_id)

    with demo_step(
        "Step 2: Vendor invalidates the report (RmInvalidateReport)"
    ):
        stored_offer = get_offer_from_datalayer(
            client, vendor.as_id, offer.as_id
        )
        invalidate = RmInvalidateReport(
            actor=vendor.as_id,
            object=stored_offer.as_id,
            content=(
                "Assessed as not a vulnerability — consistent error messages "
                "are expected behavior per the security policy."
            ),
        )
        post_to_inbox_and_wait(client, vendor.as_id, invalidate)
        with demo_check("RmInvalidateReport activity stored"):
            verify_object_stored(client, invalidate.as_id)

    with demo_step("Step 3: Vendor closes the report (RmCloseReport)"):
        close_report = RmCloseReport(
            actor=vendor.as_id,
            object=stored_offer.as_id,
            content="Report closed — assessed as not a valid vulnerability.",
        )
        post_to_inbox_and_wait(client, vendor.as_id, close_report)
        with demo_check("RmCloseReport activity stored"):
            verify_object_stored(client, close_report.as_id)

    logger.info(
        "✅ DEMO 3 COMPLETE: Report invalidated and closed (no case created)."
    )


_ALL_DEMOS: Sequence[Tuple[str, object]] = [
    ("Demo 1: Engage Path", demo_engage_path),
    ("Demo 2: Defer and Re-engage Path", demo_defer_reengage_path),
    ("Demo 3: Invalidate Path", demo_invalidate_path),
]


def main(
    skip_health_check: bool = False,
    demos: Optional[Sequence] = None,
):
    """
    Main entry point for the manage_case demo script.

    Args:
        skip_health_check: Skip the server availability check (useful for
            testing)
        demos: Optional sequence of demo functions to run. Defaults to all
            three.
    """
    client = DataLayerClient()

    if not skip_health_check and not check_server_availability(client):
        logger.error("=" * 80)
        logger.error("ERROR: API server is not available")
        logger.error("=" * 80)
        logger.error(f"Cannot connect to: {client.base_url}")
        logger.error("Please ensure the Vultron API server is running.")
        logger.error("You can start it with:")
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
            finder, vendor, coordinator = setup_clean_environment(client)
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
    logging.getLogger("requests").setLevel(logging.WARNING)
    _logger = logging.getLogger()
    hdlr = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    hdlr.setFormatter(formatter)
    _logger.addHandler(hdlr)
    _logger.setLevel(logging.DEBUG)


if __name__ == "__main__":
    _setup_logging()
    main()
