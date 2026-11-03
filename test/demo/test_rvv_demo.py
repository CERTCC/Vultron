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

"""Unit tests for the RVV three-actor CVD demo (DEMOMA-09, D5-5, #5536).

``rvv`` is written as composition (ADR-0098,
:mod:`vultron.demo.helpers.story`): its opening is the shared
:data:`~vultron.demo.helpers.vendor_story.THE_VENDOR_ANSWERS_THE_REPORTER`
prefix it shares with ``rv`` and the ``rvcv`` pair, and its own story is the
continuation after Vendor1 decides to invite a second Vendor
(DEMOMA-09-007).  The checks that used to sit on its ``_phase_*`` functions
therefore sit here on three things:

* the **story's shape** — the path read off its choices, the identity of the
  stretch it shares with its siblings, and the order of its own fragments;
* each of its **own fragments**, driven against a
  :func:`~test.demo._helpers.story_state` stand-in cast, so a test observes
  what the fragment calls;
* the **surfaces around the story** — the CLI option set, the registry entry,
  the dedicated case-actor container and the devlogs names the invariant
  harness reads.

What the shared opening does is not re-tested here: it is one copy of the
code, and ``test/demo/vendor_story/`` owns it, along with every
continuation more than one of the four scenarios tells;
``test/demo/coordinated_story/`` owns the fragments the vendor-first
family reads from the rcv family.  The seeding helper this
scenario's character actor arrives through is driven for real, against a
FastAPI TestClient, in ``TestSeedContainersRvv``; so are the two ledger
polling primitives whose timeout behaviour the closure and sync phases depend
on.  Everywhere else the collaborators are patched out, so no HTTP happens;
``demo_gate`` / ``demo_check`` / ``demo_step`` stay real wherever the test is
about control flow and are stubbed to ``nullcontext`` only where it is about
call shape (``test_demo_context_managers.py`` owns their behaviour).
"""

import contextlib
import inspect
import json
import logging
from typing import cast
from unittest.mock import MagicMock, patch

import pytest
from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from fastapi.testclient import TestClient

import vultron.demo.helpers.polling as polling_module
import vultron.demo.helpers.sync as sync_module
import vultron.demo.scenario.rvv_demo as demo
import vultron.demo.utils as demo_utils
from test.demo._helpers import (
    devlogs_name_of,
    functions_referencing,
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
    closure,
    coordinated_story,
    seeding,
    story as story_module,
    story_cast,
    vendor_story,
)
from vultron.demo.helpers.cast import CAST, REPORTER_SLOT, VENDOR_SLOT
from vultron.demo.helpers.coordinated_story import (
    REPORTER,
    REPORTER_LABEL,
    cast as coordinated_cast,
    continuations as coordinated_continuations,
    joining as coordinated_joining,
)
from vultron.demo.helpers.polling import (
    wait_for_contiguous_ledger_coverage,
    wait_for_semantic_type_in_ledger,
)
from vultron.demo.helpers.story import (
    Choose,
    StoryState,
    UnseatedContainer,
    choose,
    run_story,
    story,
)
from vultron.demo.helpers.story_cast import CASE_ACTOR_NAME
from vultron.demo.helpers.vendor_story import (
    JOIN_TIMEOUT,
    REPORTER_TELLS_THE_VENDOR,
    THE_VENDOR_ANSWERS_THE_REPORTER,
    THE_VENDORS_CASE,
    VENDOR,
    VENDOR2,
    VENDOR2_LABEL,
    VENDOR_LABEL,
    VENDORS_ANSWER,
    cast as vendor_cast,
    continuations as vendor_continuations,
    opening as vendor_opening,
)
from vultron.demo.scenario import (
    rv_demo,
    rvcv_extension_demo,
    rvcv_handoff_demo,
)
from vultron.demo.scenario.registry import registered_scenarios
from vultron.demo.utils import DataLayerClient, reset_demo_failures
from vultron.enums.roles import CVDRole
from vultron.errors import DemoStoryError
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

#: Clear the process-global failure accumulator around every test.
pytestmark = pytest.mark.usefixtures("fresh_demo_failures")

#: The scenario's three cast names, in the order the story seats them.
_CAST = (REPORTER, VENDOR, VENDOR2)

#: How many items of ``STORY`` are the shared opening.
_PREFIX_LEN = len(THE_VENDOR_ANSWERS_THE_REPORTER.items)

#: This scenario's ``(devlogs name, cast name)`` pairs.  They are the same
#: word: every scenario of the family names its actors the same on the command
#: line, in ``ROLES`` and in its devlogs (``dump_vendor_ledgers``).
_DEVLOG_REPLICAS = tuple((name, name) for name in _CAST)


@contextlib.contextmanager
def _no_banners():
    """Every module a fragment of this scenario reaches, patched once."""
    with no_demo_banners(demo, coordinated_story, vendor_story):
        yield


def _three_party_state():
    """A story state seating all three, on an open case."""
    return story_state(*_CAST, case=mock_case())


def _choice_at(items, branch_point: str) -> Choose:
    """The choice *items* declares at *branch_point*.

    Read by search rather than by index: ``rv`` tells two replica checks of
    its own between the shared steps, so its ``vendor-after-answer`` choice
    does not sit where ``rvv``'s does (``vendor_story`` module docstring).
    """
    found = [
        item
        for item in items
        if isinstance(item, Choose) and item.branch_point == branch_point
    ]
    assert len(found) == 1, found
    return found[0]


# ---------------------------------------------------------------------------
# The story's shape (DEMOCI-11-019, DEMOCI-11-024, DEMOMA-09-007)
# ---------------------------------------------------------------------------


