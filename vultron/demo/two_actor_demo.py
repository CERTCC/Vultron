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

"""Two-actor (Finder + Vendor) multi-container CVD workflow demo (D5-1-G5).

Orchestrates a complete CVD workflow across two separate API server containers:
a Finder who discovers a vulnerability and a Vendor who validates and engages
the case.  CaseActor is co-located in the Vendor container for this two-actor
scenario (D5-1-G3).

Environment variables
---------------------
``VULTRON_FINDER_BASE_URL``
    Base URL of the Finder container API
    (default: ``http://localhost:7901/api/v2``).
``VULTRON_VENDOR_BASE_URL``
    Base URL of the Vendor container API
    (default: ``http://localhost:7902/api/v2``).

Workflow
--------
1. **Seed**: Create actor records and register peers on both containers.
2. **Submit**: Finder submits a vulnerability report to the Vendor's inbox.
3. **Validate**: Vendor validates the report via the ``validate-report``
   trigger endpoint.
4. **Engage**: Vendor engages the resulting case via the ``engage-case``
   trigger endpoint.
5. **Invite**: Vendor invites Finder to join the case (delivered to
   Finder's inbox).
6. **Accept**: Finder accepts the invitation (delivered to Vendor's inbox).
7. **Verify**: Both containers show expected final state (case exists,
   Finder is a participant).

References: ``notes/multi-actor-architecture.md`` §4 G5,
``specs/multi-actor-demo.md`` DEMO-MA-03-001 through DEMO-MA-04-002.
"""

import logging
import os
import sys
from typing import Optional, Tuple

from vultron.adapters.utils import parse_id
from vultron.wire.as2.vocab.activities.case import (
    RmAcceptInviteToCaseActivity,
    RmInviteToCaseActivity,
)
from vultron.wire.as2.vocab.activities.report import (
    RmSubmitReportActivity,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)
from vultron.demo.utils import (  # noqa: F401 — re-exported for test monkeypatching
    BASE_URL,
    DataLayerClient,
    check_server_availability,
    demo_check,
    demo_step,
    logfmt,
    post_to_inbox_and_wait,
    post_to_trigger,
    ref_id,
    seed_actor,
    verify_object_stored,
)

logger = logging.getLogger(__name__)

# Default container base URLs — override via environment variables.
FINDER_BASE_URL = os.environ.get(
    "VULTRON_FINDER_BASE_URL", "http://localhost:7901/api/v2"
)
VENDOR_BASE_URL = os.environ.get(
    "VULTRON_VENDOR_BASE_URL", "http://localhost:7902/api/v2"
)

# Deterministic actor IDs from docker-compose-multi-actor.yml (D5-1-G3).
FINDER_ACTOR_ID = "http://finder:7999/api/v2/actors/finder"
VENDOR_ACTOR_ID = "http://vendor:7999/api/v2/actors/vendor"


# ---------------------------------------------------------------------------
# Seeding helpers
# ---------------------------------------------------------------------------


def seed_containers(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    finder_actor_id: str | None = None,
    vendor_actor_id: str | None = None,
) -> Tuple[as_Actor, as_Actor]:
    """Seed both containers: create actor records and register cross-container peers.

    The seeding is done in two phases to avoid ordering issues:

    1. Create the local actor on each container independently.
    2. Register each actor as a known peer on the other container.

    This function is idempotent: re-running it returns existing actors
    unchanged (the ``POST /actors/`` endpoint is idempotent).

    Args:
        finder_client: Client connected to the Finder container.
        vendor_client: Client connected to the Vendor container.
        finder_actor_id: Optional deterministic URI for the Finder actor.
            When absent the server derives one from ``VULTRON_BASE_URL``.
        vendor_actor_id: Optional deterministic URI for the Vendor actor.
            When absent the server derives one from ``VULTRON_BASE_URL``.

    Returns:
        Tuple of ``(finder, vendor)`` ``as_Actor`` objects as created on their
        respective containers.
    """
    logger.info("Phase 1: creating local actors on each container...")
    finder = seed_actor(
        client=finder_client,
        name="Finder",
        actor_type="Person",
        actor_id=finder_actor_id,
    )
    logger.info("Finder actor seeded on Finder container: %s", finder.id_)

    vendor = seed_actor(
        client=vendor_client,
        name="Vendor",
        actor_type="Organization",
        actor_id=vendor_actor_id,
    )
    logger.info("Vendor actor seeded on Vendor container: %s", vendor.id_)

    logger.info("Phase 2: registering cross-container peers...")
    seed_actor(
        client=finder_client,
        name="Vendor",
        actor_type="Organization",
        actor_id=vendor.id_,
    )
    logger.info("Vendor peer registered on Finder container: %s", vendor.id_)

    seed_actor(
        client=vendor_client,
        name="Finder",
        actor_type="Person",
        actor_id=finder.id_,
    )
    logger.info("Finder peer registered on Vendor container: %s", finder.id_)

    return finder, vendor


