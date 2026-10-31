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

"""Unit tests for the two ``owner-keep-case`` continuations (#5535).

``owner-keep-case`` is decided in both halves of the scenario tree, so each of
its continuations is written once in
:mod:`vultron.demo.helpers.owner_decision_story` and takes its cast as
:class:`~vultron.demo.helpers.owner_decision_story.Part`\\ s off the running
story (DEMOMA-17-001).  Every test here therefore drives the continuations
with a **neutral** cast — ``owner``, ``joiner``, ``newcomer`` — which is the
claim itself: a continuation that named either pair's actors could not be run
this way at all.

``demo_gate`` / ``demo_check`` / ``demo_step`` stay real wherever a test is
about a gate skipping its dependents, and are stubbed to ``nullcontext`` only
where it is about call shape (``test_demo_context_managers.py`` owns their
behaviour).
"""

import contextlib
from unittest.mock import MagicMock, patch

import pytest

import vultron.demo.utils as demo_utils
from test.demo._helpers import (
    mock_case,
    no_demo_banners,
    patch_chain_shared,
    story_state,
)
from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers import (
    coordinated_story,
    invite_chain,
    owner_decision_story as ods,
)
from vultron.demo.helpers.coordinated_story import REPORTER, REPORTER_LABEL
from vultron.demo.helpers.owner_decision_story import (
    HANDED_OVER_CASE,
    Part,
)
from vultron.demo.helpers.story import StoryProp
from vultron.demo.utils import reset_demo_failures
from vultron.enums.roles import CVDRole
from vultron.errors import DemoStoryError

#: A neutral cast, named for the part each plays rather than for either pair's
#: actors: the two-coordinator pair runs these continuations with C1, C2 and a
#: Vendor, the vendor-first pair with Vendor1, a Coordinator and Vendor2.
#: The join prop the pair's roster gate keeps and both continuations read:
#: each presupposes the joiner being an active participant (DEMOMA-13-003,
#: DEMOMA-14-010), so the module's state keeps it and two tests take it away.
JOINED: StoryProp[str] = StoryProp("test pair's join", str)

OWNER = Part("owner", "Owner")
JOINER = Part("joiner", "Joiner")
NEWCOMER = Part("newcomer", "Newcomer")

#: Every cast name a continuation of this module reaches.
_CAST = (REPORTER, OWNER.name, JOINER.name, NEWCOMER.name)

#: The roster both continuations gate their newcomer's triage on.
_SEATED = (REPORTER, OWNER.name, JOINER.name, NEWCOMER.name)


@pytest.fixture(autouse=True)
def _fresh_failures():
    """Clear the process-global failure accumulator around every test.

    ``vultron.demo.utils._demo_failures`` is process-global, and a gate skips
    its own body once anything is recorded, so a leftover failure changes what
    the next test observes (``notes/testing-pitfalls.md``).
    """
    reset_demo_failures()
    yield
    reset_demo_failures()


@contextlib.contextmanager
def _no_banners():
    """Every module a fragment of this scenario reaches, patched once."""
    with no_demo_banners(ods, coordinated_story):
        yield


def _state(joined: bool = True):
    """A story state seating the neutral cast, on an open case.

    The join prop both continuations read is kept by default, because every
    test but the two about its absence runs past that read.
    """
    state = story_state(*_CAST, case=mock_case())
    if joined:
        state.keep(JOINED, str(state.case.id_))
    return state


def _gate_failures() -> list[str]:
    """Every recorded gate failure, in order."""
    return [f for f in demo_utils._demo_failures if "GATE FAILED" in f]


# ---------------------------------------------------------------------------
# Part and the CaseActor's address
# ---------------------------------------------------------------------------


class TestPart:
    """A part is the story name of a cast member plus its scenario label."""

    def test_a_part_carries_the_cast_name_and_the_label(self):
        """The ``(state, name, label)`` pair, bundled (DEMOMA-17-001)."""
        assert (OWNER.name, OWNER.label) == ("owner", "Owner")

    def test_a_part_is_frozen(self):
        """A continuation cannot reseat the cast it was handed.

        Assigned through ``setattr`` under a variable name, because the field
        is read-only and both a direct assignment and a constant-named
        ``setattr`` are refused by the type checker and the linter before the
        test can run.
        """
        field = "name"
        with pytest.raises(AttributeError):
            setattr(OWNER, field, "someone-else")

    def test_the_reporter_is_the_default_witness_part(self):
        """Every scenario of the tree seats its Reporter under that name."""
        assert Part(REPORTER, REPORTER_LABEL) == ods.REPORTER_PART


