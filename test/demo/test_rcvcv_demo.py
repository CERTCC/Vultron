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

"""Unit tests for the RCVCV five-party CVD demo (DEMOMA-19, #5534).

``rcvcv`` is written as composition (ADR-0098,
:mod:`vultron.demo.helpers.story`): its opening is the shared
``REPORTER_ASKS_THE_VENDOR`` prefix of the Reporter → Coordinator → Vendor
family, and its own story is the continuation after C1 decides to invite a
second Coordinator.  The checks that used to sit on its ``_phase_*`` functions
therefore sit here on three things:

* the **story's shape** — the path read off its choices, the identity of the
  stretch it shares with ``rcv``, and the order of its own fragments;
* each of its **own fragments**, driven against a
  :func:`~test.demo._helpers.story_state` stand-in cast, so a test observes
  what the fragment calls;
* the **surfaces around the story** — the CLI option set, the registry entry
  and the devlogs names the invariant harness reads (DEMOMA-19-018).

What the shared opening does is not re-tested here; it is one copy of the code
and ``test/demo/test_coordinated_story.py`` owns it.  Every test patches the
collaborators out, so no HTTP happens; ``demo_gate`` / ``demo_check`` /
``demo_step`` stay real wherever the test is about control flow and are
stubbed to ``nullcontext`` only where it is about call shape
(``test_demo_context_managers.py`` owns their behaviour).
"""

import ast
import contextlib
import inspect
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

import vultron.demo.scenario.rcvcv_demo as demo
import vultron.demo.utils as demo_utils
from test.demo._helpers import (
    mock_actor,
    mock_case,
    mock_client,
    patch_chain_shared,
    story_state,
    stub_closure_gate,
)
from vultron.core.states.cs import CS_d, CS_vf
from vultron.core.states.rm import RM
from vultron.demo.actor_session import ActorSession
from vultron.demo.cli import main as cli_main
from vultron.demo.helpers import coordinated_story, invite_chain
from vultron.demo.helpers.coordinated_story import (
    COORDINATOR,
    REPORTER,
    REPORTER_ASKS_THE_VENDOR,
    TIMELINE_ANSWER,
    VENDOR,
)
from vultron.demo.helpers.polling import LATE_JOINER_TIMEOUT
from vultron.demo.helpers.story import Choose, UnseatedContainer, choose
from vultron.demo.scenario import rcv_demo
from vultron.demo.scenario.registry import registered_scenarios
from vultron.demo.utils import reset_demo_failures
from vultron.enums.roles import CVDRole
from vultron.errors import DemoStoryError
from vultron.wire.as2.vocab.base.objects.object_types import as_Note

#: The scenario's five cast names, in ``ROLES`` order.
_CAST = (REPORTER, demo.C1, demo.V1, demo.C2, demo.V2)

#: How many items of ``STORY`` are the shared opening.
_PREFIX_LEN = len(REPORTER_ASKS_THE_VENDOR.items)


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
    """Make the fragments' own context managers pass-through.

    Both modules are patched: a fragment of this scenario runs inside its own
    ``demo_step`` and reaches shared fragments that open theirs.
    """
    with contextlib.ExitStack() as stack:
        for module in (demo, coordinated_story):
            for name in ("demo_gate", "demo_check", "demo_step"):
                stack.enter_context(
                    patch.object(
                        module,
                        name,
                        side_effect=lambda _: contextlib.nullcontext(),
                    )
                )
        yield


def _five_party_state():
    """A story state seating all five, on an open case."""
    return story_state(*_CAST, case=mock_case())


def _sessions_of(mock_method) -> list[str]:
    """The actor id of each session an ``autospec``-ed verb was called on."""
    return [call.args[0].actor.id_ for call in mock_method.call_args_list]


# ---------------------------------------------------------------------------
# The story's shape (DEMOCI-11-019, DEMOCI-11-024)
# ---------------------------------------------------------------------------


class TestRcvcvStoryShape:
    """``STORY`` places the scenario on the tree, and nothing else does."""

    #: The path ``rcvcv`` declared as ``@scenario(path=...)`` before it was
    #: composed.  The composed form must walk exactly the same tree ending,
    #: or the recordings, the generated index and the invariant harness all
    #: move with it.
    DECLARED_PATH = (
        ("reporter-whom-to-tell", "coordinator"),
        ("coordinator-invite-whom", "vendor"),
        ("vendor-join", "accept"),
        ("reporter-after-join", "ask-vendor"),
        ("coordinator-after-answer", "invite-coordinator"),
    )

    def test_the_story_walks_the_path_the_scenario_used_to_declare(self):
        """The path is read off the choices, not typed beside them."""
        assert demo.STORY.path == self.DECLARED_PATH

    def test_the_opening_is_the_shared_prefix_itself(self):
        """``rcvcv`` and ``rcv`` start with the *same* prefix items.

        Identity of the shared stretch, not merely a matching sequence: the
        two scenarios' recordings must be byte-identical up to the branch
        point where they part (DEMOCI-11-018), which only holds while the
        opening is one copy of the code.  Comparing against
        ``REPORTER_ASKS_THE_VENDOR.items`` is what stops a sibling slipping a
        step in before the branch point.
        """
        assert demo.STORY.items[:_PREFIX_LEN] == REPORTER_ASKS_THE_VENDOR.items
        assert (
            rcv_demo.STORY.items[:_PREFIX_LEN]
            == REPORTER_ASKS_THE_VENDOR.items
        )
        # Every item of the prefix is the same object in both stories.
        for mine, theirs in zip(
            demo.STORY.items[:_PREFIX_LEN],
            rcv_demo.STORY.items[:_PREFIX_LEN],
            strict=True,
        ):
            assert mine is theirs or mine == theirs

    def test_the_siblings_part_at_the_coordinators_decision(self):
        """The first item after the prefix is the choice, and it differs."""
        branch = demo.STORY.items[_PREFIX_LEN]
        assert branch == Choose(
            branch_point="coordinator-after-answer",
            choice="invite-coordinator",
            by=COORDINATOR,
        )
        assert branch != rcv_demo.STORY.items[_PREFIX_LEN], (
            "rcvcv and rcv must take different choices at"
            " coordinator-after-answer, or they are the same scenario"
        )

    def test_the_prefix_ends_with_the_answered_note_thread(self):
        """#4759: C1 decides only after the Reporter asks and V1 answers."""
        assert (
            REPORTER_ASKS_THE_VENDOR.items[-1]
            is coordinated_story.reporter_asks_about_the_timeline
        )

    def test_the_continuation_runs_in_the_declared_order(self):
        """One assertion for the whole continuation, so a reordering shows.

        The order is load-bearing twice over: the character actors are seeded
        after C1's choice (DEMOCI-11-018) and C2 is invited after the note
        thread the opening posts (#4759).
        """
        assert demo.STORY.items[_PREFIX_LEN:] == (
            choose(
                "coordinator-after-answer", "invite-coordinator", by=demo.C1
            ),
            demo.replicas_drain_before_the_second_coordinator,
            demo.seed_the_second_coordinator_and_vendor,
            demo.c1_invites_the_second_coordinator,
            demo.required_participants_are_present,
            demo.c2_suggests_the_vendor_deployer,
            demo.every_replica_converges,
            demo.the_joiners_add_their_notes,
            demo.both_vendors_run_the_fix_lifecycle,
            demo.v1_publishes_then_the_others,
            demo.all_five_close_the_case,
        )

    def test_c1_and_v1_are_seated_under_the_family_role_names(self):
        """One copy of the opening serves ``rcv`` and ``rcvcv`` alike."""
        assert demo.C1 == COORDINATOR
        assert demo.V1 == VENDOR
        # The devlogs and the CLI keep the scenario's own names (DEMOMA-19-018).
        assert [role.name for role in demo.ROLES][:3] == [
            "reporter",
            "c1",
            "v1",
        ]


