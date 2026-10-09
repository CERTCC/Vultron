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

"""Effect node: store the object a received ``Create(X)`` introduced.

A ``Create(X)`` message introduces an object the receiver did not hold.
Intake archives the *activity* (CLP-10-017); this node writes the core record
from the copy the event carries.  It runs as an effect, after intake, in the
shared store-only tree (:func:`~vultron.core.behaviors.case.store_only_received_tree.create_store_only_received_tree`).

The node reports what it did through :attr:`outcome` so the handler reports
``APPLIED`` / ``SKIPPED`` (HP-01-003) without inspecting the DataLayer
(ADR-0111).  The store itself is
:func:`~vultron.core.services.idempotent_store.idempotent_store`, the one
implementation of idempotent store (CS-22-001).
"""

from typing import Any

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerActionWithPorts
from vultron.core.models.use_case_result import HandlerResult
from vultron.core.services.idempotent_store import idempotent_store


class StoreReceivedObjectNode(DataLayerActionWithPorts):
    """Idempotently store a received domain object.

    ``SUCCESS`` whenever the store ran, whatever it decided: a missing or
    already-held object is a benign no-op, not a failure.  ``FAILURE`` only
    when the DataLayer is unavailable (ARCH-15-001).  An unexpected storage
    error propagates to the bridge, which classifies it as an internal error.
    """

    def __init__(
        self,
        type_key: str | None,
        id_key: str | None,
        obj: Any,
        label: str,
        activity_id: str | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.type_key = type_key
        self.id_key = id_key
        self.obj = obj
        self.label = label
        self.activity_id = activity_id
        self.outcome: HandlerResult | None = None

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        self.outcome = idempotent_store(
            self.datalayer,
            self.type_key,
            self.id_key,
            self.obj,
            self.label,
            self.activity_id,
        )
        return Status.SUCCESS
