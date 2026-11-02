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

"""Unit tests for the RCCV-handoff four-actor CVD demo (DEMOMA-14, #5535).

``rccv-handoff`` is written as composition (ADR-0098,
:mod:`vultron.demo.helpers.story`): its opening is the shared
:data:`~vultron.demo.helpers.two_coordinator_story.C1_INVITES_C2` prefix it
shares with ``rccv-extension``, and its own story is the continuation after C1
decides to offer ownership to C2 (DEMOMA-14-017).  The checks that used to sit
on its ``_phase_*`` functions therefore sit here on three things:

* the **story's shape** — the path read off its choices, the identity of the
  stretch it shares with ``rccv-extension``, and the order of its own
  fragments;
* each of its **own fragments**, driven against a
  :func:`~test.demo._helpers.story_state` stand-in cast, so a test observes
  what the fragment calls;
* the **surfaces around the story** — the CLI option set (DEMOMA-14-008), the
  registry entry and the devlogs names the invariant harness reads.

What the shared opening does is not re-tested here: it is one copy of the code,
and ``test/demo/test_coordinated_story.py`` and
``test/demo/test_two_coordinator_story.py`` own it.  The two
``owner-keep-case`` continuations are shared with the vendor-first half, so
``test/demo/test_owner_decision_story.py`` owns their mechanics and this module
asserts only which parts ``rccv-handoff`` casts in them.

Every test patches the collaborators out, so no HTTP happens except in
``TestSeedContainersRccv``, which drives the real seeding helper through a
FastAPI TestClient.  ``demo_gate`` / ``demo_check`` / ``demo_step`` stay real
wherever the test is about control flow and are stubbed to ``nullcontext`` only
where it is about call shape (``test_demo_context_managers.py`` owns their
behaviour).
"""

import contextlib
import json
from typing import cast
from unittest.mock import MagicMock, patch

import pytest
from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from fastapi.testclient import TestClient

import vultron.demo.scenario.rccv_extension_demo as extension_demo
import vultron.demo.scenario.rccv_handoff_demo as demo
from test.demo._helpers import (
    devlogs_name_of,
    make_client,
    make_testclient_call,
    mock_actor,
    mock_case,
    mock_client,
    no_demo_banners,
    story_state,
    stub_closure_gate,
)
from test.support.case_owner import CASE_OWNER_ID
from vultron.demo.actor_session import ActorSession
from vultron.demo.cli import main as cli_main
from vultron.demo.helpers import (
    coordinated_story,
    owner_decision_story,
    story as story_module,
    two_coordinator_story,
)
from vultron.demo.helpers.coordinated_story import (
    REPORTER,
    VENDOR,
    VENDOR_LABEL,
)
from vultron.demo.helpers.story import (
    Choose,
    StoryState,
    UnseatedContainer,
    choose,
    run_story,
    story,
)
from vultron.demo.helpers.two_coordinator_story import (
    C1,
    C1_INVITES_C2,
    C1_PART,
    C1_ROLE,
    C2,
    C2_PART,
    SECOND_COORDINATOR_JOINED,
    VENDOR_PART,
    c1_invites_c2,
)
from vultron.demo.scenario.registry import registered_scenarios
from vultron.demo.utils import DataLayerClient, reset_demo_failures
from vultron.enums.roles import CVDRole
from vultron.errors import DemoStoryError
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

#: The scenario's four cast names, in the order the story seats them.
_CAST = (REPORTER, C1, C2, VENDOR)

#: How many items of ``STORY`` are the shared opening.
_PREFIX_LEN = len(C1_INVITES_C2.items)


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
    """Every module a fragment of this scenario reaches, patched once."""
    with no_demo_banners(
        demo, coordinated_story, two_coordinator_story, owner_decision_story
    ):
        yield


def _four_party_state():
    """A story state seating all four, on an open case."""
    return story_state(*_CAST, case=mock_case())


def _sessions_of(mock_method) -> list[str]:
    """The actor id of each session an ``autospec``-ed verb was called on."""
    return [call.args[0].actor.id_ for call in mock_method.call_args_list]


# ---------------------------------------------------------------------------
# The story's shape (DEMOCI-11-019, DEMOCI-11-024, DEMOMA-14-017)
# ---------------------------------------------------------------------------


