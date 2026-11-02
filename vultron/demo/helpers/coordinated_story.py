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

The opening every scenario of this family tells is written here **once**: the
Reporter tells the Coordinator, the Coordinator engages the case, the
Coordinator invites the Vendor, the Vendor accepts and the replicas converge.
Each scenario then assembles its own story from the longest prefix it shares
with its siblings plus its continuation
(:mod:`vultron.demo.helpers.story`), so no two of them place the opening by
hand (DEMOMA-17-001, DEMOCI-11-018).

The prefixes nest, one per shared stretch, so a sibling cannot slip a step in
before a branch point (``notes/demo-scenario-tree.md`` § "Composition"):

* :data:`REPORTER_TELLS_THE_COORDINATOR` stops where the Coordinator's
  decision falls: the Reporter has told it and it has engaged the case, and it
  has invited nobody yet.  The two-coordinator pair parts here
  (``coordinator-invite-whom:coordinator``,
  :mod:`vultron.demo.helpers.two_coordinator_story`).
* :data:`COORDINATOR_INVITES_VENDOR` stops where the Vendor's decision falls.
  The Invite has been delivered, so the CASE_MANAGER has seated the Vendor's
  inert participant with the role the Invite offers and the harness can read
  it (CM-17-003, DEMOCI-11-013), and the Vendor has not answered yet.
  ``rcv-reject`` parts here.
* :data:`VENDOR_JOINS_THE_CASE` continues through the Vendor's acceptance and
  the replica convergence, and stops where the Reporter's decision falls.
  The embargo pair parts here (``reporter-after-join:propose-embargo``,
  :mod:`vultron.demo.helpers.coordinated_embargo_story`).
* :data:`REPORTER_ASKS_THE_VENDOR` continues through the note thread the
  ``ask-vendor`` choice posts, and stops where the Coordinator's decision
  falls.  ``rcv`` and ``rcvcv`` part here.

