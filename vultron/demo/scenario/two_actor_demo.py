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

"""Two-actor (Finder + Vendor) multi-container CVD workflow demo.

Orchestrates the full VFDPxa lifecycle across separate Finder and Vendor
containers. The scenario module now delegates common workflow, notes, and
milestone logic to the generic helper modules under ``vultron.demo.helpers``
while preserving the public API used by the existing test suite.
"""

import json
import logging
import os
import pathlib
import sys
from typing import Optional, Tuple

import httpx

from vultron.adapters.utils import strip_id_prefix
from vultron.core.states.cs import CS_vfd
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Offer
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)

from vultron.demo.utils import (  # noqa: F401 — re-exported for test monkeypatching
    BASE_URL,
    DataLayerClient,
    assert_demo_success,
    check_server_availability,
    demo_check,
    demo_step,
    logfmt,
    post_to_inbox_and_wait,
    post_to_trigger,
    ref_id,
    reset_datalayer,
    reset_demo_failures,
    seed_actor,
    verify_object_stored,
)

# Re-export shared helpers so that existing imports via this module continue to
# work and the test suite (which patches symbols in this module's namespace)
# remains unchanged.
from vultron.demo.helpers.actions import (  # noqa: F401
    actor_closes_case,
    actor_notifies_fix_deployed,
    actor_notifies_fix_ready,
    actor_notifies_published,
    actor_notifies_state_change,
)
from vultron.demo.helpers.milestones import (
    verify_case_active,
    verify_case_closed,
    verify_fix_deployed,
    verify_fix_ready,
    verify_publicly_disclosed,
)
from vultron.demo.helpers.notes import participant_adds_note_to_case
from vultron.demo.helpers.polling import (  # noqa: F401
    _poll_until,
    wait_for_all_participants_rm_closed,
    wait_for_case_em_terminated,
    wait_for_case_on_container,
    wait_for_case_participants,
    wait_for_finder_case,
    wait_for_finder_log_entry,
    wait_for_note_in_case,
    wait_for_participant_vfd_state,
)
from vultron.demo.helpers.seeding import (  # noqa: F401
    _dl_key,
    get_actor_by_id,
    reset_containers as _reset_containers,
    seed_containers,
)
from vultron.demo.helpers.sync import (  # noqa: F401
    _extract_ref_id,
    _get_log_entries_for_case,
    trigger_log_commit,
    verify_finder_replica_state,
    verify_replica_state,
)
from vultron.demo.helpers.verification import (  # noqa: F401
    _all_fetchable_participants_rm_closed,
    _assert_case_notes,
    _assert_participant_vfd_pxa,
    _assert_vendor_case_status,
    _assert_vendor_participant_state,
    _check_participant_vfd_state_in,
    _fetch_participant,
    _fetch_participant_data,
    _require_case_participant_id,
    verify_case_actor_unused,
    verify_coordinator_case_state,
)
from vultron.demo.helpers.workflow import (  # noqa: F401
    _load_case_from_datalayer,
    _report_id_from_offer_data,
    coordinator_validates_report,
    find_case_for_offer,
    reporter_submits_report,
)

logger = logging.getLogger(__name__)

# Default container base URLs — override via environment variables.
FINDER_BASE_URL = os.environ.get(
    "VULTRON_FINDER_BASE_URL", "http://localhost:7901/api/v2"
)
VENDOR_BASE_URL = os.environ.get(
    "VULTRON_VENDOR_BASE_URL", "http://localhost:7902/api/v2"
)
CASE_ACTOR_BASE_URL = os.environ.get(
    "VULTRON_CASE_ACTOR_BASE_URL", "http://localhost:7903/api/v2"
)

# Deterministic actor IDs from docker-compose-multi-actor.yml (D5-1-G3).
FINDER_ACTOR_ID = "http://finder:7999/api/v2/actors/finder"
VENDOR_ACTOR_ID = "http://vendor:7999/api/v2/actors/vendor"

_load_vendor_case = _load_case_from_datalayer


