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

"""How an invitee joins a coordinator-first case (#5534, #5535, #5536).

Pins :mod:`vultron.demo.helpers.coordinated_story.joining`: the shared
join for an invitee whose decision is no branch point
(``invitee_joins_the_case``), the Reporter's replica before the Vendor's
triage (CLP-08-005), and the accept arm's reply to the full-case Invite.
"""

import contextlib
import logging
from collections.abc import Iterator
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from test.demo._helpers import (
    mock_case,
    patch_chain_shared,
    recorded_labels,
    story_state,
)
from test.demo.coordinated_story._support import CAST, JOINED, JOINER
from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers.coordinated_story import (
    COORDINATOR,
    COORDINATOR_LABEL,
    REPORTER,
    VENDOR,
    invitee_joins_the_case,
    invitee_triages_after_joining,
    joining as coordinated_joining,
    vendor_accepts_and_joins,
)
from vultron.demo.helpers.invite_chain import links as invite_links
from vultron.demo.utils import demo_gate
from vultron.demo.utils.check_tree import (
    CheckKind,
    CheckOutcome,
    recording_checks,
)
from vultron.demo.utils.failures import demo_failures
from vultron.enums.roles import CVDRole
from vultron.errors import DemoStoryError

#: Clear the process-global failure accumulator around every test.
pytestmark = pytest.mark.usefixtures("fresh_demo_failures")


@contextlib.contextmanager
def _join_stubs() -> Iterator[SimpleNamespace]:
    """Stub every collaborator of ``invitee_joins_the_case``.

    Yields the invite chain, the roster wait and the RM triage, so a test can
    say which of the three ran and what each was handed.  The demo context
    managers stay real: every wait their blocks make is one of these stubs,
    and a stub that raised would be recorded and suppressed rather than
    failing the test, so the block's exit asserts that nothing was recorded
    (``vultron/demo/AGENTS.md`` § "Gate Each Step on Its Cause" rule 8).
    """
    with (
        patch.object(coordinated_joining, "wait_for_case_on_container"),
        patch.object(coordinated_joining, "run_case_invite_chain") as chain,
        patch.object(
            coordinated_joining, "wait_for_case_participants"
        ) as roster,
        patch.object(
            coordinated_joining, "run_invite_path_rm_triage"
        ) as triage,
    ):
        yield SimpleNamespace(chain=chain, roster=roster, triage=triage)
    _assert_no_demo_failures()


def _assert_no_demo_failures() -> None:
    """Fail on anything a real demo context manager recorded and suppressed."""
    assert not demo_failures(), (
        f"a demo block recorded a failure: {demo_failures()!r}"
    )


@contextlib.contextmanager
def _recorded_gates() -> Iterator[list[str]]:
    """Collect every ``demo_gate`` label the fragment under test opens.

    A gate's label is what a reader sees when its wait times out, so a label
    naming the family's Coordinator while the first Vendor is the one
    inviting sends that reader to the wrong container (#5536).  Read off the
    recorded check tree, through the real ``demo_gate``; the list fills as the
    block leaves, so read it after the ``with``.
    """
    with recorded_labels(CheckKind.GATE) as labels:
        yield labels


# ---------------------------------------------------------------------------
# The shared join for an invitee whose decision is no branch point
# ---------------------------------------------------------------------------


