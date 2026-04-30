#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
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

"""Three-actor (Finder + Vendor + Coordinator) multi-container CVD demo.

This scenario extends the D5-2 two-actor workflow by introducing a dedicated
Coordinator and an authoritative CaseActor container. The workflow remains
fully deterministic for repeatable acceptance runs:

1. Reset Finder, Vendor, Coordinator, and CaseActor containers.
2. Seed each container with its local actor plus all peers.
3. Finder submits a report to the Coordinator.
4. Coordinator creates the authoritative case on the CaseActor container.
5. Coordinator invites Finder into the case and Finder accepts.
6. Coordinator proposes an embargo and Finder accepts it.
7. Coordinator invites Vendor into the case and Vendor accepts.
8. Vendor accepts the active embargo.
9. Verify the case exists only in the CaseActor container with all three
   participants registered and the embargo active.
"""

from datetime import datetime, timedelta, timezone
import logging
import os
import sys

from vultron.core.states.em import EM
from vultron.demo.scenario.two_actor_demo import (
    get_actor_by_id,
    wait_for_case_participants,
)
from vultron.demo.utils import (
    DataLayerClient,
    check_server_availability,
    demo_check,
    demo_step,
    logfmt,
    post_to_inbox_and_wait,
    post_to_trigger,
    ref_id,
    reset_datalayer,
    seed_actor,
    verify_object_stored,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)
from vultron.wire.as2.factories import (
    rm_submit_report_activity,
)
from vultron.core.models.vultron_types import VultronActivity

logger = logging.getLogger(__name__)

FINDER_BASE_URL = os.environ.get(
    "VULTRON_FINDER_BASE_URL", "http://localhost:7901/api/v2"
)
VENDOR_BASE_URL = os.environ.get(
    "VULTRON_VENDOR_BASE_URL", "http://localhost:7902/api/v2"
)
CASE_ACTOR_BASE_URL = os.environ.get(
    "VULTRON_CASE_ACTOR_BASE_URL", "http://localhost:7903/api/v2"
)
COORDINATOR_BASE_URL = os.environ.get(
    "VULTRON_COORDINATOR_BASE_URL", "http://localhost:7904/api/v2"
)

FINDER_ACTOR_ID = "http://finder:7999/api/v2/actors/finder"
VENDOR_ACTOR_ID = "http://vendor:7999/api/v2/actors/vendor"
CASE_ACTOR_ID = "http://case-actor:7999/api/v2/actors/case-actor"
COORDINATOR_ACTOR_ID = "http://coordinator:7999/api/v2/actors/coordinator"


def seed_containers(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    reporter_actor_id: str | None = None,
    vendor_actor_id: str | None = None,
    coordinator_actor_id: str | None = None,
    case_actor_id: str | None = None,
) -> tuple[as_Actor, as_Actor, as_Actor, as_Actor]:
    """Seed all containers with their local actor and all peer actors."""
    local_specs = [
        ("Finder", finder_client, "Finder", "Person", reporter_actor_id),
        ("Vendor", vendor_client, "Vendor", "Organization", vendor_actor_id),
        (
            "Coordinator",
            coordinator_client,
            "Coordinator",
            "Service",
            coordinator_actor_id,
        ),
        (
            "CaseActor",
            case_actor_client,
            "CaseActor",
            "Service",
            case_actor_id,
        ),
    ]

    actors: dict[str, as_Actor] = {}
    with demo_step("Seeding all local actors"):
        for label, client, name, actor_type, actor_id in local_specs:
            actors[label] = seed_actor(
                client=client,
                name=name,
                actor_type=actor_type,
                actor_id=actor_id,
            )
            logger.info("%s actor seeded: %s", label, actors[label].id_)

    with demo_step("Registering all peer actors on every container"):
        for label, client, _name, _actor_type, _actor_id in local_specs:
            for peer_label, peer in actors.items():
                if peer_label == label:
                    continue
                seed_actor(
                    client=client,
                    name=peer.name or peer_label,
                    actor_type=str(peer.type_),
                    actor_id=peer.id_,
                )
                logger.info(
                    "Registered peer %s on %s container: %s",
                    peer_label,
                    label,
                    peer.id_,
                )

    return (
        actors["Finder"],
        actors["Vendor"],
        actors["Coordinator"],
        actors["CaseActor"],
    )