class TestRccvHandoffStoryShape:
    """``STORY`` places the scenario on the tree, and nothing else does."""

    #: The path ``rccv-handoff`` declared as ``@scenario(path=...)`` before it
    #: was composed.  The composed form must walk exactly the same tree
    #: ending, or the recordings, the generated index and the invariant
    #: harness all move with it.
    DECLARED_PATH = (
        ("reporter-whom-to-tell", "coordinator"),
        ("coordinator-invite-whom", "coordinator"),
        ("owner-keep-case", "offer-ownership"),
    )

    def test_the_story_walks_the_path_the_scenario_used_to_declare(self):
        """The path is read off the choices, not typed beside them."""
        assert demo.STORY.path == self.DECLARED_PATH

    @pytest.mark.spec("DEMOMA-14-017")
    def test_the_opening_is_the_shared_prefix_itself(self):
        """``rccv-handoff`` and ``rccv-extension`` start with one prefix.

        Identity of the shared stretch, not merely a matching sequence: the
        two recordings must be byte-identical up to the ``owner-keep-case``
        branch point (DEMOCI-11-018), which only holds while the opening is
        one copy of the code.  Comparing against ``C1_INVITES_C2.items`` is
        what stops a sibling slipping a step in before the branch point.
        """
        assert demo.STORY.items[:_PREFIX_LEN] == C1_INVITES_C2.items
        assert extension_demo.STORY.items[:_PREFIX_LEN] == C1_INVITES_C2.items
        # Every item of the prefix is the same object in both stories.
        # Identity only: ``Choose`` is a frozen dataclass, so a hand-copied
        # duplicate compares equal and an ``or mine == theirs`` arm would make
        # this loop a second spelling of the tuple equality above.
        for mine, theirs in zip(
            demo.STORY.items[:_PREFIX_LEN],
            extension_demo.STORY.items[:_PREFIX_LEN],
            strict=True,
        ):
            assert mine is theirs

    @pytest.mark.spec("DEMOMA-13-012")
    def test_the_prefix_itself_starts_with_the_rcv_familys_opening(self):
        """The first two steps are shared with every coordinator-first run.

        ``C1_INVITES_C2`` continues ``REPORTER_TELLS_THE_COORDINATOR``, so the
        report submission and C1's triage are one copy of the code for all of
        ``rcv``, ``rcv-reject``, ``rcvcv`` and this pair (DEMOCI-11-018).
        """
        shared = coordinated_story.REPORTER_TELLS_THE_COORDINATOR.items
        assert C1_INVITES_C2.items[: len(shared)] == shared
        for mine, theirs in zip(
            demo.STORY.items[: len(shared)], shared, strict=True
        ):
            assert mine is theirs

    def test_the_siblings_part_at_the_owners_decision(self):
        """The first item after the prefix is the choice, and it differs."""
        branch = demo.STORY.items[_PREFIX_LEN]
        assert branch == Choose(
            branch_point="owner-keep-case",
            choice="offer-ownership",
            by=C1,
        )
        assert branch != extension_demo.STORY.items[_PREFIX_LEN], (
            "rccv-handoff and rccv-extension must take different choices at"
            " owner-keep-case, or they are the same scenario"
        )

    def test_the_prefix_ends_with_c2_joining_the_case(self):
        """C1 decides only once C2 is a participant (DEMOMA-14-010)."""
        assert C1_INVITES_C2.items[-1] is two_coordinator_story.c1_invites_c2

    def test_the_continuation_runs_in_the_declared_order(self):
        """One assertion for the whole continuation, so a reordering shows.

        The order is load-bearing: the handover comes before C2 invites
        anyone, because only the Case Owner may invite (DEMOMA-14-005).
        """
        assert demo.STORY.items[_PREFIX_LEN:] == (
            choose("owner-keep-case", "offer-ownership", by=C1),
            demo.c1_hands_the_case_to_c2,
            demo.c2_invites_the_vendor,
            two_coordinator_story.required_participants_are_present,
            two_coordinator_story.every_replica_converges,
            demo.the_four_exchange_notes,
            coordinated_story.vendor_reports_the_fix_ready,
            demo.everyone_publishes,
            demo.everyone_closes,
        )

    def test_c1_and_the_vendor_are_seated_under_the_family_role_names(self):
        """One copy of the opening serves the rcv family and this pair."""
        assert C1 == coordinated_story.COORDINATOR
        assert VENDOR_PART.name == VENDOR
        # The devlogs and the CLI keep the scenario's own names.
        assert [role.name for role in demo.ROLES] == [
            "reporter",
            C1_ROLE,
            C2,
            "vendor",
            "case-actor",
        ]


# ---------------------------------------------------------------------------
# The run's cast: C2 is a character actor (DEMOCI-11-018)
# ---------------------------------------------------------------------------


