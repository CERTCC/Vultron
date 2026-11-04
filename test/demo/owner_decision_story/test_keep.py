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

"""Tests of :mod:`vultron.demo.helpers.owner_decision_story.keep`: ``owner-keep-case:keep``."""

import contextlib
from types import ModuleType
from unittest.mock import patch

import pytest

from test.demo._helpers import (
    gate_failures,
    patch_chain_shared,
)
from test.demo.owner_decision_story._support import (
    JOINED,
    JOINER,
    NEWCOMER,
    OWNER,
    SEATED,
    continuation_state,
    no_banners,
)
from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers import (
    owner_decision_story as ods,
)
from vultron.demo.helpers.coordinated_story import (
    REPORTER,
    joining as coordinated_joining,
)
from vultron.demo.helpers.invite_chain import links as invite_links
from vultron.demo.helpers.owner_decision_story import (
    keep as owner_keep,
    parts as owner_parts,
)
from vultron.demo.utils.failures import _demo_failures
from vultron.enums.roles import CVDRole
from vultron.errors import DemoStoryError

#: Clear the process-global failure accumulator around every test.
pytestmark = pytest.mark.usefixtures("fresh_demo_failures")


def _resolving(name: str) -> ModuleType:
    """The submodule whose functions look *name* up.

    The CaseActor lookup both continuations make is in ``parts``; every
    other collaborator is looked up by this continuation's own submodule.
    """
    return (
        owner_parts if name == "find_case_actor_participant_id" else owner_keep
    )


# ---------------------------------------------------------------------------
# owner-keep-case:keep (ADR-0026, DEMOMA-13-004/005)
# ---------------------------------------------------------------------------


