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

This demo script showcases the participant initialization process:

1. Setup: Submit and validate a vulnerability report; the report-validation BT
   triggers ProposeReportCaseToActorNode, which causes the CaseActor to create
   the canonical VulnerabilityCase with vendor (CASE_OWNER), finder (reporter),
   and CaseActor (CASE_MANAGER) as initial participants.
2. Invite the Coordinator: the vendor, as Case Owner, asks the CaseActor to
   invite the coordinator, and the CaseActor sends the stub Invite
3. Coordinator Joins: the coordinator accepts, the CaseActor creates its
   CoordinatorParticipant, and the vendor's replica stores the record from
   the ledger entries the CaseActor commits for it

A participant is only ever initialized this way (ADR-0114):
``Add(CaseParticipant)`` is the Case Owner's request to reinstate a removed
participant, not a way to seat a new one (CM-31-011, ADR-0116).  Compare with
invite_actor_demo.py, which drives the same join through the triggers.

When run as a script, this module will:
1. Check if the API server is available
2. Reset the data layer to a clean state
3. Discover actors (finder, vendor, coordinator) via the API
4. Run the initialize_participant demo workflow
5. Verify side effects in the data layer
"""

# Standard library imports
import logging
from collections.abc import Callable, Sequence

from vultron.demo.helpers.polling import wait_for_case_participants
from vultron.demo.helpers.runner import run_exchange_demos
from vultron.demo.helpers.workflow import (
    seat_participant_through_stub_invite,
    setup_canonical_case,
)
from vultron.demo.utils import (  # noqa: F401 — BASE_URL needed for test monkeypatching
    BASE_URL,
    DataLayerClient,
    demo_check,
    demo_gate,
    demo_step,
    log_case_state,
    logfmt,
    post_to_inbox_and_wait,
    ref_id,
    setup_demo_logging,
    verify_object_stored,
)
from vultron.enums.roles import CVDRole

# Vultron imports
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

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
    2. The vendor asks the CaseActor to invite the coordinator, and the
       coordinator accepts; the CaseActor creates its participant record
    3. Verify the vendor's replica holds the coordinator from the ledger
       entries alone (CM-31-012)
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
            "Initial participant count: %s",
            len(initial_case.case_participants),
        )

    initial_count = len(initial_case.case_participants) if initial_case else 0

    with demo_step("Step 1: Coordinator joins through the stub Invite"):
        seat_participant_through_stub_invite(
            client,
            case,
            owner=vendor,
            invitee=coordinator,
            role=CVDRole.COORDINATOR,
        )

    with demo_step(
        "Step 2: Vendor's replica seats the coordinator from the ledger"
    ):
        # No Add(CaseParticipant) follows the acceptance (CM-31-012): the
        # vendor's replica stores the new member's record from the
        # create_case_participant entry and the Accept(Invite) entry the
        # CaseActor fans out to it (ADR-0114).
        with demo_gate("Coordinator is a participant on the vendor's replica"):
            wait_for_case_participants(
                vendor_client=client,
                case_id=case.id_,
                expected_actor_ids={coordinator.id_},
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
            "Final participant count: %s ✓ (initial %s + coordinator)",
            participant_count,
            initial_count,
        )

    logger.info("✅ DEMO COMPLETE: Coordinator added as participant to case.")


_ALL_DEMOS: Sequence[tuple[str, Callable[..., None]]] = [
    ("Demo: Initialize Case Participant", demo_initialize_participant),
]


def main(
    skip_health_check: bool = False,
    demos: Sequence | None = None,
) -> None:
    """Main entry point for the initialize participant demo demo script."""
    run_exchange_demos(
        _ALL_DEMOS, skip_health_check=skip_health_check, demos=demos
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
