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
from vultron.demo.helpers.harness import ScenarioHarness
from vultron.demo.helpers.seeding import get_actor_by_id, reset_containers
from vultron.demo.helpers.story import (
    Fragment,
    StoryState,
    UnseatedContainer,
)
from vultron.demo.utils import DataLayerClient, demo_step, reset_datalayer
from vultron.errors import DemoStoryError
from vultron.wire.as2.vocab.base.objects.actors import as_Actor

logger = logging.getLogger(__name__)


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


def story_open_cast(
    *,
    seats: Sequence[CastSeat],
    seed: CastSeeder,
    seed_step: str,
    case_actor_client: DataLayerClient,
    dump: Fragment,
    unseated: Mapping[str, UnseatedContainer] | None = None,
) -> Callable[[ScenarioHarness], StoryState]:
    """The ``open_cast`` callable :func:`~.story.run_story` takes.

    Every scenario hands ``run_story`` a closure over :func:`open_story_cast`,
    so it is built here rather than written out once per family.  The
    arguments are :func:`open_story_cast`'s; the harness is the one
    ``run_story`` enters, which is what puts a seeding failure inside the
    harness that dumps and reports it.
    """

    def open_cast(harness: ScenarioHarness) -> StoryState:
        return open_story_cast(
            harness,
            seats=seats,
            seed=seed,
            seed_step=seed_step,
            case_actor_client=case_actor_client,
            dump=dump,
            unseated=unseated,
        )

    return open_cast


__all__ = [
    "CastSeat",
    "CastSeeder",
    "open_story_cast",
    "story_open_cast",
]