def reset_containers(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_actor_client: DataLayerClient | None = None,
) -> None:
    """Reset all containers used by the two-actor demo to a clean baseline.

    D5-2 requires repeatable, single-command execution. Resetting each
    container's DataLayer at the start of the run ensures the demo does
    not depend on a prior ``docker compose down -v``.

    The ``reset_datalayer`` reference is passed explicitly so that test-suite
    patches on this module's ``reset_datalayer`` name are correctly intercepted
    by the generic helper in ``vultron.demo.helpers.seeding``.
    """
    targets: list[tuple[str, DataLayerClient]] = [
        ("Finder", finder_client),
        ("Vendor", vendor_client),
    ]
    if case_actor_client is not None:
        targets.append(("CaseActor", case_actor_client))
    _reset_containers(targets, reset_fn=reset_datalayer)


# ---------------------------------------------------------------------------
# Backward-compatible scenario wrappers
# ---------------------------------------------------------------------------


def finder_submits_report(
    vendor_client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    finder_client: Optional[DataLayerClient] = None,
) -> Tuple[VulnerabilityReport, as_Offer]:
    """Scenario alias for :func:`~vultron.demo.helpers.workflow.reporter_submits_report`.

    Maintained for backward compatibility; prefer ``reporter_submits_report``
    in new scenarios.
    """
    return reporter_submits_report(
        coordinator_client=vendor_client,
        reporter=finder,
        coordinator=vendor,
        reporter_client=finder_client,
    )


def vendor_validates_report(
    vendor_client: DataLayerClient,
    vendor: as_Actor,
    offer_id: str,
) -> dict:
    """Scenario alias for :func:`~vultron.demo.helpers.workflow.coordinator_validates_report`.

    Maintained for backward compatibility; prefer
    ``coordinator_validates_report`` in new scenarios.
    """
    return coordinator_validates_report(
        coordinator_client=vendor_client,
        coordinator=vendor,
        offer_id=offer_id,
    )


def finder_asks_question(
    vendor_client: DataLayerClient,
    finder_client: DataLayerClient,
    vendor: as_Actor,
    finder: as_Actor,
    case: VulnerabilityCase,
) -> as_Note:
    """Scenario alias: finder adds a question note to the case.

    Maintained for backward compatibility; prefer
    :func:`~vultron.demo.helpers.notes.participant_adds_note_to_case` in new
    scenarios.
    """
    return participant_adds_note_to_case(
        posting_client=finder_client,
        watching_client=vendor_client,
        poster=finder,
        case=case,
        note_name="Question from Finder",
        note_content=(
            "Is there a workaround available while waiting for the patch? "
            "Our security team needs to provide interim guidance to users."
        ),
    )


def vendor_replies_to_question(
    vendor_client: DataLayerClient,
    finder_client: DataLayerClient,
    vendor: as_Actor,
    finder: as_Actor,
    case: VulnerabilityCase,
    question_note: as_Note,
) -> as_Note:
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
        in_reply_to=question_note.id_,
    )


def verify_vendor_case_state(
    vendor_client: DataLayerClient,
    case_id: str,
    report_id: str,
    vendor_actor_id: str,
    reporter_actor_id: str,
    question_note_id: Optional[str] = None,
    reply_note_id: Optional[str] = None,
) -> VulnerabilityCase:
    """Scenario alias for :func:`~vultron.demo.helpers.verification.verify_coordinator_case_state`.

    Maintained for backward compatibility; prefer
    ``verify_coordinator_case_state`` in new scenarios.
    """
    return verify_coordinator_case_state(
        coordinator_client=vendor_client,
        case_id=case_id,
        report_id=report_id,
        coordinator_actor_id=vendor_actor_id,
        reporter_actor_id=reporter_actor_id,
        question_note_id=question_note_id,
        reply_note_id=reply_note_id,
    )


