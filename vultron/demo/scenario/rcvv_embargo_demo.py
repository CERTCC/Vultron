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

"""RCVV embargo demo (Reporter + Coordinator + Vendor1 + Vendor2).

A four-party case across five containers (Reporter, Coordinator, Vendor1,
Vendor2 and CaseActor) that exercises the embargo lifecycle on its own:
post-submission negotiation, a revision cycle, a late second vendor, and an
embargo that collapses by accident when the Reporter publishes
(DEMOMA-21, issue #2072).

The Coordinator creates the case and holds CASE_OWNER; the CaseActor holds
CASE_MANAGER.  Case creation activates the default embargo (EP-04-001), so the
Reporter's proposal **revises** it (``ACTIVE → REVISE → ACTIVE``, EP-09); then
Vendor1 proposes a second revision that the Reporter accepts and the
Coordinator, as owner, activates.  Vendor2 is invited only after that, and
signs the embargo in force by accepting the invitation.  After the fixes are
ready the Reporter reports public disclosure: CS.P ends the embargo
automatically (``ACTIVE → EXITED``), and nobody terminates it.

The phases run in the order DEMOMA-21-008 gives, and phases 2, 3, 4 and 6
each assert the expected EM state before the next starts (DEMOMA-21-009).

Spec: DEMOMA-21, DEMOCI-07 (GitHub issue #2072).
"""

import logging
from dataclasses import dataclass

from vultron.core.behaviors.embargo.nodes import EMBARGO_TEARDOWN_EVENT_TYPE
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import EmbargoConsentState
from vultron.demo.actor_session import ActorSession
from vultron.demo.exchange.embargo_lifecycle import (
    COMMIT_TIMEOUT_SECONDS,
    demo_propose_embargo_revision,
)
from vultron.demo.helpers.actor_roles import ActorRole, role_map
from vultron.demo.helpers.coordinated_case import (
    CoordinatedCase,
    dump_coordinated_case_ledgers,
    everyone_closes_case,
    open_case_with_vendor,
    vendor_joins_coordinated_case,
    vendor_reports_fix_ready,
)
from vultron.demo.helpers.embargo_phases import (
    assert_canonical_em_state,
    confirm_embargo_revised,
    revise_default_embargo,
)
from vultron.demo.helpers.harness import ScenarioHarness, scenario_harness
from vultron.demo.helpers.notes import reporter_asks_vendor_answers
from vultron.demo.helpers.polling import (
    resolve_case_actor_store_id,
    wait_for_case_em_state,
    wait_for_case_em_terminated,
    wait_for_event_type_in_ledger,
    wait_for_participant_embargo_consent,
)
from vultron.demo.helpers.runner import check_all_containers
from vultron.demo.helpers.seeding import (
    get_actor_by_id,
    reset_containers as _reset_containers,
    seed_containers_rcvv,
)
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
# Reporter runs in the ``finder`` container slot and Vendor2 in ``actor5``:
# compose service names are routing labels, not CVD roles
# (vultron/demo/AGENTS.md).
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
VENDOR2_BASE_URL = _ROLES["vendor2"].url
CASE_ACTOR_BASE_URL = _ROLES["case-actor"].url

#: ``vultron-demo rcvv-embargo --help`` text.
CLI_HELP = """Run the RCVV embargo demo (DEMOMA-21).

Reporter + Coordinator + Vendor1 + Vendor2, exercising the embargo lifecycle:
the Reporter and then Vendor1 revise the embargo, Vendor2 joins late and signs
it, and the embargo collapses when the Reporter publishes.

\b
Workflow:
  1. Seed the containers; Reporter submits a report to Coordinator;
     Coordinator engages the case (CASE_OWNER); Vendor1 joins by invitation.
     The default embargo is active (EM.ACTIVE).
  2. Reporter proposes new embargo terms; the CASE_MANAGER relays the proposal;
     Vendor1 consents; Coordinator, as owner, activates the revision.
  3. Vendor1 proposes a further revision; Reporter consents; Coordinator
     activates it.
  4. Coordinator invites Vendor2; Vendor2 accepts and signs the embargo.
  5. Both vendors advance to fix ready (VFd).
  6. Reporter reports publication; CS.P ends the embargo (EM.EXITED) with no
     deliberate termination.
  7. All participants close the case (RM.CLOSED on all replicas).
  8. Case ledgers are dumped for the invariant harness.
"""

