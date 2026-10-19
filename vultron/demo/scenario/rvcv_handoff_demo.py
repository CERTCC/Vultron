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

"""Reporter → Vendor1 → Coordinator (ownership transfer) → Vendor2 (RVCV-handoff) demo.

Orchestrates the RVCV-handoff CVD workflow across four separate containers:
Reporter, Vendor1 (initial CASE_OWNER), Coordinator (new CASE_OWNER after handoff),
and Vendor2.  Vendor1 transfers case ownership to Coordinator via the new
trigger endpoints (TRIG-11-001/TRIG-11-002), then Coordinator invites Vendor2.

Spec: GitHub issue #1561.
"""

import logging
import sys

from vultron.core.states.cs import CS_vf
from vultron.core.states.rm import RM
from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers.actor_roles import (
    ActorRole,
    case_actor_role,
    role_map,
)
from vultron.demo.helpers.closure import CaseLeaver, close_case_owner_last
from vultron.demo.helpers.harness import scenario_harness
from vultron.demo.helpers.invite_chain import (
    CaseInviter,
    EmittedBy,
    run_case_invite_chain,
)
from vultron.demo.helpers.ledger_dump import (
    LedgerDumpTarget,
    case_actor_dump_target,
    dump_case_ledgers,
    replica_route_key,
)
from vultron.demo.helpers.milestones import (
    verify_case_active,
    verify_fix_ready,
    verify_publicly_disclosed,
)
from vultron.demo.helpers.notes import (
    participant_adds_note_to_case,
)
from vultron.demo.helpers.polling import (
    LATE_JOINER_TIMEOUT,
    SharedBudget,
    find_case_actor_participant_id,
    find_ownership_transfer_offer_for_actor,
    wait_for_case_actor_ledger_event,
    wait_for_case_attributed_to,
    wait_for_case_em_terminated,
    wait_for_case_on_container,
    wait_for_case_participants,
    wait_for_event_type_in_ledger,
    wait_for_participant_rm_state,
    wait_for_participant_vf_state,
)
from vultron.demo.helpers.seeding import (
    get_actor_by_id,
    reset_containers as _reset_containers,
    seed_containers_rvcv,
)
from vultron.demo.helpers.sync import (
    run_sync_verification_phase,
)
from vultron.demo.helpers.workflow import (
    reporter_submits_report,
    run_direct_path_rm_triage,
    run_invite_path_rm_triage,
)
from vultron.demo.scenario.registry import scenario
from vultron.demo.utils import (  # noqa: F401 — re-exported for test monkeypatching
    DataLayerClient,
    assert_demo_success,
    bound_case_actor_client,
    check_server_availability,
    demo_check,
    demo_gate,
    demo_step,
    ref_id,
    reset_datalayer,
    reset_demo_failures,
    setup_demo_logging,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,  # used in type annotation
)

logger = logging.getLogger(__name__)

# Default container base URLs — override via environment variables.
ROLES: list[ActorRole] = [
    ActorRole(
        name="reporter",
        url_env="VULTRON_REPORTER_BASE_URL",
        default_url="http://localhost:7901/api/v2",
        url_help="Base URL of the Reporter container API "
        "(env: VULTRON_REPORTER_BASE_URL).",
        has_id=True,
        id_help="Deterministic full URI for the Reporter actor (optional).",
    ),
    ActorRole(
        name="vendor",
        url_env="VULTRON_VENDOR_BASE_URL",
        default_url="http://localhost:7902/api/v2",
        url_help="Base URL of the Vendor1 container API "
        "(env: VULTRON_VENDOR_BASE_URL).",
        has_id=True,
        id_help="Deterministic full URI for the Vendor1 actor (optional).",
    ),
    ActorRole(
        name="coordinator",
        url_env="VULTRON_COORDINATOR_BASE_URL",
        default_url="http://localhost:7903/api/v2",
        url_help="Base URL of the Coordinator container API "
        "(env: VULTRON_COORDINATOR_BASE_URL).",
        has_id=True,
        id_help="Deterministic full URI for the Coordinator actor (optional).",
    ),
    case_actor_role("http://localhost:7905/api/v2", has_id=True),
    ActorRole(
        name="vendor2",
        url_env="VULTRON_VENDOR2_BASE_URL",
        default_url="http://localhost:7904/api/v2",
        url_help="Base URL of the Vendor2 container API "
        "(env: VULTRON_VENDOR2_BASE_URL).",
        has_id=True,
        id_help="Deterministic full URI for the Vendor2 actor (optional).",
    ),
]
_ROLES = role_map(ROLES)

REPORTER_BASE_URL = _ROLES["reporter"].url
VENDOR_BASE_URL = _ROLES["vendor"].url
COORDINATOR_BASE_URL = _ROLES["coordinator"].url
CASE_ACTOR_BASE_URL = _ROLES["case-actor"].url
VENDOR2_BASE_URL = _ROLES["vendor2"].url

