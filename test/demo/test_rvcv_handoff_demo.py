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

"""Unit tests for the RVCV-handoff five-actor CVD demo (DEMOMA-11, #5536).

``rvcv-handoff`` is written as composition (ADR-0098,
:mod:`vultron.demo.helpers.story`): its opening is the shared
:data:`~vultron.demo.helpers.vendor_coordinator_story\
.THE_VENDOR_INVITES_A_COORDINATOR` prefix it shares with ``rvcv-extension``,
itself continuing the vendor-first family's
:data:`~vultron.demo.helpers.vendor_story.THE_VENDOR_ANSWERS_THE_REPORTER`,
and its own story is the continuation after Vendor1 decides to offer ownership
to the Coordinator (DEMOMA-11-015).  The checks that used to sit on its
``_phase_*`` functions therefore sit here on three things:

* the **story's shape** — the path read off its choices, the identity of the
  stretch it shares with ``rvcv-extension``, and the order of its own
  fragments;
* each of its **own fragments**, driven against a
  :func:`~test.demo._helpers.story_state` stand-in cast, so a test observes
  what the fragment calls;
* the **surfaces around the story** — the CLI option set, the registry entry
  and the devlogs names the invariant harness reads.

What the shared opening does is not re-tested here: it is one copy of the code,
and ``test/demo/coordinated_story/`` and the vendor family's own test
modules own it.  The two ``owner-keep-case`` continuations are shared with the
coordinator-first half, so ``test/demo/owner_decision_story/`` owns
their mechanics and this module asserts only which parts ``rvcv-handoff``
casts in them — and, where the casting is only observable by its effect, what
that casting makes the shared continuation do.

Two classes at the end are not about this scenario's fragments at all: they
drive the real ownership-transfer protocol over isolated FastAPI apps
(CM-21-007, SYNC-15-013/014) and are kept here because this is the scenario
whose acceptance criteria they came from.

Every other test patches the collaborators out, so no HTTP happens.
``demo_gate`` / ``demo_check`` / ``demo_step`` stay real wherever the test is
about control flow and are stubbed to ``nullcontext`` only where it is about
call shape (``test_demo_context_managers.py`` owns their behaviour).
"""

import contextlib
import json
from collections.abc import Iterator, Mapping
from datetime import timedelta
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner

import vultron.demo.scenario.rvcv_extension_demo as extension_demo
import vultron.demo.scenario.rvcv_handoff_demo as demo
from test.demo._helpers import (
    devlogs_name_of,
    mock_actor,
    mock_case,
    mock_client,
    no_demo_banners,
    patch_chain_shared,
    story_state,
)
from test.support.act_runner import run_in_act
from test.support.case_owner import CASE_OWNER_ID
from test.support.objects import make
from test.support.received import received_of_type
from vultron.demo.actor_session import ActorSession
from vultron.demo.cli import main as cli_main
from vultron.demo.helpers import (
    coordinated_story,
    owner_decision_story,
    story_cast,
    vendor_coordinator_story,
    vendor_story,
)
from vultron.demo.helpers.coordinated_story import (
    COORDINATOR,
    COORDINATOR_LABEL,
    REPORTER,
    continuations as coordinated_continuations,
    joining as coordinated_joining,
)
from vultron.demo.helpers.owner_decision_story import (
    REPORTER_PART,
    handover as owner_decision_handover,
    parts as owner_decision_parts,
)
from vultron.demo.helpers.story import (
    Choose,
    StoryState,
    UnseatedContainer,
    choose,
    run_story,
    runner as story_runner,
    story,
)
from vultron.demo.helpers.vendor_coordinator_story import (
    COORDINATOR_JOINED,
    COORDINATOR_PART,
    DEVLOG_REPLICAS,
    THE_VENDOR_INVITES_A_COORDINATOR,
    dump_vendor_coordinator_ledgers,
)
from vultron.demo.helpers.vendor_story import (
    THE_VENDOR_ANSWERS_THE_REPORTER,
    VENDOR,
    VENDOR2,
    VENDOR2_LABEL,
    VENDOR2_PART,
    VENDOR_PART,
    VENDORS_ANSWER,
    cast as vendor_cast,
    continuations as vendor_continuations,
)
from vultron.demo.in_process import (
    InProcessRouter,
    IsolatedActorApp,
    create_isolated_actor_app,
)
from vultron.demo.scenario.registry import registered_scenarios
from vultron.demo.utils import reset_demo_failures
from vultron.enums.roles import CVDRole
from vultron.errors import DemoStoryError
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

#: Clear the process-global failure accumulator around every test.
pytestmark = pytest.mark.usefixtures("fresh_demo_failures")

#: The scenario's four cast names, in the order the story seats them.
_CAST = (REPORTER, VENDOR, COORDINATOR, VENDOR2)

#: How many items of ``STORY`` are the shared opening.
_PREFIX_LEN = len(THE_VENDOR_INVITES_A_COORDINATOR.items)

#: The scenario's ``(devlogs name, cast name)`` pairs.  Every actor of this
#: pair is named the same on the command line, in ``ROLES`` and in its devlogs
#: (DEMOMA-19-018), so each pair is a name beside itself.
_DEVLOGS = tuple((name, name) for name in DEVLOG_REPLICAS)


@contextlib.contextmanager
def _no_banners():
    """Every module a fragment of this scenario reaches, patched once."""
    with no_demo_banners(
        demo,
        coordinated_story,
        vendor_story,
        vendor_coordinator_story,
        owner_decision_story,
    ):
        yield


def _four_party_state():
    """A story state seating all four, on an open case."""
    return story_state(*_CAST, case=mock_case())


# ---------------------------------------------------------------------------
# The story's shape (DEMOCI-11-019, DEMOCI-11-024, DEMOMA-11-015)
# ---------------------------------------------------------------------------