def reset_containers(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    case_actor_client: DataLayerClient,
) -> None:
    """Reset all containers used by the demo to a clean baseline."""
    targets = [
        ("Finder", finder_client),
        ("Vendor", vendor_client),
        ("Coordinator", coordinator_client),
        ("CaseActor", case_actor_client),
    ]

    with demo_step("Resetting actor containers to a clean baseline"):
        for label, client in targets:
            result = reset_datalayer(client=client, init=False)
            logger.info("%s reset result: %s", label, result)

    with demo_check("All actor containers start with no persisted cases"):
        for label, client in targets:
            cases = client.get("/datalayer/VulnerabilityCases/")
            if cases:
                raise AssertionError(
                    f"{label} container was not reset cleanly: {cases}"
                )


def finder_submits_report_to_coordinator(
    coordinator_client: DataLayerClient,
    finder: as_Actor,
    coordinator: as_Actor,
) -> tuple[VulnerabilityReport, VultronActivity]:
    """Finder submits a report to the Coordinator container."""
    report = VulnerabilityReport(
        attributed_to=finder.id_,
        name="Coordinated disclosure for dependency parser RCE",
        content=(
            "A dependency parser accepts untrusted archive metadata and can "
            "be coerced into remote code execution before package signature "
            "verification completes."
        ),
    )
    offer = rm_submit_report_activity(
        report, actor=finder.id_, to=coordinator.id_
    )
    with demo_step(
        "Finder submits vulnerability report to Coordinator's inbox"
    ):
        post_to_inbox_and_wait(coordinator_client, coordinator.id_, offer)
    with demo_check("Report and offer are stored in Coordinator's DataLayer"):
        verify_object_stored(coordinator_client, report.id_)
        verify_object_stored(coordinator_client, offer.id_)
    logger.info("Report submitted to Coordinator: %s", ref_id(report))
    return report, offer


def coordinator_creates_case_on_case_actor(
    coordinator_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    case_actor: as_Actor,
    coordinator: as_Actor,
    report: VulnerabilityReport,
) -> VulnerabilityCase:
    """Create the authoritative case on the dedicated CaseActor container."""
    with demo_step("Coordinator creates the case via trigger"):
        result = post_to_trigger(
            client=coordinator_client,
            actor_id=coordinator.id_,
            behavior="create-case",
            body={
                "name": "Three-Actor Demo Case",
                "content": (
                    "Case coordinated by the Coordinator with Finder and Vendor "
                    "participating through the dedicated CaseActor container."
                ),
                "report_id": report.id_,
            },
        )
    create_case = VultronActivity.model_validate(result["activity"])
    case = VulnerabilityCase.model_validate(
        create_case.object_.model_dump(by_alias=True)  # type: ignore[union-attr]
    )
    with demo_step("Delivering CreateCase activity to CaseActor"):
        post_to_inbox_and_wait(case_actor_client, case_actor.id_, create_case)
    with demo_check("Case is stored in the CaseActor DataLayer"):
        verify_object_stored(case_actor_client, case.id_)
    logger.info("Authoritative case created on CaseActor: %s", case.id_)
    return case


