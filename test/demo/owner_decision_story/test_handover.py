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

"""Tests of :mod:`vultron.demo.helpers.owner_decision_story.handover`: ``owner-keep-case:offer-ownership``."""

import contextlib
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

from test.demo._helpers import (
    mock_case,
    patch_chain_shared,
)
from test.demo.owner_decision_story._support import (
    JOINED,
    JOINER,
    NEWCOMER,
    OWNER,
    SEATED,
    continuation_state,
    gate_failures,
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
from vultron.demo.helpers.owner_decision_story import (
    HANDED_OVER_CASE,
    Part,
    handover as owner_handover,
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
        owner_parts
        if name == "find_case_actor_participant_id"
        else owner_handover
    )


@pytest.mark.spec("DEMOMA-14-004", "DEMOMA-14-020")
class TestTheOwnerHandsTheCaseOver:
    """The owner offers, the new owner accepts, the CASE_MANAGER commits."""

    def _hand_over(self, state, *, order=None, restated=None, **overrides):
        """Run the continuation with every collaborator stubbed out."""
        order = [] if order is None else order
        patches = {
            "find_ownership_transfer_offer_for_actor": {
                "return_value": "urn:test:ownership-offer"
            },
            "wait_for_case_actor_ledger_event": {
                "side_effect": lambda **_kw: order.append("commit")
            },
            "wait_for_case_attributed_to": {},
            "wait_for_semantic_type_in_ledger": {},
        }
        patches.update(overrides)
        with contextlib.ExitStack() as stack:
            mocks = {
                name: stack.enter_context(
                    patch.object(_resolving(name), name, **kwargs)
                )
                for name, kwargs in patches.items()
            }
            # The re-read case must be the case the story opened: nothing a
            # scenario does changes a case's id (CM-21-002).
            wire_case = stack.enter_context(
                patch.object(owner_handover, "as_VulnerabilityCase")
            )
            wire_case.model_validate.return_value = (
                mock_case(state.case.id_) if restated is None else restated
            )
            mocks["as_VulnerabilityCase"] = wire_case
            mocks["offer"] = stack.enter_context(
                patch.object(
                    ActorSession,
                    "offer_case_ownership_transfer",
                    autospec=True,
                    side_effect=lambda *_a, **_kw: (
                        order.append("offer") or MagicMock()
                    ),
                )
            )
            mocks["accept"] = stack.enter_context(
                patch.object(
                    ActorSession,
                    "accept_case_ownership_transfer",
                    autospec=True,
                    side_effect=lambda *_a, **_kw: (
                        order.append("accept") or MagicMock()
                    ),
                )
            )
            ods.the_owner_hands_the_case_over(
                state, joined=JOINED, owner=OWNER, new_owner=JOINER
            )
        mocks["order"] = order
        return mocks

    def test_the_transfer_offers_accepts_then_waits_for_the_commit(self):
        """TRIG-11-001, TRIG-11-002, then the CASE_MANAGER's own entry."""
        state = continuation_state()
        with no_banners():
            ran = self._hand_over(state)

        assert ran["order"] == ["offer", "accept", "commit"]

        # The proposal is the old owner's and names the new owner.
        assert (
            ran["offer"].call_args.args[0].actor
            is state.actor(OWNER.name).actor
        )
        assert ran["offer"].call_args.kwargs[
            "transferee_id"
        ] == state.actor_id(JOINER.name)
        assert JOINER.label in ran["offer"].call_args.kwargs["content"]

        # The CaseActor's own Offer is polled for on the new owner's replica,
        # under an id of the CaseActor's (CM-21-028, ADR-0148).
        lookup = ran[
            "find_ownership_transfer_offer_for_actor"
        ].call_args.kwargs
        assert lookup["client"] is state.client(JOINER.name)
        assert lookup["transferee_id"] == state.actor_id(JOINER.name)

        # The accept is the new owner's, on its own container.
        assert (
            ran["accept"].call_args.args[0].actor
            is state.actor(JOINER.name).actor
        )
        assert ran["accept"].call_args.kwargs == {
            "offer_id": "urn:test:ownership-offer"
        }

    @pytest.mark.spec("CM-21-007")
    def test_the_commit_is_read_on_the_case_actors_own_store(self):
        """#3602: a slow fan-out must not read as a transfer that never was."""
        state = continuation_state()
        with no_banners():
            ran = self._hand_over(state)

        kwargs = ran["wait_for_case_actor_ledger_event"].call_args.kwargs
        assert kwargs["client"] is state.case_actor_client
        assert kwargs["semantic_type"] == "update_case_owner"

    @pytest.mark.spec("DEMOMA-14-011")
    def test_both_owners_replicas_and_the_witness_are_checked(self):
        """Old owner, new owner, and a participant that is neither."""
        state = continuation_state()
        with no_banners():
            ran = self._hand_over(state)

        watched = [
            (c.kwargs["client"], c.kwargs["expected_attributed_to"])
            for c in ran["wait_for_case_attributed_to"].call_args_list
        ]
        assert watched == [
            (state.client(OWNER.name), state.actor_id(JOINER.name)),
            (state.client(JOINER.name), state.actor_id(JOINER.name)),
        ]
        # ADR-0053's own criterion: an actor outside the negotiation holds the
        # entry only if the CaseActor fanned it out to every participant.
        witness = ran["wait_for_semantic_type_in_ledger"].call_args.kwargs
        assert witness["client"] is state.client(REPORTER)
        assert witness["semantic_type"] == "accept_case_ownership_transfer"

    def test_the_witness_may_be_named_rather_than_defaulted(self):
        """A pair whose Reporter is not the odd one out can say so."""
        state = continuation_state()

        with (
            no_banners(),
            patch.object(
                owner_handover,
                "find_ownership_transfer_offer_for_actor",
                return_value="urn:test:ownership-offer",
            ),
            patch.object(owner_handover, "wait_for_case_actor_ledger_event"),
            patch.object(owner_handover, "wait_for_case_attributed_to"),
            patch.object(
                owner_handover, "wait_for_semantic_type_in_ledger"
            ) as witness_wait,
            patch.object(owner_handover, "as_VulnerabilityCase") as wire_case,
            patch.object(ActorSession, "offer_case_ownership_transfer"),
            patch.object(ActorSession, "accept_case_ownership_transfer"),
        ):
            wire_case.model_validate.return_value = mock_case(state.case.id_)
            ods.the_owner_hands_the_case_over(
                state,
                joined=JOINED,
                owner=OWNER,
                new_owner=JOINER,
                witness=NEWCOMER,
            )

        assert witness_wait.call_args.kwargs["client"] is state.client(
            NEWCOMER.name
        )

    def test_the_restate_and_the_prop_sit_inside_the_commit_gate(self):
        """A transfer the CASE_MANAGER never committed keeps nothing.

        The real ``demo_gate`` runs: the commit wait fails, so the restate and
        the prop are skipped and the fragment that invites next stops the story
        (DEMOCI-01-011).
        """
        state = continuation_state()
        ran = self._hand_over(
            state,
            wait_for_case_actor_ledger_event={
                "side_effect": AssertionError(
                    "timed out polling for update_case_owner"
                )
            },
        )

        ran["as_VulnerabilityCase"].model_validate.assert_not_called()
        ran["wait_for_case_attributed_to"].assert_not_called()
        with pytest.raises(DemoStoryError, match="handed over"):
            state.kept(HANDED_OVER_CASE)
        assert len(gate_failures()) == 1, _demo_failures

    def test_a_completed_transfer_restates_the_case_and_keeps_the_prop(self):
        """The case is re-read as the old owner now stores it (CM-21-002)."""
        state = continuation_state()
        restated = mock_case(state.case.id_)
        with no_banners():
            self._hand_over(state, restated=restated)

        assert state.case is restated
        assert state.kept(HANDED_OVER_CASE) == str(restated.id_)

    @pytest.mark.spec("CM-21-002")
    def test_a_re_read_naming_a_different_case_is_refused(self):
        """A mis-assembled restate would follow the wrong ledger (#5535).

        An ownership transfer moves ``attributed_to`` and leaves the id alone,
        so a different id means the fragment read the wrong record; the armed
        ledger dump still belongs to the first case.  ``restate_case`` refuses
        it, and the commit gate records the refusal rather than letting the
        story carry on against a case it is not dumping.
        """
        state = continuation_state()
        ran = self._hand_over(state, restated=mock_case("urn:test:other-case"))

        assert state.case.id_ == "urn:test:case"
        with pytest.raises(DemoStoryError, match="handed over"):
            state.kept(HANDED_OVER_CASE)
        assert any(
            "GATE FAILED" in f and "restate" in f
            for f in _demo_failures
        ), _demo_failures
        assert ran["wait_for_case_attributed_to"].called

    def test_the_accept_is_skipped_when_the_case_actors_offer_never_arrives(
        self,
    ):
        """#3038: the accept nests inside the delivery gate."""
        state = continuation_state()
        ran = self._hand_over(
            state,
            find_ownership_transfer_offer_for_actor={
                "side_effect": AssertionError(
                    "timed out polling for Offer(VulnerabilityCase)"
                )
            },
        )

        ran["accept"].assert_not_called()

    def test_a_failed_offer_trigger_skips_the_lookup_and_the_accept(self):
        """The delivery gate nests inside the offer step (DEMOCI-01-003)."""
        state = continuation_state()
        order: list[str] = []

        with contextlib.ExitStack() as stack:
            lookup = stack.enter_context(
                patch.object(
                    owner_handover,
                    "find_ownership_transfer_offer_for_actor",
                    return_value="urn:test:ownership-offer",
                )
            )
            for name in (
                "wait_for_case_actor_ledger_event",
                "wait_for_case_attributed_to",
                "wait_for_semantic_type_in_ledger",
            ):
                stack.enter_context(patch.object(_resolving(name), name))
            wire_case = stack.enter_context(
                patch.object(owner_handover, "as_VulnerabilityCase")
            )
            wire_case.model_validate.return_value = mock_case(state.case.id_)
            stack.enter_context(
                patch.object(
                    ActorSession,
                    "offer_case_ownership_transfer",
                    side_effect=RuntimeError("offer trigger failed"),
                )
            )
            accept = stack.enter_context(
                patch.object(
                    ActorSession,
                    "accept_case_ownership_transfer",
                    side_effect=lambda **_kw: order.append("accept"),
                )
            )
            ods.the_owner_hands_the_case_over(
                state, joined=JOINED, owner=OWNER, new_owner=JOINER
            )

        lookup.assert_not_called()
        accept.assert_not_called()
        assert order == []


class TestTheNewOwnerInvites:
    """Only the Case Owner may invite, and the CaseActor emits the Invite."""

    def _invite(self, state, *, order=None, **overrides):
        """Run the continuation with every collaborator stubbed out."""
        order = [] if order is None else order
        patches = {
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
            mocks["replica_wait"] = stack.enter_context(
                patch_chain_shared(
                    coordinated_joining, "wait_for_case_on_container"
                )
            )
            ods.the_new_owner_invites(
                state,
                new_owner=JOINER,
                invitee=NEWCOMER,
                role=CVDRole.VENDOR,
                seated=SEATED,
            )
        mocks["order"] = order
        return mocks

    @pytest.mark.spec("DEMOCI-01-011")
    def test_an_uncommitted_handover_stops_the_story(self):
        """Inviting into a case the would-be owner does not own is refused.

        A flat story cannot nest the invite inside the commit's gate, so the
        prop is the dependency: ``kept`` raises and ``run_story`` records the
        earlier failure as the headline.
        """
        state = continuation_state()

        with (
            patch.object(owner_handover, "run_case_invite_chain") as chain,
            patch.object(owner_parts, "find_case_actor_participant_id"),
            pytest.raises(DemoStoryError, match="handed over"),
        ):
            ods.the_new_owner_invites(
                state,
                new_owner=JOINER,
                invitee=NEWCOMER,
                role=CVDRole.VENDOR,
                seated=SEATED,
            )

        chain.assert_not_called()

    @pytest.mark.spec("DEMOMA-22-002")
    def test_the_invite_is_triggered_on_the_new_owners_own_container(self):
        """#2178: a trigger posted to the old owner's client 404s.

        A trigger URL is built from the named actor's bare id against the
        client's base URL, so the inviter must carry the new owner's *own*
        client and actor.
        """
        state = continuation_state()
        state.keep(HANDED_OVER_CASE, str(state.case.id_))
        with no_banners():
            ran = self._invite(state)

        inviter = ran["run_case_invite_chain"].call_args.kwargs["inviter"]
        assert inviter.client is state.client(JOINER.name)
        assert inviter.actor is state.actor(JOINER.name).actor
        assert inviter.name == JOINER.label
        assert inviter.role is CVDRole.VENDOR
        assert inviter.client is not state.client(OWNER.name)

    @pytest.mark.spec("PCR-08-008")
    def test_the_delivered_invite_must_have_been_emitted_as_the_case_actor(
        self,
    ):
        """An Invite sent by a participant routes the Accept to the wrong one.

        The CaseActor's id comes off the case (CM-17-007), so the check names
        the actor actually holding CASE_MANAGER rather than a literal.
        """
        state = continuation_state()
        state.keep(HANDED_OVER_CASE, str(state.case.id_))
        with no_banners():
            ran = self._invite(state)

        kwargs = ran["run_case_invite_chain"].call_args.kwargs
        emitted_by = kwargs["expect_emitted_by"]
        assert emitted_by.case_actor_id == "urn:test:case-actor-participant"
        assert NEWCOMER.label in emitted_by.consequence
        assert "AcceptInviteActorToCaseBT" in emitted_by.consequence
        # The CASE_MANAGER's store is on the dedicated container, so the chain
        # seeds the stub summary there (DEMOMA-06-005, CM-17-010).
        assert kwargs["case_manager_client"] is state.case_actor_client
        # The id is read off the new owner's replica of the case.
        assert ran["find_case_actor_participant_id"].call_args.args == (
            state.client(JOINER.name),
            state.case.id_,
        )

    def test_the_newcomers_triage_reads_the_new_owners_roster(self):
        """The roster is the Case Owner's, which the handover moved."""
        state = continuation_state()
        state.keep(HANDED_OVER_CASE, str(state.case.id_))
        with no_banners():
            ran = self._invite(state)

        assert ran["order"] == ["invite-chain", "triage"]
        kwargs = ran["invitee_triages_after_joining"].call_args.kwargs
        assert kwargs["owner"] == JOINER.name
        assert kwargs["owner_label"] == JOINER.label
        assert kwargs["seated"] == SEATED

    @pytest.mark.spec("CLP-08-005")
    def test_the_reporter_holds_the_case_before_the_newcomer_triages(self):
        """The join broadcasts to every participant (Bug #2135)."""
        state = continuation_state()
        state.keep(HANDED_OVER_CASE, str(state.case.id_))
        with no_banners():
            ran = self._invite(state)

        assert [
            c.kwargs["client"] for c in ran["replica_wait"].call_args_list
        ] == [state.client(REPORTER)]

    def test_a_missing_case_actor_participant_skips_the_chain(self):
        """PCR-08-008 cannot be checked, so the invite does not go out."""
        state = continuation_state()
        state.keep(HANDED_OVER_CASE, str(state.case.id_))
        ran = self._invite(
            state, find_case_actor_participant_id={"return_value": None}
        )

        ran["run_case_invite_chain"].assert_not_called()
        assert any(
            "GATE FAILED" in f and "no CaseActor participant" in f
            for f in _demo_failures
        ), _demo_failures


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

    def test_the_case_is_not_offered_without_the_join(self):
        """The transferee must be an active participant (DEMOMA-14-010)."""
        state = continuation_state(joined=False)

        with (
            patch.object(
                ActorSession, "offer_case_ownership_transfer"
            ) as offer,
            no_banners(),
            pytest.raises(DemoStoryError, match="test pair's join"),
        ):
            ods.the_owner_hands_the_case_over(
                state, joined=JOINED, owner=OWNER, new_owner=JOINER
            )

        offer.assert_not_called()


@pytest.mark.spec("CM-21-007")
class TestTheWitnessIsNotAPartyToTheTransfer:
    """ADR-0053's criterion is about an actor outside the negotiation.

    Both parties see the new owner through the offer/accept round-trip, so
    reading the ledger entry on either one's replica proves nothing about the
    CM-21-030 broadcast. The helper refuses the pairing rather than leaving it
    to the ratchet, which reads call sites lexically and cannot see a `Part`
    passed in by a caller.
    """

    @pytest.mark.parametrize(
        "witness", [OWNER, JOINER], ids=["old-owner", "new-owner"]
    )
    def test_a_party_named_as_the_witness_is_refused(self, witness: Part):
        state = continuation_state()

        with (
            patch.object(
                ActorSession, "offer_case_ownership_transfer"
            ) as offer,
            no_banners(),
            pytest.raises(DemoStoryError, match="party to the transfer"),
        ):
            ods.the_owner_hands_the_case_over(
                state,
                joined=JOINED,
                owner=OWNER,
                new_owner=JOINER,
                witness=witness,
            )

        offer.assert_not_called()