class TestRvcvHandoffStoryShape:
    """``STORY`` places the scenario on the tree, and nothing else does."""

    #: The path ``rvcv-handoff`` declared as ``@scenario(path=...)`` before it
    #: was composed.  The composed form must walk exactly the same tree
    #: ending, or the recordings, the generated index and the invariant
    #: harness all move with it.
    DECLARED_PATH = (
        ("reporter-whom-to-tell", "vendor"),
        ("vendor-after-answer", "invite-coordinator"),
        ("owner-keep-case", "offer-ownership"),
    )

    def test_the_story_walks_the_path_the_scenario_used_to_declare(self):
        """The path is read off the choices, not typed beside them."""
        assert demo.STORY.path == self.DECLARED_PATH, (
            "DEMOCI-11-019: a composed scenario's path is its choices in"
            " order, and this one must still end the same branch it declared"
        )

    @pytest.mark.spec("DEMOMA-11-015")
    def test_the_opening_is_the_shared_prefix_itself(self):
        """``rvcv-handoff`` and ``rvcv-extension`` start with one prefix.

        Identity of the shared stretch, not merely a matching sequence: the
        two recordings must be byte-identical up to the ``owner-keep-case``
        branch point (DEMOCI-11-018), which only holds while the opening is
        one copy of the code.  Comparing against
        ``THE_VENDOR_INVITES_A_COORDINATOR.items`` is what stops a sibling
        slipping a step in before the branch point.
        """
        shared = THE_VENDOR_INVITES_A_COORDINATOR.items
        assert demo.STORY.items[:_PREFIX_LEN] == shared, (
            "DEMOMA-11-015: the story begins with the items of"
            " THE_VENDOR_INVITES_A_COORDINATOR"
        )
        assert extension_demo.STORY.items[:_PREFIX_LEN] == shared, (
            "DEMOMA-11-015: rvcv-extension begins with the same prefix"
        )
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

    @pytest.mark.spec("DEMOMA-11-015")
    def test_the_prefix_itself_starts_with_the_vendor_familys_opening(self):
        """The prefixes nest, so no sibling slips a step in before a branch.

        ``THE_VENDOR_INVITES_A_COORDINATOR`` continues
        ``THE_VENDOR_ANSWERS_THE_REPORTER``, so the report submission,
        Vendor1's triage and the Reporter's workaround thread are one copy of
        the code for all of ``rv``, ``rvv`` and this pair (DEMOCI-11-018).
        """
        shared = THE_VENDOR_ANSWERS_THE_REPORTER.items
        assert THE_VENDOR_INVITES_A_COORDINATOR.items[: len(shared)] == shared
        for mine, theirs in zip(
            demo.STORY.items[: len(shared)], shared, strict=True
        ):
            assert mine is theirs

    def test_the_siblings_part_at_the_owners_decision(self):
        """The first item after the prefix is this scenario's own choice.

        The pair's paths agree up to ``owner-keep-case`` and differ there:
        Vendor1 hands the case over here and keeps it in ``rvcv-extension``,
        which is what makes them two scenarios (DEMOMA-11-015).
        """
        assert demo.STORY.items[_PREFIX_LEN] == Choose(
            branch_point="owner-keep-case",
            choice="offer-ownership",
            by=VENDOR,
        )
        assert demo.STORY.path[:-1] == extension_demo.STORY.path[:-1], (
            "the pair shares every step before the owner's decision"
        )
        assert demo.STORY.path[-1] != extension_demo.STORY.path[-1], (
            "rvcv-handoff and rvcv-extension must take different choices at"
            " owner-keep-case, or they are the same scenario"
        )

    def test_the_prefix_ends_with_the_coordinator_joining(self):
        """Vendor1 decides only once the Coordinator is a participant.

        CM-21-021: the transferee must hold the case's coordinating role and
        be an active participant before the case is offered to it.
        """
        assert (
            THE_VENDOR_INVITES_A_COORDINATOR.items[-1]
            is vendor_coordinator_story.the_vendor_invites_the_coordinator
        )

    def test_the_continuation_runs_in_the_declared_order(self):
        """One assertion for the whole continuation, so a reordering shows.

        The order is load-bearing: the handover comes before the Coordinator
        invites anyone, because only the Case Owner may invite
        (DEMOMA-11-003).
        """
        assert demo.STORY.items[_PREFIX_LEN:] == (
            choose("owner-keep-case", "offer-ownership", by=VENDOR),
            demo.vendor1_hands_the_case_to_the_coordinator,
            demo.the_coordinator_invites_the_second_vendor,
            demo.the_case_is_active,
            vendor_coordinator_story.every_replica_converges,
            demo.the_four_exchange_notes,
            demo.both_vendors_fix_the_vul,
            demo.everyone_publishes,
            demo.everyone_closes,
        )

    def test_the_cast_is_seated_under_the_family_role_names(self):
        """One copy of each shared fragment serves the whole family.

        The parts the shared continuations act on name the cast members by the
        family's own names, which is how one copy of ``owner_decision_story``
        serves both halves of the tree (DEMOMA-17-001).
        """
        assert VENDOR_PART.name == VENDOR
        assert COORDINATOR_PART.name == COORDINATOR
        assert VENDOR2_PART.name == VENDOR2
        assert REPORTER_PART.name == REPORTER
        # The devlogs and the CLI keep the scenario's own names and order.
        assert [role.name for role in demo.ROLES] == [
            "reporter",
            "vendor",
            "coordinator",
            "case-actor",
            "vendor2",
        ]


# ---------------------------------------------------------------------------
# The run's cast: the Coordinator and Vendor2 are character actors
# (DEMOCI-11-018, #5532)
# ---------------------------------------------------------------------------


class TestRvcvHandoffCast:
    """Five containers are reset; the opening seeds two of them."""

    def _open(self):
        """Run the orchestrator and open its cast, collaborators stubbed."""
        clients = {
            name: mock_client()
            for name in ("reporter", "vendor", "coordinator", "vendor2")
        }
        case_actor_client = mock_client()
        seeded = [
            MagicMock(id_=f"urn:test:{name}")
            for name in ("reporter", "vendor")
        ]
        captured: dict[str, object] = {}

        with (
            patch.object(demo, "run_story") as run_story_mock,
            patch.object(
                story_cast, "reset_datalayer", return_value={"status": "ok"}
            ) as reset,
            patch(
                "vultron.demo.helpers.seeding.reset.seed_case_actor_identity"
            ) as reseed,
            patch.object(
                vendor_cast, "seed_containers", return_value=tuple(seeded)
            ) as seed_two,
            patch.object(
                story_cast, "get_actor_by_id", side_effect=list(seeded)
            ),
            patch.object(
                vendor_coordinator_story, "seed_containers_rvcv"
            ) as seed_four,
        ):
            demo.run_rvcv_handoff_demo(
                reporter_client=clients["reporter"],
                vendor_client=clients["vendor"],
                coordinator_client=clients["coordinator"],
                case_actor_client=case_actor_client,
                vendor2_client=clients["vendor2"],
                reporter_id="urn:test:reporter",
                vendor_id="urn:test:vendor",
                coordinator_id="urn:test:coordinator",
                vendor2_id="urn:test:vendor2",
            )
            # run_story() is what plays the story; the cast opening is the
            # callable it is handed, so the test runs that and nothing else.
            open_cast = run_story_mock.call_args.args[2]
            captured["state"] = open_cast(MagicMock())
        return {
            "clients": clients,
            "case_actor_client": case_actor_client,
            "reset": reset,
            "reseed": reseed,
            "seed_two": seed_two,
            "seed_four": seed_four,
            "run_story": run_story_mock,
            "state": captured["state"],
        }

    @pytest.mark.spec("DEMOMA-11-001")
    def test_every_container_is_reset_and_the_case_actor_re_seeded(self):
        """DEMOMA-01-003: a run starts clean on every container it touches.

        The Coordinator's and Vendor2's containers are reset with the rest
        although neither is seeded yet (DEMOCI-11-018).  The reset wipes the
        CaseActor identity Vendor1 proposes the case to, so the dedicated
        container's identity is re-seeded after it (DEMOMA-06-004, #1876).
        """
        ran = self._open()

        assert [c.kwargs["client"] for c in ran["reset"].call_args_list] == [
            ran["clients"]["reporter"],
            ran["clients"]["vendor"],
            ran["clients"]["coordinator"],
            ran["clients"]["vendor2"],
            ran["case_actor_client"],
        ], "every container the run touches is reset (DEMOMA-01-003)"
        ran["reseed"].assert_called_once_with(ran["case_actor_client"])

    @pytest.mark.spec("DEMOCI-11-018")
    def test_the_opening_seeds_only_the_reporter_and_vendor1_containers(self):
        """A further actor record would move the first ledger entry's time.

        #5532: the shared opening seeds only the containers every vendor-first
        sibling uses, so this pair's recordings match ``rv``'s and ``rvv``'s
        byte for byte up to the branch point.
        """
        ran = self._open()

        ran["seed_two"].assert_called_once()
        seeding = ran["seed_two"].call_args.kwargs
        assert seeding["reporter_client"] is ran["clients"]["reporter"]
        assert seeding["vendor_client"] is ran["clients"]["vendor"]
        ran["seed_four"].assert_not_called()

        state = ran["state"]
        assert sorted(state.cast) == sorted([REPORTER, VENDOR])
        assert sorted(state.unseated) == sorted([COORDINATOR, VENDOR2])

    def test_the_late_containers_wait_with_their_deterministic_ids(self):
        """``--coordinator-id`` and ``--vendor2-id`` reach their own seeder.

        DEMOCI-11-025: the recordings need the same ids on every run, so the
        id a run was given has to travel to the fragment that seeds the
        container rather than being dropped when the opening skips it.
        """
        ran = self._open()
        unseated = ran["state"].unseated

        assert isinstance(unseated[COORDINATOR], UnseatedContainer)
        assert unseated[COORDINATOR].client is ran["clients"]["coordinator"]
        assert unseated[COORDINATOR].actor_id == "urn:test:coordinator"
        assert unseated[COORDINATOR].label == COORDINATOR_LABEL
        assert isinstance(unseated[VENDOR2], UnseatedContainer)
        assert unseated[VENDOR2].client is ran["clients"]["vendor2"]
        assert unseated[VENDOR2].actor_id == "urn:test:vendor2"
        assert unseated[VENDOR2].label == VENDOR2_LABEL

    def test_the_orchestrator_plays_this_scenarios_story(self):
        """``run_story`` is handed the registered name and ``STORY``."""
        ran = self._open()

        assert ran["run_story"].call_args.args[0] == "rvcv-handoff"
        assert ran["run_story"].call_args.args[1] is demo.STORY

    @pytest.mark.spec("DEMOMA-23-003")
    def test_the_cast_opening_arms_this_scenarios_ledger_dump(self):
        """The dump the case opening arms is this scenario's own wrapper."""
        assert self._open()["state"].dump is dump_vendor_coordinator_ledgers


