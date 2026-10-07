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

"""FCV three-actor CVD workflow demo (Finder + Coordinator + Vendor).

Orchestrates the CVD lifecycle to VFdPxa closure across four containers:
Finder, Coordinator (CASE_OWNER), Vendor, and CaseActor.

Coordinator receives the Finder's report, creates the case (holding
CASE_OWNER), the CaseActor service actor holds CASE_MANAGER.  The Finder is
seated as reporter when the case is created (CM-22-002), so it is never
invited; the Coordinator directly invites Vendor (``invite-actor-to-case``).
Vendor accepts the report and embargo, advances through the fix lifecycle
to fix ready (VFd; Vendor stops at VFd), and all three participants
coordinate to VFdPxa closure.  Coordinator closes the case.

Spec: DEMOMA-12 (GitHub issue #1593).
"""

import logging
import sys

from vultron.demo.helpers.actor_roles import ActorRole, role_map
from vultron.demo.helpers.coordinated_case import (
    CoordinatedCase,
    dump_coordinated_case_ledgers,
    everyone_closes_case,
    everyone_reports_published,
    open_coordinated_case,
    vendor_joins_coordinated_case,
    vendor_reports_fix_ready,
)
from vultron.demo.helpers.harness import scenario_harness
from vultron.demo.helpers.notes import participant_adds_note_to_case
from vultron.demo.helpers.seeding import (
    get_actor_by_id,
    reset_containers as _reset_containers,
    seed_containers_fcv,
)
from vultron.demo.helpers.sync import (
    run_sync_verification_phase,
)
from vultron.demo.scenario.registry import scenario
from vultron.demo.utils import (  # noqa: F401 — re-exported for test monkeypatching
    DataLayerClient,
    assert_demo_success,
    case_actor_id_on,
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
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Offer,
)
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
        name="finder",
        url_env="VULTRON_FINDER_BASE_URL",
        default_url="http://localhost:7901/api/v2",
        url_help="Base URL of the Finder container API "
        "(env: VULTRON_FINDER_BASE_URL).",
        has_id=True,
        id_help="Deterministic full URI for the Finder actor (optional).",
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
    ActorRole(
        name="case-actor",
        url_env="VULTRON_CASE_ACTOR_BASE_URL",
        default_url="http://localhost:7905/api/v2",
        url_help="Base URL of the CaseActor container API "
        "(env: VULTRON_CASE_ACTOR_BASE_URL).",
    ),
]
_ROLES = role_map(ROLES)

FINDER_BASE_URL = _ROLES["finder"].url
VENDOR_BASE_URL = _ROLES["vendor"].url
COORDINATOR_BASE_URL = _ROLES["coordinator"].url
CASE_ACTOR_BASE_URL = _ROLES["case-actor"].url

#: ``vultron-demo fcv --help`` text. Lives here rather than in ``cli.py``
#: because the sub-command is generated from the registry and the scenario
#: module is the only place that knows what its own workflow does.
CLI_HELP = """Run the FCV (Finder + Coordinator + Vendor) CVD demo (DEMOMA-12).

Coordinator receives the Finder's report, creates the authoritative case
(holding CASE_OWNER), and the CaseActor service manages the case ledger.
The Finder is seated as reporter at case creation; the Coordinator directly
invites Vendor.  Vendor accepts as a late joiner and receives the full ledger
backfill (LedgerFanout).  All participants advance through the fix lifecycle
(Vendor stops at VFd) to VFdPxa closure.

\b
Workflow:
  1. Seed Finder, Coordinator, and Vendor containers.
  2. Finder submits a vulnerability report to Coordinator's inbox.
  3. Coordinator validates the report and engages the case (CASE_OWNER).
  4. Coordinator invites Vendor directly (invite-actor-to-case).
  5. Vendor accepts the case invitation; case replica seeded (LedgerFanout).
  6. Verify all replica ledgers synchronized.
  7. Three-way notes exchange among all participants.
  8. Vendor advances to VF (fix ready); Vendor stops at VFd.
  9. All participants report publication; embargo terminates (EM.EXITED).
 10. All participants close the case (RM.CLOSED on all replicas).
"""

# Deterministic actor IDs from docker-compose-multi-actor.yml (D5-1-G3).
FINDER_ACTOR_ID = "http://finder:7999/api/v2/actors/finder"
COORDINATOR_ACTOR_ID = "http://coordinator:7999/api/v2/actors/coordinator"
VENDOR_ACTOR_ID = "http://vendor:7999/api/v2/actors/vendor"
CASE_ACTOR_ACTOR_ID = "http://case-actor:7999/api/v2/actors/case-actor"


