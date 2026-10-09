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

"""Open a coordinator-owned case and bring a Vendor into it.

The two steps every Reporter + Coordinator + Vendor scenario starts with
(``fcv``, ``rcv-embargo``), extracted so neither copies the other
(DEMOMA-17-001):

1. :func:`open_coordinated_case` — the Reporter submits a report to the
   Coordinator, who validates it and engages the case, holding CASE_OWNER.  The
   Reporter is seated when the case is created (CM-22-002), so it is never
   invited.
2. :func:`vendor_joins_coordinated_case` — the Coordinator, as CASE_OWNER,
   invites the Vendor directly (DEMOMA-12-004, not the ADR-0026 suggest/approve
   chain); the Vendor accepts and runs its RM triage as a late joiner.

Both expect the containers to be reset and seeded already.

The remaining steps of that lifecycle are shared the same way:
:func:`vendor_reports_fix_ready`, :func:`everyone_reports_published`,
:func:`everyone_closes_case` and :func:`dump_coordinated_case_ledgers`.
"""

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from vultron.core.states.cs import CS_vf
from vultron.core.states.rm import RM
from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers.invite_chain import (
    CaseInviter,
    run_case_invite_chain,
)
from vultron.demo.helpers.ledger_dump import (
    LedgerDumpTarget,
    dump_case_ledgers,
    replica_route_key,
    resolve_case_actor_route_key,
)
from vultron.demo.helpers.milestones import (
    verify_case_active,
    verify_case_closed,
    verify_fix_ready,
    verify_publicly_disclosed,
)
from vultron.demo.helpers.polling import (
    PARTICIPANT_JOIN_TIMEOUT,
    wait_for_all_participants_rm_closed,
    wait_for_case_em_terminated,
    wait_for_case_on_container,
    wait_for_case_participants,
    wait_for_event_type_in_ledger,
    wait_for_participant_rm_state,
    wait_for_participant_vf_state,
)
from vultron.demo.helpers.seeding import get_actor_by_id
from vultron.demo.helpers.sync import (
    run_sync_verification_phase,
    wait_for_replica_ledger_coverage,
)
from vultron.demo.helpers.workflow import (
    reporter_submits_report,
    run_direct_path_rm_triage,
    run_invite_path_rm_triage,
)
from vultron.demo.utils import (
    DataLayerClient,
    demo_check,
    demo_gate,
    demo_step,
    ref_id,
)
from vultron.enums.roles import CVDRole
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


@dataclass(frozen=True)
class CoordinatedCase:
    """What :func:`open_coordinated_case` leaves behind for later phases."""

    report: as_VulnerabilityReport
    offer: as_Offer
    case: as_VulnerabilityCase
    #: The Coordinator as its own container knows it (the object a trigger
    #: session is bound to).
    coordinator_in_coordinator: as_Actor


def open_coordinated_case(
    *,
    reporter_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    reporter: as_Actor,
    coordinator: as_Actor,
) -> CoordinatedCase:
    """The Reporter submits a report; the Coordinator validates and engages it.

    Gates on the Reporter and Coordinator both being participants and on the
    Reporter holding a case replica (M1) before returning the case as the
    Coordinator stores it.
    """
    coordinator_in_coordinator = get_actor_by_id(
        coordinator_client, coordinator.id_
    )

    report, offer = reporter_submits_report(
        receiver_client=coordinator_client,
        reporter=reporter,
        receiver=coordinator_in_coordinator,
        reporter_client=reporter_client,
    )
    # Coordinator validates then engages the case (RM→ACCEPTED), holding
    # CASE_OWNER; each step is gated on the coordinator's own RM state.
    case = run_direct_path_rm_triage(
        receiver_client=coordinator_client,
        receiver=coordinator_in_coordinator,
        offer=offer,
    )

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
    return CoordinatedCase(
        report=report,
        offer=offer,
        case=case,
        coordinator_in_coordinator=coordinator_in_coordinator,
    )


