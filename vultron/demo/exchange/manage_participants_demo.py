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

1. Accept path: vendor invites coordinator → coordinator accepts, which
   seats it (ADR-0114) → coordinator creates participant status →
   coordinator adds status to participant → vendor, as Case Owner, removes
   the participant from active participation (the record stays on the case)
   → vendor, as Case Owner, reinstates it (ADR-0116).  Each move is the
   Case Owner's own act naming the actor, sent through its trigger, and the
   CASE_MANAGER announces each to the coordinator (ADR-0199)
2. Reject path: vendor invites coordinator → coordinator rejects →
   coordinator is not added to the case

A member is seated only by accepting its stub Invite (ADR-0114); the Case
Owner's ``Add(<Actor>)`` only reinstates a removed one (CM-31-011).
Each demo starts from an initialized
case (report submitted and validated, case created through the
``create-case`` trigger, which seats the vendor as Case Owner and
CASE_MANAGER) so that the invitation and participant management workflows can
be demonstrated in isolation.

This corresponds to the workflow documented in:
    docs/howto/activitypub/activities/manage_participants.md

When run as a script, this module will:
1. Check if the API server is available
2. Reset the data layer to a clean state
3. Discover actors (reporter, vendor, coordinator) via the API
4. Run both demo workflows (accept+manage and reject)
5. Verify side effects in the data layer
"""

import logging
from collections.abc import Callable, Sequence

from vultron.core.models._helpers import authored_times
from vultron.core.models.dimensions import (
    RmDimension,
)
from vultron.core.states.rm import RM
from vultron.demo import wall_clock
from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers.polling import (
    wait_for_participant_rm_state,
    wait_for_semantic_type_in_ledger,
)
from vultron.demo.helpers.runner import run_exchange_demos
from vultron.demo.helpers.verification import (
    verify_participant_status_appended,
)
from vultron.demo.helpers.workflow import (
    invitee_declines_stub_invite,
    seat_participant_through_stub_invite,
    submit_validate_and_create_case,
)
from vultron.demo.utils import (  # noqa: F401 — BASE_URL needed for test monkeypatching
    BASE_URL,
    DataLayerClient,
    demo_check,
    demo_step,
    get_offer_from_datalayer,
    log_case_state,
    post_to_inbox_and_wait,
    ref_id,
    setup_demo_logging,
    verify_object_stored,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import (
    add_status_to_participant_activity,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.case_status import as_ParticipantStatus
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

logger = logging.getLogger(__name__)


def _setup_case_with_vendor(
    client: DataLayerClient,
    reporter: as_Actor,
    vendor: as_Actor,
) -> as_VulnerabilityCase:
    """
    Set up an initialized case owned by the vendor as a precondition for the
    manage-participants workflow.

    Steps 1–4 and the reporter's introduction check are
    :func:`submit_validate_and_create_case`:

    1. Reporter submits the report through its own ``submit-report`` trigger
    2. Vendor validates the report
    3. Vendor creates the case through the ``create-case`` trigger, which
       seats it as Vendor, Case Owner and CASE_MANAGER (CM-02-014,
       CM-02-015): a case is never without a CASE_MANAGER (CM-02-014), and
       the removal and reinstatement in the accept path are the Case Owner's
       own acts, sent to it
    4. Report is linked to the case

    Returns the created as_VulnerabilityCase.
    """
    _report, case = submit_validate_and_create_case(
        client,
        reporter,
        vendor,
        report_name="Use-After-Free in Memory Allocator",
        report_content=(
            "A use-after-free vulnerability in the memory allocator."
        ),
        validation_note=(
            "Confirmed — use-after-free via crafted allocation sequence."
        ),
        case_name="UAF Case — Memory Allocator",
        case_content="Tracking the use-after-free in the memory allocator.",
        stub_summary=(
            "Use-after-free in memory allocator"
            " — details shared after acceptance."
        ),
    )

    log_case_state(client, case.id_, "after setup")
    logger.info("✓ Setup: Case initialized with vendor as sole participant")
    return case


def _activity_id(activity: dict | None, verb: str) -> str:
    """The id of the activity the *verb* trigger returned."""
    activity_id = (activity or {}).get("id")
    if not isinstance(activity_id, str) or not activity_id:
        raise ValueError(f"The {verb} trigger returned no activity id")
    return activity_id


def _carried_id(activity: dict) -> str | None:
    """The id of the object a stored activity carries, inline or by id."""
    carried = activity.get("object_") or activity.get("object")
    if isinstance(carried, dict):
        carried_id = carried.get("id")
        return carried_id if isinstance(carried_id, str) else None
    return ref_id(carried)


def _require_one_announcement(
    client: DataLayerClient, act_id: str, recipient: as_Actor
) -> None:
    """Check the CASE_MANAGER sent *recipient* one ``Announce`` of *act_id*.

    The vendor is the CASE_MANAGER here, so its store holds the
    ``Announce(<the Owner's act>)`` it sent (ADR-0199): its ``inReplyTo``
    and its ``object`` name the act.
    """
    stored = client.get(client.dl_path("Announces/")) or {}
    notices = [
        notice
        for notice in stored.values()
        if (notice.get("inReplyTo") or notice.get("in_reply_to")) == act_id
        and _carried_id(notice) == act_id
        and recipient.id_ in (notice.get("to") or [])
    ]
    if len(notices) != 1:
        raise ValueError(
            f"Expected one Announce of '{act_id}' to '{recipient.id_}',"
            f" found {len(notices)}"
        )


def demo_manage_participants_accept(
    client: DataLayerClient,
    reporter: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor,
) -> None:
    """
    Demonstrates the full accept path of the manage-participants workflow.

    Steps:
    1. Setup: initialize case (report submitted + validated, case created
       through the trigger, vendor seated as Case Owner and CASE_MANAGER)
    2. Vendor invites coordinator to case (RmInviteToCaseActivity)
    3. Coordinator accepts invitation (RmAcceptInviteToCaseActivity), which
       seats it (ADR-0114)
    4. Coordinator adds a new status, carried inline, to their participant
       (AddStatusToParticipantActivity)
    5. Vendor, as Case Owner, removes the coordinator through the
       remove-participant trigger (Remove(<Actor>, origin=<case>))
    6. Verify the coordinator's record stays on the case and carries the
       removal fact (CM-31-001)
    7. Vendor, as Case Owner, reinstates the coordinator through the
       reinstate-participant trigger (Add(<Actor>, target=<case>), CM-31-011)
    8. Verify the removal fact is cleared and the coordinator was sent the
       CASE_MANAGER's Announce of the Owner's act (ADR-0199)

    This follows the accept branch in
    docs/howto/activitypub/activities/manage_participants.md.
    """
    at = wall_clock.now()  # one read for this step (ADR-0176)
    logger.info("=" * 80)
    logger.info("DEMO: Manage Participants — Accept + Status + Remove Path")
    logger.info("=" * 80)

    case = _setup_case_with_vendor(client, reporter, vendor)

    # Every later step acts on the participant record this step seats, so
    # they all nest inside it rather than reading a None sentinel after it
    # (ADR-0058, #3038).
    with demo_step(
        "Steps 2-3: Vendor invites coordinator; coordinator accepts and joins"
    ):
        # The stub Invite is the only way in (ADR-0114): the CASE_MANAGER
        # creates the coordinator's inert record when it sends the Invite and
        # ledgers it; the coordinator's Accept(Invite) is the entry for its
        # consent and joined mark; every replica applies those entries
        # (CM-31-012, ADR-0114).
        coordinator_participant = seat_participant_through_stub_invite(
            client,
            case,
            owner=vendor,
            invitee=coordinator,
            role=CVDRole.COORDINATOR,
        )
        with demo_check("Coordinator in case participant list"):
            updated_case = log_case_state(
                client, case.id_, "after the coordinator accepted"
            )
            if updated_case is None:
                raise ValueError("Could not retrieve case after the accept")
            stored_id = updated_case.actor_participant_index.get(
                coordinator.id_
            )
            if stored_id != coordinator_participant.id_:
                raise ValueError(
                    f"Coordinator actor '{coordinator.id_}' not seated"
                    " after accepting its stub Invite."
                    f" Index: {updated_case.actor_participant_index}"
                )

        with demo_step(
            "Step 4: Coordinator adds an as_ParticipantStatus to their"
            " participant"
        ):
            # The Add carries the new status inline: this implementation does
            # not support a separate Create(ParticipantStatus) (#4598).
            participant_status = as_ParticipantStatus(
                context=case.id_,
                rm=RmDimension(state=RM.ACCEPTED),
                attributed_to=coordinator.id_,
                cvd_role=[CVDRole.COORDINATOR],
                **authored_times(at),
            )
            add_status = add_status_to_participant_activity(
                participant_status,
                actor=coordinator.id_,
                participant=coordinator_participant.id_,
                to=[vendor.id_],
                at=at,
            )
            # A participant sends its status to the CASE_MANAGER alone
            # (PCR-08-001); the vendor holds that role here, and a replica
            # refuses an Add(ParticipantStatus) from anyone else (PCR-03-001).
            post_to_inbox_and_wait(client, vendor.id_, add_status)
            with demo_check("ParticipantStatus appended to participant"):
                verify_participant_status_appended(
                    client, case.id_, coordinator.id_, participant_status.id_
                )
            with demo_check("Case state after status update"):
                log_case_state(
                    client, case.id_, "after AddStatusToParticipantActivity"
                )

        vendor_session = ActorSession(client=client, actor=vendor).with_case(
            case
        )
        with demo_step("Step 5: Vendor, as Case Owner, removes coordinator"):
            # The Case Owner's own act, Remove(<Actor>, origin=<case>), sent
            # to the CASE_MANAGER through the remove-participant trigger
            # (CM-31-004, ADR-0199).  The vendor holds both roles here, so
            # its own inbox admits the act under the same rules.
            removal = vendor_session.remove_participant(
                participant_actor_id=coordinator.id_
            )
            removal_id = _activity_id(removal.activity, "remove-participant")
            wait_for_semantic_type_in_ledger(
                client, case.id_, "remove_participant_from_case"
            )

            # Single-use removal checks, inline for now; extract them into
            # helpers/verification/ when a second scenario removes a
            # participant (DEMOMA-17-001).
            with demo_step(
                "Step 6: Verify coordinator record is kept and inert"
            ):
                with demo_check(
                    "Coordinator still on the case roster (CM-31-015)"
                ):
                    final_case = log_case_state(
                        client, case.id_, "after the Case Owner's removal"
                    )
                    if final_case is None:
                        raise ValueError(
                            "Could not retrieve case after remove"
                        )
                    participant_ids = [
                        (ref_id(p) or str(p))
                        for p in final_case.case_participants
                    ]
                    if coordinator_participant.id_ not in participant_ids:
                        raise ValueError(
                            "Coordinator participant"
                            f" '{coordinator_participant.id_}' was deleted by"
                            " the removal; it must stay on the roster."
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
                    record = client.get(
                        client.dl_path(coordinator_participant.id_)
                    )
                    if record.get("removalActivity") != removal_id:
                        raise ValueError(
                            "Coordinator participant"
                            f" '{coordinator_participant.id_}' does not record"
                            " the removal: removalActivity="
                            f"{record.get('removalActivity')!r}, expected"
                            f" '{removal_id}'"
                        )
                    logger.info(
                        "✓ Coordinator removed from active participation;"
                        " its record stays on the case"
                    )
                with demo_check(
                    "CASE_MANAGER announced the removal to the coordinator"
                ):
                    _require_one_announcement(client, removal_id, coordinator)

        with demo_step(
            "Step 7: Vendor, as Case Owner, reinstates coordinator"
        ):
            # The Case Owner's own act, Add(<Actor>, target=<case>), through
            # the reinstate-participant trigger (CM-31-011, ADR-0199): the
            # removed coordinator is reinstated without accepting again.
            reinstatement = vendor_session.reinstate_participant(
                participant_actor_id=coordinator.id_
            )
            reinstatement_id = _activity_id(
                reinstatement.activity, "reinstate-participant"
            )
            wait_for_semantic_type_in_ledger(
                client, case.id_, "reinstate_participant_in_case"
            )

            # Single-use reinstatement checks, inline for now; extract them
            # into helpers/verification/ when a second scenario reinstates a
            # participant (DEMOMA-17-001).
            with demo_step("Step 8: Verify coordinator is active again"):
                with demo_check(
                    "Coordinator record no longer carries a removal"
                ):
                    record = client.get(
                        client.dl_path(coordinator_participant.id_)
                    )
                    if record.get("removalActivity") is not None:
                        raise ValueError(
                            "Coordinator participant"
                            f" '{coordinator_participant.id_}' still records a"
                            " removal after reinstatement:"
                            f" removalActivity={record.get('removalActivity')!r}"
                        )
                with demo_check(
                    "CASE_MANAGER announced the reinstatement to the"
                    " coordinator"
                ):
                    _require_one_announcement(
                        client, reinstatement_id, coordinator
                    )
                    logger.info(
                        "✓ Coordinator reinstated; it did not accept again"
                        " (CM-31-035)"
                    )

    logger.info(
        "✅ DEMO COMPLETE (accept path): Coordinator joined, status set,"
        " removed from active participation, then reinstated."
    )


def demo_manage_participants_reject(
    client: DataLayerClient,
    reporter: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor,
) -> None:
    """
    Demonstrates the reject path of the manage-participants workflow.

    Steps:
    1. Setup: initialize case (report submitted + validated, case created,
       vendor participant added)
    2. Vendor asks the CASE_MANAGER (itself) to invite the coordinator, which
       sends the stub Invite
    3. Coordinator rejects that Invite through its reject-case-invite trigger
    4. Verify the coordinator's inert record is closed: it never joined
       (CM-11-006, CM-11-007)

    This follows the reject branch in
    docs/howto/activitypub/activities/manage_participants.md.
    """
    logger.info("=" * 80)
    logger.info("DEMO: Manage Participants — Reject Path")
    logger.info("=" * 80)

    case = _setup_case_with_vendor(client, reporter, vendor)

    # Step 4 reads the CASE_MANAGER id this step resolves, so it nests inside
    # it rather than reading a None sentinel after it (ADR-0058, #3038).
    with demo_step(
        "Steps 2-3: Vendor has the coordinator invited; coordinator declines"
    ):
        # Through the triggers: the CASE_MANAGER sends the Invite, and the
        # coordinator rejects that recorded Invite (EP-09-010, #5438).
        case_manager_id = invitee_declines_stub_invite(
            client,
            case,
            owner=vendor,
            invitee=coordinator,
            role=CVDRole.COORDINATOR,
        )

        with demo_step("Step 4: Verify coordinator never became active"):
            # The Invite put an inert record for the coordinator on the roster
            # (CM-11-006); its Reject closes that record, which never joined
            # (CM-11-007).  The CASE_MANAGER's store holds the record.
            with demo_check("Coordinator's inert record closed after reject"):
                wait_for_participant_rm_state(
                    client=client,
                    case_id=case.id_,
                    actor_id=coordinator.id_,
                    expected_states={RM.CLOSED},
                    dl_actor_id=case_manager_id,
                )
                log_case_state(client, case.id_, "after reject")

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
