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
"""``owner-keep-case:keep``: the owner keeps the case and approves a suggestion.

The ADR-0026 suggest-actor flow, told once for both halves of the tree
(:mod:`vultron.demo.helpers.owner_decision_story`).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from vultron.demo.helpers.coordinated_story import (
    await_reporter_case_replica,
    invitee_triages_after_joining,
)
from vultron.demo.helpers.invite_chain import run_case_invite_chain
from vultron.demo.helpers.owner_decision_story.parts import (
    OWNER_DECISION_TIMEOUT,
    Part,
    case_actor_participant,
)
from vultron.demo.helpers.polling import find_cp_offer_for_case
from vultron.demo.helpers.story import StoryProp, StoryState
from vultron.demo.utils import demo_gate, demo_step
from vultron.enums.roles import CVDRole

logger = logging.getLogger(__name__)


def the_owner_approves_a_suggested_actor(
    state: StoryState,
    *,
    joined: StoryProp[str],
    owner: Part,
    suggester: Part,
    newcomer: Part,
    roles: Sequence[CVDRole],
    seated: Sequence[str],
    timeout_seconds: float = OWNER_DECISION_TIMEOUT,
    join_timeout: float = OWNER_DECISION_TIMEOUT,
) -> None:
    """*suggester* proposes *newcomer*; *owner* approves and *newcomer* joins.

    The ADR-0026 suggest-actor flow end to end: *suggester* posts
    ``suggest-actor-to-case``, the CaseActor forwards an
    ``Offer(CaseParticipant)`` to the owner, the owner posts
    ``accept-actor-recommendation``, the CaseActor sends the Invite, and
    *newcomer* accepts and runs its RM triage (CM-11-002).  The invite chain
    polls *newcomer*'s DataLayer for the Invite and puppeteers the accept —
    polling only, no post to its inbox (DEMOMA-00-002) — nesting the accept
    and the replica wait inside the Invite's gate (EDF-06-005, #3038).

    The owner keeping the case is what makes this the ``keep`` continuation:
    it is the owner, not the joiner, that converts the suggestion into an
    invitation, so ownership never moves (DEMOMA-13-014).

    Reads *joined* first: the suggestion comes from a participant, so a join
    whose roster never filled stops the story here rather than suggesting
    into a case the suggester is not in (DEMOCI-01-011, DEMOMA-13-003).

    Args:
        state: The running story's state.
        joined: The prop the joiner's roster gate kept, read before anything
            else runs.  A flat story cannot nest this continuation inside that
            gate, so the gate keeps it and this reads it
            (:func:`~vultron.demo.helpers.coordinated_story\
            .invitee_joins_the_case`).
        owner: The Case Owner, which approves the recommendation.
        suggester: The participant that suggests *newcomer*.
        newcomer: The actor being suggested; it must be seated already,
            because the suggestion names it by actor id before it has joined
            anything.
        roles: The roles the suggestion asks for.  Explicit, so
            ``EvaluateDefaultRolesNode`` does not fall back to its hardcoded
            ``[VENDOR]`` default (#1969).
        seated: Every cast name the owner's roster must hold once *newcomer*
            has joined, *newcomer* included.
        timeout_seconds: Seconds each cross-container wait may take.
        join_timeout: Seconds to wait for the roster.
    """
    state.kept(joined)
    newcomer_actor = state.actor(newcomer.name).actor

    with demo_step(
        f"{suggester.label} suggests {newcomer.label} to CaseActor"
    ):
        state.actor(suggester.name).with_case(
            state.case
        ).quiet().suggest_actor_to_case(
            suggested_actor_id=newcomer_actor.id_,
            roles=list(roles),
        )
    logger.info(
        "%s sent suggest-actor-to-case for %s (%s)",
        suggester.label,
        newcomer.label,
        newcomer_actor.id_,
    )

    # Every dependent step nests inside the gate, so a recommendation that
    # never arrives skips the lookup and the approval (ADR-0058).
    with demo_gate(
        f"Offer(CaseParticipant) for {newcomer.label} arrived in"
        f" {owner.label}'s DataLayer"
    ):
        cp_offer_id = find_cp_offer_for_case(
            client=state.client(owner.name),
            case_id=state.case.id_,
            timeout_seconds=timeout_seconds,
        )
        logger.info("Offer(CaseParticipant) ID: %s", cp_offer_id)

        case_actor_id = case_actor_participant(
            state.client(owner.name), state.case.id_
        )

        with demo_step(f"{owner.label} approves actor recommendation"):
            state.actor(owner.name).quiet().accept_actor_recommendation(
                cp_offer_id=cp_offer_id,
                case_actor_id=case_actor_id,
            )
    logger.info(
        "%s sent Accept(Offer(CaseParticipant)) to CaseActor", owner.label
    )

    # inviter=None: the CaseActor already invited, on the owner's approval.
    run_case_invite_chain(
        case=state.case,
        invitee_name=newcomer.label,
        invitee_client=state.client(newcomer.name),
        invitee=newcomer_actor,
        invitee_in_own_container=newcomer_actor,
        invite_timeout=timeout_seconds,
        replica_timeout=timeout_seconds,
        ledger_client=state.case_actor_client,
        reply_timeout=timeout_seconds,
    )

    await_reporter_case_replica(state, timeout_seconds)
    invitee_triages_after_joining(
        state,
        newcomer.name,
        newcomer.label,
        seated=seated,
        owner=owner.name,
        owner_label=owner.label,
        join_timeout=join_timeout,
        triage_timeout=timeout_seconds,
    )


__all__ = ["the_owner_approves_a_suggested_actor"]
