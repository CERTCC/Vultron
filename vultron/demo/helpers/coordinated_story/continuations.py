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

What follows a branch point of the opening: the Vendor's rejection and the
Reporter's follow-up, the fix-ready report and the Coordinator's view of it,
publication and the embargo's end, and the case's closure with the Case
Owner leaving last.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence

from vultron.core.states.cs import CS_vf
from vultron.core.states.rm import RM
from vultron.demo.helpers.closure import CaseLeaver, close_case_owner_last
from vultron.demo.helpers.coordinated_story.cast import (
    COORDINATOR,
    COORDINATOR_LABEL,
    REPORTER,
    REPORTER_LABEL,
    VENDOR,
    VENDOR_LABEL,
)
from vultron.demo.helpers.invite_chain import answer_case_invite
from vultron.demo.helpers.milestones import (
    verify_fix_ready,
    verify_publicly_disclosed,
)
from vultron.demo.helpers.notes import NotePost, add_note_thread
from vultron.demo.helpers.polling import (
    wait_for_case_em_terminated,
    wait_for_case_participants,
    wait_for_participant_rm_state,
    wait_for_participant_vf_state,
    wait_for_semantic_type_in_ledger,
)
from vultron.demo.helpers.story import StoryState
from vultron.demo.helpers.sync import run_sync_verification_phase
from vultron.demo.helpers.verification import _check_participant_rm_state_in
from vultron.demo.utils import demo_check, demo_gate, demo_step, ref_id

logger = logging.getLogger(__name__)


def vendor_rejects_invite(state: StoryState) -> None:
    """The Vendor rejects the Invite and never becomes an active participant.

    The Vendor sends ``Reject(Invite(Actor)[target=VulnerabilityCaseStub])`` and the
    CaseActor records a ``reject_invite_actor_to_case`` entry.  At invite-send
    time ``CreateInertInviteeParticipantNode`` already seated the Vendor as an
    inert participant (``joined=False``, RM ``RECEIVED``; ADR-0114,
    CM-11-006); after the Reject, CM-11-007 moves that record to RM
    ``CLOSED``.  The Vendor is in the index and was never active, and no case
    content is delivered to it (DEMOMA-27-008, DEMOMA-27-010).
    """
    vendor = state.actor(VENDOR).actor
    answer_case_invite(
        invite_id=state.delivered_invite(VENDOR),
        case=state.case,
        invitee_name=VENDOR_LABEL,
        invitee_client=state.client(VENDOR),
        invitee=vendor,
        invitee_in_own_container=vendor,
        respond="reject",
    )

    # Gate on the Reject being committed before checking participant state.
    # The Reject is a case event, admitted and ledgered like an Accept
    # (CLP-02-012).  It is self-contained on the CaseActor (CLP-10-006) — no
    # participant-effect Announce is sent, so the entry is only visible in the
    # CaseActor's own store, on the dedicated case-actor container.  A
    # demo_gate here skips the participant checks rather than running them
    # against stale state.
    with demo_gate(
        "reject_invite_actor_to_case committed (causal gate before "
        "participant state check)"
    ):
        wait_for_semantic_type_in_ledger(
            client=state.case_actor_client,
            case_id=state.case.id_,
            semantic_type="reject_invite_actor_to_case",
        )
        # Read from the CASE_MANAGER's own store: a replica stores the record
        # the CASE_MANAGER's create_case_participant entry carries (ADR-0114),
        # but this scenario checks the record
        # CreateInertInviteeParticipantNode wrote.
        with demo_check(
            f"{VENDOR_LABEL} in actor_participant_index after invite "
            "(inert record, CM-11-006)"
        ):
            wait_for_case_participants(
                vendor_client=state.case_actor_client,
                case_id=state.case.id_,
                expected_actor_ids={
                    state.actor_id(REPORTER),
                    state.actor_id(COORDINATOR),
                    state.actor_id(VENDOR),
                },
            )
        # The reject tree commits the ledger entry (the gate above) BEFORE its
        # ApplyInviteRejectToParticipantNode effect writes RM.CLOSED, so the
        # committed-entry gate proves the handler started, not that the RM
        # close landed (EDF-06-002, EDF-06-003).  Wait on the committed effect
        # itself before the one-shot check.
        wait_for_participant_rm_state(
            client=state.case_actor_client,
            case_id=str(state.case.id_),
            actor_id=state.actor_id(VENDOR),
            expected_states={RM.CLOSED},
        )
        with demo_check(
            f"{VENDOR_LABEL} participant at RM.CLOSED after rejection "
            "(never active, DEMOMA-27-008)"
        ):
            _check_participant_rm_state_in(
                client=state.case_actor_client,
                case_id=str(state.case.id_),
                actor_id=state.actor_id(VENDOR),
                expected_states={RM.CLOSED},
                label=f"{VENDOR_LABEL} (rejected invitee)",
            )
    logger.info(
        "✓ M2: %s rejected invite — inert record at RM.CLOSED, never active"
        " (DEMOMA-27-008)",
        VENDOR_LABEL,
    )