The family's three fixed-role members are seated under :data:`REPORTER`,
:data:`COORDINATOR` and :data:`VENDOR` whatever its own ``ROLES`` calls them,
so one copy of each fragment serves every scenario: ``rcvcv`` names its first
Coordinator ``c1`` on the command line and in its devlogs, and the story still
reaches it as the Coordinator it is.  A scenario's **character actors** are
seeded and seated by the fragment that brings each into the case
(:meth:`~vultron.demo.helpers.story.StoryState.seat`), never by the shared
opening: what the opening writes before the case exists is part of the bytes
its siblings must match (DEMOCI-11-018).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from vultron.core.states.cs import CS_vf
from vultron.core.states.rm import RM
from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers.actor_roles import ActorRole
from vultron.demo.helpers.cast import CASE_ACTOR
from vultron.demo.helpers.closure import CaseLeaver, close_case_owner_last
from vultron.demo.helpers.harness import ScenarioHarness
from vultron.demo.helpers.invite_chain import (
    CaseInviter,
    answer_case_invite,
    invite_and_await_delivery,
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
from vultron.demo.helpers.notes import (
    NotePost,
    add_note_thread,
    gated_note_thread,
    reporter_asks_vendor_timeline,
)
from vultron.demo.helpers.polling import (
    PARTICIPANT_JOIN_TIMEOUT,
    wait_for_case_em_terminated,
    wait_for_case_on_container,
    wait_for_case_participants,
    wait_for_participant_rm_state,
    wait_for_participant_vf_state,
    wait_for_semantic_type_in_ledger,
)
from vultron.demo.helpers.runner import check_all_containers
from vultron.demo.helpers.seeding import (
    get_actor_by_id,
    reset_containers,
    seed_containers_rcv,
)
from vultron.demo.helpers.story import (
    Fragment,
    StoryProp,
    StoryState,
    UnseatedContainer,
    choose,
    story,
)
from vultron.demo.helpers.sync import run_sync_verification_phase
from vultron.demo.helpers.verification import _check_participant_rm_state_in
from vultron.demo.helpers.workflow import (
    reporter_submits_report,
    run_direct_path_rm_triage,
    run_invite_path_rm_triage,
)
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
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

logger = logging.getLogger(__name__)

#: The names this family's stories seat their three fixed-role members under,
#: and so the keys of :attr:`StoryState.cast` every fragment here reads.
#: Shared constants rather than literals so a fragment and a
#: ``choose(..., by=...)`` cannot disagree about who decides.
REPORTER = "reporter"
COORDINATOR = "coordinator"
VENDOR = "vendor"

#: How the three are named in this family's step and gate labels.
REPORTER_LABEL = "Reporter"
COORDINATOR_LABEL = "Coordinator"
VENDOR_LABEL = "Vendor"

#: What the scenarios of this family call the dedicated CaseActor container in
#: their ``ROLES``: the cast slot's own name.
CASE_ACTOR_NAME = CASE_ACTOR.name

#: Seconds a cross-container wait of this lifecycle may take: the Invite's
#: delivery, an invitee's case replica, and each wait of its RM triage.  One
#: constant because every scenario of the family used the same literal.
CROSS_CONTAINER_TIMEOUT = 20.0

#: Seconds the Coordinator's own RM triage may take.  One authored opening
#: means one budget, so it is the widest member's: ``rcvcv`` raised it to 60 s
#: for a run that brings five actor containers up under CI load (ISSUE-2811),
#: and the narrower scenarios inherit it.  A budget only bounds how long a
#: wait may take, so raising it refuses nothing a shorter one admitted and
#: moves no byte of a recording.
OWNER_TRIAGE_TIMEOUT = 60.0

#: The Coordinator's summary closing the ``ask-vendor`` note thread.  Kept so
#: a continuation can answer it: ``rcvcv``'s later joiners reply to it rather
#: than opening a thread of their own (DEMOCI-11-017).
TIMELINE_ANSWER: StoryProp[as_Note] = StoryProp(
    "answered timeline note thread", as_Note
)

#: The case whose roster the Coordinator has confirmed, as its id.  Read by
#: :func:`coordinator_invites_vendor`, which is the causal dependent: the
#: Reporter and the Coordinator must both be seated before anyone else is
#: invited, so a roster that never arrived skips the invite and the admit
#: chain behind it rather than adding secondary failures to the first
#: (DEMOCI-01-011, ``vultron/demo/AGENTS.md`` § "Never Wrap a Causal Wait in
#: demo_check").  A flat story cannot nest the invite inside the roster's
#: gate, so the gate keeps this and the invite reads it.
ENGAGED_CASE: StoryProp[str] = StoryProp(
    "case whose roster the Coordinator confirmed", str
)


# ---------------------------------------------------------------------------
# Containers and cast
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CastContainer:
    """One container a scenario of this family drives.

    Attributes:
        role: The scenario's own name for the actor, as its ``ROLES`` seats
            it — the stem of its ``--<role>-url`` option and of its devlogs
            directory.  Its cast slot carries the address.
        label: What :func:`check_all_containers` calls it when it is down.
        url: Base-URL override from the command line, or ``None`` to take the
            cast slot's own address (DEMOCI-11-020).
    """

    role: str
    label: str
    url: str | None = None


def coordinated_clients(
    roles: Mapping[str, ActorRole],
    members: Sequence[CastContainer],
    *,
    skip_health_check: bool,
    case_actor_url: str | None = None,
) -> dict[str, DataLayerClient]:
    """Build one client per *member* plus the CaseActor's, health-checked.

    Every scenario of the family builds its clients the same way, binds the
    case-actor one to its CaseActor, and health-checks them all, so it is done
    once here rather than once per ``main()`` (DEMOMA-17-001).  Each URL falls
    back to the cast slot's own address, which is why the scenario modules
    declare no ``*_BASE_URL`` constants of their own (DEMOCI-11-020).

    Args:
        roles: The scenario's :func:`~vultron.demo.helpers.actor_roles\
            .role_map`, which names the cast slot each actor sits in.
        members: The scenario's actor containers, in ``ROLES`` order.
        skip_health_check: Skip the server availability check.
        case_actor_url: Override base URL for the CaseActor container.

    Returns:
        The clients, keyed by each member's ``role`` plus
        :data:`CASE_ACTOR_NAME`.

    Raises:
        SystemExit: When a container is unreachable and the check ran.
        KeyError: When *roles* seats no actor of a member's name — a scenario
            whose ``ROLES`` and ``main()`` have drifted apart.
    """
    clients = {
        member.role: DataLayerClient(
            base_url=member.url or roles[member.role].url
        )
        for member in members
    }
    clients[CASE_ACTOR_NAME] = bound_case_actor_client(
        case_actor_url or roles[CASE_ACTOR_NAME].url
    )
    if not skip_health_check:
        check_all_containers(
            [
                *((member.label, clients[member.role]) for member in members),
                ("CaseActor", clients[CASE_ACTOR_NAME]),
            ]
        )
    return clients


def coordinated_cast_members(
    *,
    reporter_url: str | None = None,
    coordinator_url: str | None = None,
    vendor_url: str | None = None,
) -> list[CastContainer]:
    """The three containers every scenario of this family seats by role.

    The fixed-role cast in ``ROLES`` order: the whole cast of a scenario that
    brings in no character actor, and the opening of one that does — exactly
    the three :func:`open_coordinated_cast` seeds.  Declared here rather than
    in each ``main()`` because it is the same three lines in every scenario
    that takes the family's default labels, and a fourth scenario copying them
    is how a cast drifts (DEMOMA-17-001).

    A scenario whose vendor is one of two labels it apart (``rcvv-embargo``'s
    "Vendor1") or whose roles carry its own option stems (``rcvcv``'s ``c1``
    and ``v1``) builds its own list: the labels are what a reader sees when a
    container is down, and naming them is that scenario's business.

    Args:
        reporter_url: Base-URL override for the Reporter's container, or
            ``None`` to take its cast slot's own address (DEMOCI-11-020).
        coordinator_url: The same, for the Coordinator's.
        vendor_url: The same, for the Vendor's.

    Returns:
        The three members, to hand to :func:`coordinated_clients`.
    """
    return [
        CastContainer(REPORTER, REPORTER_LABEL, reporter_url),
        CastContainer(COORDINATOR, COORDINATOR_LABEL, coordinator_url),
        CastContainer(VENDOR, VENDOR_LABEL, vendor_url),
    ]


def open_coordinated_cast(
    harness: ScenarioHarness,
    *,
    reporter_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    dump: Fragment,
    reporter_id: str | None = None,
    coordinator_id: str | None = None,
    vendor_id: str | None = None,
    unseated: Mapping[str, UnseatedContainer] | None = None,
) -> StoryState:
    """Reset this family's containers, seed its three, and return its cast.

    The opening of every Reporter + Coordinator + Vendor scenario: the same
    reset and the same seeding, so no scenario writes either (DEMOMA-17-001).
    Each seeded actor is read back from its own container, which is the form a
    trigger session binds to.

    Only the three fixed-role containers are seeded.  A scenario's character
    actors are reset here with the rest — a run must start from a clean
    baseline on every container it will touch (DEMOMA-01-003) — and seeded by
    the fragment that brings each into the case, because every actor and peer
    record written before the case exists reads the recording clock and so
    moves the first ledger entry's timestamp away from the siblings this
    opening must match byte for byte (DEMOCI-11-018, #5532).

    Args:
        harness: The run's :class:`~vultron.demo.helpers.harness\
            .ScenarioHarness`.
        reporter_client: Client for the Reporter's container.
        coordinator_client: Client for the Coordinator's container.
        vendor_client: Client for the Vendor's container.
        case_actor_client: Client for the dedicated case-actor container.
        dump: The scenario's ledger dump, armed when the case opens.
        reporter_id: Deterministic URI for the Reporter actor, when given.
        coordinator_id: Deterministic URI for the Coordinator actor.
        vendor_id: Deterministic URI for the Vendor actor.
        unseated: Each further container the scenario will seed and seat a
            character actor in, by the name it will seat it under.  Reset
            here with the rest, seeded by the fragment that brings its actor
            into the case (:class:`UnseatedContainer`).

    Returns:
        The story state the family's fragments run against.

    Raises:
        DemoStoryError: When the containers could not be seeded, so there is
            no cast to tell the story with.
    """
    waiting = dict(unseated or {})
    targets: list[tuple[str, DataLayerClient]] = [
        (REPORTER_LABEL, reporter_client),
        (COORDINATOR_LABEL, coordinator_client),
        (VENDOR_LABEL, vendor_client),
        *((slot.label, slot.client) for slot in waiting.values()),
    ]
    reset_containers(
        targets,
        reset_fn=reset_datalayer,
        case_actor_client=case_actor_client,
    )

    seeded = None
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
        unseated=waiting,
    )


