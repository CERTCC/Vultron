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
from typing import Callable, Optional, Sequence, Tuple

# Vultron imports
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.demo.helpers.runner import run_exchange_demos
from vultron.demo.helpers.workflow import setup_initialized_case
from vultron.demo.utils import (  # noqa: F401 — BASE_URL needed for test monkeypatching
    BASE_URL,
    DataLayerClient,
    demo_check,
    demo_step,
    log_case_state,
    logfmt,
    post_to_inbox_and_wait,
    ref_id,
    setup_demo_logging,
)
from vultron.wire.as2.factories import (
    rm_accept_invite_to_case_activity,
    rm_invite_to_case_activity,
    rm_reject_invite_to_case_activity,
)

logger = logging.getLogger(__name__)


def _get_case_actor_id(client: DataLayerClient, case_id: str) -> str | None:
    """Return the Case Actor Service ID for *case_id* by querying the actor list.

    The Case Actor Service is stored in the DataLayer with ``context`` equal to
    the case ID.  Returns ``None`` when no matching Service is found.
    """
    actors = client.get("/actors/")
    if not isinstance(actors, list):
        return None
    for actor in actors:
        if actor.get("type") == "Service" and actor.get("context") == case_id:
            return actor.get("id")
    return None


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

    case = setup_initialized_case(client, finder, vendor)

    # PCR-08-007: the invite MUST be sent from the Case Actor's identity.
    # The Case Actor is registered as a Service in the DataLayer after case creation.
    case_actor_id = _get_case_actor_id(client, case.id_)
    invite_actor_id = case_actor_id if case_actor_id else vendor.id_

    with demo_step("Step 2: Vendor invites coordinator to case"):
        invite = rm_invite_to_case_activity(
            coordinator,
            actor=invite_actor_id,
            target=case.id_,
            to=[coordinator.id_],
            attributed_to=vendor.id_ if case_actor_id else None,
            content=f"We're inviting you to participate in {case.name}.",
        )
        logger.info(f"Sending invite: {logfmt(invite)}")
        post_to_inbox_and_wait(client, coordinator.id_, invite)

    with demo_step("Step 3: Coordinator accepts invitation"):
        # PCR-08-008: Accept must be addressed to the Case Actor inbox.
        # The invite's actor field carries the Case Actor ID.
        accept_recipient = invite_actor_id
        accept = rm_accept_invite_to_case_activity(
            invite,
            actor=coordinator.id_,
            to=[accept_recipient],
            content=f"Accepting invitation to participate in {case.name}.",
        )
        logger.info(f"Sending accept: {logfmt(accept)}")
        post_to_inbox_and_wait(client, accept_recipient, accept)

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

    case = setup_initialized_case(client, finder, vendor)

    initial_case = log_case_state(client, case.id_, "initial")
    initial_count = len(initial_case.case_participants) if initial_case else 0

    # PCR-08-007: the invite MUST be sent from the Case Actor's identity.
    case_actor_id = _get_case_actor_id(client, case.id_)
    invite_actor_id = case_actor_id if case_actor_id else vendor.id_

    with demo_step("Step 2: Vendor invites coordinator to case"):
        invite = rm_invite_to_case_activity(
            coordinator,
            actor=invite_actor_id,
            target=case.id_,
            to=[coordinator.id_],
            attributed_to=vendor.id_ if case_actor_id else None,
            content=f"We're inviting you to participate in {case.name}.",
        )
        logger.info(f"Sending invite: {logfmt(invite)}")
        post_to_inbox_and_wait(client, coordinator.id_, invite)

    with demo_step("Step 3: Coordinator rejects invitation"):
        # PCR-08-008: Reject must also be addressed to the Case Actor inbox.
        reject_recipient = invite_actor_id
        reject = rm_reject_invite_to_case_activity(
            invite,
            actor=coordinator.id_,
            to=[reject_recipient],
            content=f"Declining the invitation to participate in {case.name}.",
        )
        logger.info(f"Sending reject: {logfmt(reject)}")
        post_to_inbox_and_wait(client, reject_recipient, reject)

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
    """Main entry point for the invite_actor demo script."""
    run_exchange_demos(
        _ALL_DEMOS, skip_health_check=skip_health_check, demos=demos
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
