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

"""rv (Reporter + Vendor) multi-container CVD workflow demo.

Orchestrates the full VFDPxa lifecycle across separate Reporter and Vendor
containers. The scenario module now delegates common workflow, notes, and
milestone logic to the generic helper modules under ``vultron.demo.helpers``
while preserving the public API used by the existing test suite.
"""

import logging
import sys

from vultron.adapters.utils import strip_id_prefix
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
from vultron.demo.helpers.ledger_commit import trigger_log_commit  # noqa: F401
from vultron.demo.helpers.ledger_dump import (
    LedgerDumpTarget,
    case_actor_dump_target,
    dump_case_ledgers,
    replica_route_key,
)
from vultron.demo.helpers.milestones import (
    verify_case_active,
    verify_case_closed,
    verify_fix_ready,
    verify_publicly_disclosed,
)
from vultron.demo.helpers.notes import participant_adds_note_to_case
from vultron.demo.helpers.polling import (  # noqa: F401
    _poll_until,
    wait_for_all_participants_rm_closed,
    wait_for_case_em_terminated,
    wait_for_case_participants,
    wait_for_note_in_case,
    wait_for_participant_rm_state,
    wait_for_participant_vf_state,
    wait_for_reporter_case,
    wait_for_reporter_log_entry,
)
from vultron.demo.helpers.seeding import (  # noqa: F401
    _dl_key,
    get_actor_by_id,
    reset_containers as _reset_containers,
    seed_case_participants_for_demo,
    seed_containers,
)
from vultron.demo.helpers.sync import (  # noqa: F401
    _extract_ref_id,
    run_sync_verification_phase,
)
from vultron.demo.helpers.verification import (  # noqa: F401
    _all_fetchable_participants_rm_closed,
    _assert_case_notes,
    _assert_participant_vf_pxa,
    _assert_vendor_case_status,
    _assert_vendor_participant_state,
    _check_participant_vf_state_in,
    _fetch_participant,
    _fetch_participant_data,
    _require_case_participant_id,
    verify_case_actor_holds_records,
    verify_receiver_case_state,
)
from vultron.demo.helpers.workflow import (  # noqa: F401
    _load_case_from_datalayer,
    find_case_for_offer,
    receiver_engages_case,
    receiver_validates_report,
    reporter_submits_report,
    run_direct_path_rm_triage,
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
    logfmt,
    ref_id,
    reset_datalayer,
    reset_demo_failures,
    seed_actor,
    setup_demo_logging,
    verify_object_stored,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Offer
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
        url_help="Base URL of the Vendor container API "
        "(env: VULTRON_VENDOR_BASE_URL).",
        has_id=True,
        id_help="Deterministic full URI for the Vendor actor (optional).",
    ),
    case_actor_role("http://localhost:7903/api/v2"),
]
_ROLES = role_map(ROLES)

# Default container base URLs — override via environment variables.
REPORTER_BASE_URL = _ROLES["reporter"].url
VENDOR_BASE_URL = _ROLES["vendor"].url
CASE_ACTOR_BASE_URL = _ROLES["case-actor"].url

#: ``vultron-demo rv --help`` text. Lives here rather than in ``cli.py`` because
#: the sub-command is generated from the registry and the scenario module is the
#: only place that knows what its own workflow does.
CLI_HELP = """Run the rv (Reporter + Vendor) multi-container CVD demo (D5-1-G5).

Orchestrates a complete CVD workflow across two separate API server
containers.  Requires both containers to be running and reachable at
the configured base URLs.

Use ``--reporter-url`` / ``--vendor-url`` (or env vars
``VULTRON_REPORTER_BASE_URL`` / ``VULTRON_VENDOR_BASE_URL``) to point
the demo at running containers.

\b
Workflow (six phases; titles match docs/tutorials/rv-demo.md):
  Setup. Seed both containers (actor records + peer registration).
  1. Report submission and case activation (M1): Reporter submits a report
     to Vendor's inbox; Vendor's tree proposes a case and the CaseActor
     creates it, seating the Reporter (it is never invited);
     Vendor validates (trigger: validate-report) and engages the case
     (trigger: engage-case).
  2. Replica synchronization verification (M2): verify the Reporter's case
     replica and that the ledgers synchronized.
  3. Notes exchange (M3): Reporter and Vendor exchange notes.
  4. Fix lifecycle (M4-M5): Vendor reports fix ready (VFd; Vendor stops
     at VFd).
  5. Publication and embargo teardown (M6): Vendor and Reporter report
     publication; embargo terminates (EM.EXITED).
  6. Case closure (M7): the Reporter closes the case, then the Vendor, the
     Case Owner, closes it last (every RM.CLOSED in the Case Actor's store).
"""

