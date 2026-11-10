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

"""Unit tests for the RVCV-extension four-actor CVD demo (DEMOMA-10, #5536).

``rvcv-extension`` is written as composition (ADR-0098,
:mod:`vultron.demo.helpers.story`): its opening is the shared
:data:`~vultron.demo.helpers.vendor_coordinator_story\
.THE_VENDOR_INVITES_A_COORDINATOR` prefix, which itself continues the
vendor-first family's ``THE_VENDOR_ANSWERS_THE_REPORTER``, and its own story
is the continuation after Vendor1, the Case Owner, decides to **keep** the
case (DEMOMA-10-010).  The checks that used to sit on its ``_phase_*``
functions therefore sit here on three things:

* the **story's shape** — the path read off its choices, the identity of the
  stretch it shares with ``rvcv-handoff``, the nesting back to the
  vendor-first opening, and the order of its own fragments;
* each of its **own fragments**, driven against a
  :func:`~test.demo._helpers.story_state` stand-in cast, so a test observes
  what the fragment calls;
* the **surfaces around the story** — the CLI option set, the registry entry,
  the dedicated case-actor container and the devlogs names the invariant
  harness reads.

What the shared opening does is not re-tested here:
``test/demo/vendor_story/`` owns the vendor-first family's stretch,
``test_vendor_coordinator_story`` owns the pair's prefix and the
continuations both scenarios tell, ``test/demo/coordinated_story/`` owns the
container plumbing and the join chain, ``test_invite_chain`` owns what a
failed invite trigger or an undelivered Invite skips, and
``test/demo/owner_decision_story/`` owns the ``owner-keep-case``
continuations.
``TestSeedContainersRvcv`` and ``TestFindCaseInviteForActor`` stay because
they are about shared helpers — the four-container seeding and the Invite
lookup — rather than this scenario's own steps, and each imports the helper
from its real home rather than through a re-export.

Every test patches the collaborators out, so no HTTP happens outside
``TestSeedContainersRvcv``; ``demo_gate`` / ``demo_check`` / ``demo_step``
stay real wherever the test is about control flow and are stubbed to
``nullcontext`` only where it is about call shape
(``test_demo_context_managers.py`` owns their behaviour).
"""

import contextlib
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from fastapi.testclient import TestClient

import vultron.demo.scenario.rvcv_extension_demo as demo
from test.demo._helpers import (
    make_client,
    make_testclient_call,
    mock_actor,
    mock_case,
    mock_client,
    no_demo_banners,
    patch_chain_shared,
    story_state,
    stub_closure_gate,
)
from vultron.core.states.cs import CS_vf
from vultron.core.states.rm import RM
from vultron.demo.actor_session import ActorSession
from vultron.demo.cli import main as cli_main
from vultron.demo.helpers import (
    coordinated_story,
    owner_decision_story,
    seeding,
    story_cast,
    vendor_coordinator_story,
    vendor_story,
)
from vultron.demo.helpers.coordinated_story import (
    COORDINATOR,
    COORDINATOR_LABEL,
    REPORTER,
    REPORTER_LABEL,
    continuations as coordinated_continuations,
    joining as coordinated_joining,
)
from vultron.demo.helpers.owner_decision_story import (
    Part,
    keep as owner_decision_keep,
    parts as owner_decision_parts,
)
from vultron.demo.helpers.polling import find_case_invite_for_actor
from vultron.demo.helpers.seeding import reset as seeding_reset
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
    DEVLOG_REPLICAS,
    THE_VENDOR_INVITES_A_COORDINATOR,
    dump_vendor_coordinator_ledgers,
)
from vultron.demo.helpers.vendor_story import (
    THE_VENDOR_ANSWERS_THE_REPORTER,
    THE_VENDORS_CASE,
    VENDOR,
    VENDOR2,
    VENDOR2_LABEL,
    VENDOR_LABEL,
    VENDORS_ANSWER,
    cast as vendor_cast,
    continuations as vendor_continuations,
)
from vultron.demo.scenario.registry import registered_scenarios
from vultron.demo.utils import reset_demo_failures
from vultron.demo.utils.failures import _demo_failures
from vultron.enums.roles import CVDRole
from vultron.errors import DemoStoryError
from vultron.wire.as2.vocab.base.objects.object_types import as_Note

#: Clear the process-global failure accumulator around every test.
pytestmark = pytest.mark.usefixtures("fresh_demo_failures")

#: The scenario's four cast names, in ``ROLES`` order.
_CAST = (REPORTER, VENDOR, COORDINATOR, VENDOR2)

#: How many items of ``STORY`` are the shared opening.
_PREFIX_LEN = len(THE_VENDOR_INVITES_A_COORDINATOR.items)


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


def _four_party_state(joined: bool = True):
    """A story state seating all four, on an open case.

    Both props the shared opening's gates keep are kept here: the roster
    (``THE_VENDORS_CASE``), which the M1 milestone reads, and the
    Coordinator's join, which the ``keep`` continuation reads because only a
    participant may suggest anyone (DEMOMA-10-004, #5536).
    """
    state = story_state(*_CAST, case=mock_case())
    state.keep(THE_VENDORS_CASE, str(state.case.id_))
    if joined:
        state.keep(COORDINATOR_JOINED, str(state.case.id_))
    return state


def _cast_name_of(state: StoryState, client: object) -> str:
    """The cast name the seated *client* belongs to, for an order assertion."""
    for name in state.cast:
        if state.client(name) is client:
            return name
    return "unknown"


# ---------------------------------------------------------------------------
# The story's shape (DEMOCI-11-019, DEMOCI-11-024, DEMOMA-10-010)
# ---------------------------------------------------------------------------


