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

"""The vendor-first family's cast names and cast opening (#5536).

Pins :mod:`vultron.demo.helpers.vendor_story.cast`: the cast names and
budgets, the two seats the shared opening seeds (DEMOCI-11-018, #5532),
the reset/seed/seat opening, and the ledger dump the invariant harnesses
read (DEMOMA-23-002).
"""

import contextlib
from collections.abc import Iterator
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from test.demo._helpers import (
    functions_referencing,
    mock_actor,
    mock_client,
)
from test.demo.vendor_story._support import SEATED, family_state
from vultron.demo.helpers import (
    seeding,
    story_cast,
    vendor_story as family,
)
from vultron.demo.helpers.coordinated_story import (
    REPORTER,
    REPORTER_LABEL,
)
from vultron.demo.helpers.owner_decision_story import Part
from vultron.demo.helpers.polling import LATE_JOINER_TIMEOUT
from vultron.demo.helpers.story import UnseatedContainer
from vultron.demo.helpers.vendor_story import (
    cast as vendor_cast,
)
from vultron.errors import DemoStoryError

#: Clear the process-global failure accumulator around every test.
pytestmark = pytest.mark.usefixtures("fresh_demo_failures")

#: A cast name the ``rvcv`` pair brings in after the branch point, used here
#: to stand for any container the opening resets but does not seed (#5532).
_JOINER = family.VENDOR2


# ---------------------------------------------------------------------------
# The family's cast names and budgets
# ---------------------------------------------------------------------------


class TestTheFamilyCastNames:
    """One copy of each fragment serves both halves of the tree."""

    def test_the_reporter_is_seated_under_the_rcv_familys_name(self):
        """So the continuations both halves share can read it (#5536).

        The vendor-first family does not define a Reporter name of its own: it
        imports the coordinator-first family's, which is the name
        :mod:`vultron.demo.helpers.owner_decision_story` reads the Reporter
        under.
        """
        assert family.REPORTER is REPORTER
        assert family.REPORTER_LABEL is REPORTER_LABEL

    def test_each_part_pairs_a_cast_name_with_this_familys_label(self):
        """A ``Part`` is the ``(name, label)`` a shared continuation needs."""
        assert Part(family.VENDOR, "Vendor1") == family.VENDOR_PART
        assert Part(family.VENDOR2, "Vendor2") == family.VENDOR2_PART

    def test_both_vendors_are_labelled_apart_even_in_rv(self):
        """One authored opening means one label (DEMOMA-17-001).

        ``rv`` has a single Vendor, but three of the four siblings have a
        second one to tell it apart from, so the shared labels number them.
        Each scenario's own ``ROLES`` keeps its own labels, which is what the
        CLI help and the health check read.
        """
        assert (family.VENDOR_LABEL, family.VENDOR2_LABEL) == (
            "Vendor1",
            "Vendor2",
        )

    def test_every_join_of_the_family_takes_the_late_joiner_budget(self):
        """Each join reaches its actor through the CaseActor's outbox.

        A budget only bounds how long a wait may take, so taking the widest
        of the four refuses nothing a shorter one admitted and moves no byte
        of a recording (DEMOCI-11-018).
        """
        assert family.JOIN_TIMEOUT is LATE_JOINER_TIMEOUT


# ---------------------------------------------------------------------------
# The shared cast opening (DEMOCI-11-018, #5532)
# ---------------------------------------------------------------------------


class TestVendorSeats:
    """Two seats, whatever else a scenario runs."""

    def test_the_seats_are_the_two_the_opening_seeds_in_seeder_order(self):
        """The order is ``seed_containers``' return order.

        That is what binds each session to its own container
        (:func:`~vultron.demo.helpers.story_cast.open_story_cast`), so a
        swapped pair would have the Reporter's session talking to the
        Vendor's store.
        """
        reporter_client = mock_client()
        vendor_client = mock_client()

        seats = family.vendor_seats(
            reporter_client=reporter_client,
            vendor_client=vendor_client,
            reporter_id="urn:test:reporter",
            vendor_id="urn:test:vendor",
        )

        assert [(s.name, s.label) for s in seats] == [
            (REPORTER, REPORTER_LABEL),
            (family.VENDOR, family.VENDOR_LABEL),
        ]
        assert [s.client for s in seats] == [reporter_client, vendor_client]
        assert [s.actor_id for s in seats] == [
            "urn:test:reporter",
            "urn:test:vendor",
        ]

    @pytest.mark.spec("DEMOCI-11-018")
    def test_only_the_cast_opening_seeds_this_familys_containers(self):
        """Nothing a fragment reaches may seed before the case exists.

        Every actor and peer record written then is one more read of the
        recording clock, so a second call site — in particular one reachable
        from a fragment — is how the four recordings would drift apart
        (#5532).  Read from the source, so the claim holds for the code as
        written and not only for the path a test drives.

        The two cast-opening entry points are named as a set rather than a
        list: whether the ``open_cast`` closure seeds through
        :func:`~vultron.demo.helpers.vendor_story.open_vendor_cast` or
        repeats its arguments is a question of duplication, not of when the
        seeding runs, and both answers satisfy this rule.
        """
        seeders = functions_referencing(family, "seed_containers")

        assert seeders, (
            "the source walk found no caller of the seeding — the check is"
            " vacuous"
        )
        assert set(seeders) <= {"open_vendor_cast", "vendor_open_cast"}, (
            "only the cast opening may seed this family's containers;"
            f" {sorted(set(seeders) - {'open_vendor_cast', 'vendor_open_cast'})}"
            " also does (DEMOCI-11-018, #5532)"
        )


