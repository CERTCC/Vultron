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

The one fan-out: ``CollectLogEntryRecipientsNode`` + ``SendLogEntryToEachNode``
→ composed as ``FanOutLogEntryNode``.

The collector picks recipients through the shared selection
(``vultron.core.participants.recipients.ledger_entry_recipients``,
CM-10-007): only active participants receive an entry (CM-10-004), and a
participant at RM ``CLOSED`` receives only the entries that record its own
closure (CM-23-004).  Skipping closed participants is not an option a tree
picks; every fan-out does it.  The collector also publishes, as
``fanout_withheld``, the joined participants that are not active — the
active embargo withholds them, or they were removed (CM-31-001)
(``inactive_joined_participants``). The send node pauses a withheld peer's
stream from this entry on (CM-10-005) and, before sending, backfills any
paused peer the gate now admits (CM-10-006) — see ``embargo_pause.py``.
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
from vultron.core.behaviors.sync.nodes.verified_send import (
    send_verified_log_entry,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.participants.recipients import (
    inactive_joined_participants,
    ledger_entry_recipients,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.errors import (
    VultronError,
    VultronUnverifiedLedgerEntryError,
    VultronWiringError,
)

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


# ---------------------------------------------------------------------------
# Fan-out — moved here from ``replay.py`` (BTND-07-004).
#
# These nodes lived in ``replay.py`` because reject-driven replay was written
# first, but fan-out is a distinct concern: replay is catch-up for one lagging
# peer, fan-out is distribution of one entry to every recipient.
# ---------------------------------------------------------------------------


class CollectLogEntryRecipientsNode(DataLayerActionWithPorts):
    """Collect a ledger entry's fan-out recipients: the active participants.

    Every participant entitled to case content except the sender
    (CM-10-004, SYNC-02-003), chosen by the shared selection (CM-10-007).
    A participant at RM ``CLOSED`` is left out unless the entry records its
    own closure (CM-23-004): the leaver receives its ``close_case`` entry and
    its closure steps, and nothing after them.  The joined participants that
    are not active (not signatories to the active embargo, or removed,
    CM-31-001) go to ``fanout_withheld``, so the send node can pause their
    streams (CM-10-005).
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

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        # Regime 1 (ADR-0087, #3101): fan-out runs after the local commit
        # persisted this entry to the case (DeclineForeignLedgerCommitNode
        # already refused a store that does not hold the log), so a missing case
        # is an anomaly. Previously this warned, emitted zero recipients, and
        # returned SUCCESS — silently dropping replication of a committed entry
        # even though the commit tree treats non-SUCCESS as a real failure
        # (ADR-0073, BT-05-006).
        case_obj, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure

        excluding = {self.actor_id}
        recipients = ledger_entry_recipients(
            case_obj,
            self.datalayer,
            cast(CaseLedgerEntry, self.log_entry),
            excluding=excluding,
        )
        withheld = inactive_joined_participants(
            case_obj, self.datalayer, excluding=excluding
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

    Every send goes through ``send_verified_log_entry`` (SYNC-03-009).  When
    this entry does not verify, it is held back from every recipient, logged
    at ERROR, and the node returns ``FAILURE`` (BT-14-001).  When step 2's
    backfill to a peer is held back at an older entry, that peer keeps its
    pause and is skipped in step 3, since it could hold this entry only as a
    forward gap; every other recipient still gets it and the node returns
    ``SUCCESS``, so one broken old entry does not stop the case committing
    (decided on #5120).

    Step 2 admits a peer whose admission preceded this entry's commit:
    ``terminate_embargo_bt`` ends the embargo, then commits the new case
    status. A received activity commits before its effect admits anyone, so
    that case is covered by ``BackfillAdmittedParticipantsNode`` instead. The
    gate is recomputed over the whole case in step 2, not read from
    ``fanout_withheld``, because the collector filters peers (RM.CLOSED)
    before it gates.

    A missing sync port is a wiring fault and raises ``VultronWiringError``.
    It used to skip at DEBUG and return ``SUCCESS``, which committed an entry
    no replica would ever receive (SYNC-02-003, BT-14-001; #4113).
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
    ) -> list[str]:
        """Pause the withheld peers and backfill the admitted ones.

        Returns the peers whose backfill was held back at an entry that does
        not verify (SYNC-03-009); each keeps its pause.
        """
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
        return backfill_admitted_peers(
            datalayer,
            case_obj,
            sync_port=sync_port,
            actor_id=self.actor_id,
            through_index=entry.log_index - 1,
        ).held_back

    def update(self) -> Status:
        if self.actor_id is None:
            self.logger.error("%s: actor_id not available", self.name)
            return Status.FAILURE

        entry = cast(CaseLedgerEntry, self.log_entry)
        recipients = cast(list[str], self.fanout_recipients)
        if self._sync_port is None:
            raise VultronWiringError(
                f"{self.name}: sync_port must be injected to fan out"
                f" log entry '{entry.id_}' (SYNC-02-003)"
            )

        held_back: list[str] = []
        if self.datalayer is not None:
            try:
                held_back = self._pause_and_backfill(entry, self._sync_port)
            except VultronError as exc:
                self.feedback_message = str(exc)
                self.logger.exception(
                    "%s: embargo gate undecidable", self.name
                )
                return Status.FAILURE

        if held_back:
            # SYNC-03-009, decided on #5120: a peer whose catch-up stopped at
            # a broken older entry stays paused and is skipped for this one,
            # which it could hold only as a forward gap.  Everyone else still
            # gets it, so the case keeps committing.  send_ledger_suffix
            # already logged the hold-back at ERROR.
            self.logger.warning(
                "%s: skipping %s for log entry '%s': their catch-up was held"
                " back at an entry that does not verify (SYNC-03-009)",
                self.name,
                held_back,
                entry.id_,
            )
            recipients = [r for r in recipients if r not in held_back]

        try:
            for recipient_id in recipients:
                send_verified_log_entry(
                    self._sync_port,
                    entry,
                    actor_id=self.actor_id,
                    to=[recipient_id],
                )
        except VultronUnverifiedLedgerEntryError as exc:
            # The first send checks the entry, so no recipient got it.
            self.feedback_message = str(exc)
            self.logger.error(  # noqa: TRY400 -- the hold-back is the report
                "%s: %s; not sent to any of %s",
                self.name,
                exc,
                recipients,
            )
            return Status.FAILURE
        self.logger.info(
            "%s: fanned out log entry '%s' to %d recipients"
            " (%d joined but inactive, stream paused — CM-10-005)",
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