@pytest.mark.spec("DEMOMA-13-004")
@pytest.mark.spec("DEMOMA-13-005", "DEMOMA-13-016", "DEMOMA-13-017")
class TestTheOwnerApprovesASuggestedActor:
    """The joiner suggests, the owner approves, the CaseActor invites."""

    def _approve(self, state, *, order=None, **overrides):
        """Run the continuation with every collaborator stubbed out.

        *overrides* replaces a patch's keyword arguments, which is how a test
        makes one link of the chain fail.
        """
        order = [] if order is None else order
        patches = {
            "find_cp_offer_for_case": {"return_value": "urn:test:cp-offer"},
            "find_case_actor_participant_id": {
                "return_value": "urn:test:case-actor-participant"
            },
            "run_case_invite_chain": {
                "side_effect": lambda **_kw: order.append("invite-chain")
            },
            "invitee_triages_after_joining": {
                "side_effect": lambda *_a, **_kw: order.append("triage")
            },
        }
        patches.update(overrides)
        with contextlib.ExitStack() as stack:
            mocks = {
                name: stack.enter_context(
                    patch.object(_resolving(name), name, **kwargs)
                )
                for name, kwargs in patches.items()
            }
            mocks["suggest"] = stack.enter_context(
                patch.object(
                    ActorSession,
                    "suggest_actor_to_case",
                    autospec=True,
                    side_effect=lambda *_a, **_kw: order.append("suggest"),
                )
            )
            mocks["approve"] = stack.enter_context(
                patch.object(
                    ActorSession,
                    "accept_actor_recommendation",
                    autospec=True,
                    side_effect=lambda *_a, **_kw: order.append("approve"),
                )
            )
            mocks["replica_wait"] = stack.enter_context(
                patch_chain_shared(
                    coordinated_joining, "wait_for_case_on_container"
                )
            )
            ods.the_owner_approves_a_suggested_actor(
                state,
                joined=JOINED,
                owner=OWNER,
                suggester=JOINER,
                newcomer=NEWCOMER,
                roles=[CVDRole.VENDOR, CVDRole.DEPLOYER],
                seated=SEATED,
            )
        mocks["order"] = order
        return mocks

    def test_the_flow_runs_suggest_approve_invite_then_triage(self):
        """One ordered pass of ADR-0026, each act from its own container."""
        state = continuation_state()
        with no_banners():
            ran = self._approve(state)

        assert ran["order"] == ["suggest", "approve", "invite-chain", "triage"]

        # The suggestion comes from the joiner and names the newcomer by actor
        # id, with its roles explicit so EvaluateDefaultRolesNode does not fall
        # back to the hardcoded [VENDOR] default (#1969).
        assert (
            ran["suggest"].call_args.args[0].actor
            is state.actor(JOINER.name).actor
        )
        assert ran["suggest"].call_args.kwargs == {
            "suggested_actor_id": state.actor_id(NEWCOMER.name),
            "roles": [CVDRole.VENDOR, CVDRole.DEPLOYER],
        }

        # The approval is the owner's, and routes back to the CaseActor.
        assert (
            ran["approve"].call_args.args[0].actor
            is state.actor(OWNER.name).actor
        )
        assert ran["approve"].call_args.kwargs == {
            "cp_offer_id": "urn:test:cp-offer",
            "case_actor_id": "urn:test:case-actor-participant",
        }
        # The forwarded recommendation is polled for on the owner's replica.
        assert ran["find_cp_offer_for_case"].call_args.kwargs[
            "client"
        ] is state.client(OWNER.name)

    def test_the_case_actor_invites_on_its_own_with_no_inviter(self):
        """ADR-0026: the Invite follows the approval, not a participant act."""
        state = continuation_state()
        with no_banners():
            ran = self._approve(state)

        kwargs = ran["run_case_invite_chain"].call_args.kwargs
        assert "inviter" not in kwargs, (
            "the CaseActor invites on the owner's approval, so the chain must"
            " be given no inviting participant (ADR-0026)"
        )
        # It reads the canonical ledger through the case-actor container, and
        # seeds nothing there: the stub summary is already seeded by then.
        assert kwargs["ledger_client"] is state.case_actor_client
        assert "case_manager_client" not in kwargs
        assert kwargs["invitee_client"] is state.client(NEWCOMER.name)
        assert kwargs["invitee"] is state.actor(NEWCOMER.name).actor
        assert kwargs["invitee_name"] == NEWCOMER.label

    def test_the_newcomers_triage_reads_the_owners_roster(self):
        """CM-11-002, from the Case Owner's replica, not the family default."""
        state = continuation_state()
        with no_banners():
            ran = self._approve(state)

        args = ran["invitee_triages_after_joining"].call_args.args
        kwargs = ran["invitee_triages_after_joining"].call_args.kwargs
        assert args[1:] == (NEWCOMER.name, NEWCOMER.label)
        assert kwargs["seated"] == SEATED
        assert kwargs["owner"] == OWNER.name
        assert kwargs["owner_label"] == OWNER.label

    @pytest.mark.spec("CLP-08-005")
    def test_the_reporter_holds_the_case_before_the_newcomers_triage(self):
        """Bug #2120: the newcomer's triage broadcasts to the Reporter too."""
        state = continuation_state()
        order: list[str] = []

        def _wait_for_case(client, case_id, **_kwargs):
            if client is state.client(REPORTER):
                order.append("reporter_wait")

        with contextlib.ExitStack() as stack:
            stack.enter_context(
                patch.object(
                    owner_keep,
                    "find_cp_offer_for_case",
                    return_value="urn:test:cp",
                )
            )
            stack.enter_context(
                patch.object(
                    owner_parts,
                    "find_case_actor_participant_id",
                    return_value="urn:test:case-actor-participant",
                )
            )
            stack.enter_context(
                patch.object(owner_keep, "run_case_invite_chain")
            )
            stack.enter_context(
                patch.object(ActorSession, "suggest_actor_to_case")
            )
            stack.enter_context(
                patch.object(ActorSession, "accept_actor_recommendation")
            )
            stack.enter_context(
                patch.object(
                    coordinated_joining,
                    "run_invite_path_rm_triage",
                    side_effect=lambda **_kw: order.append("triage"),
                )
            )
            stack.enter_context(
                patch.object(coordinated_joining, "wait_for_case_participants")
            )
            stack.enter_context(
                patch_chain_shared(
                    coordinated_joining,
                    "wait_for_case_on_container",
                    side_effect=_wait_for_case,
                )
            )
            stack.enter_context(no_banners())
            ods.the_owner_approves_a_suggested_actor(
                state,
                joined=JOINED,
                owner=OWNER,
                suggester=JOINER,
                newcomer=NEWCOMER,
                roles=[CVDRole.VENDOR],
                seated=SEATED,
            )

        assert "reporter_wait" in order, order
        assert "triage" in order, order
        assert order.index("reporter_wait") < order.index("triage"), order

    def test_the_approval_is_skipped_when_the_recommendation_never_arrives(
        self,
    ):
        """ADR-0058: the forwarded Offer is the approval's precondition.

        The real ``demo_gate`` runs, so a lookup timeout must record one
        failure and skip the approval rather than approving a ``None`` offer.
        """
        state = continuation_state()
        ran = self._approve(
            state,
            find_cp_offer_for_case={
                "side_effect": AssertionError(
                    "timed out polling for Offer(CaseParticipant)"
                )
            },
        )

        ran["approve"].assert_not_called()
        failures = gate_failures()
        assert len(failures) == 1, _demo_failures
        # The gate names the parts it was handed, not either pair's actors.
        assert NEWCOMER.label in failures[0]
        assert OWNER.label in failures[0]

    def _run_the_real_chain(self, state, *, invite_lookup):
        """Run the continuation with the **real** invite chain.

        Only the Invite lookup and the primitives the chain polls with are
        stubbed, so the accept and the replica wait are reached exactly as a
        run reaches them: by the CaseActor's Invite landing in the newcomer's
        own container (no inbox injection, DEMOMA-00-002).
        """
        with (
            patch.object(ActorSession, "suggest_actor_to_case"),
            patch.object(ActorSession, "accept_actor_recommendation"),
            patch.object(
                ActorSession, "accept_case_invite", autospec=True
            ) as accept,
            patch.object(
                owner_keep,
                "find_cp_offer_for_case",
                return_value="urn:test:cp-offer",
            ),
            patch.object(
                owner_parts,
                "find_case_actor_participant_id",
                return_value="urn:test:case-actor-participant",
            ),
            patch.object(
                invite_links, "find_case_invite_for_actor", **invite_lookup
            ) as find_invite,
            patch.object(owner_keep, "invitee_triages_after_joining"),
            patch_chain_shared(
                coordinated_joining, "wait_for_case_on_container"
            ) as replica_wait,
        ):
            ods.the_owner_approves_a_suggested_actor(
                state,
                joined=JOINED,
                owner=OWNER,
                suggester=JOINER,
                newcomer=NEWCOMER,
                roles=[CVDRole.VENDOR],
                seated=SEATED,
            )
        return find_invite, accept, replica_wait

    def test_the_newcomer_accepts_the_invite_the_case_actor_delivered(self):
        """The last hop: the Invite is found in the newcomer's own container.

        Polling only — the continuation never carries the Invite into an
        inbox, and the Accept is puppeteered from the newcomer's container.
        """
        state = continuation_state()
        find_invite, accept, replica_wait = self._run_the_real_chain(
            state, invite_lookup={"return_value": "urn:test:newcomer-invite"}
        )

        assert find_invite.call_args.kwargs["client"] is state.client(
            NEWCOMER.name
        )
        assert find_invite.call_args.kwargs["invitee_id"] == state.actor_id(
            NEWCOMER.name
        )
        accept.assert_called_once()
        assert accept.call_args.args[0].client is state.client(NEWCOMER.name)
        assert accept.call_args.kwargs == {
            "invite_id": "urn:test:newcomer-invite"
        }
        # The Accept seeds the newcomer's case replica, which the chain waits
        # for next.
        assert [
            c
            for c in replica_wait.call_args_list
            if c.kwargs.get("client") is state.client(NEWCOMER.name)
        ]

    def test_an_invite_that_never_arrived_is_never_answered(self):
        """#3038: the answer nests inside the Invite's delivery gate.

        The real ``demo_gate`` runs, so a delivery timeout must skip the
        Accept and the replica wait behind it rather than answering an Invite
        id that is ``None``.
        """
        state = continuation_state()
        _, accept, replica_wait = self._run_the_real_chain(
            state,
            invite_lookup={
                "side_effect": AssertionError("timed out polling for Invite")
            },
        )

        accept.assert_not_called()
        assert not [
            c
            for c in replica_wait.call_args_list
            if c.kwargs.get("client") is state.client(NEWCOMER.name)
        ], (
            "the newcomer's replica wait depends on the Accept, so the closed"
            f" gate must skip it: {replica_wait.call_args_list!r}"
        )

    def test_a_missing_case_actor_participant_is_recorded_not_raised(self):
        """The Accept has nowhere to route to, so the gate records it."""
        state = continuation_state()
        ran = self._approve(
            state, find_case_actor_participant_id={"return_value": None}
        )

        ran["approve"].assert_not_called()
        assert any(
            "GATE FAILED" in f and "no CaseActor participant" in f
            for f in _demo_failures
        ), _demo_failures