class TestRvvStoryShape:
    """``STORY`` places the scenario on the tree, and nothing else does."""

    #: The path ``rvv`` declared as ``@scenario(path=...)`` before it was
    #: composed.  The composed form must walk exactly the same tree ending, or
    #: the recordings, the generated index and the invariant harness all move
    #: with it.
    DECLARED_PATH = (
        ("reporter-whom-to-tell", "vendor"),
        ("vendor-after-answer", "invite-vendor"),
    )

    def test_the_story_walks_the_path_the_scenario_used_to_declare(self):
        """The path is read off the choices, not typed beside them."""
        assert demo.STORY.path == self.DECLARED_PATH

    @pytest.mark.spec("DEMOMA-09-007")
    def test_the_opening_is_the_shared_prefix_itself(self):
        """``rvv`` starts with the vendor-first family's named prefix.

        Identity of the shared stretch, not merely a matching sequence: this
        scenario's recording and its siblings' must be byte-identical up to
        the ``vendor-after-answer`` branch point (DEMOCI-11-018), which only
        holds while the opening is one copy of the code.  Comparing against
        ``THE_VENDOR_ANSWERS_THE_REPORTER.items`` is what stops a sibling
        slipping a step in before the branch point.
        """
        assert (
            demo.STORY.items[:_PREFIX_LEN]
            == THE_VENDOR_ANSWERS_THE_REPORTER.items
        )
        # Identity only: ``Choose`` is a frozen dataclass, so a hand-copied
        # duplicate compares equal and an equality arm would make this loop a
        # second spelling of the tuple comparison above.
        for mine, theirs in zip(
            demo.STORY.items[:_PREFIX_LEN],
            THE_VENDOR_ANSWERS_THE_REPORTER.items,
            strict=True,
        ):
            assert mine is theirs

    @pytest.mark.spec("DEMOMA-09-007")
    def test_the_prefix_itself_starts_with_the_reporter_telling_the_vendor(
        self,
    ):
        """The prefixes nest: the opening is not restated, it is continued.

        ``THE_VENDOR_ANSWERS_THE_REPORTER`` continues
        ``REPORTER_TELLS_THE_VENDOR``, so the report submission and Vendor1's
        triage are one copy of the code for all of ``rv``, ``rvv``,
        ``rvcv-extension`` and ``rvcv-handoff`` (DEMOCI-11-018).  Asserted on
        the prefix *and* on this story, so the chain reaches from the
        scenario back to the shortest shared stretch.
        """
        shared = len(REPORTER_TELLS_THE_VENDOR.items)
        assert (
            THE_VENDOR_ANSWERS_THE_REPORTER.items[:shared]
            == REPORTER_TELLS_THE_VENDOR.items
        )
        for mine, theirs in zip(
            demo.STORY.items[:shared],
            REPORTER_TELLS_THE_VENDOR.items,
            strict=True,
        ):
            assert mine is theirs

    def test_the_prefix_ends_with_the_vendor_answering_the_reporter(self):
        """Vendor1 decides only once it has answered the question.

        The ``vendor-after-answer`` branch point falls after Vendor1's own
        note in the thread the Reporter opened (DEMOMA-09-007), so the last
        item of the prefix is that exchange.
        """
        assert (
            THE_VENDOR_ANSWERS_THE_REPORTER.items[-1]
            is vendor_story.the_reporter_asks_about_the_workaround
        )

    def test_the_siblings_part_at_the_vendors_decision(self):
        """The first item after the prefix is the choice, and it differs."""
        branch = demo.STORY.items[_PREFIX_LEN]
        assert branch == Choose(
            branch_point="vendor-after-answer",
            choice="invite-vendor",
            by=VENDOR,
        )
        assert branch == _choice_at(demo.STORY.items, "vendor-after-answer")

    @pytest.mark.parametrize(
        "sibling",
        [rv_demo, rvcv_extension_demo, rvcv_handoff_demo],
        ids=lambda module: module.DEMO_NAME,
    )
    def test_every_sibling_takes_another_choice_at_that_branch_point(
        self, sibling
    ):
        """Two scenarios taking the same choice there are one scenario."""
        mine = _choice_at(demo.STORY.items, "vendor-after-answer")
        theirs = _choice_at(sibling.STORY.items, "vendor-after-answer")
        assert mine.choice != theirs.choice, (
            f"rvv and {sibling.DEMO_NAME} must take different choices at"
            " vendor-after-answer, or they are the same scenario"
        )

    def test_the_continuation_runs_in_the_declared_order(self):
        """One assertion for the whole continuation, so a reordering shows.

        The order is load-bearing twice over: Vendor2's container is seeded
        only after Vendor1's choice, because every record written before the
        case exists moves the first ledger entry away from the siblings
        (DEMOCI-11-018); and the invite names Vendor2 by actor id, so it
        follows the seeding that mints it (#2308).
        """
        assert demo.STORY.items[_PREFIX_LEN:] == (
            choose("vendor-after-answer", "invite-vendor", by=VENDOR),
            demo.the_second_vendor_is_seeded,
            demo.vendor1_invites_the_second_vendor,
            demo.the_case_is_active,
            demo.every_replica_converges,
            demo.the_second_vendor_adds_its_note,
            demo.both_vendors_fix_the_vul,
            demo.everyone_publishes,
            demo.everyone_closes,
        )

    def test_the_two_openers_are_seated_under_the_family_role_names(self):
        """One copy of the opening serves every vendor-first scenario."""
        assert REPORTER == coordinated_story.REPORTER
        assert VENDOR == coordinated_story.VENDOR
        # The devlogs and the CLI keep the scenario's own names, and each
        # actor sits in its cast slot rather than a URL of its own
        # (DEMOCI-11-020).
        assert [role.name for role in demo.ROLES] == [
            REPORTER,
            VENDOR,
            VENDOR2,
            CASE_ACTOR_NAME,
        ]
        assert [role.slot for role in demo.ROLES[:3]] == [
            REPORTER_SLOT,
            VENDOR_SLOT,
            CAST[3],
        ]


# ---------------------------------------------------------------------------
# The run's cast: Vendor2 is a character actor (DEMOCI-11-018, #5532)
# ---------------------------------------------------------------------------


class TestRvvCast:
    """Three containers are reset; the opening seeds two of them."""

    def _open(self):
        """Run the orchestrator and open its cast, collaborators stubbed."""
        clients = {name: mock_client() for name in _CAST}
        case_actor_client = mock_client()
        seeded = [
            mock_actor(f"urn:test:{name}") for name in (REPORTER, VENDOR)
        ]
        captured: dict[str, object] = {}

        with (
            patch.object(demo, "run_story") as run_story,
            patch.object(
                story_cast, "reset_datalayer", return_value={"status": "ok"}
            ) as reset,
            patch.object(seeding, "seed_case_actor_identity") as reseed,
            patch.object(
                vendor_cast, "seed_containers", return_value=tuple(seeded)
            ) as seed_two,
            patch.object(
                story_cast, "get_actor_by_id", side_effect=list(seeded)
            ),
            patch.object(demo, "seed_containers_rvv") as seed_three,
        ):
            demo.run_rvv_demo(
                reporter_client=clients[REPORTER],
                vendor_client=clients[VENDOR],
                vendor2_client=clients[VENDOR2],
                case_actor_client=case_actor_client,
                reporter_id="urn:test:reporter",
                vendor_id="urn:test:vendor",
                vendor2_id="urn:test:vendor2",
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
            "seed_two": seed_two,
            "seed_three": seed_three,
            "run_story": run_story,
            "state": cast(StoryState, captured["state"]),
        }

    @pytest.mark.spec("DEMOMA-01-003")
    @pytest.mark.spec("DEMOMA-09-001")
    def test_every_container_is_reset_and_the_case_actor_re_seeded(self):
        """A run starts clean on every container it touches, Vendor2's too.

        The reset wipes the CaseActor identity Vendor1 proposes the case to,
        so the dedicated container's identity is re-seeded after it
        (DEMOMA-06-004, #1876).
        """
        ran = self._open()

        assert [c.kwargs["client"] for c in ran["reset"].call_args_list] == [
            ran["clients"][REPORTER],
            ran["clients"][VENDOR],
            ran["clients"][VENDOR2],
            ran["case_actor_client"],
        ]
        ran["reseed"].assert_called_once_with(ran["case_actor_client"])

    @pytest.mark.spec("DEMOCI-11-018")
    def test_the_opening_seeds_only_the_reporter_and_the_first_vendor(self):
        """Vendor2's actor record would move the first ledger entry.

        Every actor and peer record the opening writes before the case exists
        is one more read of the recording clock, so seeding Vendor2 here would
        move the first ledger entry away from ``rv``'s and break the byte
        identity of the shared stretch (#5532).
        """
        ran = self._open()

        ran["seed_two"].assert_called_once()
        seeding_kwargs = ran["seed_two"].call_args.kwargs
        assert seeding_kwargs["reporter_client"] is ran["clients"][REPORTER]
        assert seeding_kwargs["vendor_client"] is ran["clients"][VENDOR]
        assert seeding_kwargs["case_actor_client"] is ran["case_actor_client"]
        ran["seed_three"].assert_not_called()

        state = ran["state"]
        assert sorted(state.cast) == sorted([REPORTER, VENDOR])
        assert sorted(state.unseated) == [VENDOR2]
        assert state.case_actor_client is ran["case_actor_client"]

    def test_the_second_vendors_container_waits_with_its_deterministic_id(
        self,
    ):
        """``--vendor2-id`` reaches the fragment that seeds it, not here.

        The recordings need the same ids on every run (DEMOCI-11-025), so the
        id the run was given has to survive as far as the seeding — which is
        what the waiting container carries it for.
        """
        ran = self._open()
        unseated = ran["state"].unseated

        assert isinstance(unseated[VENDOR2], UnseatedContainer)
        assert unseated[VENDOR2].client is ran["clients"][VENDOR2]
        assert unseated[VENDOR2].actor_id == "urn:test:vendor2"
        assert unseated[VENDOR2].label == VENDOR2_LABEL

    def test_the_orchestrator_plays_this_scenarios_story(self):
        """``run_story`` is handed the registered name and ``STORY``."""
        ran = self._open()

        assert ran["run_story"].call_args.args[0] == "rvv"
        assert ran["run_story"].call_args.args[1] is demo.STORY

    @pytest.mark.spec("DEMOMA-23-003")
    def test_the_cast_opening_arms_this_scenarios_dump(self):
        """The dump is armed when the case opens, and exactly once.

        Patched on this module, where the scenario reads the family's
        ``vendor_open_cast`` factory from: the scenario builds its
        ``open_cast`` callable through that factory rather than writing the
        closure out, so what it hands the factory is the whole declaration.
        """
        with (
            patch.object(demo, "run_story"),
            patch.object(demo, "vendor_open_cast") as open_vendor_cast,
        ):
            demo.run_rvv_demo(
                reporter_client=mock_client(),
                vendor_client=mock_client(),
                vendor2_client=mock_client(),
                case_actor_client=mock_client(),
                vendor2_id="urn:test:vendor2",
            )

        kwargs = open_vendor_cast.call_args.kwargs
        assert kwargs["dump"] is demo._dump_ledgers
        unseated = kwargs["unseated"]
        assert set(unseated) == {VENDOR2}
        assert isinstance(unseated[VENDOR2], UnseatedContainer)
        assert unseated[VENDOR2].label == VENDOR2_LABEL
        assert unseated[VENDOR2].actor_id == "urn:test:vendor2"


