#!/usr/bin/env python
#
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

"""Replay's read side: the CASE_MANAGER, the sorted ledger, the divergence point.

The nodes ahead of the send in ``ReplayMissingEntriesNode`` (SYNC-03-002).
"""

from __future__ import annotations

import logging
from typing import cast

from py_trees.common import Status

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.sync.nodes.embargo_pause import (
    sorted_case_ledger_entries,
)
from vultron.core.behaviors.sync.nodes.replay_case import (
    CaseNamedReplayNode,
    scoped_keys,
)
from vultron.core.models.case_ledger_entry import (
    CaseLedgerEntry,
)
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.ports.case_persistence import CasePersistence
from vultron.errors import (
    VultronError,
)

logger = logging.getLogger(__name__)


class FindCaseActorNode(CaseNamedReplayNode):
    """Resolve the authority's address, and publish the case id for later gates.

    The address is the ``CVDRole.CASE_MANAGER`` role-holder's, resolved through
    the single neutral resolver (ADR-0088, ARCH-24-001), never a ``Service``
    whose ``context`` is the case (ARCH-24-004).  This node resolves an
    *address*; it does not decide authority, which is the CASE_MANAGER gate
    the factory wraps around the effects (ARCH-24-005).  The case is
    *case_id* when the tree names it, else the activity's ``replay_case_id``.

    ``case_id`` is an output so a later node can read the case from the
    blackboard (CLP-09); ``CheckIsCaseManagerNode`` falls back to it when it
    is built without a case id.

    Failing is deliberate: a FAILURE stops the sequence, so no replay runs
    under a guessed identity.  It means the executing actor cannot answer for
    this log: it does not hold the case, or the case names no CASE_MANAGER.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=True),
    }

    # See the class docstring: ``case_id`` is published for later nodes.
    OUTPUT_PORTS: dict[str, PortInformation] = {
        "case_actor_id": PortInformation(data_type=str, required=True),
        "case_id": PortInformation(data_type=str, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "activity": "/activity",
            "case_actor_id": "/case_actor_id",
            "case_id": "/case_id",
        }

    def __init__(
        self,
        name: str | None = None,
        *,
        case_id: str | None = None,
        scope: str | None = None,
    ) -> None:
        super().__init__(name=name, case_id=case_id)
        self.scope = scope

    def _instance_port_remappings(self) -> dict[str, str]:
        return scoped_keys(self.scope, "case_actor_id", "case_id")

    def initialise(self) -> None:
        super().initialise()
        self.activity = self.get_input("activity")

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        case_id = self.replay_case(self.activity)
        self._set_output("case_id", case_id)

        # Regime 1 (ADR-0087): a peer is asking us to replay this case's log,
        # so the case must be here — its absence is an anomaly, not a branch.
        case, failure = self._require_case(case_id)
        if failure is not None:
            return failure

        case_actor_id = resolve_case_manager_id(case, self.datalayer)
        if case_actor_id is None:
            self.logger.warning(
                "%s: no CASE_MANAGER participant for case '%s'",
                self.name,
                case_id,
            )
            return Status.FAILURE

        self._set_output("case_actor_id", case_actor_id)
        return Status.SUCCESS


class CollectAndSortCaseLedgerEntriesNode(CaseNamedReplayNode):
    """Publish the case's sorted ledger and the peer (the activity's sender).

    The case is *case_id* when given, else the activity's ``replay_case_id``.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=True),
    }

    OUTPUT_PORTS: dict[str, PortInformation] = {
        "replay_case_id": PortInformation(data_type=str, required=True),
        "replay_peer_id": PortInformation(data_type=str, required=True),
        "replay_case_ledger_entries": PortInformation(
            data_type=object, required=True
        ),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "activity": "/activity",
            "replay_case_id": "/replay_case_id",
            "replay_peer_id": "/replay_peer_id",
            "replay_case_ledger_entries": "/replay_case_ledger_entries",
        }

    def initialise(self) -> None:
        super().initialise()
        self.activity = self.get_input("activity")

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        activity = self.activity
        case_id = self.replay_case(activity)
        peer_id = activity.actor_id
        if not peer_id:
            raise VultronError(
                f"{self.name}: replay request missing peer actor_id"
            )

        entries = sorted_case_ledger_entries(
            cast(CasePersistence, self.datalayer), case_id
        )

        self._set_output("replay_case_id", case_id)
        self._set_output("replay_peer_id", peer_id)
        self._set_output("replay_case_ledger_entries", entries)
        return Status.SUCCESS


class FindDivergenceIndexNode(DataLayerActionWithPorts):
    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=True),
        "replay_case_ledger_entries": PortInformation(
            data_type=object, required=True
        ),
    }

    OUTPUT_PORTS: dict[str, PortInformation] = {
        "replay_from_index": PortInformation(data_type=int, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "activity": "/activity",
            "replay_case_ledger_entries": "/replay_case_ledger_entries",
            "replay_from_index": "/replay_from_index",
        }

    def initialise(self) -> None:
        super().initialise()
        self.activity = self.get_input("activity")
        self.replay_case_ledger_entries = self.get_input(
            "replay_case_ledger_entries"
        )

    def update(self) -> Status:
        entries = cast(list[CaseLedgerEntry], self.replay_case_ledger_entries)
        from_hash = self.activity.last_accepted_hash
        from_index = -1
        for log_entry in entries:
            if log_entry.entry_hash == from_hash:
                from_index = log_entry.log_index
                break

        self._set_output("replay_from_index", from_index)
        return Status.SUCCESS
