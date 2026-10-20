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

"""Reporter → Vendor1 → Vendor2 (RVV) three-actor CVD workflow demo.

Orchestrates the full VFDPxa lifecycle across separate Reporter, Vendor1,
and Vendor2 containers with no coordinator.  Vendor1 creates the case, which
seats the Reporter, and invites Vendor2; each vendor has an
independent fix path (CS_vf/CS_d).  Vendor2's DataLayer is verified as a
LedgerFanout replica of the authoritative Vendor1 state.

Spec: D5-5 (GitHub issue #1265).
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
from vultron.demo.helpers.notes import participant_adds_note_to_case
from vultron.demo.helpers.polling import (
    wait_for_case_em_terminated,
    wait_for_case_on_container,
    wait_for_case_participants,
    wait_for_participant_rm_state,
    wait_for_participant_vf_state,
    wait_for_reporter_case,
)
from vultron.demo.helpers.seeding import (
    get_actor_by_id,
    reset_containers as _reset_containers,
    seed_containers_rvv,
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
    BASE_URL,
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
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Offer,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

logger = logging.getLogger(__name__)

# The scenario's actor slots, in main() parameter order. The demo CLI derives
# this scenario's sub-command options from this list (DEMOCI-11-011); the base
# URL constants below are its resolved values, so each env-var/default pair is
# declared once.
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
        name="vendor2",
        url_env="VULTRON_VENDOR2_BASE_URL",
        default_url="http://localhost:7904/api/v2",
        url_help="Base URL of the Vendor2 container API "
        "(env: VULTRON_VENDOR2_BASE_URL).",
        has_id=True,
        id_help="Deterministic full URI for the Vendor2 actor (optional).",
    ),
    case_actor_role("http://localhost:7905/api/v2"),
]
_ROLES = role_map(ROLES)

# Default container base URLs — override via environment variables.
REPORTER_BASE_URL = _ROLES["reporter"].url
VENDOR_BASE_URL = _ROLES["vendor"].url
VENDOR2_BASE_URL = _ROLES["vendor2"].url
CASE_ACTOR_BASE_URL = _ROLES["case-actor"].url

#: ``vultron-demo rvv --help`` text. Lives here rather than in ``cli.py``
#: because the sub-command is generated from the registry and the scenario
#: module is the only place that knows what its own workflow does.
CLI_HELP = """Run the RVV (Reporter + Vendor1 + Vendor2) multi-container CVD demo (D5-5).

Orchestrates a complete CVD workflow across three separate API server
containers with no coordinator.  Vendor1 creates the case, which seats the
Reporter, and invites Vendor2; each vendor maintains an independent
fix path.

\b
Workflow:
  1. Seed all three containers (actor records + peer registration).
  2. Reporter submits a vulnerability report to Vendor1's inbox.
  3. Vendor1 validates the report and engages the case.
  4. Vendor1 invites Vendor2; Vendor2 accepts.
  5. Verify LedgerFanout replication on Reporter and Vendor2.
  6. Both vendors independently advance through fix-ready → fix-deployed.
  7. All participants report publication; embargo terminates.
  8. All participants close the case.