# ---------------------------------------------------------------------------
# The handover and the new owner's invite (DEMOMA-11-002/003/004/014)
# ---------------------------------------------------------------------------


@pytest.mark.spec("DEMOMA-11-002")
class TestVendor1HandsTheCaseToTheCoordinator:
    """The scenario casts Vendor1 as owner and the Coordinator as new owner."""

    def test_the_handover_names_vendor1_and_the_coordinator(self):
        """The mechanics are shared; which part each plays is the scenario's.

        ``owner_decision_story`` takes ``Part``\\ s off the running story, so
        the only thing this scenario decides is the casting — and getting it
        backwards would transfer ownership the wrong way (DEMOMA-11-004,
        DEMOMA-11-014).  It also names the join the transfer presupposes,
        which the continuation reads before it offers anything (CM-21-021).
        """
        state = _four_party_state()

        with patch.object(demo, "the_owner_hands_the_case_over") as handover:
            demo.vendor1_hands_the_case_to_the_coordinator(state)

        handover.assert_called_once()
        assert handover.call_args.args == (state,)
        assert handover.call_args.kwargs == {
            "joined": COORDINATOR_JOINED,
            "owner": VENDOR_PART,
            "new_owner": COORDINATOR_PART,
        }
        assert "witness" not in handover.call_args.kwargs, (
            "ADR-0053: the shared continuation's Reporter witness stands, and"
            " naming a party to the transfer would prove nothing about the"
            " CM-21-030 broadcast"
        )

    @pytest.mark.spec("CM-21-007")
    @pytest.mark.spec("CM-21-030")
    def test_the_reporter_witnesses_the_commit_the_case_actor_made(self):
        """The casting checked by its effect, not by its keywords.

        Carried over from the phase-level tests this scenario used to have:
        the commit is read on the dedicated case-actor container first, so a
        slow fan-out reads as a slow fan-out rather than as a transfer that
        never happened (EDF-06-002, #3602); and the ledger entry is then read
        on the Reporter's replica, the ADR-0053 criterion that a non-party
        learns of the transfer from the CM-21-030 broadcast alone.  Vendor1 or
        the Coordinator in that role would witness only their own round trip.
        """
        state = _four_party_state()
        state.keep(COORDINATOR_JOINED, str(state.case.id_))
        order: list[str] = []

        with (
            _no_banners(),
            patch.object(
                owner_decision_handover,
                "find_ownership_transfer_offer_for_actor",
                return_value="urn:test:ownership-offer",
            ),
            patch.object(
                owner_decision_handover,
                "wait_for_case_actor_ledger_event",
                side_effect=lambda **kw: order.append(
                    f"commit:{kw['semantic_type']}"
                ),
            ) as commit,
            patch.object(
                owner_decision_handover,
                "wait_for_case_attributed_to",
                side_effect=lambda **kw: order.append("attributed_to"),
            ),
            patch.object(
                owner_decision_handover,
                "wait_for_semantic_type_in_ledger",
                side_effect=lambda **kw: order.append("witness"),
            ) as witness,
            patch.object(
                owner_decision_handover, "as_VulnerabilityCase"
            ) as wire_case,
            patch.object(ActorSession, "offer_case_ownership_transfer"),
            patch.object(ActorSession, "accept_case_ownership_transfer"),
        ):
            wire_case.model_validate.return_value = mock_case(state.case.id_)
            demo.vendor1_hands_the_case_to_the_coordinator(state)

        assert order == [
            "commit:update_case_owner",
            "attributed_to",
            "attributed_to",
            "witness",
        ], order
        assert commit.call_args.kwargs["client"] is state.case_actor_client, (
            "CM-21-007: the commit is the CASE_MANAGER's own, read on the"
            " dedicated case-actor container (DEMOMA-06-005)"
        )
        assert witness.call_args.kwargs["client"] is state.client(REPORTER), (
            "ADR-0053: the witness is the Reporter, neither the old nor the"
            " new owner"
        )
        assert (
            witness.call_args.kwargs["semantic_type"]
            == "accept_case_ownership_transfer"
        )


@pytest.mark.spec("DEMOMA-11-003")
class TestTheCoordinatorInvitesTheSecondVendor:
    """The Coordinator, the owner since the handoff, invites Vendor2."""

    def test_the_invite_names_the_new_owner_the_invitee_and_the_role(self):
        """The new owner invites, so the roster is read on its replica."""
        state = _four_party_state()

        with patch.object(demo, "the_new_owner_invites") as invite:
            demo.the_coordinator_invites_the_second_vendor(state)

        invite.assert_called_once()
        assert invite.call_args.args == (state,)
        assert invite.call_args.kwargs == {
            "new_owner": COORDINATOR_PART,
            "invitee": VENDOR2_PART,
            "role": CVDRole.VENDOR,
            "seated": (REPORTER, VENDOR, COORDINATOR, VENDOR2),
        }

    def test_the_invite_is_triggered_by_the_coordinator_not_vendor1(self):
        """The casting checked by its effect (DEMOMA-22-002).

        A trigger URL is built from the named actor's bare id against the
        client's base URL, so posting the new owner's invite trigger to
        Vendor1's container would 404 — which is the defect #2178 fixed in one
        scenario and not its sibling.
        """
        state = _four_party_state()
        state.keep(owner_decision_story.HANDED_OVER_CASE, str(state.case.id_))

        with (
            _no_banners(),
            patch.object(
                owner_decision_parts,
                "find_case_actor_participant_id",
                return_value="urn:test:case-actor-participant",
            ),
            patch.object(
                owner_decision_handover, "invitee_triages_after_joining"
            ),
            patch_chain_shared(
                coordinated_joining, "wait_for_case_on_container"
            ),
            patch.object(
                owner_decision_handover, "run_case_invite_chain"
            ) as chain,
        ):
            demo.the_coordinator_invites_the_second_vendor(state)

        inviter = chain.call_args.kwargs["inviter"]
        assert inviter.client is state.client(COORDINATOR), (
            "DEMOMA-11-003: the invite comes from the Coordinator, the Case"
            " Owner since the handoff"
        )
        assert inviter.client is not state.client(VENDOR)
        assert inviter.actor is state.actor(COORDINATOR).actor
        assert inviter.role is CVDRole.VENDOR
        assert chain.call_args.kwargs["invitee"] is state.actor(VENDOR2).actor
        assert chain.call_args.kwargs["expect_emitted_by"] is not None, (
            "PCR-08-008: the CaseActor emits the Invite, so Vendor2's Accept"
            " routes back to the CASE_MANAGER"
        )

    @pytest.mark.spec("DEMOCI-01-011")
    def test_an_uncommitted_handover_stops_the_story_before_the_invite(self):
        """Only the Case Owner may invite.

        The real shared continuation runs: it reads the prop the handover
        keeps, so a transfer the CASE_MANAGER never committed stops the story
        here instead of inviting into a case the Coordinator does not own.
        """
        state = _four_party_state()

        with (
            patch.object(
                owner_decision_handover, "run_case_invite_chain"
            ) as chain,
            patch.object(
                owner_decision_parts, "find_case_actor_participant_id"
            ),
            pytest.raises(DemoStoryError, match="handed over"),
        ):
            demo.the_coordinator_invites_the_second_vendor(state)

        chain.assert_not_called()


