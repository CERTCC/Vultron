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
"""The case-invite chain as a whole and in its two halves.

:func:`run_case_invite_chain`, and :func:`invite_and_await_delivery` then
:func:`answer_case_invite` for a story whose invitee's decision falls between
the Invite and the answer (:mod:`vultron.demo.helpers.invite_chain`).
"""

from collections.abc import Callable
from typing import Literal

from vultron.demo.helpers.invite_chain.links import (
    FULL_CASE_REPLY_TIMEOUT,
    CaseInviter,
    EmittedBy,
    _answer,
    _await_and_answer,
    _delivery_gate_label,
    _find_invite,
    _invite_step_label,
    _require_ledger_authority,
    _seed_stub_summary,
    _trigger_invite,
)
from vultron.demo.utils import (
    DataLayerClient,
    demo_gate,
    demo_step,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)


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
        reply_timeout: Seconds the invitee's ledger copy may go without
            advancing while the chain waits for the full-case Invite and for
            that copy to reach its floor before the reply.
        then: Runs inside the gate after the chain completes, so it is skipped
            when the invite was never delivered.

    An invitee's decision falls between the Invite's delivery and the answer,
    and is placed there by a fragment boundary rather than by a hook on this
    function: a story splits the chain into
    :func:`invite_and_await_delivery` and :func:`answer_case_invite` with its
    ``choose(...)`` item between them, which is what gives the mark the
    invitee's own role to check (CM-17-003, DEMOCI-11-019).
    """

    authority_client = (
        case_manager_client
        or ledger_client
        or (inviter.client if inviter is not None else None)
    )
    _require_ledger_authority(invitee_name, respond, authority_client)

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

    with demo_step(_invite_step_label(inviter, invitee_name)):
        _trigger_invite(inviter, invitee, invitee_name, case)
        answer(_delivery_gate_label(invitee_name))


def invite_and_await_delivery(
    *,
    case: as_VulnerabilityCase,
    invitee_name: str,
    invitee_client: DataLayerClient,
    invitee: as_Actor,
    inviter: CaseInviter,
    case_manager_client: DataLayerClient | None = None,
    invite_timeout: float = 15.0,
    expect_emitted_by: EmittedBy | None = None,
) -> str | None:
    """Invite *invitee* and gate on the Invite reaching its container.

    The chain's first half, for a story that puts a branch point between the
    Invite and the answer (:mod:`vultron.demo.helpers.story`): the invitee
    decides only once it holds the Invite, and by then the CASE_MANAGER has
    seated its inert participant carrying the role the Invite offers — which
    is where the harness reads the deciding actor's role from (CM-17-003,
    DEMOCI-11-013, DEMOCI-11-047).  :func:`answer_case_invite` is the second half.

    The step and gate labels are :func:`run_case_invite_chain`'s, so the two
    forms read the same in the logs and the CI diagnostics.

    Args:
        case: The case the invitee is invited to.
        invitee_name: Display name used in step and gate labels.
        invitee_client: Client for the invitee's container, where the Invite
            is delivered.
        invitee: The invitee as the inviter addresses it.
        inviter: The participant that triggers the invite.
        case_manager_client: As :func:`run_case_invite_chain`; seeds
            ``stub_summary`` on the CASE_MANAGER's copy of the case first.
        invite_timeout: Seconds to wait for the Invite to be delivered.
        expect_emitted_by: When given, verify the delivered Invite's sender.

    Returns:
        The delivered Invite's id, or ``None`` when the invite trigger or the
        delivery wait failed — both recorded by their own ``demo_step`` /
        ``demo_gate``, never raised (DEMOCI-01-003).
    """
    if case_manager_client is not None:
        _seed_stub_summary(case_manager_client, case)

    delivered: str | None = None
    with demo_step(_invite_step_label(inviter, invitee_name)):
        _trigger_invite(inviter, invitee, invitee_name, case)
        with demo_gate(_delivery_gate_label(invitee_name)):
            delivered = _find_invite(
                case=case,
                invitee_name=invitee_name,
                invitee_client=invitee_client,
                invitee=invitee,
                invite_timeout=invite_timeout,
                expect_emitted_by=expect_emitted_by,
            )
    return delivered


def answer_case_invite(
    *,
    invite_id: str | None,
    case: as_VulnerabilityCase,
    invitee_name: str,
    invitee_client: DataLayerClient,
    invitee: as_Actor,
    invitee_in_own_container: as_Actor,
    respond: Literal["accept", "reject"] = "accept",
    replica_timeout: float | None = None,
    reply_timeout: float = FULL_CASE_REPLY_TIMEOUT,
    authority_client: DataLayerClient | None = None,
) -> None:
    """Answer the Invite :func:`invite_and_await_delivery` delivered.

    The chain's second half.  The answer and everything after it nest in one
    gate, as they do inside the whole chain: an Invite that never arrived
    (*invite_id* is ``None``) skips them all rather than posting
    ``invite_id: None`` (EDF-06-005, #3038).

    Args:
        invite_id: The delivered Invite's id, or ``None`` when none arrived.
        case: The case the invitee was invited to.
        invitee_name: Display name used in step and gate labels.
        invitee_client: Client for the invitee's container.
        invitee: The invitee as the inviter addressed it.
        invitee_in_own_container: The invitee as its own container holds it,
            used to puppeteer the answer.
        respond: ``"accept"`` waits for the case replica and replies to the
            full-case Invite afterwards; ``"reject"`` does neither.
        replica_timeout: Seconds to wait for the case replica; the polling
            default when ``None``.
        reply_timeout: As :func:`run_case_invite_chain`.
        authority_client: Client for the container hosting the CASE_MANAGER,
            for the ledger-coverage wait before the full-case reply.  Required
            for an accepting answer (SYNC-10-004).  A composed story puts what
            follows the answer in its own fragment, so there is no ``then``
            hook here: the whole chain keeps one, for the callers that nest
            their follow-on inside its gate.

    Raises:
        ValueError: When an accepting answer is given no *authority_client*.
    """
    _require_ledger_authority(invitee_name, respond, authority_client)
    with demo_gate(f"{invitee_name} answers the case invitation"):
        if invite_id is None:
            raise AssertionError(
                f"No case Invite reached {invitee_name}, so it has none to"
                " answer; the invite trigger or its delivery failed and was"
                " recorded above (EDF-06-005)"
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
            then=None,
        )
