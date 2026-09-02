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
Demonstrates the workflow for initializing a CaseParticipant via the Vultron API.

This demo script showcases the standalone participant initialization process:

1. Setup: Submit and validate a vulnerability report; the report-validation BT
   triggers ProposeReportCaseToActorNode, which causes the CaseActor to create
   the canonical VulnerabilityCase with vendor (CASE_OWNER), finder (reporter),
   and CaseActor (CASE_MANAGER) as initial participants.
2. Create Coordinator Participant: vendor creates a CoordinatorParticipant
3. Add Coordinator to Case: vendor adds the coordinator participant to the case

This is standalone — it does not require a prior Invite.
Compare with invite_actor_demo.py, which demonstrates the invite-based path.

When run as a script, this module will:
1. Check if the API server is available
2. Reset the data layer to a clean state
3. Discover actors (finder, vendor, coordinator) via the API
4. Run the initialize_participant demo workflow
5. Verify side effects in the data layer
"""

# Standard library imports
import logging
from typing import Callable, Optional, Sequence, Tuple

# Vultron imports
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.case_participant import (
    as_CaseParticipant,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.demo.utils import (  # noqa: F401 — BASE_URL needed for test monkeypatching
    BASE_URL,
    DataLayerClient,
    demo_check,
    demo_step,
    log_case_state,
    logfmt,
    post_to_inbox_and_wait,
    ref_id,
    verify_object_stored,
    setup_demo_logging,
)
from vultron.wire.as2.factories import (
    add_participant_to_case_activity,
    create_participant_activity,
)

from vultron.demo.helpers.runner import run_exchange_demos
from vultron.demo.helpers.workflow import setup_canonical_case

logger = logging.getLogger(__name__)


def setup_case_precondition(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
) -> as_VulnerabilityCase:
    """Set up the precondition for the demo.

    Thin wrapper over
    :func:`~vultron.demo.helpers.workflow.setup_canonical_case`, which drives
    the report → validate → ``Create(CaseProposal)`` → CaseActor path so the
    resulting case has vendor (CASE_OWNER), finder/reporter, and the CaseActor
    (CASE_MANAGER) as initial participants (ADR-0041, CP-01-004).

    Returns:
        The canonical VulnerabilityCase created by the CaseActor.
    """
    logger.info("Setting up case precondition...")
    case, _case_actor_id = setup_canonical_case(
        client,
        finder,
        vendor,
        report_name="Integer Overflow in Network Stack",
        report_content=(
            "An integer overflow vulnerability in the network stack."
        ),
        validation_content=(
            "Confirmed — integer overflow via crafted packet."
        ),
    )
    logger.info("Case precondition setup complete.")
    return case


def demo_initialize_participant(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor,
):
    """Demonstrate the standalone CaseParticipant initialization workflow.

    Precondition: A canonical VulnerabilityCase exists with vendor
    (CASE_OWNER), finder (reporter), and the CaseActor (CASE_MANAGER) as
    initial participants.  This is set up automatically by the report
    validation → ProposeReportCaseToActorNode → CaseActor flow (ADR-0041).

    Steps:
    1. Show initial case participant list
    2. Vendor creates a CoordinatorParticipant (standalone, no prior invite)
    3. Vendor adds the coordinator participant to the case
    4. Verify final participant count

    This follows the workflow in:
        docs/howto/activitypub/activities/initialize_participant.md
    """
    logger.info("=" * 80)
    logger.info("DEMO: Initialize Case Participant")
    logger.info("=" * 80)

    case = setup_case_precondition(client, finder, vendor)

    initial_case = None
    with demo_check("Initial case state"):
        initial_case = log_case_state(client, case.id_, "initial")
        if initial_case is None:
            raise ValueError("Could not fetch initial case state")
        logger.info(
            f"Initial participant count: {len(initial_case.case_participants)}"
        )

    initial_count = len(initial_case.case_participants) if initial_case else 0

    coordinator_participant = None
    with demo_step(
        "Step 1: Vendor creates coordinator participant (standalone)"
    ):
        coordinator_participant = as_CaseParticipant(
            case_roles=[CVDRole.COORDINATOR],
            attributed_to=coordinator.id_,
            context=case.id_,
        )
        logger.info(
            f"Created coordinator participant: {logfmt(coordinator_participant)}"
        )
        create_coordinator_participant = create_participant_activity(
            coordinator_participant, actor=vendor.id_, context=case.id_
        )
        post_to_inbox_and_wait(
            client, vendor.id_, create_coordinator_participant
        )
        with demo_check("Coordinator participant stored in data layer"):
            verify_object_stored(client, coordinator_participant.id_)

    with demo_step("Step 2: Vendor adds coordinator participant to case"):
        add_coordinator_participant = add_participant_to_case_activity(
            coordinator_participant, actor=vendor.id_, target=case.id_
        )
        post_to_inbox_and_wait(client, vendor.id_, add_coordinator_participant)
        with demo_check("Coordinator participant added to case"):
            updated_case = log_case_state(
                client,
                case.id_,
                "after coordinator AddParticipantToCaseActivity",
            )
            if updated_case and coordinator_participant.id_ not in [
                (ref_id(p) or str(p)) for p in updated_case.case_participants
            ]:
                raise ValueError(
                    f"Coordinator participant '{coordinator_participant.id_}'"
                    " not found in case after AddParticipantToCaseActivity"
                )
        logger.info("Coordinator added as participant to case")

    expected_count = initial_count + 1
    with demo_check(f"Final case has {expected_count} participants"):
        final_case = log_case_state(client, case.id_, "final")
        if final_case is None:
            raise ValueError("Could not fetch final case state")
        participant_count = len(final_case.case_participants)
        if participant_count != expected_count:
            raise ValueError(
                f"Expected {expected_count} participants"
                f" (initial {initial_count} + coordinator),"
                f" got {participant_count}"
            )
        logger.info(
            f"Final participant count: {participant_count} ✓"
            f" (initial {initial_count} + coordinator)"
        )

    logger.info("✅ DEMO COMPLETE: Coordinator added as participant to case.")


_ALL_DEMOS: Sequence[Tuple[str, Callable[..., None]]] = [
    ("Demo: Initialize Case Participant", demo_initialize_participant),
]


def main(
    skip_health_check: bool = False,
    demos: Optional[Sequence] = None,
) -> None:
    """Main entry point for the initialize participant demo demo script."""
    run_exchange_demos(
        _ALL_DEMOS, skip_health_check=skip_health_check, demos=demos
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