class TestRccvHandoffCast:
    """Four containers are reset; the opening seeds three of them."""

    def _open(self, *, case_actor_id=None):
        """Run the orchestrator and open its cast, collaborators stubbed."""
        clients = {
            name: mock_client() for name in ("reporter", "c1", "c2", "vendor")
        }
        case_actor_client = mock_client()
        seeded = [
            MagicMock(id_=f"urn:test:{name}")
            for name in ("reporter", "c1", "vendor")
        ]
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
            patch.object(
                two_coordinator_story, "seed_containers_rccv"
            ) as seed_four,
        ):
            demo.run_rccv_handoff_demo(
                reporter_client=clients["reporter"],
                c1_client=clients["c1"],
                c2_client=clients["c2"],
                vendor_client=clients["vendor"],
                case_actor_client=case_actor_client,
                reporter_id="urn:test:reporter",
                c1_id="urn:test:c1",
                c2_id="urn:test:c2",
                vendor_id="urn:test:vendor",
                case_actor_id=case_actor_id,
            )
            # run_story() is what plays the story; the cast opening is the
            # callable it is handed, so the test runs that and nothing else.
            open_cast = run_story.call_args.args[2]
            captured["state"] = open_cast(MagicMock())
        return {
            "clients": clients,
            "case_actor_client": case_actor_client,
            "reset": reset,
            "reseed": reseed,
            "seed_three": seed_three,
            "seed_four": seed_four,
            "run_story": run_story,
            "state": captured["state"],
        }

    @pytest.mark.spec("DEMOMA-14-001")
    def test_every_container_is_reset_and_the_case_actor_re_seeded(self):
        """DEMOMA-01-003: a run starts clean on every container it touches.

        The reset wipes the CaseActor identity C1 proposes the case to, so the
        dedicated container's identity is re-seeded after it (DEMOMA-06-004,
        #1876).
        """
        ran = self._open()

        assert [c.kwargs["client"] for c in ran["reset"].call_args_list] == [
            ran["clients"]["reporter"],
            ran["clients"]["c1"],
            ran["clients"]["vendor"],
            ran["clients"]["c2"],
            ran["case_actor_client"],
        ]
        ran["reseed"].assert_called_once_with(ran["case_actor_client"])

    def test_the_opening_seeds_only_the_three_fixed_role_containers(self):
        """C2's actor record would move the first ledger entry's timestamp."""
        ran = self._open()

        ran["seed_three"].assert_called_once()
        seeding = ran["seed_three"].call_args.kwargs
        assert seeding["reporter_client"] is ran["clients"]["reporter"]
        assert seeding["coordinator_client"] is ran["clients"]["c1"]
        assert seeding["vendor_client"] is ran["clients"]["vendor"]
        ran["seed_four"].assert_not_called()

        state = ran["state"]
        assert sorted(state.cast) == sorted([REPORTER, C1, VENDOR])
        assert sorted(state.unseated) == [C2]

    def test_c2s_container_waits_with_its_deterministic_id(self):
        """``--c2-id`` reaches the fragment that seeds C2, not the opening."""
        ran = self._open()
        unseated = ran["state"].unseated

        assert isinstance(unseated[C2], UnseatedContainer)
        assert unseated[C2].client is ran["clients"]["c2"]
        assert unseated[C2].actor_id == "urn:test:c2"
        assert unseated[C2].label == "C2"

    def test_the_orchestrator_plays_this_scenarios_story(self):
        """``run_story`` is handed the registered name and ``STORY``."""
        ran = self._open()

        assert ran["run_story"].call_args.args[0] == "rccv-handoff"
        assert ran["run_story"].call_args.args[1] is demo.STORY

    @pytest.mark.spec("DEMOMA-14-008")
    def test_a_case_actor_id_override_is_accepted_and_unused(self):
        """``--case-actor-id`` has somewhere to go and seeds nothing with it.

        The case-actor container seeds its own identity on reset
        (DEMOMA-06-004), and the id the Invite check needs is read off the
        case's participant index so that it names the actor actually holding
        CASE_MANAGER (PCR-08-008).  The option therefore exists so the CLI
        contract holds, and a run given it must behave as one that is not —
        never quietly seed a CaseActor under the given id.
        """
        given = self._open(case_actor_id="urn:test:given-case-actor")

        seeding = given["seed_three"].call_args.kwargs
        assert seeding["case_actor_client"] is given["case_actor_client"]
        assert "urn:test:given-case-actor" not in seeding.values(), seeding
        # The three seeded actors are the opening's; it seeds no fourth, and
        # the canonical store stays the dedicated container's.
        assert sorted(given["state"].cast) == sorted([REPORTER, C1, VENDOR])
        assert given["state"].case_actor_client is given["case_actor_client"]


# ---------------------------------------------------------------------------
# The handover and the new owner's invite (DEMOMA-14-004/005/010/011)
# ---------------------------------------------------------------------------


