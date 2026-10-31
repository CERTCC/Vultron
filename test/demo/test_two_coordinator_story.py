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

"""Unit tests for the two-coordinator pair's shared story (#5535).

``rccv-extension`` and ``rccv-handoff`` tell one story up to a single
decision, and :mod:`vultron.demo.helpers.two_coordinator_story` is that one
copy of the code: the named prefix :data:`C1_INVITES_C2`, which continues the
rcv family's ``REPORTER_TELLS_THE_COORDINATOR``, plus every continuation both
scenarios tell afterwards (DEMOMA-13-012, DEMOMA-14-017, DEMOMA-17-001).

The tests here own what the pair shares; each scenario's own module owns its
own fragments, and ``test_coordinated_story.py`` owns the rcv family's
opening, which this prefix only names.  Every test patches the collaborators
out, so no HTTP happens; ``demo_gate`` / ``demo_check`` / ``demo_step`` stay
real wherever the test is about control flow and are stubbed to
``nullcontext`` only where it is about call shape.
"""

import contextlib
import pathlib
from unittest.mock import MagicMock, patch

import pytest

import vultron.demo.helpers.two_coordinator_story as pair
import vultron.demo.utils as demo_utils
from test.demo._helpers import (
    devlogs_name_of,
    functions_referencing,
    mock_actor,
    mock_case,
    no_demo_banners,
    patch_chain_shared,
    story_state,
)
from vultron.core.states.cs import CS_vf
from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers import coordinated_story, owner_decision_story
from vultron.demo.helpers.actor_roles import case_actor_role, role_kwarg_names
from vultron.demo.helpers.cast import (
    CAST,
    COORDINATOR_SLOT,
    REPORTER_SLOT,
    VENDOR_SLOT,
)
from vultron.demo.helpers.coordinated_story import (
    COORDINATOR,
    REPORTER,
    REPORTER_TELLS_THE_COORDINATOR,
    VENDOR,
)
from vultron.demo.helpers.notes import (
    WORKAROUND_ANSWER,
    WORKAROUND_QUESTION,
    NotePost,
)
from vultron.demo.helpers.owner_decision_story import Part
from vultron.demo.helpers.story import Choose, UnseatedContainer
from vultron.demo.utils import reset_demo_failures
from vultron.enums.roles import CVDRole
from vultron.errors import DemoStoryError

#: The pair's four cast names, in ``ROLES`` order.
_CAST = (REPORTER, pair.C1, pair.C2, VENDOR)

#: How many items of :data:`C1_INVITES_C2` are the rcv family's own opening.
_RCV_PREFIX_LEN = len(REPORTER_TELLS_THE_COORDINATOR.items)


@pytest.fixture(autouse=True)
def _fresh_failures():
    """Clear the process-global failure accumulator around every test.

    ``vultron.demo.utils._demo_failures`` is process-global, so a fragment
    that records a failure would otherwise leave it for the next test to read
    as its own (``notes/testing-pitfalls.md``).
    """
    reset_demo_failures()
    yield
    reset_demo_failures()


@contextlib.contextmanager
def _no_banners():
    """Every module a fragment of this pair reaches, patched once.

    ``owner_decision_story`` is not among them: this pair's module takes
    only ``Part`` and a timeout from it, so no fragment under test opens a
    banner there (``test_owner_decision_story.py`` owns those).
    """
    with no_demo_banners(pair, coordinated_story):
        yield


def _four_party_state():
    """A story state seating all four, on an open case."""
    return story_state(*_CAST, case=mock_case())


def _sessions_of(mock_method) -> list[str]:
    """The actor id of each session an ``autospec``-ed verb was called on."""
    return [call.args[0].actor.id_ for call in mock_method.call_args_list]


# ---------------------------------------------------------------------------
# The named prefix (DEMOMA-13-012, DEMOMA-14-017, DEMOCI-11-018)
# ---------------------------------------------------------------------------