# ---------------------------------------------------------------------------
# The character actors are seeded after the branch point (DEMOCI-11-018)
# ---------------------------------------------------------------------------


def _functions_referencing(module, name: str) -> list[str]:
    """The names of *module*'s functions whose body mentions *name*."""
    tree = ast.parse(inspect.getsource(module))
    return [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and any(
            isinstance(child, ast.Name) and child.id == name
            for child in ast.walk(node)
        )
    ]


class TestCharacterActorsSeededAfterTheBranchPoint:
    """C2 and V2 are seeded by the fragment that brings them in.

    Every actor and peer record written before the case exists is one more
    read of the recording clock, so seeding the two character actors in the
    shared opening would move the first ledger entry's timestamp away from
    ``rcv``'s and break the byte identity of the shared stretch
    (DEMOCI-11-018, #5532).
    """

    def test_the_opening_seeds_only_the_three_fixed_role_containers(self):
        """``open_cast`` resets five containers and seeds three of them."""
        clients = {name: mock_client() for name in _CAST}
        case_actor_client = mock_client()
        seeded = [mock_actor(f"urn:test:{name}") for name in _CAST[:3]]
        captured: dict[str, object] = {}

        with (
            patch.object(demo, "run_story") as run_story,
            patch.object(
                coordinated_story,
                "reset_datalayer",
                return_value={"status": "ok"},
            ) as reset,
            patch(
                "vultron.demo.helpers.seeding.seed_case_actor_identity"
            ) as reseed,
            patch.object(
                coordinated_story,
                "seed_containers_rcv",
                return_value=tuple(seeded),
            ) as seed_three,
            patch.object(
                coordinated_story, "get_actor_by_id", side_effect=list(seeded)
            ),
            patch.object(demo, "seed_containers_rcvcv") as seed_five,
        ):
            demo.run_rcvcv_demo(
                reporter_client=clients[REPORTER],
                c1_client=clients[demo.C1],
                v1_client=clients[demo.V1],
                c2_client=clients[demo.C2],
                v2_client=clients[demo.V2],
                case_actor_client=case_actor_client,
                reporter_id="urn:test:reporter",
                c1_id="urn:test:c1",
                v1_id="urn:test:v1",
                c2_id="urn:test:c2",
                v2_id="urn:test:v2",
            )
            # run_story() is what plays the story; the cast opening is the
            # callable it is handed, so the test runs that and nothing else.
            open_cast = run_story.call_args.args[2]
            captured["state"] = open_cast(MagicMock())

        # Every container the run touches starts clean (DEMOMA-01-003), the
        # character actors' included, and the dedicated case-actor container's
        # identity is re-seeded after its wipe (#1876).
        assert [c.kwargs["client"] for c in reset.call_args_list] == [
            clients[REPORTER],
            clients[demo.C1],
            clients[demo.V1],
            clients[demo.C2],
            clients[demo.V2],
            case_actor_client,
        ]
        reseed.assert_called_once_with(case_actor_client)

        # Only the three fixed-role containers are seeded, and the five-party
        # seeding has not run at all.
        seed_three.assert_called_once()
        seeding = seed_three.call_args.kwargs
        assert seeding["reporter_client"] is clients[REPORTER]
        assert seeding["coordinator_client"] is clients[demo.C1]
        assert seeding["vendor_client"] is clients[demo.V1]
        seed_five.assert_not_called()

        state = captured["state"]
        assert sorted(state.cast) == sorted(_CAST[:3])
        assert sorted(state.unseated) == sorted([demo.C2, demo.V2])
        assert state.container(demo.C2).client is clients[demo.C2]
        assert state.container(demo.C2).actor_id == "urn:test:c2"
        assert state.container(demo.V2).client is clients[demo.V2]
        assert state.container(demo.V2).actor_id == "urn:test:v2"

    def test_the_character_fragment_is_the_only_caller_of_the_seeding(self):
        """Nothing else in the module may seed the five containers.

        A second call site — in particular one reachable from the shared
        opening — is how the recording would drift from ``rcv``'s again.
        """
        assert _functions_referencing(demo, "seed_containers_rcvcv") == [
            "seed_the_second_coordinator_and_vendor"
        ]

    def test_the_seeding_fragment_follows_the_coordinators_choice(self):
        """It is placed after the ``coordinator-after-answer`` choice."""
        items = demo.STORY.items
        branch = items.index(
            choose(
                "coordinator-after-answer", "invite-coordinator", by=demo.C1
            )
        )
        seeding = items.index(demo.seed_the_second_coordinator_and_vendor)
        assert branch < seeding, (
            "seed_the_second_coordinator_and_vendor must run after C1's"
            " choice: every record it writes before the case opens moves the"
            " first ledger entry's timestamp (DEMOCI-11-018)"
        )
        assert seeding >= _PREFIX_LEN, (
            "the shared opening must not reach the five-party seeding"
        )

    def test_the_fragment_seeds_all_five_then_seats_c2_and_v2(self):
        """The three already seeded are re-seeded idempotently.

        ``seed_containers_rcvcv`` registers every actor as a peer of the other
        four (DEMOMA-19-002, DEMOMA-19-012), which needs all five clients;
        ``POST /actors/`` and the peer registrations are idempotent, so the
        three the opening seeded come back unchanged.
        """
        state = story_state(*_CAST[:3], unseated=(demo.C2, demo.V2))
        seeded = tuple(mock_actor(f"urn:test:{name}") for name in _CAST)
        # The waiting containers are consumed by the seating, so hold them.
        waiting = {name: state.container(name) for name in (demo.C2, demo.V2)}

        with (
            patch.object(
                demo, "seed_containers_rcvcv", return_value=seeded
            ) as seed,
            patch.object(
                coordinated_story,
                "get_actor_by_id",
                side_effect=[seeded[3], seeded[4]],
            ) as lookup,
            _no_banners(),
        ):
            demo.seed_the_second_coordinator_and_vendor(state)

        kwargs = seed.call_args.kwargs
        assert kwargs["reporter_client"] is state.client(REPORTER)
        assert kwargs["c1_client"] is state.client(demo.C1)
        assert kwargs["v1_client"] is state.client(demo.V1)
        assert kwargs["c2_client"] is waiting[demo.C2].client
        assert kwargs["v2_client"] is waiting[demo.V2].client
        assert kwargs["case_actor_client"] is state.case_actor_client
        # The deterministic ids come from the waiting containers, which hold
        # the --c2-id / --v2-id values the run was given.
        assert kwargs["c2_actor_id"] == "urn:test:c2"
        assert kwargs["v2_actor_id"] == "urn:test:v2"

        # Each new actor is read back from its own container (ADR-0073).
        assert [c.args[0] for c in lookup.call_args_list] == [
            state.client(demo.C2),
            state.client(demo.V2),
        ]
        assert state.unseated == {}
        assert state.actor_id(demo.C2) == "urn:test:c2"
        assert state.actor_id(demo.V2) == "urn:test:v2"

    def test_a_container_that_was_never_declared_stops_the_story(self):
        """Seating reads the container the scenario declared, or raises."""
        state = story_state(*_CAST[:3], unseated=(demo.C2,))
        with (
            patch.object(
                demo,
                "seed_containers_rcvcv",
                return_value=tuple(
                    mock_actor(f"urn:test:{name}") for name in _CAST
                ),
            ),
            patch.object(coordinated_story, "get_actor_by_id"),
            _no_banners(),
            pytest.raises(DemoStoryError, match="no container waiting"),
        ):
            demo.seed_the_second_coordinator_and_vendor(state)