# Deterministic actor IDs from docker-compose-multi-actor.yml (D5-1-G3).
REPORTER_ACTOR_ID = "http://reporter:7999/api/v2/actors/reporter"
VENDOR_ACTOR_ID = "http://vendor:7999/api/v2/actors/vendor"

_load_vendor_case = _load_case_from_datalayer


def reset_containers(
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_actor_client: DataLayerClient,
) -> None:
    """Reset all containers used by the rv demo to a clean baseline.

    D5-2 requires repeatable, single-command execution. Resetting each
    container's DataLayer at the start of the run ensures the demo does
    not depend on a prior ``docker compose down -v``.  The dedicated
    case-actor container is reset too, and its CaseActor identity re-seeded,
    since the Vendor proposes the case to it (DEMOMA-06-004).

    The ``reset_datalayer`` reference is passed explicitly so that test-suite
    patches on this module's ``reset_datalayer`` name are correctly intercepted
    by the generic helper in ``vultron.demo.helpers.seeding``.
    """
    _reset_containers(
        [("Reporter", reporter_client), ("Vendor", vendor_client)],
        reset_fn=reset_datalayer,
        case_actor_client=case_actor_client,
    )


def vendor_validates_report(
    vendor_client: DataLayerClient,
    vendor: as_Actor,
    offer_id: str,
) -> dict:
    """Vendor validates the submitted report via the trigger endpoint.

    Thin scenario wrapper around
    :func:`~vultron.demo.helpers.workflow.receiver_validates_report`.
    """
    return receiver_validates_report(
        receiver_client=vendor_client,
        receiver=vendor,
        offer_id=offer_id,
    )


def vendor_engages_case(
    vendor_client: DataLayerClient,
    vendor: as_Actor,
    case_id: str,
) -> dict:
    """Vendor engages the case via the trigger endpoint (RM → ACCEPTED).

    Thin scenario wrapper around
    :func:`~vultron.demo.helpers.workflow.receiver_engages_case`.
    """
    return receiver_engages_case(
        receiver_client=vendor_client,
        receiver=vendor,
        case_id=case_id,
    )


def reporter_asks_question(
    vendor_client: DataLayerClient,
    reporter_client: DataLayerClient,
    vendor: as_Actor,
    reporter: as_Actor,
    case: as_VulnerabilityCase,
) -> as_Note | None:
    """Scenario alias: reporter adds a question note to the case.

    Maintained for backward compatibility; prefer
    :func:`~vultron.demo.helpers.notes.participant_adds_note_to_case` in new
    scenarios.
    """
    return participant_adds_note_to_case(
        posting_client=reporter_client,
        watching_client=vendor_client,
        poster=reporter,
        case=case,
        note_name="Question from Reporter",
        note_content=(
            "Is there a workaround available while waiting for the patch? "
            "Our security team needs to provide interim guidance to users."
        ),
    )


def vendor_replies_to_question(
    vendor_client: DataLayerClient,
    reporter_client: DataLayerClient,
    vendor: as_Actor,
    reporter: as_Actor,
    case: as_VulnerabilityCase,
    question_note: as_Note | None,
) -> as_Note | None:
    """Scenario alias: vendor adds a reply note to the case.

    Maintained for backward compatibility; prefer
    :func:`~vultron.demo.helpers.notes.participant_adds_note_to_case` in new
    scenarios.
    """
    return participant_adds_note_to_case(
        posting_client=vendor_client,
        watching_client=vendor_client,
        poster=vendor,
        case=case,
        note_name="Vendor Response",
        note_content=(
            "Yes, disabling the affected network stack component is an effective "
            "workaround. A patched version is expected within 30 days. "
            "We will notify all case participants when it is available."
        ),
        in_reply_to=question_note.id_ if question_note is not None else None,
    )


def verify_vendor_case_state(
    vendor_client: DataLayerClient,
    case_id: str,
    report_id: str,
    vendor_actor_id: str,
    reporter_actor_id: str,
    question_note_id: str | None = None,
    reply_note_id: str | None = None,
) -> as_VulnerabilityCase:
    """Scenario alias for :func:`~vultron.demo.helpers.verification.verify_receiver_case_state`.

    Maintained for backward compatibility; prefer
    ``verify_receiver_case_state`` in new scenarios.
    """
    return verify_receiver_case_state(
        receiver_client=vendor_client,
        case_id=case_id,
        report_id=report_id,
        receiver_actor_id=vendor_actor_id,
        reporter_actor_id=reporter_actor_id,
        question_note_id=question_note_id,
        reply_note_id=reply_note_id,
    )


