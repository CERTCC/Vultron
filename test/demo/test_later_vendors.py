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

"""A vendor beyond the first threads through the shared story helpers.

``rcvv-embargo`` (DEMOMA-21) is the first scenario to seat a second vendor;
``rcvcv`` (DEMOMA-19) then seats a second coordinator and a vendor-deployer
the same way.  None of them is a parameter of the shared opening any more: a
later vendor is a **character actor**, seeded and seated mid-story
(``StoryState.seat``) and then brought into the case by
``invitee_joins_the_case``, closed by ``close_the_case`` and dumped by
``dump_coordinated_ledgers`` (#5534).

These tests pin that the second vendor is still invited, closed, covered and
dumped like the first — the properties the retired ``later_vendors`` and
``vendor_joins_coordinated_case`` parameters used to carry.  The generic
contracts of those three helpers (whether an invitee triages, how a
``(devlogs name, cast name)`` pair is read, which client each leaver acts
through) belong to ``test_coordinated_story.py``; what is pinned here is what
only a four-party case can show.
"""

from unittest.mock import MagicMock, patch

import pytest

from test.demo._helpers import mock_case, story_state, stub_closure_gate
from test.demo.test_coordinated_story import _bind_container_actors
from vultron.demo.helpers import closure, coordinated_story
from vultron.demo.helpers.coordinated_story import (
    CASE_ACTOR_NAME,
    COORDINATOR,
    REPORTER,
    VENDOR,
    close_the_case,
    dump_coordinated_ledgers,
    invitee_joins_the_case,
)
from vultron.demo.helpers.story import StoryState
from vultron.demo.utils import demo_failures, reset_demo_failures
from vultron.enums.roles import CVDRole
from vultron.errors import DemoStoryError

#: What ``rcvv-embargo`` calls its two vendors.  Vendor1 is the family's
#: Vendor, seated under the name ``rcv-embargo``'s only Vendor uses, because
#: the two scenarios share their path up to Vendor1's decision and their
#: ledgers must match there (DEMOCI-11-018).
VENDOR1 = VENDOR
VENDOR1_LABEL = "Vendor1"
VENDOR2 = "vendor2"
VENDOR2_LABEL = "Vendor2"

#: The four-party cast of a scenario with a later vendor, in roster order.
_FOUR = (REPORTER, COORDINATOR, VENDOR1, VENDOR2)


@pytest.fixture(autouse=True)
def _clean_failures():
    """Clear the process-global failure accumulator around every test.

    ``demo_gate`` skips its body once anything is recorded, so a leftover
    failure from another test would silently turn these runs into no-ops.
    """
    reset_demo_failures()
    yield
    reset_demo_failures()


class TestALaterVendorJoins:
    """The later vendor's invite chain, and the roster it must fill."""

    @pytest.mark.spec("DEMOMA-21-003")
    def test_the_roster_gate_expects_the_earlier_vendor_too(self):
        """Vendor2's join waits for a roster that still holds Vendor1.

        The roster check is the causal precondition of Vendor2's own RM
        triage, and it is read as a whole: a check that named only the joiner
        would pass on a case that had lost Vendor1 between the two joins.
        """
        state = story_state(*_FOUR, case=mock_case())

        with (
            patch.object(coordinated_story, "wait_for_case_on_container"),
            patch.object(coordinated_story, "run_case_invite_chain") as chain,
            patch.object(
                coordinated_story, "wait_for_case_participants"
            ) as roster,
            patch.object(
                coordinated_story, "run_invite_path_rm_triage"
            ) as triage,
        ):
            invitee_joins_the_case(
                state,
                VENDOR2,
                VENDOR2_LABEL,
                role=CVDRole.VENDOR,
                seated=_FOUR,
            )

        assert chain.call_args.kwargs["invitee_name"] == VENDOR2_LABEL
        assert chain.call_args.kwargs["invitee"] is state.actor(VENDOR2).actor
        assert roster.call_args.kwargs["expected_actor_ids"] == {
            state.actor_id(name) for name in _FOUR
        }
        # CM-11-002: a vendor judges the report it was invited over, so the
        # later vendor triages as the first one did.
        triage.assert_called_once()
        assert not demo_failures()