#: ``vultron-demo rvcv-handoff --help`` text. Lives here rather than in
#: ``cli.py`` because the sub-command is generated from the registry and the
#: scenario module is the only place that knows what its own workflow does.
CLI_HELP = """Run the RVCV-handoff (Vendor1 → Coordinator ownership transfer) demo (D5-7).

Vendor1 creates the case and invites Coordinator, then transfers case
ownership to Coordinator via the trigger endpoints (TRIG-11-001/002).
Coordinator (now CASE_OWNER) invites Vendor2.  Both vendors independently
advance through the full fix and publication lifecycle.

\b
Workflow:
  1. Seed all five containers (actor records + peer registration).
  2. Reporter submits a vulnerability report to Vendor1's inbox.
  3. Vendor1 validates and engages the case.
  4. Vendor1 invites Coordinator; Coordinator accepts.
  5. Vendor1 offers case ownership transfer to Coordinator (TRIG-11-001).
  6. Coordinator accepts the ownership transfer (TRIG-11-002).
  7. Verify case attributed_to updated to Coordinator.
  8. Coordinator invites Vendor2; Vendor2 accepts and Accept routed to CaseActor.
  9. Verify LedgerFanout replication on all replicas.
 10. Both vendors independently advance through fix-ready → fix-deployed.
 11. All participants report publication; embargo terminates.
 12. All participants close the case.
"""

# Deterministic actor IDs from docker-compose-multi-actor.yml (D5-1-G3).
REPORTER_ACTOR_ID = "http://reporter:7999/api/v2/actors/reporter"
VENDOR_ACTOR_ID = "http://vendor:7999/api/v2/actors/vendor"
COORDINATOR_ACTOR_ID = "http://coordinator:7999/api/v2/actors/coordinator"
CASE_ACTOR_ACTOR_ID = "http://case-actor:7999/api/v2/actors/case-actor"
VENDOR2_ACTOR_ID = "http://actor5:7999/api/v2/actors/vendor2"


def reset_containers(
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    vendor2_client: DataLayerClient,
) -> None:
    """Reset all five RVCV-handoff containers to a clean baseline."""
    targets: list[tuple[str, DataLayerClient]] = [
        ("Reporter", reporter_client),
        ("Vendor1", vendor_client),
        ("Coordinator", coordinator_client),
        ("Vendor2", vendor2_client),
    ]
    # Reset with the others, then its CaseActor identity is re-seeded: Vendor1
    # proposes the case to it (DEMOMA-06-004).
    _reset_containers(
        targets,
        reset_fn=reset_datalayer,
        case_actor_client=case_actor_client,
    )


# ---------------------------------------------------------------------------
# Phase helpers
# ---------------------------------------------------------------------------


def _phase_report_submission(
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    reporter_id: str | None,
    vendor_id: str | None,
    coordinator_id: str | None,
    vendor2_id: str | None,
) -> tuple[
    as_Actor,
    as_Actor,
    as_Actor,
    as_Actor,
    as_Actor,
    as_Actor,
    as_VulnerabilityReport,
    object,
    as_VulnerabilityCase,
]:
    """Reset, seed, submit report, validate, engage, and wait for initial participants."""
    logger.info("─" * 80)
    logger.info("Phase 1: Report submission and case activation")
    logger.info("─" * 80)

    reset_containers(
        reporter_client=reporter_client,
        vendor_client=vendor_client,
        coordinator_client=coordinator_client,
        case_actor_client=case_actor_client,
        vendor2_client=vendor2_client,
    )

    reporter = vendor = coordinator = vendor2 = None
    with demo_step("Seeding all four containers with actor records"):
        reporter, vendor, coordinator, vendor2 = seed_containers_rvcv(
            reporter_client=reporter_client,
            vendor_client=vendor_client,
            coordinator_client=coordinator_client,
            vendor2_client=vendor2_client,
            reporter_actor_id=reporter_id,
            vendor_actor_id=vendor_id,
            coordinator_actor_id=coordinator_id,
            vendor2_actor_id=vendor2_id,
        )

    vendor_in_vendor = get_actor_by_id(vendor_client, vendor.id_)
    coordinator_in_coordinator = get_actor_by_id(
        coordinator_client, coordinator.id_
    )

    report, offer = reporter_submits_report(
        receiver_client=vendor_client,
        reporter=reporter,
        receiver=vendor_in_vendor,
        reporter_client=reporter_client,
    )
    case = run_direct_path_rm_triage(
        receiver_client=vendor_client,
        receiver=vendor_in_vendor,
        offer=offer,
        timeout_seconds=60.0,
    )

    # Wait for initial participants (Reporter + Vendor1 + CaseActor).
    with demo_gate("participant count ≥3 before M1 verify_case_active"):
        wait_for_case_participants(
            vendor_client=vendor_client,
            case_id=case.id_,
            expected_actor_ids={reporter.id_, vendor.id_},
        )

        with demo_check(
            "Reporter's DataLayer received case replica (genesis hash available)"
        ):
            wait_for_case_on_container(
                client=reporter_client,
                case_id=case.id_,
            )

    case = as_VulnerabilityCase.model_validate(
        vendor_client.get(vendor_client.dl_path(case.id_))
    )
    return (
        reporter,
        vendor,
        vendor_in_vendor,
        coordinator,
        coordinator_in_coordinator,
        vendor2,
        report,
        offer,
        case,
    )