class TestInviteeJoinsTheCase:
    """One invite chain, and whether an RM triage follows it (CM-11-002)."""

    def test_an_accepting_invitee_triages_after_the_chain(self):
        """A vendor judges the report it was invited over (CM-11-002).

        The triage reads the canonical ledger through the case-actor
        container, not the Coordinator's replica (DEMOMA-06-005).
        """
        state = story_state(*CAST, JOINER, case=mock_case())
        seated = (REPORTER, COORDINATOR, VENDOR, JOINER)

        with _join_stubs() as stubs:
            invitee_joins_the_case(
                state,
                JOINER,
                "Joiner",
                role=CVDRole.VENDOR,
                seated=seated,
            )

        chain = stubs.chain.call_args.kwargs
        assert chain["then"] is None, (
            "an invitee that triages confirms the roster in its own gate"
        )
        assert chain["invitee_client"] is state.client(JOINER)
        assert chain["case_manager_client"] is state.case_actor_client
        assert chain["inviter"].role is CVDRole.VENDOR
        assert chain["inviter"].client is state.client(COORDINATOR)

        triage = stubs.triage.call_args.kwargs
        assert triage["invited_client"] is state.client(JOINER)
        assert triage["auth_client"] is state.case_actor_client
        roster = stubs.roster.call_args.kwargs
        assert roster["expected_actor_ids"] == {
            f"urn:test:{name}" for name in seated
        }
        assert roster["vendor_client"] is state.client(COORDINATOR)

    @pytest.mark.spec("DEMOMA-17-002")
    def test_triages_false_hands_the_roster_check_to_the_chain(self):
        """A coordinator joining to help coordinate runs no RM triage.

        Giving it one would put an ``engage_case`` act in the ledger the
        scenario's semantic-type list does not claim (DEMOMA-17-002).  Its
        roster check then moves inside the chain's own gate, as the chain's
        ``then``, so a failed invite skips it rather than timing out on a
        roster that will never fill (EDF-06-005).
        """
        state = story_state(*CAST, JOINER, case=mock_case())
        seated = (REPORTER, COORDINATOR, VENDOR, JOINER)

        with _join_stubs() as stubs:
            invitee_joins_the_case(
                state,
                JOINER,
                "Joiner",
                role=CVDRole.COORDINATOR,
                seated=seated,
                triages=False,
            )
            then = stubs.chain.call_args.kwargs["then"]
            assert then is not None, (
                "the roster check must be handed to the chain as its `then`"
            )
            stubs.roster.assert_not_called()
            then()
            roster = stubs.roster.call_args.kwargs
            assert roster["expected_actor_ids"] == {
                f"urn:test:{name}" for name in seated
            }
            assert roster["vendor_client"] is state.client(COORDINATOR)

        stubs.triage.assert_not_called()
        assert (
            stubs.chain.call_args.kwargs["inviter"].role is CVDRole.COORDINATOR
        )

    @pytest.mark.spec("DEMOCI-01-011")
    def test_a_joined_prop_makes_the_roster_a_gate_that_keeps_it(self):
        """A non-triaging joiner whose join the next act presupposes (#5535).

        The two-coordinator pair decides the case's ownership once its second
        Coordinator is a participant (DEMOMA-13-003, DEMOMA-14-010), and a
        flat story cannot nest that decision inside this roster's gate.  So
        the roster becomes the gate and keeps the case id, which the deciding
        fragment reads.  The real ``demo_gate`` runs here: this test is about
        control flow.
        """
        state = story_state(*CAST, JOINER, case=mock_case())

        with (
            patch.object(coordinated_joining, "wait_for_case_on_container"),
            patch.object(
                coordinated_joining, "run_case_invite_chain"
            ) as chain,
            patch.object(coordinated_joining, "wait_for_case_participants"),
        ):
            invitee_joins_the_case(
                state,
                JOINER,
                "Joiner",
                role=CVDRole.COORDINATOR,
                seated=(REPORTER, COORDINATOR, JOINER),
                triages=False,
                joined=JOINED,
            )
            chain.call_args.kwargs["then"]()

        assert state.kept(JOINED) == str(state.case.id_)

    @pytest.mark.spec("DEMOCI-01-011")
    def test_a_roster_that_never_fills_keeps_no_prop(self):
        """The gate records the timeout and leaves the prop unkept.

        That is how the dependent fragment stops the story instead of
        suggesting or offering into a case the joiner is not in: it reads the
        prop through an accessor that raises
        (:func:`~vultron.demo.helpers.story.run_story`).
        """
        state = story_state(*CAST, JOINER, case=mock_case())

        with (
            patch.object(coordinated_joining, "wait_for_case_on_container"),
            patch.object(
                coordinated_joining, "run_case_invite_chain"
            ) as chain,
            patch.object(
                coordinated_joining,
                "wait_for_case_participants",
                side_effect=AssertionError("roster never filled"),
            ),
        ):
            invitee_joins_the_case(
                state,
                JOINER,
                "Joiner",
                role=CVDRole.COORDINATOR,
                seated=(REPORTER, COORDINATOR, JOINER),
                triages=False,
                joined=JOINED,
            )
            chain.call_args.kwargs["then"]()

        with pytest.raises(
            DemoStoryError, match="no case the test joiner joined yet"
        ):
            state.kept(JOINED)

    @pytest.mark.spec("DEMOCI-01-003", "DEMOCI-01-007")
    def test_a_failed_triage_gate_is_recorded_and_the_join_returns(self):
        """What the ``nullcontext`` stub hid (#6155).

        A ``demo_gate`` records its failure, skips the steps inside it, and
        lets the run go on after the block.  Under the stub the roster's
        ``AssertionError`` left the shared join instead, so a test of the
        join's gate labels passed whether or not the gate held.
        """
        state = story_state(*CAST, JOINER, case=mock_case())
        label = f"{COORDINATOR_LABEL} case has Joiner before Joiner RM triage"

        with (
            patch.object(coordinated_joining, "wait_for_case_on_container"),
            patch.object(
                coordinated_joining, "run_case_invite_chain"
            ) as chain,
            patch.object(
                coordinated_joining,
                "wait_for_case_participants",
                side_effect=AssertionError("roster never filled"),
            ),
            patch.object(
                coordinated_joining, "run_invite_path_rm_triage"
            ) as triage,
            recording_checks() as recorder,
        ):
            invitee_joins_the_case(
                state,
                JOINER,
                "Joiner",
                role=CVDRole.VENDOR,
                seated=(REPORTER, COORDINATOR, VENDOR, JOINER),
            )
            # Reached only because the gate kept the failure to itself.
            with demo_gate("the step after the join"):
                pass

        assert [
            (node.kind, node.label, node.outcome) for node in recorder.tree()
        ] == [
            (
                CheckKind.CHECK,
                "Reporter's DataLayer received case replica",
                CheckOutcome.PASSED,
            ),
            (CheckKind.GATE, label, CheckOutcome.FAILED),
            (
                CheckKind.GATE,
                "the step after the join",
                CheckOutcome.PASSED,
            ),
        ]
        assert demo_failures() == (
            f"GATE FAILED: {label} — roster never filled",
        )
        chain.assert_called_once()
        # The triage depends on the roster, so the gate skipped it.
        triage.assert_not_called()

    @pytest.mark.spec("DEMOCI-01-011")
    def test_a_prop_asked_for_on_the_triaging_path_is_refused(self):
        """Only the non-triaging path keeps one, so the pairing raises.

        A triaging invitee's roster is already the gate inside
        ``invitee_triages_after_joining``, and the chain's ``then`` — the only
        place a prop is kept — is not run on that path.  Accepting the
        pairing would leave a prop no step ever keeps, so every fragment that
        read it would stop the story on a healthy run.
        """
        state = story_state(*CAST, JOINER, case=mock_case())

        with (
            _join_stubs() as stubs,
            pytest.raises(DemoStoryError, match="triages=True and a prop"),
        ):
            invitee_joins_the_case(
                state,
                JOINER,
                "Joiner",
                role=CVDRole.VENDOR,
                seated=(REPORTER, COORDINATOR, JOINER),
                joined=JOINED,
            )

        stubs.chain.assert_not_called()

    @pytest.mark.spec("CM-17-007")
    def test_the_inviter_defaults_to_the_familys_coordinator(self):
        """Every coordinator-first caller is unchanged by the keyword (#5536).

        Only the Case Owner may invite (CM-17-007), and in this family that is
        the Coordinator.  The default is pinned here so adding *inviter* for
        the vendor-first family cannot quietly move the Invite, the roster
        read or the gate label onto somebody else for the callers that pass
        nothing.
        """
        state = story_state(*CAST, JOINER, case=mock_case())

        with _join_stubs() as stubs, _recorded_gates() as labels:
            invitee_joins_the_case(
                state,
                JOINER,
                "Joiner",
                role=CVDRole.VENDOR,
                seated=(REPORTER, COORDINATOR, VENDOR, JOINER),
            )

        inviter = stubs.chain.call_args.kwargs["inviter"]
        assert inviter.name == COORDINATOR_LABEL
        assert inviter.client is state.client(COORDINATOR)
        assert inviter.actor is state.actor(COORDINATOR).actor
        assert stubs.roster.call_args.kwargs["vendor_client"] is state.client(
            COORDINATOR
        ), "the default roster read is the Coordinator's own replica"
        assert labels == [
            f"{COORDINATOR_LABEL} case has Joiner before Joiner RM triage"
        ], f"the gate must name the default inviter; got {labels!r}"

    @pytest.mark.spec("CM-17-007")
    def test_a_named_inviter_invites_from_its_own_container(self):
        """The vendor-first family has its first Vendor invite (#5536).

        Only the Case Owner may invite (CM-17-007), and which cast member that
        is differs by family.  Naming one must move all four of the things
        that follow from it: the Invite's sending client, the actor the Invite
        comes from, the replica the roster is read from, and the label that
        tells a reader whose container to look in.
        """
        state = story_state(*CAST, JOINER, case=mock_case())
        seated = (REPORTER, VENDOR, JOINER)

        with _join_stubs() as stubs, _recorded_gates() as labels:
            invitee_joins_the_case(
                state,
                JOINER,
                "Joiner",
                role=CVDRole.VENDOR,
                seated=seated,
                inviter=VENDOR,
                inviter_label="Vendor1",
            )

        inviter = stubs.chain.call_args.kwargs["inviter"]
        assert inviter.client is state.client(VENDOR), (
            "the Invite must be sent from the named inviter's own container"
            " (CM-17-007)"
        )
        assert inviter.actor is state.actor(VENDOR).actor
        assert inviter.name == "Vendor1"
        roster = stubs.roster.call_args.kwargs
        assert roster["vendor_client"] is state.client(VENDOR), (
            "a triaging invitee's roster is read from the named inviter's"
            " replica too, not from the family's Coordinator"
        )
        assert roster["expected_actor_ids"] == {
            f"urn:test:{name}" for name in seated
        }
        assert labels == ["Vendor1 case has Joiner before Joiner RM triage"], (
            f"the gate must name the inviter it waited on; got {labels!r}"
        )

    @pytest.mark.spec("CM-17-007")
    def test_a_named_inviter_also_owns_the_non_triaging_roster_gate(self):
        """The other arm of the join reads the same replica (#5536).

        A non-triaging joiner confirms the roster inside the chain's own
        ``then``, which is a second place the Case Owner is named; a default
        left behind there would wait on the Coordinator's replica for a case
        the first Vendor owns.
        """
        state = story_state(*CAST, JOINER, case=mock_case())
        seated = (REPORTER, VENDOR, JOINER)

        with _join_stubs() as stubs, _recorded_gates() as labels:
            invitee_joins_the_case(
                state,
                JOINER,
                "Joiner",
                role=CVDRole.COORDINATOR,
                seated=seated,
                triages=False,
                joined=JOINED,
                inviter=VENDOR,
                inviter_label="Vendor1",
            )
            stubs.chain.call_args.kwargs["then"]()

        assert stubs.roster.call_args.kwargs["vendor_client"] is state.client(
            VENDOR
        )
        assert labels == [
            "Vendor1 case reflects 3 participants after Joiner joined"
        ], f"the gate must name the inviter it waited on; got {labels!r}"
        assert state.kept(JOINED) == str(state.case.id_)
        stubs.triage.assert_not_called()

    @pytest.mark.spec("DEMOMA-14-005")
    def test_the_triage_roster_is_read_from_the_named_owner(self):
        """A story whose owner changed mid-run names the owner of this step.

        ``invitee_triages_after_joining`` reads the roster from the Case
        Owner's replica, which is the family's Coordinator by default and the
        new owner after an ownership transfer (#5535).
        """
        state = story_state(*CAST, JOINER, case=mock_case())

        with _join_stubs() as stubs:
            invitee_triages_after_joining(
                state,
                VENDOR,
                "Vendor",
                seated=(REPORTER, COORDINATOR, JOINER, VENDOR),
                owner=JOINER,
                owner_label="Joiner",
            )

        assert stubs.roster.call_args.kwargs["vendor_client"] is state.client(
            JOINER
        )
        stubs.triage.assert_called_once()

    @pytest.mark.spec("DEMOMA-17-002")
    def test_the_join_logs_the_milestone_the_scenario_numbers_it(self, caplog):
        """The default is the coordinator-first families' ``M2``.

        Every scenario that reached this step before the vendor-first half
        was composed numbers the join M2, so the default keeps their output
        as it was (#5536).
        """
        state = story_state(*CAST, JOINER, case=mock_case())

        with caplog.at_level(logging.INFO), _join_stubs():
            invitee_triages_after_joining(
                state,
                JOINER,
                "Joiner",
                seated=(REPORTER, COORDINATOR, VENDOR, JOINER),
            )

        assert "✓ M2: Joiner joined case" in caplog.text

    @pytest.mark.spec("DEMOMA-17-002")
    def test_a_scenario_that_numbers_no_join_milestone_logs_none(self, caplog):
        """``milestone=None`` drops the number, not the line.

        ``rvv`` spends M2 on its replica synchronization, so the shared
        step's default would put a second ``✓ M2:`` line in the output
        ``docs/howto/demos/rvv-demo.md`` documents and the two could not be
        told apart (#5536).
        """
        state = story_state(*CAST, JOINER, case=mock_case())

        with caplog.at_level(logging.INFO), _join_stubs():
            invitee_triages_after_joining(
                state,
                JOINER,
                "Joiner",
                seated=(REPORTER, COORDINATOR, VENDOR, JOINER),
                milestone=None,
            )

        assert "✓ Joiner joined case" in caplog.text
        assert "M2" not in caplog.text


