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
Demonstrates the acknowledgement workflow for vulnerability reports via the Vultron API.

This demo script showcases the RmReadReportActivity (as:Read) acknowledgement mechanism:

1. Acknowledge Only: submit → ack (RmReadReportActivity) → notify finder
2. Acknowledge then Validate: submit → ack → validate → notify finder
3. Acknowledge then Invalidate: submit → ack → invalidate → notify finder

The acknowledge workflow corresponds to:
    docs/howto/activitypub/activities/acknowledge.md

As described in that document, RmReadReportActivity acknowledges receipt without
committing to an outcome. The receiver can subsequently validate or invalidate
the report. Sending RmValidateReportActivity or RmInvalidateReportActivity already implies that
the report was read, so a separate RmReadReportActivity is optional but demonstrates
good protocol hygiene.

When run as a script, this module will:
1. Check if the API server is available
2. Reset the data layer to a clean state
3. Discover actors (finder, vendor, coordinator) via the API
4. Run three separate demo workflows, each with a unique report:
   - demo_acknowledge_only: Submit → RmReadReportActivity → notify finder
   - demo_acknowledge_then_validate: Submit → RmReadReportActivity → Validate → notify finder
   - demo_acknowledge_then_invalidate: Submit → RmReadReportActivity → Invalidate → notify finder
