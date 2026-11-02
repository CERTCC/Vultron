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

"""The reset-seed-seat opening every composed story family shares (#5536).

``vultron.demo.helpers.story_cast`` is the extraction the vendor-first family
forced: a second family would otherwise have copied the first one's opening
(DEMOMA-17-001, CS-22-001).  What it owns is the part no family may differ in
— every container the run touches is wiped, the dedicated case-actor identity
is re-seeded after the wipe (#1876 AC-2), only the fixed-role seats are
seeded, and each seeded actor is read back from *its own* container before a
session is bound to it.  Those are the claims below; a family's own seats and
seeder are its business and are pinned in its own module's tests
(``test_coordinated_story.py``, ``test_vendor_story.py``).

Every test patches the collaborators out, so no HTTP happens.  ``demo_step``
is left real wherever the test is about control flow — a seeding failure is
recorded by ``demo_step`` and *that* is what turns into the stop — and
recorded or stubbed only where the test is about the label it carries.

These tests are mock-only, yet they live here rather than in
``test/demo_unit/`` — and so are auto-marked ``integration`` — because the
ledger-rebuild guard in this directory's ``conftest.py`` runs on the way out,
as it does for every other test of a story helper.
"""

import contextlib
from collections.abc import Iterator, Sequence
from unittest.mock import MagicMock, patch

import pytest

from test.demo._helpers import mock_actor, mock_client
from vultron.demo.helpers import story_cast
from vultron.demo.helpers.story import UnseatedContainer
from vultron.demo.helpers.story_cast import (
    CastSeat,
    open_story_cast,
)
from vultron.demo.utils import reset_demo_failures
from vultron.errors import DemoStoryError
from vultron.wire.as2.vocab.base.objects.actors import as_Actor

#: The two fixed-role seats a vendor-first family opens with, as the smallest
#: cast that can still be seated in the wrong order (``vendor_seats``).
_SEATS = ("reporter", "vendor")

#: The cast name of a character actor whose container is reset here and seeded
#: by the fragment that brings it into the case (#5532).
_JOINER = "joiner"

#: The seeding step's label, which the opening is *told* rather than owning:
#: each family names its own seeder in it.
_SEED_STEP = "Seeding the Reporter and Vendor containers"


@pytest.fixture(autouse=True)
def _fresh_failures() -> Iterator[None]:
    """Clear the process-global failure accumulator around every test.

    ``vultron.demo.utils._demo_failures`` is process-global, and the failed
    seeding below records one, which the next test would read as its own.
    """
    reset_demo_failures()
    yield
    reset_demo_failures()


def _seats(*names: str) -> tuple[CastSeat, ...]:
    """One seat per name, each with its own client and deterministic id."""
    return tuple(
        CastSeat(name, name.capitalize(), mock_client(), f"urn:test:{name}")
        for name in names
    )


def _seeded(seats: Sequence[CastSeat]) -> list[MagicMock]:
    """The actors a seeder returns for *seats*, in seat order."""
    return [mock_actor(f"urn:test:{seat.name}") for seat in seats]


def _waiting(client: MagicMock) -> dict[str, UnseatedContainer]:
    """The one unseated container a scenario with a character actor declares."""
    return {_JOINER: UnseatedContainer("Joiner", client, "urn:test:joiner")}


@contextlib.contextmanager
def _opening(
    seeded: Sequence[as_Actor] | None,
    *,
    read_back: object = None,
) -> Iterator[MagicMock]:
    """Stub the opening's container collaborators; yield a call recorder.

    The reset and the case-actor re-seed are bound to one parent mock so a
    test can read their order off ``mock_calls`` (#1876 AC-2).  *seeded* is
    what the seeder closure returns, and *read_back* the ``get_actor_by_id``
    stand-in; the default returns a fresh actor per call, so a session bound
    to another container's actor is visible.
    """
    recorder = MagicMock()
    recorder.reset_datalayer.return_value = {"status": "ok"}
    with (
        patch.object(story_cast, "reset_datalayer", recorder.reset_datalayer),
        patch(
            "vultron.demo.helpers.seeding.seed_case_actor_identity",
            recorder.seed_case_actor_identity,
        ),
        patch.object(
            story_cast,
            "get_actor_by_id",
            read_back if read_back is not None else recorder.get_actor_by_id,
        ),
    ):
        recorder.seed.return_value = seeded
        yield recorder