# ---------------------------------------------------------------------------
# Bug #2135 (CLP-08-005): the Reporter's replica before the Vendor's triage
# ---------------------------------------------------------------------------


@pytest.mark.spec("CLP-08-005")
class TestReporterCaseReplicaWaitBeforeVendorTriage:
    """The Vendor's acceptance broadcasts to every participant.

    The Vendor's reply to the full-case Invite broadcasts
    ``Announce(CaseLedgerEntry)`` to all participants including the Reporter.
    If the Reporter's DataLayer does not yet hold the ``VulnerabilityCase``
    (genesis hash unavailable), the chain bootstrap fails with CLP-08-005.
    """

    def test_reporter_wait_before_vendor_triage(self):
        state = story_state(*CAST, case=mock_case())
        state.invited(VENDOR, "urn:test:invite")
        call_order: list[str] = []

        def _wait_for_case(client, case_id, **_kwargs):
            if client is state.client(REPORTER):
                call_order.append("reporter_wait")

        with (
            patch_chain_shared(
                coordinated_joining,
                "wait_for_case_on_container",
                side_effect=_wait_for_case,
            ),
            patch.object(
                coordinated_joining,
                "run_invite_path_rm_triage",
                side_effect=lambda **_kw: call_order.append("triage"),
            ),
            patch.object(ActorSession, "accept_case_invite"),
            patch.object(invite_links, "reply_to_full_case_invite"),
            patch.object(coordinated_joining, "wait_for_case_participants"),
        ):
            vendor_accepts_and_joins(state)

        _assert_no_demo_failures()

        assert "reporter_wait" in call_order, (
            "wait_for_case_on_container(reporter_client) was never called"
            " before Vendor triage"
        )
        assert "triage" in call_order, (
            "run_invite_path_rm_triage was never called"
        )
        assert call_order.index("reporter_wait") < call_order.index(
            "triage"
        ), (
            f"Reporter case-replica wait must come BEFORE "
            f"run_invite_path_rm_triage. Call order: {call_order} —"
            " Bug #2135 (CLP-08-005)"
        )


