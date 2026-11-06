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
"""The shared opening of the coordinator-first family, and its prefixes.

The fragments every scenario of the family tells before it parts from its
siblings, and the nested named prefixes built from them
(:data:`REPORTER_TELLS_THE_COORDINATOR` ⊂ :data:`COORDINATOR_INVITES_VENDOR`
⊂ :data:`VENDOR_JOINS_THE_CASE` ⊂ :data:`REPORTER_ASKS_THE_VENDOR`), one per
branch point (``notes/demo-scenario-tree.md`` § "Composition").
"""

from __future__ import annotations

import logging

from vultron.demo.helpers.coordinated_story.cast import (
    COORDINATOR,
    COORDINATOR_LABEL,
    CROSS_CONTAINER_TIMEOUT,
    OWNER_TRIAGE_TIMEOUT,
    REPORTER,
    REPORTER_LABEL,
    VENDOR,
    VENDOR_LABEL,
)
from vultron.demo.helpers.coordinated_story.joining import (
    vendor_accepts_and_joins,
)
from vultron.demo.helpers.invite_chain import (
    CaseInviter,
    invite_and_await_delivery,
)
from vultron.demo.helpers.milestones import verify_case_active
from vultron.demo.helpers.notes import (
    gated_note_thread,
    reporter_asks_vendor_timeline,
)
from vultron.demo.helpers.polling import wait_for_case_participants
from vultron.demo.helpers.story import StoryProp, StoryState, choose, story
from vultron.demo.helpers.sync import run_sync_verification_phase
from vultron.demo.helpers.workflow import (
    reporter_submits_report,
    run_direct_path_rm_triage,
)
from vultron.demo.utils import demo_check, demo_gate
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

logger = logging.getLogger(__name__)


#: The Coordinator's summary closing the ``ask-vendor`` note thread.  Kept so
#: a continuation can answer it: ``rcvcv``'s later joiners reply to it rather
#: than opening a thread of their own (DEMOCI-11-017).
TIMELINE_ANSWER: StoryProp[as_Note] = StoryProp(
    "answered timeline note thread", as_Note
)

#: The case whose roster the Coordinator has confirmed, as its id.  Read by
#: :func:`coordinator_invites_vendor`, which is the causal dependent: the
#: Reporter and the Coordinator must both be seated before anyone else is
#: invited, so a roster that never arrived skips the invite and the admit
#: chain behind it rather than adding secondary failures to the first
#: (DEMOCI-01-011, ``vultron/demo/AGENTS.md`` § "Never Wrap a Causal Wait in
#: demo_check").  A flat story cannot nest the invite inside the roster's
#: gate, so the gate keeps this and the invite reads it.
ENGAGED_CASE: StoryProp[str] = StoryProp(
    "case whose roster the Coordinator confirmed", str
)


def reporter_tells_coordinator(state: StoryState) -> None:
    """The Reporter submits its report; the Coordinator engages the case.

    The Coordinator validates the report and engages the case (RM→ACCEPTED),
    holding CASE_OWNER; each step is gated on its own RM state.  The Reporter
    is seated when the case is created (CP-09-002), so it is never invited
    (DEMOMA-12-003).

    The case is recorded as soon as the triage returns it, which arms the
    ledger dump at the first instant there is anything to dump, so every step
    below can fail without costing the ledgers (DEMOMA-23-003, ISSUE-2239).
    Then the roster wait is a ``demo_gate``: the Reporter and the Coordinator
    both being seated is the precondition for inviting anyone else, so a
    timeout skips the M1 check, the re-read and :data:`ENGAGED_CASE`, and
    :func:`coordinator_invites_vendor` stops the story rather than inviting
    into a case the owner cannot vouch for (DEMOCI-01-011).
    """
    reporter = state.actor(REPORTER).actor
    coordinator = state.actor(COORDINATOR).actor
    owner_client = state.client(COORDINATOR)
    report, offer = reporter_submits_report(
        receiver_client=owner_client,
        reporter=reporter,
        receiver=coordinator,
        reporter_client=state.client(REPORTER),
    )
    case = run_direct_path_rm_triage(
        receiver_client=owner_client,
        receiver=coordinator,
        offer=offer,
        timeout_seconds=OWNER_TRIAGE_TIMEOUT,
    )
    # Recorded here, at the first instant there is anything to dump, so every
    # step below can fail without costing the ledgers (DEMOMA-23-003,
    # ISSUE-2239) — including the gate that follows.
    state.open_case(case=case, report=report, offer=offer)

    with demo_gate(
        "Coordinator case reflects Reporter + Coordinator participants"
    ):
        wait_for_case_participants(
            vendor_client=owner_client,
            case_id=case.id_,
            expected_actor_ids={reporter.id_, coordinator.id_},
        )

        with demo_check(
            "M1: ≥3 participants, EM.ACTIVE, Reporter has replica"
        ):
            verify_case_active(
                receiver_client=owner_client,
                reporter_client=state.client(REPORTER),
                case_id=case.id_,
                receiver_actor_id=coordinator.id_,
                reporter_actor_id=reporter.id_,
            )

        # Re-read the case as the Coordinator now stores it: the triage and
        # the participant seating have moved on since the trigger returned it.
        state.restate_case(
            as_VulnerabilityCase.model_validate(
                owner_client.get(owner_client.dl_path(case.id_))
            )
        )
        state.keep(ENGAGED_CASE, str(case.id_))