class TestC1HandsTheCaseToC2:
    """The scenario casts C1 as the owner and C2 as the new owner."""

    @pytest.mark.spec("DEMOMA-14-004")
    def test_the_handover_names_c1_as_owner_and_c2_as_the_new_owner(self):
        """The mechanics are shared; which part each plays is the scenario's.

        ``owner_decision_story`` takes ``Part``\\ s off the running story, so
        the only thing this scenario decides is the casting — and getting it
        backwards would transfer ownership the wrong way (DEMOMA-14-012).  It
        also names the join the transfer presupposes, which the continuation
        reads before it offers anything (DEMOMA-14-010).
        """
        state = _four_party_state()

        with patch.object(demo, "the_owner_hands_the_case_over") as handover:
            demo.c1_hands_the_case_to_c2(state)

        handover.assert_called_once()
        assert handover.call_args.args == (state,)
        assert handover.call_args.kwargs == {
            "joined": SECOND_COORDINATOR_JOINED,
            "owner": C1_PART,
            "new_owner": C2_PART,
        }


class TestC2InvitesTheVendor:
    """C2, the owner since the handoff, invites the Vendor — not C1."""

    @pytest.mark.spec("DEMOMA-14-005")
    def test_the_invite_comes_from_c2_and_offers_the_vendor_role(self):
        """The new owner invites, so the roster is read on its replica."""
        state = _four_party_state()

        with patch.object(demo, "the_new_owner_invites") as invite:
            demo.c2_invites_the_vendor(state)

        invite.assert_called_once()
        assert invite.call_args.args == (state,)
        assert invite.call_args.kwargs == {
            "new_owner": C2_PART,
            "invitee": VENDOR_PART,
            "role": CVDRole.VENDOR,
            "seated": (REPORTER, C1, C2, VENDOR),
        }

    @pytest.mark.spec("DEMOMA-14-013")
    def test_an_uncommitted_handover_stops_the_story_before_the_invite(self):
        """Only the Case Owner may invite (DEMOCI-01-011).

        The real shared continuation runs: it reads the prop the handover
        keeps, so a transfer the CASE_MANAGER never committed stops the story
        here instead of inviting into a case C2 does not own.
        """
        state = _four_party_state()

        with (
            patch.object(
                owner_decision_story, "run_case_invite_chain"
            ) as chain,
            patch.object(
                owner_decision_story, "find_case_actor_participant_id"
            ),
            pytest.raises(DemoStoryError, match="handed over"),
        ):
            demo.c2_invites_the_vendor(state)

        chain.assert_not_called()


# ---------------------------------------------------------------------------
# The note thread (DEMOMA-16-001)
# ---------------------------------------------------------------------------


class TestTheFourExchangeNotes:
    """C2 and the Vendor answer the thread the Reporter and C1 opened."""

    def test_the_two_updates_are_posted_from_their_own_containers(self):
        """Each poster acts from its own replica; the thread is C1's.

        The question and C1's answer are the pair's shared half
        (``four_way_note_thread``); what C2 says differs with who owns the
        case by then, which is why this scenario passes its own two posts.
        """
        state = _four_party_state()

        with patch.object(two_coordinator_story, "add_note_thread") as thread:
            demo.the_four_exchange_notes(state)

        watching_client, case, posts = thread.call_args.args
        assert watching_client is state.client(C1)
        assert case is state.case
        assert [post.poster.client for post in posts] == [
            state.client(REPORTER),
            state.client(C1),
            state.client(C2),
            state.client(VENDOR),
        ]
        assert [post.name for post in posts[2:]] == [
            "C2 Update (new Case Owner)",
            f"{VENDOR_LABEL} Status Update",
        ]
        # C2 speaks as the new Case Owner, which is what distinguishes this
        # thread from ``rccv-extension``'s (DEMOMA-17-002).
        assert "new case owner" in posts[2].content.lower()


# ---------------------------------------------------------------------------
# Publication and closure (DEMOMA-14-014, DEMOMA-14-015)
# ---------------------------------------------------------------------------