5. Verify side effects in the data layer and finder's inbox for each workflow
"""

# Standard library imports
import logging
from typing import Callable, Optional, Sequence, Tuple

# Vultron imports
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)
from vultron.demo.helpers.runner import run_exchange_demos
from vultron.demo.helpers.verification import (
    verify_activity_in_inbox,
)  # noqa: F401
from vultron.demo.utils import (  # noqa: F401 — BASE_URL needed for test monkeypatching
    BASE_URL,
    DataLayerClient,
    demo_check,
    demo_step,
    logfmt,
    post_to_inbox_and_wait,
    verify_object_stored,
    setup_demo_logging,
)
from vultron.wire.as2.factories import (
    rm_invalidate_report_activity,
    rm_read_report_activity,
    rm_submit_report_activity,
    rm_validate_report_activity,
)

logger = logging.getLogger(__name__)


def demo_acknowledge_only(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    coordinator: Optional[as_Actor] = None,
):
    """
    Demonstrates a bare acknowledgement: the vendor reads the report without
    committing to validate or invalidate it.

    Workflow:
      1. Finder submits report to vendor
      2. Vendor sends RmReadReportActivity (as:Read) back to their own inbox
      3. Vendor notifies finder with an RmReadReportActivity
      4. Verify ack stored and delivered to finder
    """
    logger.info("=" * 80)
    logger.info("DEMO 1: Acknowledge Only (RmReadReportActivity)")
    logger.info("=" * 80)

    with demo_step("Step 1: Finder submits vulnerability report to vendor"):
        report = as_VulnerabilityReport(
            attributed_to=finder.id_,
            content="Possible integer overflow in the network parsing library.",
            name="Network Parser Integer Overflow",
        )
        logger.info(f"Created report: {logfmt(report)}")
        offer = rm_submit_report_activity(
            report, actor=finder.id_, to=vendor.id_
        )
        post_to_inbox_and_wait(client, vendor.id_, offer)
        with demo_check("Report offer and report stored"):
            verify_object_stored(client=client, obj_id=offer.id_)
            verify_object_stored(client=client, obj_id=report.id_)

    with demo_step(
        "Step 2: Vendor acknowledges report (RmReadReportActivity to own inbox)"
    ):
        ack = rm_read_report_activity(
            report,
            actor=vendor.id_,
            content="We have received your report and will review it shortly.",
        )
        post_to_inbox_and_wait(client, vendor.id_, ack)
        with demo_check("RmReadReportActivity activity stored"):
            verify_object_stored(client=client, obj_id=ack.id_)

    with demo_step("Step 3: Vendor notifies finder of acknowledgement"):
        ack_to_finder = rm_read_report_activity(
            report,
            actor=vendor.id_,
            to=[finder.id_],
            content="We have received your report and will review it shortly.",
        )
        post_to_inbox_and_wait(client, finder.id_, ack_to_finder)
        with demo_check("RmReadReportActivity notification in finder's inbox"):
            if not verify_activity_in_inbox(
                client, finder.id_, ack_to_finder.id_
            ):
                raise ValueError(
                    "RmReadReportActivity notification not found in finder's inbox."
                )

    logger.info("✅ DEMO 1 COMPLETE: Report acknowledged (read-only).")


def demo_acknowledge_then_validate(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    coordinator: Optional[as_Actor] = None,
):
    """
    Demonstrates acknowledge followed by validation.

    Workflow:
      1. Finder submits report to vendor
      2. Vendor sends RmReadReportActivity (as:Read)
      3. Vendor then sends RmValidateReportActivity (as:Accept)
      4. Verify both activities stored; verify validate notification to finder
    """
    logger.info("=" * 80)
    logger.info("DEMO 2: Acknowledge then Validate")
    logger.info("=" * 80)

    with demo_step("Step 1: Finder submits vulnerability report to vendor"):
        report = as_VulnerabilityReport(
            attributed_to=finder.id_,
            content=(
                "SQL injection in the admin login form — confirmed via manual testing."
            ),
            name="Admin Login SQL Injection",
        )
        logger.info(f"Created report: {logfmt(report)}")
        offer = rm_submit_report_activity(
            report, actor=finder.id_, to=vendor.id_
        )
        post_to_inbox_and_wait(client, vendor.id_, offer)
        with demo_check("Report offer and report stored"):
            verify_object_stored(client=client, obj_id=offer.id_)
            verify_object_stored(client=client, obj_id=report.id_)

    with demo_step(
        "Step 2: Vendor acknowledges report (RmReadReportActivity)"
    ):
        ack = rm_read_report_activity(
            report, actor=vendor.id_, content="Report received — under review."
        )
        post_to_inbox_and_wait(client, vendor.id_, ack)
        with demo_check("RmReadReportActivity activity stored"):
            verify_object_stored(client=client, obj_id=ack.id_)

    with demo_step(
        "Step 3: Vendor validates report (RmValidateReportActivity)"
    ):
        validate = rm_validate_report_activity(
            offer,
            actor=vendor.id_,
            content="Confirmed SQL injection. Creating a case.",
        )
        post_to_inbox_and_wait(client, vendor.id_, validate)
        with demo_check("RmValidateReportActivity activity stored"):
            verify_object_stored(client=client, obj_id=validate.id_)

    with demo_step("Step 4: Vendor notifies finder of validation"):
        validate_to_finder = rm_validate_report_activity(
            offer,
            actor=vendor.id_,
            to=[finder.id_],
            content="Your report has been validated. A case has been created.",
        )
        post_to_inbox_and_wait(client, finder.id_, validate_to_finder)
        with demo_check(
            "RmValidateReportActivity notification in finder's inbox"
        ):
            if not verify_activity_in_inbox(
                client, finder.id_, validate_to_finder.id_
            ):
                raise ValueError(
                    "RmValidateReportActivity notification not found in finder's inbox."
                )

    logger.info(
        "✅ DEMO 2 COMPLETE: Report acknowledged then validated; finder notified."
    )


def demo_acknowledge_then_invalidate(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    coordinator: Optional[as_Actor] = None,
):
    """
    Demonstrates acknowledge followed by invalidation.

    Workflow:
      1. Finder submits report to vendor
      2. Vendor sends RmReadReportActivity (as:Read)
      3. Vendor sends RmInvalidateReportActivity (as:TentativeReject)
      4. Vendor notifies finder of the invalidation
      5. Verify activities stored and invalidation in finder's inbox
    """
    logger.info("=" * 80)
    logger.info("DEMO 3: Acknowledge then Invalidate")
    logger.info("=" * 80)

    with demo_step("Step 1: Finder submits vulnerability report to vendor"):
        report = as_VulnerabilityReport(
            attributed_to=finder.id_,
            content=(
                "Crash when submitting empty form — no security impact confirmed."
            ),
            name="Empty Form Submission Crash",
        )
        logger.info(f"Created report: {logfmt(report)}")
        offer = rm_submit_report_activity(
            report, actor=finder.id_, to=vendor.id_
        )
        post_to_inbox_and_wait(client, vendor.id_, offer)
        with demo_check("Report offer and report stored"):
            verify_object_stored(client=client, obj_id=offer.id_)
            verify_object_stored(client=client, obj_id=report.id_)

    with demo_step(
        "Step 2: Vendor acknowledges report (RmReadReportActivity)"
    ):
        ack = rm_read_report_activity(
            report, actor=vendor.id_, content="Report received — under review."
        )
        post_to_inbox_and_wait(client, vendor.id_, ack)
        with demo_check("RmReadReportActivity activity stored"):
            verify_object_stored(client=client, obj_id=ack.id_)

    with demo_step(
        "Step 3: Vendor invalidates report (RmInvalidateReportActivity)"
    ):
        invalidate = rm_invalidate_report_activity(
            offer,
            actor=vendor.id_,
            content=(
                "This is a UX defect, not a security vulnerability. "
                "Holding for further review."
            ),
        )
        post_to_inbox_and_wait(client, vendor.id_, invalidate)
        with demo_check("RmInvalidateReportActivity activity stored"):
            verify_object_stored(client=client, obj_id=invalidate.id_)

    with demo_step("Step 4: Vendor notifies finder of invalidation"):
        invalidate_to_finder = rm_invalidate_report_activity(
            offer,
            actor=vendor.id_,
            to=[finder.id_],
            content=(
                "After review, this does not appear to be a security vulnerability."
            ),
        )
        post_to_inbox_and_wait(client, finder.id_, invalidate_to_finder)
        with demo_check(
            "RmInvalidateReportActivity notification in finder's inbox"
        ):
            if not verify_activity_in_inbox(
                client, finder.id_, invalidate_to_finder.id_
            ):
                raise ValueError(
                    "RmInvalidateReportActivity notification not found in finder's inbox."
                )

    logger.info(
        "✅ DEMO 3 COMPLETE: Report acknowledged then invalidated; finder notified."
    )


_ALL_DEMOS: Sequence[Tuple[str, Callable[..., None]]] = [
    ("Demo 1: Acknowledge Only", demo_acknowledge_only),
    ("Demo 2: Acknowledge then Validate", demo_acknowledge_then_validate),
    ("Demo 3: Acknowledge then Invalidate", demo_acknowledge_then_invalidate),
]


def main(
    skip_health_check: bool = False,
    demos: Optional[Sequence] = None,
):
    """Main entry point for the acknowledge demo script."""
    run_exchange_demos(
        _ALL_DEMOS, skip_health_check=skip_health_check, demos=demos
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