# ---------------------------------------------------------------------------
# The milestone, the note thread and the fix (DEMOMA-11-013, DEMOMA-16-001)
# ---------------------------------------------------------------------------


@pytest.mark.spec("DEMOMA-11-013")
class TestTheCaseIsActive:
    """M1 names this scenario's own roster and the embargo that survived."""

    def test_the_milestone_expects_five_participants_and_an_active_embargo(
        self,
    ):
        """The embargo established before the transfer still covers everyone.

        The reads are the family's; the numbering and the expected roster are
        this scenario's, so the label is what it decides.
        """
        state = _four_party_state()

        with patch.object(
            demo, "required_participants_are_present"
        ) as milestone:
            demo.the_case_is_active(state)

        assert milestone.call_args.args == (state,)
        check = milestone.call_args.kwargs["check"]
        assert check.startswith("M1:")
        assert "≥5" in check, (
            "DEMOMA-11-013: Vendor2 joined after the transfer, so the roster"
            f" the milestone names is five strong; got {check!r}"
        )
        assert "EM.ACTIVE" in check


@pytest.mark.spec("DEMOCI-11-017")
class TestTheFourExchangeNotes:
    """The Coordinator and Vendor2 answer the thread the opening posted."""

    def _exchange(self, state):
        """Run the fragment with the note posting stubbed out."""
        with patch.object(vendor_continuations, "add_note_thread") as thread:
            demo.the_four_exchange_notes(state)
        return thread

    def test_the_two_updates_reply_to_the_answer_the_opening_kept(self):
        """One thread, not a second one: the joiners reply to the Vendor.

        The question and Vendor1's answer are the family's shared opening, so
        a joiner that opened a thread of its own would leave this scenario's
        recording with a note structure none of its siblings has
        (``VENDORS_ANSWER``).
        """
        state = _four_party_state()
        answer = make(as_Note, content="Vendor1's workaround answer")
        state.keep(VENDORS_ANSWER, answer)

        thread = self._exchange(state)

        watching_client, case, posts = thread.call_args.args
        assert watching_client is state.client(VENDOR), (
            "the thread is watched on Vendor1's replica, which every scenario"
            " of the family watches"
        )
        assert case is state.case
        assert thread.call_args.kwargs["in_reply_to"] is answer, (
            "DEMOCI-11-017: the joiners' notes reply to the answer the shared"
            " opening posted, so the thread stays one thread"
        )
        assert [post.poster.client for post in posts] == [
            state.client(COORDINATOR),
            state.client(VENDOR2),
        ], "each joiner posts from its own container"
        assert [post.name for post in posts] == [
            f"{COORDINATOR_LABEL} Update",
            f"{VENDOR2_LABEL} Status Update",
        ]
        # The Coordinator speaks as the new Case Owner, which is what
        # distinguishes this thread from ``rvcv-extension``'s (DEMOMA-17-002).
        assert "new case owner" in posts[0].content.lower()

    @pytest.mark.spec("DEMOCI-01-011")
    def test_a_thread_whose_answer_never_landed_posts_nothing(self):
        """A missing prop stops the story rather than posting unthreaded.

        The shared helper reads ``VENDORS_ANSWER`` before it posts, so this
        scenario cannot leave a note the thread assertions do not describe.
        """
        state = _four_party_state()

        with pytest.raises(DemoStoryError, match="workaround answer"):
            self._exchange(state)


class TestBothVendorsFixTheVul:
    """Both vendors hold ``CVDRole.VENDOR``, so both stop at VFd."""

    @pytest.mark.spec("CSB-15-002")
    def test_the_fix_runs_the_shared_step_under_two_unnumbered_milestones(
        self,
    ):
        """This scenario numbers neither milestone; the labels say so.

        The pair says two things: the fix reached the replicas, and neither
        Vendor went on to deploy.  Both labels name both vendors, which is
        what the shared step reads (#5602).
        """
        state = _four_party_state()

        with patch.object(
            demo, "both_vendors_report_the_fix_ready"
        ) as fix_ready:
            demo.both_vendors_fix_the_vul(state)

        assert fix_ready.call_args.args == (state,)
        kwargs = fix_ready.call_args.kwargs
        assert set(kwargs) == {"reached", "stopped"}, kwargs
        assert "fix ready" in kwargs["reached"], kwargs["reached"]
        # The label names each vendor's own replica, not every
        # vendor's on every replica: each vendor's VF is read on its own
        # replica and the Reporter's, never cross-read (#5602).
        assert "each vendor's own replica" in kwargs["reached"], kwargs[
            "reached"
        ]
        assert "both vendors stopped at VFd" in kwargs["stopped"], kwargs[
            "stopped"
        ]
        assert "no fix-deployed transition" in kwargs["stopped"], kwargs[
            "stopped"
        ]


# ---------------------------------------------------------------------------
# Publication and closure (DEMOMA-11-006, DEMOMA-11-018, DEMOMA-07-003)
# ---------------------------------------------------------------------------