def reset_containers(
    finder_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_actor_client: DataLayerClient | None = None,
) -> None:
    """Reset FCV containers to a clean baseline."""
    targets: list[tuple[str, DataLayerClient]] = [
        ("Finder", finder_client),
        ("Coordinator", coordinator_client),
        ("Vendor", vendor_client),
    ]
    if case_actor_client is not None:
        targets.append(("CaseActor", case_actor_client))
    _reset_containers(targets, reset_fn=reset_datalayer)


# ---------------------------------------------------------------------------
# Polling helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Phase helpers
# ---------------------------------------------------------------------------


def _phase_report_submission(
    finder_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_actor_client: DataLayerClient | None,
    finder_id: str | None,
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
    """Reset, seed, Finder submits report to Coordinator, Coordinator engages case."""
    logger.info("─" * 80)
    logger.info("Phase 1: Report submission — Finder → Coordinator")
    logger.info("─" * 80)

    reset_containers(
        finder_client=finder_client,
        coordinator_client=coordinator_client,
        vendor_client=vendor_client,
        case_actor_client=case_actor_client,
    )

    finder = coordinator = vendor = None
    with demo_step("Seeding Finder, Coordinator, and Vendor containers"):
        finder, coordinator, vendor = seed_containers_fcv(
            finder_client=finder_client,
            coordinator_client=coordinator_client,
            vendor_client=vendor_client,
            reporter_actor_id=finder_id,
            coordinator_actor_id=coordinator_id,
            vendor_actor_id=vendor_id,
        )

    opened = open_coordinated_case(
        reporter_client=finder_client,
        coordinator_client=coordinator_client,
        reporter=finder,
        coordinator=coordinator,
    )
    finder_in_finder = get_actor_by_id(finder_client, finder.id_)
    return (
        finder,
        finder_in_finder,
        coordinator,
        opened.coordinator_in_coordinator,
        vendor,
        opened.report,
        opened.offer,
        opened.case,
    )


def _phase_invite_vendor(
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    finder_client: DataLayerClient,
    coordinator_in_coordinator: as_Actor,
    vendor: as_Actor,
    case: as_VulnerabilityCase,
    offer: as_Offer,
    report: as_VulnerabilityReport,
    finder: as_Actor,
) -> as_Actor:
    """Coordinator invites Vendor directly; Vendor accepts.

    DEMOMA-12-004: Coordinator is CASE_OWNER so uses invite-actor-to-case
    directly (not the ADR-0026 suggest/approve chain).
    """
    logger.info("─" * 80)
    logger.info("Phase 2: Coordinator invites Vendor")
    logger.info("─" * 80)

    return vendor_joins_coordinated_case(
        opened=CoordinatedCase(
            report=report,
            offer=offer,
            case=case,
            coordinator_in_coordinator=coordinator_in_coordinator,
        ),
        reporter=finder,
        reporter_client=finder_client,
        coordinator_client=coordinator_client,
        vendor=vendor,
        vendor_client=vendor_client,
    )


def _phase_sync_verification(
    finder_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    finder: as_Actor,
    coordinator: as_Actor,
    case: as_VulnerabilityCase,
    vendor: as_Actor,
) -> None:
    """Verify LedgerFanout replication for Finder and Vendor replicas."""
    logger.info("─" * 80)
    logger.info("Phase 3: Replica synchronization verification")
    logger.info("─" * 80)

    run_sync_verification_phase(
        auth_client=coordinator_client,
        auth_label="Coordinator",
        auth_actor_id=coordinator.id_,
        finder_client=finder_client,
        finder_actor_id=finder.id_,
        replicas=[(finder_client, "Finder"), (vendor_client, "Vendor")],
        case_id=case.id_,
        expected_participant_ids={finder.id_, coordinator.id_, vendor.id_},
        # Vendor joins by invitation in Phase 2 (#2202).
        late_joiners=(vendor_client,),
        state_checks=[(finder_client, "Finder"), (vendor_client, "Vendor")],
    )

    logger.info("✓ M3: All replicas synchronized (LedgerFanout verified)")


def _phase_notes_exchange(
    finder_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    finder_in_finder: as_Actor,
    coordinator_in_coordinator: as_Actor,
    vendor_in_vendor: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Run a three-way note exchange among all participants."""
    logger.info("─" * 80)
    logger.info("Phase 4: Notes exchange")
    logger.info("─" * 80)

    question_note = participant_adds_note_to_case(
        posting_client=finder_client,
        watching_client=coordinator_client,
        poster=finder_in_finder,
        case=case,
        note_name="Question from Finder",
        note_content=(
            "Could you share the timeline for patch availability with Vendor?"
        ),
    )

    vendor_reply = participant_adds_note_to_case(
        posting_client=vendor_client,
        watching_client=coordinator_client,
        poster=vendor_in_vendor,
        case=case,
        note_name="Vendor Status Update",
        note_content=(
            "We have confirmed the issue and are developing a fix. "
            "Estimated patch availability: 14 days."
        ),
        in_reply_to=question_note.id_ if question_note is not None else None,
    )

    participant_adds_note_to_case(
        posting_client=coordinator_client,
        watching_client=coordinator_client,
        poster=coordinator_in_coordinator,
        case=case,
        note_name="Coordinator Summary",
        note_content=(
            "All three parties engaged. Vendor fix expected in 14 days. "
            "Embargo holds until patch is deployed."
        ),
        in_reply_to=vendor_reply.id_ if vendor_reply is not None else None,
    )

    logger.info(
        "✓ Notes exchange complete (three notes committed to case ledger)"
    )


def _phase_fix_lifecycle(
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    coordinator: as_Actor,
    vendor: as_Actor,
    vendor_in_vendor: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Advance Vendor through fix-ready; Vendor stops at VFd (CSB-15-002)."""
    logger.info("─" * 80)
    logger.info(
        "Phase 5: Fix lifecycle — Vendor: VFd (fix ready); vendor stops at VFd (CSB-15-002)"
    )
    logger.info("─" * 80)

    vendor_reports_fix_ready(
        coordinator_client=coordinator_client,
        vendor_client=vendor_client,
        vendor_in_vendor=vendor_in_vendor,
        case=case,
    )


def _phase_publication(
    finder_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    coordinator: as_Actor,
    coordinator_in_coordinator: as_Actor,
    vendor_in_vendor: as_Actor,
    finder_in_finder: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Run publication notifications and verify public disclosure state.

    Per DEMOMA-07-003(4) the Coordinator (as CASE_OWNER) triggers CS.P.
    """
    logger.info("─" * 80)
    logger.info(
        "Phase 6: Publication — CS.VFDPxa + embargo teardown (EM.EXITED)"
    )
    logger.info("─" * 80)

    everyone_reports_published(
        reporter_client=finder_client,
        coordinator_client=coordinator_client,
        vendor_client=vendor_client,
        reporter_in_reporter=finder_in_finder,
        coordinator_in_coordinator=coordinator_in_coordinator,
        vendor_in_vendor=vendor_in_vendor,
        case=case,
    )


def _phase_case_closure(
    finder_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    coordinator_in_coordinator: as_Actor,
    vendor_in_vendor: as_Actor,
    finder_in_finder: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Close the case from all participants and verify terminal state."""
    logger.info("─" * 80)
    logger.info("Phase 7: Case closure — all participants RM.CLOSED")
    logger.info("─" * 80)

    everyone_closes_case(
        reporter_client=finder_client,
        coordinator_client=coordinator_client,
        vendor_client=vendor_client,
        reporter_in_reporter=finder_in_finder,
        coordinator_in_coordinator=coordinator_in_coordinator,
        vendor_in_vendor=vendor_in_vendor,
        case=case,
    )


def _phase_dump_case_ledgers(
    finder_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case: as_VulnerabilityCase,
    demo_name: str = "fcv",
) -> None:
    """Dump case ledger entries from each actor container to JSONL files."""
    dump_coordinated_case_ledgers(
        demo_name=demo_name,
        reporter_name="finder",
        reporter_client=finder_client,
        coordinator_client=coordinator_client,
        vendor_client=vendor_client,
        case=case,
    )


def run_fcv_demo(
    finder_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_actor_client: DataLayerClient | None = None,
    finder_id: str | None = None,
    coordinator_id: str | None = None,
    vendor_id: str | None = None,
) -> None:
    """Orchestrate the FCV CVD workflow."""
    logger.info("=" * 80)
    logger.info("FCV DEMO: Finder + Coordinator(CASE_OWNER) + Vendor")
    logger.info("=" * 80)
    logger.info("Finder container:      %s", finder_client.base_url)
    logger.info("Coordinator container: %s", coordinator_client.base_url)
    logger.info("Vendor container:      %s", vendor_client.base_url)
    if case_actor_client is not None:
        logger.info("CaseActor container:   %s", case_actor_client.base_url)

    with scenario_harness("fcv") as harness:
        (
            finder,
            finder_in_finder,
            coordinator,
            coordinator_in_coordinator,
            vendor_obj,
            report,
            offer,
            case,
        ) = _phase_report_submission(
            finder_client=finder_client,
            coordinator_client=coordinator_client,
            vendor_client=vendor_client,
            case_actor_client=case_actor_client,
            finder_id=finder_id,
            coordinator_id=coordinator_id,
            vendor_id=vendor_id,
        )

        # Register the dump as soon as there is a case to dump, so every phase
        # below can fail without costing us the ledgers (ISSUE-2239).
        harness.dump_with(
            lambda: _phase_dump_case_ledgers(
                finder_client=finder_client,
                coordinator_client=coordinator_client,
                vendor_client=vendor_client,
                case=case,
                demo_name=harness.demo_name,
            )
        )

        vendor_in_vendor = _phase_invite_vendor(
            coordinator_client=coordinator_client,
            vendor_client=vendor_client,
            finder_client=finder_client,
            coordinator_in_coordinator=coordinator_in_coordinator,
            vendor=vendor_obj,
            case=case,
            offer=offer,
            report=report,
            finder=finder,
        )

        _phase_sync_verification(
            finder_client=finder_client,
            coordinator_client=coordinator_client,
            vendor_client=vendor_client,
            finder=finder,
            coordinator=coordinator,
            case=case,
            vendor=vendor_obj,
        )

        _phase_notes_exchange(
            finder_client=finder_client,
            coordinator_client=coordinator_client,
            vendor_client=vendor_client,
            finder_in_finder=finder_in_finder,
            coordinator_in_coordinator=coordinator_in_coordinator,
            vendor_in_vendor=vendor_in_vendor,
            case=case,
        )

        _phase_fix_lifecycle(
            coordinator_client=coordinator_client,
            vendor_client=vendor_client,
            coordinator=coordinator,
            vendor=vendor_obj,
            vendor_in_vendor=vendor_in_vendor,
            case=case,
        )

        _phase_publication(
            finder_client=finder_client,
            coordinator_client=coordinator_client,
            vendor_client=vendor_client,
            coordinator=coordinator,
            coordinator_in_coordinator=coordinator_in_coordinator,
            vendor_in_vendor=vendor_in_vendor,
            finder_in_finder=finder_in_finder,
            case=case,
        )

        _phase_case_closure(
            finder_client=finder_client,
            coordinator_client=coordinator_client,
            vendor_client=vendor_client,
            coordinator_in_coordinator=coordinator_in_coordinator,
            vendor_in_vendor=vendor_in_vendor,
            finder_in_finder=finder_in_finder,
            case=case,
        )

    logger.info("=" * 80)
    logger.info("FCV DEMO COMPLETE ✓  (VFDPxa full lifecycle)")
    logger.info("=" * 80)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


@scenario(
    name="fcv",
    label="FCV",
    participants="Finder + Coordinator + Vendor",
    feature="Coordinator-mediated report and vendor onboarding",
    in_pr_set=False,
)
def main(
    skip_health_check: bool = False,
    finder_url: str | None = None,
    coordinator_url: str | None = None,
    vendor_url: str | None = None,
    case_actor_url: str | None = None,
    finder_id: str | None = None,
    coordinator_id: str | None = None,
    vendor_id: str | None = None,
) -> None:
    """Entry point for the FCV CVD workflow demo.

    Args:
        skip_health_check: Skip the server availability check.
        finder_url: Override base URL for the Finder container.
        coordinator_url: Override base URL for the Coordinator container.
        vendor_url: Override base URL for the Vendor container.
        case_actor_url: Override base URL for the CaseActor container.
        finder_id: Optional deterministic URI for the Finder actor.
        coordinator_id: Optional deterministic URI for the Coordinator actor.
        vendor_id: Optional deterministic URI for the Vendor actor.
    """
    f_url = finder_url or FINDER_BASE_URL
    c_url = coordinator_url or COORDINATOR_BASE_URL
    v_url = vendor_url or VENDOR_BASE_URL
    ca_url = case_actor_url or CASE_ACTOR_BASE_URL

    finder_client = DataLayerClient(base_url=f_url)
    coordinator_client = DataLayerClient(base_url=c_url)
    vendor_client = DataLayerClient(base_url=v_url)
    case_actor_client = DataLayerClient(
        base_url=ca_url, actor_id=case_actor_id_on(ca_url)
    )

    if not skip_health_check:
        targets: list[tuple[str, DataLayerClient]] = [
            ("Finder", finder_client),
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

    # scenario_harness() inside run_fcv_demo() owns the failure accumulator: it
    # resets it, always dumps the case ledgers, and asserts success — so a
    # failure here never costs us the artifacts (ISSUE-2239).
    run_fcv_demo(
        finder_client=finder_client,
        coordinator_client=coordinator_client,
        vendor_client=vendor_client,
        case_actor_client=case_actor_client,
        finder_id=finder_id,
        coordinator_id=coordinator_id,
        vendor_id=vendor_id,
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
