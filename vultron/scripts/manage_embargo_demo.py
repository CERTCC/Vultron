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
Demonstrates the workflow for managing an embargo via the Vultron API.

This demo script showcases two embargo management paths:

1. Activate-and-terminate path: coordinator proposes embargo → vendor accepts
   → embargo is activated → vendor terminates (removes) the embargo
2. Reject-and-repropose path: coordinator proposes embargo → vendor rejects
   → coordinator proposes a revised embargo → vendor accepts → activated

Each demo starts from a case with two participants (vendor + coordinator)
as a precondition, then exercises the post-establishment management cycle.

This corresponds to the workflow documented in:
    docs/howto/activitypub/activities/manage_embargo.md

When run as a script, this module will:
1. Check if the API server is available
2. Reset the data layer to a clean state
3. Discover actors (finder, vendor, coordinator) via the API
4. Run both demo workflows
5. Verify side effects in the data layer

Note on direct inbox communication:
This demo uses direct inbox-to-inbox communication between actors, per the
Vultron prototype design. Actors post activities directly to each other's
inboxes.
"""

import logging
import sys
from datetime import datetime, timedelta
from typing import Optional, Sequence, Tuple

from vultron.as_vocab.activities.case import (
    AddReportToCase,
    CreateCase,
    RmAcceptInviteToCase,
    RmInviteToCase,
)
from vultron.as_vocab.activities.case_participant import AddParticipantToCase
from vultron.as_vocab.activities.embargo import (
    ActivateEmbargo,
    AnnounceEmbargo,
    EmAcceptEmbargo,
    EmProposeEmbargo,
    EmRejectEmbargo,
    RemoveEmbargoFromCase,
)
from vultron.as_vocab.activities.report import RmSubmitReport, RmValidateReport
from vultron.as_vocab.base.objects.activities.transitive import as_Create
from vultron.as_vocab.base.objects.actors import as_Actor
from vultron.as_vocab.objects.case_participant import (
    CoordinatorParticipant,
    FinderReporterParticipant,
)
from vultron.as_vocab.objects.embargo_event import EmbargoEvent
from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport
from vultron.demo.utils import (
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


def _make_embargo_event(
    case: VulnerabilityCase, days: int = 90, seq: int = 1
) -> EmbargoEvent:
    """Create a deterministic EmbargoEvent for a given case."""
    now = datetime.now().astimezone()
    now = now.replace(second=0, microsecond=0)
    end_at = (now + timedelta(days=days)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    end_date_str = end_at.strftime("%Y-%m-%d")
    return EmbargoEvent(
        id=f"{case.as_id}/embargo_events/{days}d-{end_date_str}-{seq}",
        name=f"Embargo for {case.name}",
        context=case.as_id,
        start_time=now,
        end_time=end_at,
        content=f"Proposed {days}-day embargo for {case.name}.",
    )


def _setup_two_participant_case(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor,
) -> VulnerabilityCase:
    """
    Set up a case with two participants (vendor + coordinator) as a
    precondition for the embargo management workflow.

    Steps:
    1. Finder submits report to vendor
    2. Vendor validates report
    3. Vendor creates case
    4. Vendor adds report to case
    5. Vendor adds finder as FinderReporter participant
    6. Vendor invites coordinator; coordinator accepts → coordinator added
    """
    report = VulnerabilityReport(
        attributed_to=finder.as_id,
        content="A heap-overflow vulnerability in the authentication library.",
        name="Heap Overflow in Auth Library",
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
        content="Confirmed — heap overflow via malformed auth token.",
    )
    post_to_inbox_and_wait(client, vendor.as_id, validate_activity)

    case = VulnerabilityCase(
        attributed_to=vendor.as_id,
        name="Heap Overflow — Auth Library",
        content="Tracking the heap-overflow vulnerability in the auth library.",
    )
    create_case_activity = CreateCase(
        actor=vendor.as_id,
        as_object=case,
    )
    post_to_inbox_and_wait(client, vendor.as_id, create_case_activity)
    verify_object_stored(client, case.as_id)

    add_report_activity = AddReportToCase(
        actor=vendor.as_id,
        as_object=report.as_id,
        target=case.as_id,
    )
    post_to_inbox_and_wait(client, vendor.as_id, add_report_activity)

    participant = FinderReporterParticipant(
        attributed_to=finder.as_id,
        context=case.as_id,
    )
    create_participant_activity = as_Create(
        actor=vendor.as_id,
        as_object=participant,
        context=case.as_id,
    )
    post_to_inbox_and_wait(client, vendor.as_id, create_participant_activity)
    verify_object_stored(client, participant.as_id)

    add_participant_activity = AddParticipantToCase(
        actor=vendor.as_id,
        as_object=participant.as_id,
        target=case.as_id,
    )
    post_to_inbox_and_wait(client, vendor.as_id, add_participant_activity)

    invite = RmInviteToCase(
        actor=vendor.as_id,
        object=coordinator.as_id,
        target=case.as_id,
        to=[coordinator.as_id],
        content=f"Inviting you to participate in {case.name}.",
    )
    post_to_inbox_and_wait(client, coordinator.as_id, invite)

    accept = RmAcceptInviteToCase(
        actor=coordinator.as_id,
        object=invite.as_id,
        to=[vendor.as_id],
        content=f"Accepting invitation to {case.name}.",
    )
    post_to_inbox_and_wait(client, vendor.as_id, accept)

    log_case_state(client, case.as_id, "after setup (two participants)")
    logger.info(
        "✓ Setup: Case initialized with vendor and coordinator participants"
    )
    return case


def demo_activate_then_terminate(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor,
) -> None:
    """
    Demonstrates the full activate-then-terminate embargo management cycle.

    Steps:
    1. Setup: initialize case with two participants (vendor + coordinator)
    2. Coordinator proposes embargo (EmProposeEmbargo → vendor inbox)
    3. Vendor accepts embargo (EmAcceptEmbargo → coordinator inbox)
    4. Vendor activates embargo on case (ActivateEmbargo → vendor inbox)
    5. Vendor announces embargo to participants
    6. Verify case has active embargo
    7. Vendor terminates (removes) the embargo (RemoveEmbargoFromCase)
    8. Verify case has no active embargo

    This follows the activate → terminate branch in
    docs/howto/activitypub/activities/manage_embargo.md.
    """
    logger.info("=" * 80)
    logger.info("DEMO: Manage Embargo — Activate/Terminate Path")
    logger.info("=" * 80)

    case = _setup_two_participant_case(client, finder, vendor, coordinator)

    with demo_step("Step 2: Coordinator proposes embargo"):
        embargo = _make_embargo_event(case, days=90, seq=1)
        create_embargo = as_Create(
            actor=vendor.as_id,
            object=embargo,
            context=case.as_id,
        )
        post_to_inbox_and_wait(client, vendor.as_id, create_embargo)

        proposal = EmProposeEmbargo(
            id=f"{case.as_id}/embargo_proposals/activate-1",
            actor=coordinator.as_id,
            object=embargo,
            context=case.as_id,
            summary=f"Proposing a 90-day embargo for {case.name}.",
            to=[vendor.as_id],
        )
        logger.info(f"Sending embargo proposal: {logfmt(proposal)}")
        post_to_inbox_and_wait(client, vendor.as_id, proposal)

    with demo_step("Step 3: Vendor accepts embargo proposal"):
        accept = EmAcceptEmbargo(
            actor=vendor.as_id,
            object=proposal.as_id,
            context=case.as_id,
            to=[coordinator.as_id],
            summary=f"Accepting embargo proposal for {case.name}.",
        )
        logger.info(f"Sending embargo acceptance: {logfmt(accept)}")
        post_to_inbox_and_wait(client, coordinator.as_id, accept)

    with demo_step("Step 4: Vendor activates embargo on case"):
        activate = ActivateEmbargo(
            actor=vendor.as_id,
            object=embargo.as_id,
            target=case.as_id,
            in_reply_to=proposal.as_id,
            to=f"{case.as_id}/participants",
        )
        logger.info(f"Activating embargo: {logfmt(activate)}")
        post_to_inbox_and_wait(client, vendor.as_id, activate)

    with demo_step("Step 5: Vendor announces embargo to participants"):
        announce = AnnounceEmbargo(
            actor=vendor.as_id,
            object=embargo.as_id,
            context=case.as_id,
            to=f"{case.as_id}/participants",
            summary=f"Embargo for {case.name} is now active.",
        )
        logger.info(f"Announcing embargo: {logfmt(announce)}")
        post_to_inbox_and_wait(client, vendor.as_id, announce)

    with demo_step("Step 6: Verify case has active embargo"):
        with demo_check("Case has active_embargo set"):
            mid_case = log_case_state(
                client, case.as_id, "after embargo activation"
            )
            if mid_case is None:
                raise ValueError(
                    "Could not retrieve case after embargo activation"
                )
            if mid_case.active_embargo is None:
                raise ValueError(
                    f"Expected case '{case.as_id}' to have an active embargo, "
                    f"but active_embargo is None."
                )

    with demo_step("Step 7: Vendor terminates (removes) the active embargo"):
        remove = RemoveEmbargoFromCase(
            actor=vendor.as_id,
            object=embargo.as_id,
            origin=case.as_id,
            to=f"{case.as_id}/participants",
            summary=f"Terminating embargo for {case.name}.",
        )
        logger.info(f"Removing embargo from case: {logfmt(remove)}")
        post_to_inbox_and_wait(client, vendor.as_id, remove)

    with demo_step(
        "Step 8: Verify case has no active embargo after termination"
    ):
        with demo_check("Case active_embargo is None after termination"):
            final_case = log_case_state(
                client, case.as_id, "after embargo termination"
            )
            if final_case is None:
                raise ValueError(
                    "Could not retrieve case after embargo termination"
                )
            if final_case.active_embargo is not None:
                raise ValueError(
                    f"Expected case '{case.as_id}' to have no active embargo "
                    f"after termination, but active_embargo = "
                    f"{final_case.active_embargo}"
                )

    logger.info(
        "✅ DEMO COMPLETE (activate/terminate path): "
        "Embargo activated and terminated successfully."
    )


def demo_reject_then_repropose(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor,
) -> None:
    """
    Demonstrates the reject-then-repropose embargo management cycle.

    Steps:
    1. Setup: initialize case with two participants (vendor + coordinator)
    2. Coordinator proposes first embargo (45-day)
    3. Vendor rejects the proposal
    4. Verify case has no active embargo after rejection
    5. Coordinator proposes a revised embargo (90-day)
    6. Vendor accepts the revised proposal
    7. Vendor activates the revised embargo
    8. Verify case has active embargo

    This follows the reject → re-propose → accept branch in
    docs/howto/activitypub/activities/manage_embargo.md.
    """
    logger.info("=" * 80)
    logger.info("DEMO: Manage Embargo — Reject/Repropose Path")
    logger.info("=" * 80)

    case = _setup_two_participant_case(client, finder, vendor, coordinator)

    with demo_step("Step 2: Coordinator proposes first embargo (45-day)"):
        embargo_v1 = _make_embargo_event(case, days=45, seq=1)
        create_embargo_v1 = as_Create(
            actor=vendor.as_id,
            object=embargo_v1,
            context=case.as_id,
        )
        post_to_inbox_and_wait(client, vendor.as_id, create_embargo_v1)

        proposal_v1 = EmProposeEmbargo(
            id=f"{case.as_id}/embargo_proposals/reject-1",
            actor=coordinator.as_id,
            object=embargo_v1,
            context=case.as_id,
            summary=f"Proposing a 45-day embargo for {case.name}.",
            to=[vendor.as_id],
        )
        logger.info(f"Sending first embargo proposal: {logfmt(proposal_v1)}")
        post_to_inbox_and_wait(client, vendor.as_id, proposal_v1)

    with demo_step("Step 3: Vendor rejects first embargo proposal"):
        reject = EmRejectEmbargo(
            actor=vendor.as_id,
            object=proposal_v1.as_id,
            context=case.as_id,
            to=[coordinator.as_id],
            summary=(
                f"Rejecting 45-day embargo for {case.name}; "
                f"need more time."
            ),
        )
        logger.info(f"Sending embargo rejection: {logfmt(reject)}")
        post_to_inbox_and_wait(client, coordinator.as_id, reject)

    with demo_step(
        "Step 4: Verify case has no active embargo after rejection"
    ):
        with demo_check("Case active_embargo is None after rejection"):
            mid_case = log_case_state(
                client, case.as_id, "after first embargo rejection"
            )
            if mid_case is None:
                raise ValueError(
                    "Could not retrieve case after embargo rejection"
                )
            if mid_case.active_embargo is not None:
                raise ValueError(
                    f"Expected case '{case.as_id}' to have no active embargo "
                    f"after rejection, but active_embargo = "
                    f"{mid_case.active_embargo}"
                )

    with demo_step("Step 5: Coordinator proposes revised embargo (90-day)"):
        embargo_v2 = _make_embargo_event(case, days=90, seq=2)
        create_embargo_v2 = as_Create(
            actor=vendor.as_id,
            object=embargo_v2,
            context=case.as_id,
        )
        post_to_inbox_and_wait(client, vendor.as_id, create_embargo_v2)

        proposal_v2 = EmProposeEmbargo(
            id=f"{case.as_id}/embargo_proposals/reject-2",
            actor=coordinator.as_id,
            object=embargo_v2,
            context=case.as_id,
            summary=f"Re-proposing a 90-day embargo for {case.name}.",
            to=[vendor.as_id],
        )
        logger.info(f"Sending revised embargo proposal: {logfmt(proposal_v2)}")
        post_to_inbox_and_wait(client, vendor.as_id, proposal_v2)

    with demo_step("Step 6: Vendor accepts revised embargo proposal"):
        accept_v2 = EmAcceptEmbargo(
            actor=vendor.as_id,
            object=proposal_v2.as_id,
            context=case.as_id,
            to=[coordinator.as_id],
            summary=f"Accepting revised 90-day embargo for {case.name}.",
        )
        logger.info(f"Sending embargo acceptance: {logfmt(accept_v2)}")
        post_to_inbox_and_wait(client, coordinator.as_id, accept_v2)

    with demo_step("Step 7: Vendor activates revised embargo"):
        activate_v2 = ActivateEmbargo(
            actor=vendor.as_id,
            object=embargo_v2.as_id,
            target=case.as_id,
            in_reply_to=proposal_v2.as_id,
            to=f"{case.as_id}/participants",
        )
        logger.info(f"Activating revised embargo: {logfmt(activate_v2)}")
        post_to_inbox_and_wait(client, vendor.as_id, activate_v2)

    with demo_step("Step 8: Verify case has active revised embargo"):
        with demo_check("Case has active_embargo set after re-proposal"):
            final_case = log_case_state(
                client, case.as_id, "after revised embargo activation"
            )
            if final_case is None:
                raise ValueError(
                    "Could not retrieve case after revised embargo activation"
                )
            if final_case.active_embargo is None:
                raise ValueError(
                    f"Expected case '{case.as_id}' to have an active embargo "
                    f"after re-proposal and acceptance, but active_embargo is None."
                )

    logger.info(
        "✅ DEMO COMPLETE (reject/repropose path): "
        "Revised embargo accepted and activated successfully."
    )


_ALL_DEMOS: Sequence[Tuple[str, object]] = [
    (
        "Demo: Manage Embargo — Activate/Terminate Path",
        demo_activate_then_terminate,
    ),
    (
        "Demo: Manage Embargo — Reject/Repropose Path",
        demo_reject_then_repropose,
    ),
]


def main(
    skip_health_check: bool = False,
    demos: Optional[Sequence] = None,
) -> None:
    """
    Main entry point for the manage_embargo demo script.

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
