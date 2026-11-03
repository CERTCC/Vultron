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

"""Continuations more than one vendor-first scenario tells (#5536).

Pins :mod:`vultron.demo.helpers.vendor_story.continuations`: the
participant milestone, the fix-ready checks, the joiners' notes, the
embargo's end and the final disclosure check.  Each milestone's label is
the caller's, so the labels are what these tests pin.
"""

import contextlib
from collections.abc import Iterator
from unittest.mock import patch

import pytest

from test.demo._helpers import (
    mock_case,
    no_demo_banners,
    story_state,
)
from test.demo.vendor_story._support import SEATED, family_state
from vultron.core.states.cs import CS_vf
from vultron.demo.helpers import (
    vendor_story as family,
)
from vultron.demo.helpers.coordinated_story import (
    REPORTER,
)
from vultron.demo.helpers.notes import (
    WORKAROUND_ANSWER,
    WORKAROUND_ANSWER_NAME,
    NotePost,
)
from vultron.demo.helpers.vendor_story import (
    continuations as vendor_continuations,
)
from vultron.errors import DemoStoryError
from vultron.wire.as2.vocab.base.objects.object_types import as_Note

#: Clear the process-global failure accumulator around every test.
pytestmark = pytest.mark.usefixtures("fresh_demo_failures")


@contextlib.contextmanager
def _recording_checks() -> Iterator[list[str]]:
    """Stub the continuations' ``demo_check`` and collect its labels.

    Each milestone's label is the *caller's* — a scenario numbers its own
    milestones — so the labels are what a test of a shared continuation can
    pin, and a mock that only swallows them would prove nothing.
    """
    labels: list[str] = []

    def _check(label: str):
        labels.append(label)
        return contextlib.nullcontext()

    with patch.object(vendor_continuations, "demo_check", side_effect=_check):
        yield labels


# ---------------------------------------------------------------------------
# Continuations shared by more than one scenario of the family
# ---------------------------------------------------------------------------


class TestRequiredParticipantsArePresent:
    """The roster milestone, read from Vendor1's replica."""

    @pytest.mark.spec("DEMOCI-01-011")
    def test_the_milestone_reads_the_roster_prop_first(self):
        """Participants that were never seated are not worth checking.

        A roster that never arrived stops the story here, rather than failing
        a milestone whose cause is already recorded above it.
        """
        state = story_state(*SEATED, case=mock_case())

        with (
            patch.object(
                vendor_continuations, "verify_case_active"
            ) as milestone,
            no_demo_banners(family),
            pytest.raises(DemoStoryError, match="roster the Vendor"),
        ):
            family.required_participants_are_present(state, check="M1")

        milestone.assert_not_called()

    @pytest.mark.spec("VP-02-015")
    def test_the_milestone_reads_vendor1s_replica_and_the_reporters(self):
        """Vendor1 holds the case from its own triage, owner or not.

        The reads are the same in all four scenarios; only the label differs,
        because each numbers its own milestones and names the participants it
        expects by then.
        """
        state = family_state()

        with (
            patch.object(
                vendor_continuations, "verify_case_active"
            ) as milestone,
            _recording_checks() as labels,
        ):
            family.required_participants_are_present(
                state, check="M1: required participants (≥2), EM.ACTIVE"
            )

        assert labels == ["M1: required participants (≥2), EM.ACTIVE"]
        kwargs = milestone.call_args.kwargs
        assert kwargs["receiver_client"] is state.client(family.VENDOR)
        assert kwargs["reporter_client"] is state.client(REPORTER)
        assert kwargs["case_id"] == state.case.id_
        assert kwargs["receiver_actor_id"] == state.actor_id(family.VENDOR)
        assert kwargs["reporter_actor_id"] == state.actor_id(REPORTER)