REPORTER_NAME = "reporter"
VENDOR2_NAME = "vendor2"
DEMO_NAME = "rcvv-embargo"


@dataclass(frozen=True)
class _Cast:
    """The four trigger sessions of the scenario, each bound to its container.

    Vendor2 is seeded with the rest but takes no part in the case until phase 4
    invites it.
    """

    reporter: ActorSession
    coordinator: ActorSession
    vendor: ActorSession
    vendor2: ActorSession


def reset_containers(
    reporter_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    case_actor_client: DataLayerClient | None = None,
) -> None:
    """Reset the RCVV containers to a clean baseline."""
    targets: list[tuple[str, DataLayerClient]] = [
        ("Reporter", reporter_client),
        ("Coordinator", coordinator_client),
        ("Vendor1", vendor_client),
        ("Vendor2", vendor2_client),
    ]
    if case_actor_client is not None:
        targets.append(("CaseActor", case_actor_client))
    _reset_containers(targets, reset_fn=reset_datalayer)


# ---------------------------------------------------------------------------
# Phases (DEMOMA-21-008)
# ---------------------------------------------------------------------------


def _phase_report_submission(
    harness: ScenarioHarness,
    reporter_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    case_actor_client: DataLayerClient | None,
    reporter_id: str | None,
    coordinator_id: str | None,
    vendor_id: str | None,
    vendor2_id: str | None,
) -> tuple[_Cast, as_VulnerabilityCase, CoordinatedCase]:
    """Seed, submit the report, open the case, bring Vendor1 in.

    Leaves the case at ``EM.ACTIVE`` under the default embargo (EP-04-001).
    """
    logger.info("─" * 80)
    logger.info(
        "Phase 1: Report submission — Reporter → Coordinator; Vendor1 joins"
    )
    logger.info("─" * 80)

    reset_containers(
        reporter_client=reporter_client,
        coordinator_client=coordinator_client,
        vendor_client=vendor_client,
        vendor2_client=vendor2_client,
        case_actor_client=case_actor_client,
    )
    reporter = coordinator = vendor = vendor2 = None
    with demo_step("Seeding Reporter, Coordinator, Vendor1, and Vendor2"):
        reporter, coordinator, vendor, vendor2 = seed_containers_rcvv(
            reporter_client=reporter_client,
            coordinator_client=coordinator_client,
            vendor_client=vendor_client,
            vendor2_client=vendor2_client,
            reporter_actor_id=reporter_id,
            coordinator_actor_id=coordinator_id,
            vendor_actor_id=vendor_id,
            vendor2_actor_id=vendor2_id,
        )

    opened, vendor_in_vendor = open_case_with_vendor(
        reporter_client=reporter_client,
        coordinator_client=coordinator_client,
        vendor_client=vendor_client,
        reporter=reporter,
        coordinator=coordinator,
        vendor=vendor,
        # Register the dump as soon as there is a case to dump, so every phase
        # below can fail without costing us the ledgers (ISSUE-2239).
        on_case_opened=lambda opened_case: harness.dump_with(
            lambda: _phase_dump_case_ledgers(
                reporter_client=reporter_client,
                coordinator_client=coordinator_client,
                vendor_client=vendor_client,
                vendor2_client=vendor2_client,
                case=opened_case,
                demo_name=harness.demo_name,
            )
        ),
    )
    case = opened.case

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
        vendor2=ActorSession(
            client=vendor2_client,
            actor=get_actor_by_id(vendor2_client, vendor2.id_),
        ).with_case(case),
    )
    # The shared note exchange puts add_note_to_case in the ledger
    # (DEMOMA-16-001); Vendor1 is seated, Vendor2 is not yet.
    reporter_asks_vendor_answers(
        cast.reporter, cast.vendor, cast.coordinator.client, case
    )
    assert_canonical_em_state(
        cast.coordinator, case, EM.ACTIVE, "report_submission"
    )
    return cast, case, opened


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
    return revise_default_embargo(
        cast.reporter,
        cast.coordinator,
        cast.vendor,
        case,
        phase="embargo_proposal",
    )