"""

# Deterministic actor IDs from docker-compose-multi-actor.yml (D5-1-G3).
REPORTER_ACTOR_ID = "http://reporter:7999/api/v2/actors/reporter"
VENDOR_ACTOR_ID = "http://vendor:7999/api/v2/actors/vendor"
VENDOR2_ACTOR_ID = "http://actor5:7999/api/v2/actors/vendor2"


def reset_containers(
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    case_actor_client: DataLayerClient,
) -> None:
    """Reset the three RVV containers and the dedicated case-actor container.

    The case-actor container's CaseActor identity is re-seeded after the reset,
    since Vendor1 proposes the case to it (DEMOMA-06-004).
    """
    targets: list[tuple[str, DataLayerClient]] = [
        ("Reporter", reporter_client),
        ("Vendor1", vendor_client),
        ("Vendor2", vendor2_client),
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
    vendor_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    reporter_id: str | None,
    vendor_id: str | None,
    vendor2_id: str | None,
) -> tuple[
    as_Actor,
    as_Actor,
    as_Actor,
    as_Actor,
    as_VulnerabilityReport,
    as_Offer,
    as_VulnerabilityCase,
]:
    """Reset, seed, submit report, validate, engage, invite Vendor2, M1 check."""
    logger.info("─" * 80)
    logger.info("Phase 1: Report submission and case activation")
    logger.info("─" * 80)

    reset_containers(
        reporter_client=reporter_client,
        vendor_client=vendor_client,
        vendor2_client=vendor2_client,
        case_actor_client=case_actor_client,
    )

    reporter = vendor = vendor2 = None
    with demo_step("Seeding all three containers with actor records"):
        reporter, vendor, vendor2 = seed_containers_rvv(
            reporter_client=reporter_client,
            vendor_client=vendor_client,
            vendor2_client=vendor2_client,
            reporter_actor_id=reporter_id,
            vendor_actor_id=vendor_id,
            vendor2_actor_id=vendor2_id,
        )

    vendor_in_vendor = get_actor_by_id(vendor_client, vendor.id_)
    vendor2_in_vendor2 = get_actor_by_id(vendor2_client, vendor2.id_)

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
    )

    # Causal precondition: the initial case (Reporter + Vendor1 present on
    # Vendor1's replica) must exist before Vendor2 is invited.  A demo_gate — not
    # demo_check — because inviting/admitting Vendor2 operates on unestablished
    # state if this times out; the gate skips the doomed dependent steps rather
    # than cascading (DEMOCI-01-011, vultron/demo/AGENTS.md § "Never Wrap a
    # Causal Wait in demo_check").
    with demo_gate(
        "Vendor1 case has Reporter + Vendor1 before inviting Vendor2"
    ):
        wait_for_case_participants(
            vendor_client=vendor_client,
            case_id=case.id_,
            expected_actor_ids={reporter.id_, vendor.id_},
        )

        with demo_check(
            "Reporter's DataLayer received case via Vendor1 outbox delivery"
        ):
            wait_for_reporter_case(
                reporter_client=reporter_client,
                case_id=case.id_,
            )

        # Vendor1 invites Vendor2 to the case; the chain nests the delivery
        # gate, the accept and the replica wait (ADR-0058, EDF-06-005, #3038).
        run_case_invite_chain(
            case=case,
            case_manager_client=case_actor_client,
            invitee_name="Vendor2",
            invitee_client=vendor2_client,
            invitee=vendor2,
            invitee_in_own_container=vendor2_in_vendor2,
            inviter=CaseInviter(
                name="Vendor1",
                client=vendor_client,
                actor=vendor_in_vendor,
                role=CVDRole.VENDOR,
            ),
            invite_timeout=20.0,
        )

        # All 4 participants (Reporter + Vendor1 + Vendor2 + CaseActor) present is
        # the precondition for Vendor2's RM triage below.
        with demo_gate(
            "Vendor1 case has all 4 participants before Vendor2 RM triage"
        ):
            wait_for_case_participants(
                vendor_client=vendor_client,
                case_id=case.id_,
                expected_actor_ids={
                    reporter.id_,
                    vendor.id_,
                    vendor2.id_,
                },
            )

            # CLP-08-005: ensure Reporter's genesis hash is seeded before
            # Announce(CaseLedgerEntry) is broadcast by the triage cycle below.
            with demo_check(
                "Reporter's DataLayer received case replica before Vendor2 RM"
                " triage"
            ):
                wait_for_case_on_container(
                    client=reporter_client,
                    case_id=case.id_,
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
            )

    with demo_check(
        "M1: required participants (≥4), EM.ACTIVE, reporter + vendor2 have replicas"
    ):
        verify_case_active(
            receiver_client=vendor_client,
            reporter_client=reporter_client,
            case_id=case.id_,
            receiver_actor_id=vendor.id_,
            reporter_actor_id=reporter.id_,
        )

    case = as_VulnerabilityCase.model_validate(
        vendor_client.get(vendor_client.dl_path(case.id_))
    )
    return reporter, vendor, vendor_in_vendor, vendor2, report, offer, case


def _phase_sync_verification(
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    vendor: as_Actor,
    reporter: as_Actor,
    vendor2: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Verify LedgerFanout replication for both Reporter and Vendor2 replicas."""
    logger.info("─" * 80)
    logger.info("Phase 2: Replica synchronization verification")
    logger.info("─" * 80)

    run_sync_verification_phase(
        auth_client=vendor_client,
        auth_label="Vendor1",
        auth_actor_id=vendor.id_,
        reporter_client=reporter_client,
        reporter_actor_id=reporter.id_,
        replicas=[(reporter_client, "Reporter"), (vendor2_client, "Vendor2")],
        case_id=case.id_,
        expected_participant_ids={reporter.id_, vendor.id_, vendor2.id_},
        # Vendor2 joins by invitation after the report is accepted (#2852).
        late_joiners=(vendor2_client,),
        state_checks=[
            (reporter_client, "Reporter"),
            (vendor2_client, "Vendor2"),
        ],
    )

    logger.info(
        "✓ M2: Reporter and Vendor2 DataLayers synchronized (LedgerFanout verified)"
    )