def reporter_replica_converges(state: StoryState) -> None:
    """The Reporter's replica catches up with the case, the Vendor having left.

    The Reporter must hold the case and every Coordinator-committed entry
    before the notes exchange: without this gate the ``add-note-to-case``
    trigger on the Reporter's container can fail, because its DataLayer has
    not yet received the case replica or the ledger tail (SYNC-15-001).  The
    Vendor declined, so this fragment declares no participant expectation and
    no replica state check.
    """
    run_sync_verification_phase(
        auth_client=state.client(COORDINATOR),
        auth_label=COORDINATOR_LABEL,
        auth_actor_id=state.actor_id(COORDINATOR),
        reporter_client=state.client(REPORTER),
        reporter_actor_id=state.actor_id(REPORTER),
        replicas=[(state.client(REPORTER), REPORTER_LABEL)],
        case_id=state.case.id_,
    )


def reporter_asks_about_the_rejection(state: StoryState) -> None:
    """The Reporter asks what happens now the Vendor has declined."""
    add_note_thread(
        state.client(COORDINATOR),
        state.case,
        [
            NotePost(
                state.actor(REPORTER),
                "Question from Reporter",
                "Vendor rejected the invitation. "
                "What is the plan for coordinated disclosure?",
            ),
            NotePost(
                state.actor(COORDINATOR),
                "Coordinator Response",
                "Vendor declined to participate. "
                "We will proceed with Reporter-only disclosure. "
                "Embargo will be terminated and we will publish.",
            ),
        ],
    )
    logger.info(
        "✓ Notes exchange complete (two notes committed to case ledger)"
    )


def vendor_notifies_fix_ready(
    state: StoryState,
    name: str,
    label: str,
    *,
    then: Callable[[], None] | None = None,
) -> None:
    """*name* reports fix ready (VFd), gated on its own RM state.

    CSB-18-001: the trigger is refused until the vendor's own participant
    record is out of triage, so the gate reads that record first and *then*
    runs, skipping the trigger and everything after it when it never arrives.
    The vendor holds ``CVDRole.VENDOR`` and not ``DEPLOYER``, so it stops at
    VFd (CSB-15-002).

    Args:
        state: The running story's state.
        name: The reporting vendor's cast name.
        label: What this scenario calls it in step labels.
        then: Runs inside the gate, after the vendor's own VF check — what a
            scenario checks on the coordinator side before moving on.  Inside
            the gate so a refused trigger skips it rather than comparing
            replicas that were never written.
    """
    vendor = state.actor(name).actor
    with demo_gate(
        f"{name} RM ∈ {{ACCEPTED,DEFERRED,CLOSED}} before notify-fix-ready"
        " (CSB-18-001)"
    ):
        wait_for_participant_rm_state(
            client=state.client(name),
            case_id=state.case.id_,
            actor_id=vendor.id_,
            expected_states={RM.ACCEPTED, RM.DEFERRED, RM.CLOSED},
        )
        with demo_step(f"Actor {ref_id(vendor)} reports fix ready"):
            state.actor(name).with_case(state.case).quiet().notify_fix_ready()

        with demo_check(f"{label} participant vf_state transitions to VF"):
            wait_for_participant_vf_state(
                client=state.client(name),
                case_id=state.case.id_,
                actor_id=vendor.id_,
                expected_states={CS_vf.VF},
            )

        if then is not None:
            then()


