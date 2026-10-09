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

"""The closure phase every scenario shares: the Case Owner leaves last.

The Case Owner's ``Leave(VulnerabilityCase)`` closes the case for everyone
(CM-23-002), and a departure sent after ``case_fully_closed`` is not recorded
(CM-23-013).  So the owner leaves after every other participant has left
(CM-23-015), and only once the CASE_MANAGER has recorded each of those
departures: a trigger returns 202 and the ``Leave`` commits later on another
container, so "the Finder closed, then the Vendor closed" in script order is
not the same as that order on the ledger (EDF-06-002).

:func:`close_case_owner_last` is the one place that sequence lives, so no
scenario carries its own copy of the ordering or of the gate (DEMOMA-17-001).
It also runs the ledger half of the closure milestone,
:func:`~vultron.demo.helpers.milestones.verify_case_closure_recorded`, which
depends on the owner having left; a scenario adds only its replica checks.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from vultron.core.states.rm import RM
from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers.milestones import verify_case_closure_recorded
from vultron.demo.helpers.polling import (
    resolve_case_actor_store_id,
    wait_for_participant_rm_state,
)
from vultron.demo.utils import (
    DataLayerClient,
    demo_check,
    demo_gate,
    demo_step,
    ref_id,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CaseLeaver:
    """A participant that leaves the case, and the container it acts through.

    Attributes:
        client: The participant's own container client.
        actor: The participant's actor, as its own container holds it.
    """

    client: DataLayerClient
    actor: as_Actor


def close_case_owner_last(
    *,
    case: as_VulnerabilityCase,
    authority_client: DataLayerClient,
    others: Sequence[CaseLeaver],
    owner: CaseLeaver,
    milestone: str | None = None,
) -> list[str]:
    """Close *case*: every participant in *others* leaves, then *owner* does.

    Each participant in *others* sends ``Leave(VulnerabilityCase)`` in the
    order given.  The owner's ``Leave`` is gated on the CASE_MANAGER having
    recorded every one of those departures: each leaver reads ``RM.CLOSED``
    in the CASE_MANAGER's own store, where the non-owner closure commits
    (CM-23-003).  The read goes through *authority_client*, scoped to the
    co-hosted CaseActor's store when there is one
    (:func:`~vultron.demo.helpers.polling.resolve_case_actor_store_id`).
    When a departure is not recorded in time the gate fails once and the
    owner does not leave: an owner ``Leave`` sent then would close the case
    over a departure the ledger might never record (CM-23-013).

    Once the owner has left, the closure milestone's ledger check runs in its
    own ``demo_check``: every departure is recorded before
    ``case_fully_closed`` and no participant act follows it
    (:func:`~vultron.demo.helpers.milestones.verify_case_closure_recorded`,
    read through *authority_client*).  It is skipped with the owner's
    ``Leave`` when the gate fails, so the one failure names the cause.

    Args:
        case: The case being closed.
        authority_client: Client for the container that hosts the case's
            CASE_MANAGER.
        others: Every participant other than the Case Owner, in the order
            they leave.  Each MUST be distinct from *owner*.
        owner: The participant holding ``CASE_OWNER`` at closure.
        milestone: The scenario's label for its closure milestone (``"M7"``),
            prefixed to the ledger check's description; ``None`` for none.

    Returns:
        The actor ids of every participant whose ``Leave`` step ran, in that
        order, the owner last; the owner is missing when the gate failed.

    Raises:
        ValueError: If *owner* is also listed in *others*, which would
            send the owner's ``Leave`` before the others have left.

    Spec: CM-23-015, CM-23-013, CM-23-003, EDF-06-002.
    """
    owner_id = owner.actor.id_
    if any(leaver.actor.id_ == owner_id for leaver in others):
        raise ValueError(
            f"close_case_owner_last: the Case Owner {owner_id!r} is listed"
            " among the participants that leave before it"
        )

    departed: list[str] = []
    for leaver in others:
        _leave(leaver, case)
        departed.append(leaver.actor.id_)

    with demo_gate(
        "every other participant's departure recorded before the Case Owner"
        " leaves (CM-23-015)"
    ):
        store_id = resolve_case_actor_store_id(authority_client, case.id_)
        for leaver in others:
            wait_for_participant_rm_state(
                client=authority_client,
                case_id=case.id_,
                actor_id=leaver.actor.id_,
                expected_states={RM.CLOSED},
                dl_actor_id=store_id,
            )
        _leave(owner, case)
        departed.append(owner_id)
        prefix = f"{milestone}: " if milestone else ""
        with demo_check(
            f"{prefix}every departure recorded before case_fully_closed"
            " (CM-23-015)"
        ):
            verify_case_closure_recorded(
                client=authority_client,
                case_id=case.id_,
                departed_actor_ids=departed,
            )

    return departed


def _leave(leaver: CaseLeaver, case: as_VulnerabilityCase) -> None:
    """Send ``Leave(VulnerabilityCase)`` for *leaver* (ADR-0050)."""
    with demo_step(f"Actor {ref_id(leaver.actor)} closes case"):
        ActorSession(client=leaver.client, actor=leaver.actor).with_case(
            case
        ).quiet().close_case()
