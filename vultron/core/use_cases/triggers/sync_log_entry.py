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

"""Demo-only trigger: commit a canonical case ledger entry and fan it out.

:class:`SvcSyncLogEntryUseCase` is the use case behind
``POST /actors/{actor_id}/demo/sync-log-entry`` (TRIG-10-004, TRIG-02-006).
It runs :class:`~vultron.core.behaviors.sync.demo_log_entry.CommitDemoLogEntryNode`
through the shared
:class:`~vultron.core.use_cases.triggers._base.SvcBTTriggerBase` template so
the verb has a registry row like every other trigger (TRIG-12-004) instead of
building its own ``BTBridge`` inside the route.

The tree executes as the case's CASE_MANAGER, not as the requesting actor:
only the authority appends to the canonical log (CLP-09), and a BT's store
follows its executing actor (BT-05-005), so the entry is read back from that
actor's store.  No HTTP framework imports.
"""

import logging
from typing import cast

import py_trees.behaviour

from vultron.core.behaviors.store_scope import hosts_actor
from vultron.core.behaviors.sync.demo_log_entry import CommitDemoLogEntryNode
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.use_case_result import SyncLogEntryResult
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.sync_helpers import recorded_entries_for_case
from vultron.core.use_cases._helpers import _find_case_actor_id
from vultron.core.use_cases.triggers._base import SvcBTTriggerBase
from vultron.core.use_cases.triggers._helpers import resolve_actor
from vultron.core.use_cases.triggers.requests import (
    SyncLogEntryTriggerRequest,
)
from vultron.errors import VultronCanonicalEntryError

logger = logging.getLogger(__name__)


class SvcSyncLogEntryUseCase(SvcBTTriggerBase[SyncLogEntryResult]):
    """Mint a canonical ``CaseLedgerEntry`` for a case and fan it out.

    The payload snapshot is the case authority's factory-built
    ``Announce(VulnerabilityCase)``, committed from its sealed blob
    (VM-08-003), so the entry passes canonical validation (CLP-07); the
    caller-supplied ``semantic_type`` and ``object_id`` are recorded verbatim.
    The fan-out rides on the ``sync_port`` the dispatcher injects
    (SYNC-02-002).
    """

    def _prepare(self) -> None:
        request = cast(SyncLogEntryTriggerRequest, self._request)
        requester = resolve_actor(request.actor_id, self._dl)
        self._case_id: str = request.case_id
        self._object_id: str = request.object_id
        self._semantic_type: str = request.semantic_type
        # The tree runs as the case's authority (CLP-09); a case whose
        # authority cannot be resolved is committed by the requester itself,
        # which is the demo's single-actor shape.
        self._actor_id = (
            _find_case_actor_id(self._dl, self._case_id) or requester.id_
        )
        # Only the store holding the canonical log mints in it, and a tree
        # never runs as an actor this container does not host (CLP-10-014,
        # BT-05-005, ADR-0109): refuse before any tree runs.
        if not hosts_actor(self._dl, self._actor_id):
            raise VultronCanonicalEntryError(
                "sync-log-entry: no canonical entry can be recorded for case"
                f" '{self._case_id}' (semantic_type={self._semantic_type!r}) here;"
                f" its CASE_MANAGER '{self._actor_id}' is not hosted on this"
                " container, so this store does not hold its canonical log"
            )

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        self._node = CommitDemoLogEntryNode(
            case_id=self._case_id,
            object_id=self._object_id,
            semantic_type=self._semantic_type,
        )
        return self._node

    def _handle_result(self) -> None:
        # Read back from the store the commit ran *in*, not the requester's:
        # the entry was written to the executing actor's store (BT-05-005).
        commit_dl: CasePersistence = self._dl
        if self._actor_id != self._dl.actor_id:
            commit_dl = self._dl.clone_for_actor(self._actor_id)
        activity_ids = set(self._node.committed_activity_ids)
        entry = next(
            (
                e
                for e in reversed(
                    recorded_entries_for_case(
                        case_id=self._case_id, dl=commit_dl
                    )
                )
                if e.log_object_id == self._object_id
                and e.semantic_type == self._semantic_type
                and e.payload_snapshot.get("id") in activity_ids
            ),
            None,
        )
        if entry is None:
            # The tree reported SUCCESS without a commit this lookup finds.
            # The node matches the activity it committed, so this is a node
            # fault: an unhosted CASE_MANAGER was refused in ``_prepare`` and
            # the ledger-store guard raises rather than declining (CLP-10-014).
            # Raising here means the router queues no flush, so the fan-out
            # would wait in the CASE_MANAGER's outbox for its next drain.
            raise VultronCanonicalEntryError(
                "sync-log-entry: no canonical entry was recorded for case"
                f" '{self._case_id}' (semantic_type={self._semantic_type!r});"
                f" actor '{self._actor_id}' does not hold its canonical log"
            )
        self._entry: CaseLedgerEntry = entry
        logger.info(
            "Actor '%s' committed ledger entry %d (%s) for case '%s'",
            self._actor_id,
            entry.log_index,
            self._semantic_type,
            self._case_id,
        )

    def _build_result(self) -> SyncLogEntryResult:
        return SyncLogEntryResult(
            log_entry_id=self._entry.id_,
            entry_hash=self._entry.entry_hash,
            log_index=self._entry.log_index,
            emitting_actor_id=self._actor_id,
        )
