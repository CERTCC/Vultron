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
* the **character actors' seeding**, which must follow C1's decision;
* the **surfaces around the story** — the CLI option set, the registry entry
  and the devlogs names the invariant harness reads (DEMOMA-19-018).

The fragments only this scenario tells are tested in
``test_rcvcv_fragments.py``, beside their module (CS-18-004).

What the shared opening does is not re-tested here; it is one copy of the code
and ``test/demo/coordinated_story/`` owns it.  Every test patches the
collaborators out, so no HTTP happens; ``demo_gate`` / ``demo_check`` /
``demo_step`` stay real wherever the test is about control flow and are
stubbed to ``nullcontext`` only where it is about call shape
(``test_demo_context_managers.py`` owns their behaviour).
"""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

import vultron.demo.scenario.rcvcv_demo as demo
from test.demo._helpers import (
    functions_referencing,
    mock_actor,
    mock_case,
    mock_client,
    story_state,
)
from test.demo._rcvcv_support import (
    CAST,
    five_party_state,
    no_banners,
)
from vultron.demo.cli import main as cli_main
from vultron.demo.helpers import (
    coordinated_story,
    story_cast,
)
from vultron.demo.helpers.coordinated_story import (
    COORDINATOR,
    REPORTER,
    REPORTER_ASKS_THE_VENDOR,
    VENDOR,
    cast as coordinated_cast,
)
from vultron.demo.helpers.story import Choose, UnseatedContainer, choose
from vultron.demo.scenario import rcv_demo, rcvcv_fragments
from vultron.demo.scenario.registry import registered_scenarios
from vultron.errors import DemoStoryError

#: Clear the process-global failure accumulator around every test.
pytestmark = pytest.mark.usefixtures("fresh_demo_failures")

#: How many items of ``STORY`` are the shared opening.
_PREFIX_LEN = len(REPORTER_ASKS_THE_VENDOR.items)


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
        # Identity only: ``Choose`` is a frozen dataclass, so a hand-copied
        # duplicate compares equal and an ``or mine == theirs`` arm would make
        # this loop a second spelling of the tuple equality above.
        for mine, theirs in zip(
            demo.STORY.items[:_PREFIX_LEN],
            rcv_demo.STORY.items[:_PREFIX_LEN],
            strict=True,
        ):
            assert mine is theirs

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
        clients = {name: mock_client() for name in CAST}
        case_actor_client = mock_client()
        seeded = [mock_actor(f"urn:test:{name}") for name in CAST[:3]]
        captured: dict[str, object] = {}

        with (
            patch.object(demo, "run_story") as run_story,
            patch.object(
                story_cast,
                "reset_datalayer",
                return_value={"status": "ok"},
            ) as reset,
            patch(
                "vultron.demo.helpers.seeding.reset.seed_case_actor_identity"
            ) as reseed,
            patch.object(
                coordinated_cast,
                "seed_containers_rcv",
                return_value=tuple(seeded),
            ) as seed_three,
            patch.object(
                story_cast, "get_actor_by_id", side_effect=list(seeded)
            ),
            patch.object(
                rcvcv_fragments, "seed_containers_rcvcv"
            ) as seed_five,
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
        assert sorted(state.cast) == sorted(CAST[:3])
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
        assert functions_referencing(
            rcvcv_fragments, "seed_containers_rcvcv"
        ) == ["seed_the_second_coordinator_and_vendor"]
        assert functions_referencing(demo, "seed_containers_rcvcv") == []

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
        state = story_state(*CAST[:3], unseated=(demo.C2, demo.V2))
        seeded = tuple(mock_actor(f"urn:test:{name}") for name in CAST)
        # The waiting containers are consumed by the seating, so hold them.
        waiting = {name: state.container(name) for name in (demo.C2, demo.V2)}

        with (
            patch.object(
                rcvcv_fragments, "seed_containers_rcvcv", return_value=seeded
            ) as seed,
            patch.object(
                coordinated_cast,
                "get_actor_by_id",
                side_effect=[seeded[3], seeded[4]],
            ) as lookup,
            no_banners(),
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
        state = story_state(*CAST[:3], unseated=(demo.C2,))
        with (
            patch.object(
                rcvcv_fragments,
                "seed_containers_rcvcv",
                return_value=tuple(
                    mock_actor(f"urn:test:{name}") for name in CAST
                ),
            ),
            patch.object(coordinated_cast, "get_actor_by_id"),
            no_banners(),
            pytest.raises(DemoStoryError, match="no container waiting"),
        ):
            demo.seed_the_second_coordinator_and_vendor(state)


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
        with patch.object(story_cast, "dump_case_ledgers") as dump:
            demo._dump_ledgers(state)
        return dump.call_args.kwargs["targets"]

    def test_every_seated_replica_is_dumped_plus_the_canonical_ledger(self):
        """Five replicas in cast order, then the canonical ledger."""
        targets = self._dump(five_party_state())

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
        state = story_state(*CAST[:3], case=mock_case())
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
            patch.object(demo, "story_clients", return_value=clients) as built,
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
        """The registry holds the path this scenario's story chooses.

        Compared against the story object rather than against a literal, which
        this module's path test pins separately: together they say the
        registered path is both derived and the intended one.
        """
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
        """The cast opening is told which containers to wait on.

        Patched on ``coordinated_story.cast``, where the shared
        ``coordinated_open_cast`` factory looks the opening up: this scenario
        builds its ``open_cast`` callable through that factory rather than
        writing the closure out, so a patch on this module would not reach it.
        """
        with (
            patch.object(demo, "run_story") as run_story,
            patch.object(
                coordinated_cast, "open_coordinated_cast"
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
