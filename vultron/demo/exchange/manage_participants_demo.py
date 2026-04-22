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
Demonstrates the full manage-participants workflow via the Vultron API.

This demo script showcases two participant management paths:

1. Accept path: vendor invites coordinator → coordinator accepts →
   vendor creates coordinator participant → vendor adds participant to case →
   coordinator creates participant status → coordinator adds status to
   participant → vendor removes participant from case
2. Reject path: vendor invites coordinator → coordinator rejects →
   coordinator is not added to the case

Each demo starts from an initialized case (report submitted and validated,
case created, vendor participant added) so that the invitation and participant
management workflows can be demonstrated in isolation.

This corresponds to the workflow documented in:
    docs/howto/activitypub/activities/manage_participants.md

When run as a script, this module will:
1. Check if the API server is available
2. Reset the data layer to a clean state
3. Discover actors (finder, vendor, coordinator) via the API
4. Run both demo workflows (accept+manage and reject)
5. Verify side effects in the data layer
"""

import logging
import sys
from typing import Callable, Optional, Sequence, Tuple

from vultron.wire.as2.vocab.activities.case import (
    AddReportToCaseActivity,
    CreateCaseActivity,
)
from vultron.wire.as2.vocab.activities.case_participant import (
    AddParticipantToCaseActivity,
    AddStatusToParticipantActivity,
    CreateParticipantActivity,
    CreateStatusForParticipantActivity,
    RemoveParticipantFromCaseActivity,
)
from vultron.wire.as2.vocab.activities.case import (
    RmAcceptInviteToCaseActivity,
    RmInviteToCaseActivity,
    RmRejectInviteToCaseActivity,
)
from vultron.wire.as2.vocab.activities.report import (
    RmSubmitReportActivity,
    RmValidateReportActivity,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.case_participant import (
    CoordinatorParticipant,
    VendorParticipant,
)
from vultron.wire.as2.vocab.objects.case_status import ParticipantStatus
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)
from vultron.core.states.rm import RM
from vultron.core.states.cs import CS_vfd
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


def _setup_case_with_vendor(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
) -> VulnerabilityCase:
    """
    Set up an initialized case owned by the vendor as a precondition for the
    manage-participants workflow.

    Steps:
    1. Finder submits report to vendor
    2. Vendor validates the report
    3. Vendor creates a VulnerabilityCase
    4. Vendor creates a VendorParticipant and adds it to the case
    5. Report is linked to the case

    Returns the created VulnerabilityCase.
    """
    report = VulnerabilityReport(
        attributed_to=finder.id_,
        content="A use-after-free vulnerability in the memory allocator.",
        name="Use-After-Free in Memory Allocator",
    )
    report_offer = RmSubmitReportActivity(
        actor=finder.id_,
        object_=report,
        to=[vendor.id_],
    )
    post_to_inbox_and_wait(client, vendor.id_, report_offer)
    verify_object_stored(client, report.id_)

    offer = get_offer_from_datalayer(client, vendor.id_, report_offer.id_)
    validate_activity = RmValidateReportActivity(
        actor=vendor.id_,
        object_=offer,
        content="Confirmed — use-after-free via crafted allocation sequence.",
    )
    post_to_inbox_and_wait(client, vendor.id_, validate_activity)

    case = VulnerabilityCase(
        attributed_to=vendor.id_,
        name="UAF Case — Memory Allocator",
        content="Tracking the use-after-free in the memory allocator.",
    )
    create_case_activity = CreateCaseActivity(
        actor=vendor.id_,
        object_=case,
    )
    post_to_inbox_and_wait(client, vendor.id_, create_case_activity)
    verify_object_stored(client, case.id_)

    vendor_participant = VendorParticipant(
        attributed_to=vendor.id_,
        context=case.id_,
    )
    create_vendor_participant = CreateParticipantActivity(
        actor=vendor.id_,
        object_=vendor_participant,
        context=case.id_,
    )
    post_to_inbox_and_wait(client, vendor.id_, create_vendor_participant)

    add_vendor_participant = AddParticipantToCaseActivity(
        actor=vendor.id_,
        object_=vendor_participant,
        target=case.id_,
    )
    post_to_inbox_and_wait(client, vendor.id_, add_vendor_participant)

    add_report_activity = AddReportToCaseActivity(
        actor=vendor.id_,
        object_=report,
        target=case.id_,
    )
    post_to_inbox_and_wait(client, vendor.id_, add_report_activity)

    log_case_state(client, case.id_, "after setup")
    logger.info("✓ Setup: Case initialized with vendor as sole participant")
    return case


def demo_manage_participants_accept(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor,
) -> None:
    """
    Demonstrates the full accept path of the manage-participants workflow.

    Steps:
    1. Setup: initialize case (report submitted + validated, case created,
       vendor participant added)
    2. Vendor invites coordinator to case (RmInviteToCaseActivity)
    3. Coordinator accepts invitation (RmAcceptInviteToCaseActivity)
    4. Vendor creates coordinator participant (CreateParticipantActivity)
    5. Vendor adds coordinator participant to case (AddParticipantToCaseActivity)
    6. Coordinator creates a ParticipantStatus (CreateStatusForParticipantActivity)
    7. Coordinator adds the status to their participant (AddStatusToParticipantActivity)
    8. Vendor removes coordinator participant from case (RemoveParticipantFromCaseActivity)
    9. Verify coordinator no longer in case participant list

    This follows the accept branch in
    docs/howto/activitypub/activities/manage_participants.md.
    """
    logger.info("=" * 80)
    logger.info("DEMO: Manage Participants — Accept + Status + Remove Path")
    logger.info("=" * 80)

    case = _setup_case_with_vendor(client, finder, vendor)

    with demo_step("Step 2: Vendor invites coordinator to case"):
        invite = RmInviteToCaseActivity(
            actor=vendor.id_,
            object_=coordinator,
            target=case.id_,
            to=[coordinator.id_],
            content=f"Inviting you to participate in {case.name}.",
        )
        logger.info(f"Sending invite: {logfmt(invite)}")
        post_to_inbox_and_wait(client, coordinator.id_, invite)

    with demo_step("Step 3: Coordinator accepts invitation"):
        accept = RmAcceptInviteToCaseActivity(
            actor=coordinator.id_,
            object_=invite,
            to=[vendor.id_],
            content=f"Accepting invitation to participate in {case.name}.",
        )
        logger.info(f"Sending accept: {logfmt(accept)}")
        post_to_inbox_and_wait(client, vendor.id_, accept)

    with demo_step("Step 4: Vendor creates coordinator participant"):
        coordinator_participant = CoordinatorParticipant(
            attributed_to=coordinator.id_,
            context=case.id_,
        )
        create_participant = CreateParticipantActivity(
            actor=vendor.id_,
            object_=coordinator_participant,
            context=case.id_,
        )
        post_to_inbox_and_wait(client, vendor.id_, create_participant)
        with demo_check("Coordinator participant stored in data layer"):
            verify_object_stored(client, coordinator_participant.id_)

    with demo_step("Step 5: Vendor adds coordinator participant to case"):
        add_participant = AddParticipantToCaseActivity(
            actor=vendor.id_,
            object_=coordinator_participant,
            target=case.id_,
        )
        post_to_inbox_and_wait(client, vendor.id_, add_participant)
        with demo_check("Coordinator in case participant list"):
            updated_case = log_case_state(
                client, case.id_, "after AddParticipantToCaseActivity"
            )
            if updated_case is None:
                raise ValueError(
                    "Could not retrieve case after add participant"
                )
            participant_ids = [
                (ref_id(p) or str(p)) for p in updated_case.case_participants
            ]
            if coordinator_participant.id_ not in participant_ids:
                raise ValueError(
                    f"Coordinator participant '{coordinator_participant.id_}' "
                    f"not found in case after add. Participants: {participant_ids}"
                )

    with demo_step("Step 6: Coordinator creates a ParticipantStatus"):
        participant_status = ParticipantStatus(
            context=coordinator_participant.id_,
            rm_state=RM.ACCEPTED,
            vfd_state=CS_vfd.vfd,
            attributed_to=coordinator.id_,
        )
        create_status = CreateStatusForParticipantActivity(
            actor=coordinator.id_,
            object_=participant_status,
            target=coordinator_participant.id_,
        )
        post_to_inbox_and_wait(client, coordinator.id_, create_status)
        with demo_check("ParticipantStatus stored in data layer"):
            verify_object_stored(client, participant_status.id_)

    with demo_step(
        "Step 7: Coordinator adds ParticipantStatus to their participant"
    ):
        add_status = AddStatusToParticipantActivity(
            actor=coordinator.id_,
            object_=participant_status,
            target=coordinator_participant.id_,
        )
        post_to_inbox_and_wait(client, coordinator.id_, add_status)
        with demo_check("Case state after status update"):
            log_case_state(
                client, case.id_, "after AddStatusToParticipantActivity"
            )

    with demo_step("Step 8: Vendor removes coordinator from case"):
        remove_participant = RemoveParticipantFromCaseActivity(
            actor=vendor.id_,
            object_=coordinator_participant,
            target=case.id_,
        )
        post_to_inbox_and_wait(client, vendor.id_, remove_participant)

    with demo_step("Step 9: Verify coordinator no longer in case"):
        with demo_check("Coordinator absent from case participant list"):
            final_case = log_case_state(
                client, case.id_, "after RemoveParticipantFromCaseActivity"
            )
            if final_case is None:
                raise ValueError("Could not retrieve case after remove")
            participant_ids = [
                (ref_id(p) or str(p)) for p in final_case.case_participants
            ]
            if coordinator_participant.id_ in participant_ids:
                raise ValueError(
                    f"Coordinator participant '{coordinator_participant.id_}' "
                    f"still present after remove. Participants: {participant_ids}"
                )
            logger.info(
                "✓ Coordinator participant removed from case successfully"
            )

    logger.info(
        "✅ DEMO COMPLETE (accept path): Coordinator added, status set,"
        " then removed from case."
    )


def demo_manage_participants_reject(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor,
) -> None:
    """
    Demonstrates the reject path of the manage-participants workflow.

    Steps:
    1. Setup: initialize case (report submitted + validated, case created,
       vendor participant added)
    2. Vendor invites coordinator to case (RmInviteToCaseActivity)
    3. Coordinator rejects invitation (RmRejectInviteToCaseActivity)
    4. Verify coordinator does NOT appear in case participant list

    This follows the reject branch in
    docs/howto/activitypub/activities/manage_participants.md.
    """
    logger.info("=" * 80)
    logger.info("DEMO: Manage Participants — Reject Path")
    logger.info("=" * 80)

    case = _setup_case_with_vendor(client, finder, vendor)

    initial_case = log_case_state(client, case.id_, "initial")
    initial_count = len(initial_case.case_participants) if initial_case else 0

    with demo_step("Step 2: Vendor invites coordinator to case"):
        invite = RmInviteToCaseActivity(
            actor=vendor.id_,
            object_=coordinator,
            target=case.id_,
            to=[coordinator.id_],
            content=f"Inviting you to participate in {case.name}.",
        )
        logger.info(f"Sending invite: {logfmt(invite)}")
        post_to_inbox_and_wait(client, coordinator.id_, invite)

    with demo_step("Step 3: Coordinator rejects invitation"):
        reject = RmRejectInviteToCaseActivity(
            actor=coordinator.id_,
            object_=invite,
            to=[vendor.id_],
            content=f"Declining invitation to participate in {case.name}.",
        )
        logger.info(f"Sending reject: {logfmt(reject)}")
        post_to_inbox_and_wait(client, vendor.id_, reject)

    with demo_step("Step 4: Verify coordinator not added as participant"):
        with demo_check("Participant count unchanged after reject"):
            final_case = log_case_state(client, case.id_, "after reject")
            if final_case is None:
                raise ValueError("Could not retrieve case after reject")
            final_count = len(final_case.case_participants)
            if final_count != initial_count:
                raise ValueError(
                    f"Expected participant count to remain {initial_count} after "
                    f"reject, got {final_count}"
                )

    logger.info(
        "✅ DEMO COMPLETE (reject path): Invitation rejected gracefully."
    )


_ALL_DEMOS: Sequence[Tuple[str, Callable[..., None]]] = [
    (
        "Demo: Manage Participants — Accept + Status + Remove Path",
        demo_manage_participants_accept,
    ),
    (
        "Demo: Manage Participants — Reject Path",
        demo_manage_participants_reject,
    ),
]


def main(
    skip_health_check: bool = False,
    demos: Optional[Sequence] = None,
) -> None:
    """
    Main entry point for the manage_participants demo script.

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
                demo_fn(client, finder, vendor, coordinator)
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
    import logging as _logging

    formatter = _logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    hdlr.setFormatter(formatter)
    logger_.addHandler(hdlr)
    logger_.setLevel(logging.DEBUG)


if __name__ == "__main__":
    _setup_logging()
    main()