def coordinator_adds_report_to_case(
    coordinator_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    case_actor: as_Actor,
    coordinator: as_Actor,
    case: VulnerabilityCase,
    report: VulnerabilityReport,
) -> None:
    """Link the submitted report to the authoritative case."""
    with demo_step(
        "Coordinator links the submitted report to the case via trigger"
    ):
        result = post_to_trigger(
            client=coordinator_client,
            actor_id=coordinator.id_,
            behavior="add-report-to-case",
            body={
                "case_id": case.id_,
                "report_id": report.id_,
            },
        )
    add_report = VultronActivity.model_validate(result["activity"])
    with demo_step("Delivering AddReportToCase activity to CaseActor"):
        post_to_inbox_and_wait(case_actor_client, case_actor.id_, add_report)
    with demo_check("CaseActor stores the AddReportToCase activity"):
        verify_object_stored(case_actor_client, add_report.id_)


def coordinator_invites_actor(
    actor_client: DataLayerClient,
    recipient_client: DataLayerClient,
    actor: as_Actor,
    recipient: as_Actor,
    case: VulnerabilityCase,
    case_actor_client: DataLayerClient | None = None,
    case_actor: as_Actor | None = None,
) -> VultronActivity:
    """Record and deliver a case invitation from the case owner."""
    with demo_step(f"{actor.name} invites {recipient.name} via trigger"):
        result = post_to_trigger(
            client=actor_client,
            actor_id=actor.id_,
            behavior="invite-actor-to-case",
            body={
                "case_id": case.id_,
                "invitee_id": recipient.id_,
            },
        )
    invite = VultronActivity.model_validate(result["activity"])

    if (
        case_actor_client is not None
        and case_actor is not None
        and case_actor_client.base_url != actor_client.base_url
    ):
        with demo_step("Delivering invite to CaseActor container"):
            post_to_inbox_and_wait(case_actor_client, case_actor.id_, invite)
        with demo_check("Invite is stored in the CaseActor DataLayer"):
            verify_object_stored(case_actor_client, invite.id_)

    if recipient_client.base_url != actor_client.base_url:
        with demo_step(f"Delivering invite to {recipient.name}"):
            post_to_inbox_and_wait(recipient_client, recipient.id_, invite)
        with demo_check(f"Invite is stored in {recipient.name}'s DataLayer"):
            verify_object_stored(recipient_client, invite.id_)

    logger.info("Invite sent to %s: %s", recipient.name, invite.id_)
    return invite


def actor_accepts_case_invite(
    actor_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    case_actor: as_Actor,
    actor: as_Actor,
    invite: VultronActivity,
) -> VultronActivity:
    """Accept a case invitation by notifying the CaseActor container."""
    with demo_step(f"{actor.name} accepts the case invitation via trigger"):
        result = post_to_trigger(
            client=actor_client,
            actor_id=actor.id_,
            behavior="accept-case-invite",
            body={"invite_id": invite.id_},
        )
    accept = VultronActivity.model_validate(result["activity"])
    with demo_step("Delivering accept activity to CaseActor"):
        post_to_inbox_and_wait(case_actor_client, case_actor.id_, accept)
    with demo_check("Accept activity is stored in the CaseActor DataLayer"):
        verify_object_stored(case_actor_client, accept.id_)
    logger.info("Case invite accepted by %s: %s", actor.name, accept.id_)
    return accept


def coordinator_proposes_embargo(
    case_actor_client: DataLayerClient,
    coordinator: as_Actor,
    case: VulnerabilityCase,
) -> tuple[VultronActivity, str]:
    """Propose an embargo on the authoritative case."""
    end_time = datetime.now(tz=timezone.utc) + timedelta(days=30)
    with demo_step("Coordinator proposes an embargo on the case"):
        result = post_to_trigger(
            client=case_actor_client,
            actor_id=coordinator.id_,
            behavior="propose-embargo",
            body={
                "case_id": case.id_,
                "note": "Default coordinator embargo window for initial triage.",
                "end_time": end_time.isoformat(),
            },
        )
    proposal = VultronActivity.model_validate(result["activity"])
    embargo_id = ref_id(proposal.object_)
    if embargo_id is None:
        raise AssertionError(
            "Embargo proposal is missing an embargo reference"
        )
    with demo_check("Embargo proposal is stored in the CaseActor DataLayer"):
        verify_object_stored(case_actor_client, proposal.id_)
        verify_object_stored(case_actor_client, embargo_id)
    logger.info("Embargo proposed: %s", proposal.id_)
    return proposal, embargo_id