class TestTheFixReadyReachedTheReporter:
    """One copy of the check every scenario of the family makes twice."""

    @pytest.mark.spec("DEMOMA-17-002")
    def test_each_milestone_label_repeats_the_same_check(self):
        """A consolidation must not change what a scenario passes on.

        The second milestone asserts exactly what the first does — ``rv``'s
        M4 and M5, ``rvcv-extension``'s M5 and M6 — so the repetition is kept
        as it was and #5607 tracks making the pair say two different things.
        """
        state = family_state()

        with (
            patch.object(
                vendor_continuations, "wait_for_participant_vf_state"
            ) as vf_wait,
            patch.object(
                vendor_continuations, "verify_fix_ready"
            ) as milestone,
            _recording_checks() as labels,
        ):
            family.the_fix_ready_reached_the_reporter(
                state, milestones=("M4", "M5")
            )

        assert labels == ["M4", "M5"]
        assert milestone.call_count == 2
        # Vendor1's own VF state, read on its replica and on the Reporter's,
        # once per milestone.
        assert [c.kwargs["client"] for c in vf_wait.call_args_list] == [
            state.client(family.VENDOR),
            state.client(REPORTER),
            state.client(family.VENDOR),
            state.client(REPORTER),
        ]
        assert all(
            c.kwargs["actor_id"] == state.actor_id(family.VENDOR)
            and c.kwargs["expected_states"] == {CS_vf.VF}
            for c in vf_wait.call_args_list
        )
        kwargs = milestone.call_args.kwargs
        assert kwargs["receiver_client"] is state.client(family.VENDOR)
        assert kwargs["reporter_client"] is state.client(REPORTER)
        assert kwargs["receiver_actor_id"] == state.actor_id(family.VENDOR)


class TestBothVendorsReportTheFixReady:
    """Both vendors stop at VFd, each gated on its own RM state."""

    @pytest.mark.spec("CSB-15-002")
    def test_vendor1_notifies_then_vendor2_then_the_milestones_run(self):
        """The order is the one every two-vendor sibling told.

        Each trigger is refused until that vendor's own participant record is
        out of triage, which is the gate inside ``vendor_notifies_fix_ready``
        (CSB-18-001); the milestones that read both follow the two triggers.
        """
        state = family_state(family.VENDOR2)
        order: list[str] = []

        with (
            patch.object(
                vendor_continuations,
                "vendor_notifies_fix_ready",
                side_effect=lambda _s, name, label: order.append(
                    f"notified:{name}:{label}"
                ),
            ),
            patch.object(
                vendor_continuations,
                "the_fix_ready_reached_the_reporter",
                side_effect=lambda _s, milestones: order.append(
                    f"milestones:{list(milestones)}"
                ),
            ),
        ):
            family.both_vendors_report_the_fix_ready(
                state, milestones=("M4", "M5")
            )

        assert order == [
            f"notified:{family.VENDOR}:{family.VENDOR_LABEL}",
            f"notified:{family.VENDOR2}:{family.VENDOR2_LABEL}",
            "milestones:['M4', 'M5']",
        ], order


class TestTheJoinersAddTheirNotes:
    """The actors that joined after the opening answer its thread."""

    @pytest.mark.spec("DEMOCI-11-017")
    def test_the_posts_thread_onto_the_vendors_answer(self):
        """The thread the opening shares with every sibling stays one thread.

        The joiners reply to the Vendor's answer rather than opening a thread
        of their own, and post through Vendor1's replica, which every
        scenario of the family watches.
        """
        state = family_state(family.VENDOR2)
        answer = as_Note(
            name=WORKAROUND_ANSWER_NAME, content=WORKAROUND_ANSWER
        )
        state.keep(family.VENDORS_ANSWER, answer)
        updates = [
            NotePost(state.actor(family.VENDOR2), "Vendor2 Update", "ours")
        ]

        with patch.object(vendor_continuations, "add_note_thread") as thread:
            family.the_joiners_add_their_notes(state, updates)

        watching, case, posts = thread.call_args.args
        assert watching is state.client(family.VENDOR)
        assert case is state.case
        assert posts is updates
        assert thread.call_args.kwargs["in_reply_to"] is answer

    @pytest.mark.spec("DEMOCI-01-011")
    def test_an_answer_that_never_landed_stops_the_story(self):
        """A thread whose answer never landed has nothing to reply to.

        Posting anyway would put an unthreaded note on the case that the
        scenario's own note assertions do not describe.
        """
        state = family_state(family.VENDOR2)

        with (
            patch.object(vendor_continuations, "add_note_thread") as thread,
            pytest.raises(DemoStoryError, match="workaround answer"),
        ):
            family.the_joiners_add_their_notes(state, [])

        thread.assert_not_called()


