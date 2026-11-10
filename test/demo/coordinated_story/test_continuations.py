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

"""Continuations more than one coordinator-first scenario tells.

Pins :mod:`vultron.demo.helpers.coordinated_story.continuations`: the
fix-ready and publication milestones, the closure every continuation
shares (CM-23-015) and the rejection's reads of the CASE_MANAGER's own
store (#1876).
"""

import contextlib
from unittest.mock import patch

import pytest

from test.demo._helpers import (
    mock_case,
    recorded_milestone_reads,
    story_state,
)
from test.demo.coordinated_story._support import (
    CAST,
    JOINER,
    patched_rejection_polls,
)
from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers.coordinated_story import (
    COORDINATOR,
    REPORTER,
    VENDOR,
    close_the_case,
    continuations as coordinated_continuations,
    everyone_closes,
    everyone_publishes,
    reporter_then_coordinator_close,
    vendor_rejects_invite,
    vendor_reports_the_fix_ready,
)
from vultron.demo.utils.check_tree import (
    CheckKind,
    recording_checks,
    walk,
)

#: Clear the process-global failure accumulator around every test.
pytestmark = pytest.mark.usefixtures("fresh_demo_failures")

#: ``wait_for_participant_vf_state`` under the name the assertions read it by.
_VF_WAIT = "wait_for_participant_vf_state"

#: The fix-ready pair's reads, as :func:`recorded_milestone_reads` names them.
#: The same shape the vendor-first sibling records, so the two families' AC-3
#: ratchets compare the same thing (CS-22-001).
_FIX_READY_READS = {
    _VF_WAIT: ("client", "actor_id"),
    "verify_fix_ready": ("receiver_client", "receiver_actor_id"),
    "verify_stops_at_fix_ready": ("receiver_client", "receiver_actor_id"),
}

# ---------------------------------------------------------------------------
# Milestone assertions — AC-4 of ISSUE-1976, now on the fragments
# ---------------------------------------------------------------------------


