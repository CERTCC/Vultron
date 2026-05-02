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
- RmSubmitReportActivity (as:Offer) — finder submits a report to vendor
- RmValidateReportActivity (as:Accept) — vendor validates the report
- RmInvalidateReportActivity (as:TentativeReject) — vendor invalidates the report
- CreateCaseActivity (as:Create) — vendor creates a VulnerabilityCase
- RmEngageCaseActivity (as:Join) — actor actively engages the case (RM → ACCEPTED)
- RmDeferCaseActivity (as:Ignore) — actor defers the case (RM → DEFERRED)
- RmCloseCaseActivity (as:Leave) — actor closes the case (RM → CLOSED)
- RmCloseReportActivity (as:Reject) — vendor closes an invalid report

Note on re-engagement:
Per implementation notes, re-engaging a deferred case is done by sending
another RmEngageCaseActivity (as:Join) activity. There is no separate RmReEngageCase
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
from typing import Callable, Optional, Sequence, Tuple

# Vultron imports
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.case_participant import VendorParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)
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
from vultron.wire.as2.factories import (
    add_participant_to_case_activity,
    add_report_to_case_activity,
    create_case_activity,
    rm_close_case_activity,
    rm_close_report_activity,
    rm_defer_case_activity,
    rm_engage_case_activity,
    rm_invalidate_report_activity,
    rm_submit_report_activity,
    rm_validate_report_activity,
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
        attributed_to=finder.id_,
        content=report_content,
        name=report_name,
    )
    report_offer = rm_submit_report_activity(
        report, actor=finder.id_, to=vendor.id_
    )
    post_to_inbox_and_wait(client, vendor.id_, report_offer)

    offer = get_offer_from_datalayer(client, vendor.id_, report_offer.id_)
    validate_activity = rm_validate_report_activity(
        offer, actor=vendor.id_, content="Confirmed — vulnerability verified."
    )
    post_to_inbox_and_wait(client, vendor.id_, validate_activity)

    case = VulnerabilityCase(
        attributed_to=vendor.id_,
        name=case_name,
        content=case_content,
    )
    create_case_act = create_case_activity(case, actor=vendor.id_)
    post_to_inbox_and_wait(client, vendor.id_, create_case_act)

    vendor_participant = VendorParticipant(
        attributed_to=vendor.id_,
        context=case.id_,
    )
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Create,
    )

    create_vendor_participant = as_Create(
        actor=vendor.id_,
        object_=vendor_participant,
        context=case.id_,
    )
    post_to_inbox_and_wait(client, vendor.id_, create_vendor_participant)

    add_vendor_participant = add_participant_to_case_activity(
        vendor_participant, actor=vendor.id_, target=case.id_
    )
    post_to_inbox_and_wait(client, vendor.id_, add_vendor_participant)

    add_report = add_report_to_case_activity(
        report, actor=vendor.id_, target=case.id_
    )
    post_to_inbox_and_wait(client, vendor.id_, add_report)

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
    3. Vendor engages the case (RmEngageCaseActivity — RM → ACCEPTED)
    4. Vendor closes the case (RmCloseCaseActivity — RM → CLOSED)
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
            updated_case = log_case_state(client, case.id_, "after setup")
            if updated_case and report.id_ not in [
                (ref_id(r) or str(r))
                for r in updated_case.vulnerability_reports
            ]:
                raise ValueError(
                    f"Report '{report.id_}' not linked to case after setup"
                )

    with demo_step("Step 3: Vendor engages the case (RmEngageCaseActivity)"):
        engage = rm_engage_case_activity(case, actor=vendor.id_)
        post_to_inbox_and_wait(client, vendor.id_, engage)
        with demo_check("RmEngageCaseActivity activity stored"):
            verify_object_stored(client, engage.id_)

    with demo_step("Step 4: Vendor closes the case (RmCloseCaseActivity)"):
        close = rm_close_case_activity(case, actor=vendor.id_)
        post_to_inbox_and_wait(client, vendor.id_, close)
        with demo_check("RmCloseCaseActivity activity stored"):
            verify_object_stored(client, close.id_)

    logger.info("✅ DEMO 1 COMPLETE: Case engaged then closed.")


