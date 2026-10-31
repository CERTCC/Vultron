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

"""Unit tests for the RCCV-extension four-actor CVD demo (DEMOMA-13, #5535).

``rccv-extension`` is written as composition (ADR-0098,
:mod:`vultron.demo.helpers.story`): its opening is the shared
:data:`~vultron.demo.helpers.two_coordinator_story.C1_INVITES_C2` prefix,
which itself continues the rcv family's ``REPORTER_TELLS_THE_COORDINATOR``,
and its own story is the continuation after C1 decides to **keep** the case
(DEMOMA-13-012).  The checks that used to sit on its ``_phase_*`` functions
therefore sit here on three things:

* the **story's shape** — the path read off its choices, the identity of the
  stretch it shares with ``rccv-handoff``, and the order of its own fragments;
* each of its **own fragments**, driven against a
  :func:`~test.demo._helpers.story_state` stand-in cast, so a test observes
  what the fragment calls;
* the **surfaces around the story** — the CLI option set, the registry entry,
  the dedicated case-actor container and the devlogs names the invariant
  harness reads.

What the shared opening does is not re-tested here: ``test_coordinated_story``
owns the rcv family's stretch, ``test_two_coordinator_story`` owns the pair's
prefix and the continuations both scenarios tell, and
``test_owner_decision_story`` owns the ``owner-keep-case`` continuations.
Every test patches the collaborators out, so no HTTP happens; ``demo_gate`` /
``demo_check`` / ``demo_step`` stay real wherever the test is about control
flow and are stubbed to ``nullcontext`` only where it is about call shape
(``test_demo_context_managers.py`` owns their behaviour).
"""

import contextlib
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

import vultron.demo.scenario.rccv_extension_demo as demo
import vultron.demo.utils as demo_utils
from test.demo._helpers import (
    mock_actor,
    mock_case,
    mock_client,
    no_demo_banners,
    patch_chain_shared,
    story_state,
    stub_closure_gate,
)
from vultron.demo.actor_session import ActorSession
from vultron.demo.cli import main as cli_main
from vultron.demo.helpers import (
    coordinated_story,
    owner_decision_story,
    two_coordinator_story,
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
)
from vultron.demo.helpers.owner_decision_story import Part
from vultron.demo.helpers.story import Choose, UnseatedContainer, choose
from vultron.demo.helpers.two_coordinator_story import (
    C1_INVITES_C2,
    SECOND_COORDINATOR_JOINED,
)
from vultron.demo.scenario.registry import registered_scenarios
from vultron.demo.utils import reset_demo_failures
from vultron.enums.roles import CVDRole

#: The scenario's four cast names, in ``ROLES`` order.
_CAST = (REPORTER, demo.C1, demo.C2, VENDOR)

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


def _four_party_state(joined: bool = True):
    """A story state seating all four, on an open case."""
    state = story_state(*_CAST, case=mock_case())
    if joined:
        # The shared opening's roster gate keeps it; the keep continuation
        # reads it, so every test past that read needs it (#5535).
        state.keep(SECOND_COORDINATOR_JOINED, str(state.case.id_))
    return state


# ---------------------------------------------------------------------------
# The story's shape (DEMOCI-11-019, DEMOCI-11-024, DEMOMA-13-012)
# ---------------------------------------------------------------------------