class TestTheEmbargoEndsFor:
    """The termination is read on the replica the next step depends on."""

    @pytest.mark.spec("DEMOMA-07-003")
    def test_only_the_named_watchers_replica_is_read(self):
        """The Case Owner's ``notify-published`` is what ends the embargo.

        Each scenario reads the termination on the replica its own next step
        depends on, so both the label and the watcher are the caller's and
        nothing else is read.
        """
        state = family_state(family.VENDOR2)

        with (
            patch.object(
                vendor_continuations, "wait_for_case_em_terminated"
            ) as em_wait,
            _recording_checks() as labels,
        ):
            family.the_embargo_ends_for(
                state, check="Embargo terminated", watcher=family.VENDOR2
            )

        assert labels == ["Embargo terminated"]
        assert [c.kwargs["client"] for c in em_wait.call_args_list] == [
            state.client(family.VENDOR2)
        ]
        assert em_wait.call_args.kwargs["case_id"] == state.case.id_


class TestTheDisclosureReachedEveryReplica:
    """The final publication milestone: EM.EXITED, VF and CS.VFdPxa."""

    def test_the_embargo_watch_defaults_to_the_reporter_alone(self):
        """Three of the four scenarios publish as the owner first.

        Their Reporter is the last to be told, so its replica reading
        ``EM.EXITED`` is what the milestone turns on; a scenario whose owner
        publishes last names every participant instead.
        """
        state = family_state()

        with (
            patch.object(
                vendor_continuations, "wait_for_case_em_terminated"
            ) as em_wait,
            patch.object(
                vendor_continuations, "wait_for_participant_vf_state"
            ),
            patch.object(vendor_continuations, "verify_publicly_disclosed"),
            _recording_checks() as labels,
        ):
            family.the_disclosure_reached_every_replica(state, check="M7")

        assert labels == ["M7"]
        assert [c.kwargs["client"] for c in em_wait.call_args_list] == [
            state.client(REPORTER)
        ]

    def test_every_named_watcher_is_read_in_the_handoff_order(self):
        """``rvcv-handoff``'s owner publishes last, so all four are read.

        The watchers are read in the order given and no other replica is
        touched: the milestone reports what the caller declared, not a set it
        derived.
        """
        state = family_state("coordinator", family.VENDOR2)
        watchers = ("coordinator", family.VENDOR, family.VENDOR2, REPORTER)

        with (
            patch.object(
                vendor_continuations, "wait_for_case_em_terminated"
            ) as em_wait,
            patch.object(
                vendor_continuations, "wait_for_participant_vf_state"
            ),
            patch.object(vendor_continuations, "verify_publicly_disclosed"),
            no_demo_banners(family),
        ):
            family.the_disclosure_reached_every_replica(
                state, check="M7", em_watchers=watchers
            )

        assert [c.kwargs["client"] for c in em_wait.call_args_list] == [
            state.client(who) for who in watchers
        ]

    @pytest.mark.spec("DEMOMA-15-001")
    def test_the_vf_and_disclosure_checks_name_vendor1(self):
        """Vendor1 is the participant with the fix path in all four.

        Its VF state is read on its own replica and on the Reporter's,
        whatever the embargo watch named.
        """
        state = family_state()

        with (
            patch.object(vendor_continuations, "wait_for_case_em_terminated"),
            patch.object(
                vendor_continuations, "wait_for_participant_vf_state"
            ) as vf_wait,
            patch.object(
                vendor_continuations, "verify_publicly_disclosed"
            ) as disclosed,
            no_demo_banners(family),
        ):
            family.the_disclosure_reached_every_replica(state, check="M7")

        assert [c.kwargs["client"] for c in vf_wait.call_args_list] == [
            state.client(family.VENDOR),
            state.client(REPORTER),
        ]
        assert all(
            c.kwargs["actor_id"] == state.actor_id(family.VENDOR)
            and c.kwargs["expected_states"] == {CS_vf.VF}
            for c in vf_wait.call_args_list
        )
        kwargs = disclosed.call_args.kwargs
        assert kwargs["receiver_client"] is state.client(family.VENDOR)
        assert kwargs["reporter_client"] is state.client(REPORTER)
        assert kwargs["receiver_actor_id"] == state.actor_id(family.VENDOR)