class TestCaseActorParticipant:
    """The CASE_MANAGER's address is read off a replica, never assumed."""

    def test_the_id_comes_from_the_replica_it_is_handed(self):
        """So the check names the actor actually holding CASE_MANAGER.

        It takes the client and the case id rather than the story's state: it
        is a polling-style helper, not a fragment, and owns no demo context of
        its own.
        """
        state = _state()

        with patch.object(
            ods,
            "find_case_actor_participant_id",
            return_value="urn:test:case-actor-participant",
        ) as lookup:
            found = ods.case_actor_participant(
                state.client(OWNER.name), state.case.id_
            )

        assert found == "urn:test:case-actor-participant"
        assert lookup.call_args.args == (
            state.client(OWNER.name),
            state.case.id_,
        )

    def test_a_replica_naming_no_case_actor_raises_for_its_gate(self):
        """The Accept would have nowhere to route back to (CM-16-006).

        It raises rather than returning ``None``: every caller reads it inside
        a ``demo_gate``, which records the failure and skips the dependents
        (DEMOCI-01-011).
        """
        state = _state()

        with (
            patch.object(
                ods, "find_case_actor_participant_id", return_value=None
            ),
            pytest.raises(AssertionError, match="no CaseActor participant"),
        ):
            ods.case_actor_participant(
                state.client(OWNER.name), state.case.id_
            )


# ---------------------------------------------------------------------------
# owner-keep-case:keep (ADR-0026, DEMOMA-13-004/005)
# ---------------------------------------------------------------------------


