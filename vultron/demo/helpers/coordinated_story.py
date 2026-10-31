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
"""Story fragments of the Reporter → Coordinator → Vendor family.

The opening every scenario of this family tells is written here **once**
(:data:`COORDINATOR_INVITES_VENDOR`): the Reporter tells the Coordinator, the
Coordinator engages the case, and the Coordinator invites the Vendor.  Each
scenario then assembles its own story from that prefix plus its continuation
(:mod:`vultron.demo.helpers.story`), so ``rcv`` and ``rcv-reject`` no longer
each place the opening by hand (DEMOMA-17-001, DEMOCI-11-018).

The prefix stops where the Vendor's decision falls: the Invite has been
delivered, so the CASE_MANAGER has seated the Vendor's inert participant with
the role the Invite offers and the harness can read it (CM-17-003,
DEMOCI-11-013), and the Vendor has not answered yet.  Each continuation opens
with ``choose("vendor-join", ...)`` and then its own answer fragment —
:func:`vendor_accepts_and_joins` or :func:`vendor_rejects_invite`.

Every fragment here is a thin naming of the lifecycle helpers in
:mod:`vultron.demo.helpers.coordinated_case` and its neighbours: the mechanics
stay there, and a fragment only says which cast member does what to which case
(DEMOMA-23-002).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from vultron.core.states.rm import RM
from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers.actor_roles import ActorRole
from vultron.demo.helpers.cast import CASE_ACTOR
from vultron.demo.helpers.closure import CaseLeaver, close_case_owner_last
from vultron.demo.helpers.coordinated_case import (
    CROSS_CONTAINER_TIMEOUT,
    await_reporter_case_replica,
    everyone_closes_case,
    everyone_reports_published,
    invitee_triages_after_joining,
    open_coordinated_case,
    vendor_reports_fix_ready,
)
from vultron.demo.helpers.harness import ScenarioHarness
from vultron.demo.helpers.invite_chain import (
    CaseInviter,
    answer_case_invite,
    invite_and_await_delivery,
)
from vultron.demo.helpers.milestones import verify_publicly_disclosed
from vultron.demo.helpers.notes import (
    NotePost,
    add_note_thread,
    reporter_asks_vendor_timeline,
)
from vultron.demo.helpers.polling import (
    wait_for_case_em_terminated,
    wait_for_case_participants,
    wait_for_participant_rm_state,
    wait_for_semantic_type_in_ledger,
)
from vultron.demo.helpers.runner import check_all_containers
from vultron.demo.helpers.seeding import (
    get_actor_by_id,
    reset_containers,
    seed_containers_rcv,
)
from vultron.demo.helpers.story import StoryState, choose, story
from vultron.demo.helpers.sync import run_sync_verification_phase
from vultron.demo.helpers.verification import _check_participant_rm_state_in
from vultron.demo.utils import (
    DataLayerClient,
    bound_case_actor_client,
    demo_check,
    demo_gate,
    demo_step,
    ref_id,
    reset_datalayer,
)
from vultron.enums.roles import CVDRole
from vultron.errors import DemoStoryError
from vultron.wire.as2.vocab.base.objects.actors import as_Actor

logger = logging.getLogger(__name__)

#: The names this family's scenarios seat their actors under, in their
#: ``ROLES`` lists and so in :attr:`StoryState.cast`.  Shared constants rather
#: than literals so a fragment and a ``choose(..., by=...)`` cannot disagree
#: about who decides.
REPORTER = "reporter"
COORDINATOR = "coordinator"
VENDOR = "vendor"

#: How the Vendor is named in this family's step and gate labels.
VENDOR_LABEL = "Vendor"

#: What the scenarios of this family call the dedicated CaseActor container in
#: their ``ROLES``: the cast slot's own name.
CASE_ACTOR_NAME = CASE_ACTOR.name


@dataclass(frozen=True, slots=True)
class CoordinatedClients:
    """The four containers every scenario of this family drives."""

    reporter: DataLayerClient
    coordinator: DataLayerClient
    vendor: DataLayerClient
    #: Bound to the CaseActor the dedicated container hosts, so a read through
    #: it addresses the canonical case and ledger (ADR-0073, DEMOMA-06-005).
    case_actor: DataLayerClient


def coordinated_clients(
    roles: Mapping[str, ActorRole],
    *,
    skip_health_check: bool,
    reporter_url: str | None = None,
    coordinator_url: str | None = None,
    vendor_url: str | None = None,
    case_actor_url: str | None = None,
) -> CoordinatedClients:
    """Build this family's four clients, health-checked unless asked not to.

    Every scenario of the family builds the same four, binds the case-actor one
    to its CaseActor, and health-checks all four, so it is done once here
    rather than once per ``main()`` (DEMOMA-17-001).  Each URL falls back to
    the cast slot's own address, which is why the scenario modules declare no
    ``*_BASE_URL`` constants of their own (DEMOCI-11-020).

    Args:
        roles: The scenario's :func:`~vultron.demo.helpers.actor_roles
            .role_map`, which names the cast slot each actor sits in.
        skip_health_check: Skip the server availability check.
        reporter_url: Override base URL for the Reporter container.
        coordinator_url: Override base URL for the Coordinator container.
        vendor_url: Override base URL for the Vendor container.
        case_actor_url: Override base URL for the CaseActor container.

    Returns:
        The four clients.

    Raises:
        SystemExit: When a container is unreachable and the check ran.
        KeyError: When *roles* seats none of this family's four actors — a
            scenario whose ``ROLES`` and story have drifted apart.
    """
    overrides = {
        REPORTER: reporter_url,
        COORDINATOR: coordinator_url,
        VENDOR: vendor_url,
        CASE_ACTOR_NAME: case_actor_url,
    }
    urls = {
        name: override or roles[name].url
        for name, override in overrides.items()
    }
    clients = CoordinatedClients(
        reporter=DataLayerClient(base_url=urls[REPORTER]),
        coordinator=DataLayerClient(base_url=urls[COORDINATOR]),
        vendor=DataLayerClient(base_url=urls[VENDOR]),
        case_actor=bound_case_actor_client(urls[CASE_ACTOR_NAME]),
    )
    if not skip_health_check:
        check_all_containers(
            [
                ("Reporter", clients.reporter),
                ("Coordinator", clients.coordinator),
                ("Vendor", clients.vendor),
                ("CaseActor", clients.case_actor),
            ]
        )
    return clients


def open_coordinated_cast(
    harness: ScenarioHarness,
    *,
    reporter_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    dump: Callable[[StoryState], None],
    reporter_id: str | None = None,
    coordinator_id: str | None = None,
    vendor_id: str | None = None,
) -> StoryState:
    """Reset and seed this family's three containers, and return its cast.

    The opening of every Reporter + Coordinator + Vendor scenario: the same
    reset and the same seeding, so neither scenario writes either
    (DEMOMA-17-001).  Each seeded actor is read back from its own container,
    which is the form a trigger session binds to.

    Args:
        harness: The run's :class:`~vultron.demo.helpers.harness
            .ScenarioHarness`.
        reporter_client: Client for the Reporter's container.
        coordinator_client: Client for the Coordinator's container.
        vendor_client: Client for the Vendor's container.
        case_actor_client: Client for the dedicated case-actor container.
        dump: The scenario's ledger dump, armed when the case opens.
        reporter_id: Deterministic URI for the Reporter actor, when given.
        coordinator_id: Deterministic URI for the Coordinator actor.
        vendor_id: Deterministic URI for the Vendor actor.

    Returns:
        The story state the family's fragments run against.

    Raises:
        DemoStoryError: When the containers could not be seeded, so there is
            no cast to tell the story with.
    """
    targets: list[tuple[str, DataLayerClient]] = [
        ("Reporter", reporter_client),
        ("Coordinator", coordinator_client),
        ("Vendor", vendor_client),
    ]
    reset_containers(
        targets,
        reset_fn=reset_datalayer,
        case_actor_client=case_actor_client,
    )

    seeded: tuple[as_Actor, as_Actor, as_Actor] | None = None
    with demo_step("Seeding Reporter, Coordinator, and Vendor containers"):
        seeded = seed_containers_rcv(
            reporter_client=reporter_client,
            coordinator_client=coordinator_client,
            vendor_client=vendor_client,
            reporter_actor_id=reporter_id,
            coordinator_actor_id=coordinator_id,
            vendor_actor_id=vendor_id,
            case_actor_client=case_actor_client,
        )
    if seeded is None:
        raise DemoStoryError(
            "the Reporter, Coordinator and Vendor containers could not be "
            "seeded, so the story has no cast to run on; the seeding failure "
            "is recorded above."
        )
    reporter, coordinator, vendor = seeded

    return StoryState(
        cast={
            REPORTER: ActorSession(
                client=reporter_client,
                actor=get_actor_by_id(reporter_client, reporter.id_),
            ),
            COORDINATOR: ActorSession(
                client=coordinator_client,
                actor=get_actor_by_id(coordinator_client, coordinator.id_),
            ),
            VENDOR: ActorSession(
                client=vendor_client,
                actor=get_actor_by_id(vendor_client, vendor.id_),
            ),
        },
        case_actor_client=case_actor_client,
        harness=harness,
        dump=dump,
    )


def reporter_tells_coordinator(state: StoryState) -> None:
    """The Reporter submits its report; the Coordinator engages the case.

    The Coordinator holds CASE_OWNER; the Reporter is seated when the case is
    created (CM-22-002), so it is never invited (DEMOMA-12-003).
    """
    opened = open_coordinated_case(
        reporter_client=state.client(REPORTER),
        coordinator_client=state.client(COORDINATOR),
        reporter=state.actor(REPORTER).actor,
        coordinator_in_coordinator=state.actor(COORDINATOR).actor,
    )
    state.open_case(case=opened.case, report=opened.report, offer=opened.offer)


def coordinator_invites_vendor(state: StoryState) -> None:
    """The Coordinator invites the Vendor, and the Invite is delivered.

    The Coordinator is CASE_OWNER, so it invites directly rather than through
    the ADR-0026 suggest/approve chain (DEMOMA-12-004).  The fragment stops at
    delivery: the Vendor's answer is the next branch point's choice.
    """
    state.invited(
        VENDOR,
        invite_and_await_delivery(
            case=state.case,
            invitee_name=VENDOR_LABEL,
            invitee_client=state.client(VENDOR),
            invitee=state.actor(VENDOR).actor,
            inviter=CaseInviter(
                name="Coordinator",
                client=state.client(COORDINATOR),
                actor=state.actor(COORDINATOR).actor,
                role=CVDRole.VENDOR,
            ),
            case_manager_client=state.case_actor_client,
            invite_timeout=CROSS_CONTAINER_TIMEOUT,
        ),
    )


#: The opening every Reporter → Coordinator → Vendor scenario shares: the
#: Reporter tells the Coordinator, and the Coordinator invites the Vendor.
#: Named rather than assembled from the fragments at each call site, because
#: assembling siblings from fragments alone lets one of them slip a step in
#: before the branch point (``notes/demo-scenario-tree.md`` § "Composition").
COORDINATOR_INVITES_VENDOR = story(
    choose("reporter-whom-to-tell", "coordinator", by=REPORTER),
    reporter_tells_coordinator,
    choose("coordinator-invite-whom", "vendor", by=COORDINATOR),
    coordinator_invites_vendor,
)


def vendor_accepts_and_joins(state: StoryState) -> None:
    """The Vendor accepts the Invite, takes its replica and triages the report.

    The composed form of :func:`~vultron.demo.helpers.coordinated_case
    .vendor_joins_coordinated_case`\'s second half: the same
    :func:`~vultron.demo.helpers.coordinated_case.await_reporter_case_replica`
    gate (CLP-08-005, Bug #2135), the chain\'s answer, and the same
    :func:`~vultron.demo.helpers.coordinated_case
    .invitee_triages_after_joining` tail (CM-11-002).  Only the Invite\'s
    delivery, which a story places before the Vendor\'s branch point, sits
    outside it.
    """
    vendor = state.actor(VENDOR).actor
    await_reporter_case_replica(
        reporter_client=state.client(REPORTER), case=state.case
    )

    answer_case_invite(
        invite_id=state.delivered_invite(VENDOR),
        case=state.case,
        invitee_name=VENDOR_LABEL,
        invitee_client=state.client(VENDOR),
        invitee=vendor,
        invitee_in_own_container=vendor,
        respond="accept",
        replica_timeout=CROSS_CONTAINER_TIMEOUT,
        authority_client=state.case_actor_client,
    )

    invitee_triages_after_joining(
        invitee_name=VENDOR_LABEL,
        invitee_client=state.client(VENDOR),
        invitee=vendor,
        invitee_in_own_container=vendor,
        roster_client=state.client(COORDINATOR),
        expected_actor_ids={
            state.actor_id(REPORTER),
            state.actor_id(COORDINATOR),
            state.actor_id(VENDOR),
        },
        reporter=state.actor(REPORTER).actor,
        report=state.report,
        offer=state.offer,
        case=state.case,
        case_actor_client=state.case_actor_client,
    )


def vendor_rejects_invite(state: StoryState) -> None:
    """The Vendor rejects the Invite and never becomes an active participant.

    The Vendor sends ``Reject(Invite(Actor, VulnerabilityCaseStub))`` and the
    CaseActor records a ``reject_invite_actor_to_case`` entry.  At invite-send
    time ``CreateInertInviteeParticipantNode`` already seated the Vendor as an
    inert participant (``joined=False``, RM ``RECEIVED``; ADR-0114,
    CM-11-006); after the Reject, CM-11-007 moves that record to RM
    ``CLOSED``.  The Vendor is in the index and was never active, and no case
    content is delivered to it (DEMOMA-27-002).
    """
    vendor = state.actor(VENDOR).actor
    answer_case_invite(
        invite_id=state.delivered_invite(VENDOR),
        case=state.case,
        invitee_name=VENDOR_LABEL,
        invitee_client=state.client(VENDOR),
        invitee=vendor,
        invitee_in_own_container=vendor,
        respond="reject",
    )

    # Gate on the Reject being committed before checking participant state.
    # The Reject is a case event, admitted and ledgered like an Accept
    # (CLP-02-012).  It is self-contained on the CaseActor (CLP-10-006) — no
    # participant-effect Announce is sent, so the entry is only visible in the
    # CaseActor's own store, on the dedicated case-actor container.  A
    # demo_gate here skips the participant checks rather than running them
    # against stale state.
    with demo_gate(
        "reject_invite_actor_to_case committed (causal gate before "
        "participant state check)"
    ):
        wait_for_semantic_type_in_ledger(
            client=state.case_actor_client,
            case_id=state.case.id_,
            semantic_type="reject_invite_actor_to_case",
        )
        # Read from the CASE_MANAGER's own store: a replica stores the record
        # the CASE_MANAGER's create_case_participant entry carries (ADR-0114),
        # but this scenario checks the record
        # CreateInertInviteeParticipantNode wrote.
        with demo_check(
            f"{VENDOR_LABEL} in actor_participant_index after invite "
            "(inert record, CM-11-006)"
        ):
            wait_for_case_participants(
                vendor_client=state.case_actor_client,
                case_id=state.case.id_,
                expected_actor_ids={
                    state.actor_id(REPORTER),
                    state.actor_id(COORDINATOR),
                    state.actor_id(VENDOR),
                },
            )
        # The reject tree commits the ledger entry (the gate above) BEFORE its
        # ApplyInviteRejectToParticipantNode effect writes RM.CLOSED, so the
        # committed-entry gate proves the handler started, not that the RM
        # close landed (EDF-06-002, EDF-06-003).  Wait on the committed effect
        # itself before the one-shot check.
        wait_for_participant_rm_state(
            client=state.case_actor_client,
            case_id=str(state.case.id_),
            actor_id=state.actor_id(VENDOR),
            expected_states={RM.CLOSED},
        )
        with demo_check(
            f"{VENDOR_LABEL} participant at RM.CLOSED after rejection "
            "(never active, DEMOMA-27-002)"
        ):
            _check_participant_rm_state_in(
                client=state.case_actor_client,
                case_id=str(state.case.id_),
                actor_id=state.actor_id(VENDOR),
                expected_states={RM.CLOSED},
                label=f"{VENDOR_LABEL} (rejected invitee)",
            )
    logger.info(
        "✓ M2: %s rejected invite — inert record at RM.CLOSED, never active"
        " (DEMOMA-27-002)",
        VENDOR_LABEL,
    )


def replicas_converge_with_vendor(state: StoryState) -> None:
    """The Reporter's and the Vendor's replicas catch up with the case."""
    run_sync_verification_phase(
        auth_client=state.client(COORDINATOR),
        auth_label="Coordinator",
        auth_actor_id=state.actor_id(COORDINATOR),
        reporter_client=state.client(REPORTER),
        reporter_actor_id=state.actor_id(REPORTER),
        replicas=[
            (state.client(REPORTER), "Reporter"),
            (state.client(VENDOR), VENDOR_LABEL),
        ],
        case_id=state.case.id_,
        expected_participant_ids={
            state.actor_id(REPORTER),
            state.actor_id(COORDINATOR),
            state.actor_id(VENDOR),
        },
        # The Vendor joins by invitation after the case exists (#2202).
        late_joiners=(state.client(VENDOR),),
        state_checks=[
            (state.client(REPORTER), "Reporter"),
            (state.client(VENDOR), VENDOR_LABEL),
        ],
    )
    logger.info("✓ M3: All replicas synchronized (LedgerFanout verified)")


def reporter_replica_converges(state: StoryState) -> None:
    """The Reporter's replica catches up with the case, the Vendor having left.

    The Reporter must hold the case and every Coordinator-committed entry
    before the notes exchange: without this gate the ``add-note-to-case``
    trigger on the Reporter's container can fail, because its DataLayer has
    not yet received the case replica or the ledger tail (SYNC-15-001).  The
    Vendor declined, so this fragment declares no participant expectation and
    no replica state check.
    """
    run_sync_verification_phase(
        auth_client=state.client(COORDINATOR),
        auth_label="Coordinator",
        auth_actor_id=state.actor_id(COORDINATOR),
        reporter_client=state.client(REPORTER),
        reporter_actor_id=state.actor_id(REPORTER),
        replicas=[(state.client(REPORTER), "Reporter")],
        case_id=state.case.id_,
    )


def reporter_asks_about_the_timeline(state: StoryState) -> None:
    """The Reporter asks the Vendor's timeline; both others answer."""
    add_note_thread(
        state.client(COORDINATOR),
        state.case,
        reporter_asks_vendor_timeline(
            state.actor(REPORTER),
            state.actor(VENDOR),
            state.actor(COORDINATOR),
        ),
    )
    logger.info(
        "✓ Notes exchange complete (three notes committed to case ledger)"
    )


def reporter_asks_about_the_rejection(state: StoryState) -> None:
    """The Reporter asks what happens now the Vendor has declined."""
    add_note_thread(
        state.client(COORDINATOR),
        state.case,
        [
            NotePost(
                state.actor(REPORTER),
                "Question from Reporter",
                "Vendor rejected the invitation. "
                "What is the plan for coordinated disclosure?",
            ),
            NotePost(
                state.actor(COORDINATOR),
                "Coordinator Response",
                "Vendor declined to participate. "
                "We will proceed with Reporter-only disclosure. "
                "Embargo will be terminated and we will publish.",
            ),
        ],
    )
    logger.info(
        "✓ Notes exchange complete (two notes committed to case ledger)"
    )


def vendor_reports_the_fix_ready(state: StoryState) -> None:
    """The Vendor reports fix ready and stops at VFd (CSB-15-002)."""
    vendor_reports_fix_ready(
        coordinator_client=state.client(COORDINATOR),
        vendor_client=state.client(VENDOR),
        vendor_in_vendor=state.actor(VENDOR).actor,
        case=state.case,
    )


def everyone_publishes(state: StoryState) -> None:
    """Each participant reports public disclosure, the Coordinator first.

    Per DEMOMA-07-003(4) the Coordinator, as CASE_OWNER, triggers CS.P.
    """
    everyone_reports_published(
        reporter_client=state.client(REPORTER),
        coordinator_client=state.client(COORDINATOR),
        vendor_client=state.client(VENDOR),
        reporter_in_reporter=state.actor(REPORTER).actor,
        coordinator_in_coordinator=state.actor(COORDINATOR).actor,
        vendor_in_vendor=state.actor(VENDOR).actor,
        case=state.case,
    )


def coordinator_and_reporter_publish(state: StoryState) -> None:
    """The Coordinator then the Reporter report published; the embargo ends.

    The two-party form of :func:`everyone_publishes`, for a story whose Vendor
    declined: the Coordinator, as CASE_OWNER, triggers CS.P (DEMOMA-07-003(4))
    and the embargo terminates (EM.EXITED).
    """
    coordinator = state.actor(COORDINATOR)
    reporter = state.actor(REPORTER)
    with demo_step(
        f"Actor {ref_id(coordinator.actor)} reports vulnerability"
        " publicly disclosed"
    ):
        coordinator.with_case(state.case).quiet().notify_published()

    with demo_check(
        "Embargo terminated (EM.EXITED) after Coordinator reports published"
    ):
        wait_for_case_em_terminated(
            client=coordinator.client, case_id=state.case.id_
        )

    with demo_step(
        f"Actor {ref_id(reporter.actor)} reports vulnerability publicly"
        " disclosed"
    ):
        reporter.with_case(state.case).quiet().notify_published()

    with demo_check("M3: EM.EXITED, Coordinator and Reporter public-aware"):
        wait_for_case_em_terminated(
            client=reporter.client, case_id=state.case.id_
        )
        verify_publicly_disclosed(
            receiver_client=coordinator.client,
            reporter_client=reporter.client,
            case_id=state.case.id_,
            receiver_actor_id=state.actor_id(COORDINATOR),
        )


def everyone_closes(state: StoryState) -> None:
    """Every participant closes the case; the Case Owner leaves last."""
    everyone_closes_case(
        reporter_client=state.client(REPORTER),
        coordinator_client=state.client(COORDINATOR),
        case_actor_client=state.case_actor_client,
        vendor_client=state.client(VENDOR),
        reporter_in_reporter=state.actor(REPORTER).actor,
        coordinator_in_coordinator=state.actor(COORDINATOR).actor,
        vendor_in_vendor=state.actor(VENDOR).actor,
        case=state.case,
    )


def reporter_then_coordinator_close(state: StoryState) -> None:
    """The Reporter leaves, then the Coordinator, the Case Owner, leaves last.

    The two-party form of :func:`everyone_closes`: the owner leaves once the
    Reporter's departure is recorded in the CASE_MANAGER's store (CM-23-015).
    """
    close_case_owner_last(
        case=state.case,
        milestone="M4",
        authority_client=state.case_actor_client,
        others=[
            CaseLeaver(
                client=state.client(REPORTER),
                actor=state.actor(REPORTER).actor,
            )
        ],
        owner=CaseLeaver(
            client=state.client(COORDINATOR),
            actor=state.actor(COORDINATOR).actor,
        ),
    )


__all__ = [
    "CASE_ACTOR_NAME",
    "COORDINATOR",
    "COORDINATOR_INVITES_VENDOR",
    "REPORTER",
    "VENDOR",
    "VENDOR_LABEL",
    "CoordinatedClients",
    "coordinated_clients",
    "coordinator_and_reporter_publish",
    "coordinator_invites_vendor",
    "everyone_closes",
    "everyone_publishes",
    "open_coordinated_cast",
    "reporter_asks_about_the_rejection",
    "reporter_asks_about_the_timeline",
    "reporter_replica_converges",
    "reporter_tells_coordinator",
    "reporter_then_coordinator_close",
    "replicas_converge_with_vendor",
    "vendor_accepts_and_joins",
    "vendor_rejects_invite",
    "vendor_reports_the_fix_ready",
]
