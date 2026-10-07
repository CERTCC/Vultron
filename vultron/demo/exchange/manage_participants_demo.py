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
   participant → vendor, as Case Owner, removes the participant from active
   participation (the record stays on the case, ADR-0116)
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
from collections.abc import Callable, Sequence

from vultron.core.models.dimensions import (
    RmDimension,
)
from vultron.core.states.rm import RM
from vultron.demo.helpers.runner import run_exchange_demos
from vultron.demo.utils import (  # noqa: F401 — BASE_URL needed for test monkeypatching
    BASE_URL,
    DataLayerClient,
    demo_check,
    demo_step,
    get_offer_from_datalayer,
    log_case_state,
    logfmt,
    post_to_inbox_and_wait,
    ref_id,
    setup_demo_logging,
    verify_object_stored,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import (
    add_participant_to_case_activity,
    add_report_to_case_activity,
    add_status_to_participant_activity,
    create_case_activity,
    create_participant_activity,
    create_status_for_participant_activity,
    remove_participant_from_case_activity,
    rm_accept_invite_to_case_activity,
    rm_invite_to_case_activity,
    rm_reject_invite_to_case_activity,
    rm_submit_report_activity,
    rm_validate_report_activity,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.case_participant import (
    as_CaseParticipant,
)
from vultron.wire.as2.vocab.objects.case_status import as_ParticipantStatus
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

logger = logging.getLogger(__name__)


def _setup_case_with_vendor(
    client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
) -> as_VulnerabilityCase:
    """
    Set up an initialized case owned by the vendor as a precondition for the
    manage-participants workflow.

    Steps:
    1. Finder submits report to vendor
    2. Vendor validates the report
    3. Vendor creates a as_VulnerabilityCase
    4. Vendor creates its participant — Vendor, Case Owner and
       CASE_MANAGER (CM-02-015) — and adds it to the case
    5. Report is linked to the case

    Returns the created as_VulnerabilityCase.
    """
    report = as_VulnerabilityReport(
        attributed_to=finder.id_,
        content="A use-after-free vulnerability in the memory allocator.",
        name="Use-After-Free in Memory Allocator",
    )
    report_offer = rm_submit_report_activity(
        report, actor=finder.id_, to=vendor.id_
    )
    post_to_inbox_and_wait(client, vendor.id_, report_offer)
    verify_object_stored(client, report.id_)

    offer = get_offer_from_datalayer(client, vendor.id_, report_offer.id_)
    validate_activity = rm_validate_report_activity(
        offer,
        actor=vendor.id_,
        content="Confirmed — use-after-free via crafted allocation sequence.",
    )
    post_to_inbox_and_wait(client, vendor.id_, validate_activity)

    case = as_VulnerabilityCase(
        attributed_to=vendor.id_,
        name="UAF Case — Memory Allocator",
        content="Tracking the use-after-free in the memory allocator.",
        stub_summary=(
            "Use-after-free in memory allocator"
            " — details shared after acceptance."
        ),
    )
    create_case_act = create_case_activity(case, actor=vendor.id_)
    post_to_inbox_and_wait(client, vendor.id_, create_case_act)
    verify_object_stored(client, case.id_)

    # The creating vendor is the case's Case Owner and CASE_MANAGER
    # (CM-02-015): a case is never without a CASE_MANAGER (CM-24-006), and
    # the removal in the accept path is the Case Owner's request to it.
    vendor_participant = as_CaseParticipant(
        case_roles=[CVDRole.VENDOR, CVDRole.CASE_OWNER, CVDRole.CASE_MANAGER],
        attributed_to=vendor.id_,
        context=case.id_,
    )
    create_vendor_participant = create_participant_activity(
        vendor_participant, actor=vendor.id_, context=case.id_
    )
    post_to_inbox_and_wait(client, vendor.id_, create_vendor_participant)

    add_vendor_participant = add_participant_to_case_activity(
        vendor_participant, actor=vendor.id_, target=case.id_
    )
    post_to_inbox_and_wait(client, vendor.id_, add_vendor_participant)

    add_report_activity = add_report_to_case_activity(
        report, actor=vendor.id_, target=case.id_
    )
    post_to_inbox_and_wait(client, vendor.id_, add_report_activity)

    log_case_state(client, case.id_, "after setup")
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
    2. Vendor invites coordinator to case (RmInviteToCaseActivity)
    3. Coordinator accepts invitation (RmAcceptInviteToCaseActivity)
    4. Vendor creates coordinator participant (CreateParticipantActivity)
    5. Vendor adds coordinator participant to case (AddParticipantToCaseActivity)
    6. Coordinator creates a as_ParticipantStatus (CreateStatusForParticipantActivity)
    7. Coordinator adds the status to their participant (AddStatusToParticipantActivity)
    8. Vendor, as Case Owner, removes the coordinator participant
       (RemoveParticipantFromCaseActivity)
    9. Verify the coordinator's record stays on the case and carries the
       removal fact (CM-31-001)

    This follows the accept branch in
    docs/howto/activitypub/activities/manage_participants.md.
    """
    logger.info("=" * 80)
    logger.info("DEMO: Manage Participants — Accept + Status + Remove Path")
    logger.info("=" * 80)

    case = _setup_case_with_vendor(client, finder, vendor)

    invite = None
    with demo_step("Step 2: Vendor invites coordinator to case"):
        invite = rm_invite_to_case_activity(
            coordinator,
            actor=vendor.id_,
            target=case,
            to=[coordinator.id_],
            content=f"Inviting you to participate in {case.name}.",
        )
        logger.info("Sending invite: %s", logfmt(invite))
        post_to_inbox_and_wait(client, coordinator.id_, invite)

    with demo_step("Step 3: Coordinator accepts invitation"):
        accept = rm_accept_invite_to_case_activity(
            invite,
            actor=coordinator.id_,
            to=[vendor.id_],
            content=f"Accepting invitation to participate in {case.name}.",
        )
        logger.info("Sending accept: %s", logfmt(accept))
        post_to_inbox_and_wait(client, vendor.id_, accept)

    coordinator_participant = None
    with demo_step("Step 4: Vendor creates coordinator participant"):
        coordinator_participant = as_CaseParticipant(
            case_roles=[CVDRole.COORDINATOR],
            attributed_to=coordinator.id_,
            context=case.id_,
        )
        create_participant = create_participant_activity(
            coordinator_participant, actor=vendor.id_, context=case.id_
        )
        post_to_inbox_and_wait(client, vendor.id_, create_participant)
        with demo_check("Coordinator participant stored in data layer"):
            verify_object_stored(client, coordinator_participant.id_)

    with demo_step("Step 5: Vendor adds coordinator participant to case"):
        add_participant = add_participant_to_case_activity(
            coordinator_participant, actor=vendor.id_, target=case.id_
        )
        post_to_inbox_and_wait(client, vendor.id_, add_participant)
        with demo_check("Coordinator in case participant list"):
            updated_case = log_case_state(
                client, case.id_, "after AddParticipantToCaseActivity"
            )
            if updated_case is None:
                raise ValueError(
                    "Could not retrieve case after add participant"
                )
            stored_id = updated_case.actor_participant_index.get(
                coordinator.id_
            )
            if not stored_id:
                raise ValueError(
                    f"Coordinator actor '{coordinator.id_}' not found"
                    " in case actor_participant_index after add."
                    f" Index: {updated_case.actor_participant_index}"
                )

    participant_status = None
    with demo_step("Step 6: Coordinator creates a as_ParticipantStatus"):
        participant_status = as_ParticipantStatus(
            context=coordinator_participant.id_,
            rm=RmDimension(state=RM.ACCEPTED),
            attributed_to=coordinator.id_,
            cvd_role=[CVDRole.COORDINATOR],
        )
        create_status = create_status_for_participant_activity(
            participant_status,
            actor=coordinator.id_,
            target=coordinator_participant.id_,
        )
        post_to_inbox_and_wait(client, coordinator.id_, create_status)
        with demo_check("as_ParticipantStatus stored in data layer"):
            # The coordinator's store: the activity was delivered to the
            # coordinator's inbox, so that is the replica holding the status.
            # The client is bound to the vendor (the recipient in most of these
            # demos), so this read has to name the actor explicitly.
            verify_object_stored(
                client, participant_status.id_, actor_id=coordinator.id_
            )

    with demo_step(
        "Step 7: Coordinator adds as_ParticipantStatus to their participant"
    ):
        add_status = add_status_to_participant_activity(
            participant_status,
            actor=coordinator.id_,
            target=coordinator_participant.id_,
        )
        post_to_inbox_and_wait(client, coordinator.id_, add_status)
        with demo_check("Case state after status update"):
            log_case_state(
                client, case.id_, "after AddStatusToParticipantActivity"
            )

    remove_participant = None
    with demo_step("Step 8: Vendor, as Case Owner, removes coordinator"):
        # The Case Owner's request to the CASE_MANAGER (CM-31-004).  The
        # vendor holds both roles here, so it posts to its own inbox.
        remove_participant = remove_participant_from_case_activity(
            coordinator_participant, actor=vendor.id_, target=case.id_
        )
        post_to_inbox_and_wait(client, vendor.id_, remove_participant)

    with demo_step("Step 9: Verify coordinator record is kept and inert"):
        with demo_check("Coordinator still on the case roster (CM-31-001)"):
            final_case = log_case_state(
                client, case.id_, "after RemoveParticipantFromCaseActivity"
            )
            if final_case is None:
                raise ValueError("Could not retrieve case after remove")
            participant_ids = [
                (ref_id(p) or str(p)) for p in final_case.case_participants
            ]
            if coordinator_participant.id_ not in participant_ids:
                raise ValueError(
                    f"Coordinator participant '{coordinator_participant.id_}'"
                    " was deleted by the removal; it must stay on the roster."
                    f" Participants: {participant_ids}"
                )
            if (
                final_case.actor_participant_index.get(coordinator.id_)
                != coordinator_participant.id_
            ):
                raise ValueError(
                    f"Coordinator actor '{coordinator.id_}' left the"
                    " actor_participant_index after removal."
                    f" Index: {final_case.actor_participant_index}"
                )
        with demo_check("Coordinator record carries the removal fact"):
            record = client.get(client.dl_path(coordinator_participant.id_))
            if record.get("removalActivity") != remove_participant.id_:
                raise ValueError(
                    f"Coordinator participant '{coordinator_participant.id_}'"
                    " does not record the removal: removalActivity="
                    f"{record.get('removalActivity')!r}, expected"
                    f" '{remove_participant.id_}'"
                )
            logger.info(
                "✓ Coordinator removed from active participation;"
                " its record stays on the case"
            )
        with demo_check("CASE_MANAGER sent the coordinator a removal notice"):
            # The vendor is the CASE_MANAGER, so its store holds the notice it
            # sent (CM-31-006); the owner's request is not the notice.
            stored = client.get(client.dl_path("Removes/")) or {}
            notices = [
                notice
                for notice in stored.values()
                if notice.get("id") != remove_participant.id_
                and ref_id(notice.get("object_"))
                == coordinator_participant.id_
                and coordinator.id_ in (notice.get("to") or [])
            ]
            if len(notices) != 1:
                raise ValueError(
                    "Expected one Remove(CaseParticipant) notice to the"
                    f" coordinator, found {len(notices)}"
                )

    logger.info(
        "✅ DEMO COMPLETE (accept path): Coordinator added, status set,"
        " then removed from active participation."
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
    2. Vendor invites coordinator to case (RmInviteToCaseActivity)
    3. Coordinator rejects invitation (RmRejectInviteToCaseActivity)
    4. Verify coordinator does NOT appear in case participant list

    This follows the reject branch in
    docs/howto/activitypub/activities/manage_participants.md.
    """
    logger.info("=" * 80)
    logger.info("DEMO: Manage Participants — Reject Path")
    logger.info("=" * 80)

    case = _setup_case_with_vendor(client, finder, vendor)

    initial_case = log_case_state(client, case.id_, "initial")
    initial_count = len(initial_case.case_participants) if initial_case else 0

    invite = None
    with demo_step("Step 2: Vendor invites coordinator to case"):
        invite = rm_invite_to_case_activity(
            coordinator,
            actor=vendor.id_,
            target=case,
            to=[coordinator.id_],
            content=f"Inviting you to participate in {case.name}.",
        )
        logger.info("Sending invite: %s", logfmt(invite))
        post_to_inbox_and_wait(client, coordinator.id_, invite)

    with demo_step("Step 3: Coordinator rejects invitation"):
        reject = rm_reject_invite_to_case_activity(
            invite,
            actor=coordinator.id_,
            to=[vendor.id_],
            content=f"Declining invitation to participate in {case.name}.",
        )
        logger.info("Sending reject: %s", logfmt(reject))
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

    logger.info(
        "✅ DEMO COMPLETE (reject path): Invitation rejected gracefully."
    )


_ALL_DEMOS: Sequence[tuple[str, Callable[..., None]]] = [
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
    demos: Sequence | None = None,
) -> None:
    """Main entry point for the manage participants demo demo script."""
    run_exchange_demos(
        _ALL_DEMOS, skip_health_check=skip_health_check, demos=demos
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
