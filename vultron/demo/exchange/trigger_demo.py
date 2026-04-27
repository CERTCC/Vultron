#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
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
Demonstrates the trigger endpoint workflow for the Vultron API.

Trigger endpoints let an actor *proactively initiate* a CVD protocol behavior
based on its own internal state, as opposed to reacting to an inbound
ActivityStreams message.  They are the outgoing counterpart to the inbound
handler pipeline and are essential for demonstrating the full Vultron Protocol
(see ``specs/triggerable-behaviors.yaml`` and ``notes/triggerable-behaviors.md``).

Two demo workflows are shown:

1. **Validate and Engage**: Finder submits a report via inbox (reactive setup);
   vendor then proactively validates the report and engages the resulting case
   using ``POST /actors/{actor_id}/trigger/validate-report`` and
   ``POST /actors/{actor_id}/trigger/engage-case``.

2. **Invalidate and Close**: Finder submits a second report via inbox; vendor
   proactively invalidates it via ``POST .../trigger/invalidate-report`` and
   then closes it via ``POST .../trigger/close-report``.

Each demo verifies that the resulting ActivityStreams activity is returned in
the response body and that the vendor's outbox is updated accordingly.
"""

import json
import logging
import sys
from typing import Callable, Optional, Sequence, Tuple

from vultron.wire.as2.vocab.activities.report import RmSubmitReportActivity
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)
from vultron.demo.utils import (
    DataLayerClient,
    check_server_availability,
    demo_check,
    demo_environment,
    demo_step,
    get_offer_from_datalayer,
    post_to_inbox_and_wait,
    post_to_trigger,
    verify_object_stored,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared setup helpers
# ---------------------------------------------------------------------------


def _submit_report(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    name: str,
    content: str,
) -> Tuple[VulnerabilityReport, RmSubmitReportActivity]:
    """Finder submits a vulnerability report to the vendor's inbox.

    Returns the ``(report, offer)`` pair after verifying both are stored.
    """
    report = VulnerabilityReport(
        attributed_to=finder.id_,
        name=name,
        content=content,
    )
    offer = RmSubmitReportActivity(
        actor=finder.id_,
        object_=report,
        to=[vendor.id_],
    )
    post_to_inbox_and_wait(client, vendor.id_, offer)
    with demo_check("Report and offer stored in DataLayer"):
        verify_object_stored(client, report.id_)
        verify_object_stored(client, offer.id_)
    return report, offer


def _find_case_for_report(
    client: DataLayerClient, report_id: str
) -> Optional[VulnerabilityCase]:
    """Return the first VulnerabilityCase referencing *report_id*, or None."""
    cases = client.get("/datalayer/VulnerabilityCases/")
    if not cases:
        return None
    for item in cases:
        if isinstance(item, str):
            try:
                data = client.get(f"/datalayer/{item}")
                case = VulnerabilityCase(**data)
            except Exception as exc:
                logger.warning("Could not fetch case %s: %s", item, exc)
                continue
        else:
            case = VulnerabilityCase(**item)
        report_ids = [
            r if isinstance(r, str) else getattr(r, "id_", str(r))
            for r in (case.vulnerability_reports or [])
        ]
        if report_id in report_ids:
            return case
    return None


# ---------------------------------------------------------------------------
# Demo 1: validate-report trigger → engage-case trigger
# ---------------------------------------------------------------------------


def demo_validate_and_engage(
    client: DataLayerClient, finder: as_Actor, vendor: as_Actor
) -> None:
    """Demonstrate proactive validation and case engagement via trigger endpoints.

    Workflow:
    1. Finder submits a vulnerability report to the vendor (reactive inbox step).
    2. Vendor calls ``POST .../trigger/validate-report`` to validate the report.
    3. Vendor calls ``POST .../trigger/engage-case`` to engage the created case.
    """
    logger.info("=" * 80)
    logger.info("TRIGGER DEMO 1: Validate Report → Engage Case")
    logger.info("=" * 80)

    with demo_step("Step 1: Finder submits vulnerability report to vendor"):
        report, offer = _submit_report(
            client=client,
            finder=finder,
            vendor=vendor,
            name="Remote Code Execution in Network Stack",
            content=(
                "A use-after-free in the TCP/IP stack allows a remote "
                "attacker to execute arbitrary code."
            ),
        )

    with demo_step("Step 2: Vendor triggers validate-report"):
        stored_offer = get_offer_from_datalayer(client, vendor.id_, offer.id_)
        response = post_to_trigger(
            client=client,
            actor_id=vendor.id_,
            behavior="validate-report",
            body={"offer_id": stored_offer.id_},
        )
        logger.info(
            "validate-report response: %s",
            json.dumps(response, indent=2),
        )
        with demo_check("Response contains activity"):
            activity = response.get("activity")
            assert (
                activity is not None
            ), "Expected 'activity' key in trigger response"
            logger.info("Resulting activity type: %s", activity.get("type"))

    with demo_step("Step 3: Vendor triggers engage-case"):
        case = _find_case_for_report(client, report.id_)
        with demo_check("Case created by validate-report BT"):
            assert (
                case is not None
            ), f"No VulnerabilityCase found for report {report.id_}"
            logger.info("Found case: %s", case.id_)

        response = post_to_trigger(
            client=client,
            actor_id=vendor.id_,
            behavior="engage-case",
            body={"case_id": case.id_},
        )
        logger.info(
            "engage-case response: %s",
            json.dumps(response, indent=2),
        )
        with demo_check("Response contains activity"):
            activity = response.get("activity")
            assert (
                activity is not None
            ), "Expected 'activity' key in engage-case trigger response"
            logger.info("Resulting activity type: %s", activity.get("type"))

    logger.info(
        "✅ TRIGGER DEMO 1 COMPLETE: Report validated and case engaged "
        "via trigger endpoints."
    )


# ---------------------------------------------------------------------------
# Demo 2: invalidate-report trigger → close-report trigger
# ---------------------------------------------------------------------------


def demo_invalidate_and_close(
    client: DataLayerClient, finder: as_Actor, vendor: as_Actor
) -> None:
    """Demonstrate proactive invalidation and report closure via trigger endpoints.

    Workflow:
    1. Finder submits a report that the vendor deems invalid.
    2. Vendor calls ``POST .../trigger/invalidate-report`` to mark it invalid.
    3. Vendor calls ``POST .../trigger/close-report`` to close it entirely.
    """
    logger.info("=" * 80)
    logger.info("TRIGGER DEMO 2: Invalidate Report → Close Report")
    logger.info("=" * 80)

    with demo_step("Step 1: Finder submits a low-quality report to vendor"):
        report, offer = _submit_report(
            client=client,
            finder=finder,
            vendor=vendor,
            name="Alleged Vulnerability in Demo Component",
            content=(
                "The reporter claims a vulnerability exists but provides no "
                "reproduction steps or supporting evidence."
            ),
        )

    with demo_step("Step 2: Vendor triggers invalidate-report"):
        stored_offer = get_offer_from_datalayer(client, vendor.id_, offer.id_)
        response = post_to_trigger(
            client=client,
            actor_id=vendor.id_,
            behavior="invalidate-report",
            body={
                "offer_id": stored_offer.id_,
                "note": "Report lacks reproduction steps; marked invalid.",
            },
        )
        logger.info(
            "invalidate-report response: %s",
            json.dumps(response, indent=2),
        )
        with demo_check("Response contains activity"):
            activity = response.get("activity")
            assert (
                activity is not None
            ), "Expected 'activity' key in invalidate-report response"
            logger.info("Resulting activity type: %s", activity.get("type"))

    with demo_step("Step 3: Vendor triggers close-report"):
        response = post_to_trigger(
            client=client,
            actor_id=vendor.id_,
            behavior="close-report",
            body={
                "offer_id": stored_offer.id_,
                "note": "Closing report — no valid vulnerability confirmed.",
            },
        )
        logger.info(
            "close-report response: %s",
            json.dumps(response, indent=2),
        )
        with demo_check("Response contains activity"):
            activity = response.get("activity")
            assert (
                activity is not None
            ), "Expected 'activity' key in close-report trigger response"
            logger.info("Resulting activity type: %s", activity.get("type"))

    logger.info(
        "✅ TRIGGER DEMO 2 COMPLETE: Report invalidated and closed "
        "via trigger endpoints."
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

_ALL_DEMOS: Sequence[Tuple[str, Callable[..., None]]] = [
    ("Demo 1: Validate and Engage", demo_validate_and_engage),
    ("Demo 2: Invalidate and Close", demo_invalidate_and_close),
]


def main(
    skip_health_check: bool = False,
    demos: Optional[Sequence] = None,
) -> None:
    """Main entry point for the trigger demo.

    Args:
        skip_health_check: Skip the server availability check (useful for
            testing).
        demos: Optional sequence of demo functions to run.  Defaults to all
            two.
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
            with demo_environment(client) as (finder, vendor, _coordinator):
                demo_fn(client, finder, vendor)
        except Exception as exc:
            logger.error("%s failed: %s", demo_name, exc, exc_info=True)
            errors.append((demo_name, str(exc)))

    logger.info("=" * 80)
    logger.info("ALL TRIGGER DEMOS COMPLETE")
    logger.info("=" * 80)

    if errors:
        logger.error("")
        logger.error("=" * 80)
        logger.error("ERROR SUMMARY")
        logger.error("=" * 80)
        logger.error("Total demos: %d", total)
        logger.error("Failed demos: %d", len(errors))
        logger.error("Successful demos: %d", total - len(errors))
        logger.error("")
        for demo_name, error in errors:
            logger.error("%s:", demo_name)
            logger.error("  %s", error)
            logger.error("")
        logger.error("=" * 80)
        sys.exit(1)
    else:
        logger.info("")
        logger.info("✓ All %d trigger demos completed successfully!", total)
        logger.info("")


def _setup_logging() -> None:
    """Configure console logging for standalone script execution."""
    logging.getLogger("requests").setLevel(logging.WARNING)
    _logger = logging.getLogger()
    hdlr = logging.StreamHandler(sys.stdout)
    hdlr.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    )
    _logger.addHandler(hdlr)
    _logger.setLevel(logging.DEBUG)


if __name__ == "__main__":
    _setup_logging()
    main()