def coordinated_open_cast(
    *,
    reporter_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    dump: Fragment,
    reporter_id: str | None = None,
    coordinator_id: str | None = None,
    vendor_id: str | None = None,
    unseated: Mapping[str, UnseatedContainer] | None = None,
) -> Callable[[ScenarioHarness], StoryState]:
    """The ``open_cast`` callable :func:`~.story.run_story` takes.

    Every scenario of the family hands ``run_story`` the same closure over
    :func:`open_coordinated_cast`, so it is built here rather than written out
    once per scenario module (DEMOMA-17-001).  The arguments are
    :func:`open_coordinated_cast`'s; the harness is the one ``run_story``
    enters, which is what puts a seeding failure inside the harness that dumps
    and reports it.
    """

    def open_cast(harness: ScenarioHarness) -> StoryState:
        return open_coordinated_cast(
            harness,
            reporter_client=reporter_client,
            coordinator_client=coordinator_client,
            vendor_client=vendor_client,
            case_actor_client=case_actor_client,
            dump=dump,
            reporter_id=reporter_id,
            coordinator_id=coordinator_id,
            vendor_id=vendor_id,
            unseated=unseated,
        )

    return open_cast


def seat_character_actors(
    state: StoryState, joining: Mapping[str, str]
) -> None:
    """Read every named actor back from its container, then seat them all.

    The second half of bringing character actors in: the fragment seeded them
    on the containers :meth:`StoryState.container` named, and this binds the
    sessions the story's later fragments reach them through.  Each actor is
    read back from its own container, which is the form a trigger session
    binds to.

    The two halves are separated so a failed read-back leaves *none* of them
    seated: a partly seated cast lets the fragment that reaches for the seated
    one run a real protocol act before the next one stops the story
    (#2308, EDF-06-005).

    Args:
        state: The running story's state.
        joining: The actor id to seat under each cast name, in seating order.
    """
    sessions = {
        name: ActorSession(
            client=state.container(name).client,
            actor=get_actor_by_id(state.container(name).client, actor_id),
        )
        for name, actor_id in joining.items()
    }
    for name, session in sessions.items():
        state.seat(name, session)


def dump_coordinated_ledgers(
    state: StoryState,
    *,
    replicas: Sequence[str | tuple[str, str]],
    unreplicated: Sequence[str] = (),
) -> None:
    """Dump each named cast member's case ledger, and the canonical one.

    Thin scenario-agnostic wrapper (DEMOMA-23-002) over
    :func:`~vultron.demo.helpers.ledger_dump.dump_case_ledgers`, which owns
    the per-actor export, the 404 handling and the dump manifest.  This only
    says whose ledgers to dump and where each lives; the canonical one is read
    from the dedicated case-actor container (DEMOMA-06-005).

    Args:
        state: The running story's state.
        replicas: Whose replicas hold a copy, in dump order.  A cast name
            stands for itself; a ``(devlogs name, cast name)`` pair is for a
            scenario whose own name for an actor differs from the family role
            the story seats it under — ``rcvcv`` calls its Coordinator ``c1``
            in its devlogs, which is how its invariant harness finds it
            (DEMOMA-19-018).
        unreplicated: Cast names with no replica to dump, recorded in the
            manifest so a narrative tag still resolves to them — the Vendor
            that rejected its invitation was never a participant (#4248).
    """
    # Route keys come from each client's own actor id, not from its cast
    # name: the key selects the store (ADR-0073), so a literal only happens
    # to be right while a scenario seeds deterministic named ids.
    named = [
        (entry, entry) if isinstance(entry, str) else entry
        for entry in replicas
    ]
    targets = [
        LedgerDumpTarget(
            devlogs_name,
            state.client(member),
            replica_route_key(state.client(member)),
        )
        for devlogs_name, member in named
    ]
    targets.append(case_actor_dump_target(state.case_actor_client))
    dump_case_ledgers(
        demo_name=state.harness.demo_name,
        case=state.case,
        targets=targets,
        unreplicated={
            name: replica_route_key(state.client(name))
            for name in unreplicated
        }
        or None,
    )


