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

"""Unit tests for the ``rvcv`` pair's shared story (#5536).

``rvcv-extension`` and ``rvcv-handoff`` tell one story up to a single
decision, and :mod:`vultron.demo.helpers.vendor_coordinator_story` is that one
copy of the code: the named prefix
:data:`~vultron.demo.helpers.vendor_coordinator_story\
.THE_VENDOR_INVITES_A_COORDINATOR`, which continues the vendor-first family's
``THE_VENDOR_ANSWERS_THE_REPORTER``, plus the continuations both scenarios
tell afterwards (DEMOMA-10, DEMOMA-11, DEMOMA-17-001).

The tests here own what the pair shares; each scenario's own module owns its
own fragments, ``test/demo/vendor_story/`` owns the vendor-first opening this
prefix only names, and ``test/demo/owner_decision_story/`` owns the
two ``owner-keep-case`` continuations this module only names the parts of.
Every test patches the collaborators out, so no HTTP happens; ``demo_gate`` /
``demo_check`` / ``demo_step`` stay real wherever the test is about control
flow and are stubbed to ``nullcontext`` only where it is about call shape.
"""

import contextlib
from collections.abc import Iterator
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from test.demo._helpers import (
    functions_referencing,
    gate_failures,
    mock_actor,
    mock_case,
    mock_client,
    patch_chain_shared,
    story_state,
)
from vultron.demo.helpers import (
    vendor_coordinator_story as pair,
)
from vultron.demo.helpers.coordinated_story import (
    COORDINATOR,
    COORDINATOR_LABEL,
    REPORTER,
    REPORTER_LABEL,
    cast as coordinated_cast,
    joining as coordinated_joining,
)
from vultron.demo.helpers.owner_decision_story import Part
from vultron.demo.helpers.story import Choose, UnseatedContainer
from vultron.demo.helpers.story_cast import CastContainer
from vultron.demo.helpers.vendor_story import (
    JOIN_TIMEOUT,
    THE_VENDOR_ANSWERS_THE_REPORTER,
    THE_VENDORS_CASE,
    VENDOR,
    VENDOR2,
    VENDOR2_LABEL,
    VENDOR_LABEL,
)
from vultron.demo.utils.failures import _demo_failures
from vultron.enums.roles import CVDRole
from vultron.errors import DemoStoryError

#: Clear the process-global failure accumulator around every test.
pytestmark = pytest.mark.usefixtures("fresh_demo_failures")

#: The pair's four cast names, in ``ROLES`` order.
_CAST = (REPORTER, VENDOR, COORDINATOR, VENDOR2)

#: The two the vendor-first opening seeds and seats; the other two are seeded
#: after the branch point (DEMOCI-11-018, #5532).
_SEATED = (REPORTER, VENDOR)

#: How many items of the pair's prefix are the vendor-first family's opening.
_FAMILY_PREFIX_LEN = len(THE_VENDOR_ANSWERS_THE_REPORTER.items)

#: The choice at which this pair parts from ``rv`` and ``rvv``.
_BRANCH = Choose(
    branch_point="vendor-after-answer",
    choice="invite-coordinator",
    by=VENDOR,
)


def _step_failures() -> list[str]:
    """Every recorded step failure, in order (gate failures: ``gate_failures``)."""
    return [f for f in _demo_failures if "STEP FAILED" in f]


def _four_party_state():
    """A story state seating all four, on an open case."""
    state = story_state(*_CAST, case=mock_case())
    state.keep(THE_VENDORS_CASE, str(state.case.id_))
    return state


def _opening_state():
    """The state as the shared opening leaves it: two seated, two waiting."""
    return story_state(
        *_SEATED, case=mock_case(), unseated=(COORDINATOR, VENDOR2)
    )


# ---------------------------------------------------------------------------
# The named prefix (DEMOMA-10, DEMOMA-11, DEMOCI-11-018)
# ---------------------------------------------------------------------------


