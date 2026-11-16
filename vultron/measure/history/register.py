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
"""The embargo register a ledger's steps rebuild, read one entry at a time.

The case's EM state is derived from its register (ADR-0122), and the ledger
records the register's steps: a proposal, an activation that supersedes the
embargo in force, the Case Owner's rejection, the CASE_MANAGER's withdrawal of
an abandoned proposal, and a termination that cancels every open proposal
(EP-08-004).  Each step moves an entry only as the register's own table allows
(:func:`~vultron.core.states.embargo_register.register_status_after`); a step
the table refuses from where the entry stands leaves it there, so a repeated or
stale step never moves an entry back.

A carried case's register states its entries' statuses outright.  A carried
status is taken only when the entry has none yet or the table can reach it from
the one held, for the same reason: a state behind the one reached is not
reached (CEH-04-015).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from vultron.core.states.embargo_register import (
    EmbargoRegisterStatus,
    RegisterTrigger,
    register_status_after,
    register_trigger_is_legal,
)

logger = logging.getLogger(__name__)

_S = EmbargoRegisterStatus
_T = RegisterTrigger


def _reachable(status: EmbargoRegisterStatus) -> set[EmbargoRegisterStatus]:
    """Every status the register's table reaches from *status*, itself
    excluded."""
    found: set[EmbargoRegisterStatus] = set()
    frontier = [status]
    while frontier:
        current = frontier.pop()
        for trigger in RegisterTrigger:
            if register_trigger_is_legal(current, trigger):
                after = register_status_after(current, trigger)
                if after not in found:
                    found.add(after)
                    frontier.append(after)
    return found


@dataclass
class RebuiltRegister:
    """Each embargo register entry's status, as the ledger's steps leave it."""

    statuses: dict[str, EmbargoRegisterStatus] = field(default_factory=dict)

    def _step(self, embargo_id: str, trigger: RegisterTrigger) -> bool:
        """Apply *trigger* to *embargo_id* when the table allows it.

        Returns whether the entry moved.
        """
        current = self.statuses.get(embargo_id)
        if not register_trigger_is_legal(current, trigger):
            logger.debug(
                "Register step %s on %s at %s is not in the table; kept",
                trigger,
                embargo_id,
                current,
            )
            return False
        self.statuses[embargo_id] = register_status_after(current, trigger)
        return True

    def _ids_at(self, status: EmbargoRegisterStatus) -> list[str]:
        return [i for i, held in self.statuses.items() if held is status]

    def propose(self, embargo_id: str) -> None:
        """A proposal opens a new entry; a repeat of it changes nothing."""
        self._step(embargo_id, _T.PROPOSE)

    def activate(self, embargo_id: str) -> None:
        """An activation puts *embargo_id* in force, superseding the other.

        An entry the ledger never recorded proposing, as a case's creation
        seats its default embargo, goes straight into force.  A rejected,
        cancelled or ended entry is never reopened.
        """
        if embargo_id in self.statuses:
            if not self._step(embargo_id, _T.ACTIVATE):
                return
        else:
            self.statuses[embargo_id] = _S.ACTIVE
        for other in self._ids_at(_S.ACTIVE):
            if other != embargo_id:
                self._step(other, _T.SUPERSEDE)

    def reject(self, embargo_id: str) -> None:
        """The Case Owner's rejection closes an open proposal."""
        self._step(embargo_id, _T.REJECT)

    def cancel(self, embargo_id: str) -> None:
        """An abandoned proposal is cancelled (EMB-16-001)."""
        self._step(embargo_id, _T.CANCEL)

    def terminate(self, embargo_id: str) -> None:
        """A termination ends *embargo_id* and cancels every open proposal
        in the same step (EP-08-004).

        An entry the ledger never recorded, as in a merge missing its
        activation, is recorded as ended.
        """
        if embargo_id in self.statuses:
            self._step(embargo_id, _T.TERMINATE)
        else:
            self.statuses[embargo_id] = _S.TERMINATED
        for proposed in self._ids_at(_S.PROPOSED):
            self._step(proposed, _T.CANCEL)

    def carry(self, embargo_id: str, status: EmbargoRegisterStatus) -> None:
        """A carried register's status for *embargo_id*, unless it is behind
        the status held."""
        current = self.statuses.get(embargo_id)
        if current is None or status in _reachable(current):
            self.statuses[embargo_id] = status
