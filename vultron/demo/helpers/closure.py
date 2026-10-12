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
It also runs the whole closure milestone, which depends on the owner having
left.  A participant at RM ``CLOSED`` is sent nothing after the entries that
record its own closure (CM-23-004), so no replica converges on every closure:

- the CASE_MANAGER's own store is where every participant's closure is
  verified — the ledger order
  (:func:`~vultron.demo.helpers.milestones.verify_case_closure_recorded`)
  and every record at ``RM.CLOSED``
  (:func:`~vultron.demo.helpers.milestones.verify_case_closed`);
- each departing participant's replica is checked for its own closure only:
  it holds the ledger through the last entry recording that closure, nothing
  after it, and reads itself ``RM.CLOSED``.  That is the point at which a
  departing participant's replication would exit.

The CASE_MANAGER's store is read where it lives — the dedicated
``case-actor`` container when the topology has one (DEMOMA-06-004) —
through :func:`~vultron.demo.helpers.polling.case_manager_client`.
"""

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from vultron.core.states.rm import RM
from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers.milestones import (
    case_manager_ledger,
    own_closure_tail_index,
    verify_case_closed,
    verify_case_closure_recorded,
)
from vultron.demo.helpers.polling import (
    case_manager_client,
    wait_for_participant_rm_state,
)
from vultron.demo.helpers.sync import wait_for_replica_ledger_ending_at
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
    (CM-23-003).  That store is read where it lives, found through
    *authority_client* (:func:`~vultron.demo.helpers.polling
    .case_manager_client`).  When a departure is not recorded in time the
    gate fails once and the owner does not leave: an owner ``Leave`` sent
    then would close the case over a departure the ledger might never
    record (CM-23-013).

    Once the owner has left, the closure milestone runs, each part in its
    own ``demo_check``:

    1. the CASE_MANAGER's ledger records every departure before
       ``case_fully_closed`` and no participant act after it
       (:func:`~vultron.demo.helpers.milestones.verify_case_closure_recorded`);
    2. every participant is ``RM.CLOSED`` in the CASE_MANAGER's store
       (:func:`~vultron.demo.helpers.milestones.verify_case_closed`);
    3. each departing participant's own replica holds the ledger through the
       last entry recording its own closure and nothing after it, and reads
       itself ``RM.CLOSED`` (CM-23-004).  This is the leaver waiting for its
       own closure entry before it exits; it is never sent a later closure
       or ``case_fully_closed``, so no replica is checked for those.

    They are skipped with the owner's ``Leave`` when the gate fails, so the
    one failure names the cause.

    Args:
        case: The case being closed.
        authority_client: Client for a container holding the case, through
            which the CASE_MANAGER is found: the host of its CaseActor when
            co-hosted, otherwise any participant's container.
        others: Every participant other than the Case Owner, in the order
            they leave.  Each MUST be distinct from *owner*.
        owner: The participant holding ``CASE_OWNER`` at closure.
        milestone: The scenario's label for its closure milestone (``"M7"``),
            prefixed to each check's description; ``None`` for none.

    Returns:
        The actor ids of every participant whose ``Leave`` step ran, in that
        order, the owner last; the owner is missing when the gate failed.

    Raises:
        ValueError: If *owner* is also listed in *others*, which would
            send the owner's ``Leave`` before the others have left.

    Spec: CM-23-015, CM-23-013, CM-23-004, CM-23-003, EDF-06-002.
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
        manager = case_manager_client(authority_client, case.id_)
        for leaver in others:
            wait_for_participant_rm_state(
                client=manager,
                case_id=case.id_,
                actor_id=leaver.actor.id_,
                expected_states={RM.CLOSED},
            )
        _leave(owner, case)
        departed.append(owner_id)
        _verify_closure(
            manager, case, [*others, owner], departed, milestone=milestone
        )

    return departed


def _verify_closure(
    manager: DataLayerClient,
    case: as_VulnerabilityCase,
    leavers: Sequence[CaseLeaver],
    departed: list[str],
    *,
    milestone: str | None,
) -> None:
    """Run the closure milestone's checks once the owner has left."""
    prefix = f"{milestone}: " if milestone else ""
    with demo_check(
        f"{prefix}every departure recorded before case_fully_closed"
        " (CM-23-015)"
    ):
        verify_case_closure_recorded(
            client=manager,
            case_id=case.id_,
            departed_actor_ids=departed,
        )
    with demo_check(
        f"{prefix}all participants RM.CLOSED in the CASE_MANAGER's store"
        " (CM-23-004)"
    ):
        verify_case_closed(case_manager_client=manager, case_id=case.id_)
    ledger = case_manager_ledger(manager, case.id_)
    for leaver in leavers:
        with demo_check(
            f"{prefix}{ref_id(leaver.actor)} replica holds its own closure"
            " and nothing after it (CM-23-004) — temporal wait (EDF-06-006)"
        ):
            _verify_own_closure(leaver, case, ledger)


def _verify_own_closure(
    leaver: CaseLeaver,
    case: as_VulnerabilityCase,
    ledger: Sequence[Mapping[str, object]],
) -> None:
    """The leaver's replica ends at its own closure and reads it RM.CLOSED."""
    actor_id = leaver.actor.id_
    tail = own_closure_tail_index(ledger, actor_id)
    if tail is None:
        raise AssertionError(
            f"the CASE_MANAGER's ledger records no close_case entry for"
            f" {actor_id!r}"
        )
    wait_for_replica_ledger_ending_at(leaver.client, case.id_, tail)
    wait_for_participant_rm_state(
        client=leaver.client,
        case_id=case.id_,
        actor_id=actor_id,
        expected_states={RM.CLOSED},
    )


def _leave(leaver: CaseLeaver, case: as_VulnerabilityCase) -> None:
    """Send ``Leave(VulnerabilityCase)`` for *leaver* (ADR-0050)."""
    with demo_step(f"Actor {ref_id(leaver.actor)} closes case"):
        ActorSession(client=leaver.client, actor=leaver.actor).with_case(
            case
        ).quiet().close_case()