class TestTheVendorInvitesACoordinatorPrefix:
    """``THE_VENDOR_INVITES_A_COORDINATOR`` is the pair's one opening."""

    def test_the_prefix_starts_with_the_vendor_first_familys_opening(self):
        """Identity of the shared stretch, not a matching sequence.

        All four vendor-first scenarios share one copy of the report
        submission, Vendor1's triage and the note thread, which is what makes
        their recordings byte-identical up to ``vendor-after-answer``
        (DEMOCI-11-018).  Comparing against
        ``THE_VENDOR_ANSWERS_THE_REPORTER.items`` is what stops this pair
        slipping a step in before that branch point.
        """
        nested = pair.THE_VENDOR_INVITES_A_COORDINATOR.items[
            :_FAMILY_PREFIX_LEN
        ]

        assert nested == THE_VENDOR_ANSWERS_THE_REPORTER.items
        # Identity only: ``Choose`` is a frozen dataclass, so a hand-copied
        # duplicate would compare equal.
        for mine, theirs in zip(
            nested, THE_VENDOR_ANSWERS_THE_REPORTER.items, strict=True
        ):
            assert mine is theirs

    def test_the_prefix_parts_from_rv_and_rvv_after_the_vendors_answer(self):
        """Vendor1's own decision follows its answer in the note thread.

        ``rv`` publishes after its fix and ``rvv`` invites a second Vendor
        where this pair invites a Coordinator, so the choice at
        ``vendor-after-answer`` is what makes them three scenarios rather
        than one.
        """
        branch = pair.THE_VENDOR_INVITES_A_COORDINATOR.items[
            _FAMILY_PREFIX_LEN
        ]

        assert branch == _BRANCH
        # Vendor1 is the Case Owner, and only the owner may invite
        # (CM-17-007), so it is the actor that decides here.
        assert branch.by == VENDOR

    def test_the_prefix_runs_the_declared_order_and_stops_at_the_join(self):
        """One assertion for the whole prefix, so a reordering shows.

        The order is load-bearing: the Coordinator and Vendor2 are seeded
        after the branch point (DEMOCI-11-018), and the prefix ends with the
        Coordinator's join, which is the owner's decision's precondition
        (DEMOMA-10-004, CM-21-021).
        """
        assert pair.THE_VENDOR_INVITES_A_COORDINATOR.items == (
            *THE_VENDOR_ANSWERS_THE_REPORTER.items,
            _BRANCH,
            pair.the_coordinator_and_vendor2_are_seeded,
            pair.the_vendor_invites_the_coordinator,
        )

    def test_the_prefix_walks_the_two_steps_both_scenarios_declare(self):
        """The path is read off the choices, not typed beside them."""
        assert pair.THE_VENDOR_INVITES_A_COORDINATOR.path == (
            ("reporter-whom-to-tell", "vendor"),
            ("vendor-after-answer", "invite-coordinator"),
        )


# ---------------------------------------------------------------------------
# The Coordinator and Vendor2 are seeded after the branch point (#5532)
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def _seeding_stubs(
    seeded, *, seed_error=None, lookups=None
) -> Iterator[SimpleNamespace]:
    """Stub the pair's seeding and the read-back the seating does.

    ``pair``'s own ``demo_step`` is left **real**: the tests here are about
    what a failed seeding leaves seated, and patching the step out would make
    its failure propagate instead of being recorded.  The read-back is looked
    up on ``coordinated_story.cast``, where ``seat_character_actors`` lives.
    """
    with (
        patch.object(
            pair,
            "seed_containers_rvcv",
            return_value=tuple(seeded),
            side_effect=seed_error,
        ) as seed,
        patch.object(
            coordinated_cast,
            "get_actor_by_id",
            side_effect=(
                list(lookups) if lookups is not None else list(seeded[2:])
            ),
        ) as lookup,
    ):
        yield SimpleNamespace(seed=seed, lookup=lookup)


