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
2. Create Case: vendor explicitly creates a as_VulnerabilityCase
3. Add Vendor as Participant: vendor adds themselves as case creator/owner
4. Add Report to Case: vendor links the submitted report to the case
5. Invite the Finder: vendor sends the finder the stub Invite
6. Finder Joins: the finder accepts, and the vendor, as CASE_MANAGER, seats it
   (ADR-0114; ``Add(CaseParticipant)`` only reinstates, CM-31-011)
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
from collections.abc import Callable, Sequence

from vultron.demo.helpers.runner import run_exchange_demos
from vultron.demo.helpers.workflow import (
    create_case_via_trigger,
    seat_participant_through_stub_invite,
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
    verify_object_stored,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import (
    add_report_to_case_activity,
    rm_submit_report_activity,
    rm_validate_report_activity,
)

# Vultron imports
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

logger = logging.getLogger(__name__)


def demo_initialize_case(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor | None = None,
):
    """
    Demonstrates the full case initialization workflow.

    Steps:
    1. Finder submits a vulnerability report to vendor inbox
    2. Vendor validates the report (RmValidateReportActivity)
    3. Vendor creates the case through the create-case trigger
    4. The trigger registers the vendor as CASE_OWNER and CASE_MANAGER
    5. Vendor adds the report to the case (AddReportToCaseActivity)
    6. Vendor asks the CASE_MANAGER (itself) to invite the finder, which
       sends the stub Invite
    7. Finder accepts (RmAcceptInviteToCaseActivity), which seats it as a
       FINDER participant (ADR-0114)
    8. Final case state is logged

    This follows the workflow in docs/howto/activitypub/activities/initialize_case.md.
    The case creator (vendor) must be added as a participant before any other
    participants, as they need to be a case participant to act on the case.
    The vendor is also the case owner, indicated by attributed_to on the case.
    """
    logger.info("=" * 80)
    logger.info("DEMO: Initialize Case")
    logger.info("=" * 80)

    report = report_offer = None
    with demo_step("Step 1: Finder submits vulnerability report to vendor"):
        report = as_VulnerabilityReport(
            attributed_to=finder.id_,
            content="A remote code execution vulnerability in the web framework.",
            name="Remote Code Execution Vulnerability",
        )
        logger.info("Created report: %s", logfmt(report))
        report_offer = rm_submit_report_activity(
            report, actor=finder.id_, to=vendor.id_
        )
        post_to_inbox_and_wait(client, vendor.id_, report_offer)
        with demo_check("Report stored in data layer"):
            verify_object_stored(client, report.id_)

    with demo_step("Step 2: Vendor validates report"):
        offer = get_offer_from_datalayer(client, vendor.id_, report_offer.id_)
        validate_activity = rm_validate_report_activity(
            offer,
            actor=vendor.id_,
            content="Confirmed — remote code execution via unsanitized input.",
        )
        post_to_inbox_and_wait(client, vendor.id_, validate_activity)

    case = None
    with demo_step("Step 3: Vendor creates vulnerability case"):
        case = create_case_via_trigger(
            client,
            vendor,
            name="RCE Case — Web Framework",
            content="Tracking the RCE vulnerability in the web framework.",
            stub_summary=(
                "Remote code execution in web framework"
                " — details shared after acceptance."
            ),
        )
        logger.info("Created case object: %s", logfmt(case))
        with demo_check("Case stored in data layer"):
            verify_object_stored(client, case.id_)
        with demo_check("Case state after CreateCaseActivity"):
            log_case_state(client, case.id_, "after CreateCaseActivity")

    with demo_step("Step 4: Vendor is registered as case participant"):
        # The create-case trigger registers the vendor as CASE_OWNER and
        # CASE_MANAGER, so no Create/Add(CaseParticipant) is injected for it.
        with demo_check("Vendor is a case participant"):
            vendor_case = log_case_state(
                client, case.id_, "after create-case trigger"
            )
            if (
                vendor_case
                and vendor.id_ not in vendor_case.actor_participant_index
            ):
                raise ValueError(
                    f"Vendor '{vendor.id_}' is not a participant of the new case"
                )
        logger.info("Vendor added as participant to case")

    with demo_step("Step 5: Vendor links report to case"):
        add_report_activity = add_report_to_case_activity(
            report, actor=vendor.id_, target=case.id_
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

    with demo_step(
        "Steps 6-7: Vendor invites finder; finder accepts and joins"
    ):
        participant = seat_participant_through_stub_invite(
            client, case, owner=vendor, invitee=finder, role=CVDRole.FINDER
        )
        logger.info("Seated participant: %s", logfmt(participant))
        with demo_check("Finder participant in case participant list"):
            final_case = log_case_state(
                client, case.id_, "after the finder accepted"
            )
            if final_case and participant.id_ not in [
                (ref_id(p) or str(p)) for p in final_case.case_participants
            ]:
                raise ValueError(
                    f"Participant '{participant.id_}' not found in case "
                    "after the finder accepted its stub Invite"
                )

    logger.info(
        "✅ DEMO COMPLETE: Case initialized with vendor and finder participants."
    )


_ALL_DEMOS: Sequence[tuple[str, Callable[..., None]]] = [
    ("Demo: Initialize Case", demo_initialize_case),
]


def main(
    skip_health_check: bool = False,
    demos: Sequence | None = None,
) -> None:
    """Main entry point for the initialize case demo demo script."""
    run_exchange_demos(
        _ALL_DEMOS, skip_health_check=skip_health_check, demos=demos
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
