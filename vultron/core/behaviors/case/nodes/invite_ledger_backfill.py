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


"""Join-time ledger-backfill and case-announce leaf nodes for the accept-invite tree.

Queue ``Announce(VulnerabilityCase)`` to the invitee, and backfill the
canonical ``CaseLedgerEntry`` history in strict order (MV-10-003/MV-10-005).
Composed by ``create_accept_invite_actor_to_case_tree`` (BTND-07-003).
"""

import logging
from typing import cast

from py_trees.common import Status
from py_trees.ports import NoDataAvailable

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
    _EmitSingleActivityBase,
)
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.errors import VultronWiringError

logger = logging.getLogger(__name__)


class BackfillCanonicalLedgerToInviteeNode(DataLayerActionWithPorts):
    """Send the canonical CaseLedgerEntry history to a joiner in log order.

    The tree reaches this node only for an inert invitee's first Accept
    (CM-17-012), and the commit fan-out of that Accept's own entry skipped the
    invitee because it was inert.  So the backfill sends every entry on the
    ledger when it runs, the Accept's own entry included (CM-17-004 step 3).
    It keeps no replication state: the backfill commits with its Accept in
    one act or not at all (CLP-07-015).

    A missing ``sync_port`` is a wiring fault and raises
    ``VultronWiringError``, as the fan-out does (SYNC-02-003, #4126).
    """

    def __init__(
        self, case_id: str, invitee_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.invitee_id = invitee_id
        self._sync_port: SyncActivityPort | None = None

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "sync_port": PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"sync_port": "/sync_port"}

    def initialise(self) -> None:
        super().initialise()
        try:
            self._sync_port = cast(
                SyncActivityPort, self.get_input("sync_port")
            )
        except (NoDataAvailable, NotImplementedError):
            self._sync_port = None

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None
        if self._sync_port is None:
            raise VultronWiringError(
                f"{self.name}: sync_port must be injected to backfill the"
                f" ledger of case '{self.case_id}' to '{self.invitee_id}'"
                " (SYNC-02-003, #4126)"
            )

        entries: list[CaseLedgerEntry] = sorted(
            (
                obj
                for obj in self.datalayer.list_objects("CaseLedgerEntry")
                if isinstance(obj, CaseLedgerEntry)
                and obj.case_id == self.case_id
            ),
            key=lambda log_entry: log_entry.log_index,
        )
        for entry in entries:
            self._sync_port.send_announce_log_entry(
                entry=entry,
                actor_id=self.actor_id,
                to=[self.invitee_id],
            )
        self.logger.info(
            "%s: join-time backfill sent %d ledger entries to '%s' in case"
            " '%s'",
            self.name,
            len(entries),
            self.invitee_id,
            self.case_id,
        )
        return Status.SUCCESS


class EmitAnnounceCaseToInviteeNode(_EmitSingleActivityBase):
    """Queue Announce(VulnerabilityCase) to the invitee from the CaseActor.

    Per MV-10-003/MV-10-005, the CaseActor sends the full case object after
    embargo consent has been resolved (auto-signed above when an embargo is
    in force).
    Failures to enqueue Announce are logged but treated as non-fatal so the
    join-time canonical ledger backfill can still run.
    """

    def __init__(
        self, case_id: str, invitee_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.invitee_id = invitee_id

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        factory = self.trigger_activity_factory
        if factory is None:
            self.logger.warning(
                "%s: trigger_activity_factory not available;"
                " cannot emit AnnounceVulnerabilityCase for case '%s'"
                " (MV-10-003)",
                self.name,
                self.case_id,
            )
            return Status.SUCCESS

        try:
            activity_id = factory.announce_vulnerability_case(
                case_id=self.case_id,
                actor=self.actor_id,
                context_id=self.case_id,
                to=[self.invitee_id],
            )
            # Route through the shared emit seam (OX-14-001, ASK-04-008).
            # factory.announce_vulnerability_case returns str only;
            # pass an empty blob since no captured dict is present.
            self._emit_through_seam(activity_id, "")
            self.logger.info(
                "%s: queued AnnounceVulnerabilityCase '%s' to '%s'"
                " for case '%s' (MV-10-003)",
                self.name,
                activity_id,
                self.invitee_id,
                self.case_id,
            )
            return Status.SUCCESS
        except Exception as exc:  # noqa: BLE001  # ruff-baseline #3768
            self.logger.error(  # noqa: TRY400  # ruff-baseline #3353
                "%s: failed to emit AnnounceVulnerabilityCase for case '%s'"
                " to '%s': %s",
                self.name,
                self.case_id,
                self.invitee_id,
                exc,
            )
            return Status.SUCCESS