def _phase_notes_exchange(
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    reporter_in_reporter: as_Actor,
    vendor_in_vendor: as_Actor,
    vendor2_in_vendor2: as_Actor,
    case: as_VulnerabilityCase,
) -> tuple[as_Note | None, as_Note | None, as_Note | None]:
    """Run a three-way note exchange among Reporter, Vendor1, and Vendor2."""
    logger.info("─" * 80)
    logger.info("Phase 3: Notes exchange")
    logger.info("─" * 80)

    question_note = participant_adds_note_to_case(
        posting_client=reporter_client,
        watching_client=vendor_client,
        poster=reporter_in_reporter,
        case=case,
        note_name="Question from Reporter",
        note_content=(
            "Is there a workaround available while waiting for the patch? "
            "Our security team needs to provide interim guidance to users."
        ),
    )

    reply_note = participant_adds_note_to_case(
        posting_client=vendor_client,
        watching_client=vendor_client,
        poster=vendor_in_vendor,
        case=case,
        note_name="Vendor1 Response",
        note_content=(
            "Yes, disabling the affected component is an effective workaround. "
            "A patched version is expected within 30 days."
        ),
        in_reply_to=question_note.id_ if question_note is not None else None,
    )

    vendor2_note = participant_adds_note_to_case(
        posting_client=vendor2_client,
        watching_client=vendor_client,
        poster=vendor2_in_vendor2,
        case=case,
        note_name="Vendor2 Status Update",
        note_content=(
            "Vendor2 can confirm the issue affects our component. "
            "We will coordinate our fix timeline with Vendor1."
        ),
        in_reply_to=reply_note.id_ if reply_note is not None else None,
    )

    logger.info(
        "✓ Notes exchange complete (question + two replies committed to case ledger)"
    )
    return question_note, reply_note, vendor2_note


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
    """Advance both vendors through independent fix-ready and fix-deployed paths."""
    logger.info("─" * 80)
    logger.info(
        "Phase 4: Fix lifecycle — both vendors: VFd (fix ready); vendors stop at VFd (CSB-15-002)"
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
        "M4: Reporter replica shows both vendors CS include F (fix ready)"
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
        "M5: Reporter replica shows both vendors CS include F (fix ready) — vendors stop at VFd"
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
    vendor2_client: DataLayerClient,
    vendor: as_Actor,
    vendor_in_vendor: as_Actor,
    vendor2: as_Actor,
    vendor2_in_vendor2: as_Actor,
    reporter: as_Actor,
    reporter_in_reporter: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Run publication notifications and verify public disclosure state."""
    logger.info("─" * 80)
    logger.info(
        "Phase 5: Publication — CS.VFDPxa + embargo teardown (EM.EXITED)"
    )
    logger.info("─" * 80)

    with demo_step(
        f"Actor {ref_id(vendor_in_vendor)} reports vulnerability publicly"
        " disclosed"
    ):
        ActorSession(client=vendor_client, actor=vendor_in_vendor).with_case(
            case
        ).quiet().notify_published()

    with demo_check(
        "Embargo terminated (EM.EXITED) after Vendor1 reports published"
    ):
        wait_for_case_em_terminated(
            client=vendor_client,
            case_id=case.id_,
        )

    with demo_step(
        f"Actor {ref_id(vendor2_in_vendor2)} reports vulnerability publicly"
        " disclosed"
    ):
        ActorSession(
            client=vendor2_client, actor=vendor2_in_vendor2
        ).with_case(case).quiet().notify_published()

    with demo_step(
        f"Actor {ref_id(reporter_in_reporter)} reports vulnerability publicly"
        " disclosed"
    ):
        ActorSession(
            client=reporter_client, actor=reporter_in_reporter
        ).with_case(case).quiet().notify_published()

    with demo_check(
        "M6: all replicas CS.VFdPxa, EM.EXITED, all participants public-aware"
    ):
        wait_for_case_em_terminated(
            client=reporter_client,
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
    vendor2_client: DataLayerClient,
    vendor: as_Actor,
    vendor_in_vendor: as_Actor,
    vendor2: as_Actor,
    vendor2_in_vendor2: as_Actor,
    reporter: as_Actor,
    reporter_in_reporter: as_Actor,
    case: as_VulnerabilityCase,
    case_actor_client: DataLayerClient,
) -> None:
    """Close the case from all three participants and verify terminal state.

    Vendor2 and the Reporter leave first; Vendor1, the Case Owner, leaves
    last, once their departures are recorded (CM-23-015) in the
    CASE_MANAGER's store on the dedicated case-actor container.
    """
    logger.info("─" * 80)
    logger.info("Phase 6: Case closure — all participants RM.CLOSED")
    logger.info("─" * 80)

    close_case_owner_last(
        case=case,
        milestone="M7",
        authority_client=case_actor_client,
        others=[
            CaseLeaver(client=vendor2_client, actor=vendor2_in_vendor2),
            CaseLeaver(client=reporter_client, actor=reporter_in_reporter),
        ],
        owner=CaseLeaver(client=vendor_client, actor=vendor_in_vendor),
    )


def _phase_dump_case_ledgers(
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    reporter: as_Actor,
    vendor: as_Actor,
    vendor2: as_Actor,
    case: as_VulnerabilityCase,
    case_actor_client: DataLayerClient,
    demo_name: str = "rvv",
) -> None:
    """Dump case ledger entries from each actor container to JSONL files.

    Thin scenario-specific wrapper over
    :func:`~vultron.demo.helpers.ledger_dump.dump_case_ledgers`, which owns the
    per-actor export, the 404 handling, and the dump manifest. This function
    only names RVV's participants and where each one's ledger lives.
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
            "vendor2",
            vendor2_client,
            replica_route_key(vendor2_client, "vendor2"),
        ),
        # The canonical ledger, from the dedicated case-actor container.
        case_actor_dump_target(case_actor_client),
    ]

    dump_case_ledgers(demo_name=demo_name, case=case, targets=targets)