def report_fix_ready(state: StoryState, name: str, label: str) -> None:
    """*name* reports fix ready and the Coordinator sees it.

    :func:`vendor_notifies_fix_ready` plus the Coordinator-side milestones, for
    a scenario with one vendor to check.  A scenario with two batches its
    coordinator-side checks over both instead and calls the notify half
    directly.
    """
    vendor_notifies_fix_ready(
        state,
        name,
        label,
        then=lambda: _coordinator_sees_fix_ready_twice(state, name, label),
    )


def _coordinator_sees_fix_ready_twice(
    state: StoryState, name: str, label: str
) -> None:
    """The M4 and M5 milestones, which read the same thing under two names."""
    _coordinator_sees_fix_ready(
        state,
        name,
        f"M4: Coordinator replica shows {label} CS includes F (fix ready)",
    )
    _coordinator_sees_fix_ready(
        state,
        name,
        f"M5: Coordinator replica shows {label} CS includes F (fix ready)"
        f" — {label} stops at VFd",
    )


def _coordinator_sees_fix_ready(
    state: StoryState, name: str, check: str
) -> None:
    """Wait for, then verify, the Coordinator's view of *name* at VF.

    Owns its own ``demo_check`` rather than being called inside one, so the
    raising wait sits in a demo context where it is written (DEMOCI-01-011).
    """
    with demo_check(check):
        wait_for_participant_vf_state(
            client=state.client(COORDINATOR),
            case_id=state.case.id_,
            actor_id=state.actor_id(name),
            expected_states={CS_vf.VF},
        )
        verify_fix_ready(
            receiver_client=state.client(COORDINATOR),
            reporter_client=state.client(name),
            case_id=state.case.id_,
            receiver_actor_id=state.actor_id(name),
        )


def vendor_reports_the_fix_ready(state: StoryState) -> None:
    """The Vendor reports fix ready and stops at VFd (CSB-15-002)."""
    report_fix_ready(state, VENDOR, VENDOR_LABEL)


def everyone_publishes(state: StoryState) -> None:
    """Each participant reports public disclosure, the Coordinator first.

    Per DEMOMA-07-003(4) the Coordinator, as CASE_OWNER, triggers CS.P.  The
    embargo is ended by then in ``rcv-embargo`` and still active in ``rcv``;
    either way it reads ``EM.EXITED`` once the Coordinator has reported.  In
    ``rcv-embargo`` the two ``EM.EXITED`` checks below only confirm what the
    termination fragment already established; in ``rcv`` they check the
    embargo ending at publication.
    """
    the_coordinator_publishes_and_the_embargo_ends(state)

    reports_published(state, VENDOR)
    reports_published(state, REPORTER)

    with demo_check(
        "M6: all replicas CS.VFdPxa, EM.EXITED, all participants public-aware"
    ):
        wait_for_case_em_terminated(
            client=state.client(VENDOR), case_id=state.case.id_
        )
        for name in (COORDINATOR, REPORTER):
            wait_for_participant_vf_state(
                client=state.client(name),
                case_id=state.case.id_,
                actor_id=state.actor_id(VENDOR),
                expected_states={CS_vf.VF},
            )
        verify_publicly_disclosed(
            receiver_client=state.client(COORDINATOR),
            reporter_client=state.client(REPORTER),
            case_id=state.case.id_,
            receiver_actor_id=state.actor_id(VENDOR),
        )