# ---------------------------------------------------------------------------
# The shared opening
# ---------------------------------------------------------------------------


def reporter_tells_coordinator(state: StoryState) -> None:
    """The Reporter submits its report; the Coordinator engages the case.

    The Coordinator validates the report and engages the case (RM→ACCEPTED),
    holding CASE_OWNER; each step is gated on its own RM state.  The Reporter
    is seated when the case is created (CM-22-002), so it is never invited
    (DEMOMA-12-003).

    The case is recorded as soon as the triage returns it, which arms the
    ledger dump at the first instant there is anything to dump, so every step
    below can fail without costing the ledgers (DEMOMA-23-003, ISSUE-2239).
    Then the roster wait is a ``demo_gate``: the Reporter and the Coordinator
    both being seated is the precondition for inviting anyone else, so a
    timeout skips the M1 check, the re-read and :data:`ENGAGED_CASE`, and
    :func:`coordinator_invites_vendor` stops the story rather than inviting
    into a case the owner cannot vouch for (DEMOCI-01-011).
    """
    reporter = state.actor(REPORTER).actor
    coordinator = state.actor(COORDINATOR).actor
    owner_client = state.client(COORDINATOR)
    report, offer = reporter_submits_report(
        receiver_client=owner_client,
        reporter=reporter,
        receiver=coordinator,
        reporter_client=state.client(REPORTER),
    )
    case = run_direct_path_rm_triage(
        receiver_client=owner_client,
        receiver=coordinator,
        offer=offer,
        timeout_seconds=OWNER_TRIAGE_TIMEOUT,
    )
    # Recorded here, at the first instant there is anything to dump, so every
    # step below can fail without costing the ledgers (DEMOMA-23-003,
    # ISSUE-2239) — including the gate that follows.
    state.open_case(case=case, report=report, offer=offer)

    with demo_gate(
        "Coordinator case reflects Reporter + Coordinator participants"
    ):
        wait_for_case_participants(
            vendor_client=owner_client,
            case_id=case.id_,
            expected_actor_ids={reporter.id_, coordinator.id_},
        )

        with demo_check(
            "M1: ≥3 participants, EM.ACTIVE, Reporter has replica"
        ):
            verify_case_active(
                receiver_client=owner_client,
                reporter_client=state.client(REPORTER),
                case_id=case.id_,
                receiver_actor_id=coordinator.id_,
                reporter_actor_id=reporter.id_,
            )

        # Re-read the case as the Coordinator now stores it: the triage and
        # the participant seating have moved on since the trigger returned it.
        state.restate_case(
            as_VulnerabilityCase.model_validate(
                owner_client.get(owner_client.dl_path(case.id_))
            )
        )
        state.keep(ENGAGED_CASE, str(case.id_))


def coordinator_invites_vendor(state: StoryState) -> None:
    """The Coordinator invites the Vendor, and the Invite is delivered.

    The Coordinator is CASE_OWNER, so it invites directly rather than through
    the ADR-0026 suggest/approve chain (DEMOMA-12-004).  The fragment stops at
    delivery: the Vendor's answer is the next branch point's choice.

    Reads :data:`ENGAGED_CASE` first: the Reporter and the Coordinator being
    seated is this invite's causal precondition, so a roster that never
    arrived stops the story here instead of inviting into a case the owner
    cannot vouch for (DEMOCI-01-011).
    """
    state.kept(ENGAGED_CASE)
    state.invited(
        VENDOR,
        invite_and_await_delivery(
            case=state.case,
            invitee_name=VENDOR_LABEL,
            invitee_client=state.client(VENDOR),
            invitee=state.actor(VENDOR).actor,
            inviter=CaseInviter(
                name=COORDINATOR_LABEL,
                client=state.client(COORDINATOR),
                actor=state.actor(COORDINATOR).actor,
                role=CVDRole.VENDOR,
            ),
            case_manager_client=state.case_actor_client,
            invite_timeout=CROSS_CONTAINER_TIMEOUT,
        ),
    )


#: The opening every coordinator-first scenario shares, whoever the
#: Coordinator invites next: the Reporter tells the Coordinator and the
#: Coordinator engages the case.  It stops where the Coordinator's decision
#: falls — invite the Vendor (:data:`COORDINATOR_INVITES_VENDOR` and its
#: siblings) or invite a second Coordinator
#: (:mod:`vultron.demo.helpers.two_coordinator_story`, #5535).
REPORTER_TELLS_THE_COORDINATOR = story(
    choose("reporter-whom-to-tell", "coordinator", by=REPORTER),
    reporter_tells_coordinator,
)