def _phase_embargo_revision(
    cast: _Cast, case: as_VulnerabilityCase, prior_embargo_id: str
) -> str | None:
    """Vendor1 revises the embargo; the Reporter consents; the owner activates.

    Returns:
        The id of the embargo now in force, or ``None`` when the revision did
        not take effect (the failure is recorded).
    """
    logger.info("─" * 80)
    logger.info("Phase 3: Embargo revision — Vendor1 proposes new terms")
    logger.info("─" * 80)

    demo_propose_embargo_revision(
        proposing=cast.vendor,
        accepting=cast.reporter,
        owner=cast.coordinator,
        case=case,
    )

    # Vendor2 signs whatever is in force when it joins, so without a second
    # revision phase 4 would assert about the wrong embargo.
    return confirm_embargo_revised(
        cast.coordinator,
        case,
        prior_embargo_id,
        "embargo_revision",
        "The second revision is now in force",
    )


def _phase_v2_late_invite(
    cast: _Cast,
    case: as_VulnerabilityCase,
    opened: CoordinatedCase,
    embargo_id: str,
) -> bool:
    """Invite Vendor2 once the revision is active; it signs the embargo.

    Returns:
        Whether Vendor2 is a signatory of the embargo in force; a ``False`` is
        already recorded as a failure.
    """
    logger.info("─" * 80)
    logger.info(
        "Phase 4: Vendor2 late invite — joins under the revised embargo"
    )
    logger.info("─" * 80)

    vendor_joins_coordinated_case(
        opened=opened,
        reporter=cast.reporter.actor,
        reporter_client=cast.reporter.client,
        coordinator_client=cast.coordinator.client,
        vendor=cast.vendor2.actor,
        vendor_client=cast.vendor2.client,
        vendor_name="Vendor2",
        already_seated=[cast.vendor.actor],
    )
    assert_canonical_em_state(
        cast.coordinator,
        case,
        EM.ACTIVE,
        "v2_late_invite",
        active_embargo_id=embargo_id,
    )
    # Accepting the invitation consents to the embargo in force (CM-11-002), so
    # Vendor2 is a signatory before it does anything else (DEMOMA-21-012).
    # The fix lifecycle, collapse and closure presuppose it, so the caller runs
    # them only when this returns True (DEMOCI-01-007).
    signed = False
    with demo_gate("Vendor2 is a SIGNATORY to the active embargo"):
        wait_for_participant_embargo_consent(
            cast.coordinator.client,
            case.id_,
            cast.vendor2.actor.id_,
            embargo_id,
            EmbargoConsentState.ACCEPTED,
            COMMIT_TIMEOUT_SECONDS,
            dl_actor_id=resolve_case_actor_store_id(
                cast.coordinator.client, case.id_
            ),
        )
        signed = True
    with demo_check("Vendor2's replica has the revised embargo active"):
        wait_for_case_em_state(
            cast.vendor2.client,
            case.id_,
            EM.ACTIVE,
            COMMIT_TIMEOUT_SECONDS,
            active_embargo_id=embargo_id,
        )
    return signed


def _phase_fix_lifecycle(cast: _Cast, case: as_VulnerabilityCase) -> None:
    """Both vendors report fix ready; the embargo is untouched."""
    logger.info("─" * 80)
    logger.info("Phase 5: Fix lifecycle — both vendors report fix ready (VFd)")
    logger.info("─" * 80)

    for session in (cast.vendor, cast.vendor2):
        vendor_reports_fix_ready(
            coordinator_client=cast.coordinator.client,
            vendor_client=session.client,
            vendor_in_vendor=session.actor,
            case=case,
        )
    assert_canonical_em_state(
        cast.coordinator, case, EM.ACTIVE, "fix_lifecycle"
    )


