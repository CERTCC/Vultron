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
"""Open a story's cast: reset the containers, seed the fixed-role ones, seat them.

Every composed family's opening does the same three things before its first
fragment runs — reset every container the run will touch (DEMOMA-01-003), seed
the fixed-role ones, and bind an
:class:`~vultron.demo.actor_session.ActorSession` per cast name — and differs
only in which containers those are and which ``seed_containers_*`` creates
them.  That shape is written here once, so a second family does not copy the
first family's opening (DEMOMA-17-001, CS-22-001).

What a family supplies is its :class:`CastSeat`\\ s, in the order its seeder
returns actors, and the seeder itself as a :class:`CastSeeder` closure.  What
it must **not** supply is a container only some of its scenarios use: those
are reset here with the rest and left as
:class:`~vultron.demo.helpers.story.UnseatedContainer`\\ s for the fragment
that brings each actor into the case, because every actor and peer record
written before the case exists reads the recording clock and so moves the
first ledger entry away from the siblings the opening must match byte for byte
(DEMOCI-11-018, #5532).

Design: ``notes/demo-scenario-tree.md`` § "Composition".
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers.actor_roles import ActorRole
from vultron.demo.helpers.cast import CASE_ACTOR
from vultron.demo.helpers.harness import ScenarioHarness
from vultron.demo.helpers.ledger_dump import (
    LedgerDumpTarget,
    case_actor_dump_target,
    dump_case_ledgers,
    replica_route_key,
)
from vultron.demo.helpers.runner import check_all_containers
from vultron.demo.helpers.seeding import get_actor_by_id, reset_containers
from vultron.demo.helpers.story import (
    Fragment,
    StoryState,
    UnseatedContainer,
)
from vultron.demo.utils import (
    DataLayerClient,
    bound_case_actor_client,
    demo_step,
    reset_datalayer,
)
from vultron.errors import DemoStoryError
from vultron.wire.as2.vocab.base.objects.actors import as_Actor

logger = logging.getLogger(__name__)

#: The name of the dedicated CaseActor container slot (DEMOCI-11-020).
#: Used as the key for the CaseActor client in the dict :func:`story_clients`
#: returns, so every scenario can look it up without a literal.
CASE_ACTOR_NAME: str = CASE_ACTOR.name


@dataclass(frozen=True, slots=True)
class CastContainer:
    """One container a scenario drives.

    Attributes:
        role: The scenario's own name for the actor, as its ``ROLES`` seats
            it — the stem of its ``--<role>-url`` option and of its devlogs
            directory.  Its cast slot carries the address.
        label: What :func:`~vultron.demo.helpers.runner.check_all_containers`
            calls it when it is down.
        url: Base-URL override from the command line, or ``None`` to take the
            cast slot's own address (DEMOCI-11-020).
    """

    role: str
    label: str
    url: str | None = None


def story_clients(
    roles: Mapping[str, ActorRole],
    members: Sequence[CastContainer],
    *,
    skip_health_check: bool,
    case_actor_url: str | None = None,
) -> dict[str, DataLayerClient]:
    """Build one client per *member* plus the CaseActor's, health-checked.

    Every scenario of every family builds its clients the same way, binds the
    case-actor one to its CaseActor, and health-checks them all, so it is done
    once here rather than once per ``main()`` (DEMOMA-17-001).  Each URL falls
    back to the cast slot's own address, which is why scenario modules declare
    no ``*_BASE_URL`` constants of their own (DEMOCI-11-020).

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


def dump_story_ledgers(
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


@dataclass(frozen=True, slots=True)
class CastSeat:
    """One container a family's shared opening seeds and seats.

    Attributes:
        name: The cast name the story seats the actor under, the key
            :meth:`~vultron.demo.helpers.story.StoryState.actor` reads.
        label: What the reset and the health check call the container.
        client: Client for it.
        actor_id: The deterministic URI its actor is to be seeded with, when
            the run was given one; ``None`` lets the container derive it.
    """

    name: str
    label: str
    client: DataLayerClient
    actor_id: str | None = None


#: Creates the actors of a family's :class:`CastSeat`\\ s, **in seat order**.
#: A closure, because each family's ``seed_containers_*`` names its own
#: keywords.  It returns ``None`` when the seeding failed and recorded the
#: failure, which :func:`open_story_cast` turns into a stop.
CastSeeder = Callable[[], Sequence[as_Actor] | None]


def open_story_cast(
    harness: ScenarioHarness,
    *,
    seats: Sequence[CastSeat],
    seed: CastSeeder,
    seed_step: str,
    case_actor_client: DataLayerClient,
    dump: Fragment,
    unseated: Mapping[str, UnseatedContainer] | None = None,
) -> StoryState:
    """Reset this family's containers, seed its *seats*, and return its cast.

    Each seeded actor is read back from its own container, which is the form a
    trigger session binds to.  Only the *seats* are seeded: a container
    *unseated* names is reset here with the rest and seeded by the fragment
    that brings its actor into the case (:class:`CastSeat`, module docstring).

    Args:
        harness: The run's :class:`~vultron.demo.helpers.harness\
            .ScenarioHarness`.
        seats: The fixed-role containers, in the order *seed* returns actors.
        seed: Creates those actors (:data:`CastSeeder`).
        seed_step: The ``demo_step`` label the seeding runs under.
        case_actor_client: Client for the dedicated case-actor container,
            which is reset too and has its CaseActor identity re-seeded
            (DEMOMA-06-004).
        dump: The scenario's ledger dump, armed when the case opens.
        unseated: Each further container the scenario will seed and seat an
            actor in, by the name it will seat it under.

    Returns:
        The story state this family's fragments run against.

    Raises:
        DemoStoryError: When the containers could not be seeded, so there is
            no cast to tell the story with, or when *seed* returned a
            different number of actors from the seats it was given — then the
            cast would bind a session to the wrong container.
    """
    waiting = dict(unseated or {})
    reset_containers(
        [
            *((seat.label, seat.client) for seat in seats),
            *((slot.label, slot.client) for slot in waiting.values()),
        ],
        reset_fn=reset_datalayer,
        case_actor_client=case_actor_client,
    )

    seeded: Sequence[as_Actor] | None = None
    with demo_step(seed_step):
        seeded = seed()
    if seeded is None:
        raise DemoStoryError(
            "the "
            + ", ".join(seat.label for seat in seats)
            + " containers could not be seeded, so the story has no cast to "
            "run on; the seeding failure is recorded above."
        )
    if len(seeded) != len(seats):
        raise DemoStoryError(
            f"the seeding returned {len(seeded)} actors for "
            f"{len(seats)} cast seats ({[seat.name for seat in seats]}); the "
            "seeder returns one actor per seat, in seat order, or the cast "
            "would bind a session to another container's actor."
        )

    return StoryState(
        cast={
            seat.name: ActorSession(
                client=seat.client,
                actor=get_actor_by_id(seat.client, actor.id_),
            )
            for seat, actor in zip(seats, seeded, strict=True)
        },
        case_actor_client=case_actor_client,
        harness=harness,
        dump=dump,
        unseated=waiting,
    )


__all__ = [
    "CASE_ACTOR_NAME",
    "CastContainer",
    "CastSeat",
    "CastSeeder",
    "dump_story_ledgers",
    "open_story_cast",
    "story_clients",
]
