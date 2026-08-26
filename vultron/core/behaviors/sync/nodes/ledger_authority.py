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
    """SUCCESS when this store is not the one whose ledger is being appended to.

    ``CommitLogEntryBT`` mints a canonical index and fans the entry out to the
    case's participants.  Only the store that *holds* that canonical log may do
    either: an index is a claim on a position in one hash chain, and two stores
    claiming the same position fork it irreparably (CLP-08-005).

    The delegated-emit path is how a second claimant arises.  A trigger the case
    *owner* runs emits as the CaseActor — ``actor`` is the CaseActor,
    ``attributedTo`` the owner (PCR-08-007, CM-24-001) — and the emit node
    commits the ledger entry under that same ``actor_id``.  When the owner hosts
    the CaseActor, ``BTBridge._store_for_actor`` hands the tree the CaseActor's
    own store and the commit is the canonical one.  After an ownership handoff it
    does not: the CaseActor stays on the container that first received the report
    (CP-08-003) while the owner is elsewhere, and the bridge deliberately falls
    through to the *requester's* store so the activity is created and outboxed
    where it can actually be delivered (BT-05-005).  Without this guard the
    commit rides along on that fall-through and mints index N in the owner's
    replica while the real CaseActor mints its own index N from the ``cc:`` copy
    — two entries, one position, different bytes, because the owner's snapshot
    carries local enrichment (``attributedTo``, ``name``, the case's
    ``caseStatus``) the wire copy does not (CM-17-002).  Both then fan out, and
    the case partitions into the participants each reached first (#2626).

    Declining is not a lost entry.  The activity still goes out with the
    CaseActor ``cc:``'d, so the canonical log gains it the only way a remote
    store ever can (CLP-10-001), and the owner's replica gains it by replication
    from that log — byte-identical, as a replica must be (DL-07-009).

    SUCCESS means "handled, by declining", so this sits as the first child of a
    Selector ahead of the commit Sequence: every existing caller keeps treating a
    non-SUCCESS tree as a real failure.  FAILURE means "not foreign — go commit".

    Reuses :func:`~vultron.core.behaviors.store_scope.store_for_actor` with the
    same ``require_same_authority`` the bridge uses, so the guard and the
    fall-through it guards cannot drift on what "not hosted here" means.  A store
    that reports no ``actor_id`` — a test double — is never foreign, and such
    callers commit exactly as they did before per-actor storage.

    Spec: BT-05-006, CLP-08-005, CLP-10-001, DL-07-009.  Per ADR-0073.
    """

    def update(self) -> Status:
        if self.datalayer is None or not self.actor_id:
            # Nothing to compare; the commit nodes downstream raise their own
            # clearer error for a missing store or actor.
            return Status.FAILURE
        if (
            store_for_actor(
                self.datalayer, self.actor_id, require_same_authority=True
            )
            is not None
        ):
            return Status.FAILURE
        self.logger.info(
            "%s: not minting a canonical ledger index for '%s' — this store"
            " belongs to '%s' and does not host that actor's log; the entry"
            " arrives by replication from it (CLP-10-001)",
            self.name,
            self.actor_id,
            getattr(self.datalayer, "actor_id", None),
        )
        return Status.SUCCESS


__all__ = ["DeclineForeignLedgerCommitNode"]