@pytest.mark.spec("DEMOMA-11-006")
@pytest.mark.spec("DEMOMA-11-018")
class TestEveryonePublishes:
    """The Coordinator, the Case Owner since the handoff, publishes last."""

    def test_the_order_is_vendor1_vendor2_reporter_then_the_coordinator(self):
        """DEMOMA-07-003(4): the Case Owner's publication ends the embargo.

        The realistic CVD order, and the one this scenario's recording holds:
        the vendors publish their advisories, the Reporter its own writeup,
        and the Coordinator last, because it is the owner whose
        ``notify-published`` triggers the embargo teardown.  Carried over from
        the phase-level order test, now read through the devlogs names the
        invariant harness loads.
        """
        state = _four_party_state()
        order: list[str] = []

        def name_of(client: object) -> str:
            return devlogs_name_of(state, client, _DEVLOGS)

        with (
            _no_banners(),
            patch.object(
                vendor_continuations,
                "wait_for_case_em_terminated",
                side_effect=lambda client, case_id: order.append(
                    f"em_exited:{name_of(client)}"
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
                    f"published:{name_of(session.client)}"
                ),
            ),
        ):
            demo.everyone_publishes(state)

        assert order == [
            "published:vendor",
            "published:vendor2",
            "published:reporter",
            "published:coordinator",
            # The owner's own replica reads the teardown its trigger caused.
            "em_exited:coordinator",
            # Then every replica, because the owner published last: no other
            # participant's step waited on EM.EXITED on the way here.
            "em_exited:coordinator",
            "em_exited:vendor",
            "em_exited:vendor2",
            "em_exited:reporter",
        ], order

    def test_the_final_check_reads_em_exited_on_all_four_replicas(self):
        """Every participant leaves the embargo, not only the Reporter.

        The three sibling scenarios publish owner-first and read the
        termination on the Reporter's replica alone; here the owner publishes
        last, so the final milestone names all four (``em_watchers``).
        """
        state = _four_party_state()

        with (
            _no_banners(),
            patch.object(demo, "reports_published"),
            patch.object(demo, "the_embargo_ends_for"),
            patch.object(
                demo, "the_disclosure_reached_every_replica"
            ) as final,
        ):
            demo.everyone_publishes(state)

        assert final.call_args.kwargs["em_watchers"] == (
            COORDINATOR,
            VENDOR,
            VENDOR2,
            REPORTER,
        )

    def test_the_embargo_teardown_is_awaited_on_the_owners_replica(self):
        """The owner is the Coordinator, so the watcher is its container."""
        state = _four_party_state()

        with (
            _no_banners(),
            patch.object(demo, "reports_published"),
            patch.object(demo, "the_embargo_ends_for") as teardown,
            patch.object(demo, "the_disclosure_reached_every_replica"),
        ):
            demo.everyone_publishes(state)

        assert teardown.call_args.kwargs["watcher"] == COORDINATOR
        assert "CASE_OWNER" in teardown.call_args.kwargs["check"]


@pytest.mark.spec("CM-23-015")
class TestEveryoneCloses:
    """Vendor1, Vendor2 and the Reporter leave; the Coordinator leaves last."""

    def test_the_coordinator_closes_last_against_the_case_actors_store(self):
        """The owner's ``Leave`` is gated on the CASE_MANAGER's store.

        The handoff moves CASE_OWNER, not CASE_MANAGER: that store stays on
        the dedicated case-actor container (DEMOMA-06-005), so the authority
        client must be that one and not Vendor1's or the Coordinator's own.
        """
        state = _four_party_state()

        with patch.object(
            coordinated_continuations, "close_case_owner_last"
        ) as closure:
            demo.everyone_closes(state)

        kwargs = closure.call_args.kwargs
        assert kwargs["milestone"] is None, (
            "this scenario numbers no closure milestone"
        )
        assert kwargs["authority_client"] is state.case_actor_client
        assert [leaver.client for leaver in kwargs["others"]] == [
            state.client(VENDOR),
            state.client(VENDOR2),
            state.client(REPORTER),
        ]
        assert kwargs["owner"].client is state.client(COORDINATOR)
        assert kwargs["owner"].actor is state.actor(COORDINATOR).actor


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


#: One devlogs slug per cast member, deliberately unlike the directory names.
_DUMP_SLUGS = {
    REPORTER: "reporter-9f3a",
    VENDOR: "vendor-2b71",
    COORDINATOR: "coordinator-4c05",
    VENDOR2: "vendor2-8ade",
}


class TestRvcvHandoffLedgerDump:
    """Each replica is dumped under this scenario's own name for it."""

    def _state_for_dump(self, case, *, seats=_CAST):
        """A story state whose clients are dump-ready, on *case*.

        Built rather than adapted: an ``ActorSession`` is frozen, so a bound
        client has to be the one the session is made with.  *seats* is which
        cast members the run got as far as seating.
        """
        state = StoryState(
            cast={
                name: ActorSession(
                    client=_bound_client(_DUMP_SLUGS[name]),
                    actor=mock_actor(f"urn:test:{name}"),
                )
                for name in seats
            },
            case_actor_client=_bound_client("case-actor"),
            harness=MagicMock(demo_name="rvcv-handoff"),
            dump=lambda _state: None,
            unseated={
                name: UnseatedContainer(
                    label=name, client=_bound_client(_DUMP_SLUGS[name])
                )
                for name in _CAST
                if name not in seats
            },
        )
        state.open_case(case=case, report=MagicMock(), offer=MagicMock())
        return state

    def test_the_dump_writes_one_file_per_actor_under_the_demo_name(
        self, tmp_path, monkeypatch
    ):
        """Four devlogs names, each keyed on its client's own actor id."""
        case = make(
            as_VulnerabilityCase,
            attributed_to=CASE_OWNER_ID,
            id_="https://example.org/cases/rvcv-test-case",
        )
        monkeypatch.setenv("DEVLOGS_DIR", str(tmp_path))

        dump_vendor_coordinator_ledgers(self._state_for_dump(case))

        case_slug = "https_example.org_cases_rvcv-test-case"
        for devlogs_name in ("reporter", "vendor", "coordinator", "vendor2"):
            assert (
                tmp_path
                / "rvcv-handoff"
                / devlogs_name
                / f"{case_slug}-case-ledger.jsonl"
            ).exists(), devlogs_name

        # The route key selects the store (ADR-0073), so it must be the
        # client's own actor id — not the seed name the directory is named
        # after.
        manifest = json.loads(
            (tmp_path / "rvcv-handoff" / "dump-manifest.json").read_text()
        )
        keys = {r["actorName"]: r["routeKey"] for r in manifest["actors"]}
        assert keys == {
            "reporter": "reporter-9f3a",
            "vendor": "vendor-2b71",
            "coordinator": "coordinator-4c05",
            "vendor2": "vendor2-8ade",
            "case-actor": "case-actor",
        }

    @pytest.mark.spec("DEMOMA-06-005")
    @pytest.mark.spec("DEMOMA-06-009")
    def test_the_canonical_ledger_is_read_on_the_dedicated_container(
        self, tmp_path, monkeypatch
    ):
        """The CaseActor is not hosted on Vendor1's container.

        Vendor1's replica is not the canonical ledger, and it is still the
        authority for this family's replication checks — so a dump that read
        the CaseActor's log there would export a replica as canonical.
        """
        case = make(
            as_VulnerabilityCase,
            attributed_to=CASE_OWNER_ID,
            id_="https://example.org/cases/rvcv-with-ca",
            actor_participant_index={
                "https://example.org/actors/case-actor": (
                    "https://example.org/cases/rvcv-with-ca"
                    "/participants/case-actor"
                )
            },
        )
        monkeypatch.setenv("DEVLOGS_DIR", str(tmp_path))
        state = self._state_for_dump(case)

        dump_vendor_coordinator_ledgers(state)

        log_path = "/actors/case-actor/demo/cases/rvcv-with-ca/log"
        canonical = cast(MagicMock, state.case_actor_client.get_list)
        vendor_reads = cast(MagicMock, state.client(VENDOR).get_list)
        assert any(
            log_path in call.args[0] for call in canonical.call_args_list
        )
        assert not any(
            log_path in call.args[0] for call in vendor_reads.call_args_list
        )

    @pytest.mark.spec("DEMOMA-23-002")
    def test_an_actor_the_run_never_seated_is_left_out(
        self, tmp_path, monkeypatch
    ):
        """An unseated actor has no replica, so dumping it would 404.

        The dump runs on the way out whether or not an earlier step failed
        (DEMOMA-23-001), and a run that failed before the Coordinator and
        Vendor2 were seeded must still export the two replicas it has.
        """
        case = make(
            as_VulnerabilityCase,
            attributed_to=CASE_OWNER_ID,
            id_="https://example.org/cases/rvcv-early-failure",
        )
        monkeypatch.setenv("DEVLOGS_DIR", str(tmp_path))

        dump_vendor_coordinator_ledgers(
            self._state_for_dump(case, seats=(REPORTER, VENDOR))
        )

        manifest = json.loads(
            (tmp_path / "rvcv-handoff" / "dump-manifest.json").read_text()
        )
        assert [r["actorName"] for r in manifest["actors"]] == [
            "reporter",
            "vendor",
            "case-actor",
        ]
        assert not (tmp_path / "rvcv-handoff" / "coordinator").exists()