def vendor_joins_coordinated_case(
    *,
    opened: CoordinatedCase,
    reporter: as_Actor,
    reporter_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor: as_Actor,
    vendor_client: DataLayerClient,
    vendor_name: str = "Vendor",
    already_seated: Sequence[as_Actor] = (),
) -> as_Actor:
    """The Coordinator invites the Vendor; the Vendor accepts and triages.

    Args:
        vendor_name: What the scenario calls the invitee in step labels
            (``Vendor2`` for the second vendor of ``rcvv-embargo``).
        already_seated: Vendors that joined before this one, so the
            participant gate expects them as well.

    Returns:
        The Vendor as its own container knows it.
    """
    case = opened.case
    vendor_in_vendor = get_actor_by_id(vendor_client, vendor.id_)

    # The Reporter must hold the case replica before the Vendor's reply to the
    # full-case Invite (RM Received to Valid), which the chain sends, broadcasts
    # Announce(CaseLedgerEntry) to all participants (CLP-08-005).  The case is
    # already open, so the replica does not depend on the Vendor joining.
    with demo_check("Reporter's DataLayer received case replica"):
        wait_for_case_on_container(
            client=reporter_client,
            case_id=case.id_,
            timeout_seconds=20.0,
        )

    run_case_invite_chain(
        case=case,
        case_manager_client=coordinator_client,
        invitee_name=vendor_name,
        invitee_client=vendor_client,
        invitee=vendor,
        invitee_in_own_container=vendor_in_vendor,
        inviter=CaseInviter(
            name="Coordinator",
            client=coordinator_client,
            actor=opened.coordinator_in_coordinator,
            role=CVDRole.VENDOR,
        ),
        invite_timeout=20.0,
        replica_timeout=20.0,
    )

    # All participants present is the causal precondition for the Vendor's RM
    # triage: a demo_gate, not demo_check, so a timeout skips the doomed triage
    # rather than cascading (DEMOCI-01-011, vultron/demo/AGENTS.md § "Never
    # Wrap a Causal Wait in demo_check").
    with demo_gate(
        f"Coordinator case has {vendor_name} before {vendor_name} RM triage"
    ):
        wait_for_case_participants(
            vendor_client=coordinator_client,
            case_id=case.id_,
            expected_actor_ids={
                reporter.id_,
                opened.coordinator_in_coordinator.id_,
                vendor.id_,
                *(seated.id_ for seated in already_seated),
            },
            timeout_seconds=PARTICIPANT_JOIN_TIMEOUT,
        )
        logger.info("✓ M2: %s joined case", vendor_name)

        # CM-11-002: the Vendor joined via invite-accept — run its RM triage.
        run_invite_path_rm_triage(
            invited_client=vendor_client,
            invited_actor=vendor_in_vendor,
            offer=opened.offer,
            report=opened.report,
            finder=reporter,
            auth_client=coordinator_client,
            case=case,
            invited_obj=vendor,
            timeout_seconds=20.0,
        )

    return vendor_in_vendor


def open_case_with_vendor(
    *,
    reporter_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    reporter: as_Actor,
    coordinator: as_Actor,
    vendor: as_Actor,
    on_case_opened: Callable[[as_VulnerabilityCase], None] | None = None,
) -> tuple[CoordinatedCase, as_Actor]:
    """Open the case, bring the Vendor in, and verify the replicas converge.

    The shared opening of ``rcv-embargo`` and ``rcvv-embargo``: the Reporter's
    report, the Coordinator's engagement, the Vendor's invitation, then the
    sync verification of the Reporter's and the Vendor's replicas.

    Args:
        on_case_opened: Called with the case as soon as it exists, before the
            Vendor joins, so a scenario can register its ledger dump while every
            later step can still fail without costing the ledgers (ISSUE-2239).

    Returns:
        The opened case and the Vendor as its own container knows it.
    """
    opened = open_coordinated_case(
        reporter_client=reporter_client,
        coordinator_client=coordinator_client,
        reporter=reporter,
        coordinator=coordinator,
    )
    if on_case_opened is not None:
        on_case_opened(opened.case)

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
        case_id=opened.case.id_,
        expected_participant_ids={reporter.id_, coordinator.id_, vendor.id_},
        # The Vendor joins by invitation after the case exists (#2202).
        late_joiners=(vendor_client,),
        state_checks=[
            (reporter_client, "Reporter"),
            (vendor_client, "Vendor"),
        ],
    )
    return opened, vendor_in_vendor


