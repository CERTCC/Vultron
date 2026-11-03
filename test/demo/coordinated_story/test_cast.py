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

"""The coordinator-first family's cast opening and its seats (#5536).

Pins :mod:`vultron.demo.helpers.coordinated_story.cast`: one reset and one
seeding for every scenario of the family, and the seats in the seeder's
return order.
"""

from unittest.mock import MagicMock, call, patch

import pytest

from test.demo._helpers import (
    mock_actor,
    mock_client,
)
from test.demo.coordinated_story._support import CAST, JOINER
from vultron.demo.helpers import story_cast
from vultron.demo.helpers.coordinated_story import (
    COORDINATOR,
    COORDINATOR_LABEL,
    REPORTER,
    REPORTER_LABEL,
    VENDOR,
    VENDOR_LABEL,
    cast as coordinated_cast,
    coordinated_seats,
    open_coordinated_cast,
)
from vultron.demo.helpers.story import (
    UnseatedContainer,
)
from vultron.errors import DemoStoryError

# ---------------------------------------------------------------------------
# The shared cast opening
# ---------------------------------------------------------------------------


class TestOpenCoordinatedCast:
    """One reset and one seeding for every scenario of the family.

    The reset and the read-back are patched on
    ``vultron.demo.helpers.story_cast``, not on this module: the opening every
    composed family shares lives there (``open_story_cast``) and this family's
    opening only supplies its seats and its seeder, so ``reset_datalayer`` and
    ``get_actor_by_id`` are resolved on ``story_cast``.  ``seed_containers_rcv``
    stays on this module, which is the only place that names it.
    """

    def test_the_reset_covers_every_container(self):
        reporter_client = mock_client()
        coordinator_client = mock_client()
        vendor_client = mock_client()
        case_actor_client = mock_client()
        actors = [mock_actor(f"urn:test:{name}") for name in CAST]

        with (
            patch.object(
                story_cast,
                "reset_datalayer",
                return_value={"status": "ok"},
            ) as reset_mock,
            patch(
                "vultron.demo.helpers.seeding.seed_case_actor_identity"
            ) as reseed,
            patch.object(
                coordinated_cast,
                "seed_containers_rcv",
                return_value=tuple(actors),
            ),
            patch.object(
                story_cast,
                "get_actor_by_id",
                side_effect=list(actors),
            ),
        ):
            state = open_coordinated_cast(
                MagicMock(),
                reporter_client=reporter_client,
                coordinator_client=coordinator_client,
                vendor_client=vendor_client,
                case_actor_client=case_actor_client,
                dump=lambda _state: None,
            )

        reset_mock.assert_has_calls(
            [
                call(client=reporter_client),
                call(client=coordinator_client),
                call(client=vendor_client),
                call(client=case_actor_client),
            ]
        )
        # The dedicated case-actor identity is re-seeded after the wipe
        # (#1876 AC-2): every proposal is addressed to it.
        reseed.assert_called_once_with(case_actor_client)
        assert sorted(state.cast) == sorted(CAST)
        assert state.client(REPORTER) is reporter_client
        assert state.case_actor_client is case_actor_client

    def test_a_character_actors_container_is_reset_but_not_seeded(self):
        """An unseated container is wiped here and seeded later (#5532).

        A run starts from a clean baseline on every container it will touch
        (DEMOMA-01-003), so the reset covers the character actor's; but every
        actor and peer record written before the case exists reads the
        recording clock, so seeding it here would move the first ledger
        entry's timestamp away from the siblings this opening must match byte
        for byte (DEMOCI-11-018).
        """
        joiner_client = mock_client()
        actors = [mock_actor(f"urn:test:{name}") for name in CAST]

        with (
            patch.object(
                story_cast,
                "reset_datalayer",
                return_value={"status": "ok"},
            ) as reset_mock,
            patch("vultron.demo.helpers.seeding.seed_case_actor_identity"),
            patch.object(
                coordinated_cast,
                "seed_containers_rcv",
                return_value=tuple(actors),
            ) as seeded,
            patch.object(
                story_cast,
                "get_actor_by_id",
                side_effect=list(actors),
            ),
        ):
            state = open_coordinated_cast(
                MagicMock(),
                reporter_client=mock_client(),
                coordinator_client=mock_client(),
                vendor_client=mock_client(),
                case_actor_client=mock_client(),
                dump=lambda _state: None,
                unseated={
                    JOINER: UnseatedContainer(
                        "Joiner", joiner_client, "urn:test:joiner"
                    )
                },
            )

        reset_mock.assert_has_calls([call(client=joiner_client)])
        assert joiner_client not in seeded.call_args.kwargs.values()
        assert JOINER not in state.cast
        assert state.container(JOINER).client is joiner_client
        assert state.container(JOINER).actor_id == "urn:test:joiner"

    def test_a_failed_seeding_leaves_no_cast_to_tell_the_story_with(self):
        """The failure is recorded by demo_step; the story stops here."""
        with (
            patch.object(story_cast, "reset_datalayer"),
            patch("vultron.demo.helpers.seeding.seed_case_actor_identity"),
            patch.object(
                coordinated_cast,
                "seed_containers_rcv",
                side_effect=RuntimeError("container unreachable"),
            ),
            pytest.raises(DemoStoryError, match="could not be seeded"),
        ):
            open_coordinated_cast(
                MagicMock(),
                reporter_client=mock_client(),
                coordinator_client=mock_client(),
                vendor_client=mock_client(),
                case_actor_client=mock_client(),
                dump=lambda _state: None,
            )


class TestCoordinatedSeats:
    """The three seats the shared opening hands ``open_story_cast``."""

    @pytest.mark.spec("DEMOMA-17-001")
    def test_the_seats_are_in_the_seeders_return_order(self):
        """Seat order is ``seed_containers_rcv``'s return order.

        ``open_story_cast`` zips the seats with what the seeder returned, so
        the order is what binds each session to its own container: a seat out
        of place would seat the Coordinator's session on the Vendor's client
        and every later fragment would act as the wrong actor.
        ``seed_containers_rcv`` returns ``(reporter, coordinator, vendor)``.
        """
        clients = {name: mock_client() for name in CAST}

        seats = coordinated_seats(
            reporter_client=clients[REPORTER],
            coordinator_client=clients[COORDINATOR],
            vendor_client=clients[VENDOR],
            reporter_id="urn:test:reporter",
            coordinator_id="urn:test:coordinator",
            vendor_id="urn:test:vendor",
        )

        assert [seat.name for seat in seats] == list(CAST), (
            "the seats must be in seed_containers_rcv's return order, which is"
            f" what binds each session to its own container; got {seats!r}"
        )
        assert [seat.label for seat in seats] == [
            REPORTER_LABEL,
            COORDINATOR_LABEL,
            VENDOR_LABEL,
        ]
        assert [seat.client for seat in seats] == [
            clients[name] for name in CAST
        ], "each seat carries its own container's client (DEMOCI-11-020)"
        assert [seat.actor_id for seat in seats] == [
            f"urn:test:{name}" for name in CAST
        ]

    def test_an_undeclared_actor_id_leaves_the_container_to_derive_one(self):
        """A run given no deterministic id passes none on (``CastSeat``)."""
        seats = coordinated_seats(
            reporter_client=mock_client(),
            coordinator_client=mock_client(),
            vendor_client=mock_client(),
        )

        assert [seat.actor_id for seat in seats] == [None, None, None], (
            "an absent --<role>-id must stay absent, so the container derives"
            f" the actor's URI itself; got {seats!r}"
        )
