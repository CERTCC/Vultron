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

Provides leaf action nodes that set up core case state: persisting the case
record, assigning attribution, and recording creation events.

CaseActor identity is published by ``PublishCaseActorIdentityNode`` and provisioned
by ``EnsureCaseActorHostedNode``, both below.

Composite subtrees (``Sequence``/``Selector`` subclasses) that orchestrate
these leaf nodes are defined in ``case_setup_tree.py`` at the process-area
root, per BTND-07-003.

Per specs/case-management.yaml CM-02 requirements.
"""

from py_trees.common import Status

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.models.vultron_types import VultronCase


class PersistCase(DataLayerActionWithPorts):
    """
    Persist a VulnerabilityCase to the DataLayer.

    Creates the case record in DataLayer and stores the case_id in the
    blackboard for subsequent nodes.

    Per specs/case-management.yaml CM-02-001.
    """

    def __init__(self, case_obj: VultronCase, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.case_obj = case_obj

    @classmethod
    def output_ports(cls) -> dict[str, PortInformation]:
        return {"case_id": PortInformation(data_type=str, required=True)}

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"case_id": "/case_id"}

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        try:
            self.datalayer.save(self.case_obj)
            self.logger.info(
                f"{self.name}: Persisted VulnerabilityCase"
                f" {self.case_obj.id_}"
            )
            self._set_output("case_id", self.case_obj.id_)
            return Status.SUCCESS

        except Exception as e:
            self.logger.error(f"{self.name}: Error persisting case: {e}")
            return Status.FAILURE


class SetCaseAttributedTo(DataLayerActionWithPorts):
    """
    Set VulnerabilityCase.attributed_to to the receiving actor's ID.

    Must run before PersistCase so the stored case already carries the
    vendor/coordinator owner reference.

    Per specs/case-management.yaml CM-02-008.
    """

    def __init__(self, case_obj: VultronCase, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.case_obj = case_obj

    def update(self) -> Status:
        if self.actor_id is None:
            self.logger.error(f"{self.name}: actor_id not available")
            return Status.FAILURE

        self.case_obj.attributed_to = self.actor_id
        self.logger.debug(
            f"{self.name}: Set attributed_to={self.actor_id}"
            f" on case {self.case_obj.id_}"
        )
        return Status.SUCCESS


class RecordOfferReceivedEventNode(DataLayerActionWithPorts):
    """Conditionally record offer_received and stage the case object."""

    def __init__(self, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["case_id"] = PortInformation(data_type=str, required=True)
        return ports

    @classmethod
    def output_ports(cls) -> dict[str, PortInformation]:
        return {
            "case_for_creation_events": PortInformation(
                data_type=object, required=True
            )
        }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "case_id": "/case_id",
            "case_for_creation_events": "/case_for_creation_events",
        }

    def initialise(self) -> None:
        super().initialise()
        self.case_id_bb: str = self.get_input("case_id")

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        case_id = self.case_id_bb
        if not isinstance(case_id, str):
            self.logger.error(f"{self.name}: case_id not found in blackboard")
            return Status.FAILURE

        case = self.datalayer.read_case(case_id)
        if case is None:
            self.logger.error(
                f"{self.name}: Case {case_id} not found in DataLayer"
            )
            return Status.FAILURE

        self._set_output("case_for_creation_events", case)
        return Status.SUCCESS


class RecordCaseCreatedEventNode(DataLayerActionWithPorts):
    """Record case_created event and persist updated case."""

    def __init__(self, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["case_id"] = PortInformation(data_type=str, required=True)
        ports["case_for_creation_events"] = PortInformation(
            data_type=object, required=True
        )
        return ports

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "case_id": "/case_id",
            "case_for_creation_events": "/case_for_creation_events",
        }

    def initialise(self) -> None:
        super().initialise()
        self.case_id_bb: str = self.get_input("case_id")
        self.case_for_creation_events_bb = self.get_input(
            "case_for_creation_events"
        )

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case_id = self.case_id_bb
        if not isinstance(case_id, str):
            self.logger.error(f"{self.name}: case_id not found in blackboard")
            return Status.FAILURE

        case = self.case_for_creation_events_bb
        if case is None:
            self.logger.error(
                f"{self.name}: case_for_creation_events missing or invalid"
            )
            return Status.FAILURE

        return Status.SUCCESS


class PublishCaseActorIdentityNode(DataLayerActionWithPorts):
    """Publish the CaseActor's identity to the blackboard for downstream nodes.

    Replaces ``ResolveCaseActorUrlsNode``, which derived a *per-case* identity —
    ``{case_actor_service_url}/actors/case-actor-{slug}`` — and also created a
    per-case ``VultronCaseActor`` ``Service`` object to go with it. Both were
    wrong for the same reason: the CaseActor is a participant wearing the
    `CVDRole.CASE_MANAGER` hat, not a per-case entity, and an identity the sender
    invents is one no container hosts, so delivery to it 404s permanently
    (#1872, CP-04-003, BT-10-002).

    This node only *publishes*; it creates nothing. Provisioning the case-actor's
    record belongs to whoever hosts it — for a co-located case-actor that is
    ``WritePendingReportCaseLinkNode``, which writes into the case-actor's own
    store (CP-04-004); for a dedicated container, its own seed config.

    Returns ``FAILURE`` when ``case_actor_service_url`` is unconfigured, rather
    than falling back to this node's own base URL: a guessed base is how the
    proposal ends up addressed to an actor that does not exist.

    *case_id* is a required constructor argument rather than an optional
    blackboard read. ``ResolveCaseActorUrlsNode`` supported both and registered
    its ``case_id`` key as READ or WRITE accordingly; its only caller always
    passed the id, so the other arm was never exercised.
    """

    def __init__(self, case_id: str, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id

    @classmethod
    def output_ports(cls) -> dict[str, PortInformation]:
        return {
            "case_id": PortInformation(data_type=str, required=True),
            "case_actor_id": PortInformation(data_type=str, required=True),
        }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"case_id": "/case_id", "case_actor_id": "/case_actor_id"}

    def update(self) -> Status:
        from vultron.core.behaviors.case.case_actor_identity import (
            case_actor_identity,
        )

        if not self._case_id:
            self.feedback_message = f"{self.name}: case_id is empty"
            self.logger.error(self.feedback_message)
            return Status.FAILURE

        case_actor_id = case_actor_identity()
        if case_actor_id is None:
            self.feedback_message = (
                f"{self.name}: case_actor_service_url is not configured"
                " (set VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL)"
            )
            self.logger.error(self.feedback_message)
            return Status.FAILURE

        self._set_output("case_id", self._case_id)
        self._set_output("case_actor_id", case_actor_id)
        return Status.SUCCESS


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
        from vultron.core.behaviors.case.case_actor_identity import (
            case_actor_identity,
        )
        from vultron.core.behaviors.store_scope import store_for_actor
        from vultron.core.models.case_actor import (
            CaseActor as VultronCaseActor,
        )

        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case_actor_id = case_actor_identity()
        if case_actor_id is None:
            self.feedback_message = (
                f"{self.name}: case_actor_service_url is not configured"
                " (set VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL)"
            )
            self.logger.error(self.feedback_message)
            return Status.FAILURE

        case_actor = VultronCaseActor(id_=case_actor_id, name="CaseActor")
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
            except ValueError:
                pass  # already exists (race or duplicate); not an error
        return Status.SUCCESS