def _phase_accidental_collapse(
    cast: _Cast, case: as_VulnerabilityCase
) -> None:
    """The Reporter publishes; CS.P ends the embargo with no one terminating it.

    The collapse is the protocol's own consequence of the P-transition
    (DEMOMA-21-014): this phase never calls ``terminate_embargo``.
    """
    logger.info("─" * 80)
    logger.info("Phase 6: Accidental collapse — Reporter publishes (CS.P)")
    logger.info("─" * 80)

    with demo_step("Reporter reports the vulnerability publicly disclosed"):
        cast.reporter.quiet().notify_published()

    # The teardown is the CASE_MANAGER's own commit, so it is read where it
    # commits before any replica is expected to show it (EDF-06-002).
    with demo_gate("The CASE_MANAGER commits the embargo teardown"):
        wait_for_event_type_in_ledger(
            client=cast.coordinator.client,
            case_id=case.id_,
            event_type=EMBARGO_TEARDOWN_EVENT_TYPE,
            timeout_seconds=COMMIT_TIMEOUT_SECONDS,
            dl_actor_id=resolve_case_actor_store_id(
                cast.coordinator.client, case.id_
            ),
        )
    assert_canonical_em_state(
        cast.coordinator, case, EM.EXITED, "accidental_collapse"
    )
    # Replicas learn it from the ledger fan-out afterwards, so these are checks
    # of the effect, not gates for what follows (EDF-06-006).
    for label, session in (
        ("Coordinator", cast.coordinator),
        ("Reporter", cast.reporter),
        ("Vendor1", cast.vendor),
        ("Vendor2", cast.vendor2),
    ):
        with demo_check(f"{label}'s replica has EM.EXITED"):
            wait_for_case_em_terminated(
                client=session.client,
                case_id=case.id_,
                timeout_seconds=COMMIT_TIMEOUT_SECONDS,
            )


def _phase_case_closure(cast: _Cast, case: as_VulnerabilityCase) -> None:
    """Every participant closes the case."""
    logger.info("─" * 80)
    logger.info("Phase 7: Case closure — all participants RM.CLOSED")
    logger.info("─" * 80)

    everyone_closes_case(
        reporter_client=cast.reporter.client,
        coordinator_client=cast.coordinator.client,
        vendor_client=cast.vendor.client,
        reporter_in_reporter=cast.reporter.actor,
        coordinator_in_coordinator=cast.coordinator.actor,
        vendor_in_vendor=cast.vendor.actor,
        case=case,
        later_vendors=[
            ("Vendor2", cast.vendor2.client, cast.vendor2.actor),
        ],
    )
    assert_canonical_em_state(
        cast.coordinator, case, EM.EXITED, "case_closure"
    )


