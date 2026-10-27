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

"""RCV-Reject three-actor CVD workflow demo (Reporter + Coordinator + Vendor rejection).

Orchestrates a CVD workflow where Coordinator receives the Reporter's report,
creates the case (CASE_OWNER), the CaseActor service manages the ledger.
Coordinator invites Vendor (``invite-actor-to-case``), but Vendor rejects the
invitation (``reject-case-invite``).  Vendor is therefore NOT added to the case
as a participant.  Reporter and Coordinator continue to close out the case through
publication and closure.

Key difference from the RCV scenario: Vendor rejects the case invitation
(RM-layer rejection via ``Reject(Invite(actor, case))``) so Vendor never
becomes a case participant and has no case ledger replica.

Spec: GitHub issue #2047 (rcv-reject demo scenario).
"""

import logging
import sys

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
    verify_publicly_disclosed,
)
from vultron.demo.helpers.notes import participant_adds_note_to_case
from vultron.demo.helpers.polling import (
    wait_for_case_em_terminated,
    wait_for_case_participants,
    wait_for_participant_rm_state,
    wait_for_semantic_type_in_ledger,
)
from vultron.demo.helpers.seeding import (
    get_actor_by_id,
    reset_containers as _reset_containers,
    seed_containers_rcv,
)
from vultron.demo.helpers.sync import (
    run_sync_verification_phase,
)
from vultron.demo.helpers.verification import _check_participant_rm_state_in
from vultron.demo.helpers.workflow import (
    reporter_submits_report,
    run_direct_path_rm_triage,
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
    verify_object_stored,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Offer
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
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
        name="coordinator",
        url_env="VULTRON_COORDINATOR_BASE_URL",
        default_url="http://localhost:7903/api/v2",
        url_help="Base URL of the Coordinator container API "
        "(env: VULTRON_COORDINATOR_BASE_URL).",
        has_id=True,
        id_help="Deterministic full URI for the Coordinator actor (optional).",
    ),
    ActorRole(
        name="vendor",
        url_env="VULTRON_VENDOR_BASE_URL",
        default_url="http://localhost:7902/api/v2",
        url_help="Base URL of the Vendor container API "
        "(env: VULTRON_VENDOR_BASE_URL).",
        has_id=True,
        id_help="Deterministic full URI for the Vendor actor (optional).",
    ),
    case_actor_role("http://localhost:7905/api/v2"),
]
_ROLES = role_map(ROLES)

REPORTER_BASE_URL = _ROLES["reporter"].url
VENDOR_BASE_URL = _ROLES["vendor"].url
COORDINATOR_BASE_URL = _ROLES["coordinator"].url
CASE_ACTOR_BASE_URL = _ROLES["case-actor"].url

#: ``vultron-demo rcv-reject --help`` text. Lives here rather than in ``cli.py``
#: because the sub-command is generated from the registry and the scenario
#: module is the only place that knows what its own workflow does.
CLI_HELP = """Run the RCV-Reject (Reporter + Coordinator + Vendor rejection) CVD demo (#2047).

Coordinator receives the Reporter's report, creates the authoritative case
(CASE_OWNER), and the CaseActor service manages the case ledger.  Coordinator
invites Vendor, but Vendor rejects the invitation via ``reject-case-invite``.
Vendor is NOT added as a case participant.  Reporter and Coordinator proceed to
publication and closure.

\b
Workflow:
  1. Seed Reporter, Coordinator, and Vendor containers.
  2. Reporter submits a vulnerability report to Coordinator's inbox.
  3. Coordinator validates the report and engages the case (CASE_OWNER).
  4. Coordinator invites Vendor directly (invite-actor-to-case).
  5. Vendor rejects the case invitation (reject-case-invite).
  6. Verify participant count stable at 3 (Vendor not added).
  7. Two-way notes exchange between Reporter and Coordinator.
  8. Coordinator and Reporter publish; embargo terminates (EM.EXITED).
  9. The Reporter closes the case, then the Coordinator, the Case Owner,
     closes it last (every RM.CLOSED in the Case Actor's store).
"""