class TestC1InvitesC2Prefix:
    """``C1_INVITES_C2`` is the pair's one authored opening."""

    def test_the_prefix_starts_with_the_rcv_familys_own_opening(self):
        """Identity of the shared stretch, not a matching sequence.

        All four coordinator-first scenarios share one copy of the report
        submission and C1's triage, which is what makes their recordings
        byte-identical up to ``coordinator-invite-whom`` (DEMOCI-11-018).
        Comparing against ``REPORTER_TELLS_THE_COORDINATOR.items`` is what
        stops this pair slipping a step in before that branch point.
        """
        assert (
            pair.C1_INVITES_C2.items[:_RCV_PREFIX_LEN]
            == REPORTER_TELLS_THE_COORDINATOR.items
        )
        # Identity only: ``Choose`` is a frozen dataclass, so a hand-copied
        # duplicate would compare equal.
        for mine, theirs in zip(
            pair.C1_INVITES_C2.items[:_RCV_PREFIX_LEN],
            REPORTER_TELLS_THE_COORDINATOR.items,
            strict=True,
        ):
            assert mine is theirs

    def test_the_prefix_parts_from_the_rcv_family_at_the_coordinators_choice(
        self,
    ):
        """This pair invites a Coordinator where ``rcv`` invites the Vendor."""
        branch = pair.C1_INVITES_C2.items[_RCV_PREFIX_LEN]
        assert branch == Choose(
            branch_point="coordinator-invite-whom",
            choice="coordinator",
            by=COORDINATOR,
        )
        assert (
            coordinated_story.COORDINATOR_INVITES_VENDOR.items[_RCV_PREFIX_LEN]
            != branch
        ), (
            "the two-coordinator pair and the rcv family must take different"
            " choices at coordinator-invite-whom, or they are one scenario"
        )

    def test_the_prefix_runs_the_declared_order_and_stops_at_the_join(self):
        """One assertion for the whole prefix, so a reordering shows.

        The order is load-bearing: C2 is seeded after the branch point
        (DEMOCI-11-018), and the prefix ends with C2's join, which is the
        owner's decision's precondition (DEMOMA-13-003, DEMOMA-14-010).
        """
        assert pair.C1_INVITES_C2.items == (
            *REPORTER_TELLS_THE_COORDINATOR.items,
            Choose(
                branch_point="coordinator-invite-whom",
                choice="coordinator",
                by=COORDINATOR,
            ),
            pair.c2_is_seeded,
            pair.c1_invites_c2,
        )

    def test_the_prefix_walks_the_two_steps_both_scenarios_declare(self):
        """The path is read off the choices, not typed beside them."""
        assert pair.C1_INVITES_C2.path == (
            ("reporter-whom-to-tell", "coordinator"),
            ("coordinator-invite-whom", "coordinator"),
        )

    def test_c1_and_the_vendor_are_seated_under_the_family_role_names(self):
        """One copy of the rcv opening serves ``rcv`` and this pair alike."""
        assert pair.C1 == COORDINATOR
        assert pair.VENDOR_PART.name == VENDOR
        # The CLI and the devlogs keep the pair's own name for C1.
        assert pair.C1_ROLE == "c1"
        assert pair.C1_ROLE != pair.C1


# ---------------------------------------------------------------------------
# C2 is seeded after the branch point (DEMOCI-11-018, #5532)
# ---------------------------------------------------------------------------


