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


"""Unit tests for :mod:`vultron.demo.helpers.rcvcv_story` (DEMOMA-19, #5846).

The fragments only ``rcvcv`` tells after C1 decides to invite a second
Coordinator, each driven against a :func:`~test.demo._helpers.story_state`
stand-in cast, so a test observes what the fragment calls.  The story's
shape, the seating of the character actors, the ledger dump, the CLI and the
registry entry stay in ``test_rcvcv_demo.py``, beside the scenario module
that owns them (CS-18-004).  The stand-in cast both files drive lives in
``test/demo/_rcvcv_support.py``.  Each patch names the module that looks the
patched name up (``test/demo_unit/test_story_patch_targets.py``).
"""

from unittest.mock import patch

import pytest

import vultron.demo.scenario.rcvcv_demo as demo
from test.demo._helpers import (
    devlogs_name_of,
    gate_failures,
    patch_chain_shared,
    sessions_of,
    stub_closure_gate,
)
from test.demo._rcvcv_support import CAST, five_party_state, no_banners
from vultron.core.states.cs import CS_d, CS_vf
from vultron.core.states.rm import RM
from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers import rcvcv_story
from vultron.demo.helpers.coordinated_story import (
    REPORTER,
    TIMELINE_ANSWER,
    continuations as coordinated_continuations,
    joining as coordinated_joining,
)
from vultron.demo.helpers.invite_chain import links as invite_links
from vultron.demo.helpers.owner_decision_story import (
    keep as owner_decision_keep,
    parts as owner_decision_parts,
)
from vultron.demo.helpers.polling import LATE_JOINER_TIMEOUT
from vultron.demo.utils.failures import _demo_failures
from vultron.enums.roles import CVDRole
from vultron.errors import DemoStoryError
from vultron.wire.as2.vocab.base.objects.object_types import as_Note