class TestRvcvExtensionStoryShape:
    """``STORY`` places the scenario on the tree, and nothing else does."""

    #: The path ``rvcv-extension`` declared as ``@scenario(path=...)`` before
    #: it was composed.  The composed form must walk exactly the same tree
    #: ending, or the recordings, the generated index and the invariant
    #: harness all move with it.
    DECLARED_PATH = (
        ("reporter-whom-to-tell", "vendor"),
        ("vendor-after-answer", "invite-coordinator"),
        ("owner-keep-case", "keep"),
    )

    def test_the_story_walks_the_path_the_scenario_used_to_declare(self):
        """The path is read off the choices, not typed beside them."""
        assert demo.STORY.path == self.DECLARED_PATH

    def test_the_opening_is_the_shared_prefix_itself(self):
        """``rvcv-extension`` starts with the pair's prefix object.

        Identity of the shared stretch, not merely a matching sequence: the
        two scenarios' recordings must be byte-identical up to the
        ``owner-keep-case`` branch point (DEMOCI-11-018), which only holds
        while the opening is one copy of the code.  Comparing against
        ``THE_VENDOR_INVITES_A_COORDINATOR.items`` is what stops a sibling
        slipping a step in before the branch point.
        """
        assert (
            demo.STORY.items[:_PREFIX_LEN]
            == THE_VENDOR_INVITES_A_COORDINATOR.items
        )
        # Identity only: ``Choose`` is a frozen dataclass, so a hand-copied
        # duplicate compares equal and an equality arm would make this loop a
        # second spelling of the tuple comparison above.
        for mine, theirs in zip(
            demo.STORY.items[:_PREFIX_LEN],
            THE_VENDOR_INVITES_A_COORDINATOR.items,
            strict=True,
        ):
            assert mine is theirs

    @pytest.mark.spec("DEMOMA-10-010")
    def test_the_prefix_itself_starts_with_the_vendor_familys_opening(self):
        """The nesting DEMOMA-10-010 names, asserted end to end.

        Every vendor-first scenario shares the report submission, Vendor1's
        triage and the Reporter's question, so the chain of prefixes has to
        reach from this scenario's story back to
        ``THE_VENDOR_ANSWERS_THE_REPORTER`` — and the pair's own prefix must
        *nest* that opening rather than restate its fragments, or the two
        copies could drift (DEMOMA-17-003).
        """
        shared = len(THE_VENDOR_ANSWERS_THE_REPORTER.items)

        assert (
            THE_VENDOR_INVITES_A_COORDINATOR.items[:shared]
            == THE_VENDOR_ANSWERS_THE_REPORTER.items
        )
        assert (
            demo.STORY.items[:shared] == THE_VENDOR_ANSWERS_THE_REPORTER.items
        )
        for mine, theirs in zip(
            demo.STORY.items[:shared],
            THE_VENDOR_ANSWERS_THE_REPORTER.items,
            strict=True,
        ):
            assert mine is theirs

    def test_the_siblings_part_at_the_owners_decision(self):
        """The pair's one shared branch point, decided the other way.

        The choice is found by branch point rather than by position: this
        scenario reports the mark after two reads that write nothing (the M1
        milestone and the drain), so the item index differs from the
        handoff's while the decision and its decider do not.
        """
        import vultron.demo.scenario.rvcv_handoff_demo as handoff

        def decision(plot) -> Choose:
            marks = [
                item
                for item in plot.items
                if isinstance(item, Choose)
                and item.branch_point == "owner-keep-case"
            ]
            assert len(marks) == 1, marks
            return marks[0]

        branch = decision(demo.STORY)
        assert branch == Choose(
            branch_point="owner-keep-case",
            choice="keep",
            by=VENDOR,
        )
        assert branch != decision(handoff.STORY), (
            "rvcv-extension and rvcv-handoff must take different choices at"
            " owner-keep-case, or they are the same scenario"
        )
        # Neither scenario's shared opening decides it: the prefix stops
        # where the decision falls (DEMOMA-10-010).
        assert not [
            item
            for item in THE_VENDOR_INVITES_A_COORDINATOR.items
            if isinstance(item, Choose)
            and item.branch_point == "owner-keep-case"
        ]

    def test_the_prefix_ends_with_the_coordinator_joining(self):
        """Vendor1 decides only once the Coordinator is a participant.

        Either continuation presupposes it — the extension has the
        Coordinator suggest Vendor2, the handoff transfers the case to it —
        so the join is the last act of the shared opening (DEMOMA-10-004,
        CM-21-021).
        """
        assert (
            THE_VENDOR_INVITES_A_COORDINATOR.items[-1]
            is vendor_coordinator_story.the_vendor_invites_the_coordinator
        )

    def test_the_continuation_runs_in_the_declared_order(self):
        """One assertion for the whole continuation, so a reordering shows.

        The order is load-bearing: the M1 milestone and the drain both read
        state the suggestion then changes, and the suggestion is what brings
        Vendor2 in, so every later fragment depends on it.  Both of those
        reads run before the mark, which is what lets the mark fall between
        the Coordinator's join and the suggestion it then makes.
        """
        assert demo.STORY.items[_PREFIX_LEN:] == (
            demo.the_case_is_active,
            demo.replicas_drain_before_the_second_vendor,
            choose("owner-keep-case", "keep", by=VENDOR),
            demo.the_coordinator_suggests_the_second_vendor,
            vendor_coordinator_story.every_replica_converges,
            demo.the_four_exchange_notes,
            demo.both_vendors_fix_the_vul,
            demo.everyone_publishes,
            demo.everyone_closes,
        )

    def test_the_three_seated_actors_take_the_family_cast_names(self):
        """One copy of the vendor-first opening serves all four siblings.

        The Reporter, Vendor1 and Vendor2 are seated under the family's own
        names, and the Coordinator under the one both halves of the tree read
        it by, so every shared fragment reaches them without this scenario
        naming its cast twice.
        """
        assert Part(VENDOR, VENDOR_LABEL) == demo.VENDOR_PART
        assert Part(VENDOR2, VENDOR2_LABEL) == demo.VENDOR2_PART
        assert Part(COORDINATOR, COORDINATOR_LABEL) == demo.COORDINATOR_PART
        # The devlogs and the CLI keep the scenario's own names, which here
        # are the cast names themselves (DEMOMA-19-018).
        assert [role.name for role in demo.ROLES] == [
            "reporter",
            "vendor",
            "coordinator",
            "vendor2",
            "case-actor",
        ]
        assert DEVLOG_REPLICAS == (REPORTER, VENDOR, COORDINATOR, VENDOR2)


# ---------------------------------------------------------------------------
# M1: the Coordinator has joined and the embargo is still on (DEMOMA-10-006)
# ---------------------------------------------------------------------------


class TestTheCaseIsActive:
    """The milestone is re-run once the Coordinator has joined."""

    def test_the_milestone_is_this_scenarios_m1_label(self):
        """The reads are the family's; only the label is the scenario's."""
        state = _four_party_state()

        with patch.object(
            demo, "required_participants_are_present"
        ) as milestone:
            demo.the_case_is_active(state)

        assert milestone.call_args.args == (state,)
        check = milestone.call_args.kwargs["check"]
        assert check.startswith("M1:"), check
        assert "EM.ACTIVE" in check, check

    def test_the_milestone_reads_vendor1s_replica_and_the_reporters(self):
        """M1 is read from the Case Owner's replica, not the canonical case.

        Vendor1 holds the case from its own triage onward, so the real shared
        helper runs here to show whose replicas this scenario's M1 names.
        """
        state = _four_party_state()

        with (
            patch.object(vendor_continuations, "verify_case_active") as verify,
            _no_banners(),
        ):
            demo.the_case_is_active(state)

        kwargs = verify.call_args.kwargs
        assert kwargs["receiver_client"] is state.client(VENDOR)
        assert kwargs["reporter_client"] is state.client(REPORTER)
        assert kwargs["case_id"] == state.case.id_
        assert kwargs["receiver_actor_id"] == state.actor_id(VENDOR)
        assert kwargs["reporter_actor_id"] == state.actor_id(REPORTER)


# ---------------------------------------------------------------------------
# The replica drain this scenario alone tells (DEMOMA-23-005, #3906)
# ---------------------------------------------------------------------------