def coordinator_invites_vendor(state: StoryState) -> None:
    """The Coordinator invites the Vendor, and the Invite is delivered.

    The Coordinator is CASE_OWNER, so it invites directly rather than through
    the ADR-0026 suggest/approve chain (DEMOMA-12-004).  The fragment stops at
    delivery: the Vendor's answer is the next branch point's choice.

    Reads :data:`ENGAGED_CASE` first: the Reporter and the Coordinator being
    seated is this invite's causal precondition, so a roster that never
    arrived stops the story here instead of inviting into a case the owner
    cannot vouch for (DEMOCI-01-011).
    """
    state.kept(ENGAGED_CASE)
    state.invited(
        VENDOR,
        invite_and_await_delivery(
            case=state.case,
            invitee_name=VENDOR_LABEL,
            invitee_client=state.client(VENDOR),
            invitee=state.actor(VENDOR).actor,
            inviter=CaseInviter(
                name=COORDINATOR_LABEL,
                client=state.client(COORDINATOR),
                actor=state.actor(COORDINATOR).actor,
                role=CVDRole.VENDOR,
            ),
            case_manager_client=state.case_actor_client,
            invite_timeout=CROSS_CONTAINER_TIMEOUT,
        ),
    )


#: The opening every coordinator-first scenario shares, whoever the
#: Coordinator invites next: the Reporter tells the Coordinator and the
#: Coordinator engages the case.  It stops where the Coordinator's decision
#: falls — invite the Vendor (:data:`COORDINATOR_INVITES_VENDOR` and its
#: siblings) or invite a second Coordinator
#: (:mod:`vultron.demo.helpers.two_coordinator_story`, #5535).
REPORTER_TELLS_THE_COORDINATOR = story(
    choose("reporter-whom-to-tell", "coordinator", by=REPORTER),
    reporter_tells_coordinator,
)

#: The opening every Reporter → Coordinator → Vendor scenario shares: the
#: Reporter tells the Coordinator, and the Coordinator invites the Vendor.
#: Named rather than assembled from the fragments at each call site, because
#: assembling siblings from fragments alone lets one of them slip a step in
#: before the branch point (``notes/demo-scenario-tree.md`` § "Composition").
COORDINATOR_INVITES_VENDOR = story(
    REPORTER_TELLS_THE_COORDINATOR,
    choose("coordinator-invite-whom", "vendor", by=COORDINATOR),
    coordinator_invites_vendor,
)


def replicas_converge_with_vendor(state: StoryState) -> None:
    """The Reporter's and the Vendor's replicas catch up with the case."""
    run_sync_verification_phase(
        auth_client=state.client(COORDINATOR),
        auth_label=COORDINATOR_LABEL,
        auth_actor_id=state.actor_id(COORDINATOR),
        reporter_client=state.client(REPORTER),
        reporter_actor_id=state.actor_id(REPORTER),
        replicas=[
            (state.client(REPORTER), REPORTER_LABEL),
            (state.client(VENDOR), VENDOR_LABEL),
        ],
        case_id=state.case.id_,
        expected_participant_ids={
            state.actor_id(REPORTER),
            state.actor_id(COORDINATOR),
            state.actor_id(VENDOR),
        },
        # The Vendor joins by invitation after the case exists (#2202).
        late_joiners=(state.client(VENDOR),),
        state_checks=[
            (state.client(REPORTER), REPORTER_LABEL),
            (state.client(VENDOR), VENDOR_LABEL),
        ],
    )
    logger.info("✓ M3: All replicas synchronized (LedgerFanout verified)")


#: The opening through the Vendor's acceptance, which every scenario whose
#: Vendor joins shares.  It stops where the Reporter's decision falls: ask the
#: Vendor a question, or propose new embargo terms.
VENDOR_JOINS_THE_CASE = story(
    COORDINATOR_INVITES_VENDOR,
    choose("vendor-join", "accept", by=VENDOR),
    vendor_accepts_and_joins,
    replicas_converge_with_vendor,
)


def reporter_asks_about_the_timeline(state: StoryState) -> None:
    """The Reporter asks the Vendor's timeline; both others answer.

    Each poster acts from its own replica, and the Vendor's holds the case
    only once the Vendor has joined, so the thread waits on it
    (DEMOMA-22-001).  The Coordinator's closing summary is kept for a
    continuation that answers it (:data:`TIMELINE_ANSWER`).
    """
    answered = gated_note_thread(
        gate="Vendor's replica holds the case before the Reporter asks it",
        replica_client=state.client(VENDOR),
        watching_client=state.client(COORDINATOR),
        case=state.case,
        posts=reporter_asks_vendor_timeline(
            state.actor(REPORTER),
            state.actor(VENDOR),
            state.actor(COORDINATOR),
        ),
    )
    if answered is not None:
        state.keep(TIMELINE_ANSWER, answered)
    logger.info(
        "✓ Notes exchange complete (three notes committed to case ledger)"
    )


#: The opening through the note thread the ``ask-vendor`` choice posts.  It
#: stops where the Coordinator's decision falls, which follows the
#: Coordinator's own note in the thread: publish after the Vendor's fix
#: (``rcv``), or invite a second Coordinator (``rcvcv``).
REPORTER_ASKS_THE_VENDOR = story(
    VENDOR_JOINS_THE_CASE,
    choose("reporter-after-join", "ask-vendor", by=REPORTER),
    reporter_asks_about_the_timeline,
)


__all__ = [
    "COORDINATOR_INVITES_VENDOR",
    "ENGAGED_CASE",
    "REPORTER_ASKS_THE_VENDOR",
    "REPORTER_TELLS_THE_COORDINATOR",
    "TIMELINE_ANSWER",
    "VENDOR_JOINS_THE_CASE",
    "coordinator_invites_vendor",
    "replicas_converge_with_vendor",
    "reporter_asks_about_the_timeline",
    "reporter_tells_coordinator",
]