class TestC2IsSeededAfterTheBranchPoint:
    """C2 is seeded by the fragment that brings it into the case.

    Every actor and peer record written before the case exists is one more
    read of the recording clock, so seeding C2 in the shared opening would
    move the first ledger entry's timestamp away from ``rcv``'s and break the
    byte identity of the shared stretch (DEMOCI-11-018, #5532).
    """

    def test_the_seeding_fragment_is_the_only_caller_of_the_seeding(self):
        """Nothing else in the module may seed the four containers.

        A second call site — in particular one reachable from the rcv
        family's opening — is how the recording would drift again.
        """
        assert functions_referencing(pair, "seed_containers_rccv") == [
            "c2_is_seeded"
        ]

    def test_the_seeding_fragment_follows_the_coordinators_choice(self):
        """It is placed after the ``coordinator-invite-whom`` choice."""
        items = pair.C1_INVITES_C2.items
        branch = items.index(
            Choose(
                branch_point="coordinator-invite-whom",
                choice="coordinator",
                by=COORDINATOR,
            )
        )
        seeding = items.index(pair.c2_is_seeded)
        assert branch < seeding, (
            "c2_is_seeded must run after C1's choice: every record it writes"
            " before the case opens moves the first ledger entry's timestamp"
            " (DEMOCI-11-018)"
        )
        assert seeding >= _RCV_PREFIX_LEN, (
            "the rcv family's opening must not reach the four-party seeding"
        )

    def test_the_fragment_seeds_all_four_then_seats_c2(self):
        """The three already seeded are re-seeded idempotently.

        ``seed_containers_rccv`` registers every actor as a peer of the other
        three (DEMOMA-13-001, DEMOMA-14-001), which needs all four clients;
        ``POST /actors/`` and the peer registrations are idempotent, so the
        three the rcv opening seeded come back unchanged.
        """
        state = story_state(REPORTER, pair.C1, VENDOR, unseated=(pair.C2,))
        seeded = tuple(mock_actor(f"urn:test:{name}") for name in _CAST)
        # The waiting container is consumed by the seating, so hold it.
        waiting = state.container(pair.C2)

        with (
            patch.object(
                pair, "seed_containers_rccv", return_value=seeded
            ) as seed,
            patch.object(
                coordinated_story,
                "get_actor_by_id",
                side_effect=[seeded[2]],
            ) as lookup,
            _no_banners(),
        ):
            pair.c2_is_seeded(state)

        kwargs = seed.call_args.kwargs
        assert kwargs["reporter_client"] is state.client(REPORTER)
        assert kwargs["c1_client"] is state.client(pair.C1)
        assert kwargs["vendor_client"] is state.client(VENDOR)
        assert kwargs["c2_client"] is waiting.client
        assert kwargs["case_actor_client"] is state.case_actor_client
        # The deterministic id comes from the waiting container, which holds
        # the --c2-id value the run was given.
        assert kwargs["c2_actor_id"] == "urn:test:c2"

        # The new actor is read back from its own container (ADR-0073).
        assert [c.args[0] for c in lookup.call_args_list] == [
            state.client(pair.C2)
        ]
        assert state.unseated == {}
        assert state.actor_id(pair.C2) == "urn:test:c2"

    def test_a_container_that_was_never_declared_stops_the_story(self):
        """Seating reads the container the scenario declared, or raises."""
        state = story_state(REPORTER, pair.C1, VENDOR)

        with (
            patch.object(pair, "seed_containers_rccv"),
            patch.object(coordinated_story, "get_actor_by_id"),
            _no_banners(),
            pytest.raises(DemoStoryError, match="no container waiting"),
        ):
            pair.c2_is_seeded(state)


# ---------------------------------------------------------------------------
# C2 joins as a coordinator and the roster is the owner's decision's gate
# ---------------------------------------------------------------------------


