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
"""Fan-out action nodes for SYNC log-replication.

Standard fan-out (every case addressee):
  ``CollectLogEntryRecipientsNode`` + ``SendLogEntryToEachNode`` →
  composed as ``FanOutLogEntryNode``.

Closed-filtered fan-out (skip already-closed participants):
  ``CollectNonClosedLogEntryRecipientsNode`` + ``SendLogEntryToEachNode`` →
  composed as ``FanOutLogEntryExcludingClosedNode`` (CM-23-004).

Both collectors apply the CM-10-004 embargo content gate through the shared
predicate (``vultron.core.participants.embargo_gate``, CM-10-007): a participant
that has not accepted the active embargo is moved from ``fanout_recipients`` to
``fanout_withheld``. The send node pauses a withheld peer's stream from this
entry on (CM-10-005) and, before sending, backfills any paused peer the gate now
admits (CM-10-006) — see ``embargo_pause.py``.
"""

from __future__ import annotations

import logging
from typing import cast

import py_trees
from py_trees.common import Status
from py_trees.ports import NoDataAvailable

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.sync.nodes.embargo_pause import (
    backfill_admitted_peers,
    record_embargo_pause,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase, case_addressees
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.participant_status import (
    ParticipantStatus,
    participant_status_rm_state,
)
from vultron.core.participants.embargo_gate import embargo_withheld_actor_ids
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.states.rm import RM
from vultron.errors import VultronError

logger = logging.getLogger(__name__)

#: Output ports both recipient collectors declare.
_COLLECTOR_OUTPUT_PORTS: dict[str, PortInformation] = {
    "fanout_recipients": PortInformation(data_type=object, required=True),
    "fanout_withheld": PortInformation(data_type=object, required=True),
}

_COLLECTOR_REMAPPINGS: dict[str, str] = {
    "log_entry": "/log_entry",
    "fanout_recipients": "/fanout_recipients",
    "fanout_withheld": "/fanout_withheld",
}


def _apply_embargo_gate(
    candidates: list[str],
    case_obj: VulnerabilityCase,
    datalayer: CasePersistence,
) -> tuple[list[str], list[str]]:
    """Split *candidates* into ``(recipients, withheld)`` by the CM-10-004 gate.

    Order is preserved in both lists, so the fan-out stays deterministic.
    """
    gate = embargo_withheld_actor_ids(case_obj, datalayer)
    recipients = [actor_id for actor_id in candidates if actor_id not in gate]
    withheld = [actor_id for actor_id in candidates if actor_id in gate]
    return recipients, withheld


class CollectNonClosedLogEntryRecipientsNode(DataLayerActionWithPorts):
    """Collect fan-out recipients, excluding actors already at RM.CLOSED.

    Like ``CollectLogEntryRecipientsNode`` but filters out any participant
    whose latest RM state is ``RM.CLOSED``.  Used for the ``case_fully_closed``
    fan-out so that already-closed participants are not re-notified (CM-23-004).
    """

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "log_entry": PortInformation(data_type=CaseLedgerEntry, required=True),
    }

    OUTPUT_PORTS: dict[str, PortInformation] = _COLLECTOR_OUTPUT_PORTS

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return dict(_COLLECTOR_REMAPPINGS)

    def initialise(self) -> None:
        super().initialise()
        self.log_entry = self.get_input("log_entry")

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

        # Regime 1 (ADR-0087, #3101): fan-out runs after the local commit
        # persisted this entry to the case (DeclineForeignLedgerCommitNode
        # already handled the not-my-case branch upstream), so a missing case
        # is an anomaly. Previously this warned, emitted zero recipients, and
        # returned SUCCESS — silently dropping replication of a committed entry
        # even though the commit tree treats non-SUCCESS as a real failure
        # (ADR-0073, BT-05-006).
        case_obj, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure

        candidates = [
            actor_id
            for actor_id in case_obj.actor_participant_index
            if actor_id != self.actor_id
            and not self._is_rm_closed(
                case_obj.actor_participant_index.get(actor_id, "")
            )
        ]
        recipients, withheld = _apply_embargo_gate(
            candidates, case_obj, self.datalayer
        )
        self._set_output("fanout_recipients", recipients)
        self._set_output("fanout_withheld", withheld)
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
                SendLogEntryToEachNode(name="SendLogEntryToEach"),
            ],
        )


# ---------------------------------------------------------------------------
# Unfiltered fan-out — moved here from ``replay.py`` (BTND-07-004).
#
# These are the plain fan-out nodes; the filtered variants above skip
# participants already at RM.CLOSED.  They lived in ``replay.py`` because
# reject-driven replay was written first, but fan-out is a distinct concern:
# replay is catch-up for one lagging peer, fan-out is distribution of one
# entry to every recipient.  Keeping both fan-out flavours in one module also
# makes the filtered/unfiltered choice visible in one place.
# ---------------------------------------------------------------------------