def deliver_embargo_proposal(
    recipient_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    recipient: as_Actor,
    proposal: VultronActivity,
) -> None:
    """Deliver an embargo proposal activity to a participant inbox."""
    if recipient_client.base_url == case_actor_client.base_url:
        return
    with demo_step(f"Delivering embargo proposal to {recipient.name}"):
        post_to_inbox_and_wait(recipient_client, recipient.id_, proposal)
    with demo_check(
        f"Embargo proposal stored in {recipient.name}'s DataLayer"
    ):
        verify_object_stored(recipient_client, proposal.id_)


def actor_accepts_embargo(
    case_actor_client: DataLayerClient,
    actor: as_Actor,
    case: VulnerabilityCase,
    proposal: VultronActivity,
) -> None:
    """Accept the active embargo proposal on the authoritative case."""
    with demo_step(f"{actor.name} accepts the embargo proposal via trigger"):
        post_to_trigger(
            client=case_actor_client,
            actor_id=actor.id_,
            behavior="accept-embargo",
            body={
                "case_id": case.id_,
                "proposal_id": proposal.id_,
            },
        )
    logger.info("Embargo accepted by %s", actor.name)


def verify_case_actor_case_state(
    case_actor_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    case_id: str,
    report_id: str,
    coordinator_actor_id: str,
    reporter_actor_id: str,
    vendor_actor_id: str,
    embargo_id: str,
) -> VulnerabilityCase:
    """Assert the authoritative final case state on the CaseActor container."""
    final_case_data = case_actor_client.get(f"/datalayer/{case_id}")
    final_case = VulnerabilityCase(**final_case_data)

    if len(final_case.case_participants) != 3:
        raise AssertionError(
            "Expected 3 case participants on the CaseActor container, "
            f"found {len(final_case.case_participants)}"
        )

    if report_id not in [
        ref_id(report) or str(report)
        for report in final_case.vulnerability_reports
    ]:
        raise AssertionError(
            "Final case does not reference the submitted report"
        )

    current_status = final_case.current_status
    if current_status.em_state != EM.ACTIVE:
        raise AssertionError(
            f"Expected ACTIVE embargo state, found {current_status.em_state}"
        )

    if ref_id(final_case.active_embargo) != embargo_id:
        raise AssertionError(
            "Final case does not reference the accepted active embargo"
        )

    for actor_id in (coordinator_actor_id, reporter_actor_id, vendor_actor_id):
        if actor_id not in final_case.actor_participant_index:
            raise AssertionError(
                f"Actor {actor_id} missing from actor_participant_index"
            )

    participant_records = case_actor_client.get("/datalayer/CaseParticipants/")
    for actor_id in (
        coordinator_actor_id,
        reporter_actor_id,
        vendor_actor_id,
    ):
        participant_id = final_case.actor_participant_index[actor_id]
        participant_data = participant_records.get(participant_id)
        if participant_data is None:
            raise AssertionError(
                f"Participant record {participant_id} not found in CaseActor DataLayer"
            )
        participant = CaseParticipant(**participant_data)
        if embargo_id not in participant.accepted_embargo_ids:
            raise AssertionError(
                f"Participant {participant_id} did not record acceptance of "
                f"embargo {embargo_id}"
            )

    if coordinator_client.base_url != case_actor_client.base_url:
        coordinator_cases = coordinator_client.get(
            "/datalayer/VulnerabilityCases/"
        )
        if case_id in coordinator_cases:
            raise AssertionError(
                "Coordinator container unexpectedly persisted the authoritative case"
            )

    return final_case


