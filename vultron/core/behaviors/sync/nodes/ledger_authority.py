#!/usr/bin/env python

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

"""Guard for the one store allowed to mint a canonical ledger index."""

from __future__ import annotations

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerActionWithPorts
from vultron.core.behaviors.store_scope import store_for_actor


class DeclineForeignLedgerCommitNode(DataLayerActionWithPorts):
    """Fail fast when this store is not the one whose ledger is being appended to.

    **This is a store-consistency / anti-fork invariant, not an authority
    check** (ARCH-24-005). It never asks "is this actor the case authority" —
    that question has exactly one answer, the ``CVDRole.CASE_MANAGER`` role via
    ``CheckIsCaseManagerNode`` (ADR-0088, ARCH-24-003), and it has already been
    answered by the guarded-commit composition upstream of here. This node
    asserts the strictly downstream fact: *given* that role-authority said "you
    may commit", the store in hand is the one that holds the log. Conflating the
    two would make the role look like a property of a store, which it is not.

    ``CommitLogEntryBT`` mints a canonical index and fans the entry out to the
    case's participants.  Only the store that *holds* that canonical log may do
    either: an index is a claim on a position in one hash chain, and two stores
    claiming the same position fork it irreparably (CLP-08-005, #2626).

    No sanctioned path reaches this node with a foreign store.  A container
    executes trees only as actors it hosts, and a participant whose container
    does not host the CASE_MANAGER reaches it by sending the CASE_MANAGER its
    own activity (CM-24-004, ADR-0109); ``BTBridge._store_for_actor`` already
    refuses an unhosted executing actor before any tree ticks (BT-05-005).
    Reaching this node as one is therefore a programming error, and it raises
    :class:`~vultron.errors.VultronUnhostedActorError` having written nothing,
    rather than reporting a decline as success (CLP-10-014).  The name is kept
    from the retired declining guard, so the commit tree's first child is still
    found under it.

    ``SUCCESS`` means "this store holds the log — go commit".  It is the first
    child of the commit Sequence, so a raise stops the tree before the port
    guard, the chain reconstruction, the persist or the fan-out run.

    Reuses :func:`~vultron.core.behaviors.store_scope.store_for_actor` with the
    same ``require_same_authority`` the bridge uses, so the two cannot drift on
    what "not hosted here" means.  A store that reports no ``actor_id`` — a test
    double — is never foreign, and such callers commit exactly as they did
    before per-actor storage.

    Spec: BT-05-005, BT-05-006, CLP-08-005, CLP-10-014, DL-07-009, ARCH-24-005.
    Per ADR-0073, reclassified by ADR-0088, made fail-fast by ADR-0109.
    """

    def update(self) -> Status:
        if self.datalayer is None or not self.actor_id:
            # Nothing to compare; the commit nodes downstream raise their own
            # clearer error for a missing store or actor.
            return Status.SUCCESS
        # Raises VultronUnhostedActorError for an actor this store's node
        # does not host; nothing has been written yet.
        store_for_actor(
            self.datalayer, self.actor_id, require_same_authority=True
        )
        return Status.SUCCESS


__all__ = ["DeclineForeignLedgerCommitNode"]
