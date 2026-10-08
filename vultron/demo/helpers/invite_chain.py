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

"""The case-invite chain shared by every multi-actor demo scenario.

A participant joins a case through one chain: the CASE_MANAGER emits a case
Invite (CM-17-007, ADR-0109), the invitee's DataLayer receives it, the invitee
answers it, and — on an accept — the trust-bootstrap
``Announce(VulnerabilityCase)`` seeds the invitee's case replica
(MV-10-003/MV-10-004).  The CASE_MANAGER then sends the full-case Invite, and
every invitee, whatever its role, judges the case by replying to it
(CM-11-010, CM-11-011): the chain asserts the whole sequence — stub Invite,
stub Accept, Announce and replay, full-case Invite, reply.
Every scenario once wrote that chain out by hand (DEMOMA-17-001, #4192); this
module is the one place that owns it, with the variants as parameters:

- **who asks** — an inviting participant triggers the invite
  (``inviter=CaseInviter(...)``), or the CaseActor already invited after the
  owner approved a recommendation (``inviter=None``, ADR-0026);
- **how the invitee answers** — ``respond="accept"`` or ``"reject"``;
- **whether the Invite's sender is checked** — ``expect_emitted_by``;
- **what follows** — ``then`` runs inside the gate, so it is skipped when any
  earlier link fails (ADR-0058, EDF-06-005, #3038).

The chain reports pass/fail through ``demo_step`` / ``demo_gate`` /
``demo_check`` as the hand-written copies did: a failed trigger or lookup
skips its dependents and is recorded, never raised.  Two differences: step
and gate labels are now uniform across scenarios, and the Accept result is no
longer re-validated as a transitive activity (it fed only a log line).  A
failure inside ``then`` is recorded against the delivery gate, whose label
names the invite rather than the cause.
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
"""Seconds to wait for the full-case Invite and for ledger coverage (CM-11-010)."""

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


def run_case_invite_chain(
    *,
    case: as_VulnerabilityCase,
    invitee_name: str,
    invitee_client: DataLayerClient,
    invitee: as_Actor,
    invitee_in_own_container: as_Actor,
    inviter: CaseInviter | None = None,
    case_manager_client: DataLayerClient | None = None,
    ledger_client: DataLayerClient | None = None,
    respond: Literal["accept", "reject"] = "accept",
    invite_timeout: float = 15.0,
    replica_timeout: float | None = None,
    expect_emitted_by: EmittedBy | None = None,
    reply_timeout: float = FULL_CASE_REPLY_TIMEOUT,
    then: Callable[[], None] | None = None,
) -> None:
    """Drive one invitee through the case-invite chain.

    Args:
        case: The case the invitee is invited to.
        invitee_name: Display name used in step and gate labels.
        invitee_client: Client for the invitee's container, where the Invite
            is delivered and the case replica appears.
        invitee: The invitee as the inviter addresses it (``invitee_id``).
        invitee_in_own_container: The invitee as its own container holds it,
            used to puppeteer the answer.
        inviter: The participant that triggers the invite.  ``None`` when the
            CaseActor invites on its own (ADR-0026 recommend-actor path).
        case_manager_client: Client for the container hosting the case's
            CASE_MANAGER.  When given, the chain seeds ``stub_summary`` on the
            CASE_MANAGER's copy of the case before the inviter triggers the
            Invite: the CASE_MANAGER builds the stub Invite from its own
            store, and a case created by the normal flow has no summary
            (CM-17-010, MV-10-001, #4285).  Needed only on the first chain of
            a case; the seed persists.
        ledger_client: Client for the container hosting the CASE_MANAGER, for
            the ledger-coverage wait before the reply, when neither
            ``case_manager_client`` nor ``inviter`` is given (the ADR-0026
            path).  Unlike ``case_manager_client`` it seeds nothing.  An
            accepting chain needs one of the three, else it raises: the
            reply trigger fails closed below the Invite's floor (SYNC-10-004)
            and a skipped wait would race it.
        respond: ``"accept"`` waits for the case replica afterwards;
            ``"reject"`` does not, because a rejected invitee gets none.
        invite_timeout: Seconds to wait for the Invite to be delivered.
        replica_timeout: Seconds to wait for the case replica; the polling
            default when ``None``.
        expect_emitted_by: When given, verify the delivered Invite's sender.
        reply_timeout: Seconds to wait for the full-case Invite and for the
            invitee's ledger copy to reach its floor before the reply.
        then: Runs inside the gate after the chain completes, so it is skipped
            when the invite was never delivered.
    """

    authority_client = (
        case_manager_client
        or ledger_client
        or (inviter.client if inviter is not None else None)
    )
    if respond == "accept" and authority_client is None:
        raise ValueError(
            f"Chain for {invitee_name} has no client to wait on ledger"
            " coverage with: pass case_manager_client, ledger_client or"
            " inviter (SYNC-10-004)"
        )

    def answer(gate_label: str) -> None:
        _await_and_answer(
            case=case,
            invitee_name=invitee_name,
            invitee_client=invitee_client,
            invitee=invitee,
            invitee_in_own_container=invitee_in_own_container,
            gate_label=gate_label,
            respond=respond,
            invite_timeout=invite_timeout,
            replica_timeout=replica_timeout,
            expect_emitted_by=expect_emitted_by,
            reply_timeout=reply_timeout,
            authority_client=authority_client,
            then=then,
        )

    if case_manager_client is not None:
        _seed_stub_summary(case_manager_client, case)

    if inviter is None:
        answer(
            f"{invitee_name} received invite from CaseActor (ADR-0026 path)"
        )
        return

    with demo_step(
        f"{inviter.name} invites {invitee_name} with CVDRole.{inviter.role.name}"
    ):
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
        answer(
            f"{invitee_name} invite delivered to {invitee_name}'s DataLayer"
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
        invite_id = find_case_invite_for_actor(
            client=invitee_client,
            case_id=case.id_,
            invitee_id=invitee.id_,
            timeout_seconds=invite_timeout,
        )
        logger.info("CaseActor Invite for %s: %s", invitee_name, invite_id)

        if expect_emitted_by is not None:
            with demo_check(
                f"{invitee_name} invite was emitted as the CaseActor"
                " (PCR-08-008)"
            ):
                assert_received_from(
                    invitee_client,
                    invite_id,
                    expect_emitted_by.case_actor_id,
                    expect_emitted_by.consequence,
                )

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
            # run_case_invite_chain refused an accepting chain without one.
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
    the replay.  Every invitee judges the case by replying to it, whatever its
    role, so the chain waits for the Invite and answers it with
    ``accept-full-case-invite`` (RM Received to Valid).  The reply trigger
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
        logger.info("%s sent Accept(Invite(case)) to CaseActor", invitee_name)