#: The opening every Reporter → Coordinator → Vendor scenario shares: the
#: Reporter tells the Coordinator, and the Coordinator invites the Vendor.
#: Named rather than assembled from the fragments at each call site, because
#: assembling siblings from fragments alone lets one of them slip a step in
#: before the branch point (``notes/demo-scenario-tree.md`` § "Composition").
COORDINATOR_INVITES_VENDOR = story(
    REPORTER_TELLS_THE_COORDINATOR,
    choose("coordinator-invite-whom", "vendor", by=COORDINATOR),
    coordinator_invites_vendor,
)


def await_reporter_case_replica(
    state: StoryState, timeout_seconds: float = CROSS_CONTAINER_TIMEOUT
) -> None:
    """Gate the Reporter holding the case replica before an invitee answers.

    The Reporter must hold it before the invitee's reply to the full-case
    Invite (RM Received to Valid), which broadcasts
    ``Announce(CaseLedgerEntry)`` to all participants (CLP-08-005): a Reporter
    without the case has no genesis hash to anchor the chain on (Bug #2135).
    The case is already open, so the replica does not depend on the invitee
    joining.

    Args:
        state: The running story's state.
        timeout_seconds: Seconds to wait.  An invitee reached through a
            multi-hop path waits behind more fan-out, so its scenario passes a
            wider budget.
    """
    with demo_check("Reporter's DataLayer received case replica"):
        wait_for_case_on_container(
            client=state.client(REPORTER),
            case_id=state.case.id_,
            timeout_seconds=timeout_seconds,
        )


def invitee_triages_after_joining(
    state: StoryState,
    name: str,
    label: str,
    *,
    seated: Sequence[str],
    owner: str = COORDINATOR,
    owner_label: str = COORDINATOR_LABEL,
    join_timeout: float = PARTICIPANT_JOIN_TIMEOUT,
    triage_timeout: float = CROSS_CONTAINER_TIMEOUT,
) -> None:
    """Gate on every participant being seated, then run *name*'s RM triage.

    CM-11-002: an invitee that joined by accepting runs its RM triage.  All
    participants present is that triage's causal precondition, so it is a
    ``demo_gate``, not a ``demo_check``: a timeout skips the doomed triage
    rather than cascading (DEMOCI-01-011, ``vultron/demo/AGENTS.md`` § "Never
    Wrap a Causal Wait in demo_check").  The roster is read from the Case
    Owner's replica.

    Args:
        state: The running story's state.
        name: The invitee's cast name.
        label: What this scenario calls it in gate labels.
        seated: Every cast name the roster must hold by now, the invitee
            included.
        owner: The Case Owner's cast name, whose replica the roster is read
            from.  The family's Coordinator by default; a story whose owner
            changed mid-run names the owner as of this step (#5535).
        owner_label: What this scenario calls that owner in gate labels.
        join_timeout: Seconds to wait for the roster.  A joiner reached
            through a multi-hop path needs the late-joiner budget rather than
            the default one.
        triage_timeout: Seconds each wait of the triage itself may take.
    """
    invitee = state.actor(name).actor
    with demo_gate(f"{owner_label} case has {label} before {label} RM triage"):
        wait_for_case_participants(
            vendor_client=state.client(owner),
            case_id=state.case.id_,
            expected_actor_ids={state.actor_id(who) for who in seated},
            timeout_seconds=join_timeout,
        )
        logger.info("✓ M2: %s joined case", label)

        run_invite_path_rm_triage(
            invited_client=state.client(name),
            invited_actor=invitee,
            offer=state.offer,
            report=state.report,
            reporter=state.actor(REPORTER).actor,
            auth_client=state.case_actor_client,
            case=state.case,
            invited_obj=invitee,
            timeout_seconds=triage_timeout,
        )


def vendor_accepts_and_joins(state: StoryState) -> None:
    """The Vendor accepts the Invite, takes its replica and triages the report.

    The Invite's delivery, which a story places before the Vendor's branch
    point, is the only part of the join that sits outside this fragment.
    """
    vendor = state.actor(VENDOR).actor
    await_reporter_case_replica(state)

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
        state,
        VENDOR,
        VENDOR_LABEL,
        seated=(REPORTER, COORDINATOR, VENDOR),
    )