def _phase_ownership_handoff(
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    reporter: as_Actor,
    vendor: as_Actor,
    vendor_in_vendor: as_Actor,
    coordinator: as_Actor,
    coordinator_in_coordinator: as_Actor,
    case: as_VulnerabilityCase,
) -> as_VulnerabilityCase:
    """Vendor1 invites Coordinator then transfers case ownership to Coordinator.

    Returns the updated case (with Coordinator as attributed_to).
    """
    logger.info("─" * 80)
    logger.info(
        "Phase 2: Ownership handoff — Vendor1 invites Coordinator then transfers ownership"
    )
    logger.info("─" * 80)

    # Vendor1 invites Coordinator with COORDINATOR role; the chain nests the
    # delivery gate, the accept and the replica wait (ADR-0058, EDF-06-005,
    # #3038).
    run_case_invite_chain(
        case=case,
        case_manager_client=case_actor_client,
        invitee_name="Coordinator",
        invitee_client=coordinator_client,
        invitee=coordinator,
        invitee_in_own_container=coordinator_in_coordinator,
        inviter=CaseInviter(
            name="Vendor1",
            client=vendor_client,
            actor=vendor_in_vendor,
            role=CVDRole.COORDINATOR,
        ),
        invite_timeout=90.0,
    )

    # All 4 participants (Reporter + Vendor1 + Coordinator + CaseActor) present is
    # the causal precondition for the ownership-transfer offer/accept below: a
    # demo_gate — not demo_check — so a timeout skips the doomed transfer rather
    # than cascading (DEMOCI-01-011, vultron/demo/AGENTS.md § "Never Wrap a
    # Causal Wait in demo_check").
    with demo_gate(
        "Vendor1 case has all 4 participants before ownership transfer"
    ):
        wait_for_case_participants(
            vendor_client=vendor_client,
            case_id=case.id_,
            expected_actor_ids={
                reporter.id_,
                vendor.id_,
                coordinator.id_,
            },
        )
        logger.info("Coordinator has joined the case")

        # Vendor1 offers ownership transfer to Coordinator (TRIG-11-001).  The
        # delivery gate and the Coordinator's accept are nested inside the
        # offer step so a failed trigger or lookup skips them instead of
        # posting an empty ``offer_id`` (ADR-0058 nested-block model,
        # EDF-06-005, #3038).
        with demo_step(
            "Vendor1 offers case ownership transfer to Coordinator (TRIG-11-001)"
        ):
            ownership_offer = (
                ActorSession(client=vendor_client, actor=vendor_in_vendor)
                .with_case(case)
                .quiet()
                .offer_case_ownership_transfer(
                    transferee_id=coordinator.id_,
                    content=(
                        "Transferring case ownership to Coordinator for CVD"
                        " management."
                    ),
                )
            ).activity
            logger.info(
                "Vendor1 sent Offer(VulnerabilityCase) ownership transfer: %s",
                ownership_offer.id_,
            )

            # Wait for the FORWARDED offer (CM-21-005).
            # OfferCaseOwnershipTransferReceivedUseCase creates a NEW Offer
            # (forwarded_id) when the CaseActor processes Vendor1's Offer.  The
            # forwarded Offer lands in Coordinator's DataLayer under a
            # different ID; the original Offer only exists in the CaseActor's
            # DataLayer.  Polling for the original ID would never match.
            with demo_gate(
                "Forwarded Offer(VulnerabilityCase) delivered to Coordinator's"
                " DataLayer (CM-21-005)"
            ):
                ownership_offer_id = find_ownership_transfer_offer_for_actor(
                    client=coordinator_client,
                    case_id=case.id_,
                    transferee_id=coordinator.id_,
                    timeout_seconds=90.0,
                )
                logger.info(
                    "Forwarded ownership transfer offer ID: %s",
                    ownership_offer_id,
                )

                # Coordinator accepts the ownership transfer (TRIG-11-002).
                with demo_step(
                    "Coordinator accepts case ownership transfer (TRIG-11-002)"
                ):
                    accept_result = (
                        ActorSession(
                            client=coordinator_client,
                            actor=coordinator_in_coordinator,
                        )
                        .quiet()
                        .accept_case_ownership_transfer(
                            offer_id=ownership_offer_id
                        )
                    )
                    logger.info(
                        "Coordinator sent Accept(Offer(VulnerabilityCase)): %s",
                        accept_result.activity.id_,
                    )

    # The transfer reaches a replica in two hops: Accept → CaseActor inbox →
    # AcceptOwnershipTransferBT commit (CM-21-007), then CaseActor outbox →
    # Announce(CaseLedgerEntry) of the CASE_MANAGER's own update_case_participant
    # and update_case_owner entries that follow the Accept (CLP-07-013) → each
    # participant copies them.  Nothing else updates a replica —
    # the CaseActor's own node writes only the CaseActor's store (ADR-0073), so
    # Vendor1 learns of its own loss of ownership from the fan-out like anyone
    # else.  Gate on the commit first, read from the CaseActor's own store, so
    # a slow fan-out is reported as the fan-out being slow and not as the
    # transfer never having happened (EDF-06-002, #3602).  The replicas'
    # attributed_to comes from the update_case_owner entry, the last the
    # transfer commits, so that entry is the gate (CLP-07-013).
    with demo_gate(
        "CaseActor committed update_case_owner after the accepted transfer"
        " (CM-21-007, CLP-07-013)"
    ):
        wait_for_case_actor_ledger_event(
            client=case_actor_client,
            case_id=case.id_,
            event_type="update_case_owner",
        )

        # Temporal bound on the second hop (EDF-06-006, EDF-06-008): one
        # budget for the whole fan-out, because all three replicas are fed by
        # the same CaseActor outbox and the fan-out queues behind whatever
        # that outbox already holds (ADR-0112).  LATE_JOINER_TIMEOUT is the
        # budget the Reporter check below has bounded this same fan-out with
        # since #2789; sharing it caps the phase's worst case at 90 s instead
        # of 20 + 20 + 90 while no single replica is starved.
        fanout_budget = SharedBudget(LATE_JOINER_TIMEOUT)
        logger.info("Ownership-transfer fan-out budget: %r", fanout_budget)

        # Verify Vendor1's (the transferor's) replica shows the new owner.
        with demo_check(
            "Case attributed_to updated to Coordinator on Vendor1's DataLayer (AC-1)"
        ):
            wait_for_case_attributed_to(
                client=vendor_client,
                case_id=case.id_,
                expected_attributed_to=coordinator.id_,
                timeout_seconds=fanout_budget.remaining(),
            )

        # Also verify on Coordinator's side.
        with demo_check(
            "Case attributed_to updated to Coordinator on Coordinator's DataLayer"
        ):
            wait_for_case_attributed_to(
                client=coordinator_client,
                case_id=case.id_,
                expected_attributed_to=coordinator.id_,
                timeout_seconds=fanout_budget.remaining(),
            )

        # ADR-0053's own validation criterion: an actor outside the
        # negotiation learns of the completed transfer from the ledger
        # broadcast alone.  The Reporter is neither the old nor the new owner, so
        # its replica can only hold this entry if the CaseActor committed it
        # and fanned out Announce(CaseLedgerEntry) to every participant
        # (CM-21-007).
        with demo_check(
            "Reporter replica received the ownership-transfer ledger entry"
            " via Announce(CaseLedgerEntry) (CM-21-007, ADR-0053)"
        ):
            wait_for_event_type_in_ledger(
                client=reporter_client,
                case_id=case.id_,
                event_type="accept_case_ownership_transfer",
                timeout_seconds=fanout_budget.remaining(),
            )
        logger.info(
            "Ownership-transfer fan-out budget left: %r", fanout_budget
        )

    logger.info(
        "✓ Ownership transfer complete: Coordinator is now CASE_OWNER for %s",
        case.id_,
    )

    case = as_VulnerabilityCase.model_validate(
        vendor_client.get(vendor_client.dl_path(case.id_))
    )
    return case


