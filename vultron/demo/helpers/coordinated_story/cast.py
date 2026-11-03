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
"""The coordinator-first family's cast: its names, labels and containers.

The three fixed-role cast names every fragment of the family reads, the
labels its steps print, the timeouts its cross-container waits share, and
the reset/seed/seat opening that turns three containers into a
:class:`~vultron.demo.helpers.story.StoryState`
(:mod:`vultron.demo.helpers.story_cast` does the generic part).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers.harness import ScenarioHarness
from vultron.demo.helpers.seeding import get_actor_by_id, seed_containers_rcv
from vultron.demo.helpers.story import Fragment, StoryState, UnseatedContainer
from vultron.demo.helpers.story_cast import (
    CastContainer,
    CastSeat,
    open_story_cast,
)
from vultron.demo.utils import DataLayerClient

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
        The three members, to hand to
        :func:`~vultron.demo.helpers.story_cast.story_clients`.
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
    return open_story_cast(
        harness,
        seats=coordinated_seats(
            reporter_client=reporter_client,
            coordinator_client=coordinator_client,
            vendor_client=vendor_client,
            reporter_id=reporter_id,
            coordinator_id=coordinator_id,
            vendor_id=vendor_id,
        ),
        seed=lambda: seed_containers_rcv(
            reporter_client=reporter_client,
            coordinator_client=coordinator_client,
            vendor_client=vendor_client,
            reporter_actor_id=reporter_id,
            coordinator_actor_id=coordinator_id,
            vendor_actor_id=vendor_id,
            case_actor_client=case_actor_client,
        ),
        seed_step="Seeding Reporter, Coordinator, and Vendor containers",
        case_actor_client=case_actor_client,
        dump=dump,
        unseated=unseated,
    )


def coordinated_seats(
    *,
    reporter_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    reporter_id: str | None = None,
    coordinator_id: str | None = None,
    vendor_id: str | None = None,
) -> tuple[CastSeat, CastSeat, CastSeat]:
    """This family's three fixed-role seats, in ``seed_containers_rcv`` order.

    The order is the seeder's return order, which is what binds each session
    to its own container (:func:`~vultron.demo.helpers.story_cast\
    .open_story_cast`).
    """
    return (
        CastSeat(REPORTER, REPORTER_LABEL, reporter_client, reporter_id),
        CastSeat(
            COORDINATOR, COORDINATOR_LABEL, coordinator_client, coordinator_id
        ),
        CastSeat(VENDOR, VENDOR_LABEL, vendor_client, vendor_id),
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


__all__ = [
    "COORDINATOR",
    "COORDINATOR_LABEL",
    "CROSS_CONTAINER_TIMEOUT",
    "OWNER_TRIAGE_TIMEOUT",
    "REPORTER",
    "REPORTER_LABEL",
    "VENDOR",
    "VENDOR_LABEL",
    "coordinated_cast_members",
    "coordinated_open_cast",
    "coordinated_seats",
    "open_coordinated_cast",
    "seat_character_actors",
]