def invitee_joins_the_case(
    state: StoryState,
    name: str,
    label: str,
    *,
    role: CVDRole,
    seated: Sequence[str],
    triages: bool = True,
    joined: StoryProp[str] | None = None,
    join_timeout: float = PARTICIPANT_JOIN_TIMEOUT,
    cross_container_timeout: float = CROSS_CONTAINER_TIMEOUT,
) -> None:
    """The Coordinator invites the seated *name*, which accepts and joins.

    The whole invite chain in one step, for an invitee whose decision is no
    branch point of the tree: the Invite, the Accept, the case replica, the
    reply to the full-case Invite (:func:`~vultron.demo.helpers.invite_chain\
    .run_case_invite_chain`) and then its RM triage.  The Vendor's own join is
    the two-halved form instead, because the story's ``choose`` falls between
    the Invite and the answer.

    Args:
        state: The running story's state.
        name: The invitee's cast name; it must be seated already.
        label: What this scenario calls it in step and gate labels.
        role: The role the Invite offers it.
        seated: Every cast name the Case Owner's roster must hold once it has
            joined, the invitee included.
        triages: Whether the invitee runs its RM triage afterwards
            (CM-11-002).  A vendor judges the report it was invited over; a
            coordinator joining to help coordinate does not, and giving it one
            would put an ``engage_case`` act in the ledger the scenario's
            semantic-type list does not claim (DEMOMA-17-002).  When it does
            not triage, the roster check runs inside the chain's own gate
            instead, so a failed invite skips it.
        joined: When given, the roster is this join's causal gate rather than
            a check, and the case id is kept under this prop once the roster
            holds *seated*.  For a non-triaging joiner the next act depends
            on: the two-coordinator pair decides the case's ownership once its
            second Coordinator is a participant (DEMOMA-13-003,
            DEMOMA-14-010), so a roster that never arrived must stop the story
            there rather than offer or suggest into a case the joiner is not
            in (DEMOCI-01-011, #5535).  A flat story cannot nest the next
            fragment inside this gate, so the gate keeps the prop and that
            fragment reads it.  Only the non-triaging path keeps one, so
            passing both this and ``triages=True`` raises rather than leaving
            a prop no step ever keeps.
        join_timeout: Seconds to wait for the roster.
        cross_container_timeout: Seconds each cross-container wait of the
            chain may take.

    Raises:
        DemoStoryError: When *joined* is given with ``triages=True``.
    """
    if triages and joined is not None:
        raise DemoStoryError(
            f"the join of {name!r} was given both triages=True and a prop to "
            "keep, and only the non-triaging path keeps one: a triaging "
            "invitee's roster is already the gate inside "
            "invitee_triages_after_joining, so the prop would never be kept "
            "and every fragment that read it would stop the story."
        )
    invitee = state.actor(name).actor
    await_reporter_case_replica(state, cross_container_timeout)

    def confirm_joined() -> None:
        # A gate when the next fragment depends on the roster, a check when
        # nothing does.  One wait either way, so it cannot be wrapped one way
        # and left bare the other (DEMOCI-01-011).
        context = demo_check if joined is None else demo_gate
        with context(
            f"Coordinator case reflects {len(seated)} participants after "
            f"{label} joined"
        ):
            wait_for_case_participants(
                vendor_client=state.client(COORDINATOR),
                case_id=state.case.id_,
                expected_actor_ids={state.actor_id(who) for who in seated},
                timeout_seconds=join_timeout,
            )
            if joined is not None:
                state.keep(joined, str(state.case.id_))

    run_case_invite_chain(
        case=state.case,
        case_manager_client=state.case_actor_client,
        invitee_name=label,
        invitee_client=state.client(name),
        invitee=invitee,
        invitee_in_own_container=invitee,
        inviter=CaseInviter(
            name=COORDINATOR_LABEL,
            client=state.client(COORDINATOR),
            actor=state.actor(COORDINATOR).actor,
            role=role,
        ),
        invite_timeout=cross_container_timeout,
        replica_timeout=cross_container_timeout,
        then=None if triages else confirm_joined,
    )

    if triages:
        invitee_triages_after_joining(
            state,
            name,
            label,
            seated=seated,
            join_timeout=join_timeout,
            triage_timeout=cross_container_timeout,
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
        auth_label=COORDINATOR_LABEL,
        auth_actor_id=state.actor_id(COORDINATOR),
        reporter_client=state.client(REPORTER),
        reporter_actor_id=state.actor_id(REPORTER),
        replicas=[
            (state.client(REPORTER), REPORTER_LABEL),
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
            (state.client(REPORTER), REPORTER_LABEL),
            (state.client(VENDOR), VENDOR_LABEL),
        ],
    )
    logger.info("✓ M3: All replicas synchronized (LedgerFanout verified)")


#: The opening through the Vendor's acceptance, which every scenario whose
#: Vendor joins shares.  It stops where the Reporter's decision falls: ask the
#: Vendor a question, or propose new embargo terms.
VENDOR_JOINS_THE_CASE = story(
    COORDINATOR_INVITES_VENDOR,
    choose("vendor-join", "accept", by=VENDOR),
    vendor_accepts_and_joins,
    replicas_converge_with_vendor,
)


def reporter_asks_about_the_timeline(state: StoryState) -> None:
    """The Reporter asks the Vendor's timeline; both others answer.

    Each poster acts from its own replica, and the Vendor's holds the case
    only once the Vendor has joined, so the thread waits on it
    (DEMOMA-22-001).  The Coordinator's closing summary is kept for a
    continuation that answers it (:data:`TIMELINE_ANSWER`).
    """
    answered = gated_note_thread(
        gate="Vendor's replica holds the case before the Reporter asks it",
        replica_client=state.client(VENDOR),
        watching_client=state.client(COORDINATOR),
        case=state.case,
        posts=reporter_asks_vendor_timeline(
            state.actor(REPORTER),
            state.actor(VENDOR),
            state.actor(COORDINATOR),
        ),
    )
    if answered is not None:
        state.keep(TIMELINE_ANSWER, answered)
    logger.info(
        "✓ Notes exchange complete (three notes committed to case ledger)"
    )


#: The opening through the note thread the ``ask-vendor`` choice posts.  It
#: stops where the Coordinator's decision falls, which follows the
#: Coordinator's own note in the thread: publish after the Vendor's fix
#: (``rcv``), or invite a second Coordinator (``rcvcv``).
REPORTER_ASKS_THE_VENDOR = story(
    VENDOR_JOINS_THE_CASE,
    choose("reporter-after-join", "ask-vendor", by=REPORTER),
    reporter_asks_about_the_timeline,
)