def get_actor_by_id(client: DataLayerClient, actor_id: str) -> as_Actor:
    """Fetch an actor record from a container by its full URI.

    Args:
        client: Client connected to the target container.
        actor_id: Full URI of the actor to fetch.

    Returns:
        The ``as_Actor`` object.

    Raises:
        ValueError: If the actor is not found.
    """
    actors = client.get("/actors/")
    for a in actors:
        actor = as_Actor.model_validate(a)
        if actor.id_ == actor_id:
            return actor
    raise ValueError(f"Actor {actor_id!r} not found in container")


# ---------------------------------------------------------------------------
# Workflow step functions
# ---------------------------------------------------------------------------


def finder_submits_report(
    vendor_client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
) -> Tuple[VulnerabilityReport, RmSubmitReportActivity]:
    """Finder creates a vulnerability report and submits it to the Vendor's inbox.

    The activity is POSTed directly to the Vendor container's inbox endpoint
    (simulating cross-container delivery; in production the Finder's outbox
    handler would deliver this via HTTP to the Vendor's inbox URL).

    Args:
        vendor_client: Client connected to the Vendor container.
        finder: Finder ``as_Actor``.
        vendor: Vendor ``as_Actor``.

    Returns:
        Tuple of ``(report, offer)``.
    """
    report = VulnerabilityReport(
        attributed_to=finder.id_,
        name="Remote Code Execution in Network Stack",
        content=(
            "A critical remote code execution vulnerability was discovered "
            "in the network stack component. An attacker can exploit this "
            "issue to execute arbitrary code with elevated privileges."
        ),
    )
    offer = RmSubmitReportActivity(
        actor=finder.id_,
        object_=report,
        to=[vendor.id_],
    )
    with demo_step("Finder submits vulnerability report to Vendor's inbox"):
        post_to_inbox_and_wait(vendor_client, vendor.id_, offer)
    with demo_check("Report and offer stored in Vendor's DataLayer"):
        verify_object_stored(vendor_client, report.id_)
        verify_object_stored(vendor_client, offer.id_)
    logger.info("Report submitted: %s", ref_id(report))
    return report, offer


def vendor_validates_report(
    vendor_client: DataLayerClient,
    vendor: as_Actor,
    offer_id: str,
) -> dict:
    """Vendor validates the submitted report via the trigger endpoint.

    Args:
        vendor_client: Client connected to the Vendor container.
        vendor: Vendor ``as_Actor``.
        offer_id: Full URI of the ``RmSubmitReportActivity`` offer to validate.

    Returns:
        Response dict from the trigger endpoint (contains the validate activity).
    """
    vendor_obj_id = parse_id(vendor.id_)["object_id"]
    with demo_step("Vendor validates the vulnerability report"):
        result = post_to_trigger(
            client=vendor_client,
            actor_id=vendor.id_,
            behavior="validate-report",
            body={"offer_id": offer_id},
        )
    logger.info("Validate-report trigger result for actor %s", vendor_obj_id)
    return result


def vendor_engages_case(
    vendor_client: DataLayerClient,
    vendor: as_Actor,
    case_id: str,
) -> dict:
    """Vendor engages the case via the trigger endpoint.

    Args:
        vendor_client: Client connected to the Vendor container.
        vendor: Vendor ``as_Actor``.
        case_id: Full URI of the ``VulnerabilityCase`` to engage.

    Returns:
        Response dict from the trigger endpoint.
    """
    vendor_obj_id = parse_id(vendor.id_)["object_id"]
    with demo_step("Vendor engages the vulnerability case"):
        result = post_to_trigger(
            client=vendor_client,
            actor_id=vendor.id_,
            behavior="engage-case",
            body={"case_id": case_id},
        )
    logger.info("Engage-case trigger result for actor %s", vendor_obj_id)
    return result