# ---------------------------------------------------------------------------
# Vendor2 is seeded after the branch point (DEMOCI-11-018, #5532)
# ---------------------------------------------------------------------------


class TestTheSecondVendorIsSeeded:
    """Vendor2 is seeded by the fragment that brings it into the case."""

    def test_the_seeding_fragment_is_the_only_caller_of_the_seeding(self):
        """Nothing else in the module may seed the three containers.

        A second call site — in particular one the shared opening could
        reach — is how the recording would drift again (DEMOCI-11-018).  Read
        from the source, so the claim holds for the code as written and not
        only for the path a test happens to drive.
        """
        assert functions_referencing(demo, "seed_containers_rvv") == [
            "the_second_vendor_is_seeded"
        ]

    def test_the_seeding_fragment_follows_the_vendors_choice(self):
        """It is placed after the ``vendor-after-answer`` choice."""
        items = demo.STORY.items
        branch = items.index(
            Choose(
                branch_point="vendor-after-answer",
                choice="invite-vendor",
                by=VENDOR,
            )
        )
        seeded = items.index(demo.the_second_vendor_is_seeded)
        assert branch < seeded, (
            "the_second_vendor_is_seeded must run after Vendor1's choice:"
            " every record it writes before then moves the first ledger"
            " entry's timestamp (DEMOCI-11-018)"
        )
        assert seeded >= _PREFIX_LEN, (
            "the shared opening must not reach the three-party seeding"
        )

    @pytest.mark.spec("DEMOMA-09-001")
    def test_the_fragment_seeds_all_three_then_seats_the_second_vendor(self):
        """The two already seeded are re-seeded idempotently.

        ``seed_containers_rvv`` registers every actor as a peer of the other
        two, which needs all three clients; ``POST /actors/`` and the peer
        registrations are idempotent, so the two the opening seeded come back
        unchanged.
        """
        state = story_state(REPORTER, VENDOR, unseated=(VENDOR2,))
        seeded = tuple(mock_actor(f"urn:test:{name}") for name in _CAST)
        # The waiting container is consumed by the seating, so hold it.
        waiting = state.container(VENDOR2)

        with (
            patch.object(
                demo, "seed_containers_rvv", return_value=seeded
            ) as seed,
            patch.object(
                coordinated_cast, "get_actor_by_id", side_effect=[seeded[2]]
            ) as lookup,
            _no_banners(),
        ):
            demo.the_second_vendor_is_seeded(state)

        kwargs = seed.call_args.kwargs
        assert kwargs["reporter_client"] is state.client(REPORTER)
        assert kwargs["vendor_client"] is state.client(VENDOR)
        assert kwargs["vendor2_client"] is waiting.client
        assert kwargs["reporter_actor_id"] == state.actor_id(REPORTER)
        assert kwargs["vendor_actor_id"] == state.actor_id(VENDOR)
        assert kwargs["case_actor_client"] is state.case_actor_client
        # The deterministic id comes from the waiting container, which holds
        # the --vendor2-id value the run was given (DEMOCI-11-025).
        assert kwargs["vendor2_actor_id"] == "urn:test:vendor2"

        # The new actor is read back from its own container (ADR-0073).
        assert [c.args[0] for c in lookup.call_args_list] == [waiting.client]
        assert state.unseated == {}
        assert state.actor_id(VENDOR2) == "urn:test:vendor2"

    @pytest.mark.spec("EDF-06-005")
    def test_a_failed_seeding_seats_nothing(self):
        """The seating is inside the step that seeded it (#2308).

        ``demo_step`` records a failure and lets the run continue, so a
        seating placed *after* the step would seat a Vendor2 the container
        never created — and the invite below names it by actor id.  The real
        ``demo_step`` runs here, because that nesting is the subject.
        """
        state = story_state(REPORTER, VENDOR, unseated=(VENDOR2,))

        with patch.object(
            demo,
            "seed_containers_rvv",
            side_effect=RuntimeError("container unreachable"),
        ):
            demo.the_second_vendor_is_seeded(state)

        assert VENDOR2 not in state.cast
        assert sorted(state.unseated) == [VENDOR2]
        (failure,) = demo_utils._demo_failures
        assert failure.startswith("STEP FAILED")

    def test_a_container_that_was_never_declared_stops_the_story(self):
        """The fragment reads the container the scenario declared."""
        state = story_state(REPORTER, VENDOR)

        with (
            patch.object(demo, "seed_containers_rvv"),
            patch.object(coordinated_cast, "get_actor_by_id"),
            _no_banners(),
            pytest.raises(DemoStoryError, match="no container waiting"),
        ):
            demo.the_second_vendor_is_seeded(state)


# ---------------------------------------------------------------------------
# Vendor1 invites Vendor2 directly (DEMOMA-09-002, CM-11-002)
# ---------------------------------------------------------------------------