@pytest.mark.spec("DEMOMA-14-014")
class TestEveryonePublishes:
    """C2, the Case Owner since the handoff, publishes first."""

    def test_the_case_owner_is_c2_and_the_other_coordinator_is_c1(self):
        """The shared step reads the owner's part; this scenario casts it."""
        state = _four_party_state()

        with patch.object(demo, "all_four_publish") as publish:
            demo.everyone_publishes(state)

        assert publish.call_args.args == (state,)
        assert publish.call_args.kwargs == {
            "owner": C2_PART,
            "other": C1_PART,
        }

    def test_the_real_order_is_c2_then_vendor_then_c1_then_reporter(self):
        """DEMOMA-07-003(4): the Case Owner triggers CS.P first.

        The shared step runs for real, so the casting above is checked by its
        effect: a swapped owner would publish C1 first and the embargo
        teardown would be awaited after the wrong trigger.
        """
        state = _four_party_state()
        order: list[str] = []

        def name_of(client: object) -> str:
            return devlogs_name_of(
                state, client, two_coordinator_story.DEVLOG_REPLICAS
            )

        with (
            patch.object(
                two_coordinator_story,
                "wait_for_case_em_terminated",
                side_effect=lambda client, case_id: order.append(
                    f"em_exited:{name_of(client)}"
                ),
            ),
            patch.object(
                two_coordinator_story, "wait_for_participant_vf_state"
            ),
            patch.object(two_coordinator_story, "verify_publicly_disclosed"),
            patch.object(
                ActorSession,
                "notify_published",
                autospec=True,
                side_effect=lambda session: order.append(
                    f"published:{name_of(session.client)}"
                ),
            ),
            _no_banners(),
        ):
            demo.everyone_publishes(state)

        assert order == [
            "published:coordinator",
            "em_exited:vendor",
            "published:vendor2",
            "published:vendor",
            "em_exited:reporter",
            "published:reporter",
            "em_exited:reporter",
        ], order


@pytest.mark.spec("DEMOMA-14-015")
class TestEveryoneCloses:
    """C1, the Vendor and the Reporter leave; C2, the owner, leaves last."""

    def test_c2_leaves_last_and_the_departures_are_read_on_the_case_actor(
        self,
    ):
        """The owner's ``Leave`` is gated on the CASE_MANAGER's store.

        The handoff moves CASE_OWNER, not CASE_MANAGER: that store stays on
        the dedicated case-actor container (DEMOMA-06-005), so the authority
        client must be that one and not C1's or C2's own.
        """
        state = _four_party_state()

        with (
            patch.object(ActorSession, "leave_case"),
            stub_closure_gate(),
            patch.object(
                coordinated_story, "close_case_owner_last"
            ) as closure,
        ):
            demo.everyone_closes(state)

        kwargs = closure.call_args.kwargs
        assert kwargs["milestone"] == "M8"
        assert kwargs["authority_client"] is state.case_actor_client
        assert [leaver.client for leaver in kwargs["others"]] == [
            state.client(C1),
            state.client(VENDOR),
            state.client(REPORTER),
        ]
        assert kwargs["owner"].client is state.client(C2)
        assert kwargs["owner"].actor is state.actor(C2).actor


# ---------------------------------------------------------------------------
# The devlogs the invariant harness reads
# ---------------------------------------------------------------------------


def _bound_client(slug: str) -> MagicMock:
    """A dump client stub bound to a *generated* actor id, as the real one is.

    ``actor_id`` must be a real string: the dump derives its route key from it
    (``replica_route_key``, ADR-0073) and writes the key into the manifest, so
    a bare ``MagicMock()`` leaves an unserialisable object there.  The ids are
    deliberately *not* the docker-compose seed names — that is the whole point
    of deriving the key, and a stub carrying ``actor_id="reporter"`` would
    pass even if the derivation were dropped.
    """
    client = MagicMock()
    client.actor_id = f"https://example.org/actors/{slug}"
    client.get_list.return_value = [{"logIndex": 0}]
    return client