# ---------------------------------------------------------------------------
# The CLI sub-command and the registry entry (DEMOCI-11-011, DEMOMA-11-008)
# ---------------------------------------------------------------------------


@pytest.fixture
def help_text() -> str:
    """``vultron-demo rvcv-handoff --help`` as the sub-command renders it."""
    result = CliRunner().invoke(cli_main, ["rvcv-handoff", "--help"])
    assert result.exit_code == 0, result.output
    return result.output


@pytest.mark.spec("DEMOMA-11-008")
class TestRvcvHandoffCliCommand:
    """The generated sub-command offers every option this scenario needs."""

    @pytest.mark.parametrize(
        "option",
        [
            "--skip-health-check",
            "--reporter-url",
            "--vendor-url",
            "--coordinator-url",
            "--case-actor-url",
            "--vendor2-url",
            "--reporter-id",
            "--vendor-id",
            "--coordinator-id",
            "--vendor2-id",
        ],
    )
    def test_the_option_is_offered(self, help_text: str, option: str):
        """One URL and one id option per container, plus the health skip."""
        assert option in help_text, (
            "DEMOCI-11-011: the sub-command's options are generated from"
            " ROLES, so a missing one means ROLES and main() have drifted"
        )

    def test_case_actor_id_is_not_offered(self, help_text: str):
        """The CaseActor id override is gone (AC-1, DEMOMA-14-023 amended)."""
        assert "--case-actor-id" not in help_text

    def test_main_builds_one_client_per_container_and_runs_the_story(self):
        """``main()`` names its containers and passes their clients on."""
        clients = {
            name: MagicMock(name=name, base_url=f"http://{name}:7999/api/v2")
            for name in (
                "reporter",
                "vendor",
                "coordinator",
                "case-actor",
                "vendor2",
            )
        }

        with (
            patch.object(demo, "story_clients", return_value=clients) as built,
            patch.object(demo, "run_rvcv_handoff_demo") as run,
        ):
            demo.main(
                skip_health_check=True,
                coordinator_url="http://elsewhere:7999/api/v2",
                reporter_id="urn:test:reporter",
                vendor_id="urn:test:vendor",
                coordinator_id="urn:test:coordinator",
                vendor2_id="urn:test:vendor2",
            )

        members = built.call_args.args[1]
        assert [(m.role, m.label) for m in members] == [
            ("reporter", "Reporter"),
            ("vendor", "Vendor1"),
            ("coordinator", "Coordinator"),
            ("vendor2", "Vendor2"),
        ]
        assert [m.url for m in members] == [
            None,
            None,
            "http://elsewhere:7999/api/v2",
            None,
        ]
        assert built.call_args.kwargs["skip_health_check"] is True

        kwargs = run.call_args.kwargs
        assert kwargs["reporter_client"] is clients["reporter"]
        assert kwargs["vendor_client"] is clients["vendor"]
        assert kwargs["coordinator_client"] is clients["coordinator"]
        assert kwargs["case_actor_client"] is clients["case-actor"]
        assert kwargs["vendor2_client"] is clients["vendor2"]
        assert kwargs["coordinator_id"] == "urn:test:coordinator"
        assert "case_actor_id" not in kwargs


@pytest.fixture
def spec():
    """The one registry entry named ``rvcv-handoff``."""
    entries = [s for s in registered_scenarios() if s.name == "rvcv-handoff"]
    assert len(entries) == 1, entries
    return entries[0]


class TestRvcvHandoffRegistryEntry:
    """The registry is the sole declaration that ``rvcv-handoff`` exists."""

    def test_the_entry_describes_the_ownership_transfer_scenario(self, spec):
        """Every field is rendered into the generated scenario tables."""
        assert spec.label == "RVCV-handoff"
        assert (
            spec.participants == "Reporter + Vendor1 → Coordinator + Vendor2"
        )
        assert spec.feature == "Case-ownership transfer to coordinator"
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
        assert spec.demo_path == "vultron/demo/scenario/rvcv_handoff_demo.py"
        assert spec.harness_path == (
            "test/ci/invariants/test_rvcv_handoff_invariants.py"
        )


# ---------------------------------------------------------------------------
# The join the owner's decision presupposes (CM-21-021, DEMOCI-01-011)
# ---------------------------------------------------------------------------


@pytest.mark.spec("CM-21-021")
@pytest.mark.spec("DEMOMA-17-002")
class TestARosterThatNeverFillsSkipsTheTransfer:
    """The guarantee the hand-placed form got from nesting (#5536).

    Before composition the whole offer and accept sat inside the roster's own
    ``demo_gate``, so a roster that never filled skipped the transfer.  A flat
    story cannot nest, so the roster gate keeps :data:`COORDINATOR_JOINED` and
    the transfer reads it — and the runner stops the story at the unreadable
    prop.  Driven through the real ``run_story``, the real ``demo_gate`` and
    the real fragments, because every link of that chain is load-bearing and a
    test of any one of them alone is what let the guarantee go missing.
    """

    @pytest.fixture
    def marks(self, monkeypatch: MonkeyPatch):
        """Stand in for ``scenario_harness``, which needs a real case."""
        reset_demo_failures()
        harness = MagicMock()
        harness.demo_name = "rvcv-handoff"

        @contextlib.contextmanager
        def stub(_demo_name: str):
            yield harness

        monkeypatch.setattr(story_runner, "scenario_harness", stub)
        yield harness
        reset_demo_failures()

    @contextlib.contextmanager
    def _roster(self, *, fills: bool):
        """Run the join with its roster filling or timing out.

        The roster gate in ``coordinated_story.joining`` and the prop read in
        ``owner_decision_story`` are the subject, so both stay real.  Every
        poll *after* the transfer trigger is stubbed: left real they would
        each spend the whole ``OWNER_DECISION_TIMEOUT`` against a
        ``MagicMock`` store, which buys no assertion and puts the test over
        the unit tier's ceiling (``test/AGENTS.md`` § "Timeouts Are
        Two-Tier").
        """
        with (
            patch.object(coordinated_joining, "wait_for_case_on_container"),
            patch.object(
                coordinated_joining,
                "run_case_invite_chain",
                side_effect=lambda **kw: kw["then"] and kw["then"](),
            ),
            patch.object(
                coordinated_joining,
                "wait_for_case_participants",
                side_effect=None
                if fills
                else AssertionError("roster never filled"),
            ),
            patch.object(
                owner_decision_handover,
                "find_ownership_transfer_offer_for_actor",
                return_value="urn:test:offer",
            ),
            patch.object(
                owner_decision_handover, "wait_for_case_actor_ledger_event"
            ),
            patch.object(
                owner_decision_handover, "wait_for_case_attributed_to"
            ),
            patch.object(
                owner_decision_handover, "wait_for_semantic_type_in_ledger"
            ),
            patch.object(
                ActorSession, "offer_case_ownership_transfer", autospec=True
            ) as offer,
        ):
            yield offer

    def _play(self, state: StoryState) -> None:
        run_story(
            "rvcv-handoff",
            story(
                vendor_coordinator_story.the_vendor_invites_the_coordinator,
                demo.vendor1_hands_the_case_to_the_coordinator,
            ),
            lambda _harness: state,
        )

    def test_a_timed_out_roster_leaves_the_transfer_unoffered(self, marks):
        """The trigger never runs; the roster is the one failure."""
        state = _four_party_state()

        with self._roster(fills=False) as offer:
            self._play(state)

        offer.assert_not_called()
        with pytest.raises(
            DemoStoryError, match="no case the Coordinator joined"
        ):
            state.kept(COORDINATOR_JOINED)

    def test_a_filled_roster_lets_the_transfer_run(self, marks):
        """The counterpart, so the test above is not vacuous."""
        state = _four_party_state()

        with self._roster(fills=True) as offer:
            self._play(state)

        assert state.kept(COORDINATOR_JOINED) == str(state.case.id_)
        offer.assert_called_once()
        assert offer.call_args.args[0].client is state.client(VENDOR)