class TestVendor1InvitesTheSecondVendor:
    """The inviter is the first Vendor, not the family's Coordinator.

    The invite is also where this scenario's CASE_MANAGER reads happen, so
    the dedicated case-actor routing is checked here rather than in a class
    of its own (DEMOMA-06-005, #1876).
    """

    @pytest.mark.spec("DEMOMA-09-002")
    def test_the_invite_comes_from_the_first_vendor_as_a_vendor_invite(self):
        """Vendor1 is CASE_OWNER, so it invites directly (ADR-0026 aside).

        The shared join step defaults its inviter to the coordinator-first
        family's Coordinator, which this scenario does not seat at all: the
        casting is the only thing ``rvv`` decides here, and getting it wrong
        would send the Invite from a cast member that does not exist.
        """
        state = _three_party_state()

        with patch.object(demo, "invitee_joins_the_case") as join:
            demo.vendor1_invites_the_second_vendor(state)

        join.assert_called_once()
        assert join.call_args.args == (state, VENDOR2, VENDOR2_LABEL)
        assert join.call_args.kwargs == {
            "role": CVDRole.VENDOR,
            "seated": (REPORTER, VENDOR, VENDOR2),
            "inviter": VENDOR,
            "inviter_label": VENDOR_LABEL,
            "milestone": None,
            "join_timeout": JOIN_TIMEOUT,
            "cross_container_timeout": JOIN_TIMEOUT,
        }

    @pytest.mark.spec("DEMOMA-17-002")
    def test_the_join_claims_no_milestone_number(self, caplog):
        """This scenario spends M2 on its replica synchronization.

        The shared join step numbers the arrival M2 by default, which every
        coordinator-first scenario wants.  ``rvv`` does not: it already logs
        ``✓ M2:`` for the sync phase, and ``docs/howto/demos/rvv-demo.md``
        documents that marker, so a second ``✓ M2:`` line here would make the
        two indistinguishable in the output that page describes (#5536).
        """
        state = _three_party_state()

        with (
            patch.object(coordinated_joining, "wait_for_case_on_container"),
            patch.object(coordinated_joining, "run_case_invite_chain"),
            patch.object(coordinated_joining, "wait_for_case_participants"),
            patch.object(coordinated_joining, "run_invite_path_rm_triage"),
            _no_banners(),
            caplog.at_level(logging.INFO),
        ):
            demo.vendor1_invites_the_second_vendor(state)

        assert "✓ Vendor2 joined case" in caplog.text
        assert "M2" not in caplog.text

    @pytest.mark.spec("CM-11-002")
    def test_the_second_vendor_triages_the_report_it_was_invited_over(self):
        """``triages`` is left at its default, and the default is what runs.

        A vendor judges the report it was invited over, so the join is the
        triaging form; the real shared step runs here, because the default is
        only observable through the triage it reaches (DEMOMA-17-002).
        """
        state = _three_party_state()

        with (
            patch.object(coordinated_joining, "wait_for_case_on_container"),
            patch.object(
                coordinated_joining, "run_case_invite_chain"
            ) as chain,
            patch.object(coordinated_joining, "wait_for_case_participants"),
            patch.object(
                coordinated_joining, "run_invite_path_rm_triage"
            ) as triage,
            _no_banners(),
        ):
            demo.vendor1_invites_the_second_vendor(state)

        inviter = chain.call_args.kwargs["inviter"]
        assert inviter.client is state.client(VENDOR)
        assert inviter.actor is state.actor(VENDOR).actor
        assert inviter.role is CVDRole.VENDOR
        assert chain.call_args.kwargs["invitee_client"] is state.client(
            VENDOR2
        )

        triage.assert_called_once()
        assert triage.call_args.kwargs["invited_client"] is state.client(
            VENDOR2
        )

    @pytest.mark.spec("CLP-08-005")
    def test_the_reporter_holds_the_case_before_the_triage(self):
        """Bug #2135: the join broadcasts to every participant.

        Vendor2's reply to the full-case Invite and its RM triage both
        broadcast ``Announce(CaseLedgerEntry)`` to all participants, so a
        Reporter without the case replica has no genesis hash to anchor the
        chain on.  The shared step owns the wait; this scenario is the one
        that reaches it through a Vendor as inviter.
        """
        state = _three_party_state()
        order: list[str] = []

        with (
            patch.object(
                coordinated_joining,
                "wait_for_case_on_container",
                side_effect=lambda client, **_kw: order.append(
                    f"replica:{devlogs_name_of(state, client, _DEVLOG_REPLICAS)}"
                ),
            ),
            patch.object(coordinated_joining, "run_case_invite_chain"),
            patch.object(coordinated_joining, "wait_for_case_participants"),
            patch.object(
                coordinated_joining,
                "run_invite_path_rm_triage",
                side_effect=lambda **_kw: order.append("triage"),
            ),
            _no_banners(),
        ):
            demo.vendor1_invites_the_second_vendor(state)

        assert order == ["replica:reporter", "triage"], order

    @pytest.mark.spec("DEMOMA-06-005")
    def test_every_case_manager_read_goes_to_the_dedicated_container(self):
        """The CaseActor is not hosted on Vendor1's container (#1876).

        Vendor1 holds a replica, not the CASE_MANAGER's store, so the Invite's
        canonical ledger reads and the invitee's triage authority must both
        name the dedicated case-actor client; Vendor1's replica holds a copy
        that no guarded commit of the CASE_MANAGER's ever wrote to.
        """
        state = _three_party_state()

        with (
            patch.object(coordinated_joining, "wait_for_case_on_container"),
            patch.object(
                coordinated_joining, "run_case_invite_chain"
            ) as chain,
            patch.object(coordinated_joining, "wait_for_case_participants"),
            patch.object(
                coordinated_joining, "run_invite_path_rm_triage"
            ) as triage,
            _no_banners(),
        ):
            demo.vendor1_invites_the_second_vendor(state)

        assert (
            chain.call_args.kwargs["case_manager_client"]
            is state.case_actor_client
        )
        assert triage.call_args.kwargs["auth_client"] is (
            state.case_actor_client
        )


# ---------------------------------------------------------------------------
# The milestones this scenario numbers (DEMOMA-09-003/004)
# ---------------------------------------------------------------------------


class TestTheCaseIsActive:
    """M1: every participant is seated and the embargo is still on.

    Whose replicas the shared check reads is the same in all four scenarios,
    so ``test/demo/vendor_story/`` owns it; the number and the participants
    this scenario expects by then are the only thing it decides.
    """

    def test_the_milestone_is_this_scenarios_m1(self):
        """The shared check takes the label from the scenario that numbers it."""
        state = _three_party_state()

        with patch.object(demo, "required_participants_are_present") as m1:
            demo.the_case_is_active(state)

        m1.assert_called_once()
        assert m1.call_args.args == (state,)
        check = m1.call_args.kwargs["check"]
        assert check.startswith("M1: "), check
        # The scenario expects four participants by then: three actors plus
        # the CaseActor the case was proposed to (DEMOMA-09-006).
        assert "≥4" in check, check


@pytest.mark.spec("DEMOMA-09-010")
class TestEveryReplicaConverges:
    """M2: LedgerFanout reached the Reporter and the second Vendor."""

    def test_the_first_vendor_is_the_authority_and_vendor2_the_late_joiner(
        self,
    ):
        """The shared sync helper declares no scenario fact of its own.

        Which container is authoritative, which hold replicas and which
        joined late all come from here (DEMOMA-23-007): there is no
        Coordinator in this scenario, so Vendor1 is the authority, and
        Vendor2 joined by invitation after the report was accepted (#2852).
        """
        state = _three_party_state()

        with patch.object(demo, "run_sync_verification_phase") as sync:
            demo.every_replica_converges(state)

        kwargs = sync.call_args.kwargs
        assert kwargs["auth_client"] is state.client(VENDOR)
        assert kwargs["auth_label"] == VENDOR_LABEL
        assert kwargs["auth_actor_id"] == state.actor_id(VENDOR)
        assert kwargs["reporter_client"] is state.client(REPORTER)
        assert kwargs["reporter_actor_id"] == state.actor_id(REPORTER)
        assert kwargs["replicas"] == [
            (state.client(REPORTER), REPORTER_LABEL),
            (state.client(VENDOR2), VENDOR2_LABEL),
        ]
        assert kwargs["state_checks"] == kwargs["replicas"]
        assert kwargs["case_id"] == state.case.id_
        assert kwargs["expected_participant_ids"] == {
            state.actor_id(who) for who in _CAST
        }
        assert kwargs["late_joiners"] == (state.client(VENDOR2),)

    @contextlib.contextmanager
    def _sync_primitives(self, participant_wait):
        """Run the real sync phase with its container reads stubbed out.

        Only the primitives are patched: the fragment's casting reaches the
        per-replica budget and the ``demo_check`` wrap through the real
        ``run_sync_verification_phase`` and ``wait_for_participants_on_replicas``,
        and a test of either alone would not see the casting.
        """
        with (
            patch.object(
                sync_module,
                "_get_log_entries_for_case",
                return_value=[
                    {"log_index": 5, "entry_hash": "abc123def456789a"}
                ],
            ),
            patch.object(sync_module, "wait_for_case_on_container"),
            patch.object(sync_module, "wait_for_contiguous_ledger_coverage"),
            # Patched on the polling module, which is the global the real
            # wait_for_participants_on_replicas calls.
            patch.object(
                polling_module, "wait_for_case_participants", participant_wait
            ),
            patch.object(
                sync_module, "verify_replica_state"
            ) as verify_replica,
        ):
            yield verify_replica

    def test_the_late_joiner_gets_the_extended_participant_budget(self):
        """#2852: Vendor2's replica waits on the late-joiner budget.

        Vendor2 catches up from genesis, so its participant index arrives
        later than the Reporter's; the 15 s default timed out spuriously
        under CI load.  The budget follows from naming Vendor2 a late joiner,
        so this is what makes that casting load-bearing.
        """
        state = _three_party_state()
        budgets: dict[int, float] = {}

        def _capture(**kwargs):
            budgets[id(kwargs["vendor_client"])] = kwargs["timeout_seconds"]

        with self._sync_primitives(_capture):
            demo.every_replica_converges(state)

        vendor2 = id(state.client(VENDOR2))
        reporter = id(state.client(REPORTER))
        assert budgets.get(vendor2) is not None, (
            "Vendor2's replica participant wait never ran"
        )
        assert budgets[vendor2] >= 30.0, (
            f"Vendor2 (late joiner) waits {budgets[vendor2]}s — must be"
            " >= 30 s; the shorter default times out under CI load (#2852)"
        )
        # The Reporter is an early participant and takes the shorter budget.
        assert budgets[reporter] < budgets[vendor2]

    def test_a_replica_participant_timeout_is_recorded_not_raised(self):
        """#3384/#3406: one replica's timeout must not stop the phase.

        ``wait_for_participants_on_replicas`` wraps each per-replica poll in
        its own ``demo_check``, so a timeout accumulates to ``_demo_failures``
        and the fragment returns — and the ``verify_replica_state`` checks
        after it still run for both replicas (DEMOCI-01-014).
        """
        state = _three_party_state()

        def _timeout(**_kwargs):
            raise AssertionError("participant propagation timeout")

        with self._sync_primitives(_timeout) as verify_replica:
            demo.every_replica_converges(state)

        failures = demo_utils._demo_failures
        assert len(failures) == 2, failures
        assert all(
            "reflects all case participants" in failure for failure in failures
        ), failures

        # A list rather than a set: a ``DataLayerClient`` is unhashable, and
        # the replicas are state-checked in the order the fragment names
        # them anyway.
        checked = [
            call.kwargs["replica_client"]
            for call in verify_replica.call_args_list
        ]
        assert checked == [state.client(REPORTER), state.client(VENDOR2)], (
            "both replica state checks must still run after a participant"
            f" wait timed out; got {checked!r}"
        )