def _phase_coordinator_invites_vendor2(
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    reporter: as_Actor,
    vendor: as_Actor,
    coordinator: as_Actor,
    coordinator_in_coordinator: as_Actor,
    case_actor_id: str,
    vendor2: as_Actor,
    vendor2_in_vendor2: as_Actor,
    case: as_VulnerabilityCase,
    offer: object,
    report: as_VulnerabilityReport,
) -> None:
    """Coordinator (new CASE_OWNER) invites Vendor2; Vendor2 runs RM triage."""
    logger.info("─" * 80)
    logger.info("Phase 3: Coordinator invites Vendor2 (AC-2)")
    logger.info("─" * 80)

    # Post to the Coordinator's OWN container.  A trigger URL is built from the
    # named actor's bare ID against the client's base_url, so naming an actor a
    # container does not host 404s — which is exactly what posting Coordinator's
    # trigger to vendor_client did.
    #
    # The Coordinator's trigger sends its own Offer to the CASE_MANAGER, and
    # the CaseActor emits the Invite (CM-17-007, ADR-0109).  So the Invite goes
    # out as the CaseActor and Vendor2's Accept routes back to the CaseActor
    # rather than to the Coordinator, letting AcceptInviteActorToCaseBT run
    # (PCR-08-007, PCR-08-008).  The check on the delivered Invite below is
    # what holds that property honest.
    #
    # run_case_invite_chain nests the accept and the replica wait inside the
    # delivery gate (ADR-0058 nested-block model, EDF-06-005, #3038).
    run_case_invite_chain(
        case=case,
        case_manager_client=case_actor_client,
        invitee_name="Vendor2",
        invitee_client=vendor2_client,
        invitee=vendor2,
        invitee_in_own_container=vendor2_in_vendor2,
        inviter=CaseInviter(
            name="Coordinator",
            client=coordinator_client,
            actor=coordinator_in_coordinator,
            role=CVDRole.VENDOR,
        ),
        invite_timeout=90.0,
        replica_timeout=90.0,
        expect_emitted_by=EmittedBy(
            case_actor_id=case_actor_id,
            consequence=(
                "Vendor2's Accept would route to the Coordinator and"
                " AcceptInviteActorToCaseBT would not run"
            ),
        ),
    )

    # All 5 participants (Reporter + Vendor1 + Coordinator + Vendor2 + CaseActor)
    # present is the causal precondition for Vendor2's RM triage below: a
    # demo_gate — not demo_check — so a timeout skips the doomed triage rather
    # than cascading (DEMOCI-01-011, vultron/demo/AGENTS.md § "Never Wrap a
    # Causal Wait in demo_check").
    with demo_gate(
        "Vendor1 case has all 5 participants before Vendor2 RM triage"
    ):
        wait_for_case_participants(
            vendor_client=vendor_client,
            case_id=case.id_,
            expected_actor_ids={
                reporter.id_,
                vendor.id_,
                coordinator.id_,
                vendor2.id_,
            },
            timeout_seconds=LATE_JOINER_TIMEOUT,
        )
        logger.info("✓ Vendor2 joined case (%d participants)", 5)

        with demo_check(
            "Reporter's DataLayer received case replica before Vendor2 RM triage"
        ):
            wait_for_case_on_container(
                client=reporter_client,
                case_id=case.id_,
                timeout_seconds=90.0,
            )

        # CM-11-002: Vendor2 joined via invite-accept — run RM triage cycle.
        run_invite_path_rm_triage(
            invited_client=vendor2_client,
            invited_actor=vendor2_in_vendor2,
            offer=offer,
            report=report,
            reporter=reporter,
            auth_client=case_actor_client,
            case=case,
            invited_obj=vendor2,
            timeout_seconds=90.0,
        )