def verify_m1_state(
    vendor_client: DataLayerClient,
    reporter_client: DataLayerClient,
    case_id: str,
    vendor_actor_id: str,
    reporter_actor_id: str,
) -> None:
    """Scenario alias for :func:`~vultron.demo.helpers.milestones.verify_case_active`.

    Maintained for backward compatibility; prefer ``verify_case_active`` in
    new scenarios.
    """
    return verify_case_active(
        receiver_client=vendor_client,
        reporter_client=reporter_client,
        case_id=case_id,
        receiver_actor_id=vendor_actor_id,
        reporter_actor_id=reporter_actor_id,
    )


def verify_m4_state(
    vendor_client: DataLayerClient,
    reporter_client: DataLayerClient,
    case_id: str,
    vendor_actor_id: str,
) -> None:
    """Scenario alias for :func:`~vultron.demo.helpers.milestones.verify_fix_ready`."""
    return verify_fix_ready(
        receiver_client=vendor_client,
        reporter_client=reporter_client,
        case_id=case_id,
        receiver_actor_id=vendor_actor_id,
    )


def verify_m5_state(
    vendor_client: DataLayerClient,
    reporter_client: DataLayerClient,
    case_id: str,
    vendor_actor_id: str,
) -> None:
    """Scenario alias for :func:`~vultron.demo.helpers.milestones.verify_fix_ready`.

    M5 in the rv scenario is fix-ready (VFd); vendor-only actors stop at VFd
    per CSB-15-002.
    """
    return verify_fix_ready(
        receiver_client=vendor_client,
        reporter_client=reporter_client,
        case_id=case_id,
        receiver_actor_id=vendor_actor_id,
    )


def verify_m6_state(
    vendor_client: DataLayerClient,
    reporter_client: DataLayerClient,
    case_id: str,
    vendor_actor_id: str,
) -> None:
    """Scenario alias for :func:`~vultron.demo.helpers.milestones.verify_publicly_disclosed`."""
    return verify_publicly_disclosed(
        receiver_client=vendor_client,
        reporter_client=reporter_client,
        case_id=case_id,
        receiver_actor_id=vendor_actor_id,
    )


def verify_m7_state(case_actor_client: DataLayerClient, case_id: str) -> None:
    """Scenario alias for :func:`~vultron.demo.helpers.milestones.verify_case_closed`.

    Read in the CASE_MANAGER's store on the dedicated case-actor container
    (CM-23-004): no participant replica holds every closure.
    """
    return verify_case_closed(
        case_manager_client=case_actor_client, case_id=case_id
    )


# ---------------------------------------------------------------------------
# Phase helpers
# ---------------------------------------------------------------------------