def vendor_invites_finder(
    finder_client: DataLayerClient,
    vendor: as_Actor,
    finder: as_Actor,
    case: VulnerabilityCase,
) -> RmInviteToCaseActivity:
    """Vendor invites the Finder to join the case.

    The invite activity is delivered directly to the Finder container's inbox
    endpoint (simulating cross-container delivery).

    Args:
        finder_client: Client connected to the Finder container.
        vendor: Vendor ``as_Actor`` (the inviting actor).
        finder: Finder ``as_Actor`` (the invited actor).
        case: The ``VulnerabilityCase`` to invite the Finder into.

    Returns:
        The ``RmInviteToCaseActivity`` invite activity.
    """
    invite = RmInviteToCaseActivity(
        actor=vendor.id_,
        object_=finder.id_,
        target=case.id_,
        to=[finder.id_],
    )
    with demo_step("Vendor invites Finder to the case"):
        post_to_inbox_and_wait(finder_client, finder.id_, invite)
    with demo_check("Invite stored in Finder's DataLayer"):
        verify_object_stored(finder_client, invite.id_)
    logger.info("Invite sent: %s", invite.id_)
    return invite


def finder_accepts_invite(
    vendor_client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    invite: RmInviteToCaseActivity,
) -> RmAcceptInviteToCaseActivity:
    """Finder accepts the invitation and notifies the Vendor.

    The acceptance activity is delivered directly to the Vendor container's
    inbox endpoint (simulating cross-container delivery).

    Args:
        vendor_client: Client connected to the Vendor container.
        finder: Finder ``as_Actor`` (the accepting actor).
        vendor: Vendor ``as_Actor`` (the inviting actor).
        invite: The original ``RmInviteToCaseActivity`` being accepted.

    Returns:
        The ``RmAcceptInviteToCaseActivity`` acceptance activity.
    """
    # Per AGENTS.md: Accept.object must be the invite's ID string, not the
    # inline object (avoids field loss during HTTP round-trip).
    accept = RmAcceptInviteToCaseActivity(
        actor=finder.id_,
        object_=invite.id_,
        to=[vendor.id_],
    )
    with demo_step("Finder accepts the case invitation"):
        post_to_inbox_and_wait(vendor_client, vendor.id_, accept)
    with demo_check("Accept activity stored in Vendor's DataLayer"):
        verify_object_stored(vendor_client, accept.id_)
    logger.info("Acceptance sent: %s", accept.id_)
    return accept


def find_case_for_offer(
    vendor_client: DataLayerClient,
    offer_id: str,
) -> Optional[VulnerabilityCase]:
    """Find the VulnerabilityCase associated with a report offer in the Vendor container.

    Args:
        vendor_client: Client connected to the Vendor container.
        offer_id: Full URI of the ``RmSubmitReportActivity`` offer.

    Returns:
        The matching ``VulnerabilityCase``, or ``None`` if not found.
    """
    offer_data = vendor_client.get(f"/datalayer/{offer_id}")
    if not offer_data:
        return None

    offer_object = offer_data.get("object")
    report_id: str | None
    if isinstance(offer_object, str):
        report_id = offer_object
    elif isinstance(offer_object, dict):
        report_id = offer_object.get("id")
    else:
        report_id = ref_id(offer_object)

    if not report_id:
        logger.warning("Offer %s does not reference a report object", offer_id)
        return None

    cases_data = vendor_client.get("/datalayer/VulnerabilityCases/")
    if not cases_data:
        return None
    for item in cases_data:
        if isinstance(item, str):
            try:
                data = vendor_client.get(f"/datalayer/{item}")
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
# Main workflow orchestration
# ---------------------------------------------------------------------------


