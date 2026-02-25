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
from typing import Optional, Sequence, Tuple

from vultron.as_vocab.activities.case import AddReportToCase, CreateCase
from vultron.as_vocab.activities.case_participant import (
    AddParticipantToCase,
    AddStatusToParticipant,
    CreateParticipant,
    CreateStatusForParticipant,
    RemoveParticipantFromCase,
)
from vultron.as_vocab.activities.case import (
    RmAcceptInviteToCase,
    RmInviteToCase,
    RmRejectInviteToCase,
)
from vultron.as_vocab.activities.report import RmSubmitReport, RmValidateReport
from vultron.as_vocab.base.objects.actors import as_Actor
from vultron.as_vocab.objects.case_participant import (
    CoordinatorParticipant,
    VendorParticipant,
)
from vultron.as_vocab.objects.case_status import ParticipantStatus
from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport
from vultron.bt.report_management.states import RM
from vultron.case_states.states import CS_vfd
from vultron.scripts.initialize_case_demo import (
    BASE_URL,
    DataLayerClient,
    check_server_availability,
    demo_check,
    demo_step,
    get_offer_from_datalayer,
    log_case_state,
    logfmt,
    post_to_inbox_and_wait,
    setup_clean_environment,
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
        attributed_to=finder.as_id,
        content="A use-after-free vulnerability in the memory allocator.",
        name="Use-After-Free in Memory Allocator",
    )
    report_offer = RmSubmitReport(
        actor=finder.as_id,
        as_object=report,
        to=[vendor.as_id],
    )
    post_to_inbox_and_wait(client, vendor.as_id, report_offer)
    verify_object_stored(client, report.as_id)

    offer = get_offer_from_datalayer(client, vendor.as_id, report_offer.as_id)
    validate_activity = RmValidateReport(
        actor=vendor.as_id,
        object=offer.as_id,
        content="Confirmed — use-after-free via crafted allocation sequence.",
    )
    post_to_inbox_and_wait(client, vendor.as_id, validate_activity)

    case = VulnerabilityCase(
        attributed_to=vendor.as_id,
        name="UAF Case — Memory Allocator",
        content="Tracking the use-after-free in the memory allocator.",
    )
    create_case_activity = CreateCase(
        actor=vendor.as_id,
        as_object=case,
    )
    post_to_inbox_and_wait(client, vendor.as_id, create_case_activity)
    verify_object_stored(client, case.as_id)

    vendor_participant = VendorParticipant(
        attributed_to=vendor.as_id,
        context=case.as_id,
    )
    create_vendor_participant = CreateParticipant(
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

    add_report_activity = AddReportToCase(
        actor=vendor.as_id,
        as_object=report.as_id,
        target=case.as_id,
    )
    post_to_inbox_and_wait(client, vendor.as_id, add_report_activity)

    log_case_state(client, case.as_id, "after setup")
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
    2. Vendor invites coordinator to case (RmInviteToCase)
    3. Coordinator accepts invitation (RmAcceptInviteToCase)
    4. Vendor creates coordinator participant (CreateParticipant)
    5. Vendor adds coordinator participant to case (AddParticipantToCase)
    6. Coordinator creates a ParticipantStatus (CreateStatusForParticipant)
    7. Coordinator adds the status to their participant (AddStatusToParticipant)
    8. Vendor removes coordinator participant from case (RemoveParticipantFromCase)
    9. Verify coordinator no longer in case participant list

    This follows the accept branch in
    docs/howto/activitypub/activities/manage_participants.md.
    """
    logger.info("=" * 80)
    logger.info("DEMO: Manage Participants — Accept + Status + Remove Path")
    logger.info("=" * 80)

    case = _setup_case_with_vendor(client, finder, vendor)

    with demo_step("Step 2: Vendor invites coordinator to case"):
        invite = RmInviteToCase(
            actor=vendor.as_id,
            object=coordinator.as_id,
            target=case.as_id,
            to=[coordinator.as_id],
            content=f"Inviting you to participate in {case.name}.",
        )
        logger.info(f"Sending invite: {logfmt(invite)}")
        post_to_inbox_and_wait(client, coordinator.as_id, invite)

    with demo_step("Step 3: Coordinator accepts invitation"):
        accept = RmAcceptInviteToCase(
            actor=coordinator.as_id,
            object=invite.as_id,
            to=[vendor.as_id],
            content=f"Accepting invitation to participate in {case.name}.",
        )
        logger.info(f"Sending accept: {logfmt(accept)}")
        post_to_inbox_and_wait(client, vendor.as_id, accept)

    with demo_step("Step 4: Vendor creates coordinator participant"):
        coordinator_participant = CoordinatorParticipant(
            attributed_to=coordinator.as_id,
            context=case.as_id,
        )
        create_participant = CreateParticipant(
            actor=vendor.as_id,
            as_object=coordinator_participant,
            context=case.as_id,
        )
        post_to_inbox_and_wait(client, vendor.as_id, create_participant)
        with demo_check("Coordinator participant stored in data layer"):
            verify_object_stored(client, coordinator_participant.as_id)

    with demo_step("Step 5: Vendor adds coordinator participant to case"):
        add_participant = AddParticipantToCase(
            actor=vendor.as_id,
            as_object=coordinator_participant.as_id,
            target=case.as_id,
        )
        post_to_inbox_and_wait(client, vendor.as_id, add_participant)
        with demo_check("Coordinator in case participant list"):
            updated_case = log_case_state(
                client, case.as_id, "after AddParticipantToCase"
            )
            if updated_case is None:
                raise ValueError(
                    "Could not retrieve case after add participant"
                )
            participant_ids = [
                (p.as_id if hasattr(p, "as_id") else str(p))
                for p in updated_case.case_participants
            ]
            if coordinator_participant.as_id not in participant_ids:
                raise ValueError(
                    f"Coordinator participant '{coordinator_participant.as_id}' "
                    f"not found in case after add. Participants: {participant_ids}"
                )

    with demo_step("Step 6: Coordinator creates a ParticipantStatus"):
        participant_status = ParticipantStatus(
            context=coordinator_participant.as_id,
            rm_state=RM.ACCEPTED,
            vfd_state=CS_vfd.vfd,
            attributed_to=coordinator.as_id,
        )
        create_status = CreateStatusForParticipant(
            actor=coordinator.as_id,
            object=participant_status,
            target=coordinator_participant.as_id,
        )
        post_to_inbox_and_wait(client, coordinator.as_id, create_status)
        with demo_check("ParticipantStatus stored in data layer"):
            verify_object_stored(client, participant_status.as_id)

    with demo_step(
        "Step 7: Coordinator adds ParticipantStatus to their participant"
    ):
        add_status = AddStatusToParticipant(
            actor=coordinator.as_id,
            object=participant_status,
            target=coordinator_participant.as_id,
        )
        post_to_inbox_and_wait(client, coordinator.as_id, add_status)
        with demo_check("Case state after status update"):
            log_case_state(client, case.as_id, "after AddStatusToParticipant")

    with demo_step("Step 8: Vendor removes coordinator from case"):
        remove_participant = RemoveParticipantFromCase(
            actor=vendor.as_id,
            as_object=coordinator_participant.as_id,
            target=case.as_id,
        )
        post_to_inbox_and_wait(client, vendor.as_id, remove_participant)

    with demo_step("Step 9: Verify coordinator no longer in case"):
        with demo_check("Coordinator absent from case participant list"):
            final_case = log_case_state(
                client, case.as_id, "after RemoveParticipantFromCase"
            )
            if final_case is None:
                raise ValueError("Could not retrieve case after remove")
            participant_ids = [
                (p.as_id if hasattr(p, "as_id") else str(p))
                for p in final_case.case_participants
            ]
            if coordinator_participant.as_id in participant_ids:
                raise ValueError(
                    f"Coordinator participant '{coordinator_participant.as_id}' "
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
    2. Vendor invites coordinator to case (RmInviteToCase)
    3. Coordinator rejects invitation (RmRejectInviteToCase)
    4. Verify coordinator does NOT appear in case participant list

    This follows the reject branch in
    docs/howto/activitypub/activities/manage_participants.md.
    """
    logger.info("=" * 80)
    logger.info("DEMO: Manage Participants — Reject Path")
    logger.info("=" * 80)

    case = _setup_case_with_vendor(client, finder, vendor)

    initial_case = log_case_state(client, case.as_id, "initial")
    initial_count = len(initial_case.case_participants) if initial_case else 0

    with demo_step("Step 2: Vendor invites coordinator to case"):
        invite = RmInviteToCase(
            actor=vendor.as_id,
            object=coordinator.as_id,
            target=case.as_id,
            to=[coordinator.as_id],
            content=f"Inviting you to participate in {case.name}.",
        )
        logger.info(f"Sending invite: {logfmt(invite)}")
        post_to_inbox_and_wait(client, coordinator.as_id, invite)

    with demo_step("Step 3: Coordinator rejects invitation"):
        reject = RmRejectInviteToCase(
            actor=coordinator.as_id,
            object=invite.as_id,
            to=[vendor.as_id],
            content=f"Declining invitation to participate in {case.name}.",
        )
        logger.info(f"Sending reject: {logfmt(reject)}")
        post_to_inbox_and_wait(client, vendor.as_id, reject)

    with demo_step("Step 4: Verify coordinator not added as participant"):
        with demo_check("Participant count unchanged after reject"):
            final_case = log_case_state(client, case.as_id, "after reject")
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


_ALL_DEMOS: Sequence[Tuple[str, object]] = [
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
            finder, vendor, coordinator = setup_clean_environment(client)
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