def verify_m1_state(
    vendor_client: DataLayerClient,
    finder_client: DataLayerClient,
    case_id: str,
    vendor_actor_id: str,
    reporter_actor_id: str,
) -> None:
    """Scenario alias for :func:`~vultron.demo.helpers.milestones.verify_case_active`.

    Maintained for backward compatibility; prefer ``verify_case_active`` in
    new scenarios.
    """
    return verify_case_active(
        coordinator_client=vendor_client,
        reporter_client=finder_client,
        case_id=case_id,
        coordinator_actor_id=vendor_actor_id,
        reporter_actor_id=reporter_actor_id,
    )


def verify_m4_state(
    vendor_client: DataLayerClient,
    finder_client: DataLayerClient,
    case_id: str,
    vendor_actor_id: str,
) -> None:
    """Scenario alias for :func:`~vultron.demo.helpers.milestones.verify_fix_ready`."""
    return verify_fix_ready(
        coordinator_client=vendor_client,
        reporter_client=finder_client,
        case_id=case_id,
        coordinator_actor_id=vendor_actor_id,
    )


def verify_m5_state(
    vendor_client: DataLayerClient,
    finder_client: DataLayerClient,
    case_id: str,
    vendor_actor_id: str,
) -> None:
    """Scenario alias for :func:`~vultron.demo.helpers.milestones.verify_fix_deployed`."""
    return verify_fix_deployed(
        coordinator_client=vendor_client,
        reporter_client=finder_client,
        case_id=case_id,
        coordinator_actor_id=vendor_actor_id,
    )


def verify_m6_state(
    vendor_client: DataLayerClient,
    finder_client: DataLayerClient,
    case_id: str,
    vendor_actor_id: str,
) -> None:
    """Scenario alias for :func:`~vultron.demo.helpers.milestones.verify_publicly_disclosed`."""
    return verify_publicly_disclosed(
        coordinator_client=vendor_client,
        reporter_client=finder_client,
        case_id=case_id,
        coordinator_actor_id=vendor_actor_id,
    )


def verify_m7_state(
    vendor_client: DataLayerClient,
    finder_client: DataLayerClient,
    case_id: str,
) -> None:
    """Scenario alias for :func:`~vultron.demo.helpers.milestones.verify_case_closed`."""
    return verify_case_closed(
        coordinator_client=vendor_client,
        reporter_client=finder_client,
        case_id=case_id,
    )


# ---------------------------------------------------------------------------
# Phase helpers
# ---------------------------------------------------------------------------


def _phase_report_submission(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_actor_client: DataLayerClient | None,
    finder_id: str | None,
    vendor_id: str | None,
) -> tuple[
    as_Actor,
    as_Actor,
    as_Actor,
    VulnerabilityReport,
    as_Offer,
    VulnerabilityCase,
]:
    """Run reset, seeding, report submission, validation, and M1 verification."""
    logger.info("─" * 80)
    logger.info("Phase 1: Report submission and case activation")
    logger.info("─" * 80)

    reset_containers(
        finder_client=finder_client,
        vendor_client=vendor_client,
        case_actor_client=case_actor_client,
    )

    with demo_step("Seeding both containers with actor records"):
        finder, vendor = seed_containers(
            finder_client=finder_client,
            vendor_client=vendor_client,
            reporter_actor_id=finder_id,
            vendor_actor_id=vendor_id,
        )

    vendor_in_vendor = get_actor_by_id(vendor_client, vendor.id_)
    report, offer = reporter_submits_report(
        coordinator_client=vendor_client,
        reporter=finder,
        coordinator=vendor_in_vendor,
        reporter_client=finder_client,
    )
    coordinator_validates_report(
        coordinator_client=vendor_client,
        coordinator=vendor_in_vendor,
        offer_id=offer.id_,
    )

    with demo_check("VulnerabilityCase exists in Vendor's DataLayer"):
        case = find_case_for_offer(vendor_client, offer.id_)
        if case is None:
            raise AssertionError(
                "Expected VulnerabilityCase to be created after validate-report"
            )
        logger.info("Case created: %s", case.id_)

    wait_for_case_participants(
        vendor_client=vendor_client,
        case_id=case.id_,
        expected_count=3,
    )

    with demo_check(
        "Finder's DataLayer received case via Vendor outbox delivery"
    ):
        wait_for_finder_case(
            finder_client=finder_client,
            case_id=case.id_,
        )
        logger.info(
            "Case %s confirmed in Finder's DataLayer (outbox delivery verified)",
            case.id_,
        )

    with demo_check(
        "M1: required participants (vendor + finder + case-actor, ≥3), "
        "EM.ACTIVE, finder has case replica"
    ):
        verify_case_active(
            coordinator_client=vendor_client,
            reporter_client=finder_client,
            case_id=case.id_,
            coordinator_actor_id=vendor.id_,
            reporter_actor_id=finder.id_,
        )

    case = VulnerabilityCase.model_validate(
        vendor_client.get(f"/datalayer/{case.id_}")
    )
    return finder, vendor, vendor_in_vendor, report, offer, case