class TestRccvHandoffLedgerDump:
    """Each replica is dumped under this scenario's own name for it."""

    def _state_for_dump(self, case):
        """A story state whose clients are dump-ready, on *case*.

        Built rather than adapted: an ``ActorSession`` is frozen, so a bound
        client has to be the one the session is made with.
        """
        slugs = {
            REPORTER: "reporter-9f3a",
            C1: "coordinator1-2b71",
            C2: "coordinator2-4c05",
            VENDOR: "vendor-8ade",
        }
        state = StoryState(
            cast={
                name: ActorSession(
                    client=_bound_client(slug),
                    actor=mock_actor(f"urn:test:{name}"),
                )
                for name, slug in slugs.items()
            },
            case_actor_client=_bound_client("case-actor"),
            harness=MagicMock(demo_name="rccv-handoff"),
            dump=lambda _state: None,
        )
        state.open_case(case=case, report=MagicMock(), offer=MagicMock())
        return state

    def test_the_dump_writes_one_file_per_actor_under_the_demo_name(
        self, tmp_path, monkeypatch
    ):
        """Four crossed devlogs names, each keyed on its client's actor id."""
        case = as_VulnerabilityCase(
            attributed_to=CASE_OWNER_ID,
            id_="https://example.org/cases/rccv-test-case",
        )
        monkeypatch.setenv("DEVLOGS_DIR", str(tmp_path))

        demo.dump_two_coordinator_ledgers(self._state_for_dump(case))

        case_slug = "https_example.org_cases_rccv-test-case"
        for devlogs_name in ("reporter", "vendor", "coordinator", "vendor2"):
            assert (
                tmp_path
                / "rccv-handoff"
                / devlogs_name
                / f"{case_slug}-case-ledger.jsonl"
            ).exists(), devlogs_name

        # The route key selects the store (ADR-0073), so it must be the
        # client's own actor id — not the seed name the directory is named
        # after.  The pair deliberately crosses the two: C1 is the actor
        # written under "vendor".
        manifest = json.loads(
            (tmp_path / "rccv-handoff" / "dump-manifest.json").read_text()
        )
        keys = {r["actorName"]: r["routeKey"] for r in manifest["actors"]}
        assert keys == {
            "reporter": "reporter-9f3a",
            "vendor": "coordinator1-2b71",
            "coordinator": "coordinator2-4c05",
            "vendor2": "vendor-8ade",
            "case-actor": "case-actor",
        }

    def test_the_canonical_ledger_is_read_on_the_dedicated_container(
        self, tmp_path, monkeypatch
    ):
        """The CaseActor is not on C1's container (DEMOMA-06-005)."""
        case = as_VulnerabilityCase(
            attributed_to=CASE_OWNER_ID,
            id_="https://example.org/cases/rccv-with-ca",
            actor_participant_index={
                "https://example.org/actors/case-actor": (
                    "https://example.org/cases/rccv-with-ca"
                    "/participants/case-actor"
                )
            },
        )
        monkeypatch.setenv("DEVLOGS_DIR", str(tmp_path))
        state = self._state_for_dump(case)

        demo.dump_two_coordinator_ledgers(state)

        canonical = cast(MagicMock, state.case_actor_client.get_list)
        c1_reads = cast(MagicMock, state.client(C1).get_list)
        assert any(
            "/actors/case-actor/demo/cases/rccv-with-ca/log" in call.args[0]
            for call in canonical.call_args_list
        )
        assert not any(
            "/actors/case-actor/" in call.args[0]
            for call in c1_reads.call_args_list
        )

    def test_the_dump_is_what_the_cast_opening_arms(self):
        """DEMOMA-23-003: armed when the case opens, and exactly once."""
        with (
            patch.object(demo, "run_story") as run_story,
            patch.object(
                coordinated_story, "open_coordinated_cast"
            ) as open_coordinated_cast,
        ):
            demo.run_rccv_handoff_demo(
                reporter_client=mock_client(),
                c1_client=mock_client(),
                c2_client=mock_client(),
                vendor_client=mock_client(),
                case_actor_client=mock_client(),
                c2_id="urn:test:c2",
            )
            run_story.call_args.args[2](MagicMock())

        assert (
            open_coordinated_cast.call_args.kwargs["dump"]
            is demo.dump_two_coordinator_ledgers
        )


# ---------------------------------------------------------------------------
# The CLI sub-command and the registry entry (DEMOCI-11-011, DEMOMA-14-008)
# ---------------------------------------------------------------------------


@pytest.fixture
def help_text() -> str:
    """``vultron-demo rccv-handoff --help`` as the sub-command renders it."""
    result = CliRunner().invoke(cli_main, ["rccv-handoff", "--help"])
    assert result.exit_code == 0, result.output
    return result.output


@pytest.mark.spec("DEMOMA-14-008")
class TestRccvHandoffCliCommand:
    """The generated sub-command offers every option DEMOMA-14-008 names."""

    @pytest.mark.parametrize(
        "option",
        [
            "--skip-health-check",
            "--reporter-url",
            "--c1-url",
            "--c2-url",
            "--vendor-url",
            "--case-actor-url",
            "--reporter-id",
            "--c1-id",
            "--c2-id",
            "--vendor-id",
            "--case-actor-id",
        ],
    )
    def test_the_option_is_offered(self, help_text: str, option: str):
        """One URL and one id option per container, plus the health skip."""
        assert option in help_text

    def test_main_builds_one_client_per_container_and_runs_the_story(self):
        """``main()`` names its containers and passes their clients on."""
        clients = {
            name: MagicMock(name=name, base_url=f"http://{name}:7999/api/v2")
            for name in ("reporter", "c1", "c2", "vendor", "case-actor")
        }

        with (
            patch.object(
                demo, "coordinated_clients", return_value=clients
            ) as built,
            patch.object(demo, "run_rccv_handoff_demo") as run,
        ):
            demo.main(
                skip_health_check=True,
                c1_url="http://elsewhere:7999/api/v2",
                reporter_id="urn:test:reporter",
                c1_id="urn:test:c1",
                c2_id="urn:test:c2",
                vendor_id="urn:test:vendor",
                case_actor_id="urn:test:case-actor",
            )

        members = built.call_args.args[1]
        assert [(m.role, m.label) for m in members] == [
            ("reporter", "Reporter"),
            ("c1", "C1"),
            ("c2", "C2"),
            ("vendor", "Vendor"),
        ]
        assert [m.url for m in members] == [
            None,
            "http://elsewhere:7999/api/v2",
            None,
            None,
        ]
        assert built.call_args.kwargs["skip_health_check"] is True

        kwargs = run.call_args.kwargs
        assert kwargs["reporter_client"] is clients["reporter"]
        assert kwargs["c1_client"] is clients["c1"]
        assert kwargs["c2_client"] is clients["c2"]
        assert kwargs["vendor_client"] is clients["vendor"]
        assert kwargs["case_actor_client"] is clients["case-actor"]
        assert kwargs["c2_id"] == "urn:test:c2"
        assert kwargs["case_actor_id"] == "urn:test:case-actor"