class TestALaterVendorCloses:
    """The later vendor leaves with the rest, and the owner leaves last."""

    def _close(
        self, state: StoryState
    ) -> tuple[MagicMock, MagicMock, MagicMock, MagicMock]:
        """Run ``rcvv-embargo``'s closure for real, with no store to read.

        ``close_case_owner_last`` is left unpatched — the order it sends the
        ``Leave`` triggers in is the property under test — while its reads of
        the CASE_MANAGER's store are stubbed (``stub_closure_gate``), because
        a mocked closure has no store to poll.
        """
        with (
            patch.object(closure, "ActorSession") as session_cls,
            stub_closure_gate() as gate_wait,
            patch.object(closure, "verify_case_closure_recorded") as recorded,
            patch.object(closure, "_verify_own_closure") as own_closure,
        ):
            close_the_case(
                state,
                others=(VENDOR1, REPORTER, VENDOR2),
                milestone="M7",
            )
        return session_cls, gate_wait, recorded, own_closure

    @pytest.mark.spec("DEMOMA-21-008")
    def test_the_second_vendor_closes_and_its_own_replica_is_checked(self):
        """Vendor2 sends its own ``Leave`` and verifies its own closure.

        A participant at ``RM.CLOSED`` is sent nothing after the entries
        recording its own closure (CM-23-004), so each leaver's own replica is
        the only one checked for it — the later vendor's included.
        """
        state = story_state(*_FOUR, case=mock_case())
        session_cls, _gate_wait, _recorded, own_closure = self._close(state)

        closed_by = [c.kwargs["actor"].id_ for c in session_cls.call_args_list]
        assert set(closed_by) == {state.actor_id(name) for name in _FOUR}
        # Compared by identity rather than as a set: a client stand-in is a
        # MagicMock, which is not hashable.
        checked = [c.args[0].client for c in own_closure.call_args_list]
        assert sorted(map(id, checked)) == sorted(
            id(state.client(name)) for name in _FOUR
        )
        assert not demo_failures()

    @pytest.mark.spec("CM-23-015")
    def test_the_case_owner_leaves_after_every_other_departure(self):
        """The Coordinator leaves last, the later vendor among the others.

        A ``Leave`` sent after the owner's is not recorded (CM-23-013), and a
        trigger returns 202 before its ``Leave`` commits, so the owner's own
        ``Leave`` waits on each earlier departure reading ``RM.CLOSED`` in the
        CASE_MANAGER's store (EDF-06-002).  The ledger check is then handed
        every departure in the order it was sent, the owner last.
        """
        state = story_state(*_FOUR, case=mock_case())
        session_cls, gate_wait, recorded, _own = self._close(state)

        order = [
            state.actor_id(name)
            for name in (VENDOR1, REPORTER, VENDOR2, COORDINATOR)
        ]
        closed_by = [c.kwargs["actor"].id_ for c in session_cls.call_args_list]
        assert closed_by == order
        waited_on = [c.kwargs["actor_id"] for c in gate_wait.call_args_list]
        assert waited_on == order[:-1]
        assert recorded.call_args.kwargs["departed_actor_ids"] == order


class TestALaterVendorsLedgerIsDumped:
    """The later vendor's replica is exported like every other participant's."""

    @pytest.mark.spec("DEMOMA-21-008")
    def test_the_second_vendor_is_dumped_under_its_own_devlogs_name(self):
        """Vendor2 gets its own devlogs directory, read from its own client.

        The invariant harness identifies a replica by that directory name
        (DEMOMA-19-020), and the canonical ledger is read on the dedicated
        case-actor container after the replicas (DEMOMA-06-005).

        The route key is asserted beside the name because it is the half that
        selects the store (ADR-0073): a target carrying Vendor1's key would
        export Vendor1's ledger into Vendor2's directory, and the names would
        still read correctly.  A later vendor is where that mis-pairing is
        most likely — the family's own Vendor is the one the shared opening
        seats, Vendor2 the one a continuation seeds and seats — so the
        container actors are bound as seeding binds them and the real
        ``replica_route_key`` runs, rather than keying the dump on a
        ``MagicMock`` attribute that happens to differ per client.
        """
        state = story_state(*_FOUR, case=mock_case())
        _bind_container_actors(state, *_FOUR)

        with patch.object(coordinated_story, "dump_case_ledgers") as dump:
            dump_coordinated_ledgers(state, replicas=list(_FOUR))

        targets = dump.call_args.kwargs["targets"]
        assert [t.actor_name for t in targets] == [*_FOUR, CASE_ACTOR_NAME]
        assert [t.route_key for t in targets] == [*_FOUR, CASE_ACTOR_NAME]
        by_name = {t.actor_name: t for t in targets}
        assert by_name[VENDOR2].client is state.client(VENDOR2)
        assert by_name[VENDOR1].client is state.client(VENDOR1)

    def test_dumping_a_vendor_the_run_never_seated_refuses(self):
        """A run that failed before Vendor2 joined has no replica to dump.

        Vendor2's container is reset with the rest but seeded only by the
        fragment that invites it (DEMOCI-11-018), so until then the story
        seats no such actor and there is no client to read a ledger through.
        The dump raises rather than exporting somebody else's store, which is
        why each scenario's dump wrapper filters its replica list by
        ``state.cast``.
        """
        state = story_state(
            REPORTER,
            COORDINATOR,
            VENDOR1,
            case=mock_case(),
            unseated=(VENDOR2,),
        )

        with (
            patch.object(coordinated_story, "dump_case_ledgers") as dump,
            pytest.raises(DemoStoryError, match=VENDOR2),
        ):
            dump_coordinated_ledgers(state, replicas=[REPORTER, VENDOR2])

        dump.assert_not_called()