# ---------------------------------------------------------------------------
# The note the second Vendor adds (DEMOCI-11-017)
# ---------------------------------------------------------------------------


class TestTheSecondVendorAddsItsNote:
    """Vendor2 answers the thread the shared opening posted.

    That a thread whose answer never landed stops the story is the shared
    step's own guarantee, which ``test/demo/vendor_story/`` owns; what this
    scenario decides is the single post it hands that step.
    """

    def _answered(self, state: StoryState) -> as_Note:
        """Record the Vendor's answer, as the shared opening's gate does."""
        answer = as_Note(
            name="Vendor1 Response", content="A workaround exists."
        )
        state.keep(VENDORS_ANSWER, answer)
        return answer

    def test_the_update_replies_to_the_first_vendors_answer(self):
        """One thread, not two: the joiner replies rather than opens.

        Every sibling posts the same question and answer, so a joiner that
        opened a thread of its own would make this scenario's note tree
        differ from theirs for no protocol reason (DEMOCI-11-017).
        """
        state = _three_party_state()
        answer = self._answered(state)

        with patch.object(vendor_continuations, "add_note_thread") as thread:
            demo.the_second_vendor_adds_its_note(state)

        watching_client, case, posts = thread.call_args.args
        assert watching_client is state.client(VENDOR)
        assert case is state.case
        assert thread.call_args.kwargs["in_reply_to"] is answer

        (post,) = posts
        assert post.poster is state.actor(VENDOR2)
        assert post.name == f"{VENDOR2_LABEL} Status Update"
        # Vendor2 speaks for its own component and its own fix timeline
        # (DEMOMA-09-009), which is what makes it a second fix path.
        assert "fix timeline" in post.content.lower()


# ---------------------------------------------------------------------------
# Both vendors fix the vul (DEMOMA-09-003, DEMOMA-09-009, CSB-15-002)
# ---------------------------------------------------------------------------


class TestBothVendorsFixTheVul:
    """Each vendor has a fix path of its own, and both stop at VFd.

    The two triggers, their per-vendor RM gates and the order they run in are
    the shared step's, which ``test/demo/vendor_story/`` owns; the milestone
    numbers are this scenario's.
    """

    def test_the_two_milestones_are_this_scenarios_m4_and_m5(self):
        """The shared step is told which milestones the labels belong to.

        The pair deliberately asserts the same thing twice, under two
        numbers, because consolidating the family's openings must not change
        what a scenario passes or fails on (DEMOMA-17-002, #5607).
        """
        state = _three_party_state()

        with patch.object(demo, "both_vendors_report_the_fix_ready") as fixed:
            demo.both_vendors_fix_the_vul(state)

        fixed.assert_called_once()
        assert fixed.call_args.args == (state,)
        first, second = fixed.call_args.kwargs["milestones"]
        assert first.startswith("M4: ")
        assert second.startswith("M5: ")
        assert "VFd" in second, second


# ---------------------------------------------------------------------------
# Publication and closure (DEMOMA-07-003, CM-23-015)
# ---------------------------------------------------------------------------


@pytest.mark.spec("DEMOMA-07-003")
class TestEveryonePublishes:
    """Vendor1, the Case Owner, publishes first; the Reporter last."""

    def test_the_order_is_vendor1_then_vendor2_then_the_reporter(self):
        """The Case Owner's ``notify-published`` is what ends the embargo.

        The whole fragment runs for real, so the order and the watcher of
        each embargo read are both checked: the termination is awaited on
        Vendor1's replica right after Vendor1 publishes, and a swapped owner
        would wait on the wrong trigger.
        """
        state = _three_party_state()
        order: list[str] = []

        def _name_of(client: object) -> str:
            return devlogs_name_of(state, client, _DEVLOG_REPLICAS)

        with (
            patch.object(
                vendor_continuations,
                "wait_for_case_em_terminated",
                side_effect=lambda client, case_id: order.append(
                    f"em_exited:{_name_of(client)}"
                ),
            ),
            patch.object(
                vendor_continuations, "wait_for_participant_vf_state"
            ),
            patch.object(vendor_continuations, "verify_publicly_disclosed"),
            patch.object(
                ActorSession,
                "notify_published",
                autospec=True,
                side_effect=lambda session: order.append(
                    f"published:{_name_of(session.client)}"
                ),
            ),
            _no_banners(),
        ):
            demo.everyone_publishes(state)

        assert order == [
            "published:vendor",
            "em_exited:vendor",
            "published:vendor2",
            "published:reporter",
            "em_exited:reporter",
        ], order

    def test_the_final_milestone_is_this_scenarios_m6(self):
        """The last check reads the Reporter's replica (DEMOMA-09-010)."""
        state = _three_party_state()

        with (
            patch.object(demo, "reports_published"),
            patch.object(demo, "the_embargo_ends_for") as embargo,
            patch.object(
                demo, "the_disclosure_reached_every_replica"
            ) as disclosed,
        ):
            demo.everyone_publishes(state)

        assert embargo.call_args.kwargs["watcher"] == VENDOR
        assert disclosed.call_args.kwargs["check"].startswith("M6: ")