class TestRccvExtensionStoryShape:
    """``STORY`` places the scenario on the tree, and nothing else does."""

    #: The path ``rccv-extension`` declared as ``@scenario(path=...)`` before
    #: it was composed.  The composed form must walk exactly the same tree
    #: ending, or the recordings, the generated index and the invariant
    #: harness all move with it.
    DECLARED_PATH = (
        ("reporter-whom-to-tell", "coordinator"),
        ("coordinator-invite-whom", "coordinator"),
        ("owner-keep-case", "keep"),
    )

    def test_the_story_walks_the_path_the_scenario_used_to_declare(self):
        """The path is read off the choices, not typed beside them."""
        assert demo.STORY.path == self.DECLARED_PATH

    def test_the_opening_is_the_shared_prefix_itself(self):
        """``rccv-extension`` starts with the pair's prefix object.

        Identity of the shared stretch, not merely a matching sequence: the
        two scenarios' recordings must be byte-identical up to the
        ``owner-keep-case`` branch point (DEMOCI-11-018), which only holds
        while the opening is one copy of the code.  Comparing against
        ``C1_INVITES_C2.items`` is what stops a sibling slipping a step in
        before the branch point.
        """
        assert demo.STORY.items[:_PREFIX_LEN] == C1_INVITES_C2.items
        # Identity only: ``Choose`` is a frozen dataclass, so a hand-copied
        # duplicate compares equal and an equality arm would make this loop a
        # second spelling of the tuple comparison above.
        for mine, theirs in zip(
            demo.STORY.items[:_PREFIX_LEN],
            C1_INVITES_C2.items,
            strict=True,
        ):
            assert mine is theirs

    @pytest.mark.spec("DEMOMA-13-012")
    def test_the_prefix_itself_starts_with_the_rcv_familys_opening(self):
        """The nesting DEMOMA-13-012 names, asserted end to end.

        Every coordinator-first scenario shares the report submission and
        C1's triage, so the chain of prefixes has to reach from this
        scenario's story back to ``REPORTER_TELLS_THE_COORDINATOR``.
        """
        shared = len(REPORTER_TELLS_THE_COORDINATOR.items)
        assert (
            demo.STORY.items[:shared] == REPORTER_TELLS_THE_COORDINATOR.items
        )

    def test_the_siblings_part_at_the_owners_decision(self):
        """The first item after the prefix is the choice, and it differs."""
        import vultron.demo.scenario.rccv_handoff_demo as handoff

        branch = demo.STORY.items[_PREFIX_LEN]
        assert branch == Choose(
            branch_point="owner-keep-case",
            choice="keep",
            by=COORDINATOR,
        )
        assert branch != handoff.STORY.items[_PREFIX_LEN], (
            "rccv-extension and rccv-handoff must take different choices at"
            " owner-keep-case, or they are the same scenario"
        )

    def test_the_prefix_ends_with_c2_joining(self):
        """C1 decides only once C2 is a participant (DEMOMA-13-003)."""
        assert C1_INVITES_C2.items[-1] is two_coordinator_story.c1_invites_c2

    def test_the_continuation_runs_in_the_declared_order(self):
        """One assertion for the whole continuation, so a reordering shows.

        The order is load-bearing: the M1 milestone and the drain both read
        state the suggestion then changes, and the suggestion is what brings
        the Vendor in, so every later fragment depends on it.
        """
        assert demo.STORY.items[_PREFIX_LEN:] == (
            choose("owner-keep-case", "keep", by=demo.C1),
            two_coordinator_story.required_participants_are_present,
            demo.replicas_drain_before_the_vendor,
            demo.c2_suggests_the_vendor,
            two_coordinator_story.every_replica_converges,
            demo.the_four_exchange_notes,
            coordinated_story.vendor_reports_the_fix_ready,
            demo.everyone_publishes,
            demo.everyone_closes,
        )

    def test_c1_and_the_vendor_are_seated_under_the_family_role_names(self):
        """One copy of the rcv opening serves ``rcv`` and this pair alike."""
        assert demo.C1 == COORDINATOR
        assert demo.VENDOR_PART.name == VENDOR
        # The devlogs and the CLI keep the scenario's own names.
        assert [role.name for role in demo.ROLES] == [
            "reporter",
            "c1",
            "c2",
            "vendor",
            "case-actor",
        ]


# ---------------------------------------------------------------------------
# C2 suggests the Vendor; C1, keeping the case, approves (DEMOMA-13-004/005)
# ---------------------------------------------------------------------------