#: Clear the process-global failure accumulator around every test.
pytestmark = pytest.mark.usefixtures("fresh_demo_failures")


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
            patch.object(
                coordinated_joining, "run_case_invite_chain"
            ) as chain,
            patch.object(
                coordinated_joining, "run_invite_path_rm_triage"
            ) as triage,
            patch.object(
                coordinated_joining, "wait_for_case_participants"
            ) as roster,
            patch_chain_shared(
                coordinated_joining, "wait_for_case_on_container"
            ) as replica_wait,
            no_banners(),
        ):
            rcvcv_story.c1_invites_the_second_coordinator(state)
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
        state = five_party_state()
        _, triage, roster, _ = self._invite_c2(state, run_then=True)

        triage.assert_not_called()
        assert roster.call_args.kwargs["vendor_client"] is state.client(
            rcvcv_story.C1
        )
        assert roster.call_args.kwargs["expected_actor_ids"] == {
            state.actor_id(who)
            for who in (
                REPORTER,
                rcvcv_story.C1,
                rcvcv_story.V1,
                rcvcv_story.C2,
            )
        }

    @pytest.mark.spec("DEMOCI-01-011")
    @pytest.mark.spec("DEMOMA-19-009")
    def test_the_roster_keeps_the_join_c2s_suggestion_reads(self):
        """Only a participant may suggest anyone (#5535).

        C2's join is the suggestion's causal precondition, and a flat story
        cannot nest the suggestion inside the roster's gate, so the gate keeps
        :data:`~vultron.demo.scenario.rcvcv_demo.C2_JOINED` and the shared
        continuation reads it.  Without it the story stops rather than posting
        a suggestion from an actor that is not in the case.
        """
        state = five_party_state(joined=False)

        self._invite_c2(state, run_then=True)

        assert state.kept(rcvcv_story.C2_JOINED) == str(state.case.id_)

    def test_a_roster_that_never_arrives_keeps_no_join(self):
        """The gate records the timeout, so the suggestion stops the story."""
        state = five_party_state(joined=False)

        with (
            patch.object(
                coordinated_joining, "run_case_invite_chain"
            ) as chain,
            patch.object(
                coordinated_joining,
                "wait_for_case_participants",
                side_effect=AssertionError("roster never filled"),
            ),
            patch_chain_shared(
                coordinated_joining, "wait_for_case_on_container"
            ),
        ):
            rcvcv_story.c1_invites_the_second_coordinator(state)
            chain.call_args.kwargs["then"]()

        with pytest.raises(DemoStoryError, match="no case C2 joined"):
            state.kept(rcvcv_story.C2_JOINED)

    def test_the_invite_offers_the_coordinator_role_from_c1(self):
        """C1, the Case Owner, invites C2 as ``CVDRole.COORDINATOR``."""
        state = five_party_state()
        chain, _, _, _ = self._invite_c2(state)

        kwargs = chain.call_args.kwargs
        assert kwargs["invitee_name"] == rcvcv_story.C2_LABEL
        assert kwargs["invitee_client"] is state.client(rcvcv_story.C2)
        assert kwargs["invitee"] is state.actor(rcvcv_story.C2).actor
        assert kwargs["inviter"].client is state.client(rcvcv_story.C1)
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
        state = five_party_state()
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
        state = five_party_state()
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
            no_banners(),
        ):
            rcvcv_story.c2_suggests_the_vendor_deployer(state)

        assert order == ["suggest", "approve", "invite-chain", "triage"]

        # Roles must be explicit, or EvaluateDefaultRolesNode falls back to
        # the hardcoded [VENDOR] default and V2 never reaches VFD (#1969).
        assert suggest.call_args.kwargs == {
            "suggested_actor_id": state.actor_id(rcvcv_story.V2),
            "roles": [CVDRole.VENDOR, CVDRole.DEPLOYER],
        }
        assert (
            suggest.call_args.args[0].actor
            is state.actor(rcvcv_story.C2).actor
        )
        assert (
            approve.call_args.args[0].actor
            is state.actor(rcvcv_story.C1).actor
        )
        assert approve.call_args.kwargs == {
            "cp_offer_id": "urn:test:cp-offer",
            "case_actor_id": "urn:test:case-actor-participant",
        }
        # The recommendation is polled for on C1's own container.
        assert cp_offer.call_args.kwargs["client"] is state.client(
            rcvcv_story.C1
        )

        # The CaseActor invites on its own, so the chain is given no inviter
        # and reads the canonical ledger through the case-actor container.
        kwargs = chain.call_args.kwargs
        assert "inviter" not in kwargs
        assert kwargs["ledger_client"] is state.case_actor_client
        assert kwargs["invitee_client"] is state.client(rcvcv_story.V2)
        assert kwargs["invitee"] is state.actor(rcvcv_story.V2).actor

        # V2 arrives through four hops, so its waits get the multi-hop budget.
        assert kwargs["invite_timeout"] == rcvcv_story.LATE_JOIN_TIMEOUT
        assert kwargs["replica_timeout"] == rcvcv_story.LATE_JOIN_TIMEOUT
        assert kwargs["reply_timeout"] == rcvcv_story.LATE_JOIN_TIMEOUT
        # The roster the triage gates on is read from the Case Owner's own
        # replica, which is C1 here and the new owner in a story whose
        # ownership moved (#5535).
        assert triage.call_args.kwargs == {
            "seated": (
                REPORTER,
                rcvcv_story.C1,
                rcvcv_story.V1,
                rcvcv_story.C2,
                rcvcv_story.V2,
            ),
            "owner": rcvcv_story.C1,
            "owner_label": rcvcv_story.C1_LABEL,
            "join_timeout": LATE_JOINER_TIMEOUT,
            "triage_timeout": rcvcv_story.LATE_JOIN_TIMEOUT,
        }

    def test_the_approval_is_skipped_when_the_recommendation_never_arrives(
        self,
    ):
        """ADR-0058: the Offer is the approval's causal precondition.

        The real ``demo_gate`` runs: a lookup timeout must record one failure
        and skip the approval and the whole invite chain under it, rather than
        approving an Offer id that is ``None``.
        """
        state = five_party_state()

        with (
            patch.object(ActorSession, "suggest_actor_to_case"),
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
            patch.object(
                owner_decision_parts,
                "find_case_actor_participant_id",
                return_value="urn:test:case-actor-participant",
            ),
            patch.object(
                owner_decision_keep, "run_case_invite_chain"
            ) as chain,
            patch.object(
                owner_decision_keep, "invitee_triages_after_joining"
            ) as triage,
            patch_chain_shared(
                coordinated_joining, "wait_for_case_on_container"
            ),
        ):
            rcvcv_story.c2_suggests_the_vendor_deployer(state)

        approve.assert_not_called()
        # The chain and the triage sit outside the gate, so the caller still
        # reaches them; what the gate owns is the approval.
        assert chain.called
        assert triage.called
        assert gate_failures(), (
            f"the closed gate must record one failure: {_demo_failures!r}"
        )

    def test_a_missing_case_actor_participant_is_reported_not_raised(self):
        """The Accept has nowhere to route back to, so the gate records it."""
        state = five_party_state()

        with (
            patch.object(ActorSession, "suggest_actor_to_case"),
            patch.object(
                ActorSession, "accept_actor_recommendation"
            ) as approve,
            patch.object(
                owner_decision_keep,
                "find_cp_offer_for_case",
                return_value="urn:test:cp-offer",
            ),
            patch.object(
                owner_decision_parts,
                "find_case_actor_participant_id",
                return_value=None,
            ),
            patch.object(owner_decision_keep, "run_case_invite_chain"),
            patch.object(owner_decision_keep, "invitee_triages_after_joining"),
            patch_chain_shared(
                coordinated_joining, "wait_for_case_on_container"
            ),
        ):
            rcvcv_story.c2_suggests_the_vendor_deployer(state)

        approve.assert_not_called()
        assert any("route the Accept to" in f for f in gate_failures()), (
            _demo_failures
        )

    def test_v2_accepts_the_invite_the_case_actor_delivered(self):
        """The last hop: V2 answers the Invite found in its own container.

        The real invite chain runs, so the Invite is located by polling V2's
        DataLayer and the Accept is puppeteered from V2's own container — no
        inbox injection (DEMOMA-00-002, DEMOMA-19-022).
        """
        state = five_party_state()

        with (
            patch.object(ActorSession, "suggest_actor_to_case"),
            patch.object(ActorSession, "accept_actor_recommendation"),
            patch.object(
                ActorSession, "accept_case_invite", autospec=True
            ) as accept,
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
            patch.object(
                invite_links,
                "find_case_invite_for_actor",
                return_value="urn:test:v2-invite",
            ) as find_invite,
            patch.object(owner_decision_keep, "invitee_triages_after_joining"),
            patch_chain_shared(
                coordinated_joining, "wait_for_case_on_container"
            ) as replica_wait,
        ):
            rcvcv_story.c2_suggests_the_vendor_deployer(state)

        assert find_invite.call_args.kwargs["client"] is state.client(
            rcvcv_story.V2
        )
        assert find_invite.call_args.kwargs["invitee_id"] == state.actor_id(
            rcvcv_story.V2
        )
        accept.assert_called_once()
        assert accept.call_args.args[0].client is state.client(rcvcv_story.V2)
        assert accept.call_args.kwargs == {"invite_id": "urn:test:v2-invite"}
        # The Accept seeds V2's case replica, which the chain then waits for.
        assert [
            c
            for c in replica_wait.call_args_list
            if c.kwargs.get("client") is state.client(rcvcv_story.V2)
        ]

    def test_v2_never_accepts_an_invite_that_was_not_delivered(self):
        """#3038: the answer nests inside the Invite's delivery gate."""
        state = five_party_state()

        with (
            patch.object(ActorSession, "suggest_actor_to_case"),
            patch.object(ActorSession, "accept_actor_recommendation"),
            patch.object(ActorSession, "accept_case_invite") as accept,
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
            patch.object(
                invite_links,
                "find_case_invite_for_actor",
                side_effect=AssertionError("timed out polling for Invite"),
            ),
            patch.object(owner_decision_keep, "invitee_triages_after_joining"),
            patch_chain_shared(
                coordinated_joining, "wait_for_case_on_container"
            ) as replica_wait,
        ):
            rcvcv_story.c2_suggests_the_vendor_deployer(state)

        accept.assert_not_called()
        assert not [
            c
            for c in replica_wait.call_args_list
            if c.kwargs.get("client") is state.client(rcvcv_story.V2)
        ], (
            "V2's replica wait depends on the Accept, so the closed gate must"
            f" skip it: {replica_wait.call_args_list!r}"
        )

    @pytest.mark.spec("CLP-08-005")
    def test_the_reporter_holds_the_case_before_v2s_triage(self):
        """Bug #2120: V2's triage broadcasts to the Reporter too."""
        state = five_party_state()
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
            ),
            patch.object(coordinated_joining, "wait_for_case_participants"),
            patch_chain_shared(
                coordinated_joining,
                "wait_for_case_on_container",
                side_effect=_wait_for_case,
            ),
            no_banners(),
        ):
            rcvcv_story.c2_suggests_the_vendor_deployer(state)

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
        state = five_party_state()

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
                coordinated_joining, "run_invite_path_rm_triage"
            ) as triage,
            patch.object(coordinated_joining, "wait_for_case_participants"),
            patch_chain_shared(
                coordinated_joining, "wait_for_case_on_container"
            ),
            no_banners(),
        ):
            rcvcv_story.c2_suggests_the_vendor_deployer(state)

        assert (
            triage.call_args.kwargs["auth_client"] is state.case_actor_client
        )
        assert triage.call_args.kwargs["invited_client"] is state.client(
            rcvcv_story.V2
        )