class TestTheCoordinatorAndVendor2AreSeeded:
    """Both are seeded by the fragment that brings the first into the case.

    Every actor and peer record written before the case exists is one more
    read of the recording clock, so seeding either in the shared opening
    would move the first ledger entry's timestamp away from ``rv``'s and
    ``rvv``'s and break the byte identity of the shared stretch
    (DEMOCI-11-018, #5532).
    """

    def test_the_seeding_fragment_is_the_only_caller_of_the_seeding(self):
        """Nothing else in the module may seed the four containers.

        A second call site — in particular one reachable from the
        vendor-first family's opening — is how the recordings would drift
        apart again.  Read from the source, so the claim holds for the code
        as written and not only for the path a test drives.
        """
        assert functions_referencing(pair, "seed_containers_rvcv") == [
            "the_coordinator_and_vendor2_are_seeded"
        ]

    def test_the_seeding_fragment_follows_the_vendors_choice(self):
        """It is placed after the ``vendor-after-answer`` choice."""
        items = pair.THE_VENDOR_INVITES_A_COORDINATOR.items
        branch = items.index(_BRANCH)
        seeding = items.index(pair.the_coordinator_and_vendor2_are_seeded)

        assert branch < seeding, (
            "the seeding must run after Vendor1's choice: every record it"
            " writes before the case opens moves the first ledger entry's"
            " timestamp (DEMOCI-11-018)"
        )
        assert seeding >= _FAMILY_PREFIX_LEN, (
            "the vendor-first family's opening must not reach the four-party"
            " seeding"
        )

    def test_the_fragment_seeds_all_four_then_seats_the_two_newcomers(self):
        """The two already seeded are re-seeded idempotently.

        ``seed_containers_rvcv`` registers every actor as a peer of the other
        three (DEMOMA-10-001, DEMOMA-11-001), which needs all four clients;
        ``POST /actors/`` and the peer registrations are idempotent, so the
        two the shared opening seeded come back unchanged.
        """
        state = _opening_state()
        seeded = [mock_actor(f"urn:test:{name}") for name in _CAST]
        # The waiting containers are consumed by the seating, so hold them.
        waiting = {
            name: state.container(name) for name in (COORDINATOR, VENDOR2)
        }

        with _seeding_stubs(seeded) as stubs:
            pair.the_coordinator_and_vendor2_are_seeded(state)

        kwargs = stubs.seed.call_args.kwargs
        assert kwargs["reporter_client"] is state.client(REPORTER)
        assert kwargs["vendor_client"] is state.client(VENDOR)
        assert kwargs["coordinator_client"] is waiting[COORDINATOR].client
        assert kwargs["vendor2_client"] is waiting[VENDOR2].client
        assert kwargs["case_actor_client"] is state.case_actor_client
        assert kwargs["reporter_actor_id"] == state.actor_id(REPORTER)
        assert kwargs["vendor_actor_id"] == state.actor_id(VENDOR)
        # The deterministic ids come from the waiting containers, which hold
        # the ``--coordinator-id`` and ``--vendor2-id`` values of the run.
        assert kwargs["coordinator_actor_id"] == "urn:test:coordinator"
        assert kwargs["vendor2_actor_id"] == "urn:test:vendor2"

        # Each new actor is read back from its own container (ADR-0073).
        assert [c.args[0] for c in stubs.lookup.call_args_list] == [
            waiting[COORDINATOR].client,
            waiting[VENDOR2].client,
        ]
        assert state.unseated == {}
        assert state.actor_id(COORDINATOR) == "urn:test:coordinator"
        assert state.actor_id(VENDOR2) == "urn:test:vendor2"
        assert not _step_failures(), _demo_failures

    def test_both_are_seated_inside_the_step_that_seeded_them(self):
        """One step, so a reader of the devlogs sees one cause.

        The seating is the second half of bringing a character actor in, and
        it reads back what the seeding just created; splitting the two across
        steps would report a read-back failure as a step of its own, with the
        seeding above it logged as a success.
        """
        state = _opening_state()
        seeded = [mock_actor(f"urn:test:{name}") for name in _CAST]
        order: list[str] = []

        @contextlib.contextmanager
        def _step(label: str):
            order.append(f"enter:{label}")
            yield
            order.append("exit")

        with (
            patch.object(pair, "demo_step", side_effect=_step),
            patch.object(
                pair,
                "seed_containers_rvcv",
                side_effect=lambda **_kwargs: (
                    order.append("seeded") or tuple(seeded)
                ),
            ),
            patch.object(
                pair,
                "seat_character_actors",
                side_effect=lambda _s, joining: order.append(
                    f"seated:{list(joining)}"
                ),
            ),
        ):
            pair.the_coordinator_and_vendor2_are_seeded(state)

        assert order == [
            "enter:Seeding the Coordinator and Vendor2 containers with"
            " actor records",
            "seeded",
            f"seated:{[COORDINATOR, VENDOR2]}",
            "exit",
        ], order

    @pytest.mark.spec("EDF-06-005")
    def test_a_failed_seeding_seats_neither_newcomer(self):
        """#2308: a partly seated cast runs a real act before the story stops.

        Vendor2 is seated here although it joins later, so a cast holding the
        Coordinator alone would let the Coordinator's invite run before
        Vendor2's absence stopped the story.  The failure is recorded by the
        step and both containers keep waiting.
        """
        state = _opening_state()
        seeded = [mock_actor(f"urn:test:{name}") for name in _CAST]

        with _seeding_stubs(
            seeded, seed_error=RuntimeError("container unreachable")
        ) as stubs:
            pair.the_coordinator_and_vendor2_are_seeded(state)

        stubs.lookup.assert_not_called()
        assert sorted(state.cast) == sorted(_SEATED)
        assert sorted(state.unseated) == sorted([COORDINATOR, VENDOR2])
        assert _step_failures(), _demo_failures

    @pytest.mark.spec("EDF-06-005")
    def test_a_failed_read_back_of_vendor2_seats_neither(self):
        """The two halves are separated so neither is seated alone (#2308).

        The Coordinator reads back first, so this is the case a per-actor
        seating would get wrong: it would seat the Coordinator and leave
        Vendor2 waiting.
        """
        state = _opening_state()
        seeded = [mock_actor(f"urn:test:{name}") for name in _CAST]

        with _seeding_stubs(
            seeded, lookups=[seeded[2], RuntimeError("no such actor")]
        ):
            pair.the_coordinator_and_vendor2_are_seeded(state)

        assert sorted(state.cast) == sorted(_SEATED)
        assert sorted(state.unseated) == sorted([COORDINATOR, VENDOR2])
        assert _step_failures(), _demo_failures


