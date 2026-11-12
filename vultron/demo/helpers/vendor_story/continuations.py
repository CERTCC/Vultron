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
"""Continuations more than one vendor-first scenario tells.

The participant milestone, the fix-ready checks, the joiners' notes, and
the embargo's end and the final disclosure check, each read on the
replicas the scenario names.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from vultron.core.states.cs import CS_vf
from vultron.demo.helpers.coordinated_story import (
    REPORTER,
    close_the_case,
    reports_published,
    vendor_notifies_fix_ready,
)
from vultron.demo.helpers.milestones import (
    verify_case_active,
    verify_fix_ready,
    verify_publicly_disclosed,
    verify_stops_at_fix_ready,
)
from vultron.demo.helpers.notes import NotePost, add_note_thread
from vultron.demo.helpers.polling import (
    wait_for_case_em_terminated,
    wait_for_participant_vf_state,
)
from vultron.demo.helpers.story import StoryState
from vultron.demo.helpers.vendor_story.cast import (
    VENDOR,
    VENDOR2,
    VENDOR2_LABEL,
    VENDOR_LABEL,
)
from vultron.demo.helpers.vendor_story.opening import (
    THE_VENDORS_CASE,
    VENDORS_ANSWER,
)
from vultron.demo.utils import demo_check, demo_gate

logger = logging.getLogger(__name__)


def required_participants_are_present(
    state: StoryState, *, check: str
) -> None:
    """The case holds every participant invited so far, and is still embargoed.

    Read from the first Vendor's replica, which holds the case from the moment
    it engaged it whether or not it is still the owner.  Each scenario numbers
    this milestone itself and names the participants it expects by then, so the
    label is the caller's; the reads are the same in all four.

    Reads :data:`THE_VENDORS_CASE` first, so a roster that never arrived stops
    the story here instead of checking participants that were never seated
    (DEMOCI-01-011).

    Args:
        state: The running story's state.
        check: This scenario's ``demo_check`` label for the milestone.
    """
    state.kept(THE_VENDORS_CASE)
    with demo_check(check):
        verify_case_active(
            receiver_client=state.client(VENDOR),
            reporter_client=state.client(REPORTER),
            case_id=state.case.id_,
            receiver_actor_id=state.actor_id(VENDOR),
            reporter_actor_id=state.actor_id(REPORTER),
        )


def the_fix_ready_reached_the_reporter(
    state: StoryState,
    *,
    check: str,
    vendors: Sequence[str] = (VENDOR,),
) -> None:
    """Each named Vendor reads VF on its own and on the Reporter's replica.

    The first half of the pair (:func:`the_fix_ready_milestones`): the f→F
    transition each Vendor made, read on its own replica and on the
    Reporter's, then verified for each (DEMOMA-06-002).  Every named Vendor is
    read, so a scenario whose milestone label says "both vendors" checks both
    — reading Vendor1 alone under that label is the over-claim #5602 was filed
    for.  Each Vendor's own fix path is independent (DEMOMA-09-009), so each
    gets its own poll pair and its own verification.

    One ``demo_check`` covers them all, because the scenario reports one
    milestone label: the block fails as a unit, so a Vendor1 shortfall is
    recorded before Vendor2 is read.  A block per Vendor would need a label
    per Vendor, which is a scenario's call and not this helper's.

    Args:
        state: The running story's state.
        check: This scenario's ``demo_check`` label for the milestone.
        vendors: The cast names whose fix paths the label names.
    """
    with demo_check(check):
        for vendor in vendors:
            for watcher in (vendor, REPORTER):
                wait_for_participant_vf_state(
                    client=state.client(watcher),
                    case_id=state.case.id_,
                    actor_id=state.actor_id(vendor),
                    expected_states={CS_vf.VF},
                )
            verify_fix_ready(
                receiver_client=state.client(vendor),
                reporter_client=state.client(REPORTER),
                case_id=state.case.id_,
                receiver_actor_id=state.actor_id(vendor),
            )


def the_vendors_stopped_at_vfd(
    state: StoryState,
    *,
    check: str,
    vendors: Sequence[str] = (VENDOR,),
) -> None:
    """Each named Vendor's replicas record no fix-deployed transition.

    The second half of the pair: what
    :func:`the_fix_ready_reached_the_reporter` does **not** say.  Each named
    Vendor holds ``CVDRole.VENDOR`` and not ``DEPLOYER``, so VFd is its
    ceiling (CSB-15-002), and the milestone whose label says so reads the d→D
    transition that never happened rather than repeating the VF read.

    Args:
        state: The running story's state.
        check: This scenario's ``demo_check`` label for the milestone.
        vendors: The cast names whose fix paths the label names.
    """
    with demo_check(check):
        for vendor in vendors:
            verify_stops_at_fix_ready(
                receiver_client=state.client(vendor),
                reporter_client=state.client(REPORTER),
                case_id=state.case.id_,
                receiver_actor_id=state.actor_id(vendor),
            )


def the_fix_ready_milestones(
    state: StoryState,
    *,
    reached: str,
    stopped: str,
    vendors: Sequence[str] = (VENDOR,),
) -> None:
    """The two fix-ready milestones every scenario of this family tells.

    The pair used to be one check told twice under two labels — ``rv``'s M4
    and M5, ``rvv``'s M4 and M5, ``rvcv-extension``'s M5 and M6, and
    ``rvcv-handoff``'s two unnumbered ones — which made the second milestone
    assert exactly what the first did (#5602).  The two labels are separate
    parameters rather than a sequence, so neither half can be handed the
    other's label without saying which is which.

    Args:
        state: The running story's state.
        reached: This scenario's label for the fix-ready milestone.
        stopped: This scenario's label for the VFd-ceiling milestone.
        vendors: The cast names both labels name.
    """
    the_fix_ready_reached_the_reporter(state, check=reached, vendors=vendors)
    the_vendors_stopped_at_vfd(state, check=stopped, vendors=vendors)


def both_vendors_report_the_fix_ready(
    state: StoryState, *, reached: str, stopped: str
) -> None:
    """Each Vendor reports fix ready (VFd), gated on its own RM state.

    Both hold ``CVDRole.VENDOR`` and not ``DEPLOYER``, so both stop at VFd
    (CSB-15-002); each trigger is refused until that vendor's own participant
    record is out of triage, which is the gate
    (:func:`~vultron.demo.helpers.coordinated_story\
    .vendor_notifies_fix_ready`, CSB-18-001).  Told by every scenario of this
    family that has a second Vendor, so both milestones read both Vendors.

    Args:
        state: The running story's state.
        reached: This scenario's label for the fix-ready milestone.
        stopped: This scenario's label for the VFd-ceiling milestone.
    """
    for name, label in ((VENDOR, VENDOR_LABEL), (VENDOR2, VENDOR2_LABEL)):
        vendor_notifies_fix_ready(state, name, label)
    the_fix_ready_milestones(
        state, reached=reached, stopped=stopped, vendors=(VENDOR, VENDOR2)
    )


def the_joiners_add_their_notes(
    state: StoryState, updates: Sequence[NotePost]
) -> None:
    """The actors that joined after the opening answer the thread it posted.

    They reply to the Vendor's answer rather than opening a thread of their
    own, so the thread the opening shares with every sibling stays one thread
    (:data:`VENDORS_ANSWER`, DEMOCI-11-017).  Posted through the first
    Vendor's replica, which every scenario of the family watches.

    Reads :data:`VENDORS_ANSWER` first: a thread whose answer never landed has
    nothing to reply to, so the story stops here rather than posting an
    unthreaded note the scenario's note assertions do not describe
    (DEMOCI-01-011).

    Args:
        state: The running story's state.
        updates: The posts that follow the Vendor's answer, in order.
    """
    answered = state.kept(VENDORS_ANSWER)
    add_note_thread(
        state.client(VENDOR), state.case, updates, in_reply_to=answered
    )
    logger.info(
        "✓ Notes exchange complete (the joiners' notes added to the thread)"
    )


def the_embargo_ends_for(
    state: StoryState, *, check: str, watcher: str
) -> None:
    """*watcher*'s replica reads ``EM.EXITED``.

    Per DEMOMA-07-003(4) the Case Owner's ``notify-published`` is what ends
    the embargo, and each scenario reads the termination on the replica its
    own next step depends on, so the label and the watcher are the caller's.

    Args:
        state: The running story's state.
        check: This scenario's ``demo_check`` label.
        watcher: The cast name whose replica is read.
    """
    with demo_check(check):
        wait_for_case_em_terminated(
            client=state.client(watcher), case_id=state.case.id_
        )


def the_disclosure_reached_every_replica(
    state: StoryState, *, check: str, em_watchers: Sequence[str] = (REPORTER,)
) -> None:
    """The final publication milestone: EM.EXITED, VF and CS.VFdPxa.

    The last check of every scenario of this family, which differs only in
    whose replicas it reads ``EM.EXITED`` on: the Reporter's alone in the
    three whose owner published first, and every participant's in
    ``rvcv-handoff``, where the owner publishes last.

    Args:
        state: The running story's state.
        check: This scenario's ``demo_check`` label for the milestone.
        em_watchers: The cast names whose replicas must read ``EM.EXITED``.
    """
    with demo_check(check):
        for who in em_watchers:
            wait_for_case_em_terminated(
                client=state.client(who), case_id=state.case.id_
            )
        for who in (VENDOR, REPORTER):
            wait_for_participant_vf_state(
                client=state.client(who),
                case_id=state.case.id_,
                actor_id=state.actor_id(VENDOR),
                expected_states={CS_vf.VF},
            )
        verify_publicly_disclosed(
            receiver_client=state.client(VENDOR),
            reporter_client=state.client(REPORTER),
            case_id=state.case.id_,
            receiver_actor_id=state.actor_id(VENDOR),
        )


# ---------------------------------------------------------------------------
# The two-party ending: the Vendor's fix, the disclosure and the closure
# ---------------------------------------------------------------------------
#
# Told by ``rv`` and ``rv-csaf``, whose cases hold only the Reporter and the
# Vendor once the case is open.  The milestone labels are both scenarios'
# (M4 to M7): the two number their earlier milestones to match.


def the_vendor_reports_the_fix_ready(state: StoryState) -> None:
    """The Vendor reports fix ready and stops at VFd (CSB-15-002).

    The milestone checks nest inside the trigger's gate and inside a gate on
    the Reporter's replica, so a refused trigger or a replica that never
    caught up skips them rather than comparing state that was never written
    (CSB-18-001, DEMOCI-01-011).
    """
    vendor_notifies_fix_ready(
        state,
        VENDOR,
        VENDOR_LABEL,
        then=lambda: _the_reporter_replica_reflects_the_fix(state),
    )


def _the_reporter_replica_reflects_the_fix(state: StoryState) -> None:
    """The M4 and M5 milestones, inside the gate on the Reporter's replica."""
    with demo_gate("M4/M5: reporter replica reflects fix-ready vf_state"):
        wait_for_participant_vf_state(
            client=state.client(REPORTER),
            case_id=state.case.id_,
            actor_id=state.actor_id(VENDOR),
            expected_states={CS_vf.VF},
        )
        the_fix_ready_milestones(
            state,
            reached="M4: both replicas show CS includes F (fix ready)",
            stopped="M5: both replicas show the vendor stopped at VFd — no"
            " fix-deployed transition",
        )


def both_publish(state: StoryState) -> None:
    """The Vendor, the Case Owner, publishes first; then the Reporter."""
    reports_published(state, VENDOR)
    the_embargo_ends_for(
        state,
        check="Embargo terminated (EM.EXITED) after Vendor reports published",
        watcher=VENDOR,
    )
    reports_published(state, REPORTER)
    the_disclosure_reached_every_replica(
        state,
        check=(
            "M6: both replicas CS.VFdPxa, EM.EXITED, vendor participant is "
            "public-aware"
        ),
    )


def both_close(state: StoryState) -> None:
    """The Reporter leaves; the Vendor, the Case Owner, leaves last."""
    close_the_case(state, others=(REPORTER,), owner=VENDOR, milestone="M7")


__all__ = [
    "both_close",
    "both_publish",
    "both_vendors_report_the_fix_ready",
    "required_participants_are_present",
    "the_disclosure_reached_every_replica",
    "the_embargo_ends_for",
    "the_fix_ready_milestones",
    "the_fix_ready_reached_the_reporter",
    "the_joiners_add_their_notes",
    "the_vendor_reports_the_fix_ready",
    "the_vendors_stopped_at_vfd",
]