# Deterministic actor IDs from docker-compose-multi-actor.yml (D5-1-G3).
REPORTER_ACTOR_ID = "http://reporter:7999/api/v2/actors/reporter"
COORDINATOR_ACTOR_ID = "http://coordinator:7999/api/v2/actors/coordinator"
VENDOR_ACTOR_ID = "http://vendor:7999/api/v2/actors/vendor"
CASE_ACTOR_ACTOR_ID = "http://case-actor:7999/api/v2/actors/case-actor"


def reset_containers(
    reporter_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_actor_client: DataLayerClient,
) -> None:
    """Reset RCV-Reject containers to a clean baseline."""
    targets: list[tuple[str, DataLayerClient]] = [
        ("Reporter", reporter_client),
        ("Coordinator", coordinator_client),
        ("Vendor", vendor_client),
    ]
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
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    reporter_id: str | None,
    coordinator_id: str | None,
    vendor_id: str | None,
) -> tuple[
    as_Actor,
    as_Actor,
    as_Actor,
    as_Actor,
    as_Actor,
    as_VulnerabilityReport,
    as_Offer,
    as_VulnerabilityCase,
]:
    """Reset, seed, Reporter submits report to Coordinator, Coordinator engages case."""
    logger.info("─" * 80)
    logger.info("Phase 1: Report submission — Reporter → Coordinator")
    logger.info("─" * 80)

    reset_containers(
        reporter_client=reporter_client,
        coordinator_client=coordinator_client,
        vendor_client=vendor_client,
        case_actor_client=case_actor_client,
    )

    reporter = coordinator = vendor = None
    with demo_step("Seeding Reporter, Coordinator, and Vendor containers"):
        reporter, coordinator, vendor = seed_containers_rcv(
            reporter_client=reporter_client,
            coordinator_client=coordinator_client,
            vendor_client=vendor_client,
            reporter_actor_id=reporter_id,
            coordinator_actor_id=coordinator_id,
            vendor_actor_id=vendor_id,
            case_actor_client=case_actor_client,
        )

    coordinator_in_coordinator = get_actor_by_id(
        coordinator_client, coordinator.id_
    )

    report, offer = reporter_submits_report(
        receiver_client=coordinator_client,
        reporter=reporter,
        receiver=coordinator_in_coordinator,
        reporter_client=reporter_client,
    )
    case = run_direct_path_rm_triage(
        receiver_client=coordinator_client,
        receiver=coordinator_in_coordinator,
        offer=offer,
    )

    # Wait for Coordinator + Reporter + CaseActor (3 participants).
    with demo_check(
        "Coordinator case reflects Reporter + Coordinator participants"
    ):
        wait_for_case_participants(
            vendor_client=coordinator_client,
            case_id=case.id_,
            expected_actor_ids={reporter.id_, coordinator.id_},
        )

    with demo_check("M1: ≥3 participants, EM.ACTIVE, Reporter has replica"):
        verify_case_active(
            receiver_client=coordinator_client,
            reporter_client=reporter_client,
            case_id=case.id_,
            receiver_actor_id=coordinator.id_,
            reporter_actor_id=reporter.id_,
        )

    case = as_VulnerabilityCase.model_validate(
        coordinator_client.get(coordinator_client.dl_path(case.id_))
    )
    reporter_in_reporter = get_actor_by_id(reporter_client, reporter.id_)
    return (
        reporter,
        reporter_in_reporter,
        coordinator,
        coordinator_in_coordinator,
        vendor,
        report,
        offer,
        case,
    )