# ---------------------------------------------------------------------------
# C2 joins as a coordinator, and runs no RM triage (DEMOMA-17-002)
# ---------------------------------------------------------------------------


class TestC1InvitesTheSecondCoordinator:
    """C2's join is one invite chain with no report triage after it."""

    def _invite_c2(self, state, *, run_then: bool = False):
        """Run the fragment with the shared invite chain stubbed out.

        With *run_then* the chain's ``then`` callback is run while the
        collaborators are still patched, which is how a non-triaging
        invitee's roster check is reached.
        """
        with (
            patch.object(coordinated_story, "run_case_invite_chain") as chain,
            patch.object(
                coordinated_story, "run_invite_path_rm_triage"
            ) as triage,
            patch.object(
                coordinated_story, "wait_for_case_participants"
            ) as roster,
            patch_chain_shared(
                coordinated_story, "wait_for_case_on_container"
            ) as replica_wait,
            _no_banners(),
        ):
            demo.c1_invites_the_second_coordinator(state)
            then = chain.call_args.kwargs["then"]
            assert then is not None, (
                "a non-triaging invitee's roster check runs as the chain's"
                " `then`, inside its delivery gate"
            )
            # Nothing has checked the roster yet: the check is the chain's to
            # run, so a failed invite skips it.
            roster.assert_not_called()
            if run_then:
                then()
        return chain, triage, roster, replica_wait

    @pytest.mark.spec("DEMOMA-17-002")
    def test_c2_runs_no_rm_triage(self):
        """C2 joins to help coordinate, so it engages no case of its own.

        Giving it one put an extra ``engage_case`` act in the ledger and
        changed the recording; the roster check runs inside the chain's own
        gate instead, so a failed invite still skips it.
        """
        state = _five_party_state()
        _, triage, roster, _ = self._invite_c2(state, run_then=True)

        triage.assert_not_called()
        assert roster.call_args.kwargs["vendor_client"] is state.client(
            demo.C1
        )
        assert roster.call_args.kwargs["expected_actor_ids"] == {
            state.actor_id(who)
            for who in (REPORTER, demo.C1, demo.V1, demo.C2)
        }

    def test_the_invite_offers_the_coordinator_role_from_c1(self):
        """C1, the Case Owner, invites C2 as ``CVDRole.COORDINATOR``."""
        state = _five_party_state()
        chain, _, _, _ = self._invite_c2(state)

        kwargs = chain.call_args.kwargs
        assert kwargs["invitee_name"] == demo.C2_LABEL
        assert kwargs["invitee_client"] is state.client(demo.C2)
        assert kwargs["invitee"] is state.actor(demo.C2).actor
        assert kwargs["inviter"].client is state.client(demo.C1)
        assert kwargs["inviter"].role is CVDRole.COORDINATOR
        # The CASE_MANAGER's store is on the dedicated case-actor container
        # (DEMOMA-06-005): a C1 client cannot address it.
        assert kwargs["case_manager_client"] is state.case_actor_client

    @pytest.mark.spec("CLP-08-005")
    def test_the_reporter_holds_the_case_before_c2_answers(self):
        """Bug #2135: the join broadcasts to every participant.

        C2's reply to the full-case Invite broadcasts
        ``Announce(CaseLedgerEntry)`` to all participants, so a Reporter
        without the case has no genesis hash to anchor the chain on.
        """
        state = _five_party_state()
        _, _, _, replica_wait = self._invite_c2(state)

        assert [c.kwargs["client"] for c in replica_wait.call_args_list] == [
            state.client(REPORTER)
        ]


# ---------------------------------------------------------------------------
# V2 arrives through the ADR-0026 suggestion chain (DEMOMA-19-009)
# ---------------------------------------------------------------------------


