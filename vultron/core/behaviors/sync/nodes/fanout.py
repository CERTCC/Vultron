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
"""Fan-out action nodes for SYNC log-replication with RM.CLOSED filtering.

Provides filtered variants of the standard fan-out nodes used when already-closed
participants must be skipped.  The canonical use-case is the ``case_fully_closed``
ledger entry emitted on owner-Leave receive (CM-23-004).
"""

from __future__ import annotations

import logging
from typing import Any, cast

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import VultronCaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.participant_status import (
    ParticipantStatus,
    participant_status_rm_state,
)
from vultron.core.states.rm import RM
from vultron.core.ports.sync_activity import SyncActivityPort

logger = logging.getLogger(__name__)


class CollectNonClosedLogEntryRecipientsNode(DataLayerAction):
    """Collect fan-out recipients, excluding actors already at RM.CLOSED.

    Like ``CollectLogEntryRecipientsNode`` but filters out any participant
    whose latest RM state is ``RM.CLOSED``.  Used for the ``case_fully_closed``
    fan-out so that already-closed participants are not re-notified (CM-23-004).
    """

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="log_entry", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="fanout_recipients", access=py_trees.common.Access.WRITE
        )

    def _is_rm_closed(self, participant_id: str) -> bool:
        assert self.datalayer is not None
        if not participant_id:
            return False
        participant = self.datalayer.read(participant_id)
        if not isinstance(participant, CaseParticipant):
            return False
        for ps_ref in participant.participant_statuses:
            if isinstance(ps_ref, str):
                ref_id = _as_id(ps_ref)
                ps = self.datalayer.read(ref_id) if ref_id else None
            else:
                ps = ps_ref
            if not isinstance(ps, ParticipantStatus):
                continue
            if participant_status_rm_state(ps) == RM.CLOSED:
                return True
        return False

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        entry = cast(VultronCaseLedgerEntry, self.blackboard.log_entry)
        case_obj = self.datalayer.read(self.case_id)
        if not isinstance(case_obj, VulnerabilityCase):
            self.logger.warning(
                "%s: case '%s' not found; skipping fan-out for '%s'",
                self.name,
                self.case_id,
                entry.id_,
            )
            self.blackboard.fanout_recipients = []
            return Status.SUCCESS

        recipients = [
            actor_id
            for actor_id in case_obj.actor_participant_index.keys()
            if actor_id != self.actor_id
            and not self._is_rm_closed(
                case_obj.actor_participant_index.get(actor_id, "")
            )
        ]
        self.blackboard.fanout_recipients = recipients
        return Status.SUCCESS


class _SendLogEntryToEachNode(DataLayerAction):
    """Send the log entry to each recipient in ``fanout_recipients``."""

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._sync_port: SyncActivityPort | None = None

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="log_entry", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="fanout_recipients", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="sync_port", access=py_trees.common.Access.READ
        )

    def initialise(self) -> None:
        super().initialise()
        try:
            self._sync_port = cast(SyncActivityPort, self.blackboard.sync_port)
        except (AttributeError, KeyError):
            self._sync_port = None

    def update(self) -> Status:
        if self.actor_id is None:
            self.logger.error("%s: actor_id not available", self.name)
            return Status.FAILURE

        entry = cast(VultronCaseLedgerEntry, self.blackboard.log_entry)
        recipients = cast(list, self.blackboard.fanout_recipients)
        if self._sync_port is None:
            self.logger.debug(
                "%s: sync_port not injected; skipping fan-out for '%s'",
                self.name,
                entry.id_,
            )
            return Status.SUCCESS

        for recipient_id in recipients:
            self._sync_port.send_announce_log_entry(
                entry=entry,
                actor_id=self.actor_id,
                to=[recipient_id],
            )
        self.logger.info(
            "%s: fanned out log entry '%s' to %d recipients",
            self.name,
            entry.id_,
            len(recipients),
        )
        return Status.SUCCESS


class FanOutLogEntryExcludingClosedNode(py_trees.composites.Sequence):
    """Fan-out that skips participants already at RM.CLOSED (CM-23-004).

    Used for the ``case_fully_closed`` ledger entry so that already-closed
    participants are not re-notified.
    """

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(
            name=name or self.__class__.__name__,
            memory=False,
            children=[
                CollectNonClosedLogEntryRecipientsNode(
                    case_id=case_id,
                    name="CollectNonClosedLogEntryRecipients",
                ),
                _SendLogEntryToEachNode(name="SendLogEntryToEach"),
            ],
        )