def demo_defer_reengage_path(
    client: DataLayerClient, finder: as_Actor, vendor: as_Actor
):
    """
    Demonstrates the defer-and-re-engage path:
    submit → validate → create_case → defer → re-engage → close.

    Per implementation notes, re-engaging a deferred case uses another
    RmEngageCaseActivity (as:Join) — there is no separate RmReEngageCase activity.
    The RM state machine allows a direct DEFERRED → ACCEPTED transition.

    Workflow steps:
    1. Finder submits report; vendor validates it
    2. Vendor creates case with vendor participant and linked report
    3. Vendor defers the case (RmDeferCaseActivity — RM → DEFERRED)
    4. Vendor re-engages via RmEngageCaseActivity (RM → ACCEPTED)
    5. Vendor closes the case (RmCloseCaseActivity — RM → CLOSED)
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
            log_case_state(client, case.id_, "after setup")

    with demo_step("Step 3: Vendor defers the case (RmDeferCaseActivity)"):
        defer = rm_defer_case_activity(case, actor=vendor.id_)
        post_to_inbox_and_wait(client, vendor.id_, defer)
        with demo_check("RmDeferCaseActivity activity stored"):
            verify_object_stored(client, defer.id_)
        logger.info("Case is now deferred (RM → DEFERRED).")

    with demo_step(
        "Step 4: Vendor re-engages the case (RmEngageCaseActivity from DEFERRED)"
    ):
        reengage = rm_engage_case_activity(case, actor=vendor.id_)
        post_to_inbox_and_wait(client, vendor.id_, reengage)
        with demo_check("RmEngageCaseActivity (re-engage) activity stored"):
            verify_object_stored(client, reengage.id_)
        logger.info(
            "Case re-engaged via RmEngageCaseActivity (RM → ACCEPTED). "
            "Note: re-engagement uses the same RmEngageCaseActivity activity as initial "
            "engagement; there is no separate RmReEngageCase activity."
        )

    with demo_step("Step 5: Vendor closes the case (RmCloseCaseActivity)"):
        close = rm_close_case_activity(case, actor=vendor.id_)
        post_to_inbox_and_wait(client, vendor.id_, close)
        with demo_check("RmCloseCaseActivity activity stored"):
            verify_object_stored(client, close.id_)

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
    2. Vendor invalidates the report (RmInvalidateReportActivity — RM → INVALID)
    3. Vendor closes the report (RmCloseReportActivity — RM → CLOSED)
    """
    logger.info("=" * 80)
    logger.info("DEMO 3: Invalidate Path (submit → invalidate → close_report)")
    logger.info("=" * 80)

    with demo_step("Step 1: Finder submits vulnerability report to vendor"):
        report = VulnerabilityReport(
            attributed_to=finder.id_,
            content="The login page shows a different error for valid vs invalid "
            "usernames.",
            name="Alleged Username Enumeration",
        )
        logger.info(f"Created report: {logfmt(report)}")
        offer = rm_submit_report_activity(
            report, actor=finder.id_, to=vendor.id_
        )
        post_to_inbox_and_wait(client, vendor.id_, offer)
        with demo_check("Report and offer stored"):
            verify_object_stored(client, report.id_)
            verify_object_stored(client, offer.id_)

    with demo_step(
        "Step 2: Vendor invalidates the report (RmInvalidateReportActivity)"
    ):
        stored_offer = get_offer_from_datalayer(client, vendor.id_, offer.id_)
        invalidate = rm_invalidate_report_activity(
            stored_offer,
            actor=vendor.id_,
            content=(
                "Assessed as not a vulnerability — consistent error messages "
                "are expected behavior per the security policy."
            ),
        )
        post_to_inbox_and_wait(client, vendor.id_, invalidate)
        with demo_check("RmInvalidateReportActivity activity stored"):
            verify_object_stored(client, invalidate.id_)

    with demo_step("Step 3: Vendor closes the report (RmCloseReportActivity)"):
        close_report = rm_close_report_activity(
            stored_offer,
            actor=vendor.id_,
            content="Report closed — assessed as not a valid vulnerability.",
        )
        post_to_inbox_and_wait(client, vendor.id_, close_report)
        with demo_check("RmCloseReportActivity activity stored"):
            verify_object_stored(client, close_report.id_)

    logger.info(
        "✅ DEMO 3 COMPLETE: Report invalidated and closed (no case created)."
    )


_ALL_DEMOS: Sequence[Tuple[str, Callable[..., None]]] = [
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
    _logger = logging.getLogger()
    hdlr = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    hdlr.setFormatter(formatter)
    _logger.addHandler(hdlr)
    _logger.setLevel(logging.DEBUG)


if __name__ == "__main__":
    _setup_logging()
    main()