# ---------------------------------------------------------------------------
# The ownership transfer over the real protocol: the transferee's peers hold
# the committed entry without a trigger (CM-21-007, AC-5c of ISSUE-1976)
# ---------------------------------------------------------------------------

_OTC_VENDOR_BASE = "http://vendor-otc.test"
_OTC_COORDINATOR_BASE = "http://coordinator-otc.test"
_OTC_REPORTER_BASE = "http://reporter-otc.test"
_OTC_VENDOR_SLUG = "vendor-otc"
_OTC_COORDINATOR_SLUG = "coordinator-otc"
_OTC_REPORTER_SLUG = "reporter-otc"


def _otc_create_actor(client, base_api: str, slug: str, name: str) -> str:
    """POST an Organization actor; return its canonical URI."""
    actor_id = f"{base_api}/actors/{slug}"
    resp = client.post(
        "/api/v2/actors/",
        json={"type": "Organization", "name": name, "id": actor_id},
    )
    assert resp.status_code in (
        200,
        201,
    ), f"Actor creation failed ({resp.status_code}): {resp.text}"
    return actor_id


def _otc_post_inbox(client, actor_slug: str, activity) -> None:
    from test.support.received import delivered_body
    from test.support.signing import post_delivered

    # Stamped as the sender's adapter stamps a case activity (SYNC-18-001)
    # and signed by its author (SIG-01-001).
    post_delivered(
        client, f"/api/v2/actors/{actor_slug}/inbox/", delivered_body(activity)
    )


def _otc_make_offer(dl, proposal, case_manager_id: str) -> Any:
    """Run the CASE_MANAGER's received proposal use case on *dl*.

    The CASE_MANAGER ledgers the proposal and makes the Offer (ADR-0148);
    returns that Offer, the one the transferee answers.
    """
    from test.support.received import received_event
    from vultron.adapters.driven.sync_activity_adapter import (
        SyncActivityAdapter,
    )
    from vultron.adapters.driven.trigger_activity_adapter import (
        TriggerActivityAdapter,
    )
    from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
    from vultron.core.models.events.actor import (
        ProposeCaseOwnershipTransferReceivedEvent,
    )
    from vultron.core.models.use_case_result import HandlerDisposition
    from vultron.core.participants.ownership_offer import ownership_offer_id
    from vultron.core.use_cases.received.actor.ownership import (
        ProposeCaseOwnershipTransferReceivedUseCase,
    )

    event = received_event(proposal, receiving_actor_id=case_manager_id)
    assert isinstance(event, ProposeCaseOwnershipTransferReceivedEvent)
    result = run_in_act(
        ProposeCaseOwnershipTransferReceivedUseCase(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        )
    )
    assert result.disposition is HandlerDisposition.APPLIED, result
    # The proposal's and the Offer's fan-out are not this test's subject;
    # drop them so only the Accept's deliveries are observed.
    while dl.outbox_pop() is not None:
        pass
    offer = dl.read(
        ownership_offer_id(
            case_manager_id, event.case_id or "", proposal.id_, event.actor_id
        )
    )
    assert offer is not None
    return offer


@contextlib.contextmanager
def _otc_ownership_transferred(
    router: InProcessRouter,
) -> Iterator[IsolatedActorApp]:
    """Run the AC-5c ownership transfer and yield the Reporter's app.

    Three isolated actor apps wired through *router*: the Vendor (case owner),
    the Coordinator (CASE_MANAGER, which makes the Offer from the Vendor's
    proposal and receives the Accept) and the Reporter, the transferee.
    The case lives only on the Coordinator, so
    neither peer can anchor its chain: each Rejects every ledger entry it is
    sent, which is what drives the Reject/replay loop SYNC-15-003 bounds.
    Yields once the Accept's inbox POST — and every delivery it set off — has
    returned.
    """
    from vultron.adapters.driving.fastapi.outbox_handler import (
        configure_default_emitter,
        get_default_emitter,
    )
    from vultron.config import config_override
    from vultron.wire.as2.factories.case import (
        accept_case_ownership_transfer_activity,
        propose_case_ownership_transfer_activity,
    )
    from vultron.wire.as2.vocab.objects.case_participant import (
        as_CaseParticipant,
    )

    with config_override(
        VULTRON_SERVER__BASE_URL=f"{_OTC_COORDINATOR_BASE}/api/v2",
        VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL=f"{_OTC_COORDINATOR_BASE}/api/v2",
    ):
        # `actor_slug` decides which actor's store `iso.dl` is. These actors
        # are created under the module slugs below, and a store belongs to
        # exactly one actor (ADR-0073), so leaving the default `"primary"`
        # points `dl` at an empty database — the reporter's Announce assertion
        # then reads a store nothing was ever delivered to.
        vendor_iso = create_isolated_actor_app(
            base_url=_OTC_VENDOR_BASE,
            router=router,
            actor_slug=_OTC_VENDOR_SLUG,
        )
        coordinator_iso = create_isolated_actor_app(
            base_url=_OTC_COORDINATOR_BASE,
            router=router,
            actor_slug=_OTC_COORDINATOR_SLUG,
        )
        reporter_iso = create_isolated_actor_app(
            base_url=_OTC_REPORTER_BASE,
            router=router,
            actor_slug=_OTC_REPORTER_SLUG,
        )

        previous_emitter = get_default_emitter()
        configure_default_emitter(router)  # type: ignore[arg-type]

        try:
            with (
                vendor_iso.client as vendor_tc,
                coordinator_iso.client as coordinator_tc,
                reporter_iso.client as reporter_tc,
            ):
                coordinator_base_api = f"{_OTC_COORDINATOR_BASE}/api/v2"
                vendor_base_api = f"{_OTC_VENDOR_BASE}/api/v2"
                reporter_base_api = f"{_OTC_REPORTER_BASE}/api/v2"

                vendor_id = _otc_create_actor(
                    vendor_tc,
                    vendor_base_api,
                    _OTC_VENDOR_SLUG,
                    "Vendor OTC",
                )
                coordinator_id = _otc_create_actor(
                    coordinator_tc,
                    coordinator_base_api,
                    _OTC_COORDINATOR_SLUG,
                    "Coordinator OTC",
                )
                reporter_id = _otc_create_actor(
                    reporter_tc,
                    reporter_base_api,
                    _OTC_REPORTER_SLUG,
                    "Reporter OTC",
                )

                # Build a case on the Coordinator's DataLayer directly so
                # CommitCaseLedgerEntryNode can read participants and the
                # FanOutLogEntryNode knows to broadcast to Reporter.
                case = make(
                    as_VulnerabilityCase,
                    name="OTC Test Case",
                    attributed_to=vendor_id,
                    content="AC-5c integration test case",
                )
                case_id = case.id_

                vendor_p = make(
                    as_CaseParticipant,
                    attributed_to=vendor_id,
                    context=case_id,
                    case_roles=[CVDRole.CASE_OWNER],
                )
                coordinator_p = make(
                    as_CaseParticipant,
                    attributed_to=coordinator_id,
                    context=case_id,
                    case_roles=[CVDRole.CASE_MANAGER],
                )
                reporter_p = make(
                    as_CaseParticipant,
                    attributed_to=reporter_id,
                    context=case_id,
                    case_roles=[CVDRole.REPORTER],
                )
                case.actor_participant_index[vendor_id] = vendor_p.id_
                case.actor_participant_index[coordinator_id] = (
                    coordinator_p.id_
                )
                case.actor_participant_index[reporter_id] = reporter_p.id_
                case.case_participants.extend(
                    [vendor_p.id_, coordinator_p.id_, reporter_p.id_]
                )

                cdl = coordinator_iso.dl
                cdl.create(case)
                cdl.create(vendor_p)
                cdl.create(coordinator_p)
                cdl.create(reporter_p)
                # Coordinator's DL needs to know about the other actors
                # for outbox delivery routing.
                from vultron.wire.as2.vocab.base.objects.actors import (
                    as_Service,
                )

                cdl.create(make(as_Service, id_=vendor_id, name="Vendor OTC"))
                cdl.create(
                    make(as_Service, id_=reporter_id, name="Reporter OTC")
                )

                # The Vendor proposes the transfer to the Reporter; the
                # Coordinator, the CASE_MANAGER, makes and ledgers the Offer
                # (ADR-0148).  It runs in-process: the Offer's own delivery
                # is not this test's subject.
                case_wire = as_VulnerabilityCase.model_validate(
                    {
                        "attributed_to": CASE_OWNER_ID,
                        "id": case_id,
                        "name": case.name or "OTC Test Case",
                    }
                )
                proposal = propose_case_ownership_transfer_activity(
                    case_wire,
                    # Inline, as the inbox rehydrates it: the ledger
                    # commit refuses a bare-id target (CLP-07).
                    target=make(
                        as_Service, id_=reporter_id, name="Reporter OTC"
                    ),
                    actor=vendor_id,
                    to=[coordinator_id],
                )
                offer = _otc_make_offer(cdl, proposal, coordinator_id)

                # The Reporter accepts, at the Coordinator's inbox.  The
                # Coordinator IS the CaseActor so it processes the Accept,
                # updates attributed_to, commits the ledger entry, and fans
                # out Announce(CaseLedgerEntry) to all case participants.
                accept = accept_case_ownership_transfer_activity(
                    offer=offer,
                    actor=reporter_id,
                    to=[coordinator_id],
                )
                _otc_post_inbox(coordinator_tc, _OTC_COORDINATOR_SLUG, accept)

                yield reporter_iso
        finally:
            configure_default_emitter(previous_emitter)  # type: ignore[arg-type]
            vendor_iso.close()
            coordinator_iso.close()
            reporter_iso.close()