def _phase_notes_exchange(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    vendor_in_vendor: as_Actor,
    case: VulnerabilityCase,
    report: VulnerabilityReport,
) -> tuple[as_Note, as_Note, VulnerabilityCase, as_Actor]:
    """Run the question-and-reply note exchange and verify M3 state."""
    logger.info("─" * 80)
    logger.info("Phase 3: Notes exchange")
    logger.info("─" * 80)

    finder_in_finder = get_actor_by_id(finder_client, finder.id_)
    question_note = finder_asks_question(
        vendor_client=vendor_client,
        finder_client=finder_client,
        vendor=vendor_in_vendor,
        finder=finder_in_finder,
        case=case,
    )
    reply_note = vendor_replies_to_question(
        vendor_client=vendor_client,
        finder_client=finder_client,
        vendor=vendor_in_vendor,
        finder=finder_in_finder,
        case=case,
        question_note=question_note,
    )

    with demo_check(
        "M3: Vendor container holds the authoritative final case state"
    ):
        final_case = verify_coordinator_case_state(
            coordinator_client=vendor_client,
            case_id=case.id_,
            report_id=report.id_,
            coordinator_actor_id=vendor.id_,
            reporter_actor_id=finder.id_,
            question_note_id=question_note.id_,
            reply_note_id=reply_note.id_,
        )
        logger.info("Final case state (Vendor): %s", logfmt(final_case))

    return question_note, reply_note, final_case, finder_in_finder


def _phase_sync_verification(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    vendor: as_Actor,
    finder: as_Actor,
    case: VulnerabilityCase,
    case_actor_client: DataLayerClient | None,
) -> None:
    """Verify SYNC-2 replication and confirm the dedicated case actor is unused."""
    logger.info("─" * 80)
    logger.info("Phase 2: Replica synchronization verification")
    logger.info("─" * 80)

    with demo_step("Committing case log entry on Vendor (CaseActor)"):
        entry_hash = trigger_log_commit(
            client=vendor_client,
            actor_id=vendor.id_,
            case_id=case.id_,
            event_type="demo_verification",
        )

    with demo_step("Waiting for Finder to receive replicated log entry"):
        wait_for_finder_log_entry(
            finder_client=finder_client,
            case_id=case.id_,
            entry_hash=entry_hash,
        )

    with demo_check("Finder replica state matches authoritative Vendor state"):
        verify_finder_replica_state(
            finder_client=finder_client,
            vendor_client=vendor_client,
            case_id=case.id_,
            vendor_actor_id=vendor.id_,
            reporter_actor_id=finder.id_,
        )

    with demo_check("Dedicated CaseActor container remains unused for D5-2"):
        verify_case_actor_unused(case_actor_client, case.id_)

    logger.info("✓ M2: Finder DataLayer synchronized (SYNC-2 verified)")


