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
It runs ``create_commit_log_entry_tree`` through the shared
:class:`~vultron.core.use_cases.triggers._base.SvcBTTriggerBase` template so
the verb has a registry row like every other trigger (TRIG-12-004) instead of
building its own ``BTBridge`` inside the route.

The tree executes as the case's CASE_MANAGER, not as the requesting actor:
only the authority appends to the canonical log (CLP-09), and a BT's store
follows its executing actor (BT-05-005), so the entry is read back from that
actor's store.  No HTTP framework imports.
"""

import logging
from typing import Any, cast

import py_trees.behaviour

from vultron.core.behaviors.sync.commit_tree import (
    create_commit_log_entry_tree,
)
from vultron.core.models._helpers import now_utc
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.use_case_result import SyncLogEntryResult
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.sync_helpers import _find_equivalent_recorded_entry
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

    The payload snapshot is a canonical ``Announce(VulnerabilityCase)``
    authored by the case's authority, so the entry passes canonical validation
    (CLP-07); the caller-supplied ``event_type`` is recorded verbatim.  The
    fan-out rides on the ``sync_port`` the dispatcher injects (SYNC-02-002).
    """

    # The commit tree emits through ``sync_port``; it never builds a
    # trigger-side activity, so the port guard in the template is skipped.
    _requires_trigger_activity = False

    def _prepare(self) -> None:
        request = cast(SyncLogEntryTriggerRequest, self._request)
        requester = resolve_actor(request.actor_id, self._dl)
        self._case_id: str = request.case_id
        self._object_id: str = request.object_id
        self._event_type: str = request.event_type
        # The tree runs as the case's authority (CLP-09); a case whose
        # authority cannot be resolved is committed by the requester itself,
        # which is the demo's single-actor shape.
        self._actor_id = (
            _find_case_actor_id(self._dl, self._case_id) or requester.id_
        )
        self._payload_snapshot: dict[str, Any] = {
            "type": "Announce",
            "object": {"type": "VulnerabilityCase", "id": self._case_id},
            "actor": self._actor_id,
            # CLP-07-011: a recorded snapshot is the verbatim AS2 activity, and
            # an AS2 activity always carries ``published``; the commit boundary
            # refuses a snapshot without one (ISSUE-2824).
            "published": now_utc().isoformat(),
            "context": self._case_id,
        }

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        return create_commit_log_entry_tree(
            case_id=self._case_id,
            object_id=self._object_id,
            event_type=self._event_type,
            payload_snapshot=self._payload_snapshot,
        )

    def _handle_result(self) -> None:
        # Read back from the store the commit ran *in*, not the requester's:
        # the entry was written to the executing actor's store (BT-05-005).
        commit_dl: CasePersistence = self._dl
        if self._actor_id != self._dl.actor_id:
            commit_dl = self._dl.clone_for_actor(self._actor_id)
        entry = _find_equivalent_recorded_entry(
            case_id=self._case_id,
            object_id=self._object_id,
            event_type=self._event_type,
            payload_snapshot=self._payload_snapshot,
            dl=commit_dl,
        )
        if entry is None:
            # The tree reported SUCCESS without a commit: the ledger-authority
            # guard declined because this store does not hold the canonical
            # log (ADR-0073, CLP-10-014).  Not a client fault and not a bug in
            # a node, so it is neither 4xx nor a ``RuntimeError``.  Raising
            # here means the router queues no flush; had the tree committed
            # and the lookup still missed (it compares the snapshot the tree
            # recorded, so that would be a node bug), the fan-out would wait
            # in the CASE_MANAGER's outbox for its next drain.
            raise VultronCanonicalEntryError(
                "sync-log-entry: no canonical entry was recorded for case"
                f" '{self._case_id}' (event_type={self._event_type!r});"
                f" actor '{self._actor_id}' does not hold its canonical log"
            )
        self._entry: CaseLedgerEntry = entry
        logger.info(
            "Actor '%s' committed ledger entry %d (%s) for case '%s'",
            self._actor_id,
            entry.log_index,
            self._event_type,
            self._case_id,
        )

    def _build_result(self) -> SyncLogEntryResult:
        return SyncLogEntryResult(
            log_entry_id=self._entry.id_,
            entry_hash=self._entry.entry_hash,
            log_index=self._entry.log_index,
            emitting_actor_id=self._actor_id,
        )