@pytest.mark.spec("CM-21-007")
class TestOwnershipTransferAnnounceReachesReporter:
    """AC-5c: the transfer's ledger entry reaches a peer with no trigger.

    The protocol property this scenario's handover rests on, driven for real
    rather than through the story: a participant holds the transfer's ledger
    entry only because the CASE_MANAGER committed it and fanned it out
    (ADR-0053).  Three actors:

    - Vendor  — case owner, proposes the ownership transfer
    - Coordinator — CaseActor, makes the Offer from the proposal and
                    receives the Accept, commits the ledger entry,
                    broadcasts Announce
    - Reporter  — the transferee; must receive the
                Announce(CaseLedgerEntry) without any manual trigger

    All three actors use isolated FastAPI apps wired via InProcessRouter.
    The test seeds the case and participants directly on the Coordinator's
    DataLayer, has the Coordinator make the Offer from the Vendor's
    proposal, then delivers the Reporter's Accept(Offer) to the
    Coordinator's inbox
    via HTTP POST.  The outbox drains automatically (TestClient processes
    BackgroundTasks synchronously), routing the Announce to Reporter's inbox.
    Reporter's DataLayer is then checked for an Announce whose object is a
    CaseLedgerEntry with semantic_type == "accept_case_ownership_transfer".
    """

    def test_reporter_receives_announce_ledger_entry(self):
        with _otc_ownership_transferred(InProcessRouter()) as reporter_iso:
            # The TestClient processes BackgroundTasks synchronously;
            # the outbox drains during the POST and InProcessRouter
            # delivers Announce(CaseLedgerEntry) to Reporter's inbox.
            # A received Announce is held only as intake archived it
            # (DL-06-006).
            announce_values = received_of_type(reporter_iso.dl, "Announce")

            def _is_ot_announce(a: object) -> bool:
                obj = (
                    a.get("object_")
                    if isinstance(a, dict)
                    else getattr(a, "object_", None)
                )
                if obj is None:
                    return False
                semantic_type = (
                    obj.get("semantic_type")
                    if isinstance(obj, dict)
                    else getattr(obj, "semantic_type", None)
                )
                return semantic_type == "accept_case_ownership_transfer"

            ot_announces = [a for a in announce_values if _is_ot_announce(a)]
            assert len(ot_announces) >= 1, (
                "Reporter's DataLayer must contain at least one "
                "Announce(CaseLedgerEntry[semantic_type="
                "accept_case_ownership_transfer]) "
                "after ownership transfer — no manual trigger (AC-5c). "
                f"Got announces: {announce_values!r}"
            )


class _CountingRouter(InProcessRouter):
    """A router that counts deliveries and drops every one past *cap*.

    The cap turns a Reject/replay storm into a fast, readable failure instead
    of a test that never returns.
    """

    def __init__(self, cap: int) -> None:
        super().__init__()
        self.cap = cap
        self.attempted = 0

    async def emit(
        self,
        activity_id: str,
        json_body: str,
        recipients: list[str],
        inboxes: Mapping[str, str] | None = None,
    ) -> None:
        self.attempted += len(recipients)
        if self.attempted > self.cap:
            return
        await super().emit(activity_id, json_body, recipients, inboxes)


@pytest.mark.spec("SYNC-15-013")
@pytest.mark.spec("SYNC-15-014")
class TestUnanchoredPeerRejectStormIsBounded:
    """A peer that can never anchor its chain keeps no replay loop alive.

    In the AC-5c setup neither peer holds the case, and each refuses the case
    announce because it has no CASE_MANAGER on record (PCR-03-004), so every
    replayed entry comes back as a genesis Reject.  With a fixed cooldown the
    loop stopped only when one round trip beat it: on a loaded host it ran
    until the test timed out (#4882).  The fake act clock here advances on
    every act it opens, so each round looks slower than any fixed cooldown:
    the replay limits read the act's instant, never the clock (ADR-0176).
    """

    #: A healthy transfer makes a few dozen deliveries; the storm made
    #: over a thousand in two minutes.
    _DELIVERY_CAP = 300

    def test_reject_storm_terminates_under_slow_rounds(self):
        from vultron.core.models._helpers import now_utc as real_now

        start = real_now()
        reads = 0

        def slow_clock():
            nonlocal reads
            reads += 1
            return start + timedelta(seconds=3 * reads)

        router = _CountingRouter(cap=self._DELIVERY_CAP)
        with patch("vultron.adapters.driven.clock.now_utc", slow_clock):
            with _otc_ownership_transferred(router):
                pass

        assert router.attempted <= self._DELIVERY_CAP, (
            f"{router.attempted} deliveries for one ownership transfer: the"
            " Reject/replay loop to the unanchored peers did not settle"
            " (SYNC-15-003)"
        )