@pytest.mark.spec("DEMOMA-19-009")
class TestC2SuggestsTheVendorDeployer:
    """C2 suggests, C1 approves, the CaseActor invites, V2 accepts."""

    def test_the_chain_runs_suggest_then_approve_then_invite_and_triage(self):
        """One ordered pass of the ADR-0026 flow, with its roles explicit."""
        state = _five_party_state()
        order: list[str] = []

        with (
            patch.object(
                ActorSession,
                "suggest_actor_to_case",
                autospec=True,
                side_effect=lambda *a, **kw: order.append("suggest"),
            ) as suggest,
            patch.object(
                ActorSession,
                "accept_actor_recommendation",
                autospec=True,
                side_effect=lambda *a, **kw: order.append("approve"),
            ) as approve,
            patch.object(
                demo,
                "find_cp_offer_for_case",
                return_value="urn:test:cp-offer",
            ) as cp_offer,
            patch.object(
                demo,
                "find_case_actor_participant_id",
                return_value="urn:test:case-actor-participant",
            ),
            patch.object(
                demo,
                "run_case_invite_chain",
                side_effect=lambda **kw: order.append("invite-chain"),
            ) as chain,
            patch.object(
                demo,
                "invitee_triages_after_joining",
                side_effect=lambda *a, **kw: order.append("triage"),
            ) as triage,
            patch_chain_shared(
                coordinated_story, "wait_for_case_on_container"
            ),
            _no_banners(),
        ):
            demo.c2_suggests_the_vendor_deployer(state)

        assert order == ["suggest", "approve", "invite-chain", "triage"]

        # Roles must be explicit, or EvaluateDefaultRolesNode falls back to
        # the hardcoded [VENDOR] default and V2 never reaches VFD (#1969).
        assert suggest.call_args.kwargs == {
            "suggested_actor_id": state.actor_id(demo.V2),
            "roles": [CVDRole.VENDOR, CVDRole.DEPLOYER],
        }
        assert suggest.call_args.args[0].actor is state.actor(demo.C2).actor
        assert approve.call_args.args[0].actor is state.actor(demo.C1).actor
        assert approve.call_args.kwargs == {
            "cp_offer_id": "urn:test:cp-offer",
            "case_actor_id": "urn:test:case-actor-participant",
        }
        # The recommendation is polled for on C1's own container.
        assert cp_offer.call_args.kwargs["client"] is state.client(demo.C1)

        # The CaseActor invites on its own, so the chain is given no inviter
        # and reads the canonical ledger through the case-actor container.
        kwargs = chain.call_args.kwargs
        assert "inviter" not in kwargs
        assert kwargs["ledger_client"] is state.case_actor_client
        assert kwargs["invitee_client"] is state.client(demo.V2)
        assert kwargs["invitee"] is state.actor(demo.V2).actor

        # V2 arrives through four hops, so its waits get the multi-hop budget.
        assert kwargs["invite_timeout"] == demo.LATE_JOIN_TIMEOUT
        assert kwargs["replica_timeout"] == demo.LATE_JOIN_TIMEOUT
        assert kwargs["reply_timeout"] == demo.LATE_JOIN_TIMEOUT
        assert triage.call_args.kwargs == {
            "seated": (REPORTER, demo.C1, demo.V1, demo.C2, demo.V2),
            "join_timeout": LATE_JOINER_TIMEOUT,
            "triage_timeout": demo.LATE_JOIN_TIMEOUT,
        }

    def test_the_approval_is_skipped_when_the_recommendation_never_arrives(
        self,
    ):
        """ADR-0058: the Offer is the approval's causal precondition.

        The real ``demo_gate`` runs: a lookup timeout must record one failure
        and skip the approval and the whole invite chain under it, rather than
        approving an Offer id that is ``None``.
        """
        state = _five_party_state()

        with (
            patch.object(ActorSession, "suggest_actor_to_case"),
            patch.object(
                ActorSession, "accept_actor_recommendation"
            ) as approve,
            patch.object(
                demo,
                "find_cp_offer_for_case",
                side_effect=AssertionError(
                    "timed out polling for Offer(CaseParticipant)"
                ),
            ),
            patch.object(
                demo,
                "find_case_actor_participant_id",
                return_value="urn:test:case-actor-participant",
            ),
            patch.object(demo, "run_case_invite_chain") as chain,
            patch.object(demo, "invitee_triages_after_joining") as triage,
            patch_chain_shared(
                coordinated_story, "wait_for_case_on_container"
            ),
        ):
            demo.c2_suggests_the_vendor_deployer(state)

        approve.assert_not_called()
        # The chain and the triage sit outside the gate, so the caller still
        # reaches them; what the gate owns is the approval.
        assert chain.called
        assert triage.called
        assert [f for f in demo_utils._demo_failures if "GATE FAILED" in f], (
            f"the closed gate must record one failure: "
            f"{demo_utils._demo_failures!r}"
        )

    def test_a_missing_case_actor_participant_is_reported_not_raised(self):
        """The Accept has nowhere to route back to, so the gate records it."""
        state = _five_party_state()

        with (
            patch.object(ActorSession, "suggest_actor_to_case"),
            patch.object(
                ActorSession, "accept_actor_recommendation"
            ) as approve,
            patch.object(
                demo,
                "find_cp_offer_for_case",
                return_value="urn:test:cp-offer",
            ),
            patch.object(
                demo, "find_case_actor_participant_id", return_value=None
            ),
            patch.object(demo, "run_case_invite_chain"),
            patch.object(demo, "invitee_triages_after_joining"),
            patch_chain_shared(
                coordinated_story, "wait_for_case_on_container"
            ),
        ):
            demo.c2_suggests_the_vendor_deployer(state)

        approve.assert_not_called()
        assert any(
            "GATE FAILED" in f and "cannot route Accept" in f
            for f in demo_utils._demo_failures
        ), demo_utils._demo_failures

    def test_v2_accepts_the_invite_the_case_actor_delivered(self):
        """The last hop: V2 answers the Invite found in its own container.

        The real invite chain runs, so the Invite is located by polling V2's
        DataLayer and the Accept is puppeteered from V2's own container — no
        mail-carrying and no inbox injection (DEMOMA-19-022).
        """
        state = _five_party_state()

        with (
            patch.object(ActorSession, "suggest_actor_to_case"),
            patch.object(ActorSession, "accept_actor_recommendation"),
            patch.object(
                ActorSession, "accept_case_invite", autospec=True
            ) as accept,
            patch.object(
                demo,
                "find_cp_offer_for_case",
                return_value="urn:test:cp-offer",
            ),
            patch.object(
                demo,
                "find_case_actor_participant_id",
                return_value="urn:test:case-actor-participant",
            ),
            patch.object(
                invite_chain,
                "find_case_invite_for_actor",
                return_value="urn:test:v2-invite",
            ) as find_invite,
            patch.object(demo, "invitee_triages_after_joining"),
            patch_chain_shared(
                coordinated_story, "wait_for_case_on_container"
            ) as replica_wait,
        ):
            demo.c2_suggests_the_vendor_deployer(state)

        assert find_invite.call_args.kwargs["client"] is state.client(demo.V2)
        assert find_invite.call_args.kwargs["invitee_id"] == state.actor_id(
            demo.V2
        )
        accept.assert_called_once()
        assert accept.call_args.args[0].client is state.client(demo.V2)
        assert accept.call_args.kwargs == {"invite_id": "urn:test:v2-invite"}
        # The Accept seeds V2's case replica, which the chain then waits for.
        assert [
            c
            for c in replica_wait.call_args_list
            if c.kwargs.get("client") is state.client(demo.V2)
        ]

    def test_v2_never_accepts_an_invite_that_was_not_delivered(self):
        """#3038: the answer nests inside the Invite's delivery gate."""
        state = _five_party_state()

        with (
            patch.object(ActorSession, "suggest_actor_to_case"),
            patch.object(ActorSession, "accept_actor_recommendation"),
            patch.object(ActorSession, "accept_case_invite") as accept,
            patch.object(
                demo,
                "find_cp_offer_for_case",
                return_value="urn:test:cp-offer",
            ),
            patch.object(
                demo,
                "find_case_actor_participant_id",
                return_value="urn:test:case-actor-participant",
            ),
            patch.object(
                invite_chain,
                "find_case_invite_for_actor",
                side_effect=AssertionError("timed out polling for Invite"),
            ),
            patch.object(demo, "invitee_triages_after_joining"),
            patch_chain_shared(
                coordinated_story, "wait_for_case_on_container"
            ) as replica_wait,
        ):
            demo.c2_suggests_the_vendor_deployer(state)

        accept.assert_not_called()
        assert not [
            c
            for c in replica_wait.call_args_list
            if c.kwargs.get("client") is state.client(demo.V2)
        ], (
            "V2's replica wait depends on the Accept, so the closed gate must"
            f" skip it: {replica_wait.call_args_list!r}"
        )

    @pytest.mark.spec("CLP-08-005")
    def test_the_reporter_holds_the_case_before_v2s_triage(self):
        """Bug #2120: V2's triage broadcasts to the Reporter too."""
        state = _five_party_state()
        order: list[str] = []

        def _wait_for_case(client, case_id, **_kwargs):
            if client is state.client(REPORTER):
                order.append("reporter_wait")

        with (
            patch.object(ActorSession, "suggest_actor_to_case"),
            patch.object(ActorSession, "accept_actor_recommendation"),
            patch.object(
                demo,
                "find_cp_offer_for_case",
                return_value="urn:test:cp-offer",
            ),
            patch.object(
                demo,
                "find_case_actor_participant_id",
                return_value="urn:test:case-actor-participant",
            ),
            patch.object(demo, "run_case_invite_chain"),
            patch.object(
                coordinated_story,
                "run_invite_path_rm_triage",
                side_effect=lambda **_kw: order.append("triage"),
            ),
            patch.object(coordinated_story, "wait_for_case_participants"),
            patch_chain_shared(
                coordinated_story,
                "wait_for_case_on_container",
                side_effect=_wait_for_case,
            ),
            _no_banners(),
        ):
            demo.c2_suggests_the_vendor_deployer(state)

        assert "reporter_wait" in order, (
            "wait_for_case_on_container(reporter_client) was never called"
            " before V2's triage"
        )
        assert "triage" in order, "run_invite_path_rm_triage was never called"
        assert order.index("reporter_wait") < order.index("triage"), (
            f"the Reporter's case-replica wait must precede V2's RM triage;"
            f" order was {order} — Bug #2120 (CLP-08-005)"
        )

    def test_v2s_triage_reads_the_case_manager_on_the_case_actor(self):
        """The authority for the triage's waits is the canonical store."""
        state = _five_party_state()

        with (
            patch.object(ActorSession, "suggest_actor_to_case"),
            patch.object(ActorSession, "accept_actor_recommendation"),
            patch.object(
                demo,
                "find_cp_offer_for_case",
                return_value="urn:test:cp-offer",
            ),
            patch.object(
                demo,
                "find_case_actor_participant_id",
                return_value="urn:test:case-actor-participant",
            ),
            patch.object(demo, "run_case_invite_chain"),
            patch.object(
                coordinated_story, "run_invite_path_rm_triage"
            ) as triage,
            patch.object(coordinated_story, "wait_for_case_participants"),
            patch_chain_shared(
                coordinated_story, "wait_for_case_on_container"
            ),
            _no_banners(),
        ):
            demo.c2_suggests_the_vendor_deployer(state)

        assert (
            triage.call_args.kwargs["auth_client"] is state.case_actor_client
        )
        assert triage.call_args.kwargs["invited_client"] is state.client(
            demo.V2
        )


