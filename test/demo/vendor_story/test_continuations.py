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
    MilestoneRead,
    mock_case,
    no_demo_banners,
    recorded_labels,
    recorded_milestone_reads,
    story_state,
)
from test.demo.vendor_story._support import SEATED, family_state
from test.support.objects import make
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
from vultron.demo.helpers.story import StoryState
from vultron.demo.helpers.vendor_story import (
    continuations as vendor_continuations,
)
from vultron.demo.utils.check_tree import CheckKind
from vultron.demo.utils.failures import demo_failures
from vultron.errors import DemoStoryError
from vultron.wire.as2.vocab.base.objects.object_types import as_Note

#: Clear the process-global failure accumulator around every test.
pytestmark = pytest.mark.usefixtures("fresh_demo_failures")


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
            recorded_labels(CheckKind.CHECK) as labels,
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


#: The fix-ready pair's reads, as :func:`recorded_milestone_reads` names them:
#: each helper mapped to the keyword arguments naming the container it read
#: and the actor the read was about.
_FIX_READY_READS = {
    "wait_for_participant_vf_state": ("client", "actor_id"),
    "verify_fix_ready": ("receiver_client", "receiver_actor_id"),
    "verify_stops_at_fix_ready": ("receiver_client", "receiver_actor_id"),
}

#: ``wait_for_participant_vf_state`` under the name the assertions read it by.
_VF_WAIT = "wait_for_participant_vf_state"


@contextlib.contextmanager
def _recorded_reads(state: StoryState) -> Iterator[list[MilestoneRead]]:
    """This family's reads, through the recorder both families share."""
    with recorded_milestone_reads(
        state, vendor_continuations, _FIX_READY_READS
    ) as reads:
        yield reads