@pytest.fixture
def spec():
    """The one registry entry named ``rccv-handoff``."""
    entries = [s for s in registered_scenarios() if s.name == "rccv-handoff"]
    assert len(entries) == 1, entries
    return entries[0]


class TestRccvHandoffRegistryEntry:
    """The registry is the sole declaration that ``rccv-handoff`` exists."""

    def test_the_entry_describes_the_ownership_transfer_scenario(self, spec):
        """Every field is rendered into the generated scenario tables."""
        assert spec.label == "RCCV-handoff"
        assert spec.participants == "Reporter + C1 → C2 + Vendor"
        assert spec.feature == "Ownership transfer between two coordinators"
        assert spec.in_pr_set is False

    def test_the_path_is_read_off_the_story(self, spec):
        """``composed=True`` is what tells a check it places no step marks."""
        assert spec.composed is True
        assert spec.path == demo.STORY.path

    def test_the_derived_paths_point_at_this_module_and_its_harness(
        self, spec
    ):
        """Every artifact path derives from the name (DEMOCI-11-003)."""
        assert spec.demo_path == "vultron/demo/scenario/rccv_handoff_demo.py"
        assert spec.harness_path == (
            "test/ci/invariants/test_rccv_handoff_invariants.py"
        )


# ---------------------------------------------------------------------------
# The seeding helper this pair's character actor arrives through
# ---------------------------------------------------------------------------


class TestSeedContainersRccv:
    """``seed_containers_rccv`` creates the pair's four actors as peers.

    Driven against a real FastAPI TestClient, so the actor and peer records it
    writes are the ones a run writes.  The fragment that calls it is
    ``two_coordinator_story.c2_is_seeded``, whose placement after the branch
    point is that module's test's subject (DEMOCI-11-018).
    """

    @pytest.fixture(autouse=True)
    def _route_through_testclient(self, client: TestClient, base: str):
        """Route every ``DataLayerClient`` call through the one TestClient."""
        mp = MonkeyPatch()
        try:
            mp.setattr(
                DataLayerClient, "call", make_testclient_call(client, base)
            )
            yield
        finally:
            mp.undo()

    @pytest.fixture
    def base(self, client: TestClient) -> str:
        """The base URL of the single TestClient, with the /api/v2 prefix."""
        return str(client.base_url).rstrip("/") + "/api/v2"

    def test_the_seeding_creates_all_four_actors(self, base: str):
        """Reporter, C1, C2 and the Vendor, each on its own container."""
        reporter, c1, c2, vendor = two_coordinator_story.seed_containers_rccv(
            reporter_client=make_client(base),
            c1_client=make_client(base),
            c2_client=make_client(base),
            vendor_client=make_client(base),
        )

        assert [a.name for a in (reporter, c1, c2, vendor)] == [
            "Reporter",
            "Coordinator1",
            "Coordinator2",
            "Vendor",
        ]
        assert all(a.id_ for a in (reporter, c1, c2, vendor))

    def test_the_seeding_registers_every_actor_as_a_peer(self, base: str):
        """C2 must know the Vendor it will invite, and be known to C1."""
        reporter_client = make_client(base)

        two_coordinator_story.seed_containers_rccv(
            reporter_client=reporter_client,
            c1_client=make_client(base),
            c2_client=make_client(base),
            vendor_client=make_client(base),
        )

        actors = reporter_client.get("/actors/")
        names = {a.get("name") for a in actors if isinstance(a, dict)}
        assert {
            "Reporter",
            "Coordinator1",
            "Coordinator2",
            "Vendor",
        } <= names

    def test_a_deterministic_id_is_honoured_for_every_actor(self, base: str):
        """The recordings need the same ids on every run (DEMOCI-11-025)."""
        ids = {
            role: f"{base}/actors/{role}-rccv-det-test"
            for role in ("reporter", "c1", "c2", "vendor")
        }

        seeded = two_coordinator_story.seed_containers_rccv(
            reporter_client=make_client(base),
            c1_client=make_client(base),
            c2_client=make_client(base),
            vendor_client=make_client(base),
            reporter_actor_id=ids["reporter"],
            c1_actor_id=ids["c1"],
            c2_actor_id=ids["c2"],
            vendor_actor_id=ids["vendor"],
        )

        assert [a.id_ for a in seeded] == list(ids.values())