# ---------------------------------------------------------------------------
# Continuations shared by more than one scenario
# ---------------------------------------------------------------------------


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
        auth_label=COORDINATOR_LABEL,
        auth_actor_id=state.actor_id(COORDINATOR),
        reporter_client=state.client(REPORTER),
        reporter_actor_id=state.actor_id(REPORTER),
        replicas=[(state.client(REPORTER), REPORTER_LABEL)],
        case_id=state.case.id_,
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


def vendor_notifies_fix_ready(
    state: StoryState,
    name: str,
    label: str,
    *,
    then: Callable[[], None] | None = None,
) -> None:
    """*name* reports fix ready (VFd), gated on its own RM state.

    CSB-18-001: the trigger is refused until the vendor's own participant
    record is out of triage, so the gate reads that record first and *then*
    runs, skipping the trigger and everything after it when it never arrives.
    The vendor holds ``CVDRole.VENDOR`` and not ``DEPLOYER``, so it stops at
    VFd (CSB-15-002).

    Args:
        state: The running story's state.
        name: The reporting vendor's cast name.
        label: What this scenario calls it in step labels.
        then: Runs inside the gate, after the vendor's own VF check — what a
            scenario checks on the coordinator side before moving on.  Inside
            the gate so a refused trigger skips it rather than comparing
            replicas that were never written.
    """
    vendor = state.actor(name).actor
    with demo_gate(
        f"{name} RM ∈ {{ACCEPTED,DEFERRED,CLOSED}} before notify-fix-ready"
        " (CSB-18-001)"
    ):
        wait_for_participant_rm_state(
            client=state.client(name),
            case_id=state.case.id_,
            actor_id=vendor.id_,
            expected_states={RM.ACCEPTED, RM.DEFERRED, RM.CLOSED},
        )
        with demo_step(f"Actor {ref_id(vendor)} reports fix ready"):
            state.actor(name).with_case(state.case).quiet().notify_fix_ready()

        with demo_check(f"{label} participant vf_state transitions to VF"):
            wait_for_participant_vf_state(
                client=state.client(name),
                case_id=state.case.id_,
                actor_id=vendor.id_,
                expected_states={CS_vf.VF},
            )

        if then is not None:
            then()


def report_fix_ready(state: StoryState, name: str, label: str) -> None:
    """*name* reports fix ready and the Coordinator sees it.

    :func:`vendor_notifies_fix_ready` plus the Coordinator-side milestones, for
    a scenario with one vendor to check.  A scenario with two batches its
    coordinator-side checks over both instead and calls the notify half
    directly.
    """
    vendor_notifies_fix_ready(
        state,
        name,
        label,
        then=lambda: _coordinator_sees_fix_ready_twice(state, name, label),
    )


def _coordinator_sees_fix_ready_twice(
    state: StoryState, name: str, label: str
) -> None:
    """The M4 and M5 milestones, which read the same thing under two names."""
    _coordinator_sees_fix_ready(
        state,
        name,
        f"M4: Coordinator replica shows {label} CS includes F (fix ready)",
    )
    _coordinator_sees_fix_ready(
        state,
        name,
        f"M5: Coordinator replica shows {label} CS includes F (fix ready)"
        f" — {label} stops at VFd",
    )


def _coordinator_sees_fix_ready(
    state: StoryState, name: str, check: str
) -> None:
    """Wait for, then verify, the Coordinator's view of *name* at VF.

    Owns its own ``demo_check`` rather than being called inside one, so the
    raising wait sits in a demo context where it is written (DEMOCI-01-011).
    """
    with demo_check(check):
        wait_for_participant_vf_state(
            client=state.client(COORDINATOR),
            case_id=state.case.id_,
            actor_id=state.actor_id(name),
            expected_states={CS_vf.VF},
        )
        verify_fix_ready(
            receiver_client=state.client(COORDINATOR),
            reporter_client=state.client(name),
            case_id=state.case.id_,
            receiver_actor_id=state.actor_id(name),
        )


def vendor_reports_the_fix_ready(state: StoryState) -> None:
    """The Vendor reports fix ready and stops at VFd (CSB-15-002)."""
    report_fix_ready(state, VENDOR, VENDOR_LABEL)


def everyone_publishes(state: StoryState) -> None:
    """Each participant reports public disclosure, the Coordinator first.

    Per DEMOMA-07-003(4) the Coordinator, as CASE_OWNER, triggers CS.P.  The
    embargo is ended by then in ``rcv-embargo`` and still active in ``rcv``;
    either way it reads ``EM.EXITED`` once the Coordinator has reported.  In
    ``rcv-embargo`` the two ``EM.EXITED`` checks below only confirm what the
    termination fragment already established; in ``rcv`` they check the
    embargo ending at publication.
    """
    the_coordinator_publishes_and_the_embargo_ends(state)

    reports_published(state, VENDOR)
    reports_published(state, REPORTER)

    with demo_check(
        "M6: all replicas CS.VFdPxa, EM.EXITED, all participants public-aware"
    ):
        wait_for_case_em_terminated(
            client=state.client(VENDOR), case_id=state.case.id_
        )
        for name in (COORDINATOR, REPORTER):
            wait_for_participant_vf_state(
                client=state.client(name),
                case_id=state.case.id_,
                actor_id=state.actor_id(VENDOR),
                expected_states={CS_vf.VF},
            )
        verify_publicly_disclosed(
            receiver_client=state.client(COORDINATOR),
            reporter_client=state.client(REPORTER),
            case_id=state.case.id_,
            receiver_actor_id=state.actor_id(VENDOR),
        )