def vendor_reports_fix_ready(
    *,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    vendor_in_vendor: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """The Vendor reports fix ready (VFd) and the Coordinator sees it.

    The Vendor holds ``CVDRole.VENDOR`` and not ``DEPLOYER``, so it stops at
    VFd (CSB-15-002).
    """
    with demo_gate(
        "vendor RM ∈ {ACCEPTED,DEFERRED,CLOSED} before notify-fix-ready (CSB-18-001)"
    ):
        wait_for_participant_rm_state(
            client=vendor_client,
            case_id=case.id_,
            actor_id=vendor_in_vendor.id_,
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
                actor_id=vendor_in_vendor.id_,
                expected_states={CS_vf.VF},
            )

        with demo_check(
            "M4: Coordinator replica shows Vendor CS includes F (fix ready)"
        ):
            wait_for_participant_vf_state(
                client=coordinator_client,
                case_id=case.id_,
                actor_id=vendor_in_vendor.id_,
                expected_states={CS_vf.VF},
            )
            verify_fix_ready(
                receiver_client=coordinator_client,
                reporter_client=vendor_client,
                case_id=case.id_,
                receiver_actor_id=vendor_in_vendor.id_,
            )

        with demo_check(
            "M5: Coordinator replica shows Vendor CS includes F (fix ready) — vendor stops at VFd"
        ):
            wait_for_participant_vf_state(
                client=coordinator_client,
                case_id=case.id_,
                actor_id=vendor_in_vendor.id_,
                expected_states={CS_vf.VF},
            )
            verify_fix_ready(
                receiver_client=coordinator_client,
                reporter_client=vendor_client,
                case_id=case.id_,
                receiver_actor_id=vendor_in_vendor.id_,
            )


def everyone_reports_published(
    *,
    reporter_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    reporter_in_reporter: as_Actor,
    coordinator_in_coordinator: as_Actor,
    vendor_in_vendor: as_Actor,
    case: as_VulnerabilityCase,
) -> None:
    """Each participant reports public disclosure, the Coordinator first.

    Per DEMOMA-07-003(4) the Coordinator (as CASE_OWNER) triggers CS.P.  The
    embargo is ended by then in ``rcv-embargo`` and still active in ``fcv``;
    either way it reads ``EM.EXITED`` once the Coordinator has reported.
    In ``rcv-embargo`` the two ``EM.EXITED`` checks below only confirm what the
    termination phase already established (the canonical case is asserted by
    the scenario); in ``fcv`` they check the embargo ending at publication.
    """
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
        f"Actor {ref_id(vendor_in_vendor)} reports vulnerability publicly"
        " disclosed"
    ):
        ActorSession(client=vendor_client, actor=vendor_in_vendor).with_case(
            case
        ).quiet().notify_published()
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
            client=vendor_client,
            case_id=case.id_,
        )
        wait_for_participant_vf_state(
            client=coordinator_client,
            case_id=case.id_,
            actor_id=vendor_in_vendor.id_,
            expected_states={CS_vf.VF},
        )
        wait_for_participant_vf_state(
            client=reporter_client,
            case_id=case.id_,
            actor_id=vendor_in_vendor.id_,
            expected_states={CS_vf.VF},
        )
        verify_publicly_disclosed(
            receiver_client=coordinator_client,
            reporter_client=reporter_client,
            case_id=case.id_,
            receiver_actor_id=vendor_in_vendor.id_,
        )


