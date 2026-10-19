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
3. Invalidate Path: submit → invalidate → close the case (Leave)

The manage_case workflow corresponds to:
    docs/howto/activitypub/activities/manage_case.md

Key activities demonstrated:
- Report Submission (as:Offer) — finder submits a report to vendor through
  its own ``submit-report`` trigger
- RmValidateReportActivity (as:Accept) — vendor validates the report
- RmInvalidateReportActivity (as:TentativeReject) — vendor invalidates the report
- ``create-case`` trigger — vendor mints a as_VulnerabilityCase
- RmEngageCaseActivity (as:Join) — actor actively engages the case (RM → ACCEPTED)
- RmDeferCaseActivity (as:Ignore) — actor defers the case (RM → DEFERRED)
- RmCloseCaseActivity (as:Leave) — actor closes the case (RM → CLOSED)

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
   - demo_invalidate_path: submit → invalidate → close the case (Leave)
3. Verify side effects in the data layer for each workflow
"""

# Standard library imports
import logging
from collections.abc import Callable, Sequence

from vultron.demo.helpers.runner import run_exchange_demos
from vultron.demo.helpers.workflow import (
    reporter_submits_report,
    submit_validate_and_create_case,
    verify_reporter_trusts_introduction,
    wait_for_case_for_offer,
)
from vultron.demo.utils import (  # noqa: F401 — BASE_URL needed for test monkeypatching
    BASE_URL,
    DataLayerClient,
    demo_check,
    demo_step,
    get_offer_from_datalayer,
    log_case_state,
    logfmt,
    post_to_inbox_and_wait,
    ref_id,
    setup_demo_logging,
    verify_received_activity_stored,
)
from vultron.wire.as2.factories import (
    rm_close_case_activity,
    rm_defer_case_activity,
    rm_engage_case_activity,
    rm_invalidate_report_activity,
)

# Vultron imports
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
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
) -> tuple[as_VulnerabilityReport, as_VulnerabilityCase]:
    """
    Shared setup: submit and validate a report, create a case, and add the
    vendor as a participant with the report linked.

    Returns the created report and case objects.
    """
    # The trigger-minted case already lists the vendor as participant.
    return submit_validate_and_create_case(
        client,
        finder,
        vendor,
        report_name=report_name,
        report_content=report_content,
        validation_note="Confirmed — vulnerability verified.",
        case_name=case_name,
        case_content=case_content,
    )


def demo_engage_path(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor | None = None,
):
    """
    Demonstrates the full happy-path case management workflow:
    submit → validate → create_case → engage → close.

    Workflow steps:
    1. Finder submits report; vendor validates it
    2. Vendor creates as_VulnerabilityCase; adds vendor participant and report
    3. Vendor engages the case (RmEngageCaseActivity — RM → ACCEPTED)
    4. Vendor closes the case (RmCloseCaseActivity — RM → CLOSED)
    """
    logger.info("=" * 80)
    logger.info("DEMO 1: Engage Path (submit → validate → engage → close)")
    logger.info("=" * 80)

    case = None
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
            verify_received_activity_stored(client, engage.id_)

    with demo_step("Step 4: Vendor closes the case (RmCloseCaseActivity)"):
        close = rm_close_case_activity(case, actor=vendor.id_)
        post_to_inbox_and_wait(client, vendor.id_, close)
        with demo_check("RmCloseCaseActivity activity stored"):
            verify_received_activity_stored(client, close.id_)

    logger.info("✅ DEMO 1 COMPLETE: Case engaged then closed.")


def demo_defer_reengage_path(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor | None = None,
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

    case = None
    with demo_step(
        "Steps 1–2: Submit report, validate, create case with vendor "
        "participant"
    ):
        _report, case = setup_report_and_case(
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
            verify_received_activity_stored(client, defer.id_)
        logger.info("Case is now deferred (RM → DEFERRED).")

    with demo_step(
        "Step 4: Vendor re-engages the case (RmEngageCaseActivity from DEFERRED)"
    ):
        reengage = rm_engage_case_activity(case, actor=vendor.id_)
        post_to_inbox_and_wait(client, vendor.id_, reengage)
        with demo_check("RmEngageCaseActivity (re-engage) activity stored"):
            verify_received_activity_stored(client, reengage.id_)
        logger.info(
            "Case re-engaged via RmEngageCaseActivity (RM → ACCEPTED). "
            "Note: re-engagement uses the same RmEngageCaseActivity activity as initial "
            "engagement; there is no separate RmReEngageCase activity."
        )

    with demo_step("Step 5: Vendor closes the case (RmCloseCaseActivity)"):
        close = rm_close_case_activity(case, actor=vendor.id_)
        post_to_inbox_and_wait(client, vendor.id_, close)
        with demo_check("RmCloseCaseActivity activity stored"):
            verify_received_activity_stored(client, close.id_)

    logger.info("✅ DEMO 2 COMPLETE: Case deferred, re-engaged, then closed.")


def demo_invalidate_path(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor | None = None,
):
    """
    Demonstrates the invalidation path: submit → invalidate → close.

    The vendor opened a case for the report on receipt, so once the report is
    invalid the vendor, as Case Owner, closes that case with
    ``Leave(VulnerabilityCase)``: no actor sends ``Close(Report)`` for a
    report a case holds (CM-23-019).  The case is never engaged.

    Workflow steps:
    1. Finder submits a report to the vendor
    2. Vendor invalidates the report (RmInvalidateReportActivity — RM → INVALID)
    3. Vendor closes the case (RmCloseCaseActivity — as:Leave)
    """
    logger.info("=" * 80)
    logger.info("DEMO 3: Invalidate Path (submit → invalidate → close case)")
    logger.info("=" * 80)

    report = offer = None
    with demo_step("Step 1: Finder submits vulnerability report to vendor"):
        # Through the finder's own submit-report trigger (CBT-01-005, #4675).
        report, offer = reporter_submits_report(
            client,
            finder,
            vendor,
            reporter_client=client,
            report_name="Alleged Username Enumeration",
            report_content=(
                "The login page shows a different error for valid vs invalid "
                "usernames."
            ),
        )
        logger.info("Submitted report: %s", logfmt(report))

    stored_offer = None
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
            verify_received_activity_stored(client, invalidate.id_)

    with demo_step("Step 3: Vendor closes the case (RmCloseCaseActivity)"):
        case = wait_for_case_for_offer(client, stored_offer.id_)
        close = rm_close_case_activity(case, actor=vendor.id_)
        post_to_inbox_and_wait(client, vendor.id_, close)
        with demo_check("RmCloseCaseActivity activity stored"):
            verify_received_activity_stored(client, close.id_)

    # The case was created on receipt (auto_create_case), so the vendor still
    # introduces it to the finder (CBT-01-001); it is never engaged.
    verify_reporter_trusts_introduction(client, finder, vendor, report)

    logger.info(
        "✅ DEMO 3 COMPLETE: Report invalidated and closed (no case engaged)."
    )


_ALL_DEMOS: Sequence[tuple[str, Callable[..., None]]] = [
    ("Demo 1: Engage Path", demo_engage_path),
    ("Demo 2: Defer and Re-engage Path", demo_defer_reengage_path),
    ("Demo 3: Invalidate Path", demo_invalidate_path),
]


def main(
    skip_health_check: bool = False,
    demos: Sequence | None = None,
) -> None:
    """Main entry point for the manage case demo demo script."""
    run_exchange_demos(
        _ALL_DEMOS, skip_health_check=skip_health_check, demos=demos
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
