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
"""The case a peer's replay or position statement is about.

A replay node reads the case from the received activity
(:func:`replay_case_id`), or from the tree when the tree names it
(:class:`CaseNamedReplayNode`): the answer to a stamped ``ledgerPosition``
is built for the tree's case, since a case activity names it in different
slots (SYNC-18-007).  Split out of ``replay`` (BTND-07-004).
"""

from typing import Any

from vultron.core.behaviors.act_key_ports import optional_act_value
from vultron.core.behaviors.act_keys import CASE_ID
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.errors import VultronError

__all__ = [
    "CaseNamedReplayNode",
    "replay_case_id",
    "require_rejected_entry",
    "scoped_keys",
]


def replay_case_id(activity: Any, node_name: str) -> str:
    """Return the case whose ledger a peer's activity asks to have replayed.

    The activity's ``replay_case_id``: for a ``Reject(CaseLedgerEntry)`` the
    rejected entry's case; for a ``Read(<case>/ledger)`` the case its
    ``context`` names (SYNC-17-001).
    Raises ``VultronError`` when the activity names none (BT-HELPER-01).
    """
    case_id = getattr(activity, "replay_case_id", None)
    if isinstance(case_id, str) and case_id:
        return case_id
    return require_rejected_entry(activity, node_name).context


def require_rejected_entry(activity: Any, node_name: str) -> CaseLedgerEntry:
    """Return the ``CaseLedgerEntry`` a ``Reject(CaseLedgerEntry)`` carries.

    Shared by the replay nodes here and ``AnnounceCaseOnGenesisRejectNode``
    (``genesis_announce.py``). Raises ``VultronError`` when the activity
    carries no entry (BT-HELPER-01: helpers raise, ``update()`` catches).
    """
    entry = getattr(activity, "rejected_entry", None)
    if entry is None:
        entry = getattr(activity, "object_", None)
    if isinstance(entry, CaseLedgerEntry):
        return entry
    raise VultronError(
        f"{node_name}: activity did not carry a rejected CaseLedgerEntry"
    )


def scoped_keys(scope: str | None, *keys: str) -> dict[str, str]:
    """Port remappings putting *keys* under ``/<scope>/`` on the blackboard.

    Nothing for ``scope=None``: the keys stay at the root.  A replay run
    ahead of the act's own guards (the answer to a stamped ledger position,
    SYNC-18-007) scopes ``case_id`` and ``case_actor_id``, which the act's
    later nodes read from the root.
    """
    if scope is None:
        return {}
    return {key: f"/{scope}/{key}" for key in keys}


#: The input port a :class:`CaseNamedReplayNode` reads the tree's case on.
#: Not named ``case_id``: :class:`~.replay.divergence.FindCaseActorNode`
#: publishes the case it resolves on an output port of that name.
_NAMED_CASE_PORT = "named_case_id"

#: The port :class:`CaseNamedReplayNode` adds to every subclass's
#: ``INPUT_PORTS``, and its binding to ``/case_id`` (BTND-01-008).
_NAMED_CASE_PORTS: dict[str, PortInformation] = {
    _NAMED_CASE_PORT: PortInformation(data_type=object, required=False),
}
_NAMED_CASE_REMAPPINGS: dict[str, str] = {_NAMED_CASE_PORT: CASE_ID.path}


class CaseNamedReplayNode(DataLayerActionWithPorts):
    """A replay node whose case the tree may name: ``/case_id`` when the run
    holds one (a seed or an earlier node's write), else the activity's
    ``replay_case_id`` (SYNC-17-004, SYNC-18-007).

    The base adds the case port to every subclass's ``INPUT_PORTS`` and binds
    it to ``/case_id``, so no subclass can leave it out.  A subclass binds
    its own ports in :meth:`_replay_port_remappings`; defining
    ``_domain_port_remappings`` itself would drop the case binding, so it
    raises ``TypeError`` at class creation.  A tree that names the case
    seeds ``/case_id`` with
    :func:`~vultron.core.behaviors.act_key_scope.with_act_keys`.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        **_NAMED_CASE_PORTS,
    }

    def __init_subclass__(cls, **kwargs: Any) -> None:
        # Runs before PortsMixin.__init_subclass__, so the added port is
        # validated with the rest (as CaseIdInputPortMixin does).
        if "_domain_port_remappings" in vars(cls):
            raise TypeError(
                f"{cls.__name__}: bind ports in _replay_port_remappings; a"
                " CaseNamedReplayNode's _domain_port_remappings adds the"
                " /case_id binding"
            )
        cls.INPUT_PORTS = {**cls.INPUT_PORTS, **_NAMED_CASE_PORTS}
        super().__init_subclass__(**kwargs)

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {**_NAMED_CASE_REMAPPINGS, **cls._replay_port_remappings()}

    @classmethod
    def _replay_port_remappings(cls) -> dict[str, str]:
        """The subclass's own port bindings, beside the case's."""
        return {}

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)

    def initialise(self) -> None:
        super().initialise()
        self.case_id: str | None = optional_act_value(
            self, CASE_ID, str, port=_NAMED_CASE_PORT
        )

    def replay_case(self, activity: Any) -> str:
        return self.case_id or replay_case_id(activity, self.name)