class TestReplicasDrainBeforeTheSecondVendor:
    """The drain goes through the one shared coverage helper.

    DEMOMA-23-005: the read-authority-tail-then-poll-each-replica loop lives
    in ``vultron/demo/helpers/sync/`` and nowhere else (#3906).
    ``rvcv-handoff`` never drains here, so the fragment itself belongs to
    this scenario alone.
    """

    def test_the_drain_names_vendor1_as_authority_and_the_joined_replicas(
        self,
    ):
        """Only the Reporter and the Coordinator hold a replica so far.

        Vendor2 has not been suggested yet, so naming it here would wait for
        a replica no act has created.
        """
        state = _four_party_state()

        with patch.object(
            demo, "wait_for_replica_ledger_coverage"
        ) as coverage:
            demo.replicas_drain_before_the_second_vendor(state)

        coverage.assert_called_once()
        kwargs = coverage.call_args.kwargs
        assert kwargs["auth_client"] is state.client(VENDOR)
        assert kwargs["replicas"] == [
            (state.client(REPORTER), REPORTER_LABEL),
            (state.client(COORDINATOR), COORDINATOR_LABEL),
        ]
        assert kwargs["case_id"] == state.case.id_
        assert kwargs["phase_label"] == "opening drain before Vendor2 joins"
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
        import vultron.demo.helpers.sync.ledger as sync_ledger

        state = _four_party_state()
        state.client(VENDOR).base_url = "http://vendor.test/api/v2"

        with (
            patch.object(
                sync_ledger, "_get_log_entries_for_case", return_value=[]
            ),
            patch.object(
                sync_ledger, "wait_for_contiguous_ledger_coverage"
            ) as per_replica,
        ):
            demo.replicas_drain_before_the_second_vendor(state)

        per_replica.assert_not_called()
        (failure,) = _demo_failures
        assert failure.startswith("GATE FAILED")
        assert "http://vendor.test/api/v2" in failure
        assert "opening drain before Vendor2 joins" in failure
        assert "holds no CaseLedgerEntry" in failure


# ---------------------------------------------------------------------------
# The Coordinator suggests Vendor2; Vendor1, keeping the case, approves
# (DEMOMA-10-004, DEMOMA-10-005, DEMOMA-10-014, ADR-0026)
# ---------------------------------------------------------------------------


