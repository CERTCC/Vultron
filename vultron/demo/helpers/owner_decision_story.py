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
"""The two continuations of the ``owner-keep-case`` decision.

A Case Owner that has just taken a second participant on decides whether to
keep the case: keep it and approve the newcomer the joiner suggests
(``owner-keep-case:keep``, ADR-0026), or hand the case over and let the new
owner invite the newcomer itself (``owner-keep-case:offer-ownership``,
TRIG-11-001/002).  The decision appears in **both** halves of the tree — the
two-coordinator pair decides it with a Coordinator as owner and a second
Coordinator as the joiner, the vendor-first pair with a Vendor as owner and a
Coordinator as the joiner (``notes/demo-scenario-tree.md``
§ "Composition") — so each continuation is written here once and reads its
cast off the running story rather than naming either pair's actors
(DEMOMA-17-001).

A continuation therefore takes :class:`Part`\\ s, not clients: a part is the
name the story seats a cast member under plus what the scenario calls it in
its step and gate labels.  Everything else — the sessions, the case, the
case-actor client — comes from the :class:`~vultron.demo.helpers.story\
.StoryState`.

The handover's two halves are separated by a prop
(:data:`HANDED_OVER_CASE`): only the Case Owner may invite, so a transfer the
CASE_MANAGER never committed must stop the story rather than let the
would-be owner invite into a case it does not own (DEMOCI-01-011).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from vultron.demo.helpers.coordinated_story import (
    REPORTER,
    REPORTER_LABEL,
    await_reporter_case_replica,
    invitee_triages_after_joining,
)
from vultron.demo.helpers.invite_chain import (
    CaseInviter,
    EmittedBy,
    run_case_invite_chain,
)
from vultron.demo.helpers.polling import (
    LATE_JOINER_TIMEOUT,
    SharedBudget,
    find_case_actor_participant_id,
    find_cp_offer_for_case,
    find_ownership_transfer_offer_for_actor,
    wait_for_case_actor_ledger_event,
    wait_for_case_attributed_to,
    wait_for_semantic_type_in_ledger,
)
from vultron.demo.helpers.story import StoryProp, StoryState
from vultron.demo.utils import (
    DataLayerClient,
    demo_check,
    demo_gate,
    demo_step,
)
from vultron.enums.roles import CVDRole
from vultron.errors import DemoStoryError
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

logger = logging.getLogger(__name__)

#: Seconds a wait of either continuation may take.  Both reach their actors
#: through the CaseActor — a suggestion forwarded to the owner and approved,
#: or a transfer offered, accepted and fanned out — so every wait queues
#: behind the same outbox and takes the late-joiner budget, the widest either
#: scenario carried before the step was shared.  A budget only bounds how long
#: a wait may take, so taking the wider one refuses nothing the narrower one
#: admitted and moves no byte of a recording (DEMOCI-11-018).
OWNER_DECISION_TIMEOUT = LATE_JOINER_TIMEOUT

#: The case whose ownership the owner handed over, as its id.  Read by
#: :func:`the_new_owner_invites`, which is the causal dependent: only the Case
#: Owner may invite, so a transfer the CASE_MANAGER never committed stops the
#: story there instead of inviting into a case the would-be owner does not own
#: (DEMOCI-01-011).  A flat story cannot nest the invite inside the commit's
#: gate, so the gate keeps this and the invite reads it.
HANDED_OVER_CASE: StoryProp[str] = StoryProp(
    "case whose ownership the owner handed over", str
)


@dataclass(frozen=True, slots=True)
class Part:
    """One cast member a shared continuation acts on.

    The ``(state, name, label)`` pair every shared fragment of a family takes,
    bundled because these continuations act on three members at once and three
    loose pairs of strings beside each other are trivially swappable.

    Attributes:
        name: The name the story seats the member under, the key
            :meth:`~vultron.demo.helpers.story.StoryState.actor` reads.
        label: What this scenario calls it in step and gate labels — ``"C1"``
            in the two-coordinator pair, ``"Vendor1"`` in the vendor-first
            one.
    """

    name: str
    label: str


#: The Reporter's part, which every scenario of the tree so far seats under
#: that name: the default witness of a handover, being neither the old nor the
#: new owner (:func:`the_owner_hands_the_case_over`).
REPORTER_PART = Part(REPORTER, REPORTER_LABEL)


def case_actor_participant(client: DataLayerClient, case_id: str) -> str:
    """The CaseActor's actor URI, read off *client*'s replica of *case_id*.

    Both continuations need it: the approval routes the owner's
    ``Accept(Offer(CaseParticipant))`` back to the CaseActor (CM-16-006), and
    the handover's invite checks that the Invite the newcomer received was
    emitted *as* the CaseActor (PCR-08-008).  Read from a replica rather than
    assumed, so the check names the actor that actually holds CASE_MANAGER on
    this case.

    Takes the client rather than the story's state, so it is a polling-style
    helper like the one it wraps and not a story fragment: a fragment owns its
    own demo context (DEMOCI-01-011), and this one raises into the caller's
    gate exactly as ``find_case_actor_participant_id`` does.

    Raises:
        AssertionError: When the replica's participant index names no
            CaseActor, so neither the Accept nor the sender check has an
            address.  Both callers read it inside a ``demo_gate``, which
            records the failure and skips the dependents.
    """
    case_actor_id = find_case_actor_participant_id(client, case_id)
    if case_actor_id is None:
        raise AssertionError(
            "the case replica read names no CaseActor participant, so there"
            " is no CASE_MANAGER address to route the Accept to"
        )
    logger.info("CaseActor participant ID: %s", case_actor_id)
    return case_actor_id


# ---------------------------------------------------------------------------
# owner-keep-case:keep — the owner keeps the case and approves a suggestion
# ---------------------------------------------------------------------------


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
    polling only, no mail-carrying — nesting the accept and the replica wait
    inside the Invite's gate (EDF-06-005, #3038).

    The owner keeping the case is what makes this the ``keep`` continuation:
    it is the owner, not the joiner, that converts the suggestion into an
    invitation, so ownership never moves (DEMOMA-13-002).

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


# ---------------------------------------------------------------------------
# owner-keep-case:offer-ownership — the owner hands the case over
# ---------------------------------------------------------------------------


def the_owner_hands_the_case_over(
    state: StoryState,
    *,
    joined: StoryProp[str],
    owner: Part,
    new_owner: Part,
    witness: Part = REPORTER_PART,
    timeout_seconds: float = OWNER_DECISION_TIMEOUT,
) -> None:
    """*owner* offers case ownership to *new_owner*, which accepts.

    TRIG-11-001 then TRIG-11-002: the owner's proposal,
    ``Offer(Offer(VulnerabilityCase))``, is addressed to the CaseActor, which
    makes the one Offer of the transfer under an id of its own and sends it to
    *new_owner* (CM-21-005, ADR-0148) — so polling for the proposal's id would
    never match.  The delivery gate and the accept nest inside the offer step,
    so a failed trigger or lookup skips them instead of accepting an offer
    that was never made (ADR-0058, EDF-06-005, #3038).

    The transfer reaches a replica in two hops: Accept → CaseActor inbox →
    commit (CM-21-007), then CaseActor outbox → ``Announce(CaseLedgerEntry)``
    of the ``update_case_participant`` and ``update_case_owner`` entries that
    follow it (CLP-07-013) → each participant copies them.  Nothing else
    updates a replica, so the old owner learns of its own loss of ownership
    from the fan-out like anyone else.  The commit is therefore gated first,
    read from the CaseActor's own store, so a slow fan-out is reported as the
    fan-out being slow rather than as the transfer never having happened
    (EDF-06-002, #3602).

    Reads *joined* before any act: the transferee must be an active
    participant already (DEMOMA-14-010, CM-21-021), so a join whose roster
    never filled stops the story here rather than offering the case to an
    actor that is not in it.  Before composition the whole offer and accept
    nested inside that roster's own ``demo_gate``; the prop is what carries
    the guarantee through a flat sequence (DEMOCI-01-011, #5535).  Only the
    *witness* check runs ahead of it, and it reads nothing and writes
    nothing; no statement with an effect may go before the read.

    Args:
        state: The running story's state.
        joined: The prop the transferee's roster gate kept, read before any
            act of this fragment.
        owner: The Case Owner handing the case over.
        new_owner: The participant taking it; it must hold the case's
            coordinating role and be an active participant already
            (DEMOMA-13-003, DEMOMA-14-010, CM-21-021).
        witness: A participant that is neither the old nor the new owner.
            ADR-0053's own validation criterion: it can only hold the
            transfer's ledger entry if the CaseActor committed it and fanned
            it out to every participant (CM-21-007).  The Reporter in every
            scenario of the tree so far, which is why it is the default.
        timeout_seconds: Seconds the offer's delivery may take, and the whole
            fan-out's shared budget.

    Raises:
        DemoStoryError: When *joined* was never kept, or when *witness* is
            the old or the new owner — a party to the exchange learns of the
            transfer from the round-trip itself, so reading the ledger entry
            on its replica would prove nothing about the CM-21-007 broadcast
            (ADR-0053).
    """
    if witness.name in {owner.name, new_owner.name}:
        raise DemoStoryError(
            f"the handover's witness is {witness.name!r}, which is a party to"
            " the transfer; ADR-0053's criterion is that an actor outside the"
            " negotiation learns of it from the CM-21-007 broadcast alone, so"
            " the witness is neither the old nor the new owner"
        )
    state.kept(joined)
    new_owner_actor = state.actor(new_owner.name).actor

    with demo_step(
        f"{owner.label} offers case ownership transfer to"
        f" {new_owner.label} (TRIG-11-001)"
    ):
        proposal = (
            state.actor(owner.name)
            .with_case(state.case)
            .quiet()
            .offer_case_ownership_transfer(
                transferee_id=new_owner_actor.id_,
                content=(
                    f"Transferring case ownership to {new_owner.label} for"
                    " CVD management."
                ),
            )
        ).activity
        logger.info(
            "%s proposed an ownership transfer: %s", owner.label, proposal.id_
        )

        with demo_gate(
            f"CaseActor's Offer(VulnerabilityCase) delivered to"
            f" {new_owner.label}'s DataLayer (TRIG-11-001, CM-21-005)"
        ):
            offer_id = find_ownership_transfer_offer_for_actor(
                client=state.client(new_owner.name),
                case_id=state.case.id_,
                transferee_id=new_owner_actor.id_,
                timeout_seconds=timeout_seconds,
            )
            logger.info(
                "CaseActor's ownership transfer offer ID: %s", offer_id
            )

            with demo_step(
                f"{new_owner.label} accepts case ownership transfer"
                " (TRIG-11-002)"
            ):
                accepted = (
                    state.actor(new_owner.name)
                    .quiet()
                    .accept_case_ownership_transfer(offer_id=offer_id)
                )
                logger.info(
                    "%s sent Accept(Offer(VulnerabilityCase)): %s",
                    new_owner.label,
                    accepted.activity.id_,
                )

    # The replicas' attributed_to comes from update_case_owner, the last entry
    # the transfer commits, so that entry is the gate (CLP-07-013).  What the
    # gate keeps is what the invite fragment reads: only the Case Owner may
    # invite, so a transfer that never committed stops the story there.
    with demo_gate(
        "CaseActor committed update_case_owner after the accepted transfer"
        " (CM-21-007, CLP-07-013)"
    ):
        wait_for_case_actor_ledger_event(
            client=state.case_actor_client,
            case_id=state.case.id_,
            semantic_type="update_case_owner",
        )

        # Temporal bound on the second hop (EDF-06-006, EDF-06-008): one
        # budget for the whole fan-out, because every replica is fed by the
        # same CaseActor outbox and queues behind whatever it already holds
        # (ADR-0112).  Sharing it caps the step's worst case at one budget
        # instead of one per replica, while starving no single replica.
        fanout = SharedBudget(timeout_seconds)
        logger.info("Ownership-transfer fan-out budget: %r", fanout)

        for who in (owner, new_owner):
            with demo_check(
                f"Case attributed_to updated to {new_owner.label} on"
                f" {who.label}'s DataLayer"
            ):
                wait_for_case_attributed_to(
                    client=state.client(who.name),
                    case_id=state.case.id_,
                    expected_attributed_to=new_owner_actor.id_,
                    timeout_seconds=fanout.remaining(),
                )

        with demo_check(
            f"{witness.label} replica received the ownership-transfer ledger"
            " entry via Announce(CaseLedgerEntry) (CM-21-007, ADR-0053)"
        ):
            wait_for_semantic_type_in_ledger(
                client=state.client(witness.name),
                case_id=state.case.id_,
                semantic_type="accept_case_ownership_transfer",
                timeout_seconds=fanout.remaining(),
            )
        logger.info("Ownership-transfer fan-out budget left: %r", fanout)

        # The case as the old owner now stores it: the transfer moved
        # attributed_to, and the id it is keyed on is unchanged, which is what
        # restate_case checks (CM-21-002).
        owner_client = state.client(owner.name)
        state.restate_case(
            as_VulnerabilityCase.model_validate(
                owner_client.get(owner_client.dl_path(state.case.id_))
            )
        )
        state.keep(HANDED_OVER_CASE, str(state.case.id_))

    logger.info(
        "✓ Ownership transfer complete: %s is now CASE_OWNER for %s",
        new_owner.label,
        state.case.id_,
    )


def the_new_owner_invites(
    state: StoryState,
    *,
    new_owner: Part,
    invitee: Part,
    role: CVDRole,
    seated: Sequence[str],
    timeout_seconds: float = OWNER_DECISION_TIMEOUT,
    join_timeout: float = OWNER_DECISION_TIMEOUT,
) -> None:
    """*new_owner*, the owner since the handover, invites *invitee*.

    The trigger is posted to *new_owner*'s **own** container: a trigger URL is
    built from the named actor's bare id against the client's base URL, so
    posting the new owner's trigger to the old owner's client 404s, which is
    the defect #2178 fixed in one scenario and not its sibling
    (DEMOMA-22-002).  The trigger sends *new_owner*'s own Offer to the
    CASE_MANAGER and the CaseActor emits the Invite (CM-17-007, ADR-0109), so
    the Invite goes out *as* the CaseActor and *invitee*'s Accept routes back
    to the CaseActor rather than to *new_owner*, letting
    ``AcceptInviteActorToCaseBT`` run (PCR-08-007, PCR-08-008).
    ``expect_emitted_by`` is what holds that property honest.

    Reads :data:`HANDED_OVER_CASE` first: only the Case Owner may invite, so a
    transfer that never committed stops the story here (DEMOCI-01-011).

    Args:
        state: The running story's state.
        new_owner: The Case Owner since the handover.
        invitee: The actor it invites; it must be seated already.
        role: The role the Invite offers *invitee*.
        seated: Every cast name the new owner's roster must hold once
            *invitee* has joined, *invitee* included.
        timeout_seconds: Seconds each cross-container wait may take.
        join_timeout: Seconds to wait for the roster.
    """
    state.kept(HANDED_OVER_CASE)
    invitee_actor = state.actor(invitee.name).actor

    with demo_gate(
        f"the handed-over case names the CaseActor before"
        f" {new_owner.label} invites {invitee.label} (PCR-08-008)"
    ):
        case_actor_id = case_actor_participant(
            state.client(new_owner.name), state.case.id_
        )

        # The chain nests the accept and the replica wait inside the delivery
        # gate (ADR-0058, EDF-06-005, #3038).
        run_case_invite_chain(
            case=state.case,
            case_manager_client=state.case_actor_client,
            invitee_name=invitee.label,
            invitee_client=state.client(invitee.name),
            invitee=invitee_actor,
            invitee_in_own_container=invitee_actor,
            inviter=CaseInviter(
                name=new_owner.label,
                client=state.client(new_owner.name),
                actor=state.actor(new_owner.name).actor,
                role=role,
            ),
            invite_timeout=timeout_seconds,
            replica_timeout=timeout_seconds,
            expect_emitted_by=EmittedBy(
                case_actor_id=case_actor_id,
                consequence=(
                    f"{invitee.label}'s Accept would route to"
                    f" {new_owner.label} and AcceptInviteActorToCaseBT would"
                    " not run"
                ),
            ),
        )

    await_reporter_case_replica(state, timeout_seconds)
    invitee_triages_after_joining(
        state,
        invitee.name,
        invitee.label,
        seated=seated,
        owner=new_owner.name,
        owner_label=new_owner.label,
        join_timeout=join_timeout,
        triage_timeout=timeout_seconds,
    )


__all__ = [
    "HANDED_OVER_CASE",
    "OWNER_DECISION_TIMEOUT",
    "REPORTER_PART",
    "Part",
    "case_actor_participant",
    "the_new_owner_invites",
    "the_owner_approves_a_suggested_actor",
    "the_owner_hands_the_case_over",
]