def _phase_fix_lifecycle(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    vendor: as_Actor,
    vendor_in_vendor: as_Actor,
    case: VulnerabilityCase,
) -> None:
    """Advance the case through fix-ready and fix-deployed milestones."""
    logger.info("─" * 80)
    logger.info(
        "Phase 4: Fix lifecycle — VFd (fix ready) → VFD (fix deployed)"
    )
    logger.info("─" * 80)

    actor_notifies_fix_ready(
        client=vendor_client,
        actor=vendor_in_vendor,
        case_id=case.id_,
    )

    with demo_check("Vendor participant vfd_state transitions to VFd or VFD"):
        wait_for_participant_vfd_state(
            client=vendor_client,
            case_id=case.id_,
            actor_id=vendor.id_,
            expected_states={CS_vfd.VFd, CS_vfd.VFD},
        )

    with demo_check("M4: both replicas show CS includes F (fix ready)"):
        wait_for_participant_vfd_state(
            client=finder_client,
            case_id=case.id_,
            actor_id=vendor.id_,
            expected_states={CS_vfd.VFd, CS_vfd.VFD},
        )
        verify_fix_ready(
            coordinator_client=vendor_client,
            reporter_client=finder_client,
            case_id=case.id_,
            coordinator_actor_id=vendor.id_,
        )

    actor_notifies_fix_deployed(
        client=vendor_client,
        actor=vendor_in_vendor,
        case_id=case.id_,
    )

    with demo_check("M5: both replicas show CS includes D (fix deployed)"):
        wait_for_participant_vfd_state(
            client=finder_client,
            case_id=case.id_,
            actor_id=vendor.id_,
            expected_states={CS_vfd.VFD},
        )
        verify_fix_deployed(
            coordinator_client=vendor_client,
            reporter_client=finder_client,
            case_id=case.id_,
            coordinator_actor_id=vendor.id_,
        )


def _phase_publication(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    vendor: as_Actor,
    vendor_in_vendor: as_Actor,
    finder: as_Actor,
    finder_in_finder: as_Actor,
    case: VulnerabilityCase,
) -> None:
    """Run publication notifications and verify public disclosure state."""
    logger.info("─" * 80)
    logger.info(
        "Phase 5: Publication — CS.VFDPxa + embargo teardown (EM.EXITED)"
    )
    logger.info("─" * 80)

    actor_notifies_published(
        client=vendor_client,
        actor=vendor_in_vendor,
        case_id=case.id_,
    )

    with demo_check(
        "Embargo terminated (EM.EXITED) after Vendor reports published"
    ):
        wait_for_case_em_terminated(
            client=vendor_client,
            case_id=case.id_,
        )

    actor_notifies_published(
        client=finder_client,
        actor=finder_in_finder,
        case_id=case.id_,
    )

    with demo_check(
        "M6: both replicas CS.VFDPxa, EM.EXITED, vendor participant is "
        "public-aware"
    ):
        wait_for_case_em_terminated(
            client=finder_client,
            case_id=case.id_,
        )
        verify_publicly_disclosed(
            coordinator_client=vendor_client,
            reporter_client=finder_client,
            case_id=case.id_,
            coordinator_actor_id=vendor.id_,
        )


def _phase_case_closure(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    vendor: as_Actor,
    vendor_in_vendor: as_Actor,
    finder: as_Actor,
    finder_in_finder: as_Actor,
    case: VulnerabilityCase,
) -> None:
    """Close the case from both participants and verify terminal state."""
    logger.info("─" * 80)
    logger.info("Phase 6: Case closure — all participants RM.CLOSED")
    logger.info("─" * 80)

    actor_closes_case(
        client=vendor_client,
        actor=vendor_in_vendor,
        case_id=case.id_,
    )
    actor_closes_case(
        client=finder_client,
        actor=finder_in_finder,
        case_id=case.id_,
    )

    with demo_check("M7: all participants RM.CLOSED on both replicas"):
        wait_for_all_participants_rm_closed(
            client=vendor_client,
            case_id=case.id_,
        )
        wait_for_all_participants_rm_closed(
            client=finder_client,
            case_id=case.id_,
        )
        verify_case_closed(
            coordinator_client=vendor_client,
            reporter_client=finder_client,
            case_id=case.id_,
        )


# ---------------------------------------------------------------------------
# Case log export
# ---------------------------------------------------------------------------