# ---------------------------------------------------------------------------
# The replica drain and the five-replica sync phase (DEMOMA-23-005, #3906)
# ---------------------------------------------------------------------------


class TestReplicasDrainBeforeTheSecondCoordinator:
    """The opening's drain goes through the one shared coverage helper.

    It was the last private copy of the
    read-authority-tail-then-poll-each-replica loop outside
    ``vultron/demo/helpers/sync/`` (#3906), and it inherits the helper's
    behaviour when the authority holds no entries: one recorded gate failure
    naming the authority (EDF-06-005), where the private drain returned
    silently.
    """

    def test_the_drain_names_c1_as_authority_and_the_openings_replicas(self):
        """Only the Reporter and V1 hold a replica before C2 joins."""
        state = five_party_state()

        with patch.object(
            rcvcv_story, "wait_for_replica_ledger_coverage"
        ) as coverage:
            rcvcv_story.replicas_drain_before_the_second_coordinator(state)

        coverage.assert_called_once()
        kwargs = coverage.call_args.kwargs
        assert kwargs["auth_client"] is state.client(rcvcv_story.C1)
        assert kwargs["replicas"] == [
            (state.client(REPORTER), "Reporter"),
            (state.client(rcvcv_story.V1), "V1"),
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
        import vultron.demo.helpers.sync.ledger as sync_ledger

        state = five_party_state()
        state.client(rcvcv_story.C1).base_url = "http://c1.test/api/v2"

        with (
            patch.object(
                sync_ledger, "_get_log_entries_for_case", return_value=[]
            ),
            patch.object(
                sync_ledger, "wait_for_contiguous_ledger_coverage"
            ) as per_replica,
        ):
            rcvcv_story.replicas_drain_before_the_second_coordinator(state)

        per_replica.assert_not_called()
        (failure,) = _demo_failures
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
        state = five_party_state()

        with patch.object(rcvcv_story, "run_sync_verification_phase") as phase:
            rcvcv_story.every_replica_converges(state)

        kwargs = phase.call_args.kwargs
        assert kwargs["auth_client"] is state.client(rcvcv_story.C1)
        assert kwargs["auth_label"] == "C1"
        assert kwargs["auth_actor_id"] == state.actor_id(rcvcv_story.C1)
        assert kwargs["reporter_client"] is state.client(REPORTER)
        assert kwargs["replicas"] == [
            (state.client(REPORTER), "Reporter"),
            (state.client(rcvcv_story.V1), "V1"),
            (state.client(rcvcv_story.C2), "C2"),
            (state.client(rcvcv_story.V2), "V2"),
        ]
        assert kwargs["expected_participant_ids"] == {
            state.actor_id(who) for who in CAST
        }
        # V2 joined after the opening completed, so it catches up from genesis
        # and gets the late-joiner budget (#2852).
        assert kwargs["late_joiners"] == (state.client(rcvcv_story.V2),)
        assert kwargs["state_checks"] == [
            (state.client(REPORTER), "Reporter"),
            (state.client(rcvcv_story.V2), "V2"),
        ]


class TestRequiredParticipantsArePresent:
    """M1 is re-run once C2 has joined, from C1's replica."""

    @pytest.mark.spec("VP-02-015")
    def test_the_milestone_reads_c1s_replica_and_the_reporters(self):
        """M1 is read from the Case Owner's replica, not the canonical case."""
        state = five_party_state()

        with (
            patch.object(rcvcv_story, "verify_case_active") as milestone,
            no_banners(),
        ):
            rcvcv_story.required_participants_are_present(state)

        kwargs = milestone.call_args.kwargs
        assert kwargs["receiver_client"] is state.client(rcvcv_story.C1)
        assert kwargs["reporter_client"] is state.client(REPORTER)
        assert kwargs["case_id"] == state.case.id_
        assert kwargs["receiver_actor_id"] == state.actor_id(rcvcv_story.C1)
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
        state = five_party_state()
        answer = self._answer()
        state.keep(TIMELINE_ANSWER, answer)

        with patch.object(rcvcv_story, "add_note_thread") as thread:
            rcvcv_story.the_joiners_add_their_notes(state)

        watching_client, case, posts = thread.call_args.args
        assert watching_client is state.client(rcvcv_story.C1)
        assert case is state.case
        assert thread.call_args.kwargs["in_reply_to"] is answer
        # Each joiner posts from its own container.
        assert [post.poster.client for post in posts] == [
            state.client(rcvcv_story.C2),
            state.client(rcvcv_story.V2),
        ]
        assert [post.poster.actor for post in posts] == [
            state.actor(rcvcv_story.C2).actor,
            state.actor(rcvcv_story.V2).actor,
        ]

    def test_an_unanswered_thread_stops_the_story_instead_of_posting(self):
        """A fragment reads a prop through an accessor that raises.

        The opening keeps nothing when its own thread failed, so this
        fragment stops the story rather than opening a thread of its own
        (``run_story`` records it under the first failure).
        """
        state = five_party_state()

        with (
            patch.object(rcvcv_story, "add_note_thread") as thread,
            pytest.raises(DemoStoryError, match="answered timeline note"),
        ):
            rcvcv_story.the_joiners_add_their_notes(state)

        thread.assert_not_called()


# ---------------------------------------------------------------------------
# The fix lifecycle: V1 → VFd, V2 → VFD (DEMOMA-19-004/015/016/026/028/029)
# ---------------------------------------------------------------------------


@pytest.mark.spec("DEMOMA-19-004")
@pytest.mark.spec("DEMOMA-19-015")
@pytest.mark.spec("DEMOMA-19-016")
@pytest.mark.spec("DEMOMA-19-026", "DEMOMA-19-028", "DEMOMA-19-029")
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
        resolves its polls in ``coordinated_story.continuations``; the
        coordinator-side
        milestones this scenario batches over both vendors resolve theirs
        here.  Both modules are patched, because a patch on one alone would
        leave the other polling a stand-in client.
        """
        order = [] if order is None else order
        with (
            patch.object(
                coordinated_continuations,
                "wait_for_participant_rm_state",
                side_effect=rm_wait or (lambda **_kw: order.append("rm_wait")),
            ),
            patch.object(
                coordinated_continuations, "wait_for_participant_vf_state"
            ),
            patch.object(rcvcv_story, "wait_for_participant_vf_state"),
            patch.object(rcvcv_story, "wait_for_participant_d_state"),
            patch.object(rcvcv_story, "verify_fix_ready") as fix_ready,
            patch.object(rcvcv_story, "verify_fix_deployed") as fix_deployed,
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
            no_banners(),
        ):
            rcvcv_story.both_vendors_run_the_fix_lifecycle(state)
        return {
            "order": order,
            "fix_ready": fix_ready,
            "fix_deployed": fix_deployed,
            "notify_ready": notify_ready,
            "notify_deployed": notify_deployed,
        }

    def test_both_vendors_report_fix_ready_and_only_v2_deploys(self):
        """Each vendor runs the lifecycle its role set allows."""
        state = five_party_state()
        ran = self._run(state)

        assert sessions_of(ran["notify_ready"]) == [
            state.actor_id(rcvcv_story.V1),
            state.actor_id(rcvcv_story.V2),
        ]
        assert sessions_of(ran["notify_deployed"]) == [
            state.actor_id(rcvcv_story.V2)
        ], "V1 holds no DEPLOYER role, so it must never deploy (CSB-15-002)"

    def test_the_deploy_report_follows_both_fix_ready_reports(self):
        """V2's d→D step comes after the VFd pair, not between them."""
        state = five_party_state()
        order = self._run(state)["order"]

        ready = [i for i, step in enumerate(order) if step.startswith("ready")]
        deployed = [
            i for i, step in enumerate(order) if step.startswith("deployed")
        ]
        assert ready and deployed, order
        assert max(ready) < min(deployed), order

    def test_neither_verification_is_called_with_the_wrong_role(self):
        """DEMOMA-19-016 and DEMOMA-19-029, stated as the two sets of actor ids."""
        state = five_party_state()
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
            state.actor_id(rcvcv_story.V1),
            state.actor_id(rcvcv_story.V2),
        }
        assert deployed_actors == {state.actor_id(rcvcv_story.V2)}
        assert state.actor_id(rcvcv_story.V1) not in deployed_actors, (
            "verify_fix_deployed must not be called with a VENDOR-only actor"
        )

    def test_each_vendor_is_gated_on_its_own_rm_state(self):
        """CSB-18-001: notify-fix-ready needs RM out of triage first."""
        state = five_party_state()
        order: list[str] = []
        rm_calls: list[dict] = []

        def _rm_wait(**kwargs):
            rm_calls.append(kwargs)
            order.append(f"rm_wait:{kwargs['actor_id']}")

        self._run(state, order=order, rm_wait=_rm_wait)

        assert [c["actor_id"] for c in rm_calls] == [
            state.actor_id(rcvcv_story.V1),
            state.actor_id(rcvcv_story.V2),
        ]
        assert all(
            c["expected_states"] == {RM.ACCEPTED, RM.DEFERRED, RM.CLOSED}
            for c in rm_calls
        ), rm_calls
        for name in (rcvcv_story.V1, rcvcv_story.V2):
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
        state = five_party_state()

        with (
            patch.object(
                coordinated_continuations, "wait_for_participant_rm_state"
            ),
            patch.object(
                coordinated_continuations, "wait_for_participant_vf_state"
            ),
            patch.object(
                rcvcv_story, "wait_for_participant_vf_state"
            ) as vf_wait,
            patch.object(
                rcvcv_story, "wait_for_participant_d_state"
            ) as d_wait,
            patch.object(rcvcv_story, "verify_fix_ready"),
            patch.object(rcvcv_story, "verify_fix_deployed"),
            patch.object(ActorSession, "notify_fix_ready"),
            patch.object(ActorSession, "notify_fix_deployed"),
            no_banners(),
        ):
            rcvcv_story.both_vendors_run_the_fix_lifecycle(state)

        watched_vf = {
            (c.kwargs["client"], c.kwargs["actor_id"])
            for c in vf_wait.call_args_list
        }
        for watcher in (rcvcv_story.C1, REPORTER):
            for name in (rcvcv_story.V1, rcvcv_story.V2):
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
        for watcher in (rcvcv_story.C1, REPORTER):
            assert (
                state.client(watcher),
                state.actor_id(rcvcv_story.V2),
            ) in watched_d
        assert all(
            c.kwargs["expected_states"] == {CS_d.D}
            for c in d_wait.call_args_list
        ), "only V2 reaches d→D; V1 has no deploy step"
        assert not [
            c
            for c in d_wait.call_args_list
            if c.kwargs["actor_id"] == state.actor_id(rcvcv_story.V1)
        ], "V1's d state is never waited on: it has no DEPLOYER role"


