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
from typing import Callable, Optional, Sequence, Tuple

from vultron.core.states.em import is_em_embargo_active
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Create
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.demo.helpers.embargo import make_embargo_event
from vultron.demo.helpers.runner import run_exchange_demos
from vultron.demo.helpers.workflow import setup_two_participant_case
from vultron.demo.utils import (  # noqa: F401 — BASE_URL needed for test monkeypatching
    BASE_URL,
    DataLayerClient,
    demo_check,
    demo_step,
    log_case_state,
    logfmt,
    post_to_inbox_and_wait,
    setup_demo_logging,
)
from vultron.wire.as2.factories import (
    activate_embargo_activity,
    announce_embargo_activity,
    em_accept_embargo_activity,
    em_propose_embargo_activity,
    em_reject_embargo_activity,
)

logger = logging.getLogger(__name__)


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

    case = setup_two_participant_case(client, finder, vendor, coordinator)

    with demo_step("Step 2: Coordinator proposes embargo"):
        embargo = make_embargo_event(case, days=90)
        create_embargo = as_Create(
            actor=vendor.id_,
            object_=embargo,
            context=case.id_,
        )
        post_to_inbox_and_wait(client, vendor.id_, create_embargo)

        proposal = em_propose_embargo_activity(
            embargo,
            id_=f"{case.id_}/embargo_proposals/1",
            actor=coordinator.id_,
            context=case.id_,
            summary=f"Proposing a 90-day embargo for {case.name}.",
            to=[vendor.id_],
        )
        logger.info(f"Sending embargo proposal: {logfmt(proposal)}")
        post_to_inbox_and_wait(client, vendor.id_, proposal)

    with demo_step("Step 3: Vendor accepts embargo and activates it"):
        accept = em_accept_embargo_activity(
            proposal,
            actor=vendor.id_,
            context=case.id_,
            to=[coordinator.id_],
            summary=f"Accepting embargo proposal for {case.name}.",
        )
        logger.info(f"Sending embargo acceptance: {logfmt(accept)}")
        post_to_inbox_and_wait(client, coordinator.id_, accept)

        activate = activate_embargo_activity(
            embargo,
            actor=vendor.id_,
            target=case.id_,
            in_reply_to=proposal.id_,
            to=f"{case.id_}/participants",
        )
        logger.info(f"Activating embargo: {logfmt(activate)}")
        post_to_inbox_and_wait(client, vendor.id_, activate)

    with demo_step("Step 4: Vendor announces embargo to participants"):
        announce = announce_embargo_activity(
            embargo,
            actor=vendor.id_,
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
            if not is_em_embargo_active(final_case.current_status.em_state):
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

    case = setup_two_participant_case(client, finder, vendor, coordinator)

    with demo_step("Step 2: Coordinator proposes embargo"):
        embargo = make_embargo_event(case, days=45)
        create_embargo = as_Create(
            actor=vendor.id_,
            object_=embargo,
            context=case.id_,
        )
        post_to_inbox_and_wait(client, vendor.id_, create_embargo)

        proposal = em_propose_embargo_activity(
            embargo,
            id_=f"{case.id_}/embargo_proposals/1",
            actor=coordinator.id_,
            context=case.id_,
            summary=f"Proposing a 45-day embargo for {case.name}.",
            to=[vendor.id_],
        )
        logger.info(f"Sending embargo proposal: {logfmt(proposal)}")
        post_to_inbox_and_wait(client, vendor.id_, proposal)

    with demo_step("Step 3: Vendor rejects embargo proposal"):
        reject = em_reject_embargo_activity(
            proposal,
            actor=vendor.id_,
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
            if is_em_embargo_active(final_case.current_status.em_state):
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
    """Main entry point for the establish_embargo demo script."""
    run_exchange_demos(
        _ALL_DEMOS, skip_health_check=skip_health_check, demos=demos
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