class CollectLogEntryRecipientsNode(DataLayerActionWithPorts):
    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "log_entry": PortInformation(data_type=CaseLedgerEntry, required=True),
    }

    OUTPUT_PORTS: dict[str, PortInformation] = _COLLECTOR_OUTPUT_PORTS

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return dict(_COLLECTOR_REMAPPINGS)

    def initialise(self) -> None:
        super().initialise()
        self.log_entry = self.get_input("log_entry")

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        # Regime 1 (ADR-0087, #3101): see CollectNonClosedLogEntryRecipientsNode
        # — fan-out follows a local commit, so a missing case is an anomaly, not
        # a silent zero-recipient SUCCESS.
        case_obj, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure

        recipients, withheld = _apply_embargo_gate(
            case_addressees(case_obj, excluding_actor_id=self.actor_id),
            case_obj,
            self.datalayer,
        )
        self._set_output("fanout_recipients", recipients)
        self._set_output("fanout_withheld", withheld)
        return Status.SUCCESS


class SendLogEntryToEachNode(DataLayerActionWithPorts):
    """Send the log entry to each recipient, applying the embargo pause.

    Reads ``fanout_recipients`` and, when a collector supplied it,
    ``fanout_withheld``. With a sync port injected it:

    1. records a pause from this entry's ``log_index`` for every withheld peer
       (CM-10-005) — a pause already on record keeps its earlier index;
    2. backfills, through the entry just before this one, every paused peer the
       gate now admits (CM-10-006), so the backfill reaches it in log order
       before this entry does;
    3. sends this entry to each recipient.

    Step 2 admits a peer whose admission preceded this entry's commit:
    ``terminate_embargo_bt`` ends the embargo, then commits the new case
    status. A received activity commits before its effect admits anyone, so
    that case is covered by ``BackfillAdmittedParticipantsNode`` instead. The
    gate is recomputed over the whole case in step 2, not read from
    ``fanout_withheld``, because a collector may filter peers (e.g. RM.CLOSED)
    before it gates.
    """

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._sync_port: SyncActivityPort | None = None

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "log_entry": PortInformation(data_type=CaseLedgerEntry, required=True),
        "fanout_recipients": PortInformation(data_type=object, required=True),
        "fanout_withheld": PortInformation(data_type=object, required=False),
        "sync_port": PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "log_entry": "/log_entry",
            "fanout_recipients": "/fanout_recipients",
            "fanout_withheld": "/fanout_withheld",
            "sync_port": "/sync_port",
        }

    def initialise(self) -> None:
        super().initialise()
        self.log_entry = self.get_input("log_entry")
        self.fanout_recipients: list = self.get_input("fanout_recipients")
        try:
            self.fanout_withheld: list[str] = list(
                self.get_input("fanout_withheld") or []
            )
        except (NoDataAvailable, NotImplementedError):
            self.fanout_withheld = []
        try:
            self._sync_port = cast(
                SyncActivityPort, self.get_input("sync_port")
            )
        except (NoDataAvailable, NotImplementedError):
            self._sync_port = None

    def _pause_and_backfill(
        self, entry: CaseLedgerEntry, sync_port: SyncActivityPort
    ) -> None:
        assert self.datalayer is not None
        assert self.actor_id is not None
        datalayer = cast(CasePersistence, self.datalayer)
        for peer_id in self.fanout_withheld:
            record_embargo_pause(
                datalayer,
                case_id=entry.case_id,
                peer_id=peer_id,
                from_index=entry.log_index,
            )
        case_obj = datalayer.read(entry.case_id)
        if not isinstance(case_obj, VulnerabilityCase):
            # The collector already required the case; reaching here without
            # one means the store changed under the tick.
            raise VultronError(
                f"{self.name}: case '{entry.case_id}' vanished during fan-out"
            )
        backfill_admitted_peers(
            datalayer,
            case_obj,
            sync_port=sync_port,
            actor_id=self.actor_id,
            through_index=entry.log_index - 1,
        )

    def update(self) -> Status:
        if self.actor_id is None:
            self.logger.error("%s: actor_id not available", self.name)
            return Status.FAILURE

        entry = cast(CaseLedgerEntry, self.log_entry)
        recipients = cast(list[str], self.fanout_recipients)
        if self._sync_port is None:
            self.logger.debug(
                "%s: sync_port not injected; skipping fan-out for '%s'",
                self.name,
                entry.id_,
            )
            return Status.SUCCESS

        if self.datalayer is not None:
            try:
                self._pause_and_backfill(entry, self._sync_port)
            except VultronError as exc:
                self.feedback_message = str(exc)
                self.logger.exception(
                    "%s: embargo gate undecidable", self.name
                )
                return Status.FAILURE

        for recipient_id in recipients:
            self._sync_port.send_announce_log_entry(
                entry=entry,
                actor_id=self.actor_id,
                to=[recipient_id],
            )
        self.logger.info(
            "%s: fanned out log entry '%s' to %d recipients"
            " (%d withheld by the embargo gate — CM-10-005)",
            self.name,
            entry.id_,
            len(recipients),
            len(self.fanout_withheld),
        )
        return Status.SUCCESS


class FanOutLogEntryNode(py_trees.composites.Sequence):
    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(
            name=name or self.__class__.__name__,
            memory=False,
            children=[
                CollectLogEntryRecipientsNode(
                    case_id=case_id,
                    name="CollectLogEntryRecipients",
                ),
                SendLogEntryToEachNode(name="SendLogEntryToEach"),
            ],
        )