# ---------------------------------------------------------------------------
# owner-keep-case:offer-ownership (TRIG-11-001/002, DEMOMA-14-004/011/020)
# ---------------------------------------------------------------------------


@pytest.mark.spec("DEMOCI-01-011")
@pytest.mark.spec("DEMOMA-17-002")
class TestAJoinThatNeverLandedStopsTheStory:
    """Both continuations read the joiner's join before anything else.

    Before composition the owner's decision nested inside the roster's own
    ``demo_gate``, so a roster that never filled skipped it. A flat story
    cannot nest, so the gate keeps a prop and each continuation reads it
    first — and the reading raises, which is how ``run_story`` stops the
    story with the roster's failure as the headline (#5535).
    """

    def test_the_suggestion_is_not_made_without_the_join(self):
        """A non-participant may suggest nobody (DEMOMA-13-003)."""
        state = continuation_state(joined=False)

        with (
            patch.object(ActorSession, "suggest_actor_to_case") as suggest,
            no_banners(),
            pytest.raises(DemoStoryError, match="test pair's join"),
        ):
            ods.the_owner_approves_a_suggested_actor(
                state,
                joined=JOINED,
                owner=OWNER,
                suggester=JOINER,
                newcomer=NEWCOMER,
                roles=[CVDRole.VENDOR],
                seated=SEATED,
            )

        suggest.assert_not_called()
