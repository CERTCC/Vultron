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

"""The termination a voluntary termination's reason call-out chooses.

``create_terminate_active_embargo_tree`` asks three reason call-outs why the
actor ends the embargo; the one that returns SUCCESS records its cause in the
tree's :class:`ChosenTermination` (``ChooseTerminationCauseNode``, EMB-14-001).
The termination's commit and ask nodes read that slot from the ``/termination``
key when they run, so the slot is one of the values that key admits
(:data:`~vultron.core.behaviors.act_keys.TERMINATION`).

It lives in its own module, apart from the nodes that fill and read it, so the
key vocabulary can name it without importing any node.
"""

from vultron.core.models.embargo_termination import (
    EmbargoTermination,
    TerminationCause,
)
from vultron.core.states.embargo_register import TerminationReason
from vultron.errors import VultronWiringError

__all__ = ["ChosenTermination"]


class ChosenTermination:
    """The termination a reason call-out chooses, read at the write.

    Every chosen cause is ``EARLY``.  It is set by
    ``ChooseTerminationCauseNode`` and read by the termination's commit
    and ask nodes in the same run.
    """

    def __init__(self) -> None:
        self._termination: EmbargoTermination | None = None

    @property
    def reason(self) -> TerminationReason:
        """The what: a voluntary termination ends the embargo early."""
        return TerminationReason.EARLY

    def choose(self, cause: TerminationCause) -> None:
        """Record *cause* as the termination's why."""
        self._termination = EmbargoTermination(
            reason=TerminationReason.EARLY, cause=cause
        )

    @property
    def termination(self) -> EmbargoTermination:
        """The chosen termination.

        Raises:
            VultronWiringError: no reason call-out chose a cause before the
                termination ran, so the tree is composed wrongly.
        """
        if self._termination is None:
            raise VultronWiringError(
                "the termination ran before a reason call-out chose its"
                " cause (EMB-14-001)"
            )
        return self._termination