def _phase_dump_case_ledgers(
    reporter_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    case: as_VulnerabilityCase,
    demo_name: str = DEMO_NAME,
) -> None:
    """Dump each participant's case ledger (phase 8, DEMOMA-21-008).

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
        later_vendors=[(VENDOR2_NAME, vendor2_client)],
    )


def run_rcvv_embargo_demo(
    reporter_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    case_actor_client: DataLayerClient | None = None,
    reporter_id: str | None = None,
    coordinator_id: str | None = None,
    vendor_id: str | None = None,
    vendor2_id: str | None = None,
) -> None:
    """Orchestrate the RCVV embargo workflow."""
    logger.info("=" * 80)
    logger.info(
        "RCVV EMBARGO DEMO: Reporter + Coordinator(CASE_OWNER) + Vendor1 + Vendor2"
    )
    logger.info("=" * 80)
    logger.info("Reporter container:    %s", reporter_client.base_url)
    logger.info("Coordinator container: %s", coordinator_client.base_url)
    logger.info("Vendor1 container:     %s", vendor_client.base_url)
    logger.info("Vendor2 container:     %s", vendor2_client.base_url)
    if case_actor_client is not None:
        logger.info("CaseActor container:   %s", case_actor_client.base_url)

    # scenario_harness() owns the failure accumulator: it resets it, always
    # dumps the case ledgers (phase 8, dump_case_ledgers, DEMOMA-21-008) on the
    # way out whether or not a phase failed, and asserts success last
    # (ISSUE-2239).
    with scenario_harness(DEMO_NAME) as harness:
        cast, case, opened = _phase_report_submission(
            harness=harness,
            reporter_client=reporter_client,
            coordinator_client=coordinator_client,
            vendor_client=vendor_client,
            vendor2_client=vendor2_client,
            case_actor_client=case_actor_client,
            reporter_id=reporter_id,
            coordinator_id=coordinator_id,
            vendor_id=vendor_id,
            vendor2_id=vendor2_id,
        )
        proposed_embargo_id = _phase_embargo_proposal(cast, case)
        # The revision cycle revises the embargo phase 2 put in force; without
        # one, phases 3-7 would only pile secondary failures on the first.
        with demo_gate("Phase 2 put the revised embargo in force"):
            if proposed_embargo_id is None:
                raise AssertionError(
                    "no revised embargo; skipping phases 3-7"
                    " (embargo_revision through case_closure)"
                )
            revised_embargo_id = _phase_embargo_revision(
                cast, case, proposed_embargo_id
            )
            with demo_gate("Phase 3 put the second revision in force"):
                if revised_embargo_id is None:
                    raise AssertionError(
                        "no second revision; skipping phases 4-7"
                        " (v2_late_invite through case_closure)"
                    )
                if _phase_v2_late_invite(
                    cast, case, opened, revised_embargo_id
                ):
                    _phase_fix_lifecycle(cast, case)
                    _phase_accidental_collapse(cast, case)
                    _phase_case_closure(cast, case)

    logger.info("=" * 80)
    logger.info(
        "RCVV EMBARGO DEMO COMPLETE ✓  "
        "(EM: ACTIVE → REVISE → ACTIVE → REVISE → ACTIVE → EXITED)"
    )
    logger.info("=" * 80)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


@scenario(
    name=DEMO_NAME,
    label="RCVV embargo",
    participants="Reporter + Coordinator + Vendor1 + Vendor2",
    feature="Embargo revision cycle, late second vendor, and accidental collapse",
    in_pr_set=True,
)
def main(
    skip_health_check: bool = False,
    reporter_url: str | None = None,
    coordinator_url: str | None = None,
    vendor_url: str | None = None,
    vendor2_url: str | None = None,
    case_actor_url: str | None = None,
    reporter_id: str | None = None,
    coordinator_id: str | None = None,
    vendor_id: str | None = None,
    vendor2_id: str | None = None,
) -> None:
    """Entry point for the RCVV embargo demo.

    Args:
        skip_health_check: Skip the server availability check.
        reporter_url: Override base URL for the Reporter container.
        coordinator_url: Override base URL for the Coordinator container.
        vendor_url: Override base URL for the Vendor1 container.
        vendor2_url: Override base URL for the Vendor2 container.
        case_actor_url: Override base URL for the CaseActor container.
        reporter_id: Optional deterministic URI for the Reporter actor.
        coordinator_id: Optional deterministic URI for the Coordinator actor.
        vendor_id: Optional deterministic URI for the Vendor1 actor.
        vendor2_id: Optional deterministic URI for the Vendor2 actor.
    """
    reporter_client = DataLayerClient(
        base_url=reporter_url or REPORTER_BASE_URL
    )
    coordinator_client = DataLayerClient(
        base_url=coordinator_url or COORDINATOR_BASE_URL
    )
    vendor_client = DataLayerClient(base_url=vendor_url or VENDOR_BASE_URL)
    vendor2_client = DataLayerClient(base_url=vendor2_url or VENDOR2_BASE_URL)
    ca_url = case_actor_url or CASE_ACTOR_BASE_URL
    case_actor_client = DataLayerClient(
        base_url=ca_url, actor_id=case_actor_id_on(ca_url)
    )

    if not skip_health_check:
        targets: list[tuple[str, DataLayerClient]] = [
            ("Reporter", reporter_client),
            ("Coordinator", coordinator_client),
            ("Vendor1", vendor_client),
            ("Vendor2", vendor2_client),
            ("CaseActor", case_actor_client),
        ]
        check_all_containers(targets)

    run_rcvv_embargo_demo(
        reporter_client=reporter_client,
        coordinator_client=coordinator_client,
        vendor_client=vendor_client,
        vendor2_client=vendor2_client,
        case_actor_client=case_actor_client,
        reporter_id=reporter_id,
        coordinator_id=coordinator_id,
        vendor_id=vendor_id,
        vendor2_id=vendor2_id,
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
