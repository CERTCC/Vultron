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

"""The CASE_MANAGER's ``case_fully_closed`` entry (CM-23-002 step 3).

Case closure is a consequence of the Case Owner's received ``Leave``: the
``Leave`` is recorded as received (``close_case``), and the closure follows
as the CASE_MANAGER's own entry carrying the closed case (CLP-07-013,
ADR-0124).
"""

from typing import cast

from vultron.core.behaviors.case_manager_commit import (
    _CommitCaseManagerActivityBase,
)
from vultron.core.predicates.case_closure import CASE_FULLY_CLOSED_EVENT_TYPE


class CommitCaseFullyClosedNode(_CommitCaseManagerActivityBase):
    """Commit the CASE_MANAGER's ``Update(VulnerabilityCase)`` closing the case.

    Runs last on the owner-close arm, after the ``close_case`` entry that
    records the received ``Leave``, the RM closure entries it caused and the
    expired-invitation entries (CM-23-002, CM-23-014).  The activity is built
    by the factory as the executing CASE_MANAGER and carries the closed case
    in full; its sealed blob is the entry's ``payloadSnapshot`` (VM-08-003).
    It is attributed to the CASE_MANAGER alone, so no entry poses as an act
    the Case Owner did not send, and its ``published`` is the CASE_MANAGER's
    own clock.

    Addressed to nobody: the ledger fan-out is its delivery, to every
    participant not yet at ``RM.CLOSED`` (CM-23-004).  A replica applies it
    by storing it; the RM transitions it follows arrived as their own
    entries, and it changes nothing a replica at the same ledger position
    does not already hold (CM-23-016).

    A missing trigger-activity factory raises (see the base class) rather
    than failing the owner arm, which the enclosing ``OwnerOrNonOwnerEffects``
    Selector would read as "the sender is not the Case Owner" and succeed
    down the non-owner path: a half-closed case reported as SUCCESS.

    Per CM-23-002, CM-23-013, CLP-07-013, VM-08-003, ADR-0085, ADR-0124.
    """

    #: A gapped local prefix must not block case closure (CM-23-002,
    #: SYNC-10-001/002): the RM closure entries before this one skip the
    #: check for the same reason (``CommitRMClosureEntriesNode``).
    _CHECK_LEDGER_FRESHNESS = False

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(
            case_id=case_id,
            event_type=CASE_FULLY_CLOSED_EVENT_TYPE,
            notify_participants=False,
            name=name,
        )

    def _build(self, to: list[str] | None) -> tuple[str, str]:
        assert self.trigger_activity_factory is not None
        return self.trigger_activity_factory.record_case_fully_closed(
            case_id=self._case_id, actor=cast(str, self.actor_id)
        )


__all__ = ["CommitCaseFullyClosedNode"]