@pytest.mark.spec("CM-23-015")
class TestEveryoneCloses:
    """Vendor2 and the Reporter leave; Vendor1, the owner, leaves last."""

    def test_the_owner_leaves_last_and_the_departures_are_read_canonically(
        self,
    ):
        """The owner's ``Leave`` is gated on the CASE_MANAGER's store.

        That store is on the dedicated case-actor container (DEMOMA-06-005),
        so the authority client must be that one and not Vendor1's replica,
        which holds a copy and not the canonical record.
        """
        state = _three_party_state()

        with (
            patch.object(ActorSession, "leave_case"),
            stub_closure_gate(),
            patch.object(
                coordinated_continuations, "close_case_owner_last"
            ) as closure_step,
        ):
            demo.everyone_closes(state)

        kwargs = closure_step.call_args.kwargs
        assert kwargs["milestone"] == "M7"
        assert kwargs["authority_client"] is state.case_actor_client
        assert [leaver.client for leaver in kwargs["others"]] == [
            state.client(VENDOR2),
            state.client(REPORTER),
        ]
        assert kwargs["owner"].client is state.client(VENDOR)
        assert kwargs["owner"].actor is state.actor(VENDOR).actor

    def test_a_coverage_timeout_is_recorded_rather_than_raised(self):
        """#1772/#1802: a bare coverage wait crashed the run on timeout.

        Every coverage wait now runs inside the shared closure helper's
        ``demo_check``, so a timeout accumulates to ``_demo_failures`` and the
        fragment returns normally — which is what lets the ledger dump run
        and the demo exit 0 with a failure summary (DEMOCI-01-003).  The
        primitive is patched on the helper's own module and the real closure
        step runs, so the whole chain is exercised.
        """
        state = _three_party_state()
        ledger = [
            {
                "case_id": state.case.id_,
                "log_index": index,
                "semantic_type": "close_case",
                "payload_snapshot": {"actor": state.actor_id(name)},
            }
            for index, name in enumerate((VENDOR2, REPORTER, VENDOR))
        ]
        # Held before the gate stub replaces it: the own-closure check is
        # what reaches the coverage wait, so this test needs the real one
        # back while the rest of the gate stays stubbed.
        real_own_closure = closure._verify_own_closure

        with (
            patch.object(ActorSession, "leave_case"),
            stub_closure_gate(),
            patch.object(closure, "_verify_own_closure", real_own_closure),
            patch.object(closure, "case_manager_ledger", return_value=ledger),
            patch.object(
                sync_module,
                "wait_for_contiguous_ledger_coverage",
                side_effect=AssertionError(
                    "contiguous ledger coverage timeout"
                ),
            ),
        ):
            demo.everyone_closes(state)

        failures = demo_utils._demo_failures
        assert len(failures) == 3, failures
        assert all("coverage timeout" in failure for failure in failures), (
            failures
        )


# ---------------------------------------------------------------------------
# A roster that never fills stops the story (DEMOCI-01-011, #5536)
# ---------------------------------------------------------------------------


class TestARosterThatNeverFillsStopsTheStory:
    """The guarantee the hand-placed form got from nesting.

    Before composition the whole continuation sat inside the roster's own
    ``demo_gate``, so a roster that never filled skipped it.  A flat story
    cannot nest, so the opening's gate keeps :data:`THE_VENDORS_CASE` and
    every continuation reads it — and the runner stops the story at the
    unreadable prop.  Driven through the real ``run_story``, the real
    ``demo_gate`` and the real fragments, because every link of that chain is
    load-bearing and a test of any one of them alone is what let the
    guarantee go missing in the coordinator-first half (#5535).
    """

    @pytest.fixture
    def marks(self, monkeypatch: MonkeyPatch):
        """Stand in for ``scenario_harness``, which needs a real case."""
        reset_demo_failures()
        harness = MagicMock()
        harness.demo_name = "rvv"

        @contextlib.contextmanager
        def stub(_demo_name: str):
            yield harness

        monkeypatch.setattr(story_module, "scenario_harness", stub)
        yield harness
        reset_demo_failures()

    @contextlib.contextmanager
    def _roster(self, *, fills: bool):
        """Run the opening with its roster filling or timing out.

        The roster gate in ``vendor_story.opening`` and the prop read in
        ``required_participants_are_present`` are the subject, so both stay
        real; only the container reads around them are stubbed.
        """
        case = mock_case()
        with (
            patch.object(
                vendor_opening,
                "reporter_submits_report",
                return_value=(MagicMock(), MagicMock(id_="urn:test:offer")),
            ),
            patch.object(
                vendor_opening, "run_direct_path_rm_triage", return_value=case
            ),
            patch.object(
                vendor_opening,
                "wait_for_case_participants",
                side_effect=None
                if fills
                else AssertionError("roster never filled"),
            ),
            patch.object(vendor_opening, "await_reporter_case_replica"),
            patch.object(vendor_opening, "as_VulnerabilityCase") as mock_vc,
            patch.object(vendor_continuations, "verify_case_active") as verify,
        ):
            # The re-read must be the case the story opened, or restate_case
            # refuses it (#5535); a distinct object with the same id is what
            # makes the re-read observable.
            mock_vc.model_validate.return_value = mock_case()
            yield verify

    def _play(self, state: StoryState) -> None:
        run_story(
            "rvv",
            story(
                vendor_story.the_reporter_tells_the_vendor,
                demo.the_case_is_active,
            ),
            lambda _harness: state,
        )

    def test_a_timed_out_roster_leaves_the_milestone_unchecked(self, marks):
        """The M1 check never runs, and the roster is the one failure."""
        state = story_state(*_CAST)

        with self._roster(fills=False) as verify:
            self._play(state)

        verify.assert_not_called()
        with pytest.raises(
            DemoStoryError, match="roster the Vendor confirmed"
        ):
            state.kept(THE_VENDORS_CASE)

    def test_a_filled_roster_lets_the_milestone_run(self, marks):
        """The counterpart, so the test above is not vacuous."""
        state = story_state(*_CAST)

        with self._roster(fills=True) as verify:
            self._play(state)

        assert state.kept(THE_VENDORS_CASE) == str(state.case.id_)
        verify.assert_called_once()


# ---------------------------------------------------------------------------
# The devlogs the invariant harness reads (DEMOMA-06-005, DEMOMA-06-009, DEMOMA-23-002)
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


class TestRvvLedgerDump:
    """Each replica is dumped under this scenario's own name for it."""

    #: Each actor's route key, deliberately unlike its devlogs name.
    SLUGS = {
        REPORTER: "reporter-9f3a",
        VENDOR: "vendor1-2b71",
        VENDOR2: "vendor2-4c05",
    }

    def _state_for_dump(self, case, seated=_CAST):
        """A story state whose clients are dump-ready, on *case*.

        Built rather than adapted: an ``ActorSession`` is frozen, so a bound
        client has to be the one the session is made with.
        """
        state = StoryState(
            cast={
                name: ActorSession(
                    client=_bound_client(self.SLUGS[name]),
                    actor=mock_actor(f"urn:test:{name}"),
                )
                for name in seated
            },
            case_actor_client=_bound_client("case-actor"),
            harness=MagicMock(demo_name="rvv"),
            dump=lambda _state: None,
        )
        state.open_case(case=case, report=MagicMock(), offer=MagicMock())
        return state

    def test_the_dump_writes_one_file_per_actor_under_the_demo_name(
        self, tmp_path, monkeypatch
    ):
        """Three devlogs names, each keyed on its own client's actor id."""
        case = as_VulnerabilityCase(
            attributed_to=CASE_OWNER_ID,
            id_="https://example.org/cases/rvv-test-case",
        )
        monkeypatch.setenv("DEVLOGS_DIR", str(tmp_path))

        demo._dump_ledgers(self._state_for_dump(case))

        case_slug = "https_example.org_cases_rvv-test-case"
        for devlogs_name in _CAST:
            assert (
                tmp_path
                / "rvv"
                / devlogs_name
                / f"{case_slug}-case-ledger.jsonl"
            ).exists(), devlogs_name

        # The route key selects the store (ADR-0073), so it must be the
        # client's own actor id and not the directory name beside it.
        manifest = json.loads(
            (tmp_path / "rvv" / "dump-manifest.json").read_text()
        )
        keys = {r["actorName"]: r["routeKey"] for r in manifest["actors"]}
        assert keys == {
            REPORTER: self.SLUGS[REPORTER],
            VENDOR: self.SLUGS[VENDOR],
            VENDOR2: self.SLUGS[VENDOR2],
            "case-actor": "case-actor",
        }

    @pytest.mark.spec("DEMOMA-06-005")
    @pytest.mark.spec("DEMOMA-06-009")
    def test_the_canonical_ledger_is_read_on_the_dedicated_container(
        self, tmp_path, monkeypatch
    ):
        """The CaseActor is not hosted on Vendor1's container (#1876).

        Vendor1 holds a replica, and dumping that as ``case-actor`` would hide
        exactly the topology fault this target exists to expose.
        """
        case = as_VulnerabilityCase(
            attributed_to=CASE_OWNER_ID,
            id_="https://example.org/cases/rvv-with-ca",
            actor_participant_index={
                "https://example.org/actors/case-actor": (
                    "https://example.org/cases/rvv-with-ca"
                    "/participants/case-actor"
                )
            },
        )
        monkeypatch.setenv("DEVLOGS_DIR", str(tmp_path))
        state = self._state_for_dump(case)

        demo._dump_ledgers(state)

        canonical = cast(MagicMock, state.case_actor_client.get_list)
        vendor_reads = cast(MagicMock, state.client(VENDOR).get_list)
        log_path = "/actors/case-actor/demo/cases/rvv-with-ca/log"
        assert any(
            log_path in call.args[0] for call in canonical.call_args_list
        )
        assert not any(
            "/actors/case-actor/" in call.args[0]
            for call in vendor_reads.call_args_list
        )

    def test_an_unseated_second_vendor_is_left_out_of_the_dump(
        self, tmp_path, monkeypatch
    ):
        """A run that failed before the seeding has no Vendor2 replica.

        The harness dumps on the way out whether or not a step failed
        (DEMOMA-23-002), so naming an actor the run never seated would 404
        the dump — and record a failure that is not the one that stopped the
        run (ISSUE-2239).
        """
        case = as_VulnerabilityCase(
            attributed_to=CASE_OWNER_ID,
            id_="https://example.org/cases/rvv-early-exit",
        )
        monkeypatch.setenv("DEVLOGS_DIR", str(tmp_path))
        state = self._state_for_dump(case, seated=(REPORTER, VENDOR))

        demo._dump_ledgers(state)

        assert not (tmp_path / "rvv" / VENDOR2).exists()
        manifest = json.loads(
            (tmp_path / "rvv" / "dump-manifest.json").read_text()
        )
        names = [r["actorName"] for r in manifest["actors"]]
        assert names == [REPORTER, VENDOR, "case-actor"], names