class TestCoordinatedMilestones:
    """Each fragment calls the milestone helper its phase did."""

    def test_vendor_reports_the_fix_ready_calls_verify_fix_ready(self):
        """M5 runs when the Vendor reports fix ready."""
        state = story_state(*CAST, case=mock_case())

        with (
            patch.object(
                coordinated_continuations, "wait_for_participant_rm_state"
            ),
            patch.object(ActorSession, "notify_fix_ready"),
            patch.object(
                coordinated_continuations, "wait_for_participant_vf_state"
            ),
            patch.object(
                coordinated_continuations, "verify_fix_ready"
            ) as mock_m5,
            patch.object(
                coordinated_continuations,
                "demo_check",
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            vendor_reports_the_fix_ready(state)

        mock_m5.assert_called()

    def test_vendor_reports_the_fix_ready_gates_on_rm_accepted(self):
        """The RM wait precedes notify-fix-ready (ADR-0058/CSB-18-001)."""
        from vultron.core.states.rm import RM

        state = story_state(*CAST, case=mock_case())
        call_order: list[str] = []
        rm_calls: list[dict] = []

        def _rm_wait(*_args, **kwargs):
            rm_calls.append(kwargs)
            call_order.append("rm_wait")

        with (
            patch.object(
                coordinated_continuations,
                "wait_for_participant_rm_state",
                _rm_wait,
            ),
            patch.object(
                ActorSession,
                "notify_fix_ready",
                side_effect=lambda *a, **kw: call_order.append("fix_ready"),
            ),
            patch.object(
                coordinated_continuations, "wait_for_participant_vf_state"
            ),
            patch.object(coordinated_continuations, "verify_fix_ready"),
        ):
            vendor_reports_the_fix_ready(state)

        assert rm_calls, (
            "wait_for_participant_rm_state must be called (ADR-0058/CSB-18-001)"
        )
        assert all(
            c.get("expected_states") == {RM.ACCEPTED, RM.DEFERRED, RM.CLOSED}
            for c in rm_calls
        ), "expected_states must be {ACCEPTED, DEFERRED, CLOSED} (CSB-18-001)"
        # Membership first: indexing a missing call raises ValueError and the
        # ordering assertion's message never prints.
        assert "rm_wait" in call_order, call_order
        assert "fix_ready" in call_order, (
            f"notify_fix_ready was never called. Call order: {call_order}"
        )
        assert call_order.index("rm_wait") < call_order.index("fix_ready"), (
            "wait_for_participant_rm_state must precede notify_fix_ready"
            " (ADR-0058)"
        )

    @pytest.mark.spec("CSB-15-002")
    def test_m4_and_m5_do_not_assert_the_same_thing(self):
        """The ratchet for #5602, on the coordinator-first copy of the pair.

        M4 and M5 used to run one body twice, so M5 proved nothing M4 had not
        while its label claimed the Vendor stopped at VFd.  M5 now reads the
        fix-deployed transition the Vendor never makes.

        The two halves' reads are compared **each way**, on the same
        ``(helper, container, subject)`` key the vendor-first sibling uses
        (:func:`test.demo._helpers.recorded_milestone_reads`): a half whose
        reads are a subset of the other's adds nothing even though the two
        lists differ.  Keying on the container and the subject rather than on
        the helper name alone is what catches a rewrite that reads the right
        thing about the wrong actor, or on the wrong replica — which the
        earlier call-sequence pin did not (#6186).

        Read through the real ``demo_check``, not a ``nullcontext`` stub: the
        stub lets an assertion propagate, so the test would pass while proving
        nothing (``vultron/demo/AGENTS.md`` rule 8, #6127).
        """
        state = story_state(*CAST, case=mock_case())

        with (
            patch.object(
                coordinated_continuations, "wait_for_participant_rm_state"
            ),
            patch.object(ActorSession, "notify_fix_ready"),
            recorded_milestone_reads(
                state, coordinated_continuations, _FIX_READY_READS
            ) as reads,
            recording_checks() as recorder,
        ):
            vendor_reports_the_fix_ready(state)

        labels = [
            node.label
            for node in walk(recorder.tree())
            if node.kind is CheckKind.CHECK and node.label.startswith("M")
        ]
        assert len(labels) == 2, labels
        assert labels[0].startswith("M4: "), labels
        assert labels[1].startswith("M5: "), labels
        assert "stopped at VFd" in labels[1], labels[1]

        # The trigger's own gate reads the Vendor's replica, then M4 and M5
        # read the Coordinator's.  Both halves are about the Vendor, so a
        # rewrite pointed at the Coordinator's own participant record, or at
        # the wrong replica, changes this list (#6186).
        vendor = state.actor_id(VENDOR)
        assert reads == [
            (_VF_WAIT, VENDOR, vendor),
            (_VF_WAIT, COORDINATOR, vendor),
            ("verify_fix_ready", COORDINATOR, vendor),
            ("verify_stops_at_fix_ready", COORDINATOR, vendor),
        ], reads

        # Each half's own reads, sliced by position: the trigger's gate at
        # index 0 belongs to neither milestone, M4's body is next and M5's
        # is the rest.
        reached = set(reads[1:3])
        stopped = set(reads[3:])
        assert reached, "the fix-ready half read nothing"
        assert stopped, "the VFd-ceiling half read nothing"
        # Difference each way, not inequality: a half whose reads are a subset
        # of the other's asserts nothing the other does not, which is the
        # defect even though the two lists are not equal.
        assert stopped - reached, (
            "the VFd-ceiling milestone asserts nothing the fix-ready one does"
            f" not; both read {sorted(stopped)} (#5602)"
        )
        assert reached - stopped, (
            "the fix-ready milestone asserts nothing the VFd-ceiling one does"
            f" not; both read {sorted(reached)} (#5602)"
        )

    def test_everyone_publishes_calls_verify_publicly_disclosed(self):
        """M6 runs when every participant has reported publication."""
        state = story_state(*CAST, case=mock_case())

        with (
            patch.object(ActorSession, "notify_published"),
            patch.object(
                coordinated_continuations, "wait_for_case_em_terminated"
            ),
            patch.object(
                coordinated_continuations, "wait_for_participant_vf_state"
            ),
            patch.object(
                coordinated_continuations, "verify_publicly_disclosed"
            ) as mock_m6,
            patch.object(
                coordinated_continuations,
                "demo_check",
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            everyone_publishes(state)

        mock_m6.assert_called()


# ---------------------------------------------------------------------------
# The closure every continuation shares (CM-23-015)
# ---------------------------------------------------------------------------


class TestCloseTheCase:
    """Who leaves, through whose container, and who is named the owner.

    ``close_the_case`` is the shared wrapper; the sequencing itself —
    the owner's ``Leave`` after every other departure is recorded — belongs
    to ``close_case_owner_last`` and is pinned on a real run of it in
    ``test_later_vendors.py``.
    """

    def test_everyone_closes_runs_the_closure_milestone(self):
        """``rcv``'s three-party closure is M7 (CM-23-004)."""
        state = story_state(*CAST, case=mock_case())

        with patch.object(
            coordinated_continuations, "close_case_owner_last"
        ) as closure:
            everyone_closes(state)

        kwargs = closure.call_args.kwargs
        assert kwargs["milestone"] == "M7"
        assert [leaver.client for leaver in kwargs["others"]] == [
            state.client(VENDOR),
            state.client(REPORTER),
        ]
        assert kwargs["owner"].client is state.client(COORDINATOR)

    def test_reporter_then_coordinator_close_runs_its_own_milestone(self):
        """The two-party closure is the Case Owner leaving last (CM-23-015)."""
        state = story_state(*CAST, case=mock_case())

        with patch.object(
            coordinated_continuations, "close_case_owner_last"
        ) as closure:
            reporter_then_coordinator_close(state)

        kwargs = closure.call_args.kwargs
        assert kwargs["milestone"] == "M4"
        assert kwargs["authority_client"] is state.case_actor_client
        assert [leaver.client for leaver in kwargs["others"]] == [
            state.client(REPORTER)
        ]
        assert kwargs["owner"].client is state.client(COORDINATOR)

    @pytest.mark.spec("CM-23-015")
    def test_the_leavers_keep_their_order_and_the_owner_stands_apart(self):
        """The order given is the order handed over, the owner excluded.

        A scenario with a character actor among its leavers (``rcvcv``,
        ``rcvv-embargo``) passes it in the position it leaves in, and each
        leaver acts through its own container — a leaver paired with another's
        client would send that actor's ``Leave`` twice and never its own.
        """
        state = story_state(*CAST, JOINER, case=mock_case())

        with patch.object(
            coordinated_continuations, "close_case_owner_last"
        ) as closure:
            close_the_case(
                state,
                others=(VENDOR, JOINER, REPORTER),
                owner=COORDINATOR,
                milestone="M8",
            )

        kwargs = closure.call_args.kwargs
        assert kwargs["milestone"] == "M8"
        assert [leaver.actor.id_ for leaver in kwargs["others"]] == [
            f"urn:test:{name}" for name in (VENDOR, JOINER, REPORTER)
        ]
        assert [leaver.client for leaver in kwargs["others"]] == [
            state.client(name) for name in (VENDOR, JOINER, REPORTER)
        ]
        assert kwargs["owner"].actor.id_ == f"urn:test:{COORDINATOR}"
        assert kwargs["owner"].client is state.client(COORDINATOR)

    @pytest.mark.spec("CM-23-004")
    def test_a_scenario_that_numbers_no_milestone_passes_none_through(self):
        """``rvcv-handoff`` numbers no closure milestone (#5536).

        Its check descriptions are then unprefixed, which is
        ``close_case_owner_last``'s own ``milestone=None`` behaviour; the
        wrapper's part is to pass the absence through rather than invent an
        ``"M?"`` prefix the scenario never declared.
        """
        state = story_state(*CAST, case=mock_case())

        with patch.object(
            coordinated_continuations, "close_case_owner_last"
        ) as closure:
            close_the_case(state, others=(REPORTER,), milestone=None)

        kwargs = closure.call_args.kwargs
        assert kwargs["milestone"] is None, (
            "a scenario that numbers no closure milestone must reach"
            " close_case_owner_last with milestone=None, so its checks are"
            f" unprefixed (CM-23-004); got {kwargs['milestone']!r}"
        )
        assert [leaver.client for leaver in kwargs["others"]] == [
            state.client(REPORTER)
        ]
        assert kwargs["owner"].client is state.client(COORDINATOR)

    def test_the_milestone_defaults_to_none(self):
        """The default is "numbers none", so a caller opts in to a prefix."""
        state = story_state(*CAST, case=mock_case())

        with patch.object(
            coordinated_continuations, "close_case_owner_last"
        ) as closure:
            close_the_case(state, others=(REPORTER,))

        assert closure.call_args.kwargs["milestone"] is None


# ---------------------------------------------------------------------------
# The rejection reads the CASE_MANAGER's own store (#1876)
# ---------------------------------------------------------------------------


class TestVendorRejectsInvite:
    """The rejection commits only in the CASE_MANAGER's store (CLP-10-006).

    That store lives on the dedicated case-actor container; the Coordinator's
    container cannot address it, so every post-rejection read must go through
    ``case_actor_client``.
    """

    def test_post_rejection_reads_go_through_the_case_actor_client(self):
        state = story_state(*CAST, case=mock_case())
        state.invited(VENDOR, "urn:test:invite")

        with (
            patch.object(ActorSession, "reject_case_invite"),
            patched_rejection_polls() as polls,
        ):
            vendor_rejects_invite(state)

        assert (
            polls.ledger.call_args.kwargs["client"] is state.case_actor_client
        )
        assert (
            polls.roster.call_args.kwargs["vendor_client"]
            is state.case_actor_client
        )
        assert (
            polls.rm_wait.call_args.kwargs["client"] is state.case_actor_client
        )
        assert (
            polls.rm_check.call_args.kwargs["client"]
            is state.case_actor_client
        )