class TestC1InvitesC2:
    """C2's join is one invite chain, with no triage and a keeping gate."""

    def _invite(self, state, *, run_then: bool = False, roster=None):
        """Run the fragment with the shared invite chain stubbed out.

        With *run_then* the chain's ``then`` callback is run while the
        collaborators are still patched, which is how a non-triaging
        invitee's roster gate is reached.  ``demo_gate`` stays real there, so
        a failing roster records its failure and keeps no prop.
        """
        with (
            patch.object(coordinated_story, "run_case_invite_chain") as chain,
            patch.object(
                coordinated_story, "run_invite_path_rm_triage"
            ) as triage,
            patch.object(
                coordinated_story,
                "wait_for_case_participants",
                side_effect=roster,
            ) as roster_wait,
            patch_chain_shared(
                coordinated_story, "wait_for_case_on_container"
            ) as replica_wait,
            patch.object(
                coordinated_story,
                "demo_check",
                side_effect=lambda _: contextlib.nullcontext(),
            ),
            patch.object(
                coordinated_story,
                "demo_step",
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            pair.c1_invites_c2(state)
            then = chain.call_args.kwargs["then"]
            assert then is not None, (
                "a non-triaging invitee's roster gate runs as the chain's"
                " `then`, inside its delivery gate"
            )
            # Nothing has checked the roster yet: the gate is the chain's to
            # run, so a failed invite skips it.
            roster_wait.assert_not_called()
            if run_then:
                then()
        return chain, triage, roster_wait, replica_wait

    def test_the_invite_offers_the_coordinator_role_from_c1(self):
        """C1, the Case Owner, invites C2 as ``CVDRole.COORDINATOR``.

        C2 holds COORDINATOR and never CASE_MANAGER, which stays with the
        CaseActor (DEMOMA-13-003).
        """
        state = _four_party_state()
        chain, _, _, _ = self._invite(state)

        kwargs = chain.call_args.kwargs
        assert kwargs["invitee_name"] == pair.C2_LABEL
        assert kwargs["invitee_client"] is state.client(pair.C2)
        assert kwargs["invitee"] is state.actor(pair.C2).actor
        assert kwargs["inviter"].client is state.client(pair.C1)
        assert kwargs["inviter"].role is CVDRole.COORDINATOR
        # The CASE_MANAGER's store is on the dedicated case-actor container
        # (DEMOMA-06-005): a C1 client cannot address it.
        assert kwargs["case_manager_client"] is state.case_actor_client

    @pytest.mark.spec("DEMOMA-17-002")
    def test_c2_runs_no_rm_triage(self):
        """C2 joins to help coordinate, so it engages no case of its own.

        Giving it one would add an ``engage_case`` act to the ledger that
        neither scenario's semantic-type list claims; the roster runs inside
        the chain's own gate instead, so a failed invite still skips it.
        """
        state = _four_party_state()
        _, triage, roster_wait, _ = self._invite(state, run_then=True)

        triage.assert_not_called()
        assert roster_wait.call_args.kwargs["vendor_client"] is state.client(
            pair.C1
        )
        assert roster_wait.call_args.kwargs["expected_actor_ids"] == {
            state.actor_id(who) for who in (REPORTER, pair.C1, pair.C2)
        }

    @pytest.mark.spec("DEMOMA-14-010")
    def test_the_roster_keeps_the_prop_the_owners_decision_reads(self):
        """DEMOCI-01-011: the owner decides only once C2 is a participant."""
        state = _four_party_state()
        self._invite(state, run_then=True)

        assert state.kept(pair.SECOND_COORDINATOR_JOINED) == str(
            state.case.id_
        )

    @pytest.mark.spec("DEMOCI-01-011")
    def test_a_roster_that_never_arrives_keeps_nothing_and_is_recorded(self):
        """The real ``demo_gate`` runs, so one failure is recorded.

        Without the prop the next fragment — the suggestion or the ownership
        offer — stops the story rather than acting into a case C2 is not in.
        """
        state = _four_party_state()

        def _timeout(**_kwargs):
            raise AssertionError("timed out polling for the roster")

        self._invite(state, run_then=True, roster=_timeout)

        with pytest.raises(
            DemoStoryError, match="case the second Coordinator joined"
        ):
            state.kept(pair.SECOND_COORDINATOR_JOINED)
        assert [f for f in demo_utils._demo_failures if "GATE FAILED" in f], (
            demo_utils._demo_failures
        )

    @pytest.mark.spec("CLP-08-005")
    def test_the_reporter_holds_the_case_before_c2_answers(self):
        """Bug #2135: the join broadcasts to every participant.

        C2's reply to the full-case Invite broadcasts
        ``Announce(CaseLedgerEntry)`` to all participants, so a Reporter
        without the case has no genesis hash to anchor the chain on.
        """
        state = _four_party_state()
        _, _, _, replica_wait = self._invite(state)

        assert [c.kwargs["client"] for c in replica_wait.call_args_list] == [
            state.client(REPORTER)
        ]


# ---------------------------------------------------------------------------
# The CLI and cast surfaces both scenarios share (DEMOCI-11-011/020)
# ---------------------------------------------------------------------------


class TestTheSharedCliSurfaces:
    """``ROLES``, the cast members and C2's unseated container."""

    def test_the_roles_seat_four_containers_plus_the_case_actor(self):
        """One list for both scenarios, in ``main()`` parameter order."""
        roles = pair.two_coordinator_roles(case_actor=case_actor_role())

        assert [role.name for role in roles] == [
            REPORTER,
            pair.C1_ROLE,
            pair.C2,
            VENDOR,
            "case-actor",
        ]
        assert [role.slot for role in roles[:4]] == [
            REPORTER_SLOT,
            COORDINATOR_SLOT,
            CAST[3],
            VENDOR_SLOT,
        ]
        # C2 takes a character slot, whose role comes from the Invite that
        # seats it rather than from its container (DEMOCI-11-021).
        assert roles[2].slot is CAST[3]

    def test_the_case_actor_role_is_the_callers(self):
        """Only ``rccv-handoff`` exposes ``--case-actor-id`` (DEMOMA-14-008)."""
        without = pair.two_coordinator_roles(case_actor=case_actor_role())
        with_id = pair.two_coordinator_roles(
            case_actor=case_actor_role(has_id=True)
        )

        assert "case_actor_id" not in role_kwarg_names(without)
        assert "case_actor_id" in role_kwarg_names(with_id)

    def test_the_cast_members_carry_the_pairs_labels_and_url_overrides(self):
        """Each URL falls back to the cast slot's own address."""
        members = pair.two_coordinator_cast_members(
            c1_url="http://elsewhere:7999/api/v2"
        )

        assert [(m.role, m.label) for m in members] == [
            (REPORTER, "Reporter"),
            (pair.C1_ROLE, "C1"),
            (pair.C2, "C2"),
            (VENDOR, "Vendor"),
        ]
        assert [m.url for m in members] == [
            None,
            "http://elsewhere:7999/api/v2",
            None,
            None,
        ]

    def test_only_c2s_container_is_declared_unseated(self):
        """The Vendor is seeded by the rcv opening; only C2 waits."""
        client = MagicMock(name="c2")
        unseated = pair.unseated_second_coordinator(client, "urn:test:c2")

        assert set(unseated) == {pair.C2}
        slot = unseated[pair.C2]
        assert isinstance(slot, UnseatedContainer)
        assert slot.label == "C2"
        assert slot.client is client
        assert slot.actor_id == "urn:test:c2"


# ---------------------------------------------------------------------------
# The devlogs the invariant harnesses read (DEMOMA-13-009, DEMOMA-14-009)
# ---------------------------------------------------------------------------


class TestTheSharedLedgerDump:
    """Each replica is dumped under the name the harness loads."""

    def test_the_devlog_names_follow_the_rvcv_convention(self):
        """``vendor`` is C1, ``coordinator`` is C2, ``vendor2`` is the Vendor.

        The names are not the parts the actors play: both invariant harnesses
        load ``devlogs/<demo>/vendor`` for C1's replica, so the dump has to
        translate the cast names back (``test/ci/invariants/\
test_rccv_extension_invariants.py``).
        """
        assert pair.DEVLOG_REPLICAS == (
            ("reporter", REPORTER),
            ("vendor", pair.C1),
            ("coordinator", pair.C2),
            ("vendor2", VENDOR),
        )

    def _dump(self, state):
        for name in state.cast:
            state.client(name).actor_id = f"https://example.org/actors/{name}"
        state.case_actor_client.actor_id = (
            "https://example.org/actors/case-actor"
        )
        with patch.object(coordinated_story, "dump_case_ledgers") as dump:
            pair.dump_two_coordinator_ledgers(state)
        return dump.call_args.kwargs["targets"]

    def test_every_seated_replica_is_dumped_plus_the_canonical_ledger(self):
        """Four replicas in devlogs order, then the canonical ledger."""
        state = _four_party_state()
        targets = self._dump(state)

        assert [t.actor_name for t in targets] == [
            "reporter",
            "vendor",
            "coordinator",
            "vendor2",
            "case-actor",
        ]
        # The canonical ledger is read on the dedicated container, never from
        # a participant's replica (DEMOMA-06-005).
        assert targets[-1].client is state.case_actor_client
        assert targets[-1].route_key == "case-actor"

    def test_a_c2_the_run_never_seated_is_left_out(self):
        """A failure before the seeding must not 404 the dump.

        The dump runs on the way out whether or not an earlier step failed
        (DEMOMA-23-003), and an unseated container holds no replica to read.
        """
        state = story_state(REPORTER, pair.C1, VENDOR, case=mock_case())
        targets = self._dump(state)

        assert [t.actor_name for t in targets] == [
            "reporter",
            "vendor",
            "vendor2",
            "case-actor",
        ]


# ---------------------------------------------------------------------------
# The continuations both scenarios tell
# ---------------------------------------------------------------------------


class TestRequiredParticipantsArePresent:
    """M1 is read from C1's replica in both scenarios."""

    @pytest.mark.spec("VP-02-015")
    def test_the_milestone_reads_c1s_replica_and_the_reporters(self):
        """C1 holds the case from its own triage, owner or not."""
        state = _four_party_state()

        with (
            patch.object(pair, "verify_case_active") as milestone,
            _no_banners(),
        ):
            pair.required_participants_are_present(state)

        kwargs = milestone.call_args.kwargs
        assert kwargs["receiver_client"] is state.client(pair.C1)
        assert kwargs["reporter_client"] is state.client(REPORTER)
        assert kwargs["case_id"] == state.case.id_
        assert kwargs["receiver_actor_id"] == state.actor_id(pair.C1)
        assert kwargs["reporter_actor_id"] == state.actor_id(REPORTER)


class TestEveryReplicaConverges:
    """All four replicas are verified against C1, the Vendor late."""

    @pytest.mark.spec("DEMOMA-23-007")
    def test_the_sync_phase_declares_every_replica_and_the_late_joiner(self):
        """The helper declares no scenario facts; the fragment supplies them."""
        state = _four_party_state()

        with patch.object(pair, "run_sync_verification_phase") as phase:
            pair.every_replica_converges(state)

        kwargs = phase.call_args.kwargs
        assert kwargs["auth_client"] is state.client(pair.C1)
        assert kwargs["auth_label"] == "C1"
        assert kwargs["auth_actor_id"] == state.actor_id(pair.C1)
        assert kwargs["reporter_client"] is state.client(REPORTER)
        assert kwargs["replicas"] == [
            (state.client(REPORTER), "Reporter"),
            (state.client(pair.C2), "C2"),
            (state.client(VENDOR), "Vendor"),
        ]
        assert kwargs["expected_participant_ids"] == {
            state.actor_id(who) for who in _CAST
        }
        # The Vendor joins last, whichever route the owner's decision took,
        # so it catches up from genesis on the late-joiner budget (#2202).
        assert kwargs["late_joiners"] == (state.client(VENDOR),)
        assert kwargs["state_checks"] == [
            (state.client(REPORTER), "Reporter"),
            (state.client(VENDOR), "Vendor"),
        ]


class TestFourWayNoteThread:
    """One thread: the Reporter asks, C1 answers, then the caller's updates."""

    def test_the_shared_half_comes_first_and_the_updates_follow(self):
        """The question and the answer are identical in both scenarios.

        Only what C2 and the Vendor add differs with who owns the case, so
        each scenario passes its own two posts rather than copying the whole
        thread (DEMOMA-17-001).
        """
        state = _four_party_state()
        updates = [
            NotePost(state.actor(pair.C2), "C2 Update", "ours"),
            NotePost(state.actor(VENDOR), "Vendor Status Update", "theirs"),
        ]

        with patch.object(pair, "add_note_thread") as thread:
            pair.four_way_note_thread(state, updates)

        watching_client, case, posts = thread.call_args.args
        # The thread is posted through C1's replica, which both scenarios
        # watch.
        assert watching_client is state.client(pair.C1)
        assert case is state.case
        assert [post.name for post in posts] == [
            "Question from Reporter",
            "C1 Response",
            "C2 Update",
            "Vendor Status Update",
        ]
        assert [post.content for post in posts[:2]] == [
            WORKAROUND_QUESTION,
            WORKAROUND_ANSWER,
        ]
        assert [post.poster.actor for post in posts[:2]] == [
            state.actor(REPORTER).actor,
            state.actor(pair.C1).actor,
        ]
        assert posts[2:] == updates


@pytest.mark.spec("DEMOMA-13-006")
@pytest.mark.spec("DEMOMA-14-014")
class TestAllFourPublish:
    """The Case Owner publishes first, whichever Coordinator that is.

    Per DEMOMA-07-003(4) the Case Owner triggers CS.P, and the embargo reads
    ``EM.EXITED`` once it has.  One copy of the step serves the owner that
    kept the case and the owner it was handed to.
    """

    def _run(self, state, *, owner, other):
        order: list[str] = []
        with (
            patch.object(
                pair,
                "wait_for_case_em_terminated",
                side_effect=lambda client, case_id: order.append(
                    f"em_exited:{devlogs_name_of(state, client, pair.DEVLOG_REPLICAS)}"
                ),
            ),
            patch.object(pair, "wait_for_participant_vf_state") as vf_wait,
            patch.object(pair, "verify_publicly_disclosed") as disclosed,
            patch.object(
                ActorSession,
                "notify_published",
                autospec=True,
                side_effect=lambda session: order.append(
                    f"published:{session.actor.id_}"
                ),
            ),
            _no_banners(),
        ):
            pair.all_four_publish(state, owner=owner, other=other)
        return order, vf_wait, disclosed

    def test_the_extensions_owner_publishes_first_then_the_others(self):
        """C1 kept the case, so C1 publishes and C2 is the other."""
        state = _four_party_state()
        order, _, _ = self._run(state, owner=pair.C1_PART, other=pair.C2_PART)

        assert order == [
            f"published:{state.actor_id(pair.C1)}",
            "em_exited:vendor",
            f"published:{state.actor_id(VENDOR)}",
            f"published:{state.actor_id(pair.C2)}",
            "em_exited:reporter",
            f"published:{state.actor_id(REPORTER)}",
            "em_exited:reporter",
        ], order

    def test_the_handoffs_new_owner_publishes_first_then_the_others(self):
        """C2 owns the case after the handoff, so C1 is the other."""
        state = _four_party_state()
        order, _, _ = self._run(state, owner=pair.C2_PART, other=pair.C1_PART)

        assert order == [
            f"published:{state.actor_id(pair.C2)}",
            "em_exited:vendor",
            f"published:{state.actor_id(VENDOR)}",
            f"published:{state.actor_id(pair.C1)}",
            "em_exited:reporter",
            f"published:{state.actor_id(REPORTER)}",
            "em_exited:reporter",
        ], order

    @pytest.mark.spec("DEMOMA-07-003")
    def test_the_reporter_publishes_after_the_teardown_reaches_it(self):
        """A Reporter that has not seen EM.EXITED would publish too early."""
        state = _four_party_state()
        order, _, _ = self._run(state, owner=pair.C1_PART, other=pair.C2_PART)

        reporter = f"published:{state.actor_id(REPORTER)}"
        assert order.index("em_exited:reporter") < order.index(reporter), (
            "the Reporter's publish must follow the EM.EXITED propagation"
            f" check; order was {order}"
        )

    def test_the_closing_milestone_reads_the_vendor_at_vf(self):
        """M7 confirms the Vendor ended on its own fix path."""
        state = _four_party_state()
        _, vf_wait, disclosed = self._run(
            state, owner=pair.C1_PART, other=pair.C2_PART
        )

        watched = {
            (c.kwargs["client"], c.kwargs["actor_id"])
            for c in vf_wait.call_args_list
        }
        for watcher in (pair.C1, REPORTER):
            assert (
                state.client(watcher),
                state.actor_id(VENDOR),
            ) in watched
        assert all(
            c.kwargs["expected_states"] == {CS_vf.VF}
            for c in vf_wait.call_args_list
        )
        kwargs = disclosed.call_args.kwargs
        assert kwargs["receiver_client"] is state.client(pair.C1)
        assert kwargs["reporter_client"] is state.client(REPORTER)
        # The Vendor is the participant with the fix path, so it is the one
        # whose publicly-disclosed state is verified (DEMOMA-15-001).
        assert kwargs["receiver_actor_id"] == state.actor_id(VENDOR)


# ---------------------------------------------------------------------------
# The parts the shared owner-keep-case continuations act on (#5535)
# ---------------------------------------------------------------------------


def _pair_cast_references() -> frozenset[str]:
    """Every way this pair's cast could be named in another module.

    Derived from the pair module, so a new ``Part`` joins the check with no
    edit here: the constant's own identifier, plus the name and the label it
    carries, which are the same hard-wiring written out as literals.
    """
    references: set[str] = set()
    for attribute, value in vars(pair).items():
        if isinstance(value, Part):
            references |= {attribute, value.name, value.label}
    return frozenset(references)


_PAIR_CAST_REFERENCES = _pair_cast_references()


def _continuations_source() -> str:
    """The source of the shared continuations, read as written."""
    source = owner_decision_story.__file__
    assert source is not None
    return pathlib.Path(source).read_text(encoding="utf-8")


def _cast_references(source: str) -> tuple[set[str], set[str]]:
    """The modules *source* imports, and every name it could name a cast by.

    Docstrings are excluded from the literals: a continuation may describe
    the pair it serves in prose without being wired to it.
    """
    import ast

    tree = ast.parse(source)
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    } | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(
            node,
            (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
        )
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    }
    referenced = (
        {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        | {
            node.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
        }
        | {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstrings
        }
    )
    return imported, referenced


class TestTheOwnerDecisionParts:
    """The pair names its parts; the continuations take them as data.

    AC-2 of #5535: the two ``owner-keep-case`` continuations must not be
    hard-wired to this pair's cast, so the vendor-first half can reuse them.
    """

    def test_each_part_pairs_a_cast_name_with_this_pairs_label(self):
        """A ``Part`` is the ``(name, label)`` a shared fragment needs."""
        assert Part(pair.C1, "C1") == pair.C1_PART
        assert Part(pair.C2, "C2") == pair.C2_PART
        assert Part(VENDOR, "Vendor") == pair.VENDOR_PART

    def test_the_continuations_import_nothing_from_this_pair(self):
        """``owner_decision_story`` must stay reusable by the other half.

        Read from the source rather than by patching, so the claim holds for
        the code as written: a continuation that reached for this pair's
        ``C1_PART`` could not serve the vendor-first pair, whose owner is a
        Vendor (#5535 AC-2).
        """
        imported, referenced = _cast_references(_continuations_source())
        # An absence proves nothing unless the walk found something: an empty
        # set satisfies every assertion below, so pin both non-empty first
        # (notes/architecture-ratchet-corpus.md, #5595).
        assert imported, "the import walk found nothing — the check is vacuous"
        assert referenced, "the name walk found nothing — the check is vacuous"
        assert pair.__name__ not in imported, (
            f"{pair.__name__} imported by owner_decision_story would"
            " hard-wire the two-coordinator cast into a continuation the"
            " vendor-first half reuses (#5535 AC-2)"
        )
        # Nor may it name this pair's cast by any other route — through the
        # pair's constants, or by writing the same name or label out as a
        # literal, which is the same hard-wiring with the identifier removed.
        assert not referenced & _PAIR_CAST_REFERENCES, (
            "owner_decision_story names this pair's cast"
            f" ({sorted(referenced & _PAIR_CAST_REFERENCES)}), so it could"
            " not serve the vendor-first pair, whose owner is a Vendor"
            " (#5535 AC-2)"
        )

    def test_the_cast_check_flags_a_planted_reference(self):
        """The positive control for the check above.

        A check that asserts an absence is only worth what its walk can see,
        so plant each evasion the blacklist form missed and assert the walk
        catches it: the pair's constant, an aliased module attribute, and the
        cast written out as a literal (#5595).
        """
        plants = {
            "import": "from vultron.demo.helpers.two_coordinator_story"
            " import C1_PART\nOWNER = C1_PART\n",
            "attribute": "from vultron.demo.helpers import"
            " two_coordinator_story as p\nOWNER = p.C2_PART\n",
            "literal name": 'OWNER = Part("c2", "Newcomer")\n',
            "literal label": 'OWNER = Part("newcomer", "C2")\n',
        }
        for shape, source in plants.items():
            _, referenced = _cast_references(source)
            assert referenced & _PAIR_CAST_REFERENCES, (
                f"the cast check misses a {shape} plant, so its absence"
                " assertion proves less than it claims"
            )
