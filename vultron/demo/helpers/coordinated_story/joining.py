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
"""How an invitee joins a case of the Reporter → Coordinator → Vendor family.

The join helpers the shared opening and the continuations both call: the
Reporter's case-replica gate, the invitee's RM triage after joining, and the
whole invite chain for an invitee whose decision is no branch point
(:mod:`vultron.demo.helpers.coordinated_story`).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from vultron.demo.helpers.coordinated_story.cast import (
    COORDINATOR,
    COORDINATOR_LABEL,
    CROSS_CONTAINER_TIMEOUT,
    REPORTER,
)
from vultron.demo.helpers.invite_chain import (
    CaseInviter,
    run_case_invite_chain,
)
from vultron.demo.helpers.polling import (
    PARTICIPANT_JOIN_TIMEOUT,
    wait_for_case_on_container,
    wait_for_case_participants,
)
from vultron.demo.helpers.story import (
    StoryProp,
    StoryState,
)
from vultron.demo.helpers.workflow import run_invite_path_rm_triage
from vultron.demo.utils import (
    demo_check,
    demo_gate,
)
from vultron.enums.roles import CVDRole
from vultron.errors import DemoStoryError

logger = logging.getLogger(__name__)


def await_reporter_case_replica(
    state: StoryState, timeout_seconds: float = CROSS_CONTAINER_TIMEOUT
) -> None:
    """Gate the Reporter holding the case replica before an invitee answers.

    The Reporter must hold it before the invitee's reply to the full-case
    Invite (RM Received to Valid), which broadcasts
    ``Announce(CaseLedgerEntry)`` to all participants (CLP-08-005): a Reporter
    without the case has no genesis hash to anchor the chain on (Bug #2135).
    The case is already open, so the replica does not depend on the invitee
    joining.

    Args:
        state: The running story's state.
        timeout_seconds: Seconds to wait.  An invitee reached through a
            multi-hop path waits behind more fan-out, so its scenario passes a
            wider budget.
    """
    with demo_check("Reporter's DataLayer received case replica"):
        wait_for_case_on_container(
            client=state.client(REPORTER),
            case_id=state.case.id_,
            timeout_seconds=timeout_seconds,
        )


def invitee_triages_after_joining(
    state: StoryState,
    name: str,
    label: str,
    *,
    seated: Sequence[str],
    owner: str = COORDINATOR,
    owner_label: str = COORDINATOR_LABEL,
    milestone: str | None = "M2",
    join_timeout: float = PARTICIPANT_JOIN_TIMEOUT,
    triage_timeout: float = CROSS_CONTAINER_TIMEOUT,
) -> None:
    """Gate on every participant being seated, then run *name*'s RM triage.

    CM-11-002: an invitee that joined by accepting runs its RM triage.  All
    participants present is that triage's causal precondition, so it is a
    ``demo_gate``, not a ``demo_check``: a timeout skips the doomed triage
    rather than cascading (DEMOCI-01-011, ``vultron/demo/AGENTS.md`` § "Never
    Wrap a Causal Wait in demo_check").  The roster is read from the Case
    Owner's replica.

    Args:
        state: The running story's state.
        name: The invitee's cast name.
        label: What this scenario calls it in gate labels.
        seated: Every cast name the roster must hold by now, the invitee
            included.
        owner: The Case Owner's cast name, whose replica the roster is read
            from.  The family's Coordinator by default; a story whose owner
            changed mid-run names the owner as of this step (#5535).
        owner_label: What this scenario calls that owner in gate labels.
        milestone: The milestone this scenario numbers the join, or ``None``
            when it numbers it none.  A scenario's milestone numbers are its
            own, and a shared step may not stamp one the scenario spends
            elsewhere: ``rvv`` numbers its replica synchronization M2
            (``docs/howto/demos/rvv-demo.md``), so a second ``✓ M2:`` line
            for the join would make the two indistinguishable in the output
            that page documents.  As ``close_the_case``'s ``milestone``.
        join_timeout: Seconds to wait for the roster.  A joiner reached
            through a multi-hop path needs the late-joiner budget rather than
            the default one.
        triage_timeout: Seconds each wait of the triage itself may take.
    """
    invitee = state.actor(name).actor
    with demo_gate(f"{owner_label} case has {label} before {label} RM triage"):
        wait_for_case_participants(
            vendor_client=state.client(owner),
            case_id=state.case.id_,
            expected_actor_ids={state.actor_id(who) for who in seated},
            timeout_seconds=join_timeout,
        )
        prefix = f"{milestone}: " if milestone else ""
        logger.info("✓ %s%s joined case", prefix, label)

        run_invite_path_rm_triage(
            invited_client=state.client(name),
            invited_actor=invitee,
            offer=state.offer,
            report=state.report,
            reporter=state.actor(REPORTER).actor,
            auth_client=state.case_actor_client,
            case=state.case,
            invited_obj=invitee,
            timeout_seconds=triage_timeout,
        )


def invitee_joins_the_case(
    state: StoryState,
    name: str,
    label: str,
    *,
    role: CVDRole,
    seated: Sequence[str],
    triages: bool = True,
    joined: StoryProp[str] | None = None,
    inviter: str = COORDINATOR,
    inviter_label: str = COORDINATOR_LABEL,
    milestone: str | None = "M2",
    join_timeout: float = PARTICIPANT_JOIN_TIMEOUT,
    cross_container_timeout: float = CROSS_CONTAINER_TIMEOUT,
) -> None:
    """The Case Owner invites the seated *name*, which accepts and joins.

    The whole invite chain in one step, for an invitee whose decision is no
    branch point of the tree: the Invite, the Accept, the case replica, the
    reply to the full-case Invite (:func:`~vultron.demo.helpers.invite_chain\
    .run_case_invite_chain`) and then its RM triage.  The Vendor's own join is
    the two-halved form instead, because the story's ``choose`` falls between
    the Invite and the answer.

    Only the Case Owner may invite (CM-17-007), and which cast member that is
    differs by family: the Coordinator in the coordinator-first subtree, the
    first Vendor in the vendor-first one (#5536).  *inviter* therefore names
    it, defaulting to this family's Coordinator, and the roster is read from
    that member's own replica.

    Args:
        state: The running story's state.
        name: The invitee's cast name; it must be seated already.
        label: What this scenario calls it in step and gate labels.
        role: The role the Invite offers it.
        seated: Every cast name the Case Owner's roster must hold once it has
            joined, the invitee included.
        triages: Whether the invitee runs its RM triage afterwards
            (CM-11-002).  A vendor judges the report it was invited over; a
            coordinator joining to help coordinate does not, and giving it one
            would put an ``engage_case`` act in the ledger the scenario's
            semantic-type list does not claim (DEMOMA-17-002).  When it does
            not triage, the roster check runs inside the chain's own gate
            instead, so a failed invite skips it.
        joined: When given, the roster is this join's causal gate rather than
            a check, and the case id is kept under this prop once the roster
            holds *seated*.  For a non-triaging joiner the next act depends
            on: the two-coordinator pair decides the case's ownership once its
            second Coordinator is a participant (DEMOMA-13-003,
            DEMOMA-14-010), so a roster that never arrived must stop the story
            there rather than offer or suggest into a case the joiner is not
            in (DEMOCI-01-011, #5535).  A flat story cannot nest the next
            fragment inside this gate, so the gate keeps the prop and that
            fragment reads it.  Only the non-triaging path keeps one, so
            passing both this and ``triages=True`` raises rather than leaving
            a prop no step ever keeps.
        inviter: The Case Owner's cast name, which sends the Invite and whose
            replica the roster is read from.
        inviter_label: What this scenario calls that owner in gate labels.
        milestone: The milestone this scenario numbers a triaging joiner's
            arrival, or ``None`` when it numbers it none; passed on to
            :func:`invitee_triages_after_joining`, which logs it.
        join_timeout: Seconds to wait for the roster.
        cross_container_timeout: Seconds each cross-container wait of the
            chain may take.

    Raises:
        DemoStoryError: When *joined* is given with ``triages=True``.
    """
    if triages and joined is not None:
        raise DemoStoryError(
            f"the join of {name!r} was given both triages=True and a prop to "
            "keep, and only the non-triaging path keeps one: a triaging "
            "invitee's roster is already the gate inside "
            "invitee_triages_after_joining, so the prop would never be kept "
            "and every fragment that read it would stop the story."
        )
    invitee = state.actor(name).actor
    await_reporter_case_replica(state, cross_container_timeout)

    def confirm_joined() -> None:
        # A gate when the next fragment depends on the roster, a check when
        # nothing does.  One wait either way, so it cannot be wrapped one way
        # and left bare the other (DEMOCI-01-011).
        context = demo_check if joined is None else demo_gate
        with context(
            f"{inviter_label} case reflects {len(seated)} participants after "
            f"{label} joined"
        ):
            wait_for_case_participants(
                vendor_client=state.client(inviter),
                case_id=state.case.id_,
                expected_actor_ids={state.actor_id(who) for who in seated},
                timeout_seconds=join_timeout,
            )
            if joined is not None:
                state.keep(joined, str(state.case.id_))

    run_case_invite_chain(
        case=state.case,
        case_manager_client=state.case_actor_client,
        invitee_name=label,
        invitee_client=state.client(name),
        invitee=invitee,
        invitee_in_own_container=invitee,
        inviter=CaseInviter(
            name=inviter_label,
            client=state.client(inviter),
            actor=state.actor(inviter).actor,
            role=role,
        ),
        invite_timeout=cross_container_timeout,
        replica_timeout=cross_container_timeout,
        then=None if triages else confirm_joined,
    )

    if triages:
        invitee_triages_after_joining(
            state,
            name,
            label,
            seated=seated,
            owner=inviter,
            owner_label=inviter_label,
            milestone=milestone,
            join_timeout=join_timeout,
            triage_timeout=cross_container_timeout,
        )