def _phase_invite_vendor_reject(
    coordinator_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    vendor_client: DataLayerClient,
    reporter: as_Actor,
    coordinator_in_coordinator: as_Actor,
    coordinator: as_Actor,
    vendor: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Coordinator invites Vendor; Vendor rejects the invitation.

    Vendor sends Reject(Invite(actor, case)) back to the CaseActor via the
    ``reject-case-invite`` trigger.  The CaseActor records a
    ``reject_invite_actor_to_case`` ledger entry.

    ADR-0114 / CM-11-006: at invite-send time
    ``CreateInertInviteeParticipantNode`` adds Vendor to
    ``actor_participant_index`` as an *inert* participant (``joined=False``,
    RM ``RECEIVED``).  After the Reject, CM-11-007 moves that record to
    RM ``CLOSED`` — Vendor is present in the index but never active, and no
    case content is delivered to it (DEMOMA-27-002).
    """
    logger.info("─" * 80)
    logger.info("Phase 2: Coordinator invites Vendor; Vendor rejects")
    logger.info("─" * 80)

    vendor_in_vendor = get_actor_by_id(vendor_client, vendor.id_)

    # The chain's gate and Vendor's reject are nested inside the invite step
    # (ADR-0058 nested-block model, EDF-06-005, #3038).
    run_case_invite_chain(
        case=case,
        case_manager_client=case_actor_client,
        invitee_name="Vendor",
        invitee_client=vendor_client,
        invitee=vendor,
        invitee_in_own_container=vendor_in_vendor,
        inviter=CaseInviter(
            name="Coordinator",
            client=coordinator_client,
            actor=coordinator_in_coordinator,
            role=CVDRole.VENDOR,
        ),
        respond="reject",
        invite_timeout=20.0,
    )

    # Gate on Vendor's Reject being committed before checking participant
    # state.  The Reject is a case event, admitted and ledgered like an Accept
    # (CLP-02-012).  It is self-contained on the CaseActor (CLP-10-006) — no
    # participant-effect Announce is sent, so the entry is only visible in the
    # CaseActor's own store, on the dedicated case-actor container and read
    # through case_actor_client.  Using demo_gate here ensures that the participant
    # state checks are skipped (rather than run against stale state) if the
    # CaseActor has not yet committed the Reject's entry.
    with demo_gate(
        "reject_invite_actor_to_case committed (causal gate before participant state check)"
    ):
        wait_for_semantic_type_in_ledger(
            client=case_actor_client,
            case_id=case.id_,
            semantic_type="reject_invite_actor_to_case",
        )
        # DEMOMA-27-002, CM-11-006: Vendor IS in actor_participant_index from the
        # Invite-send moment (inert record created by CreateInertInviteeParticipantNode).
        # Reporter and Coordinator must also be present.  Read from the CaseActor's
        # store: a replica stores the record the CASE_MANAGER's
        # create_case_participant entry carries (ADR-0114), but this scenario
        # checks the CASE_MANAGER's own record, the one
        # CreateInertInviteeParticipantNode writes.
        with demo_check(
            "Vendor in actor_participant_index after invite (inert record, CM-11-006)"
        ):
            wait_for_case_participants(
                vendor_client=case_actor_client,
                case_id=case.id_,
                expected_actor_ids={reporter.id_, coordinator.id_, vendor.id_},
            )
        # DEMOMA-27-002, CM-11-007: Vendor's inert record must be at RM.CLOSED
        # after the rejection — it was never active (joined=False throughout).
        # Read from the CaseActor's authoritative store (not coordinator's
        # replica): the reject tree has no emit node to propagate the
        # participant state change to replicas (ADR-0073).
        #
        # The reject tree commits the ledger entry (the gate above) BEFORE its
        # ApplyInviteRejectToParticipantNode effect writes RM.CLOSED, so the
        # committed-entry gate is a proxy that proves the handler started, not
        # that the RM close landed (EDF-06-002, EDF-06-003).  Wait on the
        # committed effect itself before the one-shot check.
        wait_for_participant_rm_state(
            client=case_actor_client,
            case_id=str(case.id_),
            actor_id=str(vendor.id_),
            expected_states={RM.CLOSED},
        )
        with demo_check(
            "Vendor participant at RM.CLOSED after rejection (never active, DEMOMA-27-002)"
        ):
            _check_participant_rm_state_in(
                client=case_actor_client,
                case_id=str(case.id_),
                actor_id=str(vendor.id_),
                expected_states={RM.CLOSED},
                label="Vendor (rejected invitee)",
            )
    logger.info(
        "✓ M2: Vendor rejected invite — inert record at RM.CLOSED, never active"
        " (DEMOMA-27-002)"
    )


def _phase_sync_verification(
    reporter_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    reporter: as_Actor,
    coordinator: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Wait for Reporter to replicate all Phase 2 ledger entries before Phase 3.

    The Reporter must hold the case and all coordinator-committed ledger entries
    before the notes exchange begins; without this gate the
    ``add-note-to-case`` trigger on the Reporter container may fail because the
    Reporter's DataLayer has not yet received the case replica or the
    ledger tail ending in Vendor's ``Reject`` entry from the CaseActor fan-out
    (SYNC-15-001).

    The Vendor declined and never joins, so this scenario declares no
    participant expectation and no replica state check.
    """
    logger.info("─" * 80)
    logger.info("Phase 2.5: Reporter ledger sync verification")
    logger.info("─" * 80)

    run_sync_verification_phase(
        auth_client=coordinator_client,
        auth_label="Coordinator",
        auth_actor_id=coordinator.id_,
        reporter_client=reporter_client,
        reporter_actor_id=reporter.id_,
        replicas=[(reporter_client, "Reporter")],
        case_id=case.id_,
    )


def _phase_notes_exchange(
    reporter_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    reporter_in_reporter: as_Actor,
    coordinator_in_coordinator: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Run a two-way note exchange between Reporter and Coordinator."""
    logger.info("─" * 80)
    logger.info("Phase 3: Notes exchange (Reporter + Coordinator)")
    logger.info("─" * 80)

    question_note = participant_adds_note_to_case(
        posting_client=reporter_client,
        watching_client=coordinator_client,
        poster=reporter_in_reporter,
        case=case,
        note_name="Question from Reporter",
        note_content=(
            "Vendor rejected the invitation. "
            "What is the plan for coordinated disclosure?"
        ),
    )

    participant_adds_note_to_case(
        posting_client=coordinator_client,
        watching_client=coordinator_client,
        poster=coordinator_in_coordinator,
        case=case,
        note_name="Coordinator Response",
        note_content=(
            "Vendor declined to participate. "
            "We will proceed with Reporter-only disclosure. "
            "Embargo will be terminated and we will publish."
        ),
        in_reply_to=question_note.id_ if question_note is not None else None,
    )

    logger.info(
        "✓ Notes exchange complete (two notes committed to case ledger)"
    )


def _phase_publication(
    reporter_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    coordinator_in_coordinator: as_Actor,
    reporter_in_reporter: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Coordinator and Reporter publish; embargo terminates (EM.EXITED)."""
    logger.info("─" * 80)
    logger.info("Phase 4: Publication — embargo teardown (EM.EXITED)")
    logger.info("─" * 80)

    # Coordinator (as CASE_OWNER) triggers CS.P.
    with demo_step(
        f"Actor {ref_id(coordinator_in_coordinator)} reports vulnerability"
        " publicly disclosed"
    ):
        ActorSession(
            client=coordinator_client, actor=coordinator_in_coordinator
        ).with_case(case).quiet().notify_published()

    with demo_check(
        "Embargo terminated (EM.EXITED) after Coordinator reports published"
    ):
        wait_for_case_em_terminated(
            client=coordinator_client,
            case_id=case.id_,
        )

    with demo_step(
        f"Actor {ref_id(reporter_in_reporter)} reports vulnerability publicly"
        " disclosed"
    ):
        ActorSession(
            client=reporter_client, actor=reporter_in_reporter
        ).with_case(case).quiet().notify_published()

    with demo_check("M3: EM.EXITED, Coordinator and Reporter public-aware"):
        wait_for_case_em_terminated(
            client=reporter_client,
            case_id=case.id_,
        )
        verify_publicly_disclosed(
            receiver_client=coordinator_client,
            reporter_client=reporter_client,
            case_id=case.id_,
            receiver_actor_id=coordinator_in_coordinator.id_,
        )


def _phase_case_closure(
    reporter_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    coordinator_in_coordinator: as_Actor,
    reporter_in_reporter: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Close the case from Reporter and Coordinator; verify terminal state.

    The Reporter leaves first; the Coordinator, the Case Owner, leaves last,
    once the Reporter's departure is recorded (CM-23-015) in the CASE_MANAGER's
    store on the dedicated case-actor container.
    """
    logger.info("─" * 80)
    logger.info("Phase 5: Case closure — Reporter and Coordinator RM.CLOSED")
    logger.info("─" * 80)

    close_case_owner_last(
        case=case,
        milestone="M4",
        authority_client=case_actor_client,
        others=[
            CaseLeaver(client=reporter_client, actor=reporter_in_reporter)
        ],
        owner=CaseLeaver(
            client=coordinator_client, actor=coordinator_in_coordinator
        ),
    )


def _phase_dump_case_ledgers(
    reporter_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    case: as_VulnerabilityCase,
    demo_name: str = "rcv-reject",
    vendor_client: DataLayerClient | None = None,
) -> None:
    """Dump case ledger entries from Reporter, Coordinator, and CaseActor to JSONL.

    Vendor is intentionally excluded from the dump targets: it rejected the
    invitation and was never added as a case participant, so it has no case
    ledger replica.  Its identity is still recorded in the manifest, because
    the Case Actor's ``reject_invite_actor_to_case`` entry names it as the
    recorded actor and a narrative tag must resolve to it (#4248).

    Thin scenario-specific wrapper over
    :func:`~vultron.demo.helpers.ledger_dump.dump_case_ledgers`, which owns the
    per-actor export, the 404 handling, and the dump manifest.
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
            "coordinator",
            coordinator_client,
            replica_route_key(coordinator_client, "coordinator"),
        ),
        # The canonical ledger, on the dedicated case-actor container
        # (DEMOMA-06-005).
        case_actor_dump_target(case_actor_client),
    ]

    unreplicated = (
        {"vendor": replica_route_key(vendor_client, "vendor")}
        if vendor_client is not None
        else None
    )
    dump_case_ledgers(
        demo_name=demo_name,
        case=case,
        targets=targets,
        unreplicated=unreplicated,
    )


def run_rcv_reject_demo(
    reporter_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    reporter_id: str | None = None,
    coordinator_id: str | None = None,
    vendor_id: str | None = None,
) -> None:
    """Orchestrate the RCV-Reject CVD workflow."""
    logger.info("=" * 80)
    logger.info(
        "RCV-REJECT DEMO: Reporter + Coordinator(CASE_OWNER) + Vendor(rejects)"
    )
    logger.info("=" * 80)
    logger.info("Reporter container:      %s", reporter_client.base_url)
    logger.info("Coordinator container: %s", coordinator_client.base_url)
    logger.info("Vendor container:      %s", vendor_client.base_url)
    logger.info("CaseActor container:   %s", case_actor_client.base_url)

    with scenario_harness("rcv-reject") as harness:
        (
            _reporter,
            reporter_in_reporter,
            _coordinator,
            coordinator_in_coordinator,
            vendor_obj,
            _report,
            _offer,
            case,
        ) = _phase_report_submission(
            reporter_client=reporter_client,
            coordinator_client=coordinator_client,
            vendor_client=vendor_client,
            case_actor_client=case_actor_client,
            reporter_id=reporter_id,
            coordinator_id=coordinator_id,
            vendor_id=vendor_id,
        )

        # Register the dump as soon as there is a case to dump, so every phase
        # below can fail without costing us the ledgers (ISSUE-2239).
        harness.dump_with(
            lambda: _phase_dump_case_ledgers(
                reporter_client=reporter_client,
                coordinator_client=coordinator_client,
                case_actor_client=case_actor_client,
                case=case,
                demo_name=harness.demo_name,
                vendor_client=vendor_client,
            )
        )

        _phase_invite_vendor_reject(
            coordinator_client=coordinator_client,
            case_actor_client=case_actor_client,
            vendor_client=vendor_client,
            reporter=_reporter,
            coordinator_in_coordinator=coordinator_in_coordinator,
            coordinator=_coordinator,
            vendor=vendor_obj,
            case=case,
        )

        _phase_sync_verification(
            reporter_client=reporter_client,
            coordinator_client=coordinator_client,
            reporter=_reporter,
            coordinator=_coordinator,
            case=case,
        )

        _phase_notes_exchange(
            reporter_client=reporter_client,
            coordinator_client=coordinator_client,
            reporter_in_reporter=reporter_in_reporter,
            coordinator_in_coordinator=coordinator_in_coordinator,
            case=case,
        )

        _phase_publication(
            reporter_client=reporter_client,
            coordinator_client=coordinator_client,
            coordinator_in_coordinator=coordinator_in_coordinator,
            reporter_in_reporter=reporter_in_reporter,
            case=case,
        )

        _phase_case_closure(
            reporter_client=reporter_client,
            coordinator_client=coordinator_client,
            case_actor_client=case_actor_client,
            coordinator_in_coordinator=coordinator_in_coordinator,
            reporter_in_reporter=reporter_in_reporter,
            case=case,
        )

    logger.info("=" * 80)
    logger.info(
        "RCV-REJECT DEMO COMPLETE ✓  (Vendor rejected — Reporter+Coordinator closed)"
    )
    logger.info("=" * 80)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


@scenario(
    name="rcv-reject",
    label="RCV-reject",
    participants="Reporter + Coordinator + Vendor (Vendor rejects)",
    feature="Invite rejection path",
    in_pr_set=True,
)
def main(
    skip_health_check: bool = False,
    reporter_url: str | None = None,
    coordinator_url: str | None = None,
    vendor_url: str | None = None,
    case_actor_url: str | None = None,
    reporter_id: str | None = None,
    coordinator_id: str | None = None,
    vendor_id: str | None = None,
) -> None:
    """Entry point for the RCV-Reject CVD workflow demo.

    Args:
        skip_health_check: Skip the server availability check.
        reporter_url: Override base URL for the Reporter container.
        coordinator_url: Override base URL for the Coordinator container.
        vendor_url: Override base URL for the Vendor container.
        case_actor_url: Override base URL for the CaseActor container.
        reporter_id: Optional deterministic URI for the Reporter actor.
        coordinator_id: Optional deterministic URI for the Coordinator actor.
        vendor_id: Optional deterministic URI for the Vendor actor.
    """
    f_url = reporter_url or REPORTER_BASE_URL
    c_url = coordinator_url or COORDINATOR_BASE_URL
    v_url = vendor_url or VENDOR_BASE_URL
    ca_url = case_actor_url or CASE_ACTOR_BASE_URL

    reporter_client = DataLayerClient(base_url=f_url)
    coordinator_client = DataLayerClient(base_url=c_url)
    vendor_client = DataLayerClient(base_url=v_url)
    case_actor_client = bound_case_actor_client(ca_url)

    if not skip_health_check:
        targets: list[tuple[str, DataLayerClient]] = [
            ("Reporter", reporter_client),
            ("Coordinator", coordinator_client),
            ("Vendor", vendor_client),
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

    # scenario_harness() inside run_rcv_reject_demo() owns the failure
    # accumulator: it resets it, always dumps the case ledgers, and asserts
    # success — so a failure here never costs us the artifacts (ISSUE-2239).
    run_rcv_reject_demo(
        reporter_client=reporter_client,
        coordinator_client=coordinator_client,
        vendor_client=vendor_client,
        case_actor_client=case_actor_client,
        reporter_id=reporter_id,
        coordinator_id=coordinator_id,
        vendor_id=vendor_id,
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