# ---------------------------------------------------------------------------
# The replica drain and the five-replica sync phase (DEMOMA-23-005, #3906)
# ---------------------------------------------------------------------------


class TestReplicasDrainBeforeTheSecondCoordinator:
    """The opening's drain goes through the one shared coverage helper.

    It was the last private copy of the
    read-authority-tail-then-poll-each-replica loop outside
    ``vultron/demo/helpers/sync.py`` (#3906), and it inherits the helper's
    behaviour when the authority holds no entries: one recorded gate failure
    naming the authority (EDF-06-005), where the private drain returned
    silently.
    """

    def test_the_drain_names_c1_as_authority_and_the_openings_replicas(self):
        """Only the Reporter and V1 hold a replica before C2 joins."""
        state = _five_party_state()

        with patch.object(
            demo, "wait_for_replica_ledger_coverage"
        ) as coverage:
            demo.replicas_drain_before_the_second_coordinator(state)

        coverage.assert_called_once()
        kwargs = coverage.call_args.kwargs
        assert kwargs["auth_client"] is state.client(demo.C1)
        assert kwargs["replicas"] == [
            (state.client(REPORTER), "Reporter"),
            (state.client(demo.V1), "V1"),
        ]
        assert kwargs["case_id"] == state.case.id_
        assert kwargs["phase_label"] == "opening drain before C2 joins"
        # The drain is the helper's default causal gate; the scenario must not
        # downgrade it to a temporal check or hand it a late joiner.
        assert "causal" not in kwargs
        assert "late_joiners" not in kwargs

    def test_an_empty_authority_ledger_is_one_failure_naming_the_authority(
        self,
    ):
        """The fault is the writer's, not the fan-out's (EDF-06-005).

        The real ``wait_for_replica_ledger_coverage`` and the real
        ``demo_gate`` run; only the authority-tail read and the per-replica
        primitive are stubbed, so the recorded message is the helper's own.
        """
        import vultron.demo.helpers.sync as sync_module

        state = _five_party_state()
        state.client(demo.C1).base_url = "http://c1.test/api/v2"

        with (
            patch.object(
                sync_module, "_get_log_entries_for_case", return_value=[]
            ),
            patch.object(
                sync_module, "wait_for_contiguous_ledger_coverage"
            ) as per_replica,
        ):
            demo.replicas_drain_before_the_second_coordinator(state)

        per_replica.assert_not_called()
        (failure,) = demo_utils._demo_failures
        assert failure.startswith("GATE FAILED")
        assert "http://c1.test/api/v2" in failure
        assert "opening drain before C2 joins" in failure
        assert "holds no CaseLedgerEntry" in failure
        for label in ("Reporter", "V1"):
            assert label not in failure, failure


class TestEveryReplicaConverges:
    """All five replicas are verified against C1, V2 as the late joiner."""

    def test_the_sync_phase_declares_every_replica_and_the_late_joiner(self):
        """The helper declares no scenario facts; the fragment supplies them."""
        state = _five_party_state()

        with patch.object(demo, "run_sync_verification_phase") as phase:
            demo.every_replica_converges(state)

        kwargs = phase.call_args.kwargs
        assert kwargs["auth_client"] is state.client(demo.C1)
        assert kwargs["auth_label"] == "C1"
        assert kwargs["auth_actor_id"] == state.actor_id(demo.C1)
        assert kwargs["reporter_client"] is state.client(REPORTER)
        assert kwargs["replicas"] == [
            (state.client(REPORTER), "Reporter"),
            (state.client(demo.V1), "V1"),
            (state.client(demo.C2), "C2"),
            (state.client(demo.V2), "V2"),
        ]
        assert kwargs["expected_participant_ids"] == {
            state.actor_id(who) for who in _CAST
        }
        # V2 joined after the opening completed, so it catches up from genesis
        # and gets the late-joiner budget (#2852).
        assert kwargs["late_joiners"] == (state.client(demo.V2),)
        assert kwargs["state_checks"] == [
            (state.client(REPORTER), "Reporter"),
            (state.client(demo.V2), "V2"),
        ]


class TestRequiredParticipantsArePresent:
    """M1 is re-run once C2 has joined, from C1's replica."""

    @pytest.mark.spec("VP-02-015")
    def test_the_milestone_reads_c1s_replica_and_the_reporters(self):
        """M1 is read from the Case Owner's replica, not the canonical case."""
        state = _five_party_state()

        with (
            patch.object(demo, "verify_case_active") as milestone,
            _no_banners(),
        ):
            demo.required_participants_are_present(state)

        kwargs = milestone.call_args.kwargs
        assert kwargs["receiver_client"] is state.client(demo.C1)
        assert kwargs["reporter_client"] is state.client(REPORTER)
        assert kwargs["case_id"] == state.case.id_
        assert kwargs["receiver_actor_id"] == state.actor_id(demo.C1)
        assert kwargs["reporter_actor_id"] == state.actor_id(REPORTER)