@pytest.mark.spec("DEMOMA-10-004")
@pytest.mark.spec("DEMOMA-10-005")
@pytest.mark.spec("DEMOMA-10-014")
class TestTheCoordinatorSuggestsTheSecondVendor:
    """The ADR-0026 suggest-actor flow, with Vendor1 as approving owner."""

    def test_the_fragment_names_the_parts_and_the_vendor_role(self):
        """The shared continuation takes this scenario's cast as data.

        The ``keep`` continuation is written once for both halves of the
        tree, so it is the scenario that names Vendor1 as the owner, the
        Coordinator as the suggester and Vendor2 as the newcomer
        (DEMOMA-17-001).
        """
        state = _four_party_state()

        with patch.object(
            demo, "the_owner_approves_a_suggested_actor"
        ) as keep:
            demo.the_coordinator_suggests_the_second_vendor(state)

        kwargs = keep.call_args.kwargs
        assert keep.call_args.args == (state,)
        assert kwargs["owner"] == Part(VENDOR, VENDOR_LABEL)
        assert kwargs["suggester"] == Part(COORDINATOR, COORDINATOR_LABEL)
        assert kwargs["newcomer"] == Part(VENDOR2, VENDOR2_LABEL)
        # Roles must be explicit, or EvaluateDefaultRolesNode falls back to
        # its hardcoded [VENDOR] default (#1969) — which happens to be right
        # here, so only an explicit list keeps it honest.
        assert kwargs["roles"] == [CVDRole.VENDOR]
        assert kwargs["seated"] == (REPORTER, VENDOR, COORDINATOR, VENDOR2)
        # The join the opening's roster gate kept is the continuation's own
        # precondition, so the scenario hands it that prop and no other.
        assert kwargs["joined"] is COORDINATOR_JOINED

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
            patch.object(
                owner_decision_keep,
                "find_cp_offer_for_case",
                return_value="urn:test:cp-offer",
            ) as cp_offer,
            patch.object(
                owner_decision_parts,
                "find_case_actor_participant_id",
                return_value="urn:test:case-actor-participant",
            ),
            patch.object(
                owner_decision_keep,
                "run_case_invite_chain",
                side_effect=lambda **kw: order.append("invite-chain"),
            ) as chain,
            patch.object(
                owner_decision_keep,
                "invitee_triages_after_joining",
                side_effect=lambda *a, **kw: order.append("triage"),
            ) as triage,
            patch_chain_shared(
                coordinated_joining, "wait_for_case_on_container"
            ),
            _no_banners(),
        ):
            demo.the_coordinator_suggests_the_second_vendor(state)

        assert order == ["suggest", "approve", "invite-chain", "triage"]

        assert suggest.call_args.kwargs == {
            "suggested_actor_id": state.actor_id(VENDOR2),
            "roles": [CVDRole.VENDOR],
        }
        assert (
            suggest.call_args.args[0].actor is state.actor(COORDINATOR).actor
        )
        assert approve.call_args.args[0].actor is state.actor(VENDOR).actor
        assert approve.call_args.kwargs == {
            "cp_offer_id": "urn:test:cp-offer",
            "case_actor_id": "urn:test:case-actor-participant",
        }
        # The recommendation is polled for on Vendor1's own container, where
        # the CaseActor forwards it (ADR-0026).
        assert cp_offer.call_args.kwargs["client"] is state.client(VENDOR)

        # The CaseActor invites on its own, so the chain is given no inviter
        # and reads the canonical ledger through the case-actor container.
        kwargs = chain.call_args.kwargs
        assert "inviter" not in kwargs
        assert kwargs["ledger_client"] is state.case_actor_client
        assert kwargs["invitee_client"] is state.client(VENDOR2)
        assert kwargs["invitee"] is state.actor(VENDOR2).actor

        # The roster is read from Vendor1, which keeps the case
        # (DEMOMA-10-002).
        assert triage.call_args.kwargs["owner"] == VENDOR
        assert triage.call_args.kwargs["seated"] == (
            REPORTER,
            VENDOR,
            COORDINATOR,
            VENDOR2,
        )

    @pytest.mark.spec("CLP-08-005")
    def test_the_reporter_holds_the_case_before_vendor2s_triage(self):
        """Bug #2135: Vendor2's triage broadcasts to the Reporter too.

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
            patch.object(
                owner_decision_keep,
                "find_cp_offer_for_case",
                return_value="urn:test:cp-offer",
            ),
            patch.object(
                owner_decision_parts,
                "find_case_actor_participant_id",
                return_value="urn:test:case-actor-participant",
            ),
            patch.object(owner_decision_keep, "run_case_invite_chain"),
            patch.object(
                coordinated_joining,
                "run_invite_path_rm_triage",
                side_effect=lambda **_kw: order.append("triage"),
            ) as triage,
            patch.object(coordinated_joining, "wait_for_case_participants"),
            patch_chain_shared(
                coordinated_joining,
                "wait_for_case_on_container",
                side_effect=_wait_for_case,
            ),
            _no_banners(),
        ):
            demo.the_coordinator_suggests_the_second_vendor(state)

        assert "reporter_wait" in order, (
            "wait_for_case_on_container(reporter_client) was never called"
            " before Vendor2's triage"
        )
        assert "triage" in order, "run_invite_path_rm_triage was never called"
        assert order.index("reporter_wait") < order.index("triage"), (
            f"the Reporter's case-replica wait must precede Vendor2's RM"
            f" triage; order was {order} — Bug #2135 (CLP-08-005)"
        )
        # The triage's waits read the canonical store, not Vendor1's replica.
        assert (
            triage.call_args.kwargs["auth_client"] is state.case_actor_client
        )
        assert triage.call_args.kwargs["invited_client"] is state.client(
            VENDOR2
        )

    def test_a_missing_recommendation_skips_the_approval(self):
        """The delivery gate owns the skip (ADR-0058, EDF-06-005).

        The real ``demo_gate`` runs: an ``Offer(CaseParticipant)`` that never
        arrived must skip Vendor1's ``accept-actor-recommendation`` rather
        than approve a recommendation that was never made.
        """
        state = _four_party_state()

        with (
            patch.object(ActorSession, "suggest_actor_to_case") as suggest,
            patch.object(
                ActorSession, "accept_actor_recommendation"
            ) as approve,
            patch.object(
                owner_decision_keep,
                "find_cp_offer_for_case",
                side_effect=AssertionError(
                    "timed out polling for Offer(CaseParticipant)"
                ),
            ),
            patch.object(owner_decision_keep, "run_case_invite_chain"),
            patch.object(owner_decision_keep, "invitee_triages_after_joining"),
            patch_chain_shared(
                coordinated_joining, "wait_for_case_on_container"
            ),
        ):
            demo.the_coordinator_suggests_the_second_vendor(state)

        suggest.assert_called_once()
        approve.assert_not_called()
        assert _demo_failures, (
            "a skipped approval must leave a recorded failure, or the run"
            " would pass with Vendor2 never invited (DEMOCI-01-003)"
        )

    def test_a_coordinator_that_never_joined_stops_the_story(self):
        """The continuation reads the join before it suggests anyone.

        A suggestion from a non-participant is refused, so the fragment stops
        the story rather than acting on a case the suggester is not in
        (DEMOCI-01-011, DEMOMA-10-003).
        """
        state = _four_party_state(joined=False)

        with (
            patch.object(ActorSession, "suggest_actor_to_case") as suggest,
            pytest.raises(DemoStoryError, match="case the Coordinator joined"),
        ):
            demo.the_coordinator_suggests_the_second_vendor(state)

        suggest.assert_not_called()


# ---------------------------------------------------------------------------
# The note thread this scenario's joiners add to (DEMOCI-11-017)
# ---------------------------------------------------------------------------


class TestTheFourExchangeNotes:
    """The Coordinator and Vendor2 answer the thread the opening posted."""

    def _answer(self) -> as_Note:
        return as_Note(
            id_="urn:test:workaround-answer",
            name="Vendor1 Response",
            content="A workaround is available.",
        )

    def test_the_joiners_reply_to_the_kept_workaround_answer(self):
        """One thread, not two: the opening's thread is continued.

        The note comes off the state as the ``VENDORS_ANSWER`` prop, so the
        thread every vendor-first sibling records stays one thread
        (DEMOCI-11-017).
        """
        state = _four_party_state()
        answer = self._answer()
        state.keep(VENDORS_ANSWER, answer)

        with patch.object(vendor_continuations, "add_note_thread") as thread:
            demo.the_four_exchange_notes(state)

        watching_client, case, posts = thread.call_args.args
        # Posted through Vendor1's replica, which every sibling watches.
        assert watching_client is state.client(VENDOR)
        assert case is state.case
        assert thread.call_args.kwargs["in_reply_to"] is answer
        assert [post.name for post in posts] == [
            f"{COORDINATOR_LABEL} Update",
            f"{VENDOR2_LABEL} Status Update",
        ]
        # Each joiner posts from its own container.
        assert [post.poster.client for post in posts] == [
            state.client(COORDINATOR),
            state.client(VENDOR2),
        ]
        assert [post.poster.actor for post in posts] == [
            state.actor(COORDINATOR).actor,
            state.actor(VENDOR2).actor,
        ]
        # Vendor1 keeps the case, so no joiner claims ownership moved.
        assert all(
            "new case owner" not in post.content.lower() for post in posts
        )

    def test_an_unanswered_thread_stops_the_story_instead_of_posting(self):
        """A fragment reads a prop through an accessor that raises.

        The opening keeps nothing when its own thread failed, so this
        fragment stops the story rather than opening a thread of its own
        (``run_story`` records it under the first failure).
        """
        state = _four_party_state()

        with (
            patch.object(vendor_continuations, "add_note_thread") as thread,
            pytest.raises(DemoStoryError, match="workaround answer"),
        ):
            demo.the_four_exchange_notes(state)

        thread.assert_not_called()


# ---------------------------------------------------------------------------
# Both vendors stop at VFd (CSB-15-002, DEMOMA-10-015)
# ---------------------------------------------------------------------------


class TestBothVendorsFixTheVul:
    """Each Vendor reports fix ready; neither deploys."""

    def test_the_fragment_numbers_this_scenarios_two_milestones(self):
        """The shared step takes each half's label as its own argument.

        M5 is the fix-ready half and M6 the VFd-ceiling half, so the second
        label no longer repeats the first's claim (#5602).
        """
        state = _four_party_state()

        with patch.object(
            demo, "both_vendors_report_the_fix_ready"
        ) as fix_ready:
            demo.both_vendors_fix_the_vul(state)

        assert fix_ready.call_args.args == (state,)
        kwargs = fix_ready.call_args.kwargs
        assert set(kwargs) == {"reached", "stopped"}, kwargs
        assert kwargs["reached"].startswith("M5: ")
        assert "fix ready" in kwargs["reached"], kwargs["reached"]
        assert kwargs["stopped"].startswith("M6: ")
        assert "both vendors stopped at VFd" in kwargs["stopped"], kwargs[
            "stopped"
        ]
        assert "no fix-deployed transition" in kwargs["stopped"], kwargs[
            "stopped"
        ]

    def test_vendor1_reports_before_vendor2_and_each_is_rm_gated(self):
        """CSB-18-001: notify-fix-ready needs RM out of triage first.

        The real shared step runs, so the whole order is checked: the gate
        reads each vendor's own participant record before its own trigger,
        and Vendor1, the Case Owner, goes first.
        """
        state = _four_party_state()
        order: list[str] = []
        rm_calls: list[dict] = []

        def _rm_wait(**kwargs):
            rm_calls.append(kwargs)
            order.append(f"rm_wait:{kwargs['actor_id']}")

        with (
            patch.object(
                coordinated_continuations,
                "wait_for_participant_rm_state",
                side_effect=_rm_wait,
            ),
            patch.object(
                coordinated_continuations, "wait_for_participant_vf_state"
            ),
            patch.object(
                vendor_continuations, "wait_for_participant_vf_state"
            ),
            patch.object(vendor_continuations, "verify_fix_ready") as verify,
            patch.object(vendor_continuations, "verify_stops_at_fix_ready"),
            patch.object(
                ActorSession,
                "notify_fix_ready",
                autospec=True,
                side_effect=lambda session: order.append(
                    f"ready:{session.actor.id_}"
                ),
            ),
            _no_banners(),
        ):
            demo.both_vendors_fix_the_vul(state)

        assert [c["actor_id"] for c in rm_calls] == [
            state.actor_id(VENDOR),
            state.actor_id(VENDOR2),
        ]
        assert all(
            c["expected_states"] == {RM.ACCEPTED, RM.DEFERRED, RM.CLOSED}
            for c in rm_calls
        ), rm_calls
        assert order == [
            f"rm_wait:{state.actor_id(VENDOR)}",
            f"ready:{state.actor_id(VENDOR)}",
            f"rm_wait:{state.actor_id(VENDOR2)}",
            f"ready:{state.actor_id(VENDOR2)}",
        ], order
        # The fix-ready milestone verifies each Vendor on its own container,
        # Vendor1 first (#5602).
        assert [
            (c.kwargs["receiver_client"], c.kwargs["receiver_actor_id"])
            for c in verify.call_args_list
        ] == [
            (state.client(VENDOR), state.actor_id(VENDOR)),
            (state.client(VENDOR2), state.actor_id(VENDOR2)),
        ]

    def test_the_fix_ready_milestone_watches_both_vendors_on_both_replicas(
        self,
    ):
        """M5 reads each Vendor's VF on its own replica and the Reporter's.

        Each Vendor's fix path is its own (DEMOMA-09-009), so a label naming
        both reads both; M5 used to read Vendor1 twice (#5602).
        """
        state = _four_party_state()

        with (
            patch.object(
                coordinated_continuations, "wait_for_participant_rm_state"
            ),
            patch.object(
                coordinated_continuations, "wait_for_participant_vf_state"
            ),
            patch.object(
                vendor_continuations, "wait_for_participant_vf_state"
            ) as vf_wait,
            patch.object(vendor_continuations, "verify_fix_ready"),
            patch.object(vendor_continuations, "verify_stops_at_fix_ready"),
            patch.object(ActorSession, "notify_fix_ready"),
            _no_banners(),
        ):
            demo.both_vendors_fix_the_vul(state)

        watched = {
            (c.kwargs["client"], c.kwargs["actor_id"])
            for c in vf_wait.call_args_list
        }
        for vendor in (VENDOR, VENDOR2):
            for watcher in (vendor, REPORTER):
                assert (
                    state.client(watcher),
                    state.actor_id(vendor),
                ) in watched
        assert all(
            c.kwargs["expected_states"] == {CS_vf.VF}
            for c in vf_wait.call_args_list
        )

    @pytest.mark.spec("CSB-15-002")
    def test_the_ceiling_milestone_reads_both_vendors_missing_deployment(self):
        """M6 reads the d→D transition neither Vendor makes (#5602)."""
        state = _four_party_state()

        with (
            patch.object(
                coordinated_continuations, "wait_for_participant_rm_state"
            ),
            patch.object(
                coordinated_continuations, "wait_for_participant_vf_state"
            ),
            patch.object(
                vendor_continuations, "wait_for_participant_vf_state"
            ),
            patch.object(vendor_continuations, "verify_fix_ready"),
            patch.object(
                vendor_continuations, "verify_stops_at_fix_ready"
            ) as stopped,
            patch.object(ActorSession, "notify_fix_ready"),
            _no_banners(),
        ):
            demo.both_vendors_fix_the_vul(state)

        assert [
            (c.kwargs["receiver_client"], c.kwargs["receiver_actor_id"])
            for c in stopped.call_args_list
        ] == [
            (state.client(VENDOR), state.actor_id(VENDOR)),
            (state.client(VENDOR2), state.actor_id(VENDOR2)),
        ]


# ---------------------------------------------------------------------------
# Publication: Vendor1 publishes first, the Reporter last (DEMOMA-07-003)
# ---------------------------------------------------------------------------


@pytest.mark.spec("DEMOMA-07-003")
class TestEveryonePublishes:
    """Vendor1 keeps the case, so Vendor1's publication ends the embargo."""

    def _run(self, state) -> list[str]:
        """Run the fragment, recording every publication and EM wait."""
        order: list[str] = []

        with (
            patch.object(
                vendor_continuations,
                "wait_for_case_em_terminated",
                side_effect=lambda client, case_id: order.append(
                    f"em_exited:{_cast_name_of(state, client)}"
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
                    f"published:{_cast_name_of(state, session.client)}"
                ),
            ),
            _no_banners(),
        ):
            demo.everyone_publishes(state)
        return order

    def test_the_four_publish_in_order_with_both_teardown_waits(self):
        """The whole publication order, so a reordering shows as a diff.

        Vendor1 → Vendor2 → Coordinator → Reporter: the Case Owner publishes
        first, which is what ends the embargo (DEMOMA-07-003(4)), and the
        Reporter reports last.
        """
        state = _four_party_state()

        assert self._run(state) == [
            "published:vendor",
            "em_exited:vendor",
            "published:vendor2",
            "published:coordinator",
            "em_exited:reporter",
            "published:reporter",
            "em_exited:reporter",
        ]

    def test_the_reporters_em_wait_precedes_its_own_notify_published(self):
        """Issue #1690, carried over from ``_phase_publication``.

        The Reporter used to call ``notify-published`` before the embargo
        teardown had reached its replica, which committed an out-of-causal-
        order ``EM.ACTIVE`` ledger entry after the embargo was removed.
        """
        state = _four_party_state()
        order = self._run(state)

        assert "em_exited:reporter" in order, (
            "wait_for_case_em_terminated was never called on the Reporter's"
            " replica"
        )
        assert "published:reporter" in order, (
            "the Reporter never reported published"
        )
        assert order.index("em_exited:reporter") < order.index(
            "published:reporter"
        ), (
            "the Reporter's EM.EXITED wait must precede its own"
            f" notify-published (#1690); order was {order}"
        )

    def test_the_final_milestone_reads_vendor1_as_the_disclosing_owner(self):
        """M7 confirms CS.VFdPxa from the Case Owner's replica."""
        state = _four_party_state()

        with (
            patch.object(vendor_continuations, "wait_for_case_em_terminated"),
            patch.object(
                vendor_continuations, "wait_for_participant_vf_state"
            ),
            patch.object(
                vendor_continuations, "verify_publicly_disclosed"
            ) as disclosed,
            patch.object(ActorSession, "notify_published"),
            _no_banners(),
        ):
            demo.everyone_publishes(state)

        kwargs = disclosed.call_args.kwargs
        assert kwargs["receiver_client"] is state.client(VENDOR)
        assert kwargs["reporter_client"] is state.client(REPORTER)
        assert kwargs["receiver_actor_id"] == state.actor_id(VENDOR)


# ---------------------------------------------------------------------------
# Closure: Vendor1, the Case Owner, leaves last (CM-23-015)
# ---------------------------------------------------------------------------


@pytest.mark.spec("CM-23-015")
class TestEveryoneCloses:
    """Vendor2, the Coordinator and the Reporter leave, then Vendor1."""

    def test_vendor1_leaves_last_and_departures_read_the_case_actor(self):
        """The owner's ``Leave`` is gated on the CASE_MANAGER's store.

        That store lives on the dedicated case-actor container
        (DEMOMA-06-005), so the authority client must be that one and not
        Vendor1's own.
        """
        state = _four_party_state()

        with (
            patch.object(ActorSession, "leave_case"),
            stub_closure_gate(),
            patch.object(
                coordinated_continuations, "close_case_owner_last"
            ) as closure,
        ):
            demo.everyone_closes(state)

        kwargs = closure.call_args.kwargs
        assert kwargs["milestone"] == "M8"
        assert kwargs["authority_client"] is state.case_actor_client
        assert [leaver.client for leaver in kwargs["others"]] == [
            state.client(VENDOR2),
            state.client(COORDINATOR),
            state.client(REPORTER),
        ]
        assert kwargs["owner"].client is state.client(VENDOR)
        assert kwargs["owner"].actor is state.actor(VENDOR).actor


# ---------------------------------------------------------------------------
# The cast: every container reset, only the opening's two seeded
# (DEMOMA-01-003, DEMOCI-11-018, #5532)
# ---------------------------------------------------------------------------


class TestRvcvExtensionCastAndOpening:
    """``run_rvcv_extension_demo`` resets four containers and seeds two."""

    def _open_the_cast(self, clients, case_actor_client):
        """Run the scenario's ``open_cast`` with the seeding patched out.

        ``run_story()`` is what plays the story; the cast opening is the
        callable it is handed, so this runs that and nothing else.  The reset
        and the read-back are patched on
        :mod:`vultron.demo.helpers.story_cast`, where the shared
        ``open_story_cast`` resolves them.
        """
        seeded = [
            mock_actor(f"urn:test:{name}") for name in (REPORTER, VENDOR)
        ]
        captured = SimpleNamespace()

        with (
            patch.object(demo, "run_story") as run_story,
            patch.object(
                story_cast, "reset_datalayer", return_value={"status": "ok"}
            ) as reset,
            patch.object(seeding_reset, "seed_case_actor_identity") as reseed,
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
            demo.run_rvcv_extension_demo(
                reporter_client=clients[REPORTER],
                vendor_client=clients[VENDOR],
                coordinator_client=clients[COORDINATOR],
                vendor2_client=clients[VENDOR2],
                case_actor_client=case_actor_client,
                reporter_id="urn:test:reporter",
                vendor_id="urn:test:vendor",
                coordinator_id="urn:test:coordinator",
                vendor2_id="urn:test:vendor2",
            )
            captured.state = run_story.call_args.args[2](MagicMock())
            captured.run_story = run_story
        return captured, reset, reseed, seed_two, seed_four

    @pytest.mark.spec("DEMOMA-01-003")
    def test_reset_clears_every_container_and_reseeds_the_case_actor(self):
        """The Coordinator's and Vendor2's containers are reset too.

        A run must start from a clean baseline on every container it will
        touch, the two it seeds later included; the dedicated case-actor
        container's identity is re-seeded after its wipe (#1876).
        """
        clients = {name: mock_client() for name in _CAST}
        case_actor_client = mock_client()

        _, reset, reseed, _, _ = self._open_the_cast(
            clients, case_actor_client
        )

        assert [c.kwargs["client"] for c in reset.call_args_list] == [
            clients[REPORTER],
            clients[VENDOR],
            clients[COORDINATOR],
            clients[VENDOR2],
            case_actor_client,
        ]
        reseed.assert_called_once_with(case_actor_client)

    @pytest.mark.spec("DEMOCI-11-018")
    def test_the_opening_seeds_only_the_reporter_and_vendor1(self):
        """The Coordinator and Vendor2 are left as unseated containers.

        Every actor and peer record the opening writes before the case exists
        is one more read of the recording clock, so seeding either here would
        move the first ledger entry away from ``rv``'s and ``rvv``'s (#5532).
        """
        clients = {name: mock_client() for name in _CAST}

        captured, _, _, seed_two, seed_four = self._open_the_cast(
            clients, mock_client()
        )

        seed_two.assert_called_once()
        seeding_kwargs = seed_two.call_args.kwargs
        assert seeding_kwargs["reporter_client"] is clients[REPORTER]
        assert seeding_kwargs["vendor_client"] is clients[VENDOR]
        seed_four.assert_not_called()

        state = captured.state
        assert sorted(state.cast) == sorted([REPORTER, VENDOR])
        assert sorted(state.unseated) == sorted([COORDINATOR, VENDOR2])
        for name, label, actor_id in (
            (COORDINATOR, COORDINATOR_LABEL, "urn:test:coordinator"),
            (VENDOR2, VENDOR2_LABEL, "urn:test:vendor2"),
        ):
            waiting = state.container(name)
            assert isinstance(waiting, UnseatedContainer)
            assert waiting.client is clients[name]
            assert waiting.label == label
            assert waiting.actor_id == actor_id

    def test_the_run_plays_this_scenarios_story_under_its_own_name(self):
        """``run_story(name, plot, open_cast)`` names the registered demo."""
        clients = {name: mock_client() for name in _CAST}

        captured, _, _, _, _ = self._open_the_cast(clients, mock_client())

        run_story_mock = captured.run_story
        assert run_story_mock.call_args.args[0] == "rvcv-extension"
        assert run_story_mock.call_args.args[1] is demo.STORY


# ---------------------------------------------------------------------------
# The devlogs the invariant harness reads (DEMOMA-23-002, DEMOMA-06-005, DEMOMA-06-009)
# ---------------------------------------------------------------------------


class TestRvcvExtensionLedgerDump:
    """One file per actor, plus the canonical ledger, under the demo name."""

    def _dump(self, state):
        for name in state.cast:
            state.client(name).actor_id = f"https://example.org/actors/{name}"
        state.case_actor_client.actor_id = (
            "https://example.org/actors/case-actor"
        )
        state.harness.demo_name = "rvcv-extension"

        with patch.object(story_cast, "dump_case_ledgers") as dump:
            dump_vendor_coordinator_ledgers(state)
        return dump.call_args.kwargs

    def test_every_seated_replica_is_dumped_plus_the_canonical_ledger(self):
        """Four replicas in dump order, then the canonical ledger."""
        state = _four_party_state()
        kwargs = self._dump(state)

        assert kwargs["demo_name"] == "rvcv-extension"
        assert kwargs["case"] is state.case
        targets = kwargs["targets"]
        assert [t.actor_name for t in targets] == [
            "reporter",
            "vendor",
            "coordinator",
            "vendor2",
            "case-actor",
        ]
        # The canonical ledger is read on the dedicated container, never from
        # a participant's replica (DEMOMA-06-005, DEMOMA-06-009).
        assert targets[-1].client is state.case_actor_client
        assert targets[-1].route_key == "case-actor"

    def test_an_actor_the_run_never_seated_is_left_out(self):
        """A failure before the suggestion must not 404 the dump.

        The dump runs on the way out whether or not an earlier step failed
        (DEMOMA-23-003), and an unseated container holds no replica to read.
        """
        state = story_state(REPORTER, VENDOR, COORDINATOR, case=mock_case())
        targets = self._dump(state)["targets"]

        assert [t.actor_name for t in targets] == [
            "reporter",
            "vendor",
            "coordinator",
            "case-actor",
        ]


# ---------------------------------------------------------------------------
# The CLI sub-command and the registry entry (DEMOCI-11-011, DEMOCI-11-019)
# ---------------------------------------------------------------------------


@pytest.fixture
def help_text() -> str:
    """``vultron-demo rvcv-extension --help`` as the sub-command renders it."""
    result = CliRunner().invoke(cli_main, ["rvcv-extension", "--help"])
    assert result.exit_code == 0, result.output
    return result.output


class TestRvcvExtensionCliCommand:
    """The generated sub-command offers one option per container."""

    @pytest.mark.parametrize(
        "option",
        [
            "--skip-health-check",
            "--reporter-url",
            "--vendor-url",
            "--coordinator-url",
            "--vendor2-url",
            "--case-actor-url",
            "--reporter-id",
            "--vendor-id",
            "--coordinator-id",
            "--vendor2-id",
        ],
    )
    def test_the_option_is_offered(self, help_text: str, option: str):
        """One URL and one id option per container, plus the health skip."""
        assert option in help_text

    def test_the_case_actor_carries_no_id_option(self, help_text: str):
        """Only ``rvcv-handoff`` exposes one (DEMOMA-14-023)."""
        assert "--case-actor-id" not in help_text

    def test_main_builds_one_client_per_container_and_runs_the_story(self):
        """``main()`` names its containers and passes their clients on."""
        clients = {
            name: MagicMock(name=name, base_url=f"http://{name}:7999/api/v2")
            for name in (
                "reporter",
                "vendor",
                "coordinator",
                "vendor2",
                "case-actor",
            )
        }

        with (
            patch.object(demo, "story_clients", return_value=clients) as built,
            patch.object(demo, "run_rvcv_extension_demo") as run,
        ):
            demo.main(
                skip_health_check=True,
                vendor_url="http://elsewhere:7999/api/v2",
                case_actor_url="http://ca:7999/api/v2",
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
            "http://elsewhere:7999/api/v2",
            None,
            None,
        ]
        assert built.call_args.kwargs["skip_health_check"] is True
        # The CaseActor's own container is addressed through its override,
        # never through Vendor1's (DEMOMA-10-001).
        assert (
            built.call_args.kwargs["case_actor_url"] == "http://ca:7999/api/v2"
        )

        kwargs = run.call_args.kwargs
        assert kwargs["reporter_client"] is clients["reporter"]
        assert kwargs["vendor_client"] is clients["vendor"]
        assert kwargs["coordinator_client"] is clients["coordinator"]
        assert kwargs["vendor2_client"] is clients["vendor2"]
        assert kwargs["case_actor_client"] is clients["case-actor"]
        assert kwargs["vendor2_id"] == "urn:test:vendor2"


@pytest.fixture
def spec():
    """The one registry entry named ``rvcv-extension``."""
    entries = [s for s in registered_scenarios() if s.name == "rvcv-extension"]
    assert len(entries) == 1, entries
    return entries[0]


class TestRvcvExtensionRegistryEntry:
    """The registry is the sole declaration that the scenario exists."""

    def test_the_entry_describes_the_second_vendor_scenario(self, spec):
        """Every field is rendered into the generated scenario tables."""
        assert spec.label == "RVCV-extension"
        assert (
            spec.participants == "Reporter + Vendor1 + Coordinator + Vendor2"
        )
        assert spec.feature == "Coordinator-suggested second vendor"
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
        assert spec.demo_path == "vultron/demo/scenario/rvcv_extension_demo.py"
        assert spec.harness_path == (
            "test/ci/invariants/test_rvcv_extension_invariants.py"
        )


# ---------------------------------------------------------------------------
# A roster that never fills stops the keep continuation (#5536)
# ---------------------------------------------------------------------------


class TestARosterThatNeverFillsSkipsTheSuggestion:
    """The guarantee the nesting used to give, carried by a prop.

    ``test_rvcv_handoff_demo.py`` drives the same chain for the
    ``offer-ownership`` continuation.  Both branches of ``owner-keep-case``
    read the same prop, so both are driven through the real ``run_story``,
    the real ``demo_gate`` and the real fragments: a test of the read alone
    is what let the guarantee go missing in the first place (#5535).
    """

    @pytest.fixture
    def marks(self, monkeypatch):
        """Stand in for ``scenario_harness``, which needs a real case."""
        reset_demo_failures()
        harness = MagicMock()
        harness.demo_name = "rvcv-extension"

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
        poll after the suggestion trigger is stubbed: left real each would
        spend the whole ``OWNER_DECISION_TIMEOUT`` against a ``MagicMock``
        store and buy no assertion.
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
                owner_decision_keep,
                "find_cp_offer_for_case",
                return_value="urn:test:cp-offer",
            ),
            patch.object(owner_decision_keep, "run_case_invite_chain"),
            patch.object(owner_decision_keep, "invitee_triages_after_joining"),
            patch.object(
                ActorSession, "suggest_actor_to_case", autospec=True
            ) as suggest,
        ):
            yield suggest

    def _play(self, state) -> None:
        run_story(
            "rvcv-extension",
            story(
                vendor_coordinator_story.the_vendor_invites_the_coordinator,
                demo.the_coordinator_suggests_the_second_vendor,
            ),
            lambda _harness: state,
        )

    def test_a_timed_out_roster_leaves_vendor2_unsuggested(self, marks):
        """The suggest trigger never runs, and the roster is the one failure."""
        state = story_state(*_CAST, case=mock_case())

        with self._roster(fills=False) as suggest:
            self._play(state)

        suggest.assert_not_called()
        with pytest.raises(
            DemoStoryError, match="case the Coordinator joined"
        ):
            state.kept(COORDINATOR_JOINED)

    def test_a_filled_roster_lets_the_suggestion_run(self, marks):
        """The counterpart, so the test above is not vacuous."""
        state = story_state(*_CAST, case=mock_case())

        with self._roster(fills=True) as suggest:
            self._play(state)

        assert state.kept(COORDINATOR_JOINED) == str(state.case.id_)
        suggest.assert_called_once()
        assert suggest.call_args.args[0].client is state.client(COORDINATOR)


# ---------------------------------------------------------------------------
# Shared helpers this scenario leans on: the four-container seeding
# (DEMOMA-10-001) and the Invite lookup (ADR-0026)
# ---------------------------------------------------------------------------


@pytest.fixture
def base(client: TestClient) -> str:
    """The base URL of the in-process node, with the ``/api/v2`` prefix."""
    return str(client.base_url).rstrip("/") + "/api/v2"


@pytest.fixture
def routed_clients(client: TestClient, base: str):
    """Route every ``DataLayerClient`` call through the in-process node.

    Only the seeding test needs it: the rest of this module patches its
    collaborators out and makes no request at all.
    """
    from vultron.demo.utils import DataLayerClient

    mp = MonkeyPatch()
    try:
        mp.setattr(DataLayerClient, "call", make_testclient_call(client, base))
        yield base
    finally:
        mp.undo()


class TestSeedContainersRvcv:
    """The four-container seeding both scenarios of the pair run.

    Imported from :mod:`vultron.demo.helpers.seeding`, its real home: the
    composed scenario module re-exports nothing, and the fragment that calls
    it is the pair's shared opening, not this scenario (#5536).
    """

    def test_seed_creates_all_four_actors(self, routed_clients: str):
        """One actor per container, each named for its role."""
        base = routed_clients
        reporter, vendor, coordinator, vendor2 = seeding.seed_containers_rvcv(
            reporter_client=make_client(base),
            vendor_client=make_client(base),
            coordinator_client=make_client(base),
            vendor2_client=make_client(base),
        )

        assert reporter.id_ is not None
        assert reporter.name == "Reporter"
        assert vendor.id_ is not None
        assert vendor.name == "Vendor"
        assert coordinator.id_ is not None
        assert coordinator.name == "Coordinator"
        assert vendor2.id_ is not None
        assert vendor2.name == "Vendor2"

    def test_seed_registers_cross_container_peers(self, routed_clients: str):
        """Each actor knows the other three (DEMOMA-10-001)."""
        base = routed_clients
        reporter_client = make_client(base)

        seeding.seed_containers_rvcv(
            reporter_client=reporter_client,
            vendor_client=make_client(base),
            coordinator_client=make_client(base),
            vendor2_client=make_client(base),
        )

        actors = reporter_client.get("/actors/")
        names = {a.get("name") for a in actors if isinstance(a, dict)}
        assert {"Reporter", "Vendor", "Coordinator", "Vendor2"} <= names

    def test_seed_with_deterministic_ids(self, routed_clients: str):
        """The ``--<role>-id`` values are the ids the actors get.

        The recordings are keyed on them, so a seeded actor must take the id
        the run was given rather than deriving its own (DEMOCI-11-020).
        """
        base = routed_clients
        wanted = {
            role: f"{base}/actors/{role}-rvcv-det-test"
            for role in ("reporter", "vendor", "coordinator", "vendor2")
        }

        seeded = seeding.seed_containers_rvcv(
            reporter_client=make_client(base),
            vendor_client=make_client(base),
            coordinator_client=make_client(base),
            vendor2_client=make_client(base),
            reporter_actor_id=wanted["reporter"],
            vendor_actor_id=wanted["vendor"],
            coordinator_actor_id=wanted["coordinator"],
            vendor2_actor_id=wanted["vendor2"],
        )

        assert [actor.id_ for actor in seeded] == [
            wanted["reporter"],
            wanted["vendor"],
            wanted["coordinator"],
            wanted["vendor2"],
        ]


def _archived(rows: dict[str, dict]) -> dict[str, dict]:
    """*rows*, keyed by activity id, as intake archives them (DL-06-006).

    The invitee holds a received Invite only as a ``ReceivedActivityRecord``
    under its own key, never under the sender's id.
    """
    return {
        f"received-activity/{activity_id}": {
            "type": "ReceivedActivityRecord",
            "id": f"received-activity/{activity_id}",
            "received_body": json.dumps({"id": activity_id, **row}),
        }
        for activity_id, row in rows.items()
    }


class TestFindCaseInviteForActor:
    """The helper that locates the CaseActor's Invite for the invitee.

    In the ADR-0026 flow the CaseActor delivers an
    ``Invite(Actor)[target=VulnerabilityCaseStub]``
    to the suggested actor on the owner's approval, and the invite chain finds
    it so it can puppeteer Vendor2's accept (MV-10-004 seeds the replica only
    after the Accept).  Imported from :mod:`vultron.demo.helpers.polling`,
    where it lives.
    """

    CASE_ID = "urn:uuid:case-1"
    INVITEE_ID = "http://vendor2:7999/api/v2/actors/v2"

    def _invite(self, target, obj):
        return {"type": "Invite", "target": target, "object": obj}

    def _find(self, rows: dict[str, dict], **kwargs):
        client = MagicMock()
        client.get.return_value = _archived(rows)
        return find_case_invite_for_actor(
            client=client,
            case_id=self.CASE_ID,
            invitee_id=self.INVITEE_ID,
            **kwargs,
        )

    def test_matches_invite_with_dict_target_and_object(self):
        """The shape the wire format normally arrives in."""
        result = self._find(
            {
                "urn:uuid:invite-1": self._invite(
                    {"id": self.CASE_ID}, {"id": self.INVITEE_ID}
                )
            },
            timeout_seconds=1.0,
        )
        assert result == "urn:uuid:invite-1"

    def test_matches_invite_with_bare_string_target_and_object(self):
        """Target and object may arrive as bare URIs after a round-trip."""
        result = self._find(
            {"urn:uuid:invite-2": self._invite(self.CASE_ID, self.INVITEE_ID)},
            timeout_seconds=1.0,
        )
        assert result == "urn:uuid:invite-2"

    @pytest.mark.parametrize(
        ("activity_id", "row_name"),
        [
            ("urn:uuid:invite-3", "other case"),
            ("urn:uuid:invite-4", "other actor"),
            ("urn:uuid:offer-1", "not an Invite"),
        ],
    )
    def test_a_near_miss_is_not_this_actors_invite(
        self, activity_id: str, row_name: str
    ):
        """Accepting a near miss would accept into the wrong case."""
        rows = {
            "other case": self._invite(
                {"id": "urn:uuid:other-case"}, {"id": self.INVITEE_ID}
            ),
            "other actor": self._invite(
                {"id": self.CASE_ID}, {"id": "http://elsewhere/actors/x"}
            ),
            "not an Invite": {
                "type": "Offer",
                "target": {"id": self.CASE_ID},
                "object": {"id": self.INVITEE_ID},
            },
        }

        with pytest.raises(AssertionError, match="Timed out waiting"):
            self._find(
                {activity_id: rows[row_name]},
                timeout_seconds=0.1,
                poll_interval=0.05,
            )


# ---------------------------------------------------------------------------
# The RM-triage budget this pair raised (ISSUE-2811)
# ---------------------------------------------------------------------------


class TestTheRmTriageBudgetThisScenarioRaised:
    """Vendor1's triage keeps the 60 s budget the ``rvcv`` pair needed.

    The 20 s default raced under the load of a run that brings five
    containers up in CI (ISSUE-2811), and this scenario is the one that
    raised it.  The opening is now written once, so the budget is a constant
    of the family rather than a keyword this scenario passes, and the
    narrower siblings inherit it — which refuses nothing they admitted and
    moves no byte of a recording (DEMOCI-11-018).  That the opening passes
    the constant is ``test/demo/vendor_story/``'s; that the constant is still
    the value the regression needed is this scenario's, because it is the
    run whose load set it.
    """

    def test_the_shared_opening_carries_the_sixty_second_budget(self):
        """A regression here would restore the race in every sibling."""
        assert vendor_story.VENDOR_TRIAGE_TIMEOUT == 60.0, (
            "Vendor1's RM triage needs the 60 s budget this scenario's CI"
            " load set; the 20 s default raced (ISSUE-2811)"
        )
