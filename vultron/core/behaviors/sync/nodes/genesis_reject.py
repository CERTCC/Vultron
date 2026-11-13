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
"""Limit a missing-case participant to one genesis Reject per interval.

Split from :mod:`vultron.core.behaviors.sync.nodes.receive` to keep that
leaf module within the BTND-07-004 line limit.
"""

from __future__ import annotations

from vultron.core.behaviors.sync.nodes.receive import SendRejectLogEntryNode
from vultron.core.behaviors.sync.nodes.replay_guard import (
    MAX_REPLAY_COOLDOWN_SECONDS,
    cooldown_elapsed,
)
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.services.genesis_reject_limit import (
    last_genesis_reject_at,
    record_genesis_reject,
)
from vultron.errors import VultronWiringError


class SendGenesisRejectOnMissingCaseNode(SendRejectLogEntryNode):
    """Ask for a missing case once per interval, not once per early entry.

    Runs when the participant does not hold the entry's case (CLP-08-005),
    after :class:`BufferPreGenesisEntryNode` has held the ``Announce``.  It
    sends the genesis Reject, a ``Reject(CaseLedgerEntry)`` with
    ``last_accepted_hash=""`` asking for the case and its whole ledger
    (SYNC-15-001), unless it sent one for the same case less than
    :data:`~vultron.core.behaviors.sync.nodes.replay_guard.MAX_REPLAY_COOLDOWN_SECONDS`
    ago: one such Reject asks for everything the next would (SYNC-15-016,
    SYNC-15-020).  The first early entry after the interval sends one again,
    as a new activity, keyed on the time it asked (SYNC-15-017).

    The time of the last one is a
    :class:`~vultron.core.models.genesis_reject_record.GenesisRejectRecord`
    in the participant's store (SYNC-15-021), written in one transaction
    with the queued Reject, so neither lands without the other (ADR-0146).
    Seeding the case deletes it (SYNC-15-023).

    Returns ``FAILURE`` whether it sends or withholds, like
    :class:`SendRejectLogEntryNode`: the entry is not stored this pass.
    ``withheld`` says which, and the refusal it declares names it.
    """

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name)
        self.withheld = False

    def initialise(self) -> None:
        super().initialise()
        self.withheld = False

    def _refusal_of(self, entry: CaseLedgerEntry) -> str:
        """The missing case, and whether its genesis Reject was sent."""
        if self.withheld:
            return (
                f"case '{entry.case_id}' is not seeded here; a Reject for"
                " replay from genesis was already sent within the interval,"
                " so none is sent again (SYNC-15-016)"
            )
        return (
            f"case '{entry.case_id}' is not seeded here; Reject sent for"
            " replay from genesis (SYNC-15-001)"
        )

    def _reject(
        self,
        entry: CaseLedgerEntry,
        sync_port: SyncActivityPort,
        actor_id: str,
        sender_id: str,
        announce_id: str,
    ) -> None:
        if self.datalayer is None:
            raise VultronWiringError(
                f"{self.name}: a DataLayer must be injected to limit genesis"
                " Rejects (SYNC-15-021)"
            )
        # The check and the stamp both use the act's instant (ADR-0176).
        at = self._require_act_instant()
        # The read, the check and the write are one unit, so two deliveries
        # cannot both find no recent Reject and both send one.
        with self.datalayer.transaction():
            last_sent_at = last_genesis_reject_at(
                self.datalayer, entry.case_id
            )
            if not cooldown_elapsed(
                last_sent_at, MAX_REPLAY_COOLDOWN_SECONDS, at=at
            ):
                self.logger.info(
                    "%s: holding entry '%s' (index=%d) for missing case '%s'"
                    " without a genesis Reject: actor '%s' sent one at %s,"
                    " less than %.0f s ago (SYNC-15-016)",
                    self.name,
                    entry.id_,
                    entry.log_index,
                    entry.case_id,
                    actor_id,
                    last_sent_at,
                    MAX_REPLAY_COOLDOWN_SECONDS,
                )
                self.withheld = True
                return
            asked_at = at
            self.logger.warning(
                "%s: case '%s' of log entry '%s' is not held; sending a"
                " genesis Reject(CaseLedgerEntry) to '%s' (SYNC-15-001)",
                self.name,
                entry.case_id,
                entry.id_,
                sender_id,
            )
            sync_port.send_reject_log_entry(
                entry=entry,
                tail_hash=self.tail_hash,
                actor_id=actor_id,
                to=[sender_id],
                in_reply_to=announce_id,
                asked_at=asked_at,
                at=self._require_act_instant(),
            )
            record_genesis_reject(self.datalayer, entry.case_id, asked_at)