@pytest.mark.spec("DEMOMA-13-004")
@pytest.mark.spec("DEMOMA-13-005")
class TestC2SuggestsTheVendor:
    """The ADR-0026 suggest-actor flow, with C1 as the approving owner."""

    def test_the_fragment_names_the_parts_and_the_vendor_role(self):
        """The shared continuation takes this scenario's cast as data.

        AC-2 of #5535: the continuation is not hard-wired to the
        two-coordinator cast, so the scenario is what names C1 as the owner,
        C2 as the suggester and the Vendor as the newcomer.
        """
        state = _four_party_state()

        with patch.object(
            demo, "the_owner_approves_a_suggested_actor"
        ) as keep:
            demo.c2_suggests_the_vendor(state)

        kwargs = keep.call_args.kwargs
        assert keep.call_args.args == (state,)
        assert kwargs["owner"] == Part(demo.C1, "C1")
        assert kwargs["suggester"] == Part(demo.C2, "C2")
        assert kwargs["newcomer"] == Part(VENDOR, "Vendor")
        # Roles must be explicit, or EvaluateDefaultRolesNode falls back to
        # its hardcoded [VENDOR] default (#1969) — which happens to be right
        # here, so only an explicit list keeps it honest.
        assert kwargs["roles"] == [CVDRole.VENDOR]
        assert kwargs["seated"] == (REPORTER, demo.C1, demo.C2, VENDOR)

    def test_the_chain_runs_suggest_then_approve_then_invite_and_triage(self):
        """One ordered pass of the flow, the real continuation running."""
        state = _four_party_state()
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
            patch(
                "vultron.demo.helpers.owner_decision_story"
                ".find_cp_offer_for_case",
                return_value="urn:test:cp-offer",
            ) as cp_offer,
            patch(
                "vultron.demo.helpers.owner_decision_story"
                ".find_case_actor_participant_id",
                return_value="urn:test:case-actor-participant",
            ),
            patch(
                "vultron.demo.helpers.owner_decision_story"
                ".run_case_invite_chain",
                side_effect=lambda **kw: order.append("invite-chain"),
            ) as chain,
            patch(
                "vultron.demo.helpers.owner_decision_story"
                ".invitee_triages_after_joining",
                side_effect=lambda *a, **kw: order.append("triage"),
            ) as triage,
            patch_chain_shared(
                coordinated_story, "wait_for_case_on_container"
            ),
            _no_banners(),
        ):
            demo.c2_suggests_the_vendor(state)

        assert order == ["suggest", "approve", "invite-chain", "triage"]

        assert suggest.call_args.kwargs == {
            "suggested_actor_id": state.actor_id(VENDOR),
            "roles": [CVDRole.VENDOR],
        }
        assert suggest.call_args.args[0].actor is state.actor(demo.C2).actor
        assert approve.call_args.args[0].actor is state.actor(demo.C1).actor
        assert approve.call_args.kwargs == {
            "cp_offer_id": "urn:test:cp-offer",
            "case_actor_id": "urn:test:case-actor-participant",
        }
        # The recommendation is polled for on C1's own container, where the
        # CaseActor forwards it (ADR-0026).
        assert cp_offer.call_args.kwargs["client"] is state.client(demo.C1)

        # The CaseActor invites on its own, so the chain is given no inviter
        # and reads the canonical ledger through the case-actor container.
        kwargs = chain.call_args.kwargs
        assert "inviter" not in kwargs
        assert kwargs["ledger_client"] is state.case_actor_client
        assert kwargs["invitee_client"] is state.client(VENDOR)
        assert kwargs["invitee"] is state.actor(VENDOR).actor

        # The roster is read from C1, which keeps the case, and the triage
        # authority is the canonical store.
        assert triage.call_args.kwargs["owner"] == demo.C1
        assert triage.call_args.kwargs["seated"] == (
            REPORTER,
            demo.C1,
            demo.C2,
            VENDOR,
        )

    @pytest.mark.spec("CLP-08-005")
    def test_the_reporter_holds_the_case_before_the_vendors_triage(self):
        """Bug #2120: the Vendor's triage broadcasts to the Reporter too.

        The triage cycle broadcasts ``Announce(CaseLedgerEntry)`` to all
        participants, so a Reporter without the case replica has no genesis
        hash to anchor the chain on.
        """
        state = _four_party_state()
        order: list[str] = []

        def _wait_for_case(client, case_id, **_kwargs):
            if client is state.client(REPORTER):
                order.append("reporter_wait")

        with (
            patch.object(ActorSession, "suggest_actor_to_case"),
            patch.object(ActorSession, "accept_actor_recommendation"),
            patch(
                "vultron.demo.helpers.owner_decision_story"
                ".find_cp_offer_for_case",
                return_value="urn:test:cp-offer",
            ),
            patch(
                "vultron.demo.helpers.owner_decision_story"
                ".find_case_actor_participant_id",
                return_value="urn:test:case-actor-participant",
            ),
            patch(
                "vultron.demo.helpers.owner_decision_story"
                ".run_case_invite_chain"
            ),
            patch.object(
                coordinated_story,
                "run_invite_path_rm_triage",
                side_effect=lambda **_kw: order.append("triage"),
            ) as triage,
            patch.object(coordinated_story, "wait_for_case_participants"),
            patch_chain_shared(
                coordinated_story,
                "wait_for_case_on_container",
                side_effect=_wait_for_case,
            ),
            _no_banners(),
        ):
            demo.c2_suggests_the_vendor(state)

        assert "reporter_wait" in order, (
            "wait_for_case_on_container(reporter_client) was never called"
            " before the Vendor's triage"
        )
        assert "triage" in order, "run_invite_path_rm_triage was never called"
        assert order.index("reporter_wait") < order.index("triage"), (
            f"the Reporter's case-replica wait must precede the Vendor's RM"
            f" triage; order was {order} — Bug #2120 (CLP-08-005)"
        )
        # The triage's waits read the canonical store, not C1's replica.
        assert (
            triage.call_args.kwargs["auth_client"] is state.case_actor_client
        )
        assert triage.call_args.kwargs["invited_client"] is state.client(
            VENDOR
        )