class TestTheFixReadyMilestones:
    """The pair of milestones every scenario of this family tells."""

    @pytest.mark.spec("DEMOCI-01-003", "DEMOCI-01-010")
    def test_a_failed_milestone_is_recorded_and_the_rest_still_run(self):
        """What the `nullcontext` stub hid (#6127).

        A `demo_check` records its failure and lets execution continue; under
        the stub the assertion propagated out of the block instead, so a test
        of a continuation passed while proving nothing.
        """
        state = family_state()

        with (
            patch.object(
                vendor_continuations, "wait_for_participant_vf_state"
            ),
            patch.object(
                vendor_continuations,
                "verify_fix_ready",
                side_effect=AssertionError("the fix never landed"),
            ) as reached,
            patch.object(
                vendor_continuations,
                "verify_stops_at_fix_ready",
                side_effect=AssertionError("it deployed after all"),
            ) as stopped,
            recorded_labels(CheckKind.CHECK) as labels,
        ):
            family.the_fix_ready_milestones(state, reached="M4", stopped="M5")

        assert labels == ["M4", "M5"], "the second milestone was skipped"
        assert reached.call_count == 1
        assert stopped.call_count == 1
        assert [failure.split(":")[0] for failure in demo_failures()] == [
            "CHECK FAILED",
            "CHECK FAILED",
        ]

    @pytest.mark.spec("DEMOMA-06-002")
    def test_the_two_milestones_do_not_assert_the_same_thing(self):
        """The ratchet for #5602: neither half may become a copy of the other.

        Every vendor-first scenario reported two fix-ready milestones in a row
        whose bodies were identical, so the second one proved nothing the
        first had not.  Collapsing them back — by pointing both labels at the
        same reads — makes the two recorded lists equal and fails here.
        """
        vendors = (family.VENDOR, family.VENDOR2)
        per_half: dict[str, list[tuple[str, ...]]] = {}
        for half, teller in (
            ("reached", family.the_fix_ready_reached_the_reporter),
            ("stopped", family.the_vendors_stopped_at_vfd),
        ):
            state = family_state(family.VENDOR2)
            with (
                _recorded_reads(state) as reads,
                recorded_labels(CheckKind.CHECK) as labels,
            ):
                teller(state, check=half, vendors=vendors)
            assert labels == [half]
            per_half[half] = reads

        reached = set(per_half["reached"])
        stopped = set(per_half["stopped"])
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

    @pytest.mark.spec("DEMOMA-09-003", "DEMOMA-09-009")
    def test_the_fix_ready_half_reads_every_vendor_its_label_names(self):
        """A label naming both vendors reads both (#5602, AC-1).

        Each Vendor's fix path is its own (DEMOMA-09-009), so each gets its
        own poll on its own replica and on the Reporter's, and its own
        ``verify_fix_ready``.  Reading Vendor1 twice under a "both vendors"
        label is the over-claim #2241 was filed for.
        """
        state = family_state(family.VENDOR2)

        with _recorded_reads(state) as reads:
            family.the_fix_ready_reached_the_reporter(
                state,
                check="M4",
                vendors=(family.VENDOR, family.VENDOR2),
            )

        assert reads == [
            (_VF_WAIT, family.VENDOR, state.actor_id(family.VENDOR)),
            (_VF_WAIT, REPORTER, state.actor_id(family.VENDOR)),
            (
                "verify_fix_ready",
                family.VENDOR,
                state.actor_id(family.VENDOR),
            ),
            (_VF_WAIT, family.VENDOR2, state.actor_id(family.VENDOR2)),
            (_VF_WAIT, REPORTER, state.actor_id(family.VENDOR2)),
            (
                "verify_fix_ready",
                family.VENDOR2,
                state.actor_id(family.VENDOR2),
            ),
        ], reads

    @pytest.mark.spec("CSB-15-002")
    def test_the_ceiling_half_reads_every_vendors_missing_deployment(self):
        """ "Stops at VFd" is a claim about the d→D transition (#5602, AC-2).

        The half carrying that label reads each named Vendor's absent
        fix-deployed transition rather than repeating the VF read, and it
        polls for nothing: there is no waiting for a transition the DEPLOYER
        gate forbids.
        """
        state = family_state(family.VENDOR2)

        with _recorded_reads(state) as reads:
            family.the_vendors_stopped_at_vfd(
                state,
                check="M5",
                vendors=(family.VENDOR, family.VENDOR2),
            )

        assert reads == [
            (
                "verify_stops_at_fix_ready",
                family.VENDOR,
                state.actor_id(family.VENDOR),
            ),
            (
                "verify_stops_at_fix_ready",
                family.VENDOR2,
                state.actor_id(family.VENDOR2),
            ),
        ], reads

    @pytest.mark.spec("DEMOMA-06-002")
    def test_one_vendor_is_the_default_both_halves_read(self):
        """``rv`` has one Vendor, so neither half is told a cast."""
        state = family_state()

        with _recorded_reads(state) as reads:
            family.the_fix_ready_milestones(state, reached="M4", stopped="M5")

        assert {read[2] for read in reads} == {
            state.actor_id(family.VENDOR)
        }, reads
        assert [read[0] for read in reads] == [
            _VF_WAIT,
            _VF_WAIT,
            "verify_fix_ready",
            "verify_stops_at_fix_ready",
        ], reads


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
                "the_fix_ready_milestones",
                side_effect=lambda _s, reached, stopped, vendors: order.append(
                    f"milestones:{reached},{stopped}:{list(vendors)}"
                ),
            ),
        ):
            family.both_vendors_report_the_fix_ready(
                state, reached="M4", stopped="M5"
            )

        assert order == [
            f"notified:{family.VENDOR}:{family.VENDOR_LABEL}",
            f"notified:{family.VENDOR2}:{family.VENDOR2_LABEL}",
            # Both milestones are told both vendors: the labels name both, so
            # reading Vendor1 alone under them is the #5602 over-claim.
            f"milestones:M4,M5:{[family.VENDOR, family.VENDOR2]}",
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
        answer = make(
            as_Note, name=WORKAROUND_ANSWER_NAME, content=WORKAROUND_ANSWER
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
            recorded_labels(CheckKind.CHECK) as labels,
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
            recorded_labels(CheckKind.CHECK) as labels,
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