@contextlib.contextmanager
def _cast_stubs(seeded, *, seed_error=None) -> Iterator[SimpleNamespace]:
    """Stub the container reset, the seeding and the actor read-back.

    ``open_vendor_cast`` delegates to
    :func:`~vultron.demo.helpers.story_cast.open_story_cast`, so the reset and
    the read-back are looked up on **that** module while the seeder closure
    is looked up on ``vendor_story.cast``: patching all three on one module
    would
    stub nothing the code under test calls.
    """
    with (
        patch.object(
            story_cast, "reset_datalayer", return_value={"status": "ok"}
        ) as reset,
        patch.object(seeding, "seed_case_actor_identity") as reseed,
        patch.object(
            story_cast, "get_actor_by_id", side_effect=list(seeded)
        ) as lookup,
        patch.object(
            vendor_cast,
            "seed_containers",
            return_value=tuple(seeded),
            side_effect=seed_error,
        ) as seed,
    ):
        yield SimpleNamespace(
            reset=reset, reseed=reseed, lookup=lookup, seed=seed
        )


class TestOpenVendorCast:
    """One reset and one seeding for every scenario of the family."""

    @pytest.mark.spec("DEMOMA-01-003")
    def test_the_reset_covers_every_container_and_reseeds_the_case_actor(self):
        """A run starts clean on every container it will touch.

        The unseated ones included: they are reset here and seeded later
        (#5532).  The dedicated case-actor container is reset last and its
        CaseActor identity re-seeded, because the wipe clears it and every
        proposal is addressed to it (#1876 AC-2, DEMOMA-06-004).
        """
        reporter_client = mock_client()
        vendor_client = mock_client()
        case_actor_client = mock_client()
        joiner_client = mock_client()
        seeded = [mock_actor(f"urn:test:{name}") for name in SEATED]

        with _cast_stubs(seeded) as stubs:
            family.open_vendor_cast(
                MagicMock(),
                reporter_client=reporter_client,
                vendor_client=vendor_client,
                case_actor_client=case_actor_client,
                dump=lambda _state: None,
                unseated={
                    _JOINER: UnseatedContainer(
                        family.VENDOR2_LABEL, joiner_client, "urn:test:vendor2"
                    )
                },
            )

        assert [c.kwargs["client"] for c in stubs.reset.call_args_list] == [
            reporter_client,
            vendor_client,
            joiner_client,
            case_actor_client,
        ]
        stubs.reseed.assert_called_once_with(case_actor_client)

    @pytest.mark.spec("DEMOCI-11-018")
    def test_only_the_two_seats_are_seeded_and_the_rest_wait(self):
        """The opening seeds the containers *every* sibling uses.

        A further actor's container is left as an
        :class:`~vultron.demo.helpers.story.UnseatedContainer` with its
        deterministic id, for the fragment that brings that actor into the
        case (#5532).
        """
        reporter_client = mock_client()
        vendor_client = mock_client()
        case_actor_client = mock_client()
        joiner_client = mock_client()
        seeded = [mock_actor(f"urn:test:{name}") for name in SEATED]

        with _cast_stubs(seeded) as stubs:
            state = family.open_vendor_cast(
                MagicMock(),
                reporter_client=reporter_client,
                vendor_client=vendor_client,
                case_actor_client=case_actor_client,
                dump=lambda _state: None,
                reporter_id="urn:test:reporter",
                vendor_id="urn:test:vendor",
                unseated={
                    _JOINER: UnseatedContainer(
                        family.VENDOR2_LABEL, joiner_client, "urn:test:vendor2"
                    )
                },
            )

        kwargs = stubs.seed.call_args.kwargs
        assert kwargs["reporter_client"] is reporter_client
        assert kwargs["vendor_client"] is vendor_client
        assert kwargs["case_actor_client"] is case_actor_client
        assert kwargs["reporter_actor_id"] == "urn:test:reporter"
        assert kwargs["vendor_actor_id"] == "urn:test:vendor"
        assert joiner_client not in kwargs.values(), (
            "a container only some siblings use must not be seeded by the"
            " shared opening (DEMOCI-11-018, #5532)"
        )
        # Each seeded actor is read back from its own container, which is the
        # form a trigger session binds to (ADR-0073).
        assert [c.args[0] for c in stubs.lookup.call_args_list] == [
            reporter_client,
            vendor_client,
        ]
        assert sorted(state.cast) == sorted(SEATED)
        assert state.case_actor_client is case_actor_client
        assert _JOINER not in state.cast
        assert state.container(_JOINER).client is joiner_client
        assert state.container(_JOINER).actor_id == "urn:test:vendor2"

    def test_a_failed_seeding_leaves_no_cast_to_tell_the_story_with(self):
        """The failure is recorded by ``demo_step``; the story stops here."""
        seeded = [mock_actor(f"urn:test:{name}") for name in SEATED]

        with (
            _cast_stubs(seeded, seed_error=RuntimeError("unreachable")),
            pytest.raises(DemoStoryError, match="could not be seeded"),
        ):
            family.open_vendor_cast(
                MagicMock(),
                reporter_client=mock_client(),
                vendor_client=mock_client(),
                case_actor_client=mock_client(),
                dump=lambda _state: None,
            )

    def test_the_open_cast_closure_opens_the_same_cast(self):
        """``run_story`` takes a closure, so the harness is bound late.

        Every scenario of the family hands ``run_story`` the same one, which
        is what puts a seeding failure inside the harness that dumps and
        reports it (DEMOMA-17-001).
        """
        reporter_client = mock_client()
        vendor_client = mock_client()
        case_actor_client = mock_client()
        seeded = [mock_actor(f"urn:test:{name}") for name in SEATED]
        harness = MagicMock()

        with _cast_stubs(seeded) as stubs:
            open_cast = family.vendor_open_cast(
                reporter_client=reporter_client,
                vendor_client=vendor_client,
                case_actor_client=case_actor_client,
                dump=lambda _state: None,
            )
            # Nothing is reset or seeded until ``run_story`` calls it.
            stubs.reset.assert_not_called()
            stubs.seed.assert_not_called()
            state = open_cast(harness)

        assert state.harness is harness
        assert sorted(state.cast) == sorted(SEATED)
        assert state.client(REPORTER) is reporter_client
        assert state.client(family.VENDOR) is vendor_client