def run_rvv_demo(
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    reporter_id: str | None = None,
    vendor_id: str | None = None,
    vendor2_id: str | None = None,
) -> None:
    """Orchestrate the RVV (Reporter + Vendor1 + Vendor2) CVD workflow."""
    logger.info("=" * 80)
    logger.info("RVV DEMO: Reporter → Vendor1 → Vendor2 CVD Workflow (VFDPxa)")
    logger.info("=" * 80)
    logger.info("Reporter container:  %s", reporter_client.base_url)
    logger.info("Vendor1 container: %s", vendor_client.base_url)
    logger.info("Vendor2 container: %s", vendor2_client.base_url)
    logger.info("CaseActor container: %s", case_actor_client.base_url)

    with scenario_harness("rvv") as harness:
        reporter, vendor, vendor_in_vendor, vendor2, _report, _offer, case = (
            _phase_report_submission(
                reporter_client,
                vendor_client,
                vendor2_client,
                case_actor_client,
                reporter_id,
                vendor_id,
                vendor2_id,
            )
        )

        # Register the dump as soon as there is a case to dump, so every phase
        # below can fail without costing us the ledgers (ISSUE-2239).
        harness.dump_with(
            lambda: _phase_dump_case_ledgers(
                reporter_client=reporter_client,
                vendor_client=vendor_client,
                vendor2_client=vendor2_client,
                reporter=reporter,
                vendor=vendor,
                vendor2=vendor2,
                case=case,
                case_actor_client=case_actor_client,
                demo_name=harness.demo_name,
            )
        )

        vendor2_in_vendor2 = get_actor_by_id(vendor2_client, vendor2.id_)
        reporter_in_reporter = get_actor_by_id(reporter_client, reporter.id_)

        _phase_sync_verification(
            reporter_client,
            vendor_client,
            vendor2_client,
            vendor,
            reporter,
            vendor2,
            case,
        )
        _phase_notes_exchange(
            reporter_client=reporter_client,
            vendor_client=vendor_client,
            vendor2_client=vendor2_client,
            reporter_in_reporter=reporter_in_reporter,
            vendor_in_vendor=vendor_in_vendor,
            vendor2_in_vendor2=vendor2_in_vendor2,
            case=case,
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
            vendor2_client,
            vendor,
            vendor_in_vendor,
            vendor2,
            vendor2_in_vendor2,
            reporter,
            reporter_in_reporter,
            case,
        )
        _phase_case_closure(
            reporter_client,
            vendor_client,
            vendor2_client,
            vendor,
            vendor_in_vendor,
            vendor2,
            vendor2_in_vendor2,
            reporter,
            reporter_in_reporter,
            case,
            case_actor_client,
        )

    logger.info("=" * 80)
    logger.info("RVV DEMO COMPLETE ✓  (VFDPxa full lifecycle)")
    logger.info("=" * 80)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


