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

"""The CASE_MANAGER's one-open-Offer guard for ownership transfer (CM-21-014).

Provides:

- :class:`NoOpenOwnershipOfferNode` — precondition guard that refuses a new
  ownership-transfer Offer while an earlier one for the case is open.
- :func:`case_manager_admits_ownership_offer_guard` — the guard behind the
  CASE_MANAGER gate, for the received Offer tree's ``precondition_guards``.
"""

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.case.nodes.role_gates import (
    create_case_manager_gated_tree,
)
from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.participants.ownership_offer import open_ownership_offer


class NoOpenOwnershipOfferNode(DataLayerConditionWithPorts):
    """Guard: the case has no earlier ownership-transfer Offer still open.

    The CASE_MANAGER refuses a new ownership-transfer Offer while an earlier
    one for the case is open, because two pending Offers would let two
    transferees accept the same case (CM-21-014, CM-21-001).  "Open" is read
    from the case ledger through
    :func:`~vultron.core.participants.ownership_offer.open_ownership_offer`
    (CLP-11-001): an Offer stays open until the ledger holds an answer
    recorded after it.  Once it is closed, a new Offer is admitted to any
    transferee, including the one that declined.

    Read-only, so it runs in ``precondition_guards`` behind the CASE_MANAGER
    gate (:func:`case_manager_admits_ownership_offer_guard`): the transferee
    holds the replicated entries too, and the forward it receives must not be
    judged against the Offer it stands for.
    """

    def __init__(
        self, case_id: str, offer_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.offer_id = offer_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        earlier = open_ownership_offer(
            self.datalayer, self.case_id, other_than=self.offer_id
        )
        if earlier is None:
            return Status.SUCCESS
        self.feedback_message = (
            f"case '{self.case_id}' already has an open ownership-transfer"
            f" Offer '{earlier.offer_id}' to '{earlier.transferee_id}';"
            " it must be answered before the case is offered again"
            " — REFUSED (CM-21-014)"
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE


def case_manager_admits_ownership_offer_guard(
    case_id: str, offer_id: str
) -> py_trees.behaviour.Behaviour:
    """Precondition guard: at the CASE_MANAGER, no earlier Offer is open.

    A replica (the transferee receiving the forward) skips it as
    ``SUCCESS``; the CASE_MANAGER runs :class:`NoOpenOwnershipOfferNode`, so
    a refused Offer is neither committed nor forwarded (CM-21-014).
    """
    return create_case_manager_gated_tree(
        name="NoOpenOwnershipOfferIfCaseManager",
        case_id=case_id,
        body_name="NoOpenOwnershipOffer",
        children=[
            NoOpenOwnershipOfferNode(case_id=case_id, offer_id=offer_id)
        ],
    )
