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

1. Acknowledge Only: submit → vendor sends ack (RmReadReportActivity) to finder
2. Acknowledge then Validate: submit → ack to finder → validate → notify finder
3. Acknowledge then Invalidate: submit → ack to finder → invalidate → notify finder

The finder submits through its ``submit-report`` trigger, so it holds the
Offer and admits the ack only from the Offer's addressee, the vendor
(RMB-08-004).  The vendor sends the ack through its ``ack-report`` trigger,
which addresses the finder alone, never the CASE_MANAGER, case or no case
(RMB-08-003).

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
   - demo_acknowledge_only: Submit → RmReadReportActivity to finder
   - demo_acknowledge_then_validate: Submit → RmReadReportActivity → Validate → notify finder
   - demo_acknowledge_then_invalidate: Submit → RmReadReportActivity → Invalidate → notify finder
5. Verify side effects in the data layer and finder's inbox for each workflow
"""

# Standard library imports
import logging
from collections.abc import Callable, Sequence

from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers.polling import wait_for_object_stored
from vultron.demo.helpers.runner import run_exchange_demos
from vultron.demo.helpers.verification import (
    verify_activity_in_inbox,
)
from vultron.demo.helpers.workflow import reporter_submits_report
from vultron.demo.utils import (  # noqa: F401 — BASE_URL needed for test monkeypatching
    BASE_URL,
    DataLayerClient,
    demo_check,
    demo_step,
    post_to_inbox_and_wait,
    setup_demo_logging,
    verify_object_stored,
)
from vultron.wire.as2.factories import (
    rm_invalidate_report_activity,
    rm_validate_report_activity,
)

# Vultron imports
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Offer
from vultron.wire.as2.vocab.base.objects.actors import as_Actor

logger = logging.getLogger(__name__)


def _finder_submits_report(
    client: DataLayerClient, finder: as_Actor, vendor: as_Actor
) -> as_Offer:
    """Step 1 of every demo: the finder submits a report to the vendor.

    The finder's ``submit-report`` trigger records the Offer in the finder's
    own store, which is what lets the finder check who may acknowledge it
    (RMB-08-004), and its outbox delivers the Offer to the vendor.
    """
    _report, offer = reporter_submits_report(
        client, finder, vendor, reporter_client=client
    )
    return offer


def _vendor_acknowledges_to_finder(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    offer: as_Offer,
    content: str,
) -> None:
    """The vendor, the Offer's addressee, sends RK to the finder.

    The vendor's ``ack-report`` trigger emits the ``Read(Offer)`` to the
    reporter alone, never to the CASE_MANAGER (RMB-08-003), whether or not a
    case exists yet, and its outbox delivers it.  The finder admits it
    because the vendor is an addressee of the Offer the finder recorded
    (RMB-08-004).

    The check below confirms delivery only: intake stores a refused RK too,
    and the inbox exposes no outcome to read (IE-02-003), so the admit and
    refuse arms are covered by ``test_ack_report_routing.py`` instead.
    """
    result = ActorSession(client=client, actor=vendor).ack_report(
        offer_id=offer.id_, note=content
    )
    ack_id = (result.activity or {}).get("id")
    with demo_check("RmReadReportActivity delivered to finder"):
        if not isinstance(ack_id, str):
            raise TypeError("ack-report returned no activity id.")
        wait_for_object_stored(client, ack_id, actor_id=finder.id_)


def demo_acknowledge_only(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor | None = None,
):
    """
    Demonstrates a bare acknowledgement: the vendor reads the report without
    committing to validate or invalidate it.

    Workflow:
      1. Finder submits report to vendor
      2. Vendor, the Offer's addressee, sends RmReadReportActivity (as:Read)
         to the finder, and the demo verifies it reached the finder's inbox
    """
    logger.info("=" * 80)
    logger.info("DEMO 1: Acknowledge Only (RmReadReportActivity)")
    logger.info("=" * 80)

    offer = None
    with demo_step("Step 1: Finder submits vulnerability report to vendor"):
        offer = _finder_submits_report(client, finder, vendor)

    with demo_step("Step 2: Vendor acknowledges the report to the finder"):
        _vendor_acknowledges_to_finder(
            client,
            finder,
            vendor,
            offer,
            "We have received your report and will review it shortly.",
        )

    logger.info("✅ DEMO 1 COMPLETE: Report acknowledged (read-only).")


def demo_acknowledge_then_validate(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor | None = None,
):
    """
    Demonstrates acknowledge followed by validation.

    Workflow:
      1. Finder submits report to vendor
      2. Vendor sends RmReadReportActivity (as:Read) to the finder
      3. Vendor then sends RmValidateReportActivity (as:Accept)
      4. Verify both activities stored; verify validate notification to finder
    """
    logger.info("=" * 80)
    logger.info("DEMO 2: Acknowledge then Validate")
    logger.info("=" * 80)

    offer = None
    with demo_step("Step 1: Finder submits vulnerability report to vendor"):
        offer = _finder_submits_report(client, finder, vendor)

    with demo_step("Step 2: Vendor acknowledges the report to the finder"):
        _vendor_acknowledges_to_finder(
            client, finder, vendor, offer, "Report received — under review."
        )

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
    coordinator: as_Actor | None = None,
):
    """
    Demonstrates acknowledge followed by invalidation.

    Workflow:
      1. Finder submits report to vendor
      2. Vendor sends RmReadReportActivity (as:Read) to the finder
      3. Vendor sends RmInvalidateReportActivity (as:TentativeReject)
      4. Vendor notifies finder of the invalidation
      5. Verify activities stored and invalidation in finder's inbox
    """
    logger.info("=" * 80)
    logger.info("DEMO 3: Acknowledge then Invalidate")
    logger.info("=" * 80)

    offer = None
    with demo_step("Step 1: Finder submits vulnerability report to vendor"):
        offer = _finder_submits_report(client, finder, vendor)

    with demo_step("Step 2: Vendor acknowledges the report to the finder"):
        _vendor_acknowledges_to_finder(
            client, finder, vendor, offer, "Report received — under review."
        )

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


_ALL_DEMOS: Sequence[tuple[str, Callable[..., None]]] = [
    ("Demo 1: Acknowledge Only", demo_acknowledge_only),
    ("Demo 2: Acknowledge then Validate", demo_acknowledge_then_validate),
    ("Demo 3: Acknowledge then Invalidate", demo_acknowledge_then_invalidate),
]


def main(
    skip_health_check: bool = False,
    demos: Sequence | None = None,
):
    """Main entry point for the acknowledge demo script."""
    run_exchange_demos(
        _ALL_DEMOS, skip_health_check=skip_health_check, demos=demos
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
