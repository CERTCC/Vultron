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
"""The links of the case-invite chain, and what they are handed.

:class:`CaseInviter`, :class:`EmittedBy` and the chain's budgets, then each
link in order: the Invite's trigger, its delivery, the answer, the case
replica and the reply to the full-case Invite
(:mod:`vultron.demo.helpers.invite_chain`).
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers.polling import (
    assert_received_from,
    find_case_actor_participant_id,
    find_case_invite_for_actor,
    find_full_case_invite_for_actor,
    wait_for_case_on_container,
)
from vultron.demo.helpers.seeding import get_actor_by_id
from vultron.demo.helpers.sync import wait_for_replica_ledger_coverage
from vultron.demo.utils import (
    DataLayerClient,
    demo_check,
    demo_gate,
    demo_step,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

logger = logging.getLogger(__name__)


FULL_CASE_REPLY_TIMEOUT = 20.0
"""Seconds the invitee's ledger copy may go without advancing (CM-11-010).

Bounds the wait for the full-case Invite and for ledger coverage before the
reply.  It is a stall budget, not a total: the Invite is queued behind the
join backfill, so both waits restart it each time another replayed entry
lands and give up only when the backfill stops advancing (#4424).  Twenty
seconds is several times the slowest single-entry apply seen in CI.
"""

DEMO_STUB_SUMMARY = "Vulnerability report — details shared after acceptance."
"""The owner-chosen summary every demo stub Invite carries (CM-17-010)."""


@dataclass(frozen=True)
class CaseInviter:
    """The participant who asks the CASE_MANAGER to invite the invitee."""

    name: str
    client: DataLayerClient
    actor: as_Actor
    role: CVDRole


@dataclass(frozen=True)
class EmittedBy:
    """Check that the delivered Invite was emitted as the CaseActor.

    Holds PCR-08-008 honest: an Invite sent by a participant would route the
    invitee's Accept back to that participant and the CASE_MANAGER-side accept
    tree would never run.  *consequence* names what would break.
    """

    case_actor_id: str
    consequence: str


def _invite_step_label(inviter: CaseInviter, invitee_name: str) -> str:
    """The step label under which *inviter* triggers the Invite."""
    return (
        f"{inviter.name} invites {invitee_name} with "
        f"CVDRole.{inviter.role.name}"
    )


def _delivery_gate_label(invitee_name: str) -> str:
    """The gate label the Invite's delivery to *invitee_name* is awaited under."""
    return f"{invitee_name} invite delivered to {invitee_name}'s DataLayer"


def _require_ledger_authority(
    invitee_name: str,
    respond: Literal["accept", "reject"],
    authority_client: DataLayerClient | None,
) -> None:
    """Refuse an accepting answer with no client to wait on ledger coverage.

    Raises:
        ValueError: When one is needed and none was given (SYNC-10-004).
    """
    if respond == "accept" and authority_client is None:
        raise ValueError(
            f"Chain for {invitee_name} has no client to wait on ledger"
            " coverage with: pass case_manager_client, ledger_client or"
            " inviter (SYNC-10-004)"
        )


def _trigger_invite(
    inviter: CaseInviter,
    invitee: as_Actor,
    invitee_name: str,
    case: as_VulnerabilityCase,
) -> None:
    """Have *inviter* ask the CASE_MANAGER to invite *invitee* to *case*."""
    invite_offer = (
        ActorSession(client=inviter.client, actor=inviter.actor)
        .with_case(case)
        .quiet()
        .invite_actor_to_case(invitee_id=invitee.id_, roles=[inviter.role])
    ).activity
    logger.info(
        "%s asked the CASE_MANAGER to invite %s: %s",
        inviter.name,
        invitee_name,
        invite_offer.id_,
    )


def _seed_stub_summary(
    case_manager_client: DataLayerClient, case: as_VulnerabilityCase
) -> None:
    """Seed ``stub_summary`` on the CASE_MANAGER's DataLayer copy of *case*."""
    case_manager_id = find_case_actor_participant_id(
        case_manager_client, case.id_
    )
    if case_manager_id is None:
        raise ValueError(
            f"No CASE_MANAGER participant found for case '{case.id_}'"
            " (CM-02-014, CM-02-015)"
        )
    ActorSession(
        client=case_manager_client,
        actor=get_actor_by_id(case_manager_client, case_manager_id),
    ).with_case(case).quiet().set_stub_summary(DEMO_STUB_SUMMARY)


def _await_and_answer(
    *,
    case: as_VulnerabilityCase,
    invitee_name: str,
    invitee_client: DataLayerClient,
    invitee: as_Actor,
    invitee_in_own_container: as_Actor,
    gate_label: str,
    respond: Literal["accept", "reject"],
    invite_timeout: float,
    replica_timeout: float | None,
    expect_emitted_by: EmittedBy | None,
    reply_timeout: float,
    authority_client: DataLayerClient | None,
    then: Callable[[], None] | None,
) -> None:
    """Gate on the Invite's delivery, then answer it and run what follows.

    The delivered Invite is the causal precondition for the answer, so the
    answer and everything after it nest inside the gate: a timeout skips them
    instead of posting ``invite_id: None`` (EDF-06-005, #3038).
    """
    with demo_gate(gate_label):
        invite_id = _find_invite(
            case=case,
            invitee_name=invitee_name,
            invitee_client=invitee_client,
            invitee=invitee,
            invite_timeout=invite_timeout,
            expect_emitted_by=expect_emitted_by,
        )
        _answer(
            invite_id=invite_id,
            case=case,
            invitee_name=invitee_name,
            invitee_client=invitee_client,
            invitee=invitee,
            invitee_in_own_container=invitee_in_own_container,
            respond=respond,
            replica_timeout=replica_timeout,
            reply_timeout=reply_timeout,
            authority_client=authority_client,
            then=then,
        )


def _find_invite(
    *,
    case: as_VulnerabilityCase,
    invitee_name: str,
    invitee_client: DataLayerClient,
    invitee: as_Actor,
    invite_timeout: float,
    expect_emitted_by: EmittedBy | None,
) -> str:
    """Wait for the CASE_MANAGER's Invite for *invitee* and return its id.

    Raises:
        AssertionError: When no Invite arrives within *invite_timeout*; the
            caller runs this inside the delivery gate, which records it.
    """
    invite_id = find_case_invite_for_actor(
        client=invitee_client,
        case_id=case.id_,
        invitee_id=invitee.id_,
        timeout_seconds=invite_timeout,
    )
    logger.info("CaseActor Invite for %s: %s", invitee_name, invite_id)

    if expect_emitted_by is not None:
        with demo_check(
            f"{invitee_name} invite was emitted as the CaseActor (PCR-08-008)"
        ):
            assert_received_from(
                invitee_client,
                invite_id,
                expect_emitted_by.case_actor_id,
                expect_emitted_by.consequence,
            )
    return invite_id


def _answer(
    *,
    invite_id: str,
    case: as_VulnerabilityCase,
    invitee_name: str,
    invitee_client: DataLayerClient,
    invitee: as_Actor,
    invitee_in_own_container: as_Actor,
    respond: Literal["accept", "reject"],
    replica_timeout: float | None,
    reply_timeout: float,
    authority_client: DataLayerClient | None,
    then: Callable[[], None] | None,
) -> None:
    """Answer the delivered Invite and run what follows it.

    Runs inside the caller's gate, so a failure here skips the rest of it.
    """
    session = ActorSession(
        client=invitee_client, actor=invitee_in_own_container
    ).quiet()
    if respond == "accept":
        with demo_step(f"{invitee_name} accepts the case invitation"):
            session.accept_case_invite(invite_id=invite_id)
        logger.info("%s sent Accept(Invite) to CaseActor", invitee_name)
        _await_case_replica(
            invitee_name, invitee_client, case, replica_timeout
        )
        # Both entry points refuse an accepting answer without one.
        assert authority_client is not None
        reply_to_full_case_invite(
            invitee_name=invitee_name,
            invitee_client=invitee_client,
            invitee=invitee,
            invitee_in_own_container=invitee_in_own_container,
            case=case,
            authority_client=authority_client,
            timeout=reply_timeout,
        )
    else:
        with demo_step(f"{invitee_name} rejects the case invitation"):
            session.reject_case_invite(invite_id=invite_id)
        logger.info("%s sent Reject(Invite) to CaseActor", invitee_name)

    if then is not None:
        then()


def _await_case_replica(
    invitee_name: str,
    invitee_client: DataLayerClient,
    case: as_VulnerabilityCase,
    replica_timeout: float | None,
) -> None:
    """Verify the Accept seeded the invitee's case replica.

    The replica arrives via the CaseActor's ``Announce(VulnerabilityCase)``
    sent in response to the Accept (MV-10-003).
    """
    with demo_check(f"{invitee_name}'s DataLayer received case replica"):
        if replica_timeout is None:
            wait_for_case_on_container(client=invitee_client, case_id=case.id_)
        else:
            wait_for_case_on_container(
                client=invitee_client,
                case_id=case.id_,
                timeout_seconds=replica_timeout,
            )
    logger.info("%s received case replica", invitee_name)


def reply_to_full_case_invite(
    *,
    invitee_name: str,
    invitee_client: DataLayerClient,
    invitee: as_Actor,
    invitee_in_own_container: as_Actor,
    case: as_VulnerabilityCase,
    authority_client: DataLayerClient,
    timeout: float,
) -> None:
    """Assert the full-case Invite arrives, then answer it (CM-11-010/011).

    After the join the CASE_MANAGER sends the full-case Invite, queued after
    the replay, so the invitee holds it only once its inbox has applied every
    replayed entry ahead of it.  Both waits below therefore follow the
    backfill: *timeout* is how long the invitee's ledger copy may go without
    advancing, not a total (#4424).  Every invitee judges the case by
    replying to it, whatever its role, so the chain waits for the Invite and
    answers it with ``accept-full-case-invite`` (RM Received to Valid).  The
    reply trigger
    fails closed until the invitee's own ledger copy reaches the Invite's
    floor (SYNC-10-004), so the reply is gated on ledger coverage first
    (ADR-0058).  The invitee never answers the reporter's report Offer
    (CM-11-020, ADR-0121).
    """
    with demo_gate(f"{invitee_name} received the full-case Invite"):
        invite_id = find_full_case_invite_for_actor(
            client=invitee_client,
            case_id=case.id_,
            invitee_id=invitee.id_,
            timeout_seconds=timeout,
        )
        logger.info("%s received the full-case Invite", invitee_name)
        wait_for_replica_ledger_coverage(
            authority_client,
            [(invitee_client, f"{invitee.id_} (full-case Invite floor)")],
            case.id_,
            default_timeout=timeout,
            phase_label="before accepting the full-case Invite",
        )
        with demo_step(f"{invitee_name} accepts the full-case Invite"):
            ActorSession(
                client=invitee_client, actor=invitee_in_own_container
            ).quiet().accept_full_case_invite(invite_id=invite_id)
        logger.info(
            "%s sent Accept(Invite(Actor)[target=VulnerabilityCase]) to CaseActor",
            invitee_name,
        )