# ---------------------------------------------------------------------------
# The note thread this scenario's joiners add to (DEMOMA-13-006)
# ---------------------------------------------------------------------------


class TestTheFourExchangeNotes:
    """C2 and the Vendor follow the Reporter's question and C1's answer."""

    def test_the_updates_follow_the_shared_question_and_answer(self):
        """One thread of four, with this scenario's own two updates.

        The Reporter's question and C1's answer are the pair's shared half
        (``four_way_note_thread``); what C2 and the Vendor add is this
        scenario's, because C1 still owns the case here.
        """
        state = _four_party_state()

        with patch.object(two_coordinator_story, "add_note_thread") as thread:
            demo.the_four_exchange_notes(state)

        watching_client, case, posts = thread.call_args.args
        assert watching_client is state.client(demo.C1)
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
        # Each poster acts from its own container.
        assert [post.poster.client for post in posts] == [
            state.client(REPORTER),
            state.client(demo.C1),
            state.client(demo.C2),
            state.client(VENDOR),
        ]
        # C2's update does not claim ownership moved: C1 keeps the case.
        assert "new case owner" not in posts[2].content.lower()


# ---------------------------------------------------------------------------
# Publication and closure with C1 still the owner (DEMOMA-13-002/006)
# ---------------------------------------------------------------------------


@pytest.mark.spec("DEMOMA-13-002")
class TestEveryonePublishes:
    """C1 never hands the case over, so C1 publishes first."""

    def test_c1_is_the_owner_and_c2_is_the_other_coordinator(self):
        """The shared step takes who owns the case as data (#5535 AC-2)."""
        state = _four_party_state()

        with patch.object(demo, "all_four_publish") as publish:
            demo.everyone_publishes(state)

        assert publish.call_args.args == (state,)
        assert publish.call_args.kwargs == {
            "owner": Part(demo.C1, "C1"),
            "other": Part(demo.C2, "C2"),
        }

    @pytest.mark.spec("DEMOMA-07-003")
    def test_c1_publishes_before_every_other_participant(self):
        """The real shared step runs, so the whole order is checked."""
        state = _four_party_state()
        published: list[str] = []

        with (
            patch.object(two_coordinator_story, "wait_for_case_em_terminated"),
            patch.object(
                two_coordinator_story, "wait_for_participant_vf_state"
            ),
            patch.object(two_coordinator_story, "verify_publicly_disclosed"),
            patch.object(
                ActorSession,
                "notify_published",
                autospec=True,
                side_effect=lambda session: published.append(
                    session.actor.id_
                ),
            ),
            _no_banners(),
        ):
            demo.everyone_publishes(state)

        assert published == [
            state.actor_id(demo.C1),
            state.actor_id(VENDOR),
            state.actor_id(demo.C2),
            state.actor_id(REPORTER),
        ]