# ---------------------------------------------------------------------------
# The CLI sub-command and the registry entry (DEMOCI-11-011, DEMOCI-11-019)
# ---------------------------------------------------------------------------


@pytest.fixture
def help_text() -> str:
    """``vultron-demo rvv --help`` as the sub-command renders it."""
    result = CliRunner().invoke(cli_main, ["rvv", "--help"])
    assert result.exit_code == 0, result.output
    return result.output


class TestRvvCliCommand:
    """The generated sub-command offers one option per container."""

    def test_the_sub_command_describes_the_rvv_workflow(self, help_text: str):
        """The help text comes from the scenario module's ``CLI_HELP``."""
        assert "Reporter" in help_text
        assert "Vendor2" in help_text

    @pytest.mark.parametrize(
        "option",
        [
            "--skip-health-check",
            "--reporter-url",
            "--vendor-url",
            "--vendor2-url",
            "--case-actor-url",
            "--reporter-id",
            "--vendor-id",
            "--vendor2-id",
        ],
    )
    def test_the_option_is_offered(self, help_text: str, option: str):
        """One URL and one id option per container, plus the health skip."""
        assert option in help_text

    def test_the_case_actor_carries_no_id_option(self, help_text: str):
        """Only ``rccv-handoff`` exposes one (DEMOMA-14-023).

        The case-actor container seeds its own identity on reset
        (DEMOMA-06-004), so there is nothing here for an override to name.
        """
        assert "--case-actor-id" not in help_text

    def test_main_builds_one_client_per_container_and_runs_the_story(self):
        """``main()`` names its containers and passes their clients on."""
        clients = {
            name: MagicMock(name=name, base_url=f"http://{name}:7999/api/v2")
            for name in (REPORTER, VENDOR, VENDOR2, CASE_ACTOR_NAME)
        }

        with (
            patch.object(demo, "story_clients", return_value=clients) as built,
            patch.object(demo, "run_rvv_demo") as run,
        ):
            demo.main(
                skip_health_check=True,
                vendor_url="http://elsewhere:7999/api/v2",
                case_actor_url="http://ca:7999/api/v2",
                reporter_id="urn:test:reporter",
                vendor_id="urn:test:vendor",
                vendor2_id="urn:test:vendor2",
            )

        members = built.call_args.args[1]
        assert [(m.role, m.label) for m in members] == [
            (REPORTER, REPORTER_LABEL),
            (VENDOR, VENDOR_LABEL),
            (VENDOR2, VENDOR2_LABEL),
        ]
        assert [m.url for m in members] == [
            None,
            "http://elsewhere:7999/api/v2",
            None,
        ]
        assert built.call_args.kwargs["skip_health_check"] is True
        # The CaseActor's own container is addressed through its override,
        # never through Vendor1's (DEMOMA-09-006).
        assert (
            built.call_args.kwargs["case_actor_url"] == "http://ca:7999/api/v2"
        )

        kwargs = run.call_args.kwargs
        assert kwargs["reporter_client"] is clients[REPORTER]
        assert kwargs["vendor_client"] is clients[VENDOR]
        assert kwargs["vendor2_client"] is clients[VENDOR2]
        assert kwargs["case_actor_client"] is clients[CASE_ACTOR_NAME]
        assert kwargs["reporter_id"] == "urn:test:reporter"
        assert kwargs["vendor_id"] == "urn:test:vendor"
        assert kwargs["vendor2_id"] == "urn:test:vendor2"


@pytest.fixture
def spec():
    """The one registry entry named ``rvv``."""
    entries = [s for s in registered_scenarios() if s.name == "rvv"]
    assert len(entries) == 1, entries
    return entries[0]


class TestRvvRegistryEntry:
    """The registry is the sole declaration that ``rvv`` exists."""

    def test_the_entry_describes_the_second_vendor_scenario(self, spec):
        """Every field is rendered into the generated scenario tables."""
        assert spec.label == "RVV"
        assert spec.participants == "Reporter + Vendor1 + Vendor2"
        assert spec.feature == "Direct invitation of a second vendor"
        assert spec.in_pr_set is False

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
        assert spec.demo_path == "vultron/demo/scenario/rvv_demo.py"
        assert spec.harness_path == (
            "test/ci/invariants/test_rvv_invariants.py"
        )


# ---------------------------------------------------------------------------
# The seeding helper this scenario's character actor arrives through
# ---------------------------------------------------------------------------


