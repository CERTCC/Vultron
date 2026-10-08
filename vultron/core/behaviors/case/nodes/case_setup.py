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

"""
Case setup action nodes for case management behavior trees.

Provides leaf action nodes that set up core case state.

``EnsureCaseActorHostedNode`` provisions the CaseActor record in the
co-located store so its inbox answers (CP-04-004).

Per specs/case-management.yaml CM-02 requirements.
"""

from py_trees.common import Status

from vultron.core.behaviors.case.case_actor_identity import (
    case_actor_identity,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
)
from vultron.core.behaviors.store_scope import store_for_actor
from vultron.core.models.case_actor import CaseActor
from vultron.errors import VultronAlreadyExistsError


class EnsureCaseActorHostedNode(DataLayerActionWithPorts):
    """Make this container's CaseActor a *hosted* actor so its inbox answers.

    ``POST /actors/{slug}/inbox/`` resolves the actor from the store that slug
    names (``_resolve_actor_or_404``, ADR-0073), so the record has to be in the
    CaseActor's **own** store before ``Create(as_CaseProposal)`` is delivered.
    Writing it only into the sending actor's store is why delivery answered
    ``404 Actor not found`` and the proposal round-trip never began (#1872,
    CP-04-002, CP-04-004).

    A copy also goes into the sending actor's own store, as an address-book entry
    for a peer it now knows (ADR-0073#peer-records-in-knowers-store) — sibling nodes resolve the
    CaseActor from the *executing* actor's store.  The two writes are not
    redundant: one publishes an endpoint, the other records knowledge.  Under a
    shared store they were indistinguishable, which is why one used to do.

    Co-located only.  When the CaseActor runs in a different container this node
    cannot reach its store, and provisioning there is that container's own
    business (its seed config) — which is exactly what a *stable* identity makes
    possible and a per-case one did not.  ``store_for_actor`` is asked for the
    same authority for that reason: ``clone_for_actor`` succeeds for *any*
    well-formed id, so without the guard a remote CaseActor's id opens a fresh
    empty local store that looks like a success and publishes nothing.

    Extracted from ``WritePendingReportCaseLinkNode.update()``, which had grown
    to two jobs — provisioning and link-writing — in breach of the ~20–30 line
    leaf-node budget (BTND-02-001, "No God Nodes").  Always returns ``SUCCESS``
    when the identity is configured, so the enclosing ``Sequence`` continues:
    a CaseActor hosted elsewhere is a normal topology, not a failure.
    """

    def __init__(self, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case_actor_id = case_actor_identity()
        if case_actor_id is None:
            self.feedback_message = (
                f"{self.name}: case_actor_service_url is not configured"
                " (set VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL)"
            )
            self.logger.error("%s", self.feedback_message)
            return Status.FAILURE

        case_actor = CaseActor(id_=case_actor_id, name="CaseActor")
        own_store = store_for_actor(
            self.datalayer, case_actor_id, require_same_authority=True
        )
        stores = (
            ("its own", own_store),
            ("the sending actor's", self.datalayer),
        )
        for label, store in stores:
            if store is None:
                self.logger.debug(
                    "%s: CaseActor '%s' is hosted elsewhere; it provisions its"
                    " own %s store from its seed config",
                    self.name,
                    case_actor_id,
                    label,
                )
                continue
            if store.read(case_actor_id) is not None:
                continue
            try:
                store.create(case_actor)
            except VultronAlreadyExistsError:
                pass  # already exists (race or duplicate); not an error
        return Status.SUCCESS