# ---------------------------------------------------------------------------
# Vendor1 invites the Coordinator (DEMOMA-10-003, DEMOMA-17-002)
# ---------------------------------------------------------------------------


class TestTheVendorInvitesTheCoordinator:
    """The invite is Vendor1's, offers COORDINATOR and runs no triage."""

    def test_the_join_is_declared_in_full_and_sent_by_vendor1(self):
        """Only the Case Owner may invite (CM-17-007), and that is Vendor1.

        The inviter is named rather than defaulted: the shared helper's
        default is the coordinator-first family's Coordinator, which in this
        pair is the *invitee* — taking the default would have the Coordinator
        invite itself.
        """
        state = _four_party_state()

        with patch.object(pair, "invitee_joins_the_case") as join:
            pair.the_vendor_invites_the_coordinator(state)

        assert join.call_args.args == (state, COORDINATOR, COORDINATOR_LABEL)
        kwargs = join.call_args.kwargs
        assert kwargs["inviter"] == VENDOR
        assert kwargs["inviter"] != COORDINATOR, (
            "the inviter is Vendor1, the Case Owner, not the family's"
            " Coordinator — which is the invitee here (CM-17-007)"
        )
        assert kwargs["inviter_label"] == VENDOR_LABEL
        # The Coordinator holds COORDINATOR and never CASE_MANAGER, which
        # stays with the CaseActor (DEMOMA-10-003).
        assert kwargs["role"] is CVDRole.COORDINATOR
        assert kwargs["seated"] == (REPORTER, VENDOR, COORDINATOR)
        assert kwargs["join_timeout"] == JOIN_TIMEOUT
        assert kwargs["cross_container_timeout"] == JOIN_TIMEOUT

    @pytest.mark.spec("DEMOMA-17-002")
    def test_the_coordinator_runs_no_rm_triage(self):
        """It joins to help coordinate, so it engages no case of its own.

        CM-11-002 applies to an invitee that answers over a report it must
        triage; giving this one a triage would put an ``engage_case`` act in
        the ledger neither scenario's semantic-type list claims.
        """
        state = _four_party_state()

        with patch.object(pair, "invitee_joins_the_case") as join:
            pair.the_vendor_invites_the_coordinator(state)

        assert join.call_args.kwargs["triages"] is False

    @pytest.mark.spec("DEMOCI-01-011")
    def test_the_roster_is_the_gate_that_keeps_the_join(self):
        """Either continuation presupposes the Coordinator being in the case.

        The extension has it suggest Vendor2 (DEMOMA-10-004) and the handoff
        transfers ownership to it (CM-21-021), so a roster that never arrived
        must stop the story there rather than suggesting or offering into a
        case the Coordinator is not in.
        """
        state = _four_party_state()

        with patch.object(pair, "invitee_joins_the_case") as join:
            pair.the_vendor_invites_the_coordinator(state)

        assert join.call_args.kwargs["joined"] is pair.COORDINATOR_JOINED


