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
Demonstrates the workflow for establishing an embargo via the Vultron API.

This demo script showcases two embargo paths:

1. Accept path: participant proposes embargo → case owner accepts →
   embargo is activated on the case (EM state = ACTIVE)
2. Reject path: participant proposes embargo → case owner rejects →
   embargo is not activated (EM state unchanged)

Each demo starts from an initialized case with two participants so the
embargo negotiation workflow can be demonstrated in isolation.

This corresponds to the workflow documented in:
    docs/howto/activitypub/activities/establish_embargo.md

When run as a script, this module will:
1. Check if the API server is available
2. Reset the data layer to a clean state
3. Discover actors (finder, vendor, coordinator) via the API
4. Run both demo workflows (propose-accept and propose-reject)
5. Verify side effects in the data layer

Note on direct inbox communication:
This demo uses direct inbox-to-inbox communication between actors, per the
Vultron prototype design. Actors post activities directly to each other's
inboxes.
"""

import logging
import sys
from datetime import datetime, timedelta
from typing import Callable, Optional, Sequence, Tuple

from vultron.wire.as2.vocab.activities.case import (
    AddReportToCaseActivity,
    CreateCaseActivity,
    RmAcceptInviteToCaseActivity,
    RmInviteToCaseActivity,
)
from vultron.wire.as2.vocab.activities.case_participant import (
    AddParticipantToCaseActivity,
)
from vultron.wire.as2.vocab.activities.embargo import (
    ActivateEmbargoActivity,
    AnnounceEmbargoActivity,
    EmAcceptEmbargoActivity,
    EmProposeEmbargoActivity,
    EmRejectEmbargoActivity,
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
from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
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
    log_case_state,
    logfmt,
    demo_environment,
    post_to_inbox_and_wait,
    verify_object_stored,
)

logger = logging.getLogger(__name__)


def _make_embargo_event(
    case: VulnerabilityCase, days: int = 90
) -> EmbargoEvent:
    """Create a deterministic EmbargoEvent for a given case."""
    now = datetime.now().astimezone()
    now = now.replace(second=0, microsecond=0)
    end_at = (now + timedelta(days=days)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    # Use a URL-safe date string (no colons) for the ID path segment
    end_date_str = end_at.strftime("%Y-%m-%d")
    return EmbargoEvent(
        id_=f"{case.id_}/embargo_events/{days}d-{end_date_str}",
        name=f"Embargo for {case.name}",
        context=case.id_,
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
    precondition for the embargo workflow.

    Steps:
    1. Finder submits report to vendor
    2. Vendor validates report
    3. Vendor creates case
    4. Vendor adds report to case
    5. Vendor adds finder as FinderReporter participant
    6. Vendor invites coordinator; coordinator accepts → coordinator added
    """
    report = VulnerabilityReport(
        attributed_to=finder.id_,
        content="A use-after-free vulnerability in the network stack.",
        name="Use-After-Free in Network Stack",
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
        object_=offer.id_,
        content="Confirmed — use-after-free via unsanitized network input.",
    )
    post_to_inbox_and_wait(client, vendor.id_, validate_activity)

    case = VulnerabilityCase(
        attributed_to=vendor.id_,
        name="UAF Case — Network Stack",
        content="Tracking the use-after-free vulnerability in the network stack.",
    )
    create_case_activity = CreateCaseActivity(
        actor=vendor.id_,
        object_=case,
    )
    post_to_inbox_and_wait(client, vendor.id_, create_case_activity)
    verify_object_stored(client, case.id_)

    add_report_activity = AddReportToCaseActivity(
        actor=vendor.id_,
        object_=report.id_,
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
        object_=participant.id_,
        target=case.id_,
    )
    post_to_inbox_and_wait(client, vendor.id_, add_participant_activity)

    # Invite coordinator and have them accept
    invite = RmInviteToCaseActivity(
        actor=vendor.id_,
        object_=coordinator.id_,
        target=case.id_,
        to=[coordinator.id_],
        content=f"Inviting you to participate in {case.name}.",
    )
    post_to_inbox_and_wait(client, coordinator.id_, invite)

    accept = RmAcceptInviteToCaseActivity(
        actor=coordinator.id_,
        object_=invite.id_,
        to=[vendor.id_],
        content=f"Accepting invitation to {case.name}.",
    )
    post_to_inbox_and_wait(client, vendor.id_, accept)

    log_case_state(client, case.id_, "after setup (two participants)")
    logger.info(
        "✓ Setup: Case initialized with vendor and coordinator participants"
    )
    return case