def everyone_closes_case(
    *,
    reporter_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    reporter_in_reporter: as_Actor,
    coordinator_in_coordinator: as_Actor,
    vendor_in_vendor: as_Actor,
    case: as_VulnerabilityCase,
    later_vendors: Sequence[tuple[str, DataLayerClient, as_Actor]] = (),
) -> None:
    """Every participant closes the case; check the terminal state everywhere.

    *later_vendors* are ``(label, client, actor)`` for vendors beyond the first
    (the second vendor of ``rcvv-embargo``); each closes and is checked for
    ledger coverage like the rest.
    """
    with demo_step(f"Actor {ref_id(coordinator_in_coordinator)} closes case"):
        ActorSession(
            client=coordinator_client, actor=coordinator_in_coordinator
        ).with_case(case).quiet().close_case()
    with demo_step(f"Actor {ref_id(vendor_in_vendor)} closes case"):
        ActorSession(client=vendor_client, actor=vendor_in_vendor).with_case(
            case
        ).quiet().close_case()
    with demo_step(f"Actor {ref_id(reporter_in_reporter)} closes case"):
        ActorSession(
            client=reporter_client, actor=reporter_in_reporter
        ).with_case(case).quiet().close_case()
    for label, client, actor in later_vendors:
        with demo_step(f"Actor {ref_id(actor)} ({label}) closes case"):
            ActorSession(client=client, actor=actor).with_case(
                case
            ).quiet().close_case()

    with demo_check("M7: all participants RM.CLOSED on all replicas"):
        wait_for_all_participants_rm_closed(
            client=coordinator_client,
            case_id=case.id_,
        )
        wait_for_all_participants_rm_closed(
            client=reporter_client,
            case_id=case.id_,
        )
        verify_case_closed(
            receiver_client=coordinator_client,
            reporter_client=reporter_client,
            case_id=case.id_,
        )

    with demo_check(
        "close_case entry present on authoritative actor (coordinator)"
    ):
        wait_for_event_type_in_ledger(
            client=coordinator_client,
            case_id=case.id_,
            event_type="close_case",
        )
    # Temporal (EDF-06-006): after close_case the authority's outbox fans out
    # Announce(CaseLedgerEntry) to each replica via BackgroundTasks; nothing
    # but the ledger dump depends on it. Bounded per replica by
    # LEDGER_COVERAGE_TIMEOUT / LATE_JOINER_COVERAGE_TIMEOUT (EDF-06-008).
    wait_for_replica_ledger_coverage(
        auth_client=coordinator_client,
        replicas=[
            (reporter_client, "Reporter"),
            (vendor_client, "Vendor"),
            *((client, label) for label, client, _ in later_vendors),
        ],
        case_id=case.id_,
        late_joiners=(
            vendor_client,
            *(client for _, client, _ in later_vendors),
        ),
        phase_label="close phase",
        causal=False,
    )


def dump_coordinated_case_ledgers(
    *,
    demo_name: str,
    reporter_name: str,
    reporter_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case: as_VulnerabilityCase,
    later_vendors: Sequence[tuple[str, DataLayerClient]] = (),
) -> None:
    """Dump each participant's case ledger to JSONL under ``devlogs/<demo_name>/``.

    Thin scenario-agnostic wrapper over
    :func:`~vultron.demo.helpers.ledger_dump.dump_case_ledgers`, which owns the
    per-actor export, the 404 handling, and the dump manifest.  This function
    only names the participants and where each one's ledger lives.

    Args:
        demo_name: The scenario's name; the devlogs subdirectory.
        reporter_name: What the scenario calls the Reporter's replica
            (``finder`` for ``fcv``, ``reporter`` for ``rcv-embargo``) —
            the invariant harness loads devlogs by this name.
        later_vendors: ``(name, client)`` of each vendor beyond the first
            (``vendor2`` for ``rcvv-embargo``), dumped under *name*.
    """
    # Route keys come from each client's own actor id, not from its display
    # name: the key selects the store (ADR-0073), so a literal only happens to
    # be right while a scenario seeds deterministic named ids. See
    # :func:`replica_route_key`.
    targets = [
        LedgerDumpTarget(
            reporter_name,
            reporter_client,
            replica_route_key(reporter_client, reporter_name),
        ),
        LedgerDumpTarget(
            "coordinator",
            coordinator_client,
            replica_route_key(coordinator_client, "coordinator"),
        ),
        LedgerDumpTarget(
            "vendor", vendor_client, replica_route_key(vendor_client, "vendor")
        ),
        *(
            LedgerDumpTarget(name, client, replica_route_key(client, name))
            for name, client in later_vendors
        ),
    ]
    # The case-actor is a sub-actor inside the coordinator container.
    case_actor_route_key = resolve_case_actor_route_key(case)
    if case_actor_route_key is not None:
        targets.append(
            LedgerDumpTarget(
                "case-actor", coordinator_client, case_actor_route_key
            )
        )

    dump_case_ledgers(demo_name=demo_name, case=case, targets=targets)