@pytest.mark.spec("DEMOMA-13-004")
@pytest.mark.spec("DEMOMA-13-005")
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
                name: stack.enter_context(patch.object(ods, name, **kwargs))
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
                    coordinated_story, "wait_for_case_on_container"
                )
            )
            ods.the_owner_approves_a_suggested_actor(
                state,
                joined=JOINED,
                owner=OWNER,
                suggester=JOINER,
                newcomer=NEWCOMER,
                roles=[CVDRole.VENDOR, CVDRole.DEPLOYER],
                seated=_SEATED,
            )
        mocks["order"] = order
        return mocks

    def test_the_flow_runs_suggest_approve_invite_then_triage(self):
        """One ordered pass of ADR-0026, each act from its own container."""
        state = _state()
        with _no_banners():
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
        state = _state()
        with _no_banners():
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
        state = _state()
        with _no_banners():
            ran = self._approve(state)

        args = ran["invitee_triages_after_joining"].call_args.args
        kwargs = ran["invitee_triages_after_joining"].call_args.kwargs
        assert args[1:] == (NEWCOMER.name, NEWCOMER.label)
        assert kwargs["seated"] == _SEATED
        assert kwargs["owner"] == OWNER.name
        assert kwargs["owner_label"] == OWNER.label

    @pytest.mark.spec("CLP-08-005")
    def test_the_reporter_holds_the_case_before_the_newcomers_triage(self):
        """Bug #2120: the newcomer's triage broadcasts to the Reporter too."""
        state = _state()
        order: list[str] = []

        def _wait_for_case(client, case_id, **_kwargs):
            if client is state.client(REPORTER):
                order.append("reporter_wait")

        with contextlib.ExitStack() as stack:
            stack.enter_context(
                patch.object(
                    ods, "find_cp_offer_for_case", return_value="urn:test:cp"
                )
            )
            stack.enter_context(
                patch.object(
                    ods,
                    "find_case_actor_participant_id",
                    return_value="urn:test:case-actor-participant",
                )
            )
            stack.enter_context(patch.object(ods, "run_case_invite_chain"))
            stack.enter_context(
                patch.object(ActorSession, "suggest_actor_to_case")
            )
            stack.enter_context(
                patch.object(ActorSession, "accept_actor_recommendation")
            )
            stack.enter_context(
                patch.object(
                    coordinated_story,
                    "run_invite_path_rm_triage",
                    side_effect=lambda **_kw: order.append("triage"),
                )
            )
            stack.enter_context(
                patch.object(coordinated_story, "wait_for_case_participants")
            )
            stack.enter_context(
                patch_chain_shared(
                    coordinated_story,
                    "wait_for_case_on_container",
                    side_effect=_wait_for_case,
                )
            )
            stack.enter_context(_no_banners())
            ods.the_owner_approves_a_suggested_actor(
                state,
                joined=JOINED,
                owner=OWNER,
                suggester=JOINER,
                newcomer=NEWCOMER,
                roles=[CVDRole.VENDOR],
                seated=_SEATED,
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
        state = _state()
        ran = self._approve(
            state,
            find_cp_offer_for_case={
                "side_effect": AssertionError(
                    "timed out polling for Offer(CaseParticipant)"
                )
            },
        )

        ran["approve"].assert_not_called()
        failures = _gate_failures()
        assert len(failures) == 1, demo_utils._demo_failures
        # The gate names the parts it was handed, not either pair's actors.
        assert NEWCOMER.label in failures[0]
        assert OWNER.label in failures[0]

    def _run_the_real_chain(self, state, *, invite_lookup):
        """Run the continuation with the **real** invite chain.

        Only the Invite lookup and the primitives the chain polls with are
        stubbed, so the accept and the replica wait are reached exactly as a
        run reaches them: by the CaseActor's Invite landing in the newcomer's
        own container (no mail-carrying, no inbox injection).
        """
        with (
            patch.object(ActorSession, "suggest_actor_to_case"),
            patch.object(ActorSession, "accept_actor_recommendation"),
            patch.object(
                ActorSession, "accept_case_invite", autospec=True
            ) as accept,
            patch.object(
                ods, "find_cp_offer_for_case", return_value="urn:test:cp-offer"
            ),
            patch.object(
                ods,
                "find_case_actor_participant_id",
                return_value="urn:test:case-actor-participant",
            ),
            patch.object(
                invite_chain, "find_case_invite_for_actor", **invite_lookup
            ) as find_invite,
            patch.object(ods, "invitee_triages_after_joining"),
            patch_chain_shared(
                coordinated_story, "wait_for_case_on_container"
            ) as replica_wait,
        ):
            ods.the_owner_approves_a_suggested_actor(
                state,
                joined=JOINED,
                owner=OWNER,
                suggester=JOINER,
                newcomer=NEWCOMER,
                roles=[CVDRole.VENDOR],
                seated=_SEATED,
            )
        return find_invite, accept, replica_wait

    def test_the_newcomer_accepts_the_invite_the_case_actor_delivered(self):
        """The last hop: the Invite is found in the newcomer's own container.

        Polling only — the continuation never carries the Invite into an
        inbox, and the Accept is puppeteered from the newcomer's container.
        """
        state = _state()
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
        state = _state()
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
        state = _state()
        ran = self._approve(
            state, find_case_actor_participant_id={"return_value": None}
        )

        ran["approve"].assert_not_called()
        assert any(
            "GATE FAILED" in f and "no CaseActor participant" in f
            for f in demo_utils._demo_failures
        ), demo_utils._demo_failures


# ---------------------------------------------------------------------------
# owner-keep-case:offer-ownership (TRIG-11-001/002, DEMOMA-14-004/011)
# ---------------------------------------------------------------------------


@pytest.mark.spec("DEMOMA-14-004")
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
                name: stack.enter_context(patch.object(ods, name, **kwargs))
                for name, kwargs in patches.items()
            }
            # The re-read case must be the case the story opened: nothing a
            # scenario does changes a case's id (CM-21-002).
            wire_case = stack.enter_context(
                patch.object(ods, "as_VulnerabilityCase")
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
        state = _state()
        with _no_banners():
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
        # under an id of the CaseActor's (CM-21-005, ADR-0148).
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
        state = _state()
        with _no_banners():
            ran = self._hand_over(state)

        kwargs = ran["wait_for_case_actor_ledger_event"].call_args.kwargs
        assert kwargs["client"] is state.case_actor_client
        assert kwargs["semantic_type"] == "update_case_owner"

    @pytest.mark.spec("DEMOMA-14-011")
    def test_both_owners_replicas_and_the_witness_are_checked(self):
        """Old owner, new owner, and a participant that is neither."""
        state = _state()
        with _no_banners():
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
        state = _state()

        with (
            _no_banners(),
            patch.object(
                ods,
                "find_ownership_transfer_offer_for_actor",
                return_value="urn:test:ownership-offer",
            ),
            patch.object(ods, "wait_for_case_actor_ledger_event"),
            patch.object(ods, "wait_for_case_attributed_to"),
            patch.object(
                ods, "wait_for_semantic_type_in_ledger"
            ) as witness_wait,
            patch.object(ods, "as_VulnerabilityCase") as wire_case,
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
        state = _state()
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
        assert len(_gate_failures()) == 1, demo_utils._demo_failures

    def test_a_completed_transfer_restates_the_case_and_keeps_the_prop(self):
        """The case is re-read as the old owner now stores it (CM-21-002)."""
        state = _state()
        restated = mock_case(state.case.id_)
        with _no_banners():
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
        state = _state()
        ran = self._hand_over(state, restated=mock_case("urn:test:other-case"))

        assert state.case.id_ == "urn:test:case"
        with pytest.raises(DemoStoryError, match="handed over"):
            state.kept(HANDED_OVER_CASE)
        assert any(
            "GATE FAILED" in f and "restate" in f
            for f in demo_utils._demo_failures
        ), demo_utils._demo_failures
        assert ran["wait_for_case_attributed_to"].called

    def test_the_accept_is_skipped_when_the_case_actors_offer_never_arrives(
        self,
    ):
        """#3038: the accept nests inside the delivery gate."""
        state = _state()
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
        state = _state()
        order: list[str] = []

        with contextlib.ExitStack() as stack:
            lookup = stack.enter_context(
                patch.object(
                    ods,
                    "find_ownership_transfer_offer_for_actor",
                    return_value="urn:test:ownership-offer",
                )
            )
            for name in (
                "wait_for_case_actor_ledger_event",
                "wait_for_case_attributed_to",
                "wait_for_semantic_type_in_ledger",
            ):
                stack.enter_context(patch.object(ods, name))
            wire_case = stack.enter_context(
                patch.object(ods, "as_VulnerabilityCase")
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
                name: stack.enter_context(patch.object(ods, name, **kwargs))
                for name, kwargs in patches.items()
            }
            mocks["replica_wait"] = stack.enter_context(
                patch_chain_shared(
                    coordinated_story, "wait_for_case_on_container"
                )
            )
            ods.the_new_owner_invites(
                state,
                new_owner=JOINER,
                invitee=NEWCOMER,
                role=CVDRole.VENDOR,
                seated=_SEATED,
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
        state = _state()

        with (
            patch.object(ods, "run_case_invite_chain") as chain,
            patch.object(ods, "find_case_actor_participant_id"),
            pytest.raises(DemoStoryError, match="handed over"),
        ):
            ods.the_new_owner_invites(
                state,
                new_owner=JOINER,
                invitee=NEWCOMER,
                role=CVDRole.VENDOR,
                seated=_SEATED,
            )

        chain.assert_not_called()

    @pytest.mark.spec("DEMOMA-22-002")
    def test_the_invite_is_triggered_on_the_new_owners_own_container(self):
        """#2178: a trigger posted to the old owner's client 404s.

        A trigger URL is built from the named actor's bare id against the
        client's base URL, so the inviter must carry the new owner's *own*
        client and actor.
        """
        state = _state()
        state.keep(HANDED_OVER_CASE, str(state.case.id_))
        with _no_banners():
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
        state = _state()
        state.keep(HANDED_OVER_CASE, str(state.case.id_))
        with _no_banners():
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
        state = _state()
        state.keep(HANDED_OVER_CASE, str(state.case.id_))
        with _no_banners():
            ran = self._invite(state)

        assert ran["order"] == ["invite-chain", "triage"]
        kwargs = ran["invitee_triages_after_joining"].call_args.kwargs
        assert kwargs["owner"] == JOINER.name
        assert kwargs["owner_label"] == JOINER.label
        assert kwargs["seated"] == _SEATED

    @pytest.mark.spec("CLP-08-005")
    def test_the_reporter_holds_the_case_before_the_newcomer_triages(self):
        """The join broadcasts to every participant (Bug #2135)."""
        state = _state()
        state.keep(HANDED_OVER_CASE, str(state.case.id_))
        with _no_banners():
            ran = self._invite(state)

        assert [
            c.kwargs["client"] for c in ran["replica_wait"].call_args_list
        ] == [state.client(REPORTER)]

    def test_a_missing_case_actor_participant_skips_the_chain(self):
        """PCR-08-008 cannot be checked, so the invite does not go out."""
        state = _state()
        state.keep(HANDED_OVER_CASE, str(state.case.id_))
        ran = self._invite(
            state, find_case_actor_participant_id={"return_value": None}
        )

        ran["run_case_invite_chain"].assert_not_called()
        assert any(
            "GATE FAILED" in f and "no CaseActor participant" in f
            for f in demo_utils._demo_failures
        ), demo_utils._demo_failures


# ---------------------------------------------------------------------------
# What each continuation presupposes (DEMOCI-01-011, #5535)
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
        state = _state(joined=False)

        with (
            patch.object(ActorSession, "suggest_actor_to_case") as suggest,
            _no_banners(),
            pytest.raises(DemoStoryError, match="test pair's join"),
        ):
            ods.the_owner_approves_a_suggested_actor(
                state,
                joined=JOINED,
                owner=OWNER,
                suggester=JOINER,
                newcomer=NEWCOMER,
                roles=[CVDRole.VENDOR],
                seated=_SEATED,
            )

        suggest.assert_not_called()

    def test_the_case_is_not_offered_without_the_join(self):
        """The transferee must be an active participant (DEMOMA-14-010)."""
        state = _state(joined=False)

        with (
            patch.object(
                ActorSession, "offer_case_ownership_transfer"
            ) as offer,
            _no_banners(),
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
    CM-21-007 broadcast. The helper refuses the pairing rather than leaving it
    to the ratchet, which reads call sites lexically and cannot see a `Part`
    passed in by a caller.
    """

    @pytest.mark.parametrize(
        "witness", [OWNER, JOINER], ids=["old-owner", "new-owner"]
    )
    def test_a_party_named_as_the_witness_is_refused(self, witness: Part):
        state = _state()

        with (
            patch.object(
                ActorSession, "offer_case_ownership_transfer"
            ) as offer,
            _no_banners(),
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