@pytest.mark.spec("VP-08-004")
class TestSeedContainersRvv:
    """``seed_containers_rvv`` creates the three actors as peers.

    Driven against a real FastAPI TestClient, so the actor and peer records it
    writes are the ones a run writes.  The fragment that calls it is
    ``demo.the_second_vendor_is_seeded``, whose placement after the branch
    point is ``TestTheSecondVendorIsSeeded``'s subject (DEMOCI-11-018).
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

    def test_the_seeding_creates_all_three_actors(self, base: str):
        """Reporter, Vendor1 and Vendor2, each on its own container."""
        reporter, vendor, vendor2 = seeding.seed_containers_rvv(
            reporter_client=make_client(base),
            vendor_client=make_client(base),
            vendor2_client=make_client(base),
        )

        assert [a.name for a in (reporter, vendor, vendor2)] == [
            "Reporter",
            "Vendor",
            "Vendor2",
        ]
        assert all(a.id_ for a in (reporter, vendor, vendor2))

    def test_the_seeding_registers_every_actor_as_a_peer(self, base: str):
        """Vendor1 must know the Vendor2 it invites, and both the Reporter."""
        reporter_client = make_client(base)

        seeding.seed_containers_rvv(
            reporter_client=reporter_client,
            vendor_client=make_client(base),
            vendor2_client=make_client(base),
        )

        actors = reporter_client.get("/actors/")
        names = {a.get("name") for a in actors if isinstance(a, dict)}
        assert {"Reporter", "Vendor", "Vendor2"} <= names

    def test_a_deterministic_id_is_honoured_for_every_actor(self, base: str):
        """The recordings need the same ids on every run (DEMOCI-11-025)."""
        ids = {
            role: f"{base}/actors/{role}-rvv-det-test"
            for role in ("reporter", "vendor", "vendor2")
        }

        seeded = seeding.seed_containers_rvv(
            reporter_client=make_client(base),
            vendor_client=make_client(base),
            vendor2_client=make_client(base),
            reporter_actor_id=ids["reporter"],
            vendor_actor_id=ids["vendor"],
            vendor2_actor_id=ids["vendor2"],
        )

        assert [a.id_ for a in seeded] == list(ids.values())


# ---------------------------------------------------------------------------
# The ledger polling primitives the sync and closure steps rest on
# ---------------------------------------------------------------------------


class TestWaitForContiguousLedgerCoverage:
    """The pre-dump ledger coverage gate (issue #1363).

    The bug: the closure phase waited only for the tail entry hash before
    dumping the logs.  Because ``Announce(CaseLedgerEntry)`` activities arrive
    independently, an intermediate entry (e.g. ``logIndex=17``) could arrive
    after the tail, leaving the JSONL with a gap.
    ``wait_for_contiguous_ledger_coverage`` closes the race by verifying that
    *all* indices 0…expected_tail_index are present before the dump proceeds.
    """

    def _make_raw_entries(self, case_id: str, indices: list[int]) -> dict:
        """The dict ``GET /datalayer/CaseLedgerEntrys/`` returns."""
        return {
            f"entry-{i}": {
                "case_id": case_id,
                "log_index": i,
                "entry_hash": f"hash{i:04d}",
            }
            for i in indices
        }

    def test_it_returns_when_all_indices_are_present(self):
        """Returns at once when indices 0…N are all there."""
        case_id = "https://example.org/cases/test-coverage-1"
        client = MagicMock()
        client.get.return_value = self._make_raw_entries(
            case_id, list(range(5))
        )

        wait_for_contiguous_ledger_coverage(
            client=client,
            case_id=case_id,
            expected_tail_index=4,
            timeout_seconds=1.0,
        )
        assert client.get.call_count >= 1

    def test_it_raises_when_an_intermediate_index_is_missing(self):
        """The exact race of #1363: 0…16 and 18…20 present, 17 absent."""
        case_id = "https://example.org/cases/test-coverage-2"
        indices_with_gap = list(range(17)) + list(range(18, 21))
        client = MagicMock()
        client.get.return_value = self._make_raw_entries(
            case_id, indices_with_gap
        )

        with pytest.raises(AssertionError, match="contiguous ledger coverage"):
            wait_for_contiguous_ledger_coverage(
                client=client,
                case_id=case_id,
                expected_tail_index=20,
                timeout_seconds=0.1,
                poll_interval=0.05,
            )

    def test_it_raises_when_the_tail_arrived_before_the_early_entries(self):
        """A tail-only read is what the old tail-hash wait accepted."""
        case_id = "https://example.org/cases/test-coverage-3"
        client = MagicMock()
        client.get.return_value = self._make_raw_entries(case_id, [5])

        with pytest.raises(AssertionError, match="contiguous ledger coverage"):
            wait_for_contiguous_ledger_coverage(
                client=client,
                case_id=case_id,
                expected_tail_index=5,
                timeout_seconds=0.1,
                poll_interval=0.05,
            )

    def test_it_ignores_entries_for_other_cases(self):
        """Another case's entries do not count toward coverage."""
        case_id = "https://example.org/cases/target-case"
        other_case_id = "https://example.org/cases/other-case"
        client = MagicMock()
        target_entries = self._make_raw_entries(case_id, list(range(4)))
        other_entries = self._make_raw_entries(
            other_case_id, list(range(4, 10))
        )
        client.get.return_value = {**target_entries, **other_entries}

        with pytest.raises(AssertionError, match="contiguous ledger coverage"):
            wait_for_contiguous_ledger_coverage(
                client=client,
                case_id=case_id,
                expected_tail_index=5,
                timeout_seconds=0.1,
                poll_interval=0.05,
            )

    def test_it_raises_when_no_entries_are_present(self):
        """An empty DataLayer is a timeout, not a pass."""
        case_id = "https://example.org/cases/test-coverage-4"
        client = MagicMock()
        client.get.return_value = {}

        with pytest.raises(AssertionError, match="contiguous ledger coverage"):
            wait_for_contiguous_ledger_coverage(
                client=client,
                case_id=case_id,
                expected_tail_index=3,
                timeout_seconds=0.1,
                poll_interval=0.05,
            )

    def test_the_default_timeout_tolerates_ci_scheduling_latency(self):
        """At least 30 s, or the fan-out times out spuriously (#1911).

        The ``rv`` Demo Integration job failed intermittently with two
        cascading check failures when the coverage wait timed out after 15 s
        under CI load; the second failure cascaded because it ran straight
        after and found an empty replica.
        """
        sig = inspect.signature(wait_for_contiguous_ledger_coverage)
        default_timeout = sig.parameters["timeout_seconds"].default
        assert default_timeout >= 30.0, (
            "wait_for_contiguous_ledger_coverage's default timeout is"
            f" {default_timeout}s — must be >= 30s to tolerate CI load"
            " (issue #1911)"
        )


class TestWaitForSemanticTypeInLedger:
    """Wait for an asynchronously committed entry before reading the tail.

    Without the wait the tail excludes the entry, coverage "succeeds" for the
    wrong tail, the dump runs before the entry replicates, and the invariant
    harness fails (issue #1772).  The close phase it was found in no longer
    reads the authority's tail: a closed participant is sent nothing after its
    own closure entries (CM-23-004, CM-23-031).
    """

    def _make_entries(self, case_id: str, semantic_types: list[str]) -> dict:
        """One entry per semantic type, in log order."""
        return {
            f"e{i}": {
                "case_id": case_id,
                "log_index": i,
                "entry_hash": f"hash{i:04d}",
                "semantic_type": et,
            }
            for i, et in enumerate(semantic_types)
        }

    def test_it_returns_when_the_semantic_type_is_present(self):
        """Returns at once when the target type is already in the log."""
        case_id = "https://example.org/cases/bug-b-present"
        client = MagicMock()
        client.get.return_value = self._make_entries(
            case_id, ["validate_report", "close_case"]
        )

        wait_for_semantic_type_in_ledger(
            client=client,
            case_id=case_id,
            semantic_type="close_case",
            timeout_seconds=1.0,
        )
        assert client.get.call_count >= 1

    def test_it_raises_when_the_semantic_type_never_appears(self):
        """A missing entry is a timeout naming the type waited for."""
        case_id = "https://example.org/cases/bug-b-absent"
        client = MagicMock()
        client.get.return_value = self._make_entries(
            case_id,
            ["validate_report", "add_participant_status_to_participant"],
        )

        with pytest.raises(AssertionError, match="close_case"):
            wait_for_semantic_type_in_ledger(
                client=client,
                case_id=case_id,
                semantic_type="close_case",
                timeout_seconds=0.1,
                poll_interval=0.05,
            )

    def test_it_ignores_entries_from_other_cases(self):
        """Another case's ``close_case`` is not this case's."""
        case_id = "https://example.org/cases/bug-b-target"
        other_case_id = "https://example.org/cases/bug-b-other"
        client = MagicMock()
        entries = self._make_entries(case_id, ["validate_report"])
        other_entries = {
            "other-e0": {
                "case_id": other_case_id,
                "log_index": 0,
                "entry_hash": "hashOther",
                "semantic_type": "close_case",
            }
        }
        client.get.return_value = {**entries, **other_entries}

        with pytest.raises(AssertionError, match="close_case"):
            wait_for_semantic_type_in_ledger(
                client=client,
                case_id=case_id,
                semantic_type="close_case",
                timeout_seconds=0.1,
                poll_interval=0.05,
            )

    def test_it_returns_once_the_entry_arrives(self):
        """The wait polls, so an entry that lands late still passes."""
        case_id = "https://example.org/cases/bug-b-eventual"
        call_count = 0
        no_close_entries = self._make_entries(case_id, ["validate_report"])
        with_close_entries = self._make_entries(
            case_id, ["validate_report", "close_case"]
        )

        def _get_side_effect(_path: str):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return no_close_entries
            return with_close_entries

        client = MagicMock()
        client.get.side_effect = _get_side_effect

        wait_for_semantic_type_in_ledger(
            client=client,
            case_id=case_id,
            semantic_type="close_case",
            timeout_seconds=5.0,
            poll_interval=0.05,
        )
        assert call_count >= 3
