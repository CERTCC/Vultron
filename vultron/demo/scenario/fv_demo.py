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

"""FV (Finder + Vendor) multi-container CVD workflow demo.

Orchestrates the full VFDPxa lifecycle across separate Finder and Vendor
containers. The scenario module now delegates common workflow, notes, and
milestone logic to the generic helper modules under ``vultron.demo.helpers``
while preserving the public API used by the existing test suite.
"""

import logging
import os
import sys
from typing import Optional, Tuple

from vultron.core.states.cs import CS_vfd
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Offer
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

from vultron.demo.utils import (  # noqa: F401 — re-exported for test monkeypatching
    BASE_URL,
    DataLayerClient,
    assert_demo_success,
    check_server_availability,
    demo_check,
    demo_gate,
    demo_step,
    logfmt,
    post_to_trigger,
    ref_id,
    reset_datalayer,
    reset_demo_failures,
    seed_actor,
    verify_object_stored,
    setup_demo_logging,
)

# Re-export shared helpers so that existing imports via this module continue to
# work and the test suite (which patches symbols in this module's namespace)
# remains unchanged.
from vultron.demo.helpers.actions import (  # noqa: F401
    actor_closes_case,
    actor_notifies_fix_ready,
    actor_notifies_published,
    actor_notifies_state_change,
)
from vultron.demo.helpers.harness import scenario_harness
from vultron.demo.helpers.ledger_dump import (
    LedgerDumpTarget,
    dump_case_ledgers,
    resolve_case_actor_route_key,
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
    wait_for_case_on_container,
    wait_for_case_participants,
    wait_for_finder_case,
    wait_for_contiguous_ledger_coverage,
    wait_for_event_type_in_ledger,
    wait_for_finder_log_entry,
    wait_for_note_in_case,
    wait_for_participant_rm_state,
    wait_for_participant_vfd_state,
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
    """Reset all containers used by the FV demo to a clean baseline.

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
) -> Tuple[as_VulnerabilityReport, as_Offer]:
    """Scenario alias for :func:`~vultron.demo.helpers.workflow.reporter_submits_report`.

    Maintained for backward compatibility; prefer ``reporter_submits_report``
    in new scenarios.
    """
    return reporter_submits_report(
        receiver_client=vendor_client,
        reporter=finder,
        receiver=vendor,
        reporter_client=finder_client,
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


def finder_asks_question(
    vendor_client: DataLayerClient,
    finder_client: DataLayerClient,
    vendor: as_Actor,
    finder: as_Actor,
    case: as_VulnerabilityCase,
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
    case: as_VulnerabilityCase,
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
        receiver_client=vendor_client,
        reporter_client=finder_client,
        case_id=case_id,
        receiver_actor_id=vendor_actor_id,
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
        receiver_client=vendor_client,
        reporter_client=finder_client,
        case_id=case_id,
        receiver_actor_id=vendor_actor_id,
    )


def verify_m5_state(
    vendor_client: DataLayerClient,
    finder_client: DataLayerClient,
    case_id: str,
    vendor_actor_id: str,
) -> None:
    """Scenario alias for :func:`~vultron.demo.helpers.milestones.verify_fix_ready`.

    M5 in the FV scenario is fix-ready (VFd); vendor-only actors stop at VFd
    per CSB-15-002.
    """
    return verify_fix_ready(
        receiver_client=vendor_client,
        reporter_client=finder_client,
        case_id=case_id,
        receiver_actor_id=vendor_actor_id,
    )


def verify_m6_state(
    vendor_client: DataLayerClient,
    finder_client: DataLayerClient,
    case_id: str,
    vendor_actor_id: str,
) -> None:
    """Scenario alias for :func:`~vultron.demo.helpers.milestones.verify_publicly_disclosed`."""
    return verify_publicly_disclosed(
        receiver_client=vendor_client,
        reporter_client=finder_client,
        case_id=case_id,
        receiver_actor_id=vendor_actor_id,
    )


def verify_m7_state(
    vendor_client: DataLayerClient,
    finder_client: DataLayerClient,
    case_id: str,
) -> None:
    """Scenario alias for :func:`~vultron.demo.helpers.milestones.verify_case_closed`."""
    return verify_case_closed(
        receiver_client=vendor_client,
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
    as_VulnerabilityReport,
    as_Offer,
    as_VulnerabilityCase,
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

    finder = vendor = None
    with demo_step("Seeding both containers with actor records"):
        finder, vendor = seed_containers(
            finder_client=finder_client,
            vendor_client=vendor_client,
            reporter_actor_id=finder_id,
            vendor_actor_id=vendor_id,
        )

    vendor_in_vendor = get_actor_by_id(vendor_client, vendor.id_)
    report, offer = reporter_submits_report(
        receiver_client=vendor_client,
        reporter=finder,
        receiver=vendor_in_vendor,
        reporter_client=finder_client,
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
            expected_actor_ids={FINDER_ACTOR_ID, VENDOR_ACTOR_ID},
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
                receiver_client=vendor_client,
                reporter_client=finder_client,
                case_id=case.id_,
                receiver_actor_id=vendor.id_,
                reporter_actor_id=finder.id_,
            )

    case = as_VulnerabilityCase.model_validate(
        vendor_client.get(f"/datalayer/{case.id_}")
    )
    return finder, vendor, vendor_in_vendor, report, offer, case


def _phase_notes_exchange(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    vendor_in_vendor: as_Actor,
    case: as_VulnerabilityCase,
    report: as_VulnerabilityReport,
) -> tuple[as_Note, as_Note, as_VulnerabilityCase, as_Actor]:
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

    final_case = None
    with demo_check(
        "M3: Vendor container holds the authoritative final case state"
    ):
        final_case = verify_receiver_case_state(
            receiver_client=vendor_client,
            case_id=case.id_,
            report_id=report.id_,
            receiver_actor_id=vendor.id_,
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
    case: as_VulnerabilityCase,
    case_actor_client: DataLayerClient | None,
) -> None:
    """Verify LedgerFanout replication and confirm the dedicated case actor is unused."""
    logger.info("─" * 80)
    logger.info("Phase 2: Replica synchronization verification")
    logger.info("─" * 80)

    # Synthetic checkpoint entries (demo_verification) are explicitly
    # excluded from the canonical case ledger per ADR-0019 (CLP-07-004):
    # only verbatim asserted protocol-significant AS2 activities belong on
    # the chain. Diagnostic markers belong in Python `logging`. Replication
    # is verified by comparing replica state directly rather than polling
    # for a new entry.
    #
    # `trigger_log_commit` and `wait_for_finder_log_entry` remain available
    # in `vultron.demo.helpers.sync` for tests that need to drive a *real*
    # protocol event and wait for its replica; they are intentionally not
    # called here — EXCEPT for the replica-state check below, where we must
    # wait for finder to receive all canonical entries before comparing state.
    # The vendor's report-acceptance creates canonical ledger entries whose
    # Announce(CaseLedgerEntry) fan-out is an async BackgroundTask; without
    # this wait intermediate entries may not have arrived yet (issue #1434).
    # Checkpoint: ensure the Finder has the VulnerabilityCase (and its genesis
    # hash) before waiting for ledger coverage.  If the Finder does not hold the
    # case, ReconstructChainTailNode cannot anchor the chain (CLP-08-005), so
    # Announce(CaseLedgerEntry) deliveries would be rejected and replayed rather
    # than accepted, extending the time needed to reach full coverage.  Failing
    # here fast surfaces the real problem instead of a confusing coverage timeout
    # (SYNC-15-001, issue #1873).
    with demo_gate("Finder case seeded before ledger coverage wait (SYNC-15)"):
        wait_for_case_on_container(
            client=finder_client,
            case_id=case.id_,
        )

        vendor_entries = _get_log_entries_for_case(vendor_client, case.id_)
        if vendor_entries:
            vendor_tail = max(vendor_entries, key=lambda e: e["log_index"])
            vendor_tail_index: int = vendor_tail["log_index"]
            logger.info(
                "Waiting for finder to replicate all vendor entries (0…%d)",
                vendor_tail_index,
            )
            with demo_gate("Finder ledger coverage (sync-verification phase)"):
                wait_for_contiguous_ledger_coverage(
                    client=finder_client,
                    case_id=case.id_,
                    expected_tail_index=vendor_tail_index,
                )

                logger.info(
                    "Verifying LedgerFanout replication by comparing vendor ↔ finder replica"
                    " state (ADR-0019: synthetic entries omitted from canonical ledger)"
                )

                with demo_check(
                    "Finder replica state matches authoritative Vendor state"
                ):
                    verify_finder_replica_state(
                        finder_client=finder_client,
                        vendor_client=vendor_client,
                        case_id=case.id_,
                        vendor_actor_id=vendor.id_,
                        reporter_actor_id=finder.id_,
                    )

    with demo_check(
        "Dedicated external CaseActor container holds no case data "
        "(vendor's own case-actor sub-actor handled the CaseProposal)"
    ):
        verify_case_actor_unused(case_actor_client, case.id_)

    logger.info("✓ M2: Finder DataLayer synchronized (LedgerFanout verified)")


def _phase_fix_lifecycle(
    finder_client: DataLayerClient,
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

    with demo_gate("M4/M5: finder replica reflects fix-ready vfd_state"):
        wait_for_participant_vfd_state(
            client=finder_client,
            case_id=case.id_,
            actor_id=vendor.id_,
            expected_states={CS_vfd.VFd, CS_vfd.VFD},
        )
        with demo_check("M4: both replicas show CS includes F (fix ready)"):
            wait_for_participant_vfd_state(
                client=vendor_client,
                case_id=case.id_,
                actor_id=vendor.id_,
                expected_states={CS_vfd.VFd, CS_vfd.VFD},
            )
            verify_fix_ready(
                receiver_client=vendor_client,
                reporter_client=finder_client,
                case_id=case.id_,
                receiver_actor_id=vendor.id_,
            )
        with demo_check(
            "M5: both replicas show CS includes F (fix ready) — vendor stops at VFd"
        ):
            wait_for_participant_vfd_state(
                client=vendor_client,
                case_id=case.id_,
                actor_id=vendor.id_,
                expected_states={CS_vfd.VFd},
            )
            wait_for_participant_vfd_state(
                client=finder_client,
                case_id=case.id_,
                actor_id=vendor.id_,
                expected_states={CS_vfd.VFd},
            )
            verify_fix_ready(
                receiver_client=vendor_client,
                reporter_client=finder_client,
                case_id=case.id_,
                receiver_actor_id=vendor.id_,
            )


def _phase_publication(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    vendor: as_Actor,
    vendor_in_vendor: as_Actor,
    finder: as_Actor,
    finder_in_finder: as_Actor,
    case: as_VulnerabilityCase,
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
        "M6: both replicas CS.VFdPxa, EM.EXITED, vendor participant is "
        "public-aware"
    ):
        wait_for_case_em_terminated(
            client=finder_client,
            case_id=case.id_,
        )
        wait_for_participant_vfd_state(
            client=vendor_client,
            case_id=case.id_,
            actor_id=vendor.id_,
            expected_states={CS_vfd.VFd},
        )
        wait_for_participant_vfd_state(
            client=finder_client,
            case_id=case.id_,
            actor_id=vendor.id_,
            expected_states={CS_vfd.VFd},
        )
        verify_publicly_disclosed(
            receiver_client=vendor_client,
            reporter_client=finder_client,
            case_id=case.id_,
            receiver_actor_id=vendor.id_,
        )


def _phase_case_closure(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    vendor: as_Actor,
    vendor_in_vendor: as_Actor,
    finder: as_Actor,
    finder_in_finder: as_Actor,
    case: as_VulnerabilityCase,
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
            receiver_client=vendor_client,
            reporter_client=finder_client,
            case_id=case.id_,
        )

    # Wait for finder to receive all canonical ledger entries (including the
    # close_case tail) before _phase_dump_case_ledgers writes devlog files.
    # AutoClose fans out Announce(CaseLedgerEntry) as an async BackgroundTask;
    # intermediate entries may arrive after the tail (issue #1434).
    #
    # Bug B fix: wait for close_case entry on the authoritative actor before
    # reading the tail, so we don't snapshot a tail that omits close_case.
    with demo_gate("close_case entry present on authoritative actor (vendor)"):
        wait_for_event_type_in_ledger(
            client=vendor_client,
            case_id=case.id_,
            event_type="close_case",
        )
        vendor_entries = _get_log_entries_for_case(vendor_client, case.id_)
        if vendor_entries:
            vendor_tail = max(vendor_entries, key=lambda e: e["log_index"])
            vendor_tail_index: int = vendor_tail["log_index"]
            logger.info(
                "Waiting for finder to replicate all vendor entries after closure"
                " (0…%d)",
                vendor_tail_index,
            )
            with demo_gate("Finder ledger coverage (close phase)"):
                wait_for_contiguous_ledger_coverage(
                    client=finder_client,
                    case_id=case.id_,
                    expected_tail_index=vendor_tail_index,
                )


# ---------------------------------------------------------------------------
# Case log export
# ---------------------------------------------------------------------------


def _phase_dump_case_ledgers(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    finder: as_Actor,
    vendor: as_Actor,
    case: as_VulnerabilityCase,
    case_actor_client: DataLayerClient | None = None,
    demo_name: str = "fv",
) -> None:
    """Dump case ledger entries from each actor container to JSONL files.

    Thin scenario-specific wrapper over
    :func:`~vultron.demo.helpers.ledger_dump.dump_case_ledgers`, which owns the
    per-actor export, the 404 handling, and the dump manifest written under
    ``{DEVLOGS_DIR}/{demo_name}/``. This function only names FV's participants
    and where each one's ledger lives.

    The case-actor log is always included: from *case_actor_client* when a
    dedicated case-actor service is configured, otherwise from the vendor
    container using the in-container case-actor sub-actor route key.

    Args:
        finder_client: DataLayerClient for the Finder container.
        vendor_client: DataLayerClient for the Vendor container.
        finder: Finder actor object (used to derive the actor object ID).
        vendor: Vendor actor object (used to derive the actor object ID).
        case: The as_VulnerabilityCase whose log entries are to be exported.
        case_actor_client: Optional DataLayerClient for the CaseActor container.
        demo_name: Sub-directory name under the output root (default ``"fv"``).
    """
    targets = [
        LedgerDumpTarget("finder", finder_client, "finder"),
        LedgerDumpTarget("vendor", vendor_client, "vendor"),
    ]
    case_actor_route_key = resolve_case_actor_route_key(case)
    if case_actor_client is not None:
        # D5-2: the dedicated case-actor container may not hold the case — the
        # case-actor can be a sub-actor inside the vendor container instead —
        # so fall back to the vendor container's sub-actor route key.
        targets.append(
            LedgerDumpTarget(
                "case-actor",
                case_actor_client,
                "case-actor",
                fallback_client=(
                    vendor_client if case_actor_route_key is not None else None
                ),
                fallback_route_key=case_actor_route_key,
            )
        )
    elif case_actor_route_key is not None:
        targets.append(
            LedgerDumpTarget("case-actor", vendor_client, case_actor_route_key)
        )

    dump_case_ledgers(demo_name=demo_name, case=case, targets=targets)


def run_fv_demo(
    finder_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_actor_client: DataLayerClient | None = None,
    finder_id: str | None = None,
    vendor_id: str | None = None,
) -> None:
    """Orchestrate the complete FV (Finder + Vendor) CVD workflow."""
    logger.info("=" * 80)
    logger.info("FV DEMO: Finder + Vendor CVD Workflow (VFDPxa)")
    logger.info("=" * 80)
    logger.info("Finder container: %s", finder_client.base_url)
    logger.info("Vendor container: %s", vendor_client.base_url)
    if case_actor_client is not None:
        logger.info("CaseActor container: %s", case_actor_client.base_url)

    with scenario_harness("fv") as harness:
        finder, vendor, vendor_in_vendor, report, offer, case = (
            _phase_report_submission(
                finder_client,
                vendor_client,
                case_actor_client,
                finder_id,
                vendor_id,
            )
        )

        # Register the dump as soon as there is a case to dump, so every phase
        # below can fail without costing us the ledgers (ISSUE-2239).
        harness.dump_with(
            lambda: _phase_dump_case_ledgers(
                finder_client=finder_client,
                vendor_client=vendor_client,
                finder=finder,
                vendor=vendor,
                case=case,
                case_actor_client=case_actor_client,
                demo_name=harness.demo_name,
            )
        )

        _phase_sync_verification(
            finder_client,
            vendor_client,
            vendor,
            finder,
            case,
            case_actor_client,
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

    logger.info("=" * 80)
    logger.info("FV DEMO COMPLETE ✓  (VFDPxa full lifecycle)")
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
    """Entry point for the FV (Finder + Vendor) multi-container CVD workflow demo.

    Args:
        skip_health_check: Skip the server availability check (useful for
            testing).
        finder_url: Override base URL for the Finder container.
        vendor_url: Override base URL for the Vendor container.
        case_actor_url: Optional base URL for the dedicated CaseActor container.
        finder_id: Optional deterministic URI for the Finder actor.
        vendor_id: Optional deterministic URI for the Vendor actor.
    """
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

    # scenario_harness() inside run_fv_demo() owns the failure accumulator: it
    # resets it, always dumps the case ledgers, and asserts success — so a
    # failure here never costs us the artifacts (ISSUE-2239).
    run_fv_demo(
        finder_client=finder_client,
        vendor_client=vendor_client,
        case_actor_client=case_actor_client,
        finder_id=finder_id,
        vendor_id=vendor_id,
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