# ---------------------------------------------------------------------------
# The join the owner's decision presupposes (DEMOMA-14-010, DEMOCI-01-011)
# ---------------------------------------------------------------------------


@pytest.mark.spec("DEMOMA-14-010")
@pytest.mark.spec("DEMOMA-17-002")
class TestARosterThatNeverFillsSkipsTheTransfer:
    """The guarantee the hand-placed form got from nesting (#5535).

    Before composition the whole offer and accept sat inside the roster's own
    ``demo_gate``, so a roster that never filled skipped the transfer.  A flat
    story cannot nest, so the roster gate keeps
    :data:`SECOND_COORDINATOR_JOINED` and the transfer reads it — and the
    runner stops the story at the unreadable prop.  Driven through the real
    ``run_story``, the real ``demo_gate`` and the real fragments, because
    every link of that chain is load-bearing and a test of any one of them
    alone is what let the guarantee go missing.
    """

    @pytest.fixture
    def marks(self, monkeypatch: MonkeyPatch):
        """Stand in for ``scenario_harness``, which needs a real case."""
        reset_demo_failures()
        harness = MagicMock()
        harness.demo_name = "rccv-handoff"

        @contextlib.contextmanager
        def stub(_demo_name: str):
            yield harness

        monkeypatch.setattr(story_module, "scenario_harness", stub)
        yield harness
        reset_demo_failures()

    @contextlib.contextmanager
    def _roster(self, *, fills: bool):
        """Run the join with its roster filling or timing out.

        The roster gate in ``coordinated_story`` and the prop read in
        ``owner_decision_story`` are the subject, so both stay real.  Every
        poll *after* the transfer trigger is stubbed: left real they would
        each spend the whole ``OWNER_DECISION_TIMEOUT`` against a
        ``MagicMock`` store, which buys no assertion and puts the test over
        the unit tier's ceiling (``test/AGENTS.md`` § "Timeouts Are
        Two-Tier").
        """
        with (
            patch.object(coordinated_story, "wait_for_case_on_container"),
            patch.object(
                coordinated_story,
                "run_case_invite_chain",
                side_effect=lambda **kw: kw["then"] and kw["then"](),
            ),
            patch.object(
                coordinated_story,
                "wait_for_case_participants",
                side_effect=None
                if fills
                else AssertionError("roster never filled"),
            ),
            patch.object(
                coordinated_story,
                "demo_step",
                side_effect=lambda _: contextlib.nullcontext(),
            ),
            patch.object(
                owner_decision_story,
                "find_ownership_transfer_offer_for_actor",
                return_value="urn:test:offer",
            ),
            patch.object(
                owner_decision_story, "wait_for_case_actor_ledger_event"
            ),
            patch.object(owner_decision_story, "wait_for_case_attributed_to"),
            patch.object(
                owner_decision_story, "wait_for_semantic_type_in_ledger"
            ),
            patch.object(
                ActorSession, "offer_case_ownership_transfer", autospec=True
            ) as offer,
        ):
            yield offer

    def _play(self, state: StoryState) -> None:
        run_story(
            "rccv-handoff",
            story(c1_invites_c2, demo.c1_hands_the_case_to_c2),
            lambda _harness: state,
        )

    def test_a_timed_out_roster_leaves_the_transfer_unoffered(self, marks):
        """The transfer trigger never runs, and the roster is the one failure."""
        state = story_state(REPORTER, C1, C2, VENDOR, case=mock_case())

        with self._roster(fills=False) as offer:
            self._play(state)

        offer.assert_not_called()
        with pytest.raises(
            DemoStoryError, match="no case the second Coordinator joined"
        ):
            state.kept(SECOND_COORDINATOR_JOINED)

    def test_a_filled_roster_lets_the_transfer_run(self, marks):
        """The counterpart, so the test above is not vacuous."""
        state = story_state(REPORTER, C1, C2, VENDOR, case=mock_case())

        with self._roster(fills=True) as offer:
            self._play(state)

        assert state.kept(SECOND_COORDINATOR_JOINED) == str(state.case.id_)
        offer.assert_called_once()
        assert offer.call_args.args[0].client is state.client(C1)
