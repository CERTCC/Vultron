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
    remove_embargo_from_case_activity,
)

logger = logging.getLogger(__name__)


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
    2. Coordinator proposes embargo (EmProposeEmbargoActivity → vendor inbox)
    3. Vendor accepts embargo (EmAcceptEmbargoActivity → coordinator inbox)
    4. Vendor activates embargo on case (ActivateEmbargoActivity → vendor inbox)
    5. Vendor announces embargo to participants
    6. Verify case has active embargo
    7. Vendor terminates (removes) the embargo (RemoveEmbargoFromCaseActivity)
    8. Verify case has no active embargo

    This follows the activate → terminate branch in
    docs/howto/activitypub/activities/manage_embargo.md.
    """
    logger.info("=" * 80)
    logger.info("DEMO: Manage Embargo — Activate/Terminate Path")
    logger.info("=" * 80)

    case = setup_two_participant_case(client, finder, vendor, coordinator)

    with demo_step("Step 2: Coordinator proposes embargo"):
        embargo = make_embargo_event(case, days=90, seq=1)
        create_embargo = as_Create(
            actor=vendor.id_,
            object_=embargo,
            context=case.id_,
        )
        post_to_inbox_and_wait(client, vendor.id_, create_embargo)

        proposal = em_propose_embargo_activity(
            embargo,
            id_=f"{case.id_}/embargo_proposals/activate-1",
            actor=coordinator.id_,
            context=case.id_,
            summary=f"Proposing a 90-day embargo for {case.name}.",
            to=[vendor.id_],
        )
        logger.info(f"Sending embargo proposal: {logfmt(proposal)}")
        post_to_inbox_and_wait(client, vendor.id_, proposal)

    with demo_step("Step 3: Vendor accepts embargo proposal"):
        accept = em_accept_embargo_activity(
            proposal,
            actor=vendor.id_,
            context=case.id_,
            to=[coordinator.id_],
            summary=f"Accepting embargo proposal for {case.name}.",
        )
        logger.info(f"Sending embargo acceptance: {logfmt(accept)}")
        post_to_inbox_and_wait(client, coordinator.id_, accept)

    with demo_step("Step 4: Vendor activates embargo on case"):
        activate = activate_embargo_activity(
            embargo,
            actor=vendor.id_,
            target=case.id_,
            in_reply_to=proposal.id_,
            to=f"{case.id_}/participants",
        )
        logger.info(f"Activating embargo: {logfmt(activate)}")
        post_to_inbox_and_wait(client, vendor.id_, activate)

    with demo_step("Step 5: Vendor announces embargo to participants"):
        announce = announce_embargo_activity(
            embargo,
            actor=vendor.id_,
            context=case.id_,
            to=f"{case.id_}/participants",
            summary=f"Embargo for {case.name} is now active.",
        )
        logger.info(f"Announcing embargo: {logfmt(announce)}")
        post_to_inbox_and_wait(client, vendor.id_, announce)

    with demo_step("Step 6: Verify case has active embargo"):
        with demo_check("Case has active_embargo set"):
            mid_case = log_case_state(
                client, case.id_, "after embargo activation"
            )
            if mid_case is None:
                raise ValueError(
                    "Could not retrieve case after embargo activation"
                )
            if not is_em_embargo_active(mid_case.current_status.em_state):
                raise ValueError(
                    f"Expected case '{case.id_}' to have an active embargo, "
                    f"but active_embargo is None."
                )

    with demo_step("Step 7: Vendor terminates (removes) the active embargo"):
        remove = remove_embargo_from_case_activity(
            embargo,
            actor=vendor.id_,
            origin=case.id_,
            to=f"{case.id_}/participants",
            summary=f"Terminating embargo for {case.name}.",
        )
        logger.info(f"Removing embargo from case: {logfmt(remove)}")
        post_to_inbox_and_wait(client, vendor.id_, remove)

    with demo_step(
        "Step 8: Verify case has no active embargo after termination"
    ):
        with demo_check("Case active_embargo is None after termination"):
            final_case = log_case_state(
                client, case.id_, "after embargo termination"
            )
            if final_case is None:
                raise ValueError(
                    "Could not retrieve case after embargo termination"
                )
            if is_em_embargo_active(final_case.current_status.em_state):
                raise ValueError(
                    f"Expected case '{case.id_}' to have no active embargo "
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

    case = setup_two_participant_case(client, finder, vendor, coordinator)

    with demo_step("Step 2: Coordinator proposes first embargo (45-day)"):
        embargo_v1 = make_embargo_event(case, days=45, seq=1)
        create_embargo_v1 = as_Create(
            actor=vendor.id_,
            object_=embargo_v1,
            context=case.id_,
        )
        post_to_inbox_and_wait(client, vendor.id_, create_embargo_v1)

        proposal_v1 = em_propose_embargo_activity(
            embargo_v1,
            id_=f"{case.id_}/embargo_proposals/reject-1",
            actor=coordinator.id_,
            context=case.id_,
            summary=f"Proposing a 45-day embargo for {case.name}.",
            to=[vendor.id_],
        )
        logger.info(f"Sending first embargo proposal: {logfmt(proposal_v1)}")
        post_to_inbox_and_wait(client, vendor.id_, proposal_v1)

    with demo_step("Step 3: Vendor rejects first embargo proposal"):
        reject = em_reject_embargo_activity(
            proposal_v1,
            actor=vendor.id_,
            context=case.id_,
            to=[coordinator.id_],
            summary=(
                f"Rejecting 45-day embargo for {case.name}; "
                f"need more time."
            ),
        )
        logger.info(f"Sending embargo rejection: {logfmt(reject)}")
        post_to_inbox_and_wait(client, coordinator.id_, reject)

    with demo_step(
        "Step 4: Verify case has no active embargo after rejection"
    ):
        with demo_check("Case active_embargo is None after rejection"):
            mid_case = log_case_state(
                client, case.id_, "after first embargo rejection"
            )
            if mid_case is None:
                raise ValueError(
                    "Could not retrieve case after embargo rejection"
                )
            if is_em_embargo_active(mid_case.current_status.em_state):
                raise ValueError(
                    f"Expected case '{case.id_}' to have no active embargo "
                    f"after rejection, but active_embargo = "
                    f"{mid_case.active_embargo}"
                )

    with demo_step("Step 5: Coordinator proposes revised embargo (90-day)"):
        embargo_v2 = make_embargo_event(case, days=90, seq=2)
        create_embargo_v2 = as_Create(
            actor=vendor.id_,
            object_=embargo_v2,
            context=case.id_,
        )
        post_to_inbox_and_wait(client, vendor.id_, create_embargo_v2)

        proposal_v2 = em_propose_embargo_activity(
            embargo_v2,
            id_=f"{case.id_}/embargo_proposals/reject-2",
            actor=coordinator.id_,
            context=case.id_,
            summary=f"Re-proposing a 90-day embargo for {case.name}.",
            to=[vendor.id_],
        )
        logger.info(f"Sending revised embargo proposal: {logfmt(proposal_v2)}")
        post_to_inbox_and_wait(client, vendor.id_, proposal_v2)

    with demo_step("Step 6: Vendor accepts revised embargo proposal"):
        accept_v2 = em_accept_embargo_activity(
            proposal_v2,
            actor=vendor.id_,
            context=case.id_,
            to=[coordinator.id_],
            summary=f"Accepting revised 90-day embargo for {case.name}.",
        )
        logger.info(f"Sending embargo acceptance: {logfmt(accept_v2)}")
        post_to_inbox_and_wait(client, coordinator.id_, accept_v2)

    with demo_step("Step 7: Vendor activates revised embargo"):
        activate_v2 = activate_embargo_activity(
            embargo_v2,
            actor=vendor.id_,
            target=case.id_,
            in_reply_to=proposal_v2.id_,
            to=f"{case.id_}/participants",
        )
        logger.info(f"Activating revised embargo: {logfmt(activate_v2)}")
        post_to_inbox_and_wait(client, vendor.id_, activate_v2)

    with demo_step("Step 8: Verify case has active revised embargo"):
        with demo_check("Case has active_embargo set after re-proposal"):
            final_case = log_case_state(
                client, case.id_, "after revised embargo activation"
            )
            if final_case is None:
                raise ValueError(
                    "Could not retrieve case after revised embargo activation"
                )
            if not is_em_embargo_active(final_case.current_status.em_state):
                raise ValueError(
                    f"Expected case '{case.id_}' to have an active embargo "
                    f"after re-proposal and acceptance, but active_embargo is None."
                )

    logger.info(
        "✅ DEMO COMPLETE (reject/repropose path): "
        "Revised embargo accepted and activated successfully."
    )


_ALL_DEMOS: Sequence[Tuple[str, Callable[..., None]]] = [
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
    """Main entry point for the manage_embargo demo script."""
    run_exchange_demos(
        _ALL_DEMOS, skip_health_check=skip_health_check, demos=demos
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