def _phase_dump_case_logs(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    case: VulnerabilityCase,
    case_actor_client: DataLayerClient | None = None,
    demo_name: str = "two-actor",
) -> None:
    """Dump case log entries from each actor container to JSONL files.

    Reads ``DEVLOGS_DIR`` from the environment (default ``/app/devlogs``) and
    writes one JSONL file per actor under::

        {DEVLOGS_DIR}/{demo_name}/{actor_name}/{case_id_slug}-case-log.jsonl

    The case-actor log is always included: from *case_actor_client* when a
    dedicated case-actor service is configured, otherwise from the vendor
    container using the in-container case-actor sub-actor route key. Each
    dump step is wrapped in ``demo_step`` so that a failure is recorded and
    ultimately surfaced by ``assert_demo_success()``.

    Args:
        finder_client: DataLayerClient for the Finder container.
        vendor_client: DataLayerClient for the Vendor container.
        finder: Finder actor object (used to derive the actor object ID).
        vendor: Vendor actor object (used to derive the actor object ID).
        case: The VulnerabilityCase whose log entries are to be exported.
        case_actor_client: Optional DataLayerClient for the CaseActor container.
        demo_name: Sub-directory name under the output root (default
            ``"two-actor"``).
    """
    logger.info("─" * 80)
    logger.info("Phase: Case log JSONL export")
    logger.info("─" * 80)

    output_root = pathlib.Path(os.environ.get("DEVLOGS_DIR", "/app/devlogs"))
    case_id = case.id_ or ""
    case_id_slug = (
        case_id.replace("://", "_")
        .replace("/", "_")
        .replace(":", "_")
        .strip("_")
    )

    case_actor_sub_actor_key = next(
        (
            strip_id_prefix(actor_id)
            for actor_id in case.actor_participant_index
            if strip_id_prefix(actor_id).startswith("case-actor")
        ),
        None,
    )

    actors: list[tuple[str, DataLayerClient, str]] = [
        ("finder", finder_client, "finder"),
        ("vendor", vendor_client, "vendor"),
    ]
    if case_actor_client is not None:
        actors.append(("case-actor", case_actor_client, "case-actor"))
    elif case_actor_sub_actor_key is not None:
        actors.append(("case-actor", vendor_client, case_actor_sub_actor_key))

    for actor_name, client, actor_route_key in actors:
        with demo_step(f"Dumping case log for {actor_name}"):
            case_key = strip_id_prefix(case_id)
            log_path = f"/actors/{actor_route_key}/demo/cases/{case_key}/log"
            try:
                entries = client.get_list(log_path)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 404:
                    raise
                # D5-2: the dedicated case-actor container does not hold the
                # case; the case-actor sub-actor runs inside the vendor
                # container. Treat 404 the same as an empty list so the
                # sub-actor fallback below can supply the entries.
                logger.info(
                    "Case not found on dedicated %s container (HTTP 404, D5-2);"
                    " will attempt vendor sub-actor fallback.",
                    actor_name,
                )
                entries = []
            if (
                not entries
                and actor_name == "case-actor"
                and client is case_actor_client
                and case_actor_sub_actor_key is not None
            ):
                fallback_path = (
                    "/actors/"
                    f"{case_actor_sub_actor_key}/demo/cases/{case_key}/log"
                )
                logger.info(
                    "Dedicated case-actor log unavailable; "
                    "falling back to vendor sub-actor route key '%s'",
                    case_actor_sub_actor_key,
                )
                entries = vendor_client.get_list(fallback_path)
            if not entries:
                raise ValueError(
                    f"No case log entries for actor={actor_name!r}, "
                    f"case_id={case_id!r}"
                )

            out_dir = output_root / demo_name / actor_name
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / f"{case_id_slug}-case-log.jsonl"

            with out_file.open("w", encoding="utf-8") as fh:
                for entry in entries:
                    fh.write(json.dumps(entry) + "\n")

            logger.info("Wrote %d log entries → %s", len(entries), out_file)