class TestOpenStoryCast:
    """One reset, one seeding and one seating for every composed family."""

    def test_the_reset_covers_every_container_then_reseeds_the_case_actor(
        self,
    ):
        """Every container the run touches, the unseated one included.

        A run must start from a clean baseline on every container it will
        touch (DEMOMA-01-003), and the dedicated case-actor container is wiped
        with them — which destroys the CaseActor identity every proposal is
        addressed to, so it is re-created *after* the wipe and not before
        (#1876 AC-2, DEMOMA-06-004).
        """
        seats = _seats(*_SEATS)
        waiting_client = mock_client()
        case_actor_client = mock_client()

        with _opening(_seeded(seats)) as recorder:
            open_story_cast(
                MagicMock(),
                seats=seats,
                seed=recorder.seed,
                seed_step=_SEED_STEP,
                case_actor_client=case_actor_client,
                dump=lambda _state: None,
                unseated=_waiting(waiting_client),
            )

        reset = [
            c.kwargs["client"] for c in recorder.reset_datalayer.call_args_list
        ]
        assert reset == [
            seats[0].client,
            seats[1].client,
            waiting_client,
            case_actor_client,
        ], (
            "the reset must cover every seat, every unseated container and the"
            f" case-actor container (DEMOMA-01-003); it covered {reset!r}"
        )
        names = [name for name, _args, _kwargs in recorder.mock_calls]
        assert names.index("seed_case_actor_identity") > names.index(
            "reset_datalayer"
        ), (
            "the CaseActor identity must be re-seeded after the wipe that"
            f" destroyed it (#1876 AC-2); the calls ran {names!r}"
        )
        recorder.seed_case_actor_identity.assert_called_once_with(
            case_actor_client
        )

    def test_only_the_seats_are_seeded_inside_the_step_it_is_told(self):
        """The seeder is a closure, run inside the label the family named.

        The opening cannot know what a family's ``seed_containers_*`` is
        called, so it takes both the closure and the ``demo_step`` label.  The
        closure is called with nothing, which is what makes "only the seats
        are seeded" structural: there is no argument an unseated container
        could arrive through.
        """
        seats = _seats(*_SEATS)
        waiting_client = mock_client()
        order: list[str] = []
        handed: list[tuple[tuple[object, ...], dict[str, object]]] = []

        @contextlib.contextmanager
        def _step(label: str) -> Iterator[None]:
            order.append(f"enter {label}")
            yield
            order.append(f"exit {label}")

        def _seed(*args: object, **kwargs: object) -> list[MagicMock]:
            handed.append((args, kwargs))
            order.append("seed")
            return _seeded(seats)

        with (
            _opening(None),
            patch.object(story_cast, "demo_step", side_effect=_step),
        ):
            state = open_story_cast(
                MagicMock(),
                seats=seats,
                seed=_seed,
                seed_step=_SEED_STEP,
                case_actor_client=mock_client(),
                dump=lambda _state: None,
                unseated=_waiting(waiting_client),
            )

        assert order == [
            f"enter {_SEED_STEP}",
            "seed",
            f"exit {_SEED_STEP}",
        ], (
            "the seeding must run inside a demo_step carrying the label the"
            f" family named, so its failure is recorded; the run went {order!r}"
        )
        assert handed == [((), {})], (
            "the seeder is a no-argument closure, so no container can reach it"
            f" but the ones it closed over; it was handed {handed!r}"
        )
        assert sorted(state.cast) == sorted(_SEATS), (
            "only the seats are seated by the opening (DEMOCI-11-018, #5532);"
            f" it seated {sorted(state.cast)}"
        )

    def test_each_actor_is_read_back_from_its_own_container(self):
        """A session is bound to the actor its *own* container stores.

        The read-back is the form a trigger session binds to, and it is
        per-container: reading the Vendor's actor through the Reporter's
        client would bind the Vendor's session to the Reporter's container and
        every later fragment would act as the wrong actor.  The stand-in
        returns a distinct object per call, so a crossed pairing shows.
        """
        seats = _seats(*_SEATS)
        reads: list[tuple[object, str]] = []

        def _read_back(client: object, actor_id: str) -> MagicMock:
            reads.append((client, actor_id))
            return mock_actor(f"{actor_id}#as-stored")

        with _opening(_seeded(seats), read_back=_read_back) as recorder:
            state = open_story_cast(
                MagicMock(),
                seats=seats,
                seed=recorder.seed,
                seed_step=_SEED_STEP,
                case_actor_client=mock_client(),
                dump=lambda _state: None,
            )

        assert reads == [
            (seat.client, f"urn:test:{seat.name}") for seat in seats
        ], (
            "each seeded actor must be read back through its own seat's"
            f" client, in seat order; the reads were {reads!r}"
        )
        for seat in seats:
            session = state.cast[seat.name]
            assert session.client is seat.client, (
                f"the {seat.name!r} session must be bound to its own"
                " container, or a trigger would run against another replica"
            )
            assert session.actor.id_ == f"urn:test:{seat.name}#as-stored", (
                "the session must carry the actor as its container stores it,"
                f" not as the seeder returned it; it carries {session.actor!r}"
            )

    def test_a_failed_seeding_leaves_no_cast_to_tell_the_story_with(self):
        """``demo_step`` records the failure; the opening then stops.

        The seeder returns ``None`` because its ``demo_step`` swallowed and
        recorded the failure, so there is nothing to raise by the time the
        opening looks.  It must stop anyway: a ``StoryState`` with an empty
        cast would let the first fragment fail again on every actor it reads,
        burying the one real cause (EDF-06-005).
        """
        seats = _seats(*_SEATS)
        from vultron.demo import utils

        with (
            _opening(None) as recorder,
            pytest.raises(DemoStoryError) as raised,
        ):
            recorder.seed.side_effect = RuntimeError("container unreachable")
            open_story_cast(
                MagicMock(),
                seats=seats,
                seed=recorder.seed,
                seed_step=_SEED_STEP,
                case_actor_client=mock_client(),
                dump=lambda _state: None,
            )

        message = str(raised.value)
        assert "could not be seeded" in message
        assert "no cast" in message, (
            "the stop must say the story has no cast to run on, which is why"
            f" it stops rather than failing per fragment; it said {message!r}"
        )
        for seat in seats:
            assert seat.label in message, (
                "the stop must name the containers whose seeding failed, so a"
                f" reader knows where to look; it named {message!r}"
            )
        assert any(
            "container unreachable" in f for f in utils._demo_failures
        ), (
            "the real cause must still be in the accumulator, recorded by the"
            f" seeding's own demo_step; it holds {utils._demo_failures!r}"
        )

    @pytest.mark.parametrize("extra", [-1, 1])
    def test_a_seeder_that_miscounts_binds_no_session(self, extra: int):
        """A count mismatch is refused before any session is bound.

        The seats and the seeded actors are paired by position, so a seeder
        returning the wrong number would seat a session on another
        container's actor — or, with ``strict=True``, raise ``ValueError``
        from ``zip`` and report the arity of a comprehension rather than the
        contract that was broken.  Expecting ``DemoStoryError`` is what makes
        this test fail if the explicit length check is removed: ``zip`` would
        then raise ``ValueError``, which this does not catch.
        """
        seats = _seats(*_SEATS)
        miscounted = _seeded(seats)
        if extra > 0:
            miscounted.append(mock_actor("urn:test:extra"))
        else:
            miscounted.pop()

        with (
            _opening(miscounted) as recorder,
            pytest.raises(DemoStoryError) as raised,
        ):
            open_story_cast(
                MagicMock(),
                seats=seats,
                seed=recorder.seed,
                seed_step=_SEED_STEP,
                case_actor_client=mock_client(),
                dump=lambda _state: None,
            )

        message = str(raised.value)
        assert f"returned {len(miscounted)} actors" in message
        assert f"{len(seats)} cast seats" in message, (
            "the stop must report both counts, so a reader can see which side"
            f" drifted; it said {message!r}"
        )
        recorder.get_actor_by_id.assert_not_called()

    def test_an_unseated_container_is_left_waiting_with_its_own_details(self):
        """Reset with the rest, seeded by the fragment that needs it (#5532).

        A character actor's container cannot be seeded here: every actor and
        peer record written before the case exists reads the recording clock,
        so it would move the first ledger entry away from the siblings this
        opening must match byte for byte (DEMOCI-11-018).  It is handed on
        whole — label, client and deterministic id — because the fragment that
        seeds it needs all three.
        """
        seats = _seats(*_SEATS)
        waiting_client = mock_client()

        with _opening(_seeded(seats)) as recorder:
            state = open_story_cast(
                MagicMock(),
                seats=seats,
                seed=recorder.seed,
                seed_step=_SEED_STEP,
                case_actor_client=mock_client(),
                dump=lambda _state: None,
                unseated=_waiting(waiting_client),
            )

        assert _JOINER not in state.cast, (
            "an unseated container's actor is seated by the fragment that"
            " brings it into the case, not by the opening (#5532)"
        )
        pending = state.container(_JOINER)
        assert pending.label == "Joiner"
        assert pending.client is waiting_client
        assert pending.actor_id == "urn:test:joiner", (
            "the deterministic id must survive the opening, or the fragment"
            f" that seeds the actor would derive another; it holds {pending!r}"
        )
        read = [c.args[0] for c in recorder.get_actor_by_id.call_args_list]
        assert waiting_client not in read, (
            "nothing is read back from a container whose actor does not exist"
            " yet"
        )

    def test_the_declared_containers_are_copied_not_shared(self):
        """The state's ``unseated`` is the opening's own dict.

        ``StoryState.seat`` deletes the name it seats, so a state sharing the
        caller's mapping would mutate a module-level declaration and the
        second run of a scenario would find its character actor already
        seated.
        """
        seats = _seats(*_SEATS)
        declared = _waiting(mock_client())

        with _opening(_seeded(seats)) as recorder:
            state = open_story_cast(
                MagicMock(),
                seats=seats,
                seed=recorder.seed,
                seed_step=_SEED_STEP,
                case_actor_client=mock_client(),
                dump=lambda _state: None,
                unseated=declared,
            )

        assert state.unseated is not declared
        assert state.unseated == declared
