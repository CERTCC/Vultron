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

This demo script showcases the RmReadReport (as:Read) acknowledgement mechanism:

1. Acknowledge Only: submit → ack (RmReadReport) → notify finder
2. Acknowledge then Validate: submit → ack → validate → notify finder
3. Acknowledge then Invalidate: submit → ack → invalidate → notify finder

The acknowledge workflow corresponds to:
    docs/howto/activitypub/activities/acknowledge.md

As described in that document, RmReadReport acknowledges receipt without
committing to an outcome. The receiver can subsequently validate or invalidate
the report. Sending RmValidateReport or RmInvalidateReport already implies that
the report was read, so a separate RmReadReport is optional but demonstrates
good protocol hygiene.

When run as a script, this module will:
1. Check if the API server is available
2. Reset the data layer to a clean state
3. Discover actors (finder, vendor, coordinator) via the API
4. Run three separate demo workflows, each with a unique report:
   - demo_acknowledge_only: Submit → RmReadReport → notify finder
   - demo_acknowledge_then_validate: Submit → RmReadReport → Validate → notify finder
   - demo_acknowledge_then_invalidate: Submit → RmReadReport → Invalidate → notify finder
5. Verify side effects in the data layer and finder's inbox for each workflow
"""

# Standard library imports
import logging
import sys
from typing import Optional, Sequence, Tuple

# Vultron imports
from vultron.api.v2.data.utils import parse_id
from vultron.as_vocab.activities.report import (
    RmInvalidateReport,
    RmReadReport,
    RmSubmitReport,
    RmValidateReport,
)
from vultron.as_vocab.base.objects.actors import as_Actor
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport
from vultron.demo.utils import (
    BASE_URL,
    DataLayerClient,
    check_server_availability,
    demo_check,
    demo_step,
    demo_environment,
    get_offer_from_datalayer,
    logfmt,
    post_to_inbox_and_wait,
    verify_object_stored,
)

logger = logging.getLogger(__name__)


def get_actor_by_id(
    client: DataLayerClient, actor_id: str
) -> Optional[as_Actor]:
    """Retrieve an actor by ID from the DataLayer, or ``None`` if not found."""
    actors_data = client.get("/actors/")
    for actor_data in actors_data:
        actor = as_Actor(**actor_data)
        if actor.as_id == actor_id:
            return actor
    return None


def get_item_id(item):
    """Extract the ``as_id`` string from an activity item or return the item as-is."""
    if item is None:
        return None
    if isinstance(item, str):
        return item
    return getattr(item, "as_id", None)


def verify_activity_in_inbox(
    client: DataLayerClient, actor_id: str, activity_id: str
) -> bool:
    """Check whether ``activity_id`` appears in the actor's inbox.

    Returns:
        ``True`` if found; ``False`` otherwise.

    Raises:
        ValueError: If the actor cannot be found or has no inbox.
    """
    actor = get_actor_by_id(client, actor_id)
    if not actor or not actor.inbox:
        raise ValueError(f"Actor {actor_id} not found or has no inbox")
    logger.info(
        f"Actor {parse_id(actor_id)['object_id']} inbox has "
        f"{len(actor.inbox.items)} items"
    )
    for item in actor.inbox.items:
        item_id = get_item_id(item)
        if item_id == activity_id:
            logger.info(f"✓ Found activity in inbox: {logfmt(item)}")
            return True
    logger.warning(f"Activity {activity_id} not found in inbox")
    return False


def demo_acknowledge_only(
    client: DataLayerClient, finder: as_Actor, vendor: as_Actor
):
    """
    Demonstrates a bare acknowledgement: the vendor reads the report without
    committing to validate or invalidate it.

    Workflow:
      1. Finder submits report to vendor
      2. Vendor sends RmReadReport (as:Read) back to their own inbox
      3. Vendor notifies finder with an RmReadReport
      4. Verify ack stored and delivered to finder
    """
    logger.info("=" * 80)
    logger.info("DEMO 1: Acknowledge Only (RmReadReport)")
    logger.info("=" * 80)

    with demo_step("Step 1: Finder submits vulnerability report to vendor"):
        report = VulnerabilityReport(
            attributed_to=finder.as_id,
            content="Possible integer overflow in the network parsing library.",
            name="Network Parser Integer Overflow",
        )
        logger.info(f"Created report: {logfmt(report)}")
        offer = RmSubmitReport(
            actor=finder.as_id,
            as_object=report,
            to=[vendor.as_id],
        )
        post_to_inbox_and_wait(client, vendor.as_id, offer)
        with demo_check("Report offer and report stored"):
            verify_object_stored(client=client, obj_id=offer.as_id)
            verify_object_stored(client=client, obj_id=report.as_id)

    with demo_step(
        "Step 2: Vendor acknowledges report (RmReadReport to own inbox)"
    ):
        stored_offer = get_offer_from_datalayer(
            client, vendor.as_id, offer.as_id
        )
        ack = RmReadReport(
            actor=vendor.as_id,
            as_object=stored_offer.as_id,
            content="We have received your report and will review it shortly.",
        )
        post_to_inbox_and_wait(client, vendor.as_id, ack)
        with demo_check("RmReadReport activity stored"):
            verify_object_stored(client=client, obj_id=ack.as_id)

    with demo_step("Step 3: Vendor notifies finder of acknowledgement"):
        ack_to_finder = RmReadReport(
            actor=vendor.as_id,
            as_object=stored_offer.as_id,
            to=[finder.as_id],
            content="We have received your report and will review it shortly.",
        )
        post_to_inbox_and_wait(client, finder.as_id, ack_to_finder)
        with demo_check("RmReadReport notification in finder's inbox"):
            if not verify_activity_in_inbox(
                client, finder.as_id, ack_to_finder.as_id
            ):
                raise ValueError(
                    "RmReadReport notification not found in finder's inbox."
                )

    logger.info("✅ DEMO 1 COMPLETE: Report acknowledged (read-only).")


def demo_acknowledge_then_validate(
    client: DataLayerClient, finder: as_Actor, vendor: as_Actor
):
    """
    Demonstrates acknowledge followed by validation.

    Workflow:
      1. Finder submits report to vendor
      2. Vendor sends RmReadReport (as:Read)
      3. Vendor then sends RmValidateReport (as:Accept)
      4. Verify both activities stored; verify validate notification to finder
    """
    logger.info("=" * 80)
    logger.info("DEMO 2: Acknowledge then Validate")
    logger.info("=" * 80)

    with demo_step("Step 1: Finder submits vulnerability report to vendor"):
        report = VulnerabilityReport(
            attributed_to=finder.as_id,
            content=(
                "SQL injection in the admin login form — confirmed via manual testing."
            ),
            name="Admin Login SQL Injection",
        )
        logger.info(f"Created report: {logfmt(report)}")
        offer = RmSubmitReport(
            actor=finder.as_id,
            as_object=report,
            to=[vendor.as_id],
        )
        post_to_inbox_and_wait(client, vendor.as_id, offer)
        with demo_check("Report offer and report stored"):
            verify_object_stored(client=client, obj_id=offer.as_id)
            verify_object_stored(client=client, obj_id=report.as_id)

    with demo_step("Step 2: Vendor acknowledges report (RmReadReport)"):
        stored_offer = get_offer_from_datalayer(
            client, vendor.as_id, offer.as_id
        )
        ack = RmReadReport(
            actor=vendor.as_id,
            as_object=stored_offer.as_id,
            content="Report received — under review.",
        )
        post_to_inbox_and_wait(client, vendor.as_id, ack)
        with demo_check("RmReadReport activity stored"):
            verify_object_stored(client=client, obj_id=ack.as_id)

    with demo_step("Step 3: Vendor validates report (RmValidateReport)"):
        validate = RmValidateReport(
            actor=vendor.as_id,
            object=stored_offer.as_id,
            content="Confirmed SQL injection. Creating a case.",
        )
        post_to_inbox_and_wait(client, vendor.as_id, validate)
        with demo_check("RmValidateReport activity stored"):
            verify_object_stored(client=client, obj_id=validate.as_id)

    with demo_step("Step 4: Vendor notifies finder of validation"):
        validate_to_finder = RmValidateReport(
            actor=vendor.as_id,
            object=stored_offer.as_id,
            to=[finder.as_id],
            content="Your report has been validated. A case has been created.",
        )
        post_to_inbox_and_wait(client, finder.as_id, validate_to_finder)
        with demo_check("RmValidateReport notification in finder's inbox"):
            if not verify_activity_in_inbox(
                client, finder.as_id, validate_to_finder.as_id
            ):
                raise ValueError(
                    "RmValidateReport notification not found in finder's inbox."
                )

    logger.info(
        "✅ DEMO 2 COMPLETE: Report acknowledged then validated; finder notified."
    )


def demo_acknowledge_then_invalidate(
    client: DataLayerClient, finder: as_Actor, vendor: as_Actor
):
    """
    Demonstrates acknowledge followed by invalidation.

    Workflow:
      1. Finder submits report to vendor
      2. Vendor sends RmReadReport (as:Read)
      3. Vendor sends RmInvalidateReport (as:TentativeReject)
      4. Vendor notifies finder of the invalidation
      5. Verify activities stored and invalidation in finder's inbox
    """
    logger.info("=" * 80)
    logger.info("DEMO 3: Acknowledge then Invalidate")
    logger.info("=" * 80)

    with demo_step("Step 1: Finder submits vulnerability report to vendor"):
        report = VulnerabilityReport(
            attributed_to=finder.as_id,
            content=(
                "Crash when submitting empty form — no security impact confirmed."
            ),
            name="Empty Form Submission Crash",
        )
        logger.info(f"Created report: {logfmt(report)}")
        offer = RmSubmitReport(
            actor=finder.as_id,
            as_object=report,
            to=[vendor.as_id],
        )
        post_to_inbox_and_wait(client, vendor.as_id, offer)
        with demo_check("Report offer and report stored"):
            verify_object_stored(client=client, obj_id=offer.as_id)
            verify_object_stored(client=client, obj_id=report.as_id)

    with demo_step("Step 2: Vendor acknowledges report (RmReadReport)"):
        stored_offer = get_offer_from_datalayer(
            client, vendor.as_id, offer.as_id
        )
        ack = RmReadReport(
            actor=vendor.as_id,
            as_object=stored_offer.as_id,
            content="Report received — under review.",
        )
        post_to_inbox_and_wait(client, vendor.as_id, ack)
        with demo_check("RmReadReport activity stored"):
            verify_object_stored(client=client, obj_id=ack.as_id)

    with demo_step("Step 3: Vendor invalidates report (RmInvalidateReport)"):
        invalidate = RmInvalidateReport(
            actor=vendor.as_id,
            object=stored_offer.as_id,
            content=(
                "This is a UX defect, not a security vulnerability. "
                "Holding for further review."
            ),
        )
        post_to_inbox_and_wait(client, vendor.as_id, invalidate)
        with demo_check("RmInvalidateReport activity stored"):
            verify_object_stored(client=client, obj_id=invalidate.as_id)

    with demo_step("Step 4: Vendor notifies finder of invalidation"):
        invalidate_to_finder = RmInvalidateReport(
            actor=vendor.as_id,
            object=stored_offer.as_id,
            to=[finder.as_id],
            content=(
                "After review, this does not appear to be a security vulnerability."
            ),
        )
        post_to_inbox_and_wait(client, finder.as_id, invalidate_to_finder)
        with demo_check("RmInvalidateReport notification in finder's inbox"):
            if not verify_activity_in_inbox(
                client, finder.as_id, invalidate_to_finder.as_id
            ):
                raise ValueError(
                    "RmInvalidateReport notification not found in finder's inbox."
                )

    logger.info(
        "✅ DEMO 3 COMPLETE: Report acknowledged then invalidated; finder notified."
    )


_ALL_DEMOS: Sequence[Tuple[str, object]] = [
    ("Demo 1: Acknowledge Only", demo_acknowledge_only),
    ("Demo 2: Acknowledge then Validate", demo_acknowledge_then_validate),
    ("Demo 3: Acknowledge then Invalidate", demo_acknowledge_then_invalidate),
]


def main(
    skip_health_check: bool = False,
    demos: Optional[Sequence] = None,
):
    """
    Main entry point for the acknowledge demo script.

    Args:
        skip_health_check: Skip the server availability check (useful for testing)
        demos: Optional sequence of demo functions to run. Defaults to all three.
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