def _phase_report_submission(
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    reporter_id: str | None,
    vendor_id: str | None,
) -> tuple[
    as_Actor,
    as_Actor,
    as_Actor,
    as_VulnerabilityReport,
    as_Offer,
    as_VulnerabilityCase,
]:
    """Run reset, seeding, report submission, validation, and M1 verification."""
    logger.info("─" * 80)
    logger.info("Phase 1: Report submission and case activation")
    logger.info("─" * 80)

    reset_containers(
        reporter_client=reporter_client,
        vendor_client=vendor_client,
        case_actor_client=case_actor_client,
    )

    reporter = vendor = None
    with demo_step("Seeding both containers with actor records"):
        reporter, vendor = seed_containers(
            reporter_client=reporter_client,
            vendor_client=vendor_client,
            reporter_actor_id=reporter_id,
            vendor_actor_id=vendor_id,
        )

    vendor_in_vendor = get_actor_by_id(vendor_client, vendor.id_)
    report, offer = reporter_submits_report(
        receiver_client=vendor_client,
        reporter=reporter,
        receiver=vendor_in_vendor,
        reporter_client=reporter_client,
    )
    # ADR-0041: case creation is gated on the CaseActor accepting a CaseProposal.
    # run_direct_path_rm_triage fires validate-report (which sends
    # Create(CaseProposal) to the vendor's CaseActor), waits for the case to
    # appear, then drives RM through VALID → ACCEPTED via engage-case.
    case = run_direct_path_rm_triage(
        receiver_client=vendor_client,
        receiver=vendor_in_vendor,
        offer=offer,
    )

    with demo_gate("participant count ≥3 before M1 verify_case_active"):
        wait_for_case_participants(
            vendor_client=vendor_client,
            case_id=case.id_,
            expected_actor_ids={reporter.id_, vendor.id_},
        )

        with demo_check(
            "Reporter's DataLayer received case via Vendor outbox delivery"
        ):
            wait_for_reporter_case(
                reporter_client=reporter_client,
                case_id=case.id_,
            )
            logger.info(
                "Case %s confirmed in Reporter's DataLayer (outbox delivery verified)",
                case.id_,
            )

        with demo_check(
            "M1: required participants (vendor + reporter + case-actor, ≥3), "
            "EM.ACTIVE, reporter has case replica"
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
    return reporter, vendor, vendor_in_vendor, report, offer, case


def _phase_notes_exchange(
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    reporter: as_Actor,
    vendor: as_Actor,
    vendor_in_vendor: as_Actor,
    case: as_VulnerabilityCase,
    report: as_VulnerabilityReport,
) -> tuple[as_Note | None, as_Note | None, as_VulnerabilityCase, as_Actor]:
    """Run the question-and-reply note exchange and verify M3 state."""
    logger.info("─" * 80)
    logger.info("Phase 3: Notes exchange")
    logger.info("─" * 80)

    reporter_in_reporter = get_actor_by_id(reporter_client, reporter.id_)
    question_note = reporter_asks_question(
        vendor_client=vendor_client,
        reporter_client=reporter_client,
        vendor=vendor_in_vendor,
        reporter=reporter_in_reporter,
        case=case,
    )
    reply_note = vendor_replies_to_question(
        vendor_client=vendor_client,
        reporter_client=reporter_client,
        vendor=vendor_in_vendor,
        reporter=reporter_in_reporter,
        case=case,
        question_note=question_note,
    )

    final_case = None
    with demo_check(
        "M3: Vendor container holds the authoritative final case state"
    ):
        final_case = verify_receiver_case_state(
            receiver_client=vendor_client,
            case_id=case.id_,
            report_id=report.id_,
            receiver_actor_id=vendor.id_,
            reporter_actor_id=reporter.id_,
            question_note_id=(
                question_note.id_ if question_note is not None else None
            ),
            reply_note_id=reply_note.id_ if reply_note is not None else None,
        )
        logger.info("Final case state (Vendor): %s", logfmt(final_case))

    return question_note, reply_note, final_case, reporter_in_reporter


def _phase_sync_verification(
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    vendor: as_Actor,
    reporter: as_Actor,
    case: as_VulnerabilityCase,
    case_actor_client: DataLayerClient,
) -> None:
    """Verify LedgerFanout replication and that the dedicated CaseActor holds the case."""
    logger.info("─" * 80)
    logger.info("Phase 2: Replica synchronization verification")
    logger.info("─" * 80)

    # Synthetic checkpoint entries (demo_verification) are excluded from the
    # canonical case ledger (ADR-0019, CLP-07-004), so replication is verified
    # by comparing replica state directly rather than polling for a new entry
    # (issue #1434).
    run_sync_verification_phase(
        auth_client=vendor_client,
        auth_label="Vendor",
        auth_actor_id=vendor.id_,
        reporter_client=reporter_client,
        reporter_actor_id=reporter.id_,
        replicas=[(reporter_client, "Reporter")],
        case_id=case.id_,
        state_checks=[(reporter_client, "Reporter")],
    )

    with demo_check(
        "Dedicated case-actor container holds the case, with its CaseActor as"
        " the CASE_MANAGER participant (DEMOMA-06-004)"
    ):
        verify_case_actor_holds_records(case_actor_client, case.id_)

    logger.info(
        "✓ M2: Reporter DataLayer synchronized (LedgerFanout verified)"
    )


def _phase_fix_lifecycle(
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    vendor: as_Actor,
    vendor_in_vendor: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Advance the case through fix-ready and fix-deployed milestones."""
    logger.info("─" * 80)
    logger.info(
        "Phase 4: Fix lifecycle — VFd (fix ready); vendor stops at VFd (CSB-15-002)"
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

        with demo_check("Vendor participant vf_state transitions to VF"):
            wait_for_participant_vf_state(
                client=vendor_client,
                case_id=case.id_,
                actor_id=vendor.id_,
                expected_states={CS_vf.VF},
            )

        with demo_gate("M4/M5: reporter replica reflects fix-ready vf_state"):
            wait_for_participant_vf_state(
                client=reporter_client,
                case_id=case.id_,
                actor_id=vendor.id_,
                expected_states={CS_vf.VF},
            )
            with demo_check(
                "M4: both replicas show CS includes F (fix ready)"
            ):
                wait_for_participant_vf_state(
                    client=vendor_client,
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
                "M5: both replicas show CS includes F (fix ready) — vendor stops at VFd"
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
    vendor: as_Actor,
    vendor_in_vendor: as_Actor,
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
        f"Actor {ref_id(vendor_in_vendor)} reports vulnerability publicly disclosed"
    ):
        ActorSession(client=vendor_client, actor=vendor_in_vendor).with_case(
            case
        ).quiet().notify_published()

    with demo_check(
        "Embargo terminated (EM.EXITED) after Vendor reports published"
    ):
        wait_for_case_em_terminated(
            client=vendor_client,
            case_id=case.id_,
        )

    with demo_step(
        f"Actor {ref_id(reporter_in_reporter)} reports vulnerability publicly disclosed"
    ):
        ActorSession(
            client=reporter_client, actor=reporter_in_reporter
        ).with_case(case).quiet().notify_published()

    with demo_check(
        "M6: both replicas CS.VFdPxa, EM.EXITED, vendor participant is "
        "public-aware"
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
    vendor: as_Actor,
    vendor_in_vendor: as_Actor,
    reporter: as_Actor,
    reporter_in_reporter: as_Actor,
    case: as_VulnerabilityCase,
    case_actor_client: DataLayerClient,
) -> None:
    """Close the case from both participants and verify terminal state.

    The Reporter leaves first; the Vendor, the Case Owner, leaves last, once
    the Reporter's departure is recorded (CM-23-015) in the CASE_MANAGER's store
    on the dedicated case-actor container.
    """
    logger.info("─" * 80)
    logger.info("Phase 6: Case closure — all participants RM.CLOSED")
    logger.info("─" * 80)

    close_case_owner_last(
        case=case,
        milestone="M7",
        authority_client=case_actor_client,
        others=[
            CaseLeaver(client=reporter_client, actor=reporter_in_reporter)
        ],
        owner=CaseLeaver(client=vendor_client, actor=vendor_in_vendor),
    )


def _phase_dump_case_ledgers(
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    reporter: as_Actor,
    vendor: as_Actor,
    case: as_VulnerabilityCase,
    case_actor_client: DataLayerClient,
    demo_name: str = "rv",
) -> None:
    """Dump case ledger entries from each actor container to JSONL files.

    Thin scenario-specific wrapper over
    :func:`~vultron.demo.helpers.ledger_dump.dump_case_ledgers`, which owns the
    per-actor export, the 404 handling, and the dump manifest written under
    ``{DEVLOGS_DIR}/{demo_name}/``. This function only names rv's participants
    and where each one's ledger lives.

    The case-actor log is read from the dedicated case-actor container, which
    holds the canonical ledger (DEMOMA-06-005).

    Args:
        reporter_client: DataLayerClient for the Reporter container.
        vendor_client: DataLayerClient for the Vendor container.
        reporter: Reporter actor object (used to derive the actor object ID).
        vendor: Vendor actor object (used to derive the actor object ID).
        case: The as_VulnerabilityCase whose log entries are to be exported.
        case_actor_client: DataLayerClient for the dedicated CaseActor container.
        demo_name: Sub-directory name under the output root (default ``"rv"``).
    """
    # Route keys come from the actors' own ids, not from their display names.
    # These were the literals "reporter" and "vendor", which worked only while the
    # route key was decorative: a shared store returned the combined case log
    # whichever actor the path named. The route key now *selects the store*
    # (ADR-0073), so a literal reads whichever actor happens to be hosted under
    # that slug — a different actor from the one this run used, whose store is
    # empty. The dump then reported "No case ledger entries for actor='reporter'"
    # while the reporter's real store held twelve.
    #
    # The actor objects are in hand here, so they are the key's source; the
    # literal is passed to replica_route_key() only as the last-resort fallback
    # the sibling scenarios also use, keeping one derivation path across all of
    # them.
    targets = [
        LedgerDumpTarget(
            "reporter",
            reporter_client,
            strip_id_prefix(reporter.id_ or "")
            or replica_route_key(reporter_client, "reporter"),
        ),
        LedgerDumpTarget(
            "vendor",
            vendor_client,
            strip_id_prefix(vendor.id_ or "")
            or replica_route_key(vendor_client, "vendor"),
        ),
        case_actor_dump_target(case_actor_client),
    ]

    dump_case_ledgers(demo_name=demo_name, case=case, targets=targets)


def run_rv_demo(
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    reporter_id: str | None = None,
    vendor_id: str | None = None,
) -> None:
    """Orchestrate the complete rv (Reporter + Vendor) CVD workflow."""
    logger.info("=" * 80)
    logger.info("rv DEMO: Reporter + Vendor CVD Workflow (VFDPxa)")
    logger.info("=" * 80)
    logger.info("Reporter container: %s", reporter_client.base_url)
    logger.info("Vendor container: %s", vendor_client.base_url)
    logger.info("CaseActor container: %s", case_actor_client.base_url)

    with scenario_harness("rv") as harness:
        reporter, vendor, vendor_in_vendor, report, _offer, case = (
            _phase_report_submission(
                reporter_client,
                vendor_client,
                case_actor_client,
                reporter_id,
                vendor_id,
            )
        )

        # Register the dump as soon as there is a case to dump, so every phase
        # below can fail without costing us the ledgers (ISSUE-2239).
        harness.dump_with(
            lambda: _phase_dump_case_ledgers(
                reporter_client=reporter_client,
                vendor_client=vendor_client,
                reporter=reporter,
                vendor=vendor,
                case=case,
                case_actor_client=case_actor_client,
                demo_name=harness.demo_name,
            )
        )

        _phase_sync_verification(
            reporter_client,
            vendor_client,
            vendor,
            reporter,
            case,
            case_actor_client,
        )
        _, _, _, reporter_in_reporter = _phase_notes_exchange(
            reporter_client,
            vendor_client,
            reporter,
            vendor,
            vendor_in_vendor,
            case,
            report,
        )
        _phase_fix_lifecycle(
            reporter_client,
            vendor_client,
            vendor,
            vendor_in_vendor,
            case,
        )
        _phase_publication(
            reporter_client,
            vendor_client,
            vendor,
            vendor_in_vendor,
            reporter,
            reporter_in_reporter,
            case,
        )
        _phase_case_closure(
            reporter_client,
            vendor_client,
            vendor,
            vendor_in_vendor,
            reporter,
            reporter_in_reporter,
            case,
            case_actor_client,
        )

    logger.info("=" * 80)
    logger.info("rv DEMO COMPLETE ✓  (VFDPxa full lifecycle)")
    logger.info("=" * 80)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


@scenario(
    name="rv",
    label="rv",
    participants="Reporter + Vendor",
    feature="Baseline two-actor CVD",
    in_pr_set=True,
)
def main(
    skip_health_check: bool = False,
    reporter_url: str | None = None,
    vendor_url: str | None = None,
    case_actor_url: str | None = None,
    reporter_id: str | None = None,
    vendor_id: str | None = None,
) -> None:
    """Entry point for the rv (Reporter + Vendor) multi-container CVD workflow demo.

    Args:
        skip_health_check: Skip the server availability check (useful for
            testing).
        reporter_url: Override base URL for the Reporter container.
        vendor_url: Override base URL for the Vendor container.
        case_actor_url: Override base URL for the dedicated CaseActor container.
        reporter_id: Optional deterministic URI for the Reporter actor.
        vendor_id: Optional deterministic URI for the Vendor actor.
    """
    f_url = reporter_url or REPORTER_BASE_URL
    v_url = vendor_url or VENDOR_BASE_URL
    c_url = case_actor_url or CASE_ACTOR_BASE_URL

    reporter_client = DataLayerClient(base_url=f_url)
    vendor_client = DataLayerClient(base_url=v_url)
    # actor_id must be bound here: the dedicated CaseActor container hosts the
    # `case-actor` actor, and a /datalayer/ read has to name whose store it is
    # about (ADR-0073).  Leaving it unset makes every dl_path() call raise.
    case_actor_client = bound_case_actor_client(c_url)

    if not skip_health_check:
        targets: list[tuple[str, DataLayerClient]] = [
            ("Reporter", reporter_client),
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

    # scenario_harness() inside run_rv_demo() owns the failure accumulator: it
    # resets it, always dumps the case ledgers, and asserts success — so a
    # failure here never costs us the artifacts (ISSUE-2239).
    run_rv_demo(
        reporter_client=reporter_client,
        vendor_client=vendor_client,
        case_actor_client=case_actor_client,
        reporter_id=reporter_id,
        vendor_id=vendor_id,
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