def run_two_actor_demo(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    finder_id: str | None = None,
    vendor_id: str | None = None,
) -> None:
    """Orchestrate the complete two-actor (Finder + Vendor) CVD workflow.

    1. Seed both containers.
    2. Finder submits report → Vendor's inbox.
    3. Vendor validates report and engages case.
    4. Vendor invites Finder to the case → Finder's inbox.
    5. Finder accepts invite → Vendor's inbox.
    6. Verify final state on both containers.

    Args:
        finder_client: Client connected to the Finder container.
        vendor_client: Client connected to the Vendor container.
        finder_id: Optional deterministic URI for the Finder actor.
        vendor_id: Optional deterministic URI for the Vendor actor.
    """
    logger.info("=" * 80)
    logger.info("TWO-ACTOR DEMO: Finder + Vendor CVD Workflow (D5-1-G5)")
    logger.info("=" * 80)
    logger.info("Finder container: %s", finder_client.base_url)
    logger.info("Vendor container: %s", vendor_client.base_url)

    # ── Step 1: Seed containers ───────────────────────────────────────────
    with demo_step("Seeding both containers with actor records"):
        finder, vendor = seed_containers(
            finder_client=finder_client,
            vendor_client=vendor_client,
            finder_actor_id=finder_id,
            vendor_actor_id=vendor_id,
        )

    # Fetch vendor as seen from the vendor container (same actor, same ID).
    vendor_in_vendor = get_actor_by_id(vendor_client, vendor.id_)

    # ── Step 2: Finder submits report ─────────────────────────────────────
    report, offer = finder_submits_report(
        vendor_client=vendor_client,
        finder=finder,
        vendor=vendor_in_vendor,
    )

    # ── Step 3: Vendor validates and engages ──────────────────────────────
    vendor_validates_report(
        vendor_client=vendor_client,
        vendor=vendor_in_vendor,
        offer_id=offer.id_,
    )

    with demo_check("VulnerabilityCase exists in Vendor's DataLayer"):
        case = find_case_for_offer(vendor_client, offer.id_)
        if case is None:
            raise AssertionError(
                "Expected VulnerabilityCase to be created after validate-report"
            )
        logger.info("Case created: %s", case.id_)

    vendor_engages_case(
        vendor_client=vendor_client,
        vendor=vendor_in_vendor,
        case_id=case.id_,
    )

    # ── Step 4: Vendor invites Finder ─────────────────────────────────────
    # Refresh case to get up-to-date state.
    case_data = vendor_client.get(f"/datalayer/{case.id_}")
    case = VulnerabilityCase(**case_data)

    # Finder actor as known by the vendor container.
    finder_in_vendor = get_actor_by_id(vendor_client, finder.id_)

    invite = vendor_invites_finder(
        finder_client=finder_client,
        vendor=vendor_in_vendor,
        finder=finder_in_vendor,
        case=case,
    )

    # ── Step 5: Finder accepts ────────────────────────────────────────────
    # Finder actor from the Finder container.
    finder_in_finder = get_actor_by_id(finder_client, finder.id_)
    # Vendor as known by the Finder container.
    vendor_in_finder = get_actor_by_id(finder_client, vendor.id_)

    finder_accepts_invite(
        vendor_client=vendor_client,
        finder=finder_in_finder,
        vendor=vendor_in_finder,
        invite=invite,
    )

    # ── Step 6: Verify final state ────────────────────────────────────────
    with demo_check("Vendor container: case is present"):
        final_case_data = vendor_client.get(f"/datalayer/{case.id_}")
        final_case = VulnerabilityCase(**final_case_data)
        assert final_case.id_ == case.id_, "Case ID mismatch"
        logger.info("Final case state (Vendor): %s", logfmt(final_case))

    with demo_check("Finder container: invite is present"):
        verify_object_stored(finder_client, invite.id_)

    logger.info("=" * 80)
    logger.info("TWO-ACTOR DEMO COMPLETE ✓")
    logger.info("=" * 80)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(
    skip_health_check: bool = False,
    finder_url: str | None = None,
    vendor_url: str | None = None,
    finder_id: str | None = None,
    vendor_id: str | None = None,
) -> None:
    """Entry point for the two-actor multi-container CVD workflow demo.

    Args:
        skip_health_check: Skip the server availability check (useful for
            testing).
        finder_url: Override base URL for the Finder container.
        vendor_url: Override base URL for the Vendor container.
        finder_id: Optional deterministic URI for the Finder actor.
        vendor_id: Optional deterministic URI for the Vendor actor.
    """
    f_url = finder_url or FINDER_BASE_URL
    v_url = vendor_url or VENDOR_BASE_URL

    finder_client = DataLayerClient(base_url=f_url)
    vendor_client = DataLayerClient(base_url=v_url)

    if not skip_health_check:
        for label, client in [
            ("Finder", finder_client),
            ("Vendor", vendor_client),
        ]:
            if not check_server_availability(client):
                logger.error("=" * 80)
                logger.error("ERROR: %s API server is not available", label)
                logger.error("=" * 80)
                logger.error("Cannot connect to: %s", client.base_url)
                logger.error(
                    "Ensure the %s container is running and healthy.", label
                )
                logger.error("=" * 80)
                sys.exit(1)

    try:
        run_two_actor_demo(
            finder_client=finder_client,
            vendor_client=vendor_client,
            finder_id=finder_id,
            vendor_id=vendor_id,
        )
    except Exception as exc:
        logger.error("Two-actor demo failed: %s", exc, exc_info=True)
        logger.error("=" * 80)
        logger.error("ERROR SUMMARY")
        logger.error("=" * 80)
        logger.error("%s", exc)
        logger.error("=" * 80)
        sys.exit(1)


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