# ---------------------------------------------------------------------------
# The joiners answer the thread the opening posted (DEMOCI-11-017)
# ---------------------------------------------------------------------------


class TestTheJoinersAddTheirNotes:
    """C2 and V2 reply to the note the shared opening kept as a prop."""

    def _answer(self) -> as_Note:
        return as_Note(
            id_="urn:test:timeline-answer",
            name="Coordinator Summary",
            content="Target disclosure in 30 days.",
        )

    def test_the_joiners_reply_to_the_kept_timeline_answer(self):
        """One thread, not two: the opening's thread is continued.

        The note comes off the state as the ``TIMELINE_ANSWER`` prop, so no
        earlier fragment has to hand it along a phase-function return value.
        """
        state = _five_party_state()
        answer = self._answer()
        state.keep(TIMELINE_ANSWER, answer)

        with patch.object(demo, "add_note_thread") as thread:
            demo.the_joiners_add_their_notes(state)

        watching_client, case, posts = thread.call_args.args
        assert watching_client is state.client(demo.C1)
        assert case is state.case
        assert thread.call_args.kwargs["in_reply_to"] is answer
        # Each joiner posts from its own container.
        assert [post.poster.client for post in posts] == [
            state.client(demo.C2),
            state.client(demo.V2),
        ]
        assert [post.poster.actor for post in posts] == [
            state.actor(demo.C2).actor,
            state.actor(demo.V2).actor,
        ]

    def test_an_unanswered_thread_stops_the_story_instead_of_posting(self):
        """A fragment reads a prop through an accessor that raises.

        The opening keeps nothing when its own thread failed, so this
        fragment stops the story rather than opening a thread of its own
        (``run_story`` records it under the first failure).
        """
        state = _five_party_state()

        with (
            patch.object(demo, "add_note_thread") as thread,
            pytest.raises(DemoStoryError, match="answered timeline note"),
        ):
            demo.the_joiners_add_their_notes(state)

        thread.assert_not_called()


# ---------------------------------------------------------------------------
# The fix lifecycle: V1 → VFd, V2 → VFD (DEMOMA-19-004/015/016)
# ---------------------------------------------------------------------------


@pytest.mark.spec("DEMOMA-19-004")
@pytest.mark.spec("DEMOMA-19-015")
@pytest.mark.spec("DEMOMA-19-016")
class TestBothVendorsRunTheFixLifecycle:
    """V1 stops at VFd; V2 goes on to VFD.

    V1 holds ``CVDRole.VENDOR`` only and V2 holds ``VENDOR`` and
    ``DEPLOYER``, which is the distinction this scenario exists to exercise:
    ``verify_fix_ready`` requires VENDOR and ``verify_fix_deployed`` requires
    DEPLOYER, so calling either with the wrong actor would exercise the wrong
    guard and mask a weakened BT gate.
    """

    def _run(self, state, *, order=None, rm_wait=None):
        """Run the fragment, recording every verb and verification.

        The per-vendor half — the RM gate, the trigger and the vendor's own VF
        check — is the shared ``vendor_notifies_fix_ready`` (#5534), which
        resolves its polls in ``coordinated_story``; the coordinator-side
        milestones this scenario batches over both vendors resolve theirs
        here.  Both modules are patched, because a patch on one alone would
        leave the other polling a stand-in client.
        """
        order = [] if order is None else order
        with (
            patch.object(
                coordinated_story,
                "wait_for_participant_rm_state",
                side_effect=rm_wait or (lambda **_kw: order.append("rm_wait")),
            ),
            patch.object(coordinated_story, "wait_for_participant_vf_state"),
            patch.object(demo, "wait_for_participant_vf_state"),
            patch.object(demo, "wait_for_participant_d_state"),
            patch.object(demo, "verify_fix_ready") as fix_ready,
            patch.object(demo, "verify_fix_deployed") as fix_deployed,
            patch.object(
                ActorSession,
                "notify_fix_ready",
                autospec=True,
                side_effect=lambda session: order.append(
                    f"ready:{session.actor.id_}"
                ),
            ) as notify_ready,
            patch.object(
                ActorSession,
                "notify_fix_deployed",
                autospec=True,
                side_effect=lambda session: order.append(
                    f"deployed:{session.actor.id_}"
                ),
            ) as notify_deployed,
            _no_banners(),
        ):
            demo.both_vendors_run_the_fix_lifecycle(state)
        return {
            "order": order,
            "fix_ready": fix_ready,
            "fix_deployed": fix_deployed,
            "notify_ready": notify_ready,
            "notify_deployed": notify_deployed,
        }

    def test_both_vendors_report_fix_ready_and_only_v2_deploys(self):
        """Each vendor runs the lifecycle its role set allows."""
        state = _five_party_state()
        ran = self._run(state)

        assert _sessions_of(ran["notify_ready"]) == [
            state.actor_id(demo.V1),
            state.actor_id(demo.V2),
        ]
        assert _sessions_of(ran["notify_deployed"]) == [
            state.actor_id(demo.V2)
        ], "V1 holds no DEPLOYER role, so it must never deploy (CSB-15-002)"

    def test_the_deploy_report_follows_both_fix_ready_reports(self):
        """V2's d→D step comes after the VFd pair, not between them."""
        state = _five_party_state()
        order = self._run(state)["order"]

        ready = [i for i, step in enumerate(order) if step.startswith("ready")]
        deployed = [
            i for i, step in enumerate(order) if step.startswith("deployed")
        ]
        assert ready and deployed, order
        assert max(ready) < min(deployed), order

    def test_neither_verification_is_called_with_the_wrong_role(self):
        """DEMOMA-19-016, stated as the two sets of actor ids."""
        state = _five_party_state()
        ran = self._run(state)

        ready_actors = {
            c.kwargs["receiver_actor_id"]
            for c in ran["fix_ready"].call_args_list
        }
        deployed_actors = {
            c.kwargs["receiver_actor_id"]
            for c in ran["fix_deployed"].call_args_list
        }
        assert ready_actors == {
            state.actor_id(demo.V1),
            state.actor_id(demo.V2),
        }
        assert deployed_actors == {state.actor_id(demo.V2)}
        assert state.actor_id(demo.V1) not in deployed_actors, (
            "verify_fix_deployed must not be called with a VENDOR-only actor"
        )

    def test_each_vendor_is_gated_on_its_own_rm_state(self):
        """CSB-18-001: notify-fix-ready needs RM out of triage first."""
        state = _five_party_state()
        order: list[str] = []
        rm_calls: list[dict] = []

        def _rm_wait(**kwargs):
            rm_calls.append(kwargs)
            order.append(f"rm_wait:{kwargs['actor_id']}")

        self._run(state, order=order, rm_wait=_rm_wait)

        assert [c["actor_id"] for c in rm_calls] == [
            state.actor_id(demo.V1),
            state.actor_id(demo.V2),
        ]
        assert all(
            c["expected_states"] == {RM.ACCEPTED, RM.DEFERRED, RM.CLOSED}
            for c in rm_calls
        ), rm_calls
        for name in (demo.V1, demo.V2):
            actor_id = state.actor_id(name)
            assert f"rm_wait:{actor_id}" in order, order
            assert f"ready:{actor_id}" in order, order
            assert order.index(f"rm_wait:{actor_id}") < order.index(
                f"ready:{actor_id}"
            ), order

    def test_the_milestones_watch_both_coordinator_side_replicas(self):
        """M5/M6 are read on C1's and the Reporter's replicas.

        ``rcv``'s own fix-ready fragment checks the Coordinator's view twice
        for its one Vendor; this scenario checks both vendors on both
        coordinator-side replicas, which is why it is its own fragment.
        """
        state = _five_party_state()

        with (
            patch.object(coordinated_story, "wait_for_participant_rm_state"),
            patch.object(coordinated_story, "wait_for_participant_vf_state"),
            patch.object(demo, "wait_for_participant_vf_state") as vf_wait,
            patch.object(demo, "wait_for_participant_d_state") as d_wait,
            patch.object(demo, "verify_fix_ready"),
            patch.object(demo, "verify_fix_deployed"),
            patch.object(ActorSession, "notify_fix_ready"),
            patch.object(ActorSession, "notify_fix_deployed"),
            _no_banners(),
        ):
            demo.both_vendors_run_the_fix_lifecycle(state)

        watched_vf = {
            (c.kwargs["client"], c.kwargs["actor_id"])
            for c in vf_wait.call_args_list
        }
        for watcher in (demo.C1, REPORTER):
            for name in (demo.V1, demo.V2):
                assert (
                    state.client(watcher),
                    state.actor_id(name),
                ) in watched_vf
        assert all(
            c.kwargs["expected_states"] == {CS_vf.VF}
            for c in vf_wait.call_args_list
        )
        watched_d = {
            (c.kwargs["client"], c.kwargs["actor_id"])
            for c in d_wait.call_args_list
        }
        for watcher in (demo.C1, REPORTER):
            assert (
                state.client(watcher),
                state.actor_id(demo.V2),
            ) in watched_d
        assert all(
            c.kwargs["expected_states"] == {CS_d.D}
            for c in d_wait.call_args_list
        ), "only V2 reaches d→D; V1 has no deploy step"
        assert not [
            c
            for c in d_wait.call_args_list
            if c.kwargs["actor_id"] == state.actor_id(demo.V1)
        ], "V1's d state is never waited on: it has no DEPLOYER role"