class TestTheJoinAsTheSharedHelperRunsIt:
    """The declaration above, run through the real invite helper.

    One pass with the chain stubbed rather than the whole helper, because the
    combination is what this pair relies on: ``triages=False`` moves the
    roster into the chain's own gate, and ``joined=`` makes that gate keep
    the prop (``test/demo/coordinated_story/`` owns the helper itself).
    """

    def _invite(self, state, *, run_then: bool = False, roster=None):
        """Run the fragment with the invite chain stubbed out.

        With *run_then* the chain's ``then`` callback is run while the
        collaborators are still patched, which is how a non-triaging
        invitee's roster gate is reached.  ``demo_gate`` stays real there, so
        a failing roster records its failure and keeps no prop.
        """
        with (
            patch.object(
                coordinated_joining, "run_case_invite_chain"
            ) as chain,
            patch.object(
                coordinated_joining, "run_invite_path_rm_triage"
            ) as triage,
            patch.object(
                coordinated_joining,
                "wait_for_case_participants",
                side_effect=roster,
            ) as roster_wait,
            patch_chain_shared(
                coordinated_joining, "wait_for_case_on_container"
            ) as replica_wait,
            patch.object(
                coordinated_joining,
                "demo_check",
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            pair.the_vendor_invites_the_coordinator(state)
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
        return SimpleNamespace(
            chain=chain,
            triage=triage,
            roster=roster_wait,
            replica=replica_wait,
        )

    def test_the_invite_offers_the_coordinator_role_from_vendor1(self):
        """Vendor1's session sends it; the CaseActor holds CASE_MANAGER."""
        state = _four_party_state()
        stubs = self._invite(state)

        kwargs = stubs.chain.call_args.kwargs
        assert kwargs["invitee_name"] == COORDINATOR_LABEL
        assert kwargs["invitee_client"] is state.client(COORDINATOR)
        assert kwargs["invitee"] is state.actor(COORDINATOR).actor
        assert kwargs["inviter"].client is state.client(VENDOR)
        assert kwargs["inviter"].role is CVDRole.COORDINATOR
        # The CASE_MANAGER's store is on the dedicated case-actor container
        # (DEMOMA-06-005): a Vendor1 client cannot address it.
        assert kwargs["case_manager_client"] is state.case_actor_client

    @pytest.mark.spec("DEMOMA-17-002")
    def test_no_triage_runs_and_the_roster_is_read_on_vendor1s_replica(self):
        """The roster is read from the inviter's own replica.

        Vendor1 is the Case Owner, so its replica is the one that reflects
        the seating; the three names are the Reporter, Vendor1 and the
        Coordinator, Vendor2 having only been seeded.
        """
        state = _four_party_state()
        stubs = self._invite(state, run_then=True)

        stubs.triage.assert_not_called()
        kwargs = stubs.roster.call_args.kwargs
        assert kwargs["vendor_client"] is state.client(VENDOR)
        assert kwargs["expected_actor_ids"] == {
            state.actor_id(who) for who in (REPORTER, VENDOR, COORDINATOR)
        }
        assert kwargs["timeout_seconds"] == JOIN_TIMEOUT

    @pytest.mark.spec("DEMOMA-10-004")
    def test_the_roster_keeps_the_prop_the_owners_decision_reads(self):
        """DEMOCI-01-011: the owner decides only once the Coordinator is in."""
        state = _four_party_state()
        self._invite(state, run_then=True)

        assert state.kept(pair.COORDINATOR_JOINED) == str(state.case.id_)

    @pytest.mark.spec("DEMOCI-01-011")
    def test_a_roster_that_never_arrives_keeps_nothing_and_is_recorded(self):
        """The real ``demo_gate`` runs, so one failure is recorded.

        Without the prop the next fragment — the suggestion or the ownership
        offer — stops the story rather than acting into a case the
        Coordinator is not in.
        """
        state = _four_party_state()

        def _timeout(**_kwargs):
            raise AssertionError("timed out polling for the roster")

        self._invite(state, run_then=True, roster=_timeout)

        with pytest.raises(
            DemoStoryError, match="case the Coordinator joined"
        ):
            state.kept(pair.COORDINATOR_JOINED)
        assert gate_failures(), _demo_failures

    @pytest.mark.spec("CLP-08-005")
    def test_the_reporter_holds_the_case_before_the_coordinator_answers(self):
        """Bug #2135: the join broadcasts to every participant.

        The Coordinator's reply to the full-case Invite broadcasts
        ``Announce(CaseLedgerEntry)`` to all participants, so a Reporter
        without the case has no genesis hash to anchor the chain on.
        """
        state = _four_party_state()
        stubs = self._invite(state)

        assert [c.kwargs["client"] for c in stubs.replica.call_args_list] == [
            state.client(REPORTER)
        ]


# ---------------------------------------------------------------------------
# Continuations both scenarios tell, whichever way the owner decided
# ---------------------------------------------------------------------------


class TestEveryReplicaConverges:
    """All four replicas are verified against Vendor1, Vendor2 late."""

    @pytest.mark.spec("DEMOMA-23-007")
    def test_the_sync_phase_declares_every_replica_and_the_late_joiner(self):
        """The helper declares no scenario facts; the fragment supplies them.

        Vendor1 is the authority in both scenarios: it holds the case from
        its own triage onward, so its replica is complete whether or not the
        ownership moved (DEMOMA-10-016, DEMOMA-11-019).
        """
        state = _four_party_state()

        with patch.object(pair, "run_sync_verification_phase") as phase:
            pair.every_replica_converges(state)

        kwargs = phase.call_args.kwargs
        assert kwargs["auth_client"] is state.client(VENDOR)
        assert kwargs["auth_label"] == VENDOR_LABEL
        assert kwargs["auth_actor_id"] == state.actor_id(VENDOR)
        assert kwargs["reporter_client"] is state.client(REPORTER)
        assert kwargs["reporter_actor_id"] == state.actor_id(REPORTER)
        assert kwargs["case_id"] == state.case.id_
        assert kwargs["replicas"] == [
            (state.client(REPORTER), REPORTER_LABEL),
            (state.client(COORDINATOR), COORDINATOR_LABEL),
            (state.client(VENDOR2), VENDOR2_LABEL),
        ]
        assert kwargs["expected_participant_ids"] == {
            state.actor_id(who) for who in _CAST
        }
        # Vendor2 joins after the early replicas exist (#2202), whichever
        # route the owner's decision took, so it catches up from genesis.
        assert kwargs["late_joiners"] == (state.client(VENDOR2),)
        assert kwargs["state_checks"] == [
            (state.client(REPORTER), REPORTER_LABEL),
            (state.client(VENDOR2), VENDOR2_LABEL),
        ]


# ---------------------------------------------------------------------------
# The CLI and cast surfaces both scenarios share (DEMOCI-11-011/020)
# ---------------------------------------------------------------------------


class TestTheSharedCastSurfaces:
    """The four containers, and the two that wait for an actor."""

    def test_the_cast_members_are_the_four_in_roles_order(self):
        """The same four lines in both ``main()`` functions otherwise.

        Each URL falls back to the cast slot's own address (DEMOCI-11-020),
        so a scenario declares no ``*_BASE_URL`` of its own.
        """
        members = pair.vendor_coordinator_cast_members(
            coordinator_url="http://elsewhere:7999/api/v2"
        )

        assert members == [
            CastContainer(REPORTER, REPORTER_LABEL, None),
            CastContainer(VENDOR, VENDOR_LABEL, None),
            CastContainer(
                COORDINATOR,
                COORDINATOR_LABEL,
                "http://elsewhere:7999/api/v2",
            ),
            CastContainer(VENDOR2, VENDOR2_LABEL, None),
        ]

    def test_only_the_coordinator_and_vendor2_are_declared_unseated(self):
        """The Reporter and Vendor1 are seeded by the shared opening.

        Neither newcomer takes any part until Vendor1 has decided to invite a
        Coordinator, so neither is seeded before the branch point
        (DEMOCI-11-018).
        """
        coordinator_client = mock_client()
        vendor2_client = mock_client()

        unseated = pair.unseated_coordinator_and_vendor2(
            coordinator_client=coordinator_client,
            coordinator_id="urn:test:coordinator",
            vendor2_client=vendor2_client,
            vendor2_id="urn:test:vendor2",
        )

        assert set(unseated) == {COORDINATOR, VENDOR2}
        assert unseated[COORDINATOR] == UnseatedContainer(
            COORDINATOR_LABEL, coordinator_client, "urn:test:coordinator"
        )
        assert unseated[VENDOR2] == UnseatedContainer(
            VENDOR2_LABEL, vendor2_client, "urn:test:vendor2"
        )

    def test_the_devlogs_name_each_replica_by_its_cast_name(self):
        """Every actor of this pair is named the same everywhere.

        On the command line, in ``ROLES`` and in its devlogs, so one cast
        name serves all three and the dump needs no translation table
        (DEMOMA-19-018).
        """
        assert pair.DEVLOG_REPLICAS == (REPORTER, VENDOR, COORDINATOR, VENDOR2)


# ---------------------------------------------------------------------------
# The part the shared owner-keep-case continuations act on (#5536)
# ---------------------------------------------------------------------------


class TestTheCoordinatorPart:
    """The pair names its part; the continuations take it as data."""

    def test_the_part_is_the_rcv_familys_cast_name_and_label(self):
        """One copy of every fragment that reads a Coordinator serves both.

        The ``owner-keep-case`` decision appears in the coordinator-first
        half of the tree too, so its continuations live in
        ``owner_decision_story`` and are handed this part rather than naming
        a Coordinator of their own (DEMOMA-17-001).
        """
        assert Part(COORDINATOR, COORDINATOR_LABEL) == pair.COORDINATOR_PART
        assert pair.COORDINATOR_PART.name is COORDINATOR
        assert pair.COORDINATOR_PART.label is COORDINATOR_LABEL

    def test_the_part_is_frozen(self):
        """A continuation cannot reseat the cast it was handed.

        Assigned through ``setattr`` under a variable name, because the field
        is read-only and both a direct assignment and a constant-named
        ``setattr`` are refused by the type checker and the linter before the
        test can run.
        """
        field = "name"
        with pytest.raises(AttributeError):
            setattr(pair.COORDINATOR_PART, field, "someone-else")


class TestTheJoinProp:
    """The prop the roster gate keeps and both continuations read."""

    def test_the_prop_holds_the_case_id_as_a_string(self):
        """A prop's type is checked on the way in, so a reader never does.

        It is the case id rather than the case: the continuations read it to
        confirm the Coordinator joined, and the case itself is already on the
        story's state.
        """
        state = _four_party_state()
        state.keep(pair.COORDINATOR_JOINED, str(state.case.id_))

        assert state.kept(pair.COORDINATOR_JOINED) == str(state.case.id_)
        with pytest.raises(DemoStoryError, match="not one"):
            state.keep(pair.COORDINATOR_JOINED, MagicMock())
