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
"""The lookup of the ledger entry a replica's fault reports refusing.

A replica that refuses a copied entry sends the CASE_MANAGER
``Create(ProcessingFault)`` whose ``inReplyTo`` names the refused
``Add(CaseLedgerEntry)`` by reference; the fault carries no case
(ASK-07-004, ASK-07-006).  Only this store knows which entry that ``Add``
carried, and so which case the fault is about, so the entry is a per-act
value a lookup node finds (BT-25-009).

:class:`FindRefusedLedgerEntry` is that node.  A received fault tree runs it
ahead of its path stage, which reads the receiver's role in the case it
published, and every later node reads the same keys (BT-25-011).  It never
refuses: a miss publishes nothing, the path stage reads the no-case path,
and :class:`RefusedLedgerEntryFound` refuses the miss there (BT-25-010).
"""

from py_trees.common import Status
from py_trees.ports import PortInformation

from vultron.core.behaviors.act_key_ports import (
    act_key_ports,
    act_key_remappings,
    optional_act_value,
)
from vultron.core.behaviors.act_keys import (
    ANNOUNCE_ID,
    CASE_ID,
    REFUSED_ENTRY,
)
from vultron.core.behaviors.case.nodes.case_lookup import CaseResolving
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
)
from vultron.core.behaviors.idempotency import DeclaredRefusalMixin
from vultron.core.behaviors.received_request import (
    ReceivedRequestInputMixin,
)
from vultron.core.behaviors.sync.nodes.reseed import announced_ledger_entry
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.errors import VultronNotFoundError

__all__ = [
    "FindRefusedLedgerEntry",
    "RefusedLedgerEntryFound",
    "unnamed_entry_reason",
]

#: The keys :class:`FindRefusedLedgerEntry` publishes on a hit.
_PUBLISHED = (CASE_ID, REFUSED_ENTRY, ANNOUNCE_ID)


def unnamed_entry_reason(*, answer: str, requirement: str) -> str:
    """Why a fault naming no ``Add(CaseLedgerEntry)`` this actor sent is
    refused: there is no case to *answer* for.

    *requirement* is the requirement of the response that cannot run.
    """
    return (
        "the fault names no Add(CaseLedgerEntry) this actor sent, so it"
        f" names no case to {answer} ({requirement}, ASK-07-004)"
    )


class FindRefusedLedgerEntry(
    CaseResolving, ReceivedRequestInputMixin, DataLayerActionWithPorts
):
    """Publish the entry a received fault reports refusing, and its case.

    Reads the fault from the ``/activity`` run key: its ``inReplyTo``
    (``failed_activity_id``) names the refused ``Add(CaseLedgerEntry)``.
    Only an ``Add`` the executing actor sent counts
    (:func:`~vultron.core.behaviors.sync.nodes.reseed.announced_ledger_entry`):
    one this store merely received names nothing it sent the peer.  On a
    hit it publishes the entry on ``/refused_entry``, its case on
    ``/case_id`` and the ``Add``'s id on ``/announce_id`` (BT-25-009).

    It never refuses.  A fault with no ``inReplyTo``, or one naming no
    ``Add`` of a ``CaseLedgerEntry`` the executing actor sent, publishes
    nothing and succeeds, so the path stage puts the receiver on the
    no-case path and :class:`RefusedLedgerEntryFound` refuses it there
    (BT-25-010).  It reads the store and writes only blackboard keys, so it
    is :class:`CaseResolving`.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
    }
    OUTPUT_PORTS: dict[str, PortInformation] = {
        key.name: PortInformation(data_type=key.value_type, required=True)
        for key in _PUBLISHED
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            **super()._domain_port_remappings(),
            **act_key_remappings(*_PUBLISHED),
        }

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None
        announce_id = self._failed_activity_id()
        if announce_id is None:
            self.logger.debug(
                "%s: the fault names no inReplyTo; the tree's declaration"
                " decides the delivery",
                self.name,
            )
            return Status.SUCCESS
        try:
            entry = announced_ledger_entry(
                self.datalayer, announce_id, self.actor_id
            )
        except VultronNotFoundError:
            # A miss is an answer, not a refusal: the miss guard decides it.
            self.logger.debug(
                "%s: '%s' is no Add(CaseLedgerEntry) actor '%s' sent; the"
                " tree's declaration decides the delivery",
                self.name,
                announce_id,
                self.actor_id,
            )
            return Status.SUCCESS
        self._set_output(CASE_ID.name, entry.case_id)
        self._set_output(REFUSED_ENTRY.name, entry)
        self._set_output(ANNOUNCE_ID.name, announce_id)
        self.logger.debug(
            "%s: found ledger entry '%s' of case '%s' in Add '%s'",
            self.name,
            entry.id_,
            entry.case_id,
            announce_id,
        )
        return Status.SUCCESS

    def _failed_activity_id(self) -> str | None:
        """The fault's ``inReplyTo``, or ``None`` when it names none."""
        value = getattr(self._received, "failed_activity_id", None)
        return value if isinstance(value, str) and value else None


class RefusedLedgerEntryFound(
    DeclaredRefusalMixin, CaseResolving, DataLayerConditionWithPorts
):
    """Refuse a fault whose entry :class:`FindRefusedLedgerEntry` did not find.

    The miss half of the lookup (BT-25-010): it reads ``/refused_entry`` and
    fails when nothing was published there, declaring the refusal
    :func:`unnamed_entry_reason` words.  It reads no store and publishes
    nothing, so the lookup stays the one source of its keys (BT-25-011).

    Args:
        answer: What the response would do for the case, as the reason
            names it (``"re-seed"``).
        requirement: The requirement of the response that cannot run
            (``"SYNC-16-003"``).
        name: Node name; defaults to the class name.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerConditionWithPorts.INPUT_PORTS,
        **act_key_ports(REFUSED_ENTRY),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return act_key_remappings(REFUSED_ENTRY)

    def __init__(
        self, *, answer: str, requirement: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._reason = unnamed_entry_reason(
            answer=answer, requirement=requirement
        )
        self._found: CaseLedgerEntry | None = None

    def initialise(self) -> None:
        super().initialise()
        self._found = optional_act_value(self, REFUSED_ENTRY, CaseLedgerEntry)

    def update(self) -> Status:
        if self._found is not None:
            return Status.SUCCESS
        self.feedback_message = self._reason
        # INFO, not WARNING: a fault may name an activity that is no
        # announce of this store's, which is the sender's mistake, not ours.
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return self._refuse(self._reason)
