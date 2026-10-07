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

"""RCV embargo demo (Reporter + Coordinator + Vendor, deliberate termination).

A three-party case across four containers (Reporter, Coordinator, Vendor and
CaseActor) that exercises the embargo lifecycle on its own: a post-submission
embargo negotiation and a deliberate early termination (DEMOMA-20, issue #2071).

The Coordinator creates the case and holds CASE_OWNER; the CaseActor holds
CASE_MANAGER.  Case creation activates the default embargo (EP-04-001), so the
case is at ``EM.ACTIVE`` before anyone proposes anything.  The Reporter's
proposal therefore **revises** that embargo (``ACTIVE → REVISE → ACTIVE``): the
CASE_MANAGER relays it, the Vendor consents, and the Coordinator, as owner,
activates the revision (EP-09).  After the fix is ready the Coordinator ends the
embargo deliberately (``ACTIVE → EXITED``); publication and closure follow.

The phases run in the order DEMOMA-20-007 gives, and each asserts the expected
EM state before the next starts (DEMOMA-20-008).  The assertions read the
CASE_MANAGER's canonical case, or wait for the fan-out; none reads a triggering
actor's replica straight after its trigger (DEMOMA-20-011).

Spec: DEMOMA-20, DEMOCI-07 (GitHub issue #2071).
"""

import logging
from dataclasses import dataclass