@scenario(
    name="rvv",
    label="RVV",
    participants="Reporter + Vendor1 + Vendor2",
    feature="Direct invitation of a second vendor",
    in_pr_set=False,
)
def main(
    skip_health_check: bool = False,
    reporter_url: str | None = None,
    vendor_url: str | None = None,
    vendor2_url: str | None = None,
    case_actor_url: str | None = None,
    reporter_id: str | None = None,
    vendor_id: str | None = None,
    vendor2_id: str | None = None,
) -> None:
    """Entry point for the RVV (Reporter + Vendor1 + Vendor2) CVD workflow demo.

    Args:
        skip_health_check: Skip the server availability check (useful for
            testing).
        reporter_url: Override base URL for the Reporter container.
        vendor_url: Override base URL for the Vendor1 container.
        vendor2_url: Override base URL for the Vendor2 container.
        case_actor_url: Override base URL for the dedicated CaseActor
            container.
        reporter_id: Optional deterministic URI for the Reporter actor.
        vendor_id: Optional deterministic URI for the Vendor1 actor.
        vendor2_id: Optional deterministic URI for the Vendor2 actor.
    """
    f_url = reporter_url or REPORTER_BASE_URL
    v_url = vendor_url or VENDOR_BASE_URL
    v2_url = vendor2_url or VENDOR2_BASE_URL
    ca_url = case_actor_url or CASE_ACTOR_BASE_URL

    reporter_client = DataLayerClient(base_url=f_url)
    vendor_client = DataLayerClient(base_url=v_url)
    vendor2_client = DataLayerClient(base_url=v2_url)
    # Bound to the CaseActor: a /datalayer/ read names whose store it is about
    # (ADR-0073).
    case_actor_client = bound_case_actor_client(ca_url)

    if not skip_health_check:
        targets: list[tuple[str, DataLayerClient]] = [
            ("Reporter", reporter_client),
            ("Vendor1", vendor_client),
            ("Vendor2", vendor2_client),
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

    # scenario_harness() inside run_rvv_demo() owns the failure accumulator: it
    # resets it, always dumps the case ledgers, and asserts success — so a
    # failure here never costs us the artifacts (ISSUE-2239).
    run_rvv_demo(
        reporter_client=reporter_client,
        vendor_client=vendor_client,
        vendor2_client=vendor2_client,
        case_actor_client=case_actor_client,
        reporter_id=reporter_id,
        vendor_id=vendor_id,
        vendor2_id=vendor2_id,
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
