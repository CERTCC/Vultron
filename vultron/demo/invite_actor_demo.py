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
Demonstrates the workflow for inviting an actor to a case via the Vultron API.

This demo script showcases two invitation paths:

1. Accept path: case owner invites coordinator → coordinator accepts →
   coordinator becomes a case participant
2. Reject path: case owner invites coordinator → coordinator rejects →
   coordinator is not added to the case

Each demo starts from an initialized case (report submitted and validated,
case created, finder participant added) so that the invitation workflow can
be demonstrated in isolation.

This corresponds to the workflow documented in:
    docs/howto/activitypub/activities/invite_actor.md

When run as a script, this module will:
1. Check if the API server is available
2. Reset the data layer to a clean state
3. Discover actors (finder, vendor, coordinator) via the API
4. Run both demo workflows (accept and reject)
5. Verify side effects in the data layer

Note on direct inbox communication:
This demo uses direct inbox-to-inbox communication between actors, per the
Vultron prototype design. Actors post activities directly to each other's
inboxes.
"""

# Standard library imports
import logging
import sys
from typing import Callable, Optional, Sequence, Tuple

# Vultron imports
from vultron.wire.as2.vocab.activities.case import (
    AddReportToCaseActivity,
    CreateCaseActivity,
)
from vultron.wire.as2.vocab.activities.case import (
    RmAcceptInviteToCaseActivity,
    RmInviteToCaseActivity,
    RmRejectInviteToCaseActivity,
)
from vultron.wire.as2.vocab.activities.case_participant import (
    AddParticipantToCaseActivity,
)
from vultron.wire.as2.vocab.activities.report import (
    RmSubmitReportActivity,
    RmValidateReportActivity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Create
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.case_participant import (
    FinderReporterParticipant,
)
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
    demo_environment,
    log_case_state,
    logfmt,
    post_to_inbox_and_wait,
    ref_id,
    verify_object_stored,
)

logger = logging.getLogger(__name__)


def _setup_initialized_case(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
) -> VulnerabilityCase:
    """
    Set up an initialized case as a precondition for the invite workflow.

    Mirrors demo_initialize_case from initialize_case_demo but returns the
    VulnerabilityCase so subsequent steps can reference it.
    """
    report = VulnerabilityReport(
        attributed_to=finder.id_,
        content="A remote code execution vulnerability in the web framework.",
        name="Remote Code Execution Vulnerability",
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
        content="Confirmed — remote code execution via unsanitized input.",
    )
    post_to_inbox_and_wait(client, vendor.id_, validate_activity)

    case = VulnerabilityCase(
        attributed_to=vendor.id_,
        name="RCE Case — Web Framework",
        content="Tracking the RCE vulnerability in the web framework.",
    )
    create_case_activity = CreateCaseActivity(
        actor=vendor.id_,
        object_=case,
    )
    post_to_inbox_and_wait(client, vendor.id_, create_case_activity)
    verify_object_stored(client, case.id_)

    add_report_activity = AddReportToCaseActivity(
        actor=vendor.id_,
        object_=report,
        target=case.id_,
    )
    post_to_inbox_and_wait(client, vendor.id_, add_report_activity)

    participant = FinderReporterParticipant(
        attributed_to=finder.id_,
        context=case.id_,
    )
    create_participant_activity = as_Create(
        actor=vendor.id_,
        object_=participant,
        context=case.id_,
    )
    post_to_inbox_and_wait(client, vendor.id_, create_participant_activity)
    verify_object_stored(client, participant.id_)

    add_participant_activity = AddParticipantToCaseActivity(
        actor=vendor.id_,
        object_=participant,
        target=case.id_,
    )
    post_to_inbox_and_wait(client, vendor.id_, add_participant_activity)

    log_case_state(client, case.id_, "after setup")
    logger.info("✓ Setup: Case initialized with report and finder participant")
    return case


def demo_invite_actor_accept(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor,
) -> None:
    """
    Demonstrates the accept path of the invite-actor-to-case workflow.

    Steps:
    1. Setup: initialize case (report submitted + validated, case created,
       finder participant added)
    2. Vendor invites coordinator to case (RmInviteToCaseActivity → coordinator inbox)
    3. Coordinator accepts invitation (RmAcceptInviteToCaseActivity → vendor inbox)
    4. Verify coordinator appears in case participant list

    This follows the accept branch in
    docs/howto/activitypub/activities/invite_actor.md.
    """
    logger.info("=" * 80)
    logger.info("DEMO: Invite Actor — Accept Path")
    logger.info("=" * 80)

    case = _setup_initialized_case(client, finder, vendor)

    with demo_step("Step 2: Vendor invites coordinator to case"):
        invite = RmInviteToCaseActivity(
            actor=vendor.id_,
            object_=coordinator,
            target=case.id_,
            to=[coordinator.id_],
            content=f"We're inviting you to participate in {case.name}.",
        )
        logger.info(f"Sending invite: {logfmt(invite)}")
        post_to_inbox_and_wait(client, coordinator.id_, invite)

    with demo_step("Step 3: Coordinator accepts invitation"):
        # reference invite by ID so the handler can rehydrate it from the
        # datalayer with all fields intact
        accept = RmAcceptInviteToCaseActivity(
            actor=coordinator.id_,
            object_=invite,
            to=[vendor.id_],
            content=f"Accepting invitation to participate in {case.name}.",
        )
        logger.info(f"Sending accept: {logfmt(accept)}")
        post_to_inbox_and_wait(client, vendor.id_, accept)

    with demo_step("Step 4: Verify coordinator added as case participant"):
        with demo_check("Coordinator present in case participant list"):
            # The handler creates a participant with ID
            # {case_uuid}/participants/{coord_segment}. Check participant list grew.
            final_case = log_case_state(client, case.id_, "after accept")
            if final_case is None:
                raise ValueError("Could not retrieve case after accept")
            participant_ids = [
                (ref_id(p) or str(p)) for p in final_case.case_participants
            ]
            coord_segment = coordinator.id_.split("/")[-1]
            coord_participant = [
                pid
                for pid in participant_ids
                if str(pid).endswith(coord_segment)
            ]
            if not coord_participant:
                raise ValueError(
                    f"Coordinator '{coordinator.id_}' not found in case "
                    f"participants after accept. Participants: {participant_ids}"
                )

    logger.info("✅ DEMO COMPLETE (accept path): Coordinator added to case.")


def demo_invite_actor_reject(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor,
) -> None:
    """
    Demonstrates the reject path of the invite-actor-to-case workflow.

    Steps:
    1. Setup: initialize case (report submitted + validated, case created,
       finder participant added)
    2. Vendor invites coordinator to case (RmInviteToCaseActivity → coordinator inbox)
    3. Coordinator rejects invitation (RmRejectInviteToCaseActivity → vendor inbox)
    4. Verify coordinator does NOT appear in case participant list

    This follows the reject branch in
    docs/howto/activitypub/activities/invite_actor.md.
    """
    logger.info("=" * 80)
    logger.info("DEMO: Invite Actor — Reject Path")
    logger.info("=" * 80)

    case = _setup_initialized_case(client, finder, vendor)

    initial_case = log_case_state(client, case.id_, "initial")
    initial_count = len(initial_case.case_participants) if initial_case else 0

    with demo_step("Step 2: Vendor invites coordinator to case"):
        invite = RmInviteToCaseActivity(
            actor=vendor.id_,
            object_=coordinator,
            target=case.id_,
            to=[coordinator.id_],
            content=f"We're inviting you to participate in {case.name}.",
        )
        logger.info(f"Sending invite: {logfmt(invite)}")
        post_to_inbox_and_wait(client, coordinator.id_, invite)

    with demo_step("Step 3: Coordinator rejects invitation"):
        # reference invite by ID so the handler can rehydrate it from the
        # datalayer with all fields intact
        reject = RmRejectInviteToCaseActivity(
            actor=coordinator.id_,
            object_=invite,
            to=[vendor.id_],
            content=f"Declining the invitation to participate in {case.name}.",
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

    logger.info("✅ DEMO COMPLETE (reject path): Invite rejected gracefully.")


_ALL_DEMOS: Sequence[Tuple[str, Callable[..., None]]] = [
    ("Demo: Invite Actor — Accept Path", demo_invite_actor_accept),
    ("Demo: Invite Actor — Reject Path", demo_invite_actor_reject),
]


def main(
    skip_health_check: bool = False,
    demos: Optional[Sequence] = None,
) -> None:
    """
    Main entry point for the invite_actor demo script.

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