def the_coordinator_publishes_and_the_embargo_ends(state: StoryState) -> None:
    """The Coordinator, as CASE_OWNER, triggers CS.P; the embargo exits.

    Per DEMOMA-07-003(4) the Coordinator reports first, and the embargo reads
    ``EM.EXITED`` once it has: in ``rcv`` that is the embargo ending at
    publication, and in ``rcv-embargo`` it confirms the termination the
    scenario already asserted.  One copy for every continuation that starts
    this way, whether the Vendor joined or declined.
    """
    reports_published(state, COORDINATOR)

    with demo_check(
        "Embargo terminated (EM.EXITED) after Coordinator reports published"
    ):
        wait_for_case_em_terminated(
            client=state.client(COORDINATOR), case_id=state.case.id_
        )


def reports_published(state: StoryState, name: str) -> None:
    """*name* triggers CS.P from its own container.

    One copy for every scenario of the family: the order its participants
    report in differs, and the step itself does not.
    """
    session = state.actor(name)
    with demo_step(
        f"Actor {ref_id(session.actor)} reports vulnerability"
        " publicly disclosed"
    ):
        session.with_case(state.case).quiet().notify_published()


def coordinator_and_reporter_publish(state: StoryState) -> None:
    """The Coordinator then the Reporter report published; the embargo ends.

    The two-party form of :func:`everyone_publishes`, for a story whose Vendor
    declined: the Coordinator, as CASE_OWNER, triggers CS.P (DEMOMA-07-003(4))
    and the embargo terminates (EM.EXITED).
    """
    the_coordinator_publishes_and_the_embargo_ends(state)

    reports_published(state, REPORTER)

    with demo_check("M3: EM.EXITED, Coordinator and Reporter public-aware"):
        wait_for_case_em_terminated(
            client=state.client(REPORTER), case_id=state.case.id_
        )
        verify_publicly_disclosed(
            receiver_client=state.client(COORDINATOR),
            reporter_client=state.client(REPORTER),
            case_id=state.case.id_,
            receiver_actor_id=state.actor_id(COORDINATOR),
        )


def close_the_case(
    state: StoryState,
    *,
    others: Sequence[str],
    owner: str = COORDINATOR,
    milestone: str,
) -> None:
    """*others* leave the case in order; *owner*, the Case Owner, leaves last.

    The owner leaves once the others' departures are recorded in the
    CASE_MANAGER's store (CM-23-015).  Every closure is verified there,
    through the dedicated case-actor container, and each leaver's own replica
    only for its own closure (CM-23-004,
    :func:`~vultron.demo.helpers.closure.close_case_owner_last`).

    Args:
        state: The running story's state.
        others: The cast names that leave first, in leaving order.
        owner: The cast name of the Case Owner.
        milestone: The closure milestone this scenario numbers it.
    """
    close_case_owner_last(
        case=state.case,
        milestone=milestone,
        authority_client=state.case_actor_client,
        others=[
            CaseLeaver(
                client=state.client(name), actor=state.actor(name).actor
            )
            for name in others
        ],
        owner=CaseLeaver(
            client=state.client(owner), actor=state.actor(owner).actor
        ),
    )


def everyone_closes(state: StoryState) -> None:
    """Every participant closes the case; the Case Owner leaves last."""
    close_the_case(state, others=(VENDOR, REPORTER), milestone="M7")


def reporter_then_coordinator_close(state: StoryState) -> None:
    """The Reporter leaves, then the Coordinator, the Case Owner, leaves last.

    The two-party form of :func:`everyone_closes`.
    """
    close_the_case(state, others=(REPORTER,), milestone="M4")


__all__ = [
    "CASE_ACTOR_NAME",
    "ENGAGED_CASE",
    "COORDINATOR",
    "COORDINATOR_INVITES_VENDOR",
    "COORDINATOR_LABEL",
    "CROSS_CONTAINER_TIMEOUT",
    "OWNER_TRIAGE_TIMEOUT",
    "REPORTER",
    "REPORTER_ASKS_THE_VENDOR",
    "REPORTER_LABEL",
    "REPORTER_TELLS_THE_COORDINATOR",
    "TIMELINE_ANSWER",
    "VENDOR",
    "VENDOR_JOINS_THE_CASE",
    "VENDOR_LABEL",
    "CastContainer",
    "await_reporter_case_replica",
    "close_the_case",
    "coordinated_cast_members",
    "coordinated_clients",
    "coordinated_open_cast",
    "coordinator_and_reporter_publish",
    "coordinator_invites_vendor",
    "dump_coordinated_ledgers",
    "everyone_closes",
    "everyone_publishes",
    "invitee_joins_the_case",
    "invitee_triages_after_joining",
    "open_coordinated_cast",
    "report_fix_ready",
    "vendor_notifies_fix_ready",
    "reporter_asks_about_the_rejection",
    "reports_published",
    "the_coordinator_publishes_and_the_embargo_ends",
    "reporter_asks_about_the_timeline",
    "reporter_replica_converges",
    "reporter_tells_coordinator",
    "reporter_then_coordinator_close",
    "replicas_converge_with_vendor",
    "seat_character_actors",
    "vendor_accepts_and_joins",
    "vendor_rejects_invite",
    "vendor_reports_the_fix_ready",
]