# ---------------------------------------------------------------------------
# Publication order and the embargo teardown (DEMOMA-19-005, DEMOMA-19-027)
# ---------------------------------------------------------------------------


@pytest.mark.spec("DEMOMA-19-005", "DEMOMA-19-027")
class TestV1PublishesThenTheOthers:
    """V1 publishes first and the teardown is awaited before V2 does.

    V1 publishing first tests a teardown started by a VENDOR participant that
    is not the Case Owner (RSH-03-002).  If V2 published before the teardown
    committed the two publications would race and the ledger order would
    change from run to run.
    """

    def _run(self, state):
        order: list[str] = []

        def name_of(client: object) -> str:
            return devlogs_name_of(state, client, demo.DEVLOG_REPLICAS)

        with (
            patch.object(
                rcvcv_story,
                "wait_for_case_em_terminated",
                side_effect=lambda client, case_id: order.append(
                    f"em_exited:{name_of(client)}"
                ),
            ),
            patch.object(rcvcv_story, "wait_for_participant_vf_state"),
            patch.object(rcvcv_story, "wait_for_participant_d_state"),
            patch.object(
                rcvcv_story, "verify_publicly_disclosed"
            ) as disclosed,
            patch.object(
                ActorSession,
                "notify_published",
                autospec=True,
                side_effect=lambda session: order.append(
                    f"published:{session.actor.id_}"
                ),
            ),
            no_banners(),
        ):
            rcvcv_story.v1_publishes_then_the_others(state)
        return order, disclosed

    def test_v1_publishes_first_with_the_teardown_awaited_before_v2(self):
        """The whole publication order, so a reordering shows as a diff."""
        state = five_party_state()
        order, _ = self._run(state)

        assert order == [
            f"published:{state.actor_id(rcvcv_story.V1)}",
            "em_exited:v1",
            f"published:{state.actor_id(rcvcv_story.V2)}",
            f"published:{state.actor_id(rcvcv_story.C2)}",
            f"published:{state.actor_id(rcvcv_story.C1)}",
            "em_exited:reporter",
            f"published:{state.actor_id(REPORTER)}",
            "em_exited:reporter",
        ], order

    def test_the_closing_milestone_reads_v1_at_vf_and_v2_at_d(self):
        """M7 confirms the two vendors ended on their own paths."""
        state = five_party_state()

        with (
            patch.object(rcvcv_story, "wait_for_case_em_terminated"),
            patch.object(
                rcvcv_story, "wait_for_participant_vf_state"
            ) as vf_wait,
            patch.object(
                rcvcv_story, "wait_for_participant_d_state"
            ) as d_wait,
            patch.object(
                rcvcv_story, "verify_publicly_disclosed"
            ) as disclosed,
            patch.object(ActorSession, "notify_published"),
            no_banners(),
        ):
            rcvcv_story.v1_publishes_then_the_others(state)

        assert vf_wait.call_args.kwargs["client"] is state.client(
            rcvcv_story.C1
        )
        assert vf_wait.call_args.kwargs["actor_id"] == state.actor_id(
            rcvcv_story.V1
        )
        assert vf_wait.call_args.kwargs["expected_states"] == {CS_vf.VF}
        assert d_wait.call_args.kwargs["actor_id"] == state.actor_id(
            rcvcv_story.V2
        )
        assert d_wait.call_args.kwargs["expected_states"] == {CS_d.D}
        assert disclosed.call_args.kwargs["receiver_client"] is state.client(
            rcvcv_story.C1
        )
        assert disclosed.call_args.kwargs[
            "receiver_actor_id"
        ] == state.actor_id(rcvcv_story.C1)


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
        state = five_party_state()

        with (
            patch.object(ActorSession, "leave_case"),
            stub_closure_gate(),
            patch.object(
                coordinated_continuations, "close_case_owner_last"
            ) as closure,
        ):
            rcvcv_story.all_five_close_the_case(state)

        kwargs = closure.call_args.kwargs
        assert kwargs["milestone"] == "M8"
        assert kwargs["authority_client"] is state.case_actor_client
        assert [leaver.client for leaver in kwargs["others"]] == [
            state.client(rcvcv_story.V1),
            state.client(rcvcv_story.V2),
            state.client(rcvcv_story.C2),
            state.client(REPORTER),
        ]
        assert kwargs["owner"].client is state.client(rcvcv_story.C1)
        assert kwargs["owner"].actor is state.actor(rcvcv_story.C1).actor
