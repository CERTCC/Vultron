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

"""The refusals a composed guard ends a side with: an empty side, and the
last arm of an any-of side (HP-01-023, HP-01-024).
"""

from py_trees.common import Status

from vultron.core.behaviors.sender_entitlement.base import (
    SenderEntitlementConditionNode,
)
from vultron.core.behaviors.sender_entitlement.declarations import (
    SenderEntitlementKind,
    in_declaration_order,
)

# ---------------------------------------------------------------------------
# Condition node: a side the declared rule leaves empty
# ---------------------------------------------------------------------------


class NoSenderAdmittedNode(SenderEntitlementConditionNode):
    """Guard for a side a :class:`SenderRule` leaves empty: it admits no one.

    The factory composes it when the receiver is on a side the use case's
    rule names no kind for, such as a participant receiving an activity only
    the CASE_MANAGER may be sent (HP-01-008).  It always fails, naming the
    side, so the tree ends ``REFUSED`` with nothing written.

    Spec: HP-01-006, HP-01-024.
    """

    def __init__(self, side: str, name: str | None = None) -> None:
        """Create the guard.

        Args:
            side: Plain-language name of the empty side, e.g.
                ``"a participant other than the CASE_MANAGER"``.
            name: Optional node name.
        """
        super().__init__(name=name or self.__class__.__name__)
        self._side = side

    def update(self) -> Status:
        return self._refuse_by_placement(
            f"No sender is entitled to send this activity to {self._side}"
            " — REFUSED (HP-01-006, HP-01-024)"
        )


class SenderHoldsNoneOfNode(SenderEntitlementConditionNode):
    """The last arm of an any-of side: the sender held none of its kinds.

    The factory appends it to the selector of an any-of side (HP-01-023), so
    a refused sender's reason names every standing the side accepts rather
    than only the last kind tried (HP-01-006, BT-13-001).  It always fails.

    Spec: HP-01-006, HP-01-023.
    """

    def __init__(
        self,
        kinds: frozenset[SenderEntitlementKind],
        name: str | None = None,
    ) -> None:
        """Create the guard.

        Args:
            kinds: The kinds the side accepts, any one sufficing.
            name: Optional node name.
        """
        super().__init__(name=name or self.__class__.__name__)
        self._kinds = in_declaration_order(kinds)

    def update(self) -> Status:
        names = ", ".join(kind.name for kind in self._kinds)
        return self._refuse_by_placement(
            f"Sender holds none of the standings this activity accepts"
            f" ({names}) — REFUSED (HP-01-006, HP-01-023)"
        )