def the_coordinator_publishes_and_the_embargo_ends(state: StoryState) -> None:
    """The Coordinator, as CASE_OWNER, triggers CS.P; the embargo exits.

    Per DEMOMA-07-003(4) the Coordinator reports first, and the embargo reads
    ``EM.EXITED`` once it has: in ``rcv`` that is the embargo ending at
    publication, and in ``rcv-embargo`` it confirms the termination the
    scenario already asserted.  One copy for every continuation that starts
    this way, whether the Vendor joined or declined.
    """
    reports_published(state, COORDINATOR)

    with demo_check(
        "Embargo terminated (EM.EXITED) after Coordinator reports published"
    ):
        wait_for_case_em_terminated(
            client=state.client(COORDINATOR), case_id=state.case.id_
        )


def reports_published(state: StoryState, name: str) -> None:
    """*name* triggers CS.P from its own container.

    One copy for every scenario of the family: the order its participants
    report in differs, and the step itself does not.
    """
    session = state.actor(name)
    with demo_step(
        f"Actor {ref_id(session.actor)} reports vulnerability"
        " publicly disclosed"
    ):
        session.with_case(state.case).quiet().notify_published()


def coordinator_and_reporter_publish(state: StoryState) -> None:
    """The Coordinator then the Reporter report published; the embargo ends.

    The two-party form of :func:`everyone_publishes`, for a story whose Vendor
    declined: the Coordinator, as CASE_OWNER, triggers CS.P (DEMOMA-07-003(4))
    and the embargo terminates (EM.EXITED).
    """
    the_coordinator_publishes_and_the_embargo_ends(state)

    reports_published(state, REPORTER)

    with demo_check("M3: EM.EXITED, Coordinator and Reporter public-aware"):
        wait_for_case_em_terminated(
            client=state.client(REPORTER), case_id=state.case.id_
        )
        verify_publicly_disclosed(
            receiver_client=state.client(COORDINATOR),
            reporter_client=state.client(REPORTER),
            case_id=state.case.id_,
            receiver_actor_id=state.actor_id(COORDINATOR),
        )


def close_the_case(
    state: StoryState,
    *,
    others: Sequence[str],
    owner: str = COORDINATOR,
    milestone: str | None = None,
) -> None:
    """*others* leave the case in order; *owner*, the Case Owner, leaves last.

    The owner leaves once the others' departures are recorded in the
    CASE_MANAGER's store (CM-23-015).  Every closure is verified there,
    through the dedicated case-actor container, and each leaver's own replica
    only for its own closure (CM-23-004,
    :func:`~vultron.demo.helpers.closure.close_case_owner_last`).

    Args:
        state: The running story's state.
        others: The cast names that leave first, in leaving order.
        owner: The cast name of the Case Owner.
        milestone: The closure milestone this scenario numbers it, prefixed
            to each check's description; ``None`` for a scenario that numbers
            none (``rvcv-handoff``).
    """
    close_case_owner_last(
        case=state.case,
        milestone=milestone,
        authority_client=state.case_actor_client,
        others=[
            CaseLeaver(
                client=state.client(name), actor=state.actor(name).actor
            )
            for name in others
        ],
        owner=CaseLeaver(
            client=state.client(owner), actor=state.actor(owner).actor
        ),
    )


def everyone_closes(state: StoryState) -> None:
    """Every participant closes the case; the Case Owner leaves last."""
    close_the_case(state, others=(VENDOR, REPORTER), milestone="M7")


def reporter_then_coordinator_close(state: StoryState) -> None:
    """The Reporter leaves, then the Coordinator, the Case Owner, leaves last.

    The two-party form of :func:`everyone_closes`.
    """
    close_the_case(state, others=(REPORTER,), milestone="M4")


__all__ = [
    "close_the_case",
    "coordinator_and_reporter_publish",
    "everyone_closes",
    "everyone_publishes",
    "report_fix_ready",
    "reporter_asks_about_the_rejection",
    "reporter_replica_converges",
    "reporter_then_coordinator_close",
    "reports_published",
    "the_coordinator_publishes_and_the_embargo_ends",
    "vendor_notifies_fix_ready",
    "vendor_rejects_invite",
    "vendor_reports_the_fix_ready",
]