from vultron.core.states.em import EM
from vultron.demo.actor_session import ActorSession
from vultron.demo.exchange.embargo_lifecycle import (
    COMMIT_TIMEOUT_SECONDS,
    demo_propose_and_activate_embargo,
    demo_terminate_embargo,
)
from vultron.demo.helpers.actor_roles import ActorRole, role_map
from vultron.demo.helpers.coordinated_case import (
    dump_coordinated_case_ledgers,
    everyone_closes_case,
    everyone_reports_published,
    open_coordinated_case,
    vendor_joins_coordinated_case,
    vendor_reports_fix_ready,
)
from vultron.demo.helpers.harness import ScenarioHarness, scenario_harness
from vultron.demo.helpers.notes import participant_adds_note_to_case
from vultron.demo.helpers.polling import (
    resolve_case_actor_store_id,
    wait_for_case_em_state,
    wait_for_case_em_terminated,
)
from vultron.demo.helpers.runner import check_all_containers
from vultron.demo.helpers.seeding import (
    get_actor_by_id,
    reset_containers as _reset_containers,
    seed_containers_fcv,
)
from vultron.demo.helpers.sync import run_sync_verification_phase
from vultron.demo.scenario.registry import scenario
from vultron.demo.utils import (
    DataLayerClient,
    case_actor_id_on,
    demo_check,
    demo_gate,
    demo_step,
    reset_datalayer,
    setup_demo_logging,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

logger = logging.getLogger(__name__)

# Default container base URLs — override via environment variables.  The
# Reporter runs in the ``finder`` container slot: compose service names are
# routing labels, not CVD roles (vultron/demo/AGENTS.md).
ROLES: list[ActorRole] = [
    ActorRole(
        name="reporter",
        url_env="VULTRON_FINDER_BASE_URL",
        default_url="http://localhost:7901/api/v2",
        url_help="Base URL of the Reporter container API "
        "(env: VULTRON_FINDER_BASE_URL).",
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
    ActorRole(
        name="case-actor",
        url_env="VULTRON_CASE_ACTOR_BASE_URL",
        default_url="http://localhost:7905/api/v2",
        url_help="Base URL of the CaseActor container API "
        "(env: VULTRON_CASE_ACTOR_BASE_URL).",
    ),
]
_ROLES = role_map(ROLES)

REPORTER_BASE_URL = _ROLES["reporter"].url
COORDINATOR_BASE_URL = _ROLES["coordinator"].url
VENDOR_BASE_URL = _ROLES["vendor"].url
CASE_ACTOR_BASE_URL = _ROLES["case-actor"].url

#: ``vultron-demo rcv-embargo --help`` text.
CLI_HELP = """Run the RCV embargo demo (DEMOMA-20).

Reporter + Coordinator + Vendor, exercising the embargo lifecycle: the
Reporter revises the default embargo after submitting its report, and the
Coordinator later ends the embargo deliberately, before publication.

\b
Workflow:
  1. Seed the containers; Reporter submits a report to Coordinator;
     Coordinator engages the case (CASE_OWNER); Vendor joins by invitation.
     The default embargo is active (EM.ACTIVE).
  2. Reporter proposes new embargo terms; the CASE_MANAGER relays the proposal;
     Vendor consents; Coordinator, as owner, activates the revision.
  3. Vendor advances to fix ready (VFd).
  4. Coordinator terminates the embargo (EM.EXITED).
  5. All participants report publication.
  6. All participants close the case (RM.CLOSED on all replicas).
  7. Case ledgers are dumped for the invariant harness.
"""

REPORTER_NAME = "reporter"
DEMO_NAME = "rcv-embargo"


@dataclass(frozen=True)
class _Cast:
    """The three trigger sessions of the scenario, each bound to its container."""

    reporter: ActorSession
    coordinator: ActorSession
    vendor: ActorSession


def reset_containers(
    reporter_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_actor_client: DataLayerClient | None = None,
) -> None:
    """Reset the RCV containers to a clean baseline."""
    targets: list[tuple[str, DataLayerClient]] = [
        ("Reporter", reporter_client),
        ("Coordinator", coordinator_client),
        ("Vendor", vendor_client),
    ]
    if case_actor_client is not None:
        targets.append(("CaseActor", case_actor_client))
    _reset_containers(targets, reset_fn=reset_datalayer)


def _canonical_case(
    session: ActorSession, case: as_VulnerabilityCase
) -> as_VulnerabilityCase:
    """The case as the CASE_MANAGER holds it, read through *session*'s container."""
    client = session.client
    return as_VulnerabilityCase.model_validate(
        client.get(
            client.dl_path(
                case.id_,
                actor_id=resolve_case_actor_store_id(client, case.id_),
            )
        )
    )


def _assert_em_state(
    cast: _Cast,
    case: as_VulnerabilityCase,
    expected: EM,
    phase: str,
    active_embargo_id: str | None = None,
) -> None:
    """Assert the CASE_MANAGER's canonical case is at *expected* (DEMOMA-20-008)."""
    client = cast.coordinator.client
    with demo_check(
        f"{phase}: CASE_MANAGER's canonical case has {expected.name}"
    ):
        wait_for_case_em_state(
            client,
            case.id_,
            expected,
            COMMIT_TIMEOUT_SECONDS,
            dl_actor_id=resolve_case_actor_store_id(client, case.id_),
            active_embargo_id=active_embargo_id,
        )


# ---------------------------------------------------------------------------
# Phases (DEMOMA-20-007)
# ---------------------------------------------------------------------------


def _notes_exchange(cast: _Cast, case: as_VulnerabilityCase) -> None:
    """The Reporter asks about the embargo and the Vendor answers (DEMOMA-16-001)."""
    question = participant_adds_note_to_case(
        posting_client=cast.reporter.client,
        watching_client=cast.coordinator.client,
        poster=cast.reporter.actor,
        case=case,
        note_name="Question from Reporter",
        note_content="Could the embargo be shorter than the default?",
    )
    participant_adds_note_to_case(
        posting_client=cast.vendor.client,
        watching_client=cast.coordinator.client,
        poster=cast.vendor.actor,
        case=case,
        note_name="Vendor Status Update",
        note_content="A fix is in progress; a shorter embargo is workable.",
        in_reply_to=question.id_ if question is not None else None,
    )


def _phase_report_submission(
    harness: ScenarioHarness,
    reporter_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_actor_client: DataLayerClient | None,
    reporter_id: str | None,
    coordinator_id: str | None,
    vendor_id: str | None,
) -> tuple[_Cast, as_VulnerabilityCase]:
    """Seed, submit the report, open the case, bring the Vendor in.

    Leaves the case at ``EM.ACTIVE`` under the default embargo (EP-04-001).
    """
    logger.info("─" * 80)
    logger.info(
        "Phase 1: Report submission — Reporter → Coordinator; Vendor joins"
    )
    logger.info("─" * 80)

    reset_containers(
        reporter_client=reporter_client,
        coordinator_client=coordinator_client,
        vendor_client=vendor_client,
        case_actor_client=case_actor_client,
    )
    reporter = coordinator = vendor = None
    with demo_step("Seeding Reporter, Coordinator, and Vendor containers"):
        reporter, coordinator, vendor = seed_containers_fcv(
            finder_client=reporter_client,
            coordinator_client=coordinator_client,
            vendor_client=vendor_client,
            reporter_actor_id=reporter_id,
            coordinator_actor_id=coordinator_id,
            vendor_actor_id=vendor_id,
        )

    opened = open_coordinated_case(
        reporter_client=reporter_client,
        coordinator_client=coordinator_client,
        reporter=reporter,
        coordinator=coordinator,
    )
    case = opened.case

    # Register the dump as soon as there is a case to dump, so every phase
    # below can fail without costing us the ledgers (ISSUE-2239).
    harness.dump_with(
        lambda: _phase_dump_case_ledgers(
            reporter_client=reporter_client,
            coordinator_client=coordinator_client,
            vendor_client=vendor_client,
            case=case,
            demo_name=harness.demo_name,
        )
    )

    vendor_in_vendor = vendor_joins_coordinated_case(
        opened=opened,
        reporter=reporter,
        reporter_client=reporter_client,
        coordinator_client=coordinator_client,
        vendor=vendor,
        vendor_client=vendor_client,
    )

    run_sync_verification_phase(
        auth_client=coordinator_client,
        auth_label="Coordinator",
        auth_actor_id=coordinator.id_,
        finder_client=reporter_client,
        finder_actor_id=reporter.id_,
        replicas=[(reporter_client, "Reporter"), (vendor_client, "Vendor")],
        case_id=case.id_,
        expected_participant_ids={reporter.id_, coordinator.id_, vendor.id_},
        # The Vendor joins by invitation after the case exists (#2202).
        late_joiners=(vendor_client,),
        state_checks=[
            (reporter_client, "Reporter"),
            (vendor_client, "Vendor"),
        ],
    )

    cast = _Cast(
        reporter=ActorSession(
            client=reporter_client,
            actor=get_actor_by_id(reporter_client, reporter.id_),
        ).with_case(case),
        coordinator=ActorSession(
            client=coordinator_client, actor=opened.coordinator_in_coordinator
        ).with_case(case),
        vendor=ActorSession(
            client=vendor_client, actor=vendor_in_vendor
        ).with_case(case),
    )
    _notes_exchange(cast, case)
    _assert_em_state(cast, case, EM.ACTIVE, "report_submission")
    return cast, case


def _phase_embargo_proposal(
    cast: _Cast, case: as_VulnerabilityCase
) -> str | None:
    """The Reporter revises the default embargo; the Coordinator activates it.

    Returns:
        The id of the embargo now in force.
    """
    logger.info("─" * 80)
    logger.info(
        "Phase 2: Embargo proposal — Reporter revises the default embargo"
    )
    logger.info("─" * 80)

    default_embargo_id = _canonical_case(
        cast.coordinator, case
    ).active_embargo_id

    demo_propose_and_activate_embargo(
        cast.reporter, cast.coordinator, cast.vendor, case
    )

    # A gate, not a check: phase 4 ends the embargo this phase put in force, so
    # without a revision it would only add secondary failures (DEMOCI-01-007).
    revised_embargo_id: str | None = None
    with demo_gate("The revision, not the default embargo, is now in force"):
        in_force = _canonical_case(cast.coordinator, case).active_embargo_id
        if in_force is None or in_force == default_embargo_id:
            raise AssertionError(
                f"active embargo {in_force!r} is not a revision of"
                f" the default {default_embargo_id!r}"
            )
        revised_embargo_id = in_force
        _assert_em_state(
            cast,
            case,
            EM.ACTIVE,
            "embargo_proposal",
            active_embargo_id=revised_embargo_id,
        )
    return revised_embargo_id


def _phase_fix_lifecycle(cast: _Cast, case: as_VulnerabilityCase) -> None:
    """The Vendor reports fix ready; the embargo is untouched."""
    logger.info("─" * 80)
    logger.info("Phase 3: Fix lifecycle — Vendor reports fix ready (VFd)")
    logger.info("─" * 80)

    vendor_reports_fix_ready(
        coordinator_client=cast.coordinator.client,
        vendor_client=cast.vendor.client,
        vendor_in_vendor=cast.vendor.actor,
        case=case,
    )
    _assert_em_state(cast, case, EM.ACTIVE, "fix_lifecycle")


def _phase_embargo_termination(
    cast: _Cast, case: as_VulnerabilityCase
) -> None:
    """The Coordinator ends the embargo deliberately, before publication."""
    logger.info("─" * 80)
    logger.info("Phase 4: Embargo termination — Coordinator ends the embargo")
    logger.info("─" * 80)

    # The helper asserts EM.EXITED on the CASE_MANAGER's canonical case and no
    # participant's consent (DEMOMA-20-011, DEMOMA-20-012).
    demo_terminate_embargo(cast.coordinator, case)
    _assert_em_state(cast, case, EM.EXITED, "embargo_termination")
    # Replicas learn it from the ledger fan-out afterwards, so these are
    # checks of the effect, not gates for what follows (EDF-06-006).
    for label, session in (
        ("Reporter", cast.reporter),
        ("Vendor", cast.vendor),
    ):
        with demo_check(f"{label}'s replica has EM.EXITED"):
            wait_for_case_em_terminated(
                client=session.client,
                case_id=case.id_,
                timeout_seconds=COMMIT_TIMEOUT_SECONDS,
            )


def _phase_publication(cast: _Cast, case: as_VulnerabilityCase) -> None:
    """Everyone reports publication; the ended embargo stays ended."""
    logger.info("─" * 80)
    logger.info("Phase 5: Publication — CS.P after the embargo has ended")
    logger.info("─" * 80)

    everyone_reports_published(
        reporter_client=cast.reporter.client,
        coordinator_client=cast.coordinator.client,
        vendor_client=cast.vendor.client,
        reporter_in_reporter=cast.reporter.actor,
        coordinator_in_coordinator=cast.coordinator.actor,
        vendor_in_vendor=cast.vendor.actor,
        case=case,
    )
    _assert_em_state(cast, case, EM.EXITED, "publication")


def _phase_case_closure(cast: _Cast, case: as_VulnerabilityCase) -> None:
    """Every participant closes the case."""
    logger.info("─" * 80)
    logger.info("Phase 6: Case closure — all participants RM.CLOSED")
    logger.info("─" * 80)

    everyone_closes_case(
        reporter_client=cast.reporter.client,
        coordinator_client=cast.coordinator.client,
        vendor_client=cast.vendor.client,
        reporter_in_reporter=cast.reporter.actor,
        coordinator_in_coordinator=cast.coordinator.actor,
        vendor_in_vendor=cast.vendor.actor,
        case=case,
    )
    _assert_em_state(cast, case, EM.EXITED, "case_closure")


def _phase_dump_case_ledgers(
    reporter_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case: as_VulnerabilityCase,
    demo_name: str = DEMO_NAME,
) -> None:
    """Dump each participant's case ledger (phase 7, DEMOMA-20-007).

    Thin wrapper (DEMOMA-23-002): the harness runs it on the way out, whether
    or not an earlier phase failed.
    """
    dump_coordinated_case_ledgers(
        demo_name=demo_name,
        reporter_name=REPORTER_NAME,
        reporter_client=reporter_client,
        coordinator_client=coordinator_client,
        vendor_client=vendor_client,
        case=case,
    )


def run_rcv_embargo_demo(
    reporter_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_actor_client: DataLayerClient | None = None,
    reporter_id: str | None = None,
    coordinator_id: str | None = None,
    vendor_id: str | None = None,
) -> None:
    """Orchestrate the RCV embargo workflow."""
    logger.info("=" * 80)
    logger.info(
        "RCV EMBARGO DEMO: Reporter + Coordinator(CASE_OWNER) + Vendor"
    )
    logger.info("=" * 80)
    logger.info("Reporter container:    %s", reporter_client.base_url)
    logger.info("Coordinator container: %s", coordinator_client.base_url)
    logger.info("Vendor container:      %s", vendor_client.base_url)
    if case_actor_client is not None:
        logger.info("CaseActor container:   %s", case_actor_client.base_url)

    # scenario_harness() owns the failure accumulator: it resets it, always
    # dumps the case ledgers (phase 7, dump_case_ledgers, DEMOMA-20-007) on the
    # way out whether or not a phase failed, and asserts success last
    # (ISSUE-2239).
    with scenario_harness(DEMO_NAME) as harness:
        cast, case = _phase_report_submission(
            harness=harness,
            reporter_client=reporter_client,
            coordinator_client=coordinator_client,
            vendor_client=vendor_client,
            case_actor_client=case_actor_client,
            reporter_id=reporter_id,
            coordinator_id=coordinator_id,
            vendor_id=vendor_id,
        )
        revised_embargo_id = _phase_embargo_proposal(cast, case)
        _phase_fix_lifecycle(cast, case)
        # Termination, publication and closure all presuppose the revised
        # embargo of phase 2, so they run only while it is in force.
        with demo_gate("Phase 2 put the revised embargo in force"):
            if revised_embargo_id is None:
                raise AssertionError(
                    "no revised embargo; skipping phases 4-6 (embargo_termination,"
                    " publication, case_closure)"
                )
            _phase_embargo_termination(cast, case)
            _phase_publication(cast, case)
            _phase_case_closure(cast, case)

    logger.info("=" * 80)
    logger.info(
        "RCV EMBARGO DEMO COMPLETE ✓  (EM: ACTIVE → REVISE → ACTIVE → EXITED)"
    )
    logger.info("=" * 80)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


@scenario(
    name=DEMO_NAME,
    label="RCV embargo",
    participants="Reporter + Coordinator + Vendor",
    feature="Embargo revision after submission and deliberate termination",
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
    """Entry point for the RCV embargo demo.

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
    r_url = reporter_url or REPORTER_BASE_URL
    c_url = coordinator_url or COORDINATOR_BASE_URL
    v_url = vendor_url or VENDOR_BASE_URL
    ca_url = case_actor_url or CASE_ACTOR_BASE_URL

    reporter_client = DataLayerClient(base_url=r_url)
    coordinator_client = DataLayerClient(base_url=c_url)
    vendor_client = DataLayerClient(base_url=v_url)
    case_actor_client = DataLayerClient(
        base_url=ca_url, actor_id=case_actor_id_on(ca_url)
    )

    if not skip_health_check:
        targets: list[tuple[str, DataLayerClient]] = [
            ("Reporter", reporter_client),
            ("Coordinator", coordinator_client),
            ("Vendor", vendor_client),
            ("CaseActor", case_actor_client),
        ]
        check_all_containers(targets)

    run_rcv_embargo_demo(
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