# ---------------------------------------------------------------------------
# Publication order and the embargo teardown (DEMOMA-19-005)
# ---------------------------------------------------------------------------


@pytest.mark.spec("DEMOMA-19-005")
class TestV1PublishesThenTheOthers:
    """V1 publishes first and the teardown is awaited before V2 does.

    V1 publishing first tests a teardown started by a VENDOR participant that
    is not the Case Owner (RSH-03-002).  If V2 published before the teardown
    committed the two publications would race and the ledger order would
    change from run to run.
    """

    def _run(self, state):
        order: list[str] = []
        with (
            patch.object(
                demo,
                "wait_for_case_em_terminated",
                side_effect=lambda client, case_id: order.append(
                    f"em_exited:{_client_name(state, client)}"
                ),
            ),
            patch.object(demo, "wait_for_participant_vf_state"),
            patch.object(demo, "wait_for_participant_d_state"),
            patch.object(demo, "verify_publicly_disclosed") as disclosed,
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
            demo.v1_publishes_then_the_others(state)
        return order, disclosed

    def test_v1_publishes_first_with_the_teardown_awaited_before_v2(self):
        """The whole publication order, so a reordering shows as a diff."""
        state = _five_party_state()
        order, _ = self._run(state)

        assert order == [
            f"published:{state.actor_id(demo.V1)}",
            "em_exited:v1",
            f"published:{state.actor_id(demo.V2)}",
            f"published:{state.actor_id(demo.C2)}",
            f"published:{state.actor_id(demo.C1)}",
            "em_exited:reporter",
            f"published:{state.actor_id(REPORTER)}",
            "em_exited:reporter",
        ], order

    def test_the_closing_milestone_reads_v1_at_vf_and_v2_at_d(self):
        """M7 confirms the two vendors ended on their own paths."""
        state = _five_party_state()

        with (
            patch.object(demo, "wait_for_case_em_terminated"),
            patch.object(demo, "wait_for_participant_vf_state") as vf_wait,
            patch.object(demo, "wait_for_participant_d_state") as d_wait,
            patch.object(demo, "verify_publicly_disclosed") as disclosed,
            patch.object(ActorSession, "notify_published"),
            _no_banners(),
        ):
            demo.v1_publishes_then_the_others(state)

        assert vf_wait.call_args.kwargs["client"] is state.client(demo.C1)
        assert vf_wait.call_args.kwargs["actor_id"] == state.actor_id(demo.V1)
        assert vf_wait.call_args.kwargs["expected_states"] == {CS_vf.VF}
        assert d_wait.call_args.kwargs["actor_id"] == state.actor_id(demo.V2)
        assert d_wait.call_args.kwargs["expected_states"] == {CS_d.D}
        assert disclosed.call_args.kwargs["receiver_client"] is state.client(
            demo.C1
        )
        assert disclosed.call_args.kwargs[
            "receiver_actor_id"
        ] == state.actor_id(demo.C1)


def _client_name(state, client) -> str:
    """The devlogs name of the cast member *client* belongs to."""
    for devlogs_name, member in demo.DEVLOG_REPLICAS:
        if state.client(member) is client:
            return devlogs_name
    return "unknown"


# ---------------------------------------------------------------------------
# Closure: C1, the Case Owner, leaves last (CM-23-015)
# ---------------------------------------------------------------------------


class TestAllFiveCloseTheCase:
    """Four participants leave in order, then the Case Owner."""

    def test_c1_leaves_last_and_the_departures_are_read_on_the_case_actor(
        self,
    ):
        """The owner's ``Leave`` is gated on the CASE_MANAGER's store.

        That store lives on the dedicated case-actor container
        (DEMOMA-06-005), so the authority client must be that one and not
        C1's own.
        """
        state = _five_party_state()

        with (
            patch.object(ActorSession, "leave_case"),
            stub_closure_gate(),
            patch.object(
                coordinated_story, "close_case_owner_last"
            ) as closure,
        ):
            demo.all_five_close_the_case(state)

        kwargs = closure.call_args.kwargs
        assert kwargs["milestone"] == "M8"
        assert kwargs["authority_client"] is state.case_actor_client
        assert [leaver.client for leaver in kwargs["others"]] == [
            state.client(demo.V1),
            state.client(demo.V2),
            state.client(demo.C2),
            state.client(REPORTER),
        ]
        assert kwargs["owner"].client is state.client(demo.C1)
        assert kwargs["owner"].actor is state.actor(demo.C1).actor


# ---------------------------------------------------------------------------
# The devlogs the invariant harness reads (DEMOMA-19-018)
# ---------------------------------------------------------------------------


@pytest.mark.spec("DEMOMA-19-018")
class TestRcvcvLedgerDump:
    """Each replica is dumped under this scenario's own name for it."""

    def test_the_devlog_names_are_the_scenario_role_names(self):
        """``reporter``, ``c1``, ``v1``, ``c2``, ``v2`` — not cast names.

        C1 and V1 are seated under the family's role names, so the dump has
        to translate them back: the harness loads ``devlogs/rcvcv/c1``.
        """
        assert demo.DEVLOG_REPLICAS == (
            ("reporter", REPORTER),
            ("c1", demo.C1),
            ("v1", demo.V1),
            ("c2", demo.C2),
            ("v2", demo.V2),
        )

    def _dump(self, state):
        for name in state.cast:
            state.client(name).actor_id = f"https://example.org/actors/{name}"
        state.case_actor_client.actor_id = (
            "https://example.org/actors/case-actor"
        )
        with patch.object(coordinated_story, "dump_case_ledgers") as dump:
            demo._dump_ledgers(state)
        return dump.call_args.kwargs["targets"]

    def test_every_seated_replica_is_dumped_plus_the_canonical_ledger(self):
        """Five replicas in cast order, then the canonical ledger."""
        targets = self._dump(_five_party_state())

        assert [t.actor_name for t in targets] == [
            "reporter",
            "c1",
            "v1",
            "c2",
            "v2",
            "case-actor",
        ]
        # The canonical ledger is read on the dedicated container, never from
        # a participant's replica (DEMOMA-06-005).
        assert targets[-1].route_key == "case-actor"

    def test_a_character_actor_the_run_never_seated_is_left_out(self):
        """A failure before the seeding must not 404 the dump.

        The dump runs on the way out whether or not an earlier step failed
        (DEMOMA-23-003), and an unseated container holds no replica to read.
        """
        state = story_state(*_CAST[:3], case=mock_case())
        targets = self._dump(state)

        assert [t.actor_name for t in targets] == [
            "reporter",
            "c1",
            "v1",
            "case-actor",
        ]


# ---------------------------------------------------------------------------
# The CLI sub-command and the registry entry (DEMOCI-11-011, DEMOCI-11-019)
# ---------------------------------------------------------------------------


@pytest.fixture
def help_text() -> str:
    """``vultron-demo rcvcv --help`` as the generated sub-command renders it."""
    result = CliRunner().invoke(cli_main, ["rcvcv", "--help"])
    assert result.exit_code == 0, result.output
    return result.output


class TestRcvcvCliCommand:
    """The generated ``rcvcv`` sub-command offers one option per container."""

    @pytest.mark.parametrize(
        "option",
        [
            "--skip-health-check",
            "--reporter-url",
            "--c1-url",
            "--v1-url",
            "--c2-url",
            "--v2-url",
            "--case-actor-url",
            "--reporter-id",
            "--c1-id",
            "--v1-id",
            "--c2-id",
            "--v2-id",
        ],
    )
    def test_the_option_is_offered(self, help_text: str, option: str):
        """One URL and one id option per container, plus the health skip."""
        assert option in help_text

    def test_main_builds_one_client_per_container_and_runs_the_story(self):
        """``main()`` names its containers and passes their clients on."""
        clients = {
            name: MagicMock(name=name, base_url=f"http://{name}:7999/api/v2")
            for name in ("reporter", "c1", "v1", "c2", "v2", "case-actor")
        }

        with (
            patch.object(
                demo, "coordinated_clients", return_value=clients
            ) as built,
            patch.object(demo, "run_rcvcv_demo") as run,
        ):
            demo.main(
                skip_health_check=True,
                c1_url="http://elsewhere:7999/api/v2",
                reporter_id="urn:test:reporter",
                c1_id="urn:test:c1",
                v1_id="urn:test:v1",
                c2_id="urn:test:c2",
                v2_id="urn:test:v2",
            )

        members = built.call_args.args[1]
        assert [(m.role, m.label) for m in members] == [
            ("reporter", "Reporter"),
            ("c1", "C1"),
            ("v1", "V1"),
            ("c2", "C2"),
            ("v2", "V2"),
        ]
        assert [m.url for m in members] == [
            None,
            "http://elsewhere:7999/api/v2",
            None,
            None,
            None,
        ]
        assert built.call_args.kwargs["skip_health_check"] is True

        kwargs = run.call_args.kwargs
        assert kwargs["reporter_client"] is clients["reporter"]
        assert kwargs["c1_client"] is clients["c1"]
        assert kwargs["v1_client"] is clients["v1"]
        assert kwargs["c2_client"] is clients["c2"]
        assert kwargs["v2_client"] is clients["v2"]
        assert kwargs["case_actor_client"] is clients["case-actor"]
        assert kwargs["c2_id"] == "urn:test:c2"


@pytest.fixture
def spec():
    """The one registry entry named ``rcvcv``."""
    entries = [s for s in registered_scenarios() if s.name == "rcvcv"]
    assert len(entries) == 1, entries
    return entries[0]


class TestRcvcvRegistryEntry:
    """The registry is the sole declaration that ``rcvcv`` exists."""

    def test_the_entry_describes_the_five_party_suggestion_scenario(
        self, spec
    ):
        """Every field is rendered into the generated scenario tables."""
        assert spec.label == "RCVCV"
        assert spec.participants == "Reporter + C1 + V1 + C2 + V2"
        assert spec.feature == "Actor-suggestion flow (ADR-0026)"
        assert spec.in_pr_set is True

    def test_the_path_is_read_off_the_story(self, spec):
        """``composed=True`` is what tells a check it places no step marks."""
        assert spec.composed is True
        assert spec.path == demo.STORY.path

    def test_the_derived_paths_point_at_this_module_and_its_harness(
        self, spec
    ):
        """Every artifact path derives from the name (DEMOCI-11-003)."""
        assert spec.demo_path == "vultron/demo/scenario/rcvcv_demo.py"
        assert (
            spec.harness_path == "test/ci/invariants/test_rcvcv_invariants.py"
        )


# ---------------------------------------------------------------------------
# The unseated containers the scenario declares (DEMOCI-11-018)
# ---------------------------------------------------------------------------


class TestRcvcvUnseatedContainers:
    """C2 and V2 are declared as containers, not as cast members."""

    def test_run_rcvcv_demo_declares_both_character_actors_unseated(self):
        """``open_coordinated_cast`` is told which containers to wait on."""
        with (
            patch.object(demo, "run_story") as run_story,
            patch.object(
                demo, "open_coordinated_cast"
            ) as open_coordinated_cast,
        ):
            demo.run_rcvcv_demo(
                reporter_client=mock_client(),
                c1_client=mock_client(),
                v1_client=mock_client(),
                c2_client=mock_client(),
                v2_client=mock_client(),
                case_actor_client=mock_client(),
                c2_id="urn:test:c2",
                v2_id="urn:test:v2",
            )
            run_story.call_args.args[2](MagicMock())

        unseated = open_coordinated_cast.call_args.kwargs["unseated"]
        assert set(unseated) == {demo.C2, demo.V2}
        assert all(
            isinstance(slot, UnseatedContainer) for slot in unseated.values()
        )
        assert unseated[demo.C2].label == "C2"
        assert unseated[demo.V2].label == "V2"
        assert unseated[demo.C2].actor_id == "urn:test:c2"
        assert unseated[demo.V2].actor_id == "urn:test:v2"
        assert run_story.call_args.args[0] == "rcvcv"
        assert run_story.call_args.args[1] is demo.STORY