def _phase_sync_verification(
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    vendor: as_Actor,
    reporter: as_Actor,
    coordinator: as_Actor,
    vendor2: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Verify LedgerFanout replication for Reporter, Coordinator, and Vendor2 replicas."""
    logger.info("─" * 80)
    logger.info("Phase 4: Replica synchronization verification")
    logger.info("─" * 80)

    run_sync_verification_phase(
        auth_client=vendor_client,
        auth_label="Vendor1",
        auth_actor_id=vendor.id_,
        reporter_client=reporter_client,
        reporter_actor_id=reporter.id_,
        replicas=[
            (reporter_client, "Reporter"),
            (coordinator_client, "Coordinator"),
            (vendor2_client, "Vendor2"),
        ],
        case_id=case.id_,
        expected_participant_ids={
            reporter.id_,
            vendor.id_,
            coordinator.id_,
            vendor2.id_,
        },
        # Vendor2 joins by invitation after the early replicas exist (#2202).
        late_joiners=(vendor2_client,),
        state_checks=[
            (reporter_client, "Reporter"),
            (vendor2_client, "Vendor2"),
        ],
    )

    logger.info("✓ All replicas synchronized")


def _phase_notes_exchange(
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    reporter_in_reporter: as_Actor,
    vendor_in_vendor: as_Actor,
    coordinator_in_coordinator: as_Actor,
    vendor2_in_vendor2: as_Actor,
    case: as_VulnerabilityCase,
) -> tuple[as_Note | None, as_Note | None, as_Note | None, as_Note | None]:
    """Run a four-way note exchange among all participants.

    Emits ``add_note_to_case`` events into the canonical case ledger,
    exercising the note-threading path and satisfying the universal
    ``add_note_to_case`` invariant asserted by the case-ledger harness.
    """
    logger.info("─" * 80)
    logger.info("Phase 4b: Notes exchange")
    logger.info("─" * 80)

    question_note = participant_adds_note_to_case(
        posting_client=reporter_client,
        watching_client=vendor_client,
        poster=reporter_in_reporter,
        case=case,
        note_name="Question from Reporter",
        note_content=(
            "Is there a workaround available while the patch is being developed?"
        ),
    )

    vendor_reply = participant_adds_note_to_case(
        posting_client=vendor_client,
        watching_client=vendor_client,
        poster=vendor_in_vendor,
        case=case,
        note_name="Vendor1 Response",
        note_content=(
            "Yes, disabling the affected module is an effective interim workaround."
        ),
        in_reply_to=question_note.id_ if question_note is not None else None,
    )

    coordinator_note = participant_adds_note_to_case(
        posting_client=coordinator_client,
        watching_client=vendor_client,
        poster=coordinator_in_coordinator,
        case=case,
        note_name="Coordinator Update",
        note_content=(
            "As the new case owner, I confirm both Vendor1 and Vendor2 are "
            "engaged. Target disclosure in 30 days."
        ),
        in_reply_to=vendor_reply.id_ if vendor_reply is not None else None,
    )

    vendor2_note = participant_adds_note_to_case(
        posting_client=vendor2_client,
        watching_client=vendor_client,
        poster=vendor2_in_vendor2,
        case=case,
        note_name="Vendor2 Status Update",
        note_content=(
            "Vendor2 confirms the issue affects our component as well. "
            "We will align our fix timeline with Vendor1."
        ),
        in_reply_to=(
            coordinator_note.id_ if coordinator_note is not None else None
        ),
    )

    logger.info(
        "✓ Notes exchange complete (four notes committed to case ledger)"
    )
    return question_note, vendor_reply, coordinator_note, vendor2_note


def _phase_fix_lifecycle(
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    vendor: as_Actor,
    vendor_in_vendor: as_Actor,
    vendor2: as_Actor,
    vendor2_in_vendor2: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Advance both vendors through fix-ready and fix-deployed paths."""
    logger.info("─" * 80)
    logger.info(
        "Phase 5: Fix lifecycle — both vendors: VFd (fix ready); vendors stop at VFd (CSB-15-002)"
    )
    logger.info("─" * 80)

    with demo_gate(
        "vendor RM ∈ {ACCEPTED,DEFERRED,CLOSED} before notify-fix-ready (CSB-18-001)"
    ):
        wait_for_participant_rm_state(
            client=vendor_client,
            case_id=case.id_,
            actor_id=vendor.id_,
            expected_states={RM.ACCEPTED, RM.DEFERRED, RM.CLOSED},
        )
        with demo_step(f"Actor {ref_id(vendor_in_vendor)} reports fix ready"):
            ActorSession(
                client=vendor_client, actor=vendor_in_vendor
            ).with_case(case).quiet().notify_fix_ready()
        with demo_check("Vendor1 participant vf_state transitions to VF"):
            wait_for_participant_vf_state(
                client=vendor_client,
                case_id=case.id_,
                actor_id=vendor.id_,
                expected_states={CS_vf.VF},
            )

    with demo_gate(
        "vendor2 RM ∈ {ACCEPTED,DEFERRED,CLOSED} before notify-fix-ready (CSB-18-001)"
    ):
        wait_for_participant_rm_state(
            client=vendor2_client,
            case_id=case.id_,
            actor_id=vendor2.id_,
            expected_states={RM.ACCEPTED, RM.DEFERRED, RM.CLOSED},
        )
        with demo_step(
            f"Actor {ref_id(vendor2_in_vendor2)} reports fix ready"
        ):
            ActorSession(
                client=vendor2_client, actor=vendor2_in_vendor2
            ).with_case(case).quiet().notify_fix_ready()
        with demo_check("Vendor2 participant vf_state transitions to VF"):
            wait_for_participant_vf_state(
                client=vendor2_client,
                case_id=case.id_,
                actor_id=vendor2.id_,
                expected_states={CS_vf.VF},
            )

    with demo_check(
        "Reporter replica shows both vendors CS include F (fix ready)"
    ):
        wait_for_participant_vf_state(
            client=vendor_client,
            case_id=case.id_,
            actor_id=vendor.id_,
            expected_states={CS_vf.VF},
        )
        wait_for_participant_vf_state(
            client=reporter_client,
            case_id=case.id_,
            actor_id=vendor.id_,
            expected_states={CS_vf.VF},
        )
        verify_fix_ready(
            receiver_client=vendor_client,
            reporter_client=reporter_client,
            case_id=case.id_,
            receiver_actor_id=vendor.id_,
        )

    with demo_check(
        "Reporter replica shows both vendors CS include F (fix ready) — vendors stop at VFd"
    ):
        wait_for_participant_vf_state(
            client=vendor_client,
            case_id=case.id_,
            actor_id=vendor.id_,
            expected_states={CS_vf.VF},
        )
        wait_for_participant_vf_state(
            client=reporter_client,
            case_id=case.id_,
            actor_id=vendor.id_,
            expected_states={CS_vf.VF},
        )
        verify_fix_ready(
            receiver_client=vendor_client,
            reporter_client=reporter_client,
            case_id=case.id_,
            receiver_actor_id=vendor.id_,
        )


def _phase_publication(
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    vendor: as_Actor,
    vendor_in_vendor: as_Actor,
    vendor2: as_Actor,
    vendor2_in_vendor2: as_Actor,
    reporter: as_Actor,
    reporter_in_reporter: as_Actor,
    coordinator: as_Actor,
    coordinator_in_coordinator: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Run publication notifications and verify public disclosure state."""
    logger.info("─" * 80)
    logger.info(
        "Phase 6: Publication — CS.VFDPxa + embargo teardown (EM.EXITED)"
    )
    logger.info("─" * 80)

    # Realistic CVD publication order: vendors publish their advisories first,
    # then Reporter may publish an independent writeup, then Coordinator publishes
    # last as the CASE_OWNER whose notify-published triggers embargo teardown
    # (DEMOMA-07-003 step 4).
    with demo_step(
        f"Actor {ref_id(vendor_in_vendor)} reports vulnerability publicly disclosed"
    ):
        ActorSession(client=vendor_client, actor=vendor_in_vendor).with_case(
            case
        ).quiet().notify_published()
    with demo_step(
        f"Actor {ref_id(vendor2_in_vendor2)} reports vulnerability publicly disclosed"
    ):
        ActorSession(
            client=vendor2_client, actor=vendor2_in_vendor2
        ).with_case(case).quiet().notify_published()
    with demo_step(
        f"Actor {ref_id(reporter_in_reporter)} reports vulnerability publicly disclosed"
    ):
        ActorSession(
            client=reporter_client, actor=reporter_in_reporter
        ).with_case(case).quiet().notify_published()

    # Coordinator publishes last — as CASE_OWNER this triggers embargo teardown.
    with demo_step(
        f"Actor {ref_id(coordinator_in_coordinator)} reports vulnerability publicly disclosed"
    ):
        ActorSession(
            client=coordinator_client, actor=coordinator_in_coordinator
        ).with_case(case).quiet().notify_published()

    with demo_check(
        "Embargo terminated (EM.EXITED) after Coordinator (CASE_OWNER) reports published"
    ):
        wait_for_case_em_terminated(
            client=coordinator_client,
            case_id=case.id_,
        )

    with demo_check(
        "All replicas CS.VFdPxa, EM.EXITED, all participants public-aware"
    ):
        for _label, client in [
            ("coordinator", coordinator_client),
            ("vendor", vendor_client),
            ("vendor2", vendor2_client),
            ("reporter", reporter_client),
        ]:
            wait_for_case_em_terminated(
                client=client,
                case_id=case.id_,
            )
        wait_for_participant_vf_state(
            client=vendor_client,
            case_id=case.id_,
            actor_id=vendor.id_,
            expected_states={CS_vf.VF},
        )
        wait_for_participant_vf_state(
            client=reporter_client,
            case_id=case.id_,
            actor_id=vendor.id_,
            expected_states={CS_vf.VF},
        )
        verify_publicly_disclosed(
            receiver_client=vendor_client,
            reporter_client=reporter_client,
            case_id=case.id_,
            receiver_actor_id=vendor.id_,
        )


def _phase_case_closure(
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    vendor: as_Actor,
    vendor_in_vendor: as_Actor,
    vendor2: as_Actor,
    vendor2_in_vendor2: as_Actor,
    reporter: as_Actor,
    reporter_in_reporter: as_Actor,
    coordinator: as_Actor,
    coordinator_in_coordinator: as_Actor,
    case: as_VulnerabilityCase,
    case_actor_client: DataLayerClient,
) -> None:
    """Close the case from all four participants and verify terminal state.

    Vendor1, Vendor2 and the Reporter leave first; the Coordinator, the Case
    Owner since the handoff, leaves last, once their departures are recorded
    (CM-23-015).  The handoff moves ownership, not the CASE_MANAGER, which
    stays on the dedicated case-actor container.
    """
    logger.info("─" * 80)
    logger.info("Phase 7: Case closure — all participants RM.CLOSED")
    logger.info("─" * 80)

    close_case_owner_last(
        case=case,
        authority_client=case_actor_client,
        others=[
            CaseLeaver(client=vendor_client, actor=vendor_in_vendor),
            CaseLeaver(client=vendor2_client, actor=vendor2_in_vendor2),
            CaseLeaver(client=reporter_client, actor=reporter_in_reporter),
        ],
        owner=CaseLeaver(
            client=coordinator_client, actor=coordinator_in_coordinator
        ),
    )


def _phase_dump_case_ledgers(
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    case: as_VulnerabilityCase,
    demo_name: str = "rvcv-handoff",
) -> None:
    """Dump case ledger entries from each actor container to JSONL files.

    Thin scenario-specific wrapper over
    :func:`~vultron.demo.helpers.ledger_dump.dump_case_ledgers`, which owns the
    per-actor export, the 404 handling, and the dump manifest. This function
    only names RVCV-handoff's participants and where each ledger lives.
    """
    # Route keys come from each client's own actor id, not its display
    # name: the key selects the store (ADR-0073), so a literal is right
    # only while the scenario seeds deterministic named ids.
    targets = [
        LedgerDumpTarget(
            "reporter",
            reporter_client,
            replica_route_key(reporter_client, "reporter"),
        ),
        LedgerDumpTarget(
            "vendor", vendor_client, replica_route_key(vendor_client, "vendor")
        ),
        LedgerDumpTarget(
            "coordinator",
            coordinator_client,
            replica_route_key(coordinator_client, "coordinator"),
        ),
        LedgerDumpTarget(
            "vendor2",
            vendor2_client,
            replica_route_key(vendor2_client, "vendor2"),
        ),
        # The canonical ledger, from the dedicated case-actor container.
        case_actor_dump_target(case_actor_client),
    ]

    dump_case_ledgers(demo_name=demo_name, case=case, targets=targets)


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


def run_rvcv_handoff_demo(
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    reporter_id: str | None = None,
    vendor_id: str | None = None,
    coordinator_id: str | None = None,
    case_actor_id: str | None = None,
    vendor2_id: str | None = None,
) -> None:
    """Orchestrate the RVCV-handoff CVD workflow."""
    with scenario_harness("rvcv-handoff") as harness:
        logger.info("=" * 80)
        logger.info(
            "RVCV-HANDOFF DEMO: Reporter + Vendor1 → Coordinator (ownership) + Vendor2"
        )
        logger.info("=" * 80)
        logger.info("Reporter container:      %s", reporter_client.base_url)
        logger.info("Vendor1 container:     %s", vendor_client.base_url)
        logger.info("Coordinator container: %s", coordinator_client.base_url)
        logger.info("CaseActor container:   %s", case_actor_client.base_url)
        logger.info("Vendor2 container:     %s", vendor2_client.base_url)

        (
            reporter,
            vendor,
            vendor_in_vendor,
            coordinator,
            coordinator_in_coordinator,
            vendor2,
            report,
            offer,
            case,
        ) = _phase_report_submission(
            reporter_client,
            vendor_client,
            coordinator_client,
            case_actor_client,
            vendor2_client,
            reporter_id,
            vendor_id,
            coordinator_id,
            vendor2_id,
        )

        # Register the dump as soon as there is a case to dump, so every phase
        # below can fail without costing us the ledgers (ISSUE-2239).
        harness.dump_with(
            lambda: _phase_dump_case_ledgers(
                reporter_client=reporter_client,
                vendor_client=vendor_client,
                coordinator_client=coordinator_client,
                vendor2_client=vendor2_client,
                case_actor_client=case_actor_client,
                case=case,
                demo_name=harness.demo_name,
            )
        )

        # The case's CaseActor is the dedicated case-actor container's identity
        # (CP-08-008, DEMOMA-06-004), and it stays the CASE_MANAGER through the
        # ownership handoff.  Read it off the case's own participants rather
        # than constructing it from a slug, so the Invite check below asserts
        # the actor the case actually names.
        dynamic_case_actor_id = find_case_actor_participant_id(
            vendor_client, case.id_
        )
        if dynamic_case_actor_id is None:
            raise AssertionError(
                "CaseActor participant not found in case — cannot route Vendor2 Accept"
            )
        logger.info("CaseActor participant ID: %s", dynamic_case_actor_id)

        vendor2_in_vendor2 = get_actor_by_id(vendor2_client, vendor2.id_)
        reporter_in_reporter = get_actor_by_id(reporter_client, reporter.id_)

        case = _phase_ownership_handoff(
            reporter_client=reporter_client,
            vendor_client=vendor_client,
            coordinator_client=coordinator_client,
            case_actor_client=case_actor_client,
            reporter=reporter,
            vendor=vendor,
            vendor_in_vendor=vendor_in_vendor,
            coordinator=coordinator,
            coordinator_in_coordinator=coordinator_in_coordinator,
            case=case,
        )

        _phase_coordinator_invites_vendor2(
            reporter_client=reporter_client,
            vendor_client=vendor_client,
            coordinator_client=coordinator_client,
            case_actor_client=case_actor_client,
            vendor2_client=vendor2_client,
            reporter=reporter,
            vendor=vendor,
            coordinator=coordinator,
            coordinator_in_coordinator=coordinator_in_coordinator,
            case_actor_id=dynamic_case_actor_id,
            vendor2=vendor2,
            vendor2_in_vendor2=vendor2_in_vendor2,
            case=case,
            offer=offer,
            report=report,
        )

        # Verify case active now that all participants have joined.
        with demo_check(
            "M1: required participants (≥5), EM.ACTIVE, reporter + coordinator have replicas"
        ):
            verify_case_active(
                receiver_client=vendor_client,
                reporter_client=reporter_client,
                case_id=case.id_,
                receiver_actor_id=vendor.id_,
                reporter_actor_id=reporter.id_,
            )

        _phase_sync_verification(
            reporter_client,
            vendor_client,
            coordinator_client,
            vendor2_client,
            vendor,
            reporter,
            coordinator,
            vendor2,
            case,
        )
        _phase_notes_exchange(
            reporter_client,
            vendor_client,
            coordinator_client,
            vendor2_client,
            reporter_in_reporter,
            vendor_in_vendor,
            coordinator_in_coordinator,
            vendor2_in_vendor2,
            case,
        )
        _phase_fix_lifecycle(
            reporter_client,
            vendor_client,
            vendor2_client,
            vendor,
            vendor_in_vendor,
            vendor2,
            vendor2_in_vendor2,
            case,
        )
        _phase_publication(
            reporter_client,
            vendor_client,
            coordinator_client,
            vendor2_client,
            vendor,
            vendor_in_vendor,
            vendor2,
            vendor2_in_vendor2,
            reporter,
            reporter_in_reporter,
            coordinator,
            coordinator_in_coordinator,
            case,
        )
        _phase_case_closure(
            reporter_client,
            vendor_client,
            coordinator_client,
            vendor2_client,
            vendor,
            vendor_in_vendor,
            vendor2,
            vendor2_in_vendor2,
            reporter,
            reporter_in_reporter,
            coordinator,
            coordinator_in_coordinator,
            case,
            case_actor_client,
        )

    logger.info("=" * 80)
    logger.info(
        "RVCV-HANDOFF DEMO COMPLETE ✓  (ownership transfer + VFDPxa full lifecycle)"
    )
    logger.info("=" * 80)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


@scenario(
    name="rvcv-handoff",
    label="RVCV-handoff",
    participants="Reporter + Vendor1 → Coordinator + Vendor2",
    feature="Case-ownership transfer to coordinator",
    in_pr_set=True,
)
def main(
    skip_health_check: bool = False,
    reporter_url: str | None = None,
    vendor_url: str | None = None,
    coordinator_url: str | None = None,
    case_actor_url: str | None = None,
    vendor2_url: str | None = None,
    reporter_id: str | None = None,
    vendor_id: str | None = None,
    coordinator_id: str | None = None,
    case_actor_id: str | None = None,
    vendor2_id: str | None = None,
) -> None:
    """Entry point for the RVCV-handoff CVD workflow demo.

    Args:
        skip_health_check: Skip the server availability check.
        reporter_url: Override base URL for the Reporter container.
        vendor_url: Override base URL for the Vendor1 container.
        coordinator_url: Override base URL for the Coordinator container.
        case_actor_url: Override base URL for the CaseActor container.
        vendor2_url: Override base URL for the Vendor2 container.
        reporter_id: Optional deterministic URI for the Reporter actor.
        vendor_id: Optional deterministic URI for the Vendor1 actor.
        coordinator_id: Optional deterministic URI for the Coordinator actor.
        case_actor_id: Optional deterministic URI for the CaseActor actor.
        vendor2_id: Optional deterministic URI for the Vendor2 actor.
    """
    f_url = reporter_url or REPORTER_BASE_URL
    v_url = vendor_url or VENDOR_BASE_URL
    c_url = coordinator_url or COORDINATOR_BASE_URL
    ca_url = case_actor_url or CASE_ACTOR_BASE_URL
    v2_url = vendor2_url or VENDOR2_BASE_URL

    reporter_client = DataLayerClient(base_url=f_url)
    vendor_client = DataLayerClient(base_url=v_url)
    coordinator_client = DataLayerClient(base_url=c_url)
    case_actor_client = bound_case_actor_client(ca_url)
    vendor2_client = DataLayerClient(base_url=v2_url)

    if not skip_health_check:
        targets: list[tuple[str, DataLayerClient]] = [
            ("Reporter", reporter_client),
            ("Vendor1", vendor_client),
            ("Coordinator", coordinator_client),
            ("CaseActor", case_actor_client),
            ("Vendor2", vendor2_client),
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

    # scenario_harness() inside run_rvcv_handoff_demo() owns the failure
    # accumulator: it resets it, always dumps the case ledgers, and asserts
    # success — so a failure here never costs us the artifacts (ISSUE-2239).
    run_rvcv_handoff_demo(
        reporter_client=reporter_client,
        vendor_client=vendor_client,
        coordinator_client=coordinator_client,
        case_actor_client=case_actor_client,
        vendor2_client=vendor2_client,
        reporter_id=reporter_id,
        vendor_id=vendor_id,
        coordinator_id=coordinator_id,
        case_actor_id=case_actor_id,
        vendor2_id=vendor2_id,
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