def run_two_actor_demo(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_actor_client: DataLayerClient | None = None,
    finder_id: str | None = None,
    vendor_id: str | None = None,
) -> None:
    """Orchestrate the complete two-actor (Finder + Vendor) CVD workflow."""
    logger.info("=" * 80)
    logger.info("TWO-ACTOR DEMO: Reporter + Coordinator CVD Workflow (VFDPxa)")
    logger.info("=" * 80)
    logger.info("Finder container: %s", finder_client.base_url)
    logger.info("Vendor container: %s", vendor_client.base_url)
    if case_actor_client is not None:
        logger.info("CaseActor container: %s", case_actor_client.base_url)

    finder, vendor, vendor_in_vendor, report, offer, case = (
        _phase_report_submission(
            finder_client,
            vendor_client,
            case_actor_client,
            finder_id,
            vendor_id,
        )
    )
    _, _, _, finder_in_finder = _phase_notes_exchange(
        finder_client,
        vendor_client,
        finder,
        vendor,
        vendor_in_vendor,
        case,
        report,
    )
    _phase_sync_verification(
        finder_client,
        vendor_client,
        vendor,
        finder,
        case,
        case_actor_client,
    )
    _phase_fix_lifecycle(
        finder_client,
        vendor_client,
        vendor,
        vendor_in_vendor,
        case,
    )
    _phase_publication(
        finder_client,
        vendor_client,
        vendor,
        vendor_in_vendor,
        finder,
        finder_in_finder,
        case,
    )
    _phase_case_closure(
        finder_client,
        vendor_client,
        vendor,
        vendor_in_vendor,
        finder,
        finder_in_finder,
        case,
    )
    _phase_dump_case_logs(
        finder_client=finder_client,
        vendor_client=vendor_client,
        finder=finder,
        vendor=vendor,
        case=case,
        case_actor_client=case_actor_client,
    )

    logger.info("=" * 80)
    logger.info("TWO-ACTOR DEMO COMPLETE ✓  (VFDPxa full lifecycle)")
    logger.info("=" * 80)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(
    skip_health_check: bool = False,
    finder_url: str | None = None,
    vendor_url: str | None = None,
    case_actor_url: str | None = None,
    finder_id: str | None = None,
    vendor_id: str | None = None,
) -> None:
    """Entry point for the two-actor multi-container CVD workflow demo.

    Args:
        skip_health_check: Skip the server availability check (useful for
            testing).
        finder_url: Override base URL for the Finder container.
        vendor_url: Override base URL for the Vendor container.
        case_actor_url: Optional base URL for the dedicated CaseActor container.
        finder_id: Optional deterministic URI for the Finder actor.
        vendor_id: Optional deterministic URI for the Vendor actor.
    """
    reset_demo_failures()

    f_url = finder_url or FINDER_BASE_URL
    v_url = vendor_url or VENDOR_BASE_URL
    c_url = case_actor_url or CASE_ACTOR_BASE_URL

    finder_client = DataLayerClient(base_url=f_url)
    vendor_client = DataLayerClient(base_url=v_url)
    case_actor_client = DataLayerClient(base_url=c_url) if c_url else None

    if not skip_health_check:
        targets: list[tuple[str, DataLayerClient]] = [
            ("Finder", finder_client),
            ("Vendor", vendor_client),
        ]
        if case_actor_client is not None:
            targets.append(("CaseActor", case_actor_client))
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
        run_two_actor_demo(
            finder_client=finder_client,
            vendor_client=vendor_client,
            case_actor_client=case_actor_client,
            finder_id=finder_id,
            vendor_id=vendor_id,
        )
    finally:
        assert_demo_success()


def _setup_logging() -> None:
    """Configure console logging for standalone script execution."""
    logging.getLogger("httpx").setLevel(logging.WARNING)
    _logger = logging.getLogger()
    hdlr = logging.StreamHandler(sys.stdout)
    hdlr.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    )
    _logger.addHandler(hdlr)
    _logger.setLevel(logging.DEBUG)


if __name__ == "__main__":
    _setup_logging()
    main()
