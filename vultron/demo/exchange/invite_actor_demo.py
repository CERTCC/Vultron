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
from collections.abc import Callable, Sequence

from vultron.core.states.rm import RM
from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers.runner import run_exchange_demos
from vultron.demo.helpers.verification import _check_participant_rm_state_in
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
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import (
    rm_accept_invite_to_case_activity,
    rm_invite_to_case_activity,
    rm_reject_invite_to_case_activity,
)

# Vultron imports
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.case_participant import (
    as_CaseParticipant,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

logger = logging.getLogger(__name__)


def _find_case_manager_actor(
    client: DataLayerClient, vendor_id: str, case_id: str
) -> str | None:
    """Return the CASE_MANAGER actor ID by reading the case participant roster (ADR-0088).

    Authority is the ``CVDRole.CASE_MANAGER`` role — hosting location is not
    consulted (ARCH-24-004, CM-02-013).
    """
    try:
        case_data = client.get(client.dl_path(case_id, actor_id=vendor_id))
        case_obj = as_VulnerabilityCase(**case_data)
    except Exception:  # noqa: BLE001  # ruff-baseline #3326
        return None

    for p_ref in case_obj.case_participants:
        pid = ref_id(p_ref) or str(p_ref)
        if not pid:
            continue
        try:
            p_data = client.get(client.dl_path(pid, actor_id=vendor_id))
            p = as_CaseParticipant(**p_data)
            if CVDRole.CASE_MANAGER in p.case_roles:
                attr = p.attributed_to
                return (
                    attr
                    if isinstance(attr, str)
                    else getattr(attr, "id_", None)
                )
        except Exception:  # noqa: BLE001, S112  # ruff-baseline #3326
            continue
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

    # PCR-08-007: the invite MUST be sent from the CASE_MANAGER's identity (ADR-0088).
    invite_actor_id = _find_case_manager_actor(client, vendor.id_, case.id_)
    if invite_actor_id is None:
        raise ValueError(
            f"No CASE_MANAGER participant found for case '{case.id_}' (CM-02-014, CM-02-015)"
        )

    invite = None
    with demo_step("Step 2: Vendor invites coordinator to case"):
        invite = rm_invite_to_case_activity(
            coordinator,
            actor=invite_actor_id,
            target=case.id_,
            to=[coordinator.id_],
            attributed_to=vendor.id_,
            roles=[CVDRole.COORDINATOR],
            content=f"We're inviting you to participate in {case.name}.",
        )
        logger.info("Sending invite: %s", logfmt(invite))
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
        logger.info("Sending accept: %s", logfmt(accept))
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
    """Reject path of the invite-actor-to-case workflow.

    ADR-0114 / CM-11-006: the invite-actor-to-case trigger is called first so
    that ``CreateInertInviteeParticipantNode`` records an inert
    ``CaseParticipant`` for coordinator at invite-send time.  The invite
    activity is then also posted to coordinator's inbox directly (exchange-demo
    pattern) so coordinator can reject it.  After the Reject,
    ``ApplyInviteRejectToParticipantNode`` closes the inert record at
    RM ``CLOSED`` (CM-11-007) — coordinator is present in
    ``actor_participant_index`` but never active (DEMOMA-27-002).

    Steps:
    1. Setup: initialize case (report submitted + validated, case created,
       finder participant added)
    2. Vendor fires invite-actor-to-case trigger (creates inert participant,
       CM-11-006) and delivers the invite to coordinator's inbox
    3. Coordinator rejects invitation (RmRejectInviteToCaseActivity → vendor inbox)
    4. Verify coordinator is in actor_participant_index at RM.CLOSED (never active)

    This follows the reject branch in
    docs/howto/activitypub/activities/invite_actor.md.
    """
    logger.info("=" * 80)
    logger.info("DEMO: Invite Actor — Reject Path")
    logger.info("=" * 80)

    case = setup_initialized_case(client, finder, vendor)

    # PCR-08-007: the invite MUST be sent from the CASE_MANAGER's identity (ADR-0088).
    invite_actor_id = _find_case_manager_actor(client, vendor.id_, case.id_)
    if invite_actor_id is None:
        raise ValueError(
            f"No CASE_MANAGER participant found for case '{case.id_}' (CM-02-014, CM-02-015)"
        )

    invite = None
    with demo_step(
        "Step 2: Vendor fires invite-actor-to-case trigger and delivers invite"
    ):
        # Fire the trigger so CreateInertInviteeParticipantNode records the inert
        # participant on the CASE_MANAGER side at invite-send time (ADR-0114,
        # CM-11-006).
        ActorSession(client=client, actor=vendor).with_case(
            case
        ).quiet().invite_actor_to_case(
            invitee_id=str(coordinator.id_), roles=[CVDRole.COORDINATOR]
        )
        # Also post the invite directly to coordinator's inbox (exchange-demo
        # delivery pattern) so coordinator has an invite to reject in Step 3.
        invite = rm_invite_to_case_activity(
            coordinator,
            actor=invite_actor_id,
            target=case.id_,
            to=[coordinator.id_],
            attributed_to=vendor.id_,
            roles=[CVDRole.COORDINATOR],
            content=f"We're inviting you to participate in {case.name}.",
        )
        logger.info("Sending invite: %s", logfmt(invite))
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
        logger.info("Sending reject: %s", logfmt(reject))
        post_to_inbox_and_wait(client, reject_recipient, reject)

    with demo_step(
        "Step 4: Verify coordinator in actor_participant_index at RM.CLOSED"
    ):
        with demo_check(
            "Coordinator present in actor_participant_index (inert record from"
            " invite-send, CM-11-006)"
        ):
            final_case = log_case_state(client, case.id_, "after reject")
            if final_case is None:
                raise ValueError("Could not retrieve case after reject")
            if coordinator.id_ not in final_case.actor_participant_index:
                raise ValueError(
                    f"Coordinator '{coordinator.id_}' missing from"
                    f" actor_participant_index — expected inert record from"
                    f" invite-send (ADR-0114, CM-11-006)"
                )
        with demo_check(
            "Coordinator at RM.CLOSED after rejection (never active, DEMOMA-27-002)"
        ):
            _check_participant_rm_state_in(
                client=client,
                case_id=str(case.id_),
                actor_id=str(coordinator.id_),
                expected_states={RM.CLOSED},
                label="Coordinator (rejected invitee)",
            )

    logger.info(
        "✅ DEMO COMPLETE (reject path): Coordinator at RM.CLOSED, never active."
    )


_ALL_DEMOS: Sequence[tuple[str, Callable[..., None]]] = [
    ("Demo: Invite Actor — Accept Path", demo_invite_actor_accept),
    ("Demo: Invite Actor — Reject Path", demo_invite_actor_reject),
]


def main(
    skip_health_check: bool = False,
    demos: Sequence | None = None,
) -> None:
    """Main entry point for the invite_actor demo script."""
    run_exchange_demos(
        _ALL_DEMOS, skip_health_check=skip_health_check, demos=demos
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