# ---------------------------------------------------------------------------
# The accept arm answers against the canonical case (#5533)
# ---------------------------------------------------------------------------


@pytest.mark.spec("SYNC-10-004")
class TestVendorAcceptsAndJoins:
    """The ledger authority of the accept arm is the case-actor container.

    The full-case reply trigger fails closed until the invitee's own ledger
    copy reaches the Invite's floor, so the chain waits for coverage against
    the container holding the canonical ledger first (SYNC-10-004, ADR-0073,
    DEMOMA-06-005).  A participant's replica is the wrong one to wait on and
    would pass the wait before the entries landed.

    ``rcv`` is the only scenario that reaches this fragment and it is not in
    the PR set (``in_pr_set=False``), so Docker CI exercises the wiring only
    on the full suite; it is pinned here.
    """

    def test_the_full_case_reply_waits_on_the_case_actor_container(self):
        state = story_state(*CAST, case=mock_case())
        state.invited(VENDOR, "urn:test:invite")

        with (
            patch_chain_shared(
                coordinated_joining, "wait_for_case_on_container"
            ),
            patch.object(coordinated_joining, "run_invite_path_rm_triage"),
            patch.object(ActorSession, "accept_case_invite"),
            patch.object(invite_links, "reply_to_full_case_invite") as reply,
            patch.object(coordinated_joining, "wait_for_case_participants"),
        ):
            vendor_accepts_and_joins(state)

        _assert_no_demo_failures()

        reply.assert_called_once()
        assert (
            reply.call_args.kwargs["authority_client"]
            is state.case_actor_client
        )