@pytest.mark.spec("CM-23-015")
class TestEveryoneCloses:
    """Three participants leave in order, then C1, the Case Owner."""

    def test_c1_leaves_last_and_the_departures_are_read_on_the_case_actor(
        self,
    ):
        """The owner's ``Leave`` is gated on the CASE_MANAGER's store.

        That store lives on the dedicated case-actor container
        (DEMOMA-06-005), so the authority client must be that one and not
        C1's own.
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
            state.client(VENDOR),
            state.client(demo.C2),
            state.client(REPORTER),
        ]
        assert kwargs["owner"].client is state.client(demo.C1)
        assert kwargs["owner"].actor is state.actor(demo.C1).actor


# ---------------------------------------------------------------------------
# The dedicated case-actor container (DEMOMA-06-004, DEMOMA-13-010, #1876)
# ---------------------------------------------------------------------------


class TestRccvExtensionDedicatedCaseActor:
    """Every CASE_MANAGER read and act goes to the case-actor container.

    C1 proposes the case to the dedicated case-actor container, so the
    CaseActor's store is there and nowhere else: a C1 client cannot address
    it (DEMOMA-13-001, DEMOMA-13-010).
    """

    def _open_the_cast(self, clients, case_actor_client):
        """Run the scenario's ``open_cast`` with the seeding patched out.

        ``run_story()`` is what plays the story; the cast opening is the
        callable it is handed, so this runs that and nothing else.
        """
        seeded = [
            mock_actor(f"urn:test:{name}")
            for name in (REPORTER, demo.C1, VENDOR)
        ]
        captured: dict[str, Any] = {}

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
            patch.object(two_coordinator_story, "seed_containers_rccv") as (
                seed_four
            ),
        ):
            demo.run_rccv_extension_demo(
                reporter_client=clients[REPORTER],
                c1_client=clients[demo.C1],
                c2_client=clients[demo.C2],
                vendor_client=clients[VENDOR],
                case_actor_client=case_actor_client,
                reporter_id="urn:test:reporter",
                c1_id="urn:test:c1",
                c2_id="urn:test:c2",
                vendor_id="urn:test:vendor",
            )
            captured["state"] = run_story.call_args.args[2](MagicMock())
            captured["run_story"] = run_story
        return captured, reset, reseed, seed_three, seed_four

    @pytest.mark.spec("DEMOMA-01-003")
    def test_reset_clears_every_container_and_reseeds_the_case_actor(self):
        """C2's container is reset with the rest, then left unseeded.

        A run must start from a clean baseline on every container it will
        touch, the character actor's included; the dedicated case-actor
        container's identity is re-seeded after its wipe (#1876).
        """
        clients = {name: mock_client() for name in _CAST}
        case_actor_client = mock_client()

        _, reset, reseed, _, _ = self._open_the_cast(
            clients, case_actor_client
        )

        assert [c.kwargs["client"] for c in reset.call_args_list] == [
            clients[REPORTER],
            clients[demo.C1],
            clients[VENDOR],
            clients[demo.C2],
            case_actor_client,
        ]
        reseed.assert_called_once_with(case_actor_client)

    @pytest.mark.spec("DEMOCI-11-018")
    def test_the_opening_seeds_only_the_three_the_rcv_family_seeds(self):
        """C2 is left as an unseated container for its own fragment.

        Every actor and peer record the opening writes before the case exists
        is one more read of the recording clock, so seeding C2 here would
        move the first ledger entry away from ``rcv``'s (#5532).
        """
        clients = {name: mock_client() for name in _CAST}
        case_actor_client = mock_client()

        captured, _, _, seed_three, seed_four = self._open_the_cast(
            clients, case_actor_client
        )

        seed_three.assert_called_once()
        seeding = seed_three.call_args.kwargs
        assert seeding["reporter_client"] is clients[REPORTER]
        assert seeding["coordinator_client"] is clients[demo.C1]
        assert seeding["vendor_client"] is clients[VENDOR]
        seed_four.assert_not_called()

        state = captured["state"]
        assert sorted(state.cast) == sorted([REPORTER, demo.C1, VENDOR])
        assert sorted(state.unseated) == [demo.C2]
        assert state.container(demo.C2).client is clients[demo.C2]
        assert state.container(demo.C2).actor_id == "urn:test:c2"

    def test_the_run_plays_this_scenarios_story_under_its_own_name(self):
        """``run_story(name, plot, open_cast)`` names the registered demo."""
        clients = {name: mock_client() for name in _CAST}

        captured, _, _, _, _ = self._open_the_cast(clients, mock_client())

        run_story = captured["run_story"]
        assert run_story.call_args.args[0] == "rccv-extension"
        assert run_story.call_args.args[1] is demo.STORY

    def test_the_unseated_container_is_declared_through_the_pair_helper(self):
        """The cast opening is told which container to wait on.

        Patched on ``coordinated_story``, where the shared
        ``coordinated_open_cast`` factory looks the opening up: this scenario
        builds its ``open_cast`` callable through that factory rather than
        writing the closure out, so a patch on this module would not reach it.
        """
        with (
            patch.object(demo, "run_story") as run_story,
            patch.object(
                coordinated_story, "open_coordinated_cast"
            ) as open_coordinated_cast,
        ):
            demo.run_rccv_extension_demo(
                reporter_client=mock_client(),
                c1_client=mock_client(),
                c2_client=mock_client(),
                vendor_client=mock_client(),
                case_actor_client=mock_client(),
                c2_id="urn:test:c2",
            )
            run_story.call_args.args[2](MagicMock())

        unseated = open_coordinated_cast.call_args.kwargs["unseated"]
        assert set(unseated) == {demo.C2}
        assert isinstance(unseated[demo.C2], UnseatedContainer)
        assert unseated[demo.C2].label == "C2"
        assert unseated[demo.C2].actor_id == "urn:test:c2"

    def test_the_dump_reads_the_canonical_ledger_on_the_dedicated_container(
        self,
    ):
        """The scenario's dump is the pair's, which the harness loads."""
        state = _four_party_state()
        for name in state.cast:
            state.client(name).actor_id = f"https://example.org/actors/{name}"
        state.case_actor_client.actor_id = (
            "https://example.org/actors/case-actor"
        )

        with patch.object(coordinated_story, "dump_case_ledgers") as dump:
            demo.dump_two_coordinator_ledgers(state)

        targets = dump.call_args.kwargs["targets"]
        case_actor_targets = [
            t for t in targets if t.actor_name == "case-actor"
        ]
        assert len(case_actor_targets) == 1
        assert case_actor_targets[0].client is state.case_actor_client
        assert case_actor_targets[0].route_key == "case-actor"


# ---------------------------------------------------------------------------
# The CLI sub-command and the registry entry (DEMOCI-11-011, DEMOCI-11-019)
# ---------------------------------------------------------------------------


@pytest.fixture
def help_text() -> str:
    """``vultron-demo rccv-extension --help`` as the sub-command renders it."""
    result = CliRunner().invoke(cli_main, ["rccv-extension", "--help"])
    assert result.exit_code == 0, result.output
    return result.output


class TestRccvExtensionCliCommand:
    """The generated sub-command offers one option per container."""

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
        ],
    )
    def test_the_option_is_offered(self, help_text: str, option: str):
        """One URL and one id option per container, plus the health skip."""
        assert option in help_text

    def test_the_case_actor_carries_no_id_option(self, help_text: str):
        """Only ``rccv-handoff`` exposes one (DEMOMA-14-008)."""
        assert "--case-actor-id" not in help_text

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
            patch.object(demo, "run_rccv_extension_demo") as run,
        ):
            demo.main(
                skip_health_check=True,
                c1_url="http://elsewhere:7999/api/v2",
                case_actor_url="http://ca:7999/api/v2",
                reporter_id="urn:test:reporter",
                c1_id="urn:test:c1",
                c2_id="urn:test:c2",
                vendor_id="urn:test:vendor",
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
        # The CaseActor's own container is addressed through its override,
        # never through C1's (DEMOMA-13-010).
        assert (
            built.call_args.kwargs["case_actor_url"] == "http://ca:7999/api/v2"
        )

        kwargs = run.call_args.kwargs
        assert kwargs["reporter_client"] is clients["reporter"]
        assert kwargs["c1_client"] is clients["c1"]
        assert kwargs["c2_client"] is clients["c2"]
        assert kwargs["vendor_client"] is clients["vendor"]
        assert kwargs["case_actor_client"] is clients["case-actor"]
        assert kwargs["c2_id"] == "urn:test:c2"


@pytest.fixture
def spec():
    """The one registry entry named ``rccv-extension``."""
    entries = [s for s in registered_scenarios() if s.name == "rccv-extension"]
    assert len(entries) == 1, entries
    return entries[0]


class TestRccvExtensionRegistryEntry:
    """The registry is the sole declaration that the scenario exists."""

    def test_the_entry_describes_the_second_coordinator_scenario(self, spec):
        """Every field is rendered into the generated scenario tables."""
        assert spec.label == "RCCV-extension"
        assert spec.participants == "Reporter + C1 + C2 + Vendor"
        assert spec.feature == "Second coordinator suggests vendor"
        assert spec.in_pr_set is False

    def test_the_path_is_read_off_the_story(self, spec):
        """``composed=True`` is what tells a check it places no step marks."""
        assert spec.composed is True
        assert spec.path == demo.STORY.path

    def test_the_derived_paths_point_at_this_module_and_its_harness(
        self, spec
    ):
        """Every artifact path derives from the name (DEMOCI-11-003)."""
        assert spec.demo_path == "vultron/demo/scenario/rccv_extension_demo.py"
        assert spec.harness_path == (
            "test/ci/invariants/test_rccv_extension_invariants.py"
        )


# ---------------------------------------------------------------------------
# The replica drain this scenario alone tells (DEMOMA-23-005, #3906)
# ---------------------------------------------------------------------------


class TestReplicasDrainBeforeTheVendor:
    """The drain goes through the one shared coverage helper.

    DEMOMA-23-005 and DEMOMA-23-006: the
    read-authority-tail-then-poll-each-replica loop lives in
    ``vultron/demo/helpers/sync.py`` and nowhere else (#3906).
    """

    def test_the_drain_names_c1_as_authority_and_the_joined_replicas(self):
        """Only the Reporter and C2 hold a replica before the Vendor joins."""
        state = _four_party_state()

        with patch.object(
            demo, "wait_for_replica_ledger_coverage"
        ) as coverage:
            demo.replicas_drain_before_the_vendor(state)

        coverage.assert_called_once()
        kwargs = coverage.call_args.kwargs
        assert kwargs["auth_client"] is state.client(two_coordinator_story.C1)
        assert kwargs["replicas"] == [
            (state.client(REPORTER), "Reporter"),
            (state.client(two_coordinator_story.C2), "C2"),
        ]
        assert kwargs["case_id"] == state.case.id_
        assert kwargs["phase_label"] == "opening drain before the Vendor joins"
        # The drain is the helper's default causal gate; the fragment must not
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

        state = _four_party_state()
        state.client(
            two_coordinator_story.C1
        ).base_url = "http://c1.test/api/v2"

        with (
            patch.object(
                sync_module, "_get_log_entries_for_case", return_value=[]
            ),
            patch.object(
                sync_module, "wait_for_contiguous_ledger_coverage"
            ) as per_replica,
        ):
            demo.replicas_drain_before_the_vendor(state)

        per_replica.assert_not_called()
        (failure,) = demo_utils._demo_failures
        assert failure.startswith("GATE FAILED")
        assert "http://c1.test/api/v2" in failure
        assert "opening drain before the Vendor joins" in failure
        assert "holds no CaseLedgerEntry" in failure