def run_three_actor_demo(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    finder_id: str | None = None,
    vendor_id: str | None = None,
    coordinator_id: str | None = None,
    case_actor_id: str | None = None,
) -> None:
    """Run the full deterministic three-actor scenario."""
    logger.info("=" * 80)
    logger.info("THREE-ACTOR DEMO: Finder + Vendor + Coordinator (D5-3)")
    logger.info("=" * 80)
    logger.info("Finder container: %s", finder_client.base_url)
    logger.info("Vendor container: %s", vendor_client.base_url)
    logger.info("Coordinator container: %s", coordinator_client.base_url)
    logger.info("CaseActor container: %s", case_actor_client.base_url)

    reset_containers(
        finder_client=finder_client,
        vendor_client=vendor_client,
        coordinator_client=coordinator_client,
        case_actor_client=case_actor_client,
    )

    with demo_step("Seeding all containers with actor records"):
        finder, vendor, coordinator, case_actor = seed_containers(
            finder_client=finder_client,
            vendor_client=vendor_client,
            coordinator_client=coordinator_client,
            case_actor_client=case_actor_client,
            reporter_actor_id=finder_id,
            vendor_actor_id=vendor_id,
            coordinator_actor_id=coordinator_id,
            case_actor_id=case_actor_id,
        )

    coordinator_in_coordinator = get_actor_by_id(
        coordinator_client, coordinator.id_
    )
    coordinator_in_case_actor = get_actor_by_id(
        case_actor_client, coordinator.id_
    )
    finder_in_coordinator = get_actor_by_id(coordinator_client, finder.id_)
    vendor_in_coordinator = get_actor_by_id(coordinator_client, vendor.id_)
    finder_in_finder = get_actor_by_id(finder_client, finder.id_)
    vendor_in_vendor = get_actor_by_id(vendor_client, vendor.id_)

    report, _offer = finder_submits_report_to_coordinator(
        coordinator_client=coordinator_client,
        finder=finder,
        coordinator=coordinator_in_coordinator,
    )

    case = coordinator_creates_case_on_case_actor(
        coordinator_client=coordinator_client,
        case_actor_client=case_actor_client,
        case_actor=case_actor,
        coordinator=coordinator_in_coordinator,
        report=report,
    )
    coordinator_adds_report_to_case(
        coordinator_client=coordinator_client,
        case_actor_client=case_actor_client,
        case_actor=case_actor,
        coordinator=coordinator_in_coordinator,
        case=case,
        report=report,
    )

    finder_invite = coordinator_invites_actor(
        actor_client=coordinator_client,
        recipient_client=finder_client,
        actor=coordinator_in_coordinator,
        recipient=finder_in_coordinator,
        case=case,
        case_actor_client=case_actor_client,
        case_actor=case_actor,
    )
    actor_accepts_case_invite(
        actor_client=finder_client,
        case_actor_client=case_actor_client,
        case_actor=case_actor,
        actor=finder_in_finder,
        invite=finder_invite,
    )
    wait_for_case_participants(
        vendor_client=case_actor_client,
        case_id=case.id_,
        expected_count=2,
    )

    embargo_proposal, embargo_id = coordinator_proposes_embargo(
        case_actor_client=case_actor_client,
        coordinator=coordinator_in_case_actor,
        case=case,
    )
    deliver_embargo_proposal(
        recipient_client=finder_client,
        case_actor_client=case_actor_client,
        recipient=finder_in_finder,
        proposal=embargo_proposal,
    )
    actor_accepts_embargo(
        case_actor_client=case_actor_client,
        actor=coordinator_in_case_actor,
        case=case,
        proposal=embargo_proposal,
    )
    actor_accepts_embargo(
        case_actor_client=case_actor_client,
        actor=finder_in_finder,
        case=case,
        proposal=embargo_proposal,
    )

    vendor_invite = coordinator_invites_actor(
        actor_client=coordinator_client,
        recipient_client=vendor_client,
        actor=coordinator_in_coordinator,
        recipient=vendor_in_coordinator,
        case=case,
        case_actor_client=case_actor_client,
        case_actor=case_actor,
    )
    actor_accepts_case_invite(
        actor_client=vendor_client,
        case_actor_client=case_actor_client,
        case_actor=case_actor,
        actor=vendor_in_vendor,
        invite=vendor_invite,
    )
    wait_for_case_participants(
        vendor_client=case_actor_client,
        case_id=case.id_,
        expected_count=3,
    )

    deliver_embargo_proposal(
        recipient_client=vendor_client,
        case_actor_client=case_actor_client,
        recipient=vendor_in_vendor,
        proposal=embargo_proposal,
    )
    actor_accepts_embargo(
        case_actor_client=case_actor_client,
        actor=vendor_in_vendor,
        case=case,
        proposal=embargo_proposal,
    )

    with demo_check(
        "CaseActor container holds the authoritative three-actor final state"
    ):
        final_case = verify_case_actor_case_state(
            case_actor_client=case_actor_client,
            coordinator_client=coordinator_client,
            case_id=case.id_,
            report_id=report.id_,
            coordinator_actor_id=coordinator.id_,
            reporter_actor_id=finder.id_,
            vendor_actor_id=vendor.id_,
            embargo_id=embargo_id,
        )
        logger.info("Final case state (CaseActor): %s", logfmt(final_case))

    logger.info("=" * 80)
    logger.info("THREE-ACTOR DEMO COMPLETE ✓")
    logger.info("=" * 80)