def demo_propose_embargo_accept(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor,
) -> None:
    """
    Demonstrates the accept path of the propose-embargo workflow.

    Steps:
    1. Setup: initialize case with two participants (vendor + coordinator)
    2. Coordinator proposes embargo (EmProposeEmbargoActivity → vendor inbox)
    3. Vendor accepts embargo (EmAcceptEmbargoActivity → coordinator inbox, then
       vendor activates via ActivateEmbargoActivity → vendor's own processing)
    4. Vendor announces embargo to all participants
    5. Verify case has ACTIVE embargo

    This follows the accept branch in
    docs/howto/activitypub/activities/establish_embargo.md.
    """
    logger.info("=" * 80)
    logger.info("DEMO: Establish Embargo — Propose/Accept Path")
    logger.info("=" * 80)

    case = _setup_two_participant_case(client, finder, vendor, coordinator)

    with demo_step("Step 2: Coordinator proposes embargo"):
        embargo = _make_embargo_event(case, days=90)
        create_embargo = as_Create(
            actor=vendor.id_,
            object_=embargo,
            context=case.id_,
        )
        post_to_inbox_and_wait(client, vendor.id_, create_embargo)

        proposal = EmProposeEmbargoActivity(
            id_=f"{case.id_}/embargo_proposals/1",
            actor=coordinator.id_,
            object_=embargo,
            context=case.id_,
            summary=f"Proposing a 90-day embargo for {case.name}.",
            to=[vendor.id_],
        )
        logger.info(f"Sending embargo proposal: {logfmt(proposal)}")
        post_to_inbox_and_wait(client, vendor.id_, proposal)

    with demo_step("Step 3: Vendor accepts embargo and activates it"):
        accept = EmAcceptEmbargoActivity(
            actor=vendor.id_,
            object_=proposal.id_,
            context=case.id_,
            to=[coordinator.id_],
            summary=f"Accepting embargo proposal for {case.name}.",
        )
        logger.info(f"Sending embargo acceptance: {logfmt(accept)}")
        post_to_inbox_and_wait(client, coordinator.id_, accept)

        activate = ActivateEmbargoActivity(
            actor=vendor.id_,
            object_=embargo.id_,
            target=case.id_,
            in_reply_to=proposal.id_,
            to=f"{case.id_}/participants",
        )
        logger.info(f"Activating embargo: {logfmt(activate)}")
        post_to_inbox_and_wait(client, vendor.id_, activate)

    with demo_step("Step 4: Vendor announces embargo to participants"):
        announce = AnnounceEmbargoActivity(
            actor=vendor.id_,
            object_=embargo.id_,
            context=case.id_,
            to=f"{case.id_}/participants",
            summary=f"Embargo for {case.name} is now active.",
        )
        logger.info(f"Announcing embargo: {logfmt(announce)}")
        post_to_inbox_and_wait(client, vendor.id_, announce)

    with demo_step("Step 5: Verify case has active embargo"):
        with demo_check("Case has active_embargo set"):
            final_case = log_case_state(
                client, case.id_, "after embargo acceptance"
            )
            if final_case is None:
                raise ValueError(
                    "Could not retrieve case after embargo acceptance"
                )
            if final_case.active_embargo is None:
                raise ValueError(
                    f"Expected case '{case.id_}' to have an active embargo after "
                    f"acceptance, but active_embargo is None. "
                    f"Case status: {final_case.current_status}"
                )

    logger.info(
        "✅ DEMO COMPLETE (accept path): Embargo established successfully."
    )


def demo_propose_embargo_reject(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor,
) -> None:
    """
    Demonstrates the reject path of the propose-embargo workflow.

    Steps:
    1. Setup: initialize case with two participants (vendor + coordinator)
    2. Coordinator proposes embargo (EmProposeEmbargoActivity → vendor inbox)
    3. Vendor rejects embargo (EmRejectEmbargoActivity → coordinator inbox)
    4. Verify case has no active embargo

    This follows the reject branch in
    docs/howto/activitypub/activities/establish_embargo.md.
    """
    logger.info("=" * 80)
    logger.info("DEMO: Establish Embargo — Propose/Reject Path")
    logger.info("=" * 80)

    case = _setup_two_participant_case(client, finder, vendor, coordinator)

    with demo_step("Step 2: Coordinator proposes embargo"):
        embargo = _make_embargo_event(case, days=45)
        create_embargo = as_Create(
            actor=vendor.id_,
            object_=embargo,
            context=case.id_,
        )
        post_to_inbox_and_wait(client, vendor.id_, create_embargo)

        proposal = EmProposeEmbargoActivity(
            id_=f"{case.id_}/embargo_proposals/1",
            actor=coordinator.id_,
            object_=embargo,
            context=case.id_,
            summary=f"Proposing a 45-day embargo for {case.name}.",
            to=[vendor.id_],
        )
        logger.info(f"Sending embargo proposal: {logfmt(proposal)}")
        post_to_inbox_and_wait(client, vendor.id_, proposal)

    with demo_step("Step 3: Vendor rejects embargo proposal"):
        reject = EmRejectEmbargoActivity(
            actor=vendor.id_,
            object_=proposal.id_,
            context=case.id_,
            to=[coordinator.id_],
            summary=f"Rejecting embargo proposal for {case.name}.",
        )
        logger.info(f"Sending embargo rejection: {logfmt(reject)}")
        post_to_inbox_and_wait(client, coordinator.id_, reject)

    with demo_step("Step 4: Verify case has no active embargo"):
        with demo_check("Case active_embargo is None after rejection"):
            final_case = log_case_state(
                client, case.id_, "after embargo rejection"
            )
            if final_case is None:
                raise ValueError(
                    "Could not retrieve case after embargo rejection"
                )
            if final_case.active_embargo is not None:
                raise ValueError(
                    f"Expected case '{case.id_}' to have no active embargo after "
                    f"rejection, but active_embargo = {final_case.active_embargo}"
                )

    logger.info("✅ DEMO COMPLETE (reject path): Embargo rejected gracefully.")


_ALL_DEMOS: Sequence[Tuple[str, Callable[..., None]]] = [
    (
        "Demo: Establish Embargo — Propose/Accept Path",
        demo_propose_embargo_accept,
    ),
    (
        "Demo: Establish Embargo — Propose/Reject Path",
        demo_propose_embargo_reject,
    ),
]


def main(
    skip_health_check: bool = False,
    demos: Optional[Sequence] = None,
) -> None:
    """
    Main entry point for the establish_embargo demo script.

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
