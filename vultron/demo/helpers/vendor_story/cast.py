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
"""The vendor-first family's cast: its names, labels and containers.

The cast names and labels of the two Vendors, the timeouts the family's
waits share, the parts the ``owner-keep-case`` continuations act on, and
the reset/seed/seat opening that seeds only the Reporter's and the first
Vendor's containers (DEMOCI-11-018, #5532).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from vultron.demo.helpers.coordinated_story import REPORTER, REPORTER_LABEL
from vultron.demo.helpers.harness import ScenarioHarness
from vultron.demo.helpers.owner_decision_story import Part
from vultron.demo.helpers.polling import LATE_JOINER_TIMEOUT
from vultron.demo.helpers.seeding import seed_containers
from vultron.demo.helpers.story import Fragment, StoryState, UnseatedContainer
from vultron.demo.helpers.story_cast import (
    CastSeat,
    dump_story_ledgers,
    open_story_cast,
)
from vultron.demo.utils import DataLayerClient

#: The names this family's stories seat their two opening members under, and
#: so the keys of :attr:`StoryState.cast` every fragment here reads.  The
#: Reporter's is the rcv family's, because the continuations both halves of
#: the tree share read the Reporter under that name
#: (:data:`~vultron.demo.helpers.owner_decision_story.REPORTER_PART`).
VENDOR = "vendor"

#: The second Vendor, which three of the four scenarios bring in: ``rvv`` by
#: invitation from the first Vendor, the ``rvcv`` pair through the owner's
#: decision.  Seated by the fragment that seeds it, never by the opening.
VENDOR2 = "vendor2"

#: How the two vendors are named in this family's step and gate labels.
#: ``Vendor1`` rather than ``Vendor`` even in ``rv``, which has only one: one
#: authored opening means one label, and three of the four scenarios have a
#: second Vendor to tell it apart from.  Each scenario's ``ROLES`` keeps its
#: own labels, which is what the CLI help and the health check read.
VENDOR_LABEL = "Vendor1"
VENDOR2_LABEL = "Vendor2"

#: Seconds the first Vendor's own RM triage may take.  One authored opening
#: means one budget, so it is the widest member's: the ``rvcv`` pair raised it
#: to 60 s for a run that brings five actor containers up under CI load, and
#: the narrower scenarios inherit it.  A budget only bounds how long a wait may
#: take, so raising it refuses nothing a shorter one admitted and moves no byte
#: of a recording (DEMOCI-11-018).
VENDOR_TRIAGE_TIMEOUT = 60.0

#: Seconds the Reporter's case replica may take to arrive.  The 30 s
#: ``wait_for_reporter_case`` budget every scenario of this family used for it.
CASE_REPLICA_TIMEOUT = 30.0

#: Seconds each cross-container wait of a joiner's arrival may take.  Every
#: join of this family reaches its actor through the CaseActor — invited
#: directly, suggested and approved, or invited by a new owner — so each wait
#: queues behind the same outbox and takes the late-joiner budget, the widest
#: any of these scenarios carried before the step was shared.
JOIN_TIMEOUT = LATE_JOINER_TIMEOUT

#: The parts the continuations of ``owner-keep-case`` act on
#: (:mod:`vultron.demo.helpers.owner_decision_story`).
VENDOR_PART = Part(VENDOR, VENDOR_LABEL)
VENDOR2_PART = Part(VENDOR2, VENDOR2_LABEL)


def vendor_seats(
    *,
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    reporter_id: str | None = None,
    vendor_id: str | None = None,
) -> tuple[CastSeat, CastSeat]:
    """The two seats the shared opening seeds, in ``seed_containers`` order.

    Only two, whatever else a scenario runs: the opening seeds the containers
    *every* sibling uses, and each further actor and peer record written
    before the case exists moves the first ledger entry away from the siblings
    this opening must match byte for byte (DEMOCI-11-018, #5532).
    """
    return (
        CastSeat(REPORTER, REPORTER_LABEL, reporter_client, reporter_id),
        CastSeat(VENDOR, VENDOR_LABEL, vendor_client, vendor_id),
    )


def open_vendor_cast(
    harness: ScenarioHarness,
    *,
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    dump: Fragment,
    reporter_id: str | None = None,
    vendor_id: str | None = None,
    unseated: Mapping[str, UnseatedContainer] | None = None,
) -> StoryState:
    """Reset this family's containers, seed its two, and return its cast.

    The opening of every vendor-first scenario: the same reset and the same
    seeding, so no scenario writes either (DEMOMA-17-001).

    Args:
        harness: The run's :class:`~vultron.demo.helpers.harness\
            .ScenarioHarness`.
        reporter_client: Client for the Reporter's container.
        vendor_client: Client for the first Vendor's container.
        case_actor_client: Client for the dedicated case-actor container.
        dump: The scenario's ledger dump, armed when the case opens.
        reporter_id: Deterministic URI for the Reporter actor, when given.
        vendor_id: Deterministic URI for the first Vendor's actor.
        unseated: Each further container the scenario will seed and seat an
            actor in, by the name it will seat it under.  Reset here with the
            rest, seeded by the fragment that brings its actor into the case
            (:class:`UnseatedContainer`).

    Returns:
        The story state the family's fragments run against.

    Raises:
        DemoStoryError: When the containers could not be seeded, so there is
            no cast to tell the story with.
    """
    return open_story_cast(
        harness,
        seats=vendor_seats(
            reporter_client=reporter_client,
            vendor_client=vendor_client,
            reporter_id=reporter_id,
            vendor_id=vendor_id,
        ),
        seed=lambda: seed_containers(
            reporter_client=reporter_client,
            vendor_client=vendor_client,
            reporter_actor_id=reporter_id,
            vendor_actor_id=vendor_id,
            case_actor_client=case_actor_client,
        ),
        seed_step="Seeding the Reporter and Vendor containers",
        case_actor_client=case_actor_client,
        dump=dump,
        unseated=unseated,
    )


def vendor_open_cast(
    *,
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    dump: Fragment,
    reporter_id: str | None = None,
    vendor_id: str | None = None,
    unseated: Mapping[str, UnseatedContainer] | None = None,
) -> Callable[[ScenarioHarness], StoryState]:
    """The ``open_cast`` callable :func:`~.story.run_story` takes.

    Every scenario of the family hands ``run_story`` the same closure over
    :func:`open_vendor_cast`, so it is built here rather than written out once
    per scenario module (DEMOMA-17-001).  The arguments are
    :func:`open_vendor_cast`'s; the harness is the one ``run_story`` enters,
    which is what puts a seeding failure inside the harness that dumps and
    reports it.

    The closure calls :func:`open_vendor_cast` rather than
    :func:`~vultron.demo.helpers.story_cast.open_story_cast` with the same
    arguments: the seats, the seeder and the step label would then exist twice
    and could drift (CS-22-001), and the opening would be reachable only
    through this factory, so a test that patches :func:`open_vendor_cast` as
    the first step of the run that can die would patch nothing
    (``test/demo/test_issue_2239_ledger_dump_in_finally.py``, DEMOMA-23-003).
    """

    def open_cast(harness: ScenarioHarness) -> StoryState:
        return open_vendor_cast(
            harness,
            reporter_client=reporter_client,
            vendor_client=vendor_client,
            case_actor_client=case_actor_client,
            dump=dump,
            reporter_id=reporter_id,
            vendor_id=vendor_id,
            unseated=unseated,
        )

    return open_cast


def dump_vendor_ledgers(state: StoryState, replicas: Sequence[str]) -> None:
    """Dump each named cast member's case ledger, and the canonical one.

    Thin wrapper (DEMOMA-23-002): the harness runs it on the way out, whether
    or not an earlier step failed.  An actor the run never seated has no
    replica to read, so it is left out rather than 404ing the dump.  Every
    scenario of this family names its actors the same on the command line, in
    ``ROLES`` and in its devlogs, so one cast name serves all three.

    Args:
        state: The running story's state.
        replicas: Whose replicas to dump, in dump order.
    """
    dump_story_ledgers(
        state, replicas=[name for name in replicas if name in state.cast]
    )


__all__ = [
    "CASE_REPLICA_TIMEOUT",
    "JOIN_TIMEOUT",
    "VENDOR",
    "VENDOR2",
    "VENDOR2_LABEL",
    "VENDOR2_PART",
    "VENDOR_LABEL",
    "VENDOR_PART",
    "VENDOR_TRIAGE_TIMEOUT",
    "dump_vendor_ledgers",
    "open_vendor_cast",
    "vendor_open_cast",
    "vendor_seats",
]