def main(
    skip_health_check: bool = False,
    finder_url: str | None = None,
    vendor_url: str | None = None,
    coordinator_url: str | None = None,
    case_actor_url: str | None = None,
    finder_id: str | None = None,
    vendor_id: str | None = None,
    coordinator_id: str | None = None,
    case_actor_id: str | None = None,
) -> None:
    """Entry point for the three-actor multi-container demo."""
    f_url = finder_url or FINDER_BASE_URL
    v_url = vendor_url or VENDOR_BASE_URL
    coord_url = coordinator_url or COORDINATOR_BASE_URL
    c_url = case_actor_url or CASE_ACTOR_BASE_URL

    finder_client = DataLayerClient(base_url=f_url)
    vendor_client = DataLayerClient(base_url=v_url)
    coordinator_client = DataLayerClient(base_url=coord_url)
    case_actor_client = DataLayerClient(base_url=c_url)

    if not skip_health_check:
        targets = [
            ("Finder", finder_client),
            ("Vendor", vendor_client),
            ("Coordinator", coordinator_client),
            ("CaseActor", case_actor_client),
        ]
        for label, client in targets:
            if not check_server_availability(client):
                logger.error("=" * 80)
                logger.error("ERROR: %s API server is not available", label)
                logger.error("=" * 80)
                logger.error("Cannot connect to: %s", client.base_url)
                logger.error(
                    "Ensure the %s container is running and healthy.", label
                )
                logger.error("=" * 80)
                sys.exit(1)

    try:
        run_three_actor_demo(
            finder_client=finder_client,
            vendor_client=vendor_client,
            coordinator_client=coordinator_client,
            case_actor_client=case_actor_client,
            finder_id=finder_id,
            vendor_id=vendor_id,
            coordinator_id=coordinator_id,
            case_actor_id=case_actor_id,
        )
    except Exception as exc:
        logger.error("Three-actor demo failed: %s", exc, exc_info=True)
        logger.error("=" * 80)
        logger.error("ERROR SUMMARY")
        logger.error("=" * 80)
        logger.error("%s", exc)
        logger.error("=" * 80)
        sys.exit(1)


def _setup_logging() -> None:
    """Configure console logging for standalone execution."""
    logging.getLogger("requests").setLevel(logging.WARNING)
    root = logging.getLogger()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    )
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)


if __name__ == "__main__":
    _setup_logging()
    main()