# ---------------------------------------------------------------------------
# The devlogs the invariant harnesses read (DEMOMA-23-002)
# ---------------------------------------------------------------------------


class TestDumpVendorLedgers:
    """Each replica is dumped under the cast name the harness loads."""

    def _dump(self, state, replicas):
        for name in state.cast:
            state.client(name).actor_id = f"http://{name}:7999/actors/{name}"
        state.case_actor_client.actor_id = (
            "http://case-actor:7999/actors/case-actor"
        )
        with patch.object(story_cast, "dump_case_ledgers") as dump:
            family.dump_vendor_ledgers(state, replicas)
        return dump.call_args.kwargs["targets"]

    def test_every_seated_replica_is_dumped_plus_the_canonical_ledger(self):
        """One cast name serves all four: each names its actors the same.

        The canonical ledger is read on the dedicated case-actor container,
        never from a participant's replica (DEMOMA-06-005).
        """
        state = family_state(family.VENDOR2)
        targets = self._dump(state, (REPORTER, family.VENDOR, family.VENDOR2))

        assert [t.actor_name for t in targets] == [
            REPORTER,
            family.VENDOR,
            family.VENDOR2,
            "case-actor",
        ]
        assert targets[-1].client is state.case_actor_client

    @pytest.mark.spec("DEMOMA-23-003")
    def test_a_cast_name_the_run_never_seated_is_left_out(self):
        """A failure before the seeding must not 404 the dump.

        The dump runs on the way out whether or not an earlier step failed,
        and an unseated container holds no replica to read — so the name is
        dropped rather than dumped as an error.
        """
        state = family_state()
        targets = self._dump(
            state, (REPORTER, family.VENDOR, "coordinator", family.VENDOR2)
        )

        assert [t.actor_name for t in targets] == [
            REPORTER,
            family.VENDOR,
            "case-actor",
        ]
