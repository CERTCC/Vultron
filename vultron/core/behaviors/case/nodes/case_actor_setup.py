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

"""CaseActor identity resolution and registration action nodes.

Provides the leaf nodes that resolve deterministic CaseActor service URLs,
guard against duplicate participant registration, create the CaseActor service
object, and attach the CaseActor participant to the case record.

Composite subtrees that orchestrate these leaf nodes are in
``case_setup_tree.py`` at the process-area root (BTND-07-003).

Per specs/case-management.yaml CP-08, CM-02.
"""

from __future__ import annotations

import hashlib
from typing import Any

from py_trees.common import Status
from py_trees.ports import NoDataAvailable

from vultron.config import get_config
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.vultron_types import (
    VultronCaseActor,
    VultronParticipant,
)
from vultron.enums.roles import CVDRole


def _derive_case_slug(case_id: str) -> str:
    """Derive a short deterministic slug from case_id."""
    if case_id.startswith("urn:uuid:"):
        return case_id[len("urn:uuid:") :]
    return hashlib.sha256(case_id.encode()).hexdigest()[:12]


class ResolveCaseActorUrlsNode(DataLayerActionWithPorts):
    """Resolve case_id + deterministic CaseActor IDs and publish to blackboard.

    Reads ``case_actor_service_url`` from ``ActorConfig`` (CP-08-002).
    Returns ``FAILURE`` when the field is not configured (CP-08-003).
    """

    def __init__(self, case_id: str | None = None, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self._case_id_arg = case_id

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        # "case_id_in" is the read-side alias; remapped to the same physical
        # key as the write-side "case_id" output port.  Distinct logical names
        # are required because py_trees forbids a name appearing in both
        # input_ports() and output_ports().
        ports["case_id_in"] = PortInformation(data_type=str, required=False)
        return ports

    @classmethod
    def output_ports(cls) -> dict[str, PortInformation]:
        return {
            "case_id": PortInformation(data_type=str, required=True),
            "case_actor_id": PortInformation(data_type=str, required=True),
            "case_actor_participant_id": PortInformation(
                data_type=str, required=True
            ),
        }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "case_id_in": "/case_id",
            "case_id": "/case_id",
            "case_actor_id": "/case_actor_id",
            "case_actor_participant_id": "/case_actor_participant_id",
        }

    def initialise(self) -> None:
        super().initialise()
        if self._case_id_arg is None:
            try:
                self._case_id_bb: str | None = self.get_input("case_id_in")
            except (NoDataAvailable, NotImplementedError):
                self._case_id_bb = None
        else:
            self._case_id_bb = None

    def update(self) -> Status:
        case_id = self._case_id_arg
        if case_id is None:
            case_id = self._case_id_bb
        if not isinstance(case_id, str) or case_id == "":
            self.logger.error(
                "%s: case_id not available from constructor or blackboard",
                self.name,
            )
            return Status.FAILURE

        cfg = get_config().actor
        if cfg.case_actor_service_url is None:
            self.logger.error(
                "%s: case_actor_service_url is not configured in ActorConfig"
                " (set VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL)",
                self.name,
            )
            return Status.FAILURE

        base_url = str(cfg.case_actor_service_url).rstrip("/")
        case_slug = _derive_case_slug(case_id)
        case_actor_id = f"{base_url}/actors/case-actor-{case_slug}"
        participant_id = (
            f"{base_url}/actors/case-actor-{case_slug}/participant"
        )

        if self._case_id_arg is not None:
            self._set_output("case_id", case_id)
        self._set_output("case_actor_id", case_actor_id)
        self._set_output("case_actor_participant_id", participant_id)
        return Status.SUCCESS


class ReuseExistingCaseActorParticipantNode(DataLayerActionWithPorts):
    """Idempotency guard: succeed if CaseActor participant already exists."""

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        # "case_actor_id_in" is the read-side alias; remapped to the same
        # physical key as the write-side "case_actor_id" output port.
        ports["case_actor_id_in"] = PortInformation(
            data_type=str, required=True
        )
        ports["case_actor_participant_id"] = PortInformation(
            data_type=str, required=True
        )
        return ports

    @classmethod
    def output_ports(cls) -> dict[str, PortInformation]:
        return {"case_actor_id": PortInformation(data_type=str, required=True)}

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "case_actor_id_in": "/case_actor_id",
            "case_actor_id": "/case_actor_id",
            "case_actor_participant_id": "/case_actor_participant_id",
        }

    def initialise(self) -> None:
        super().initialise()
        self.case_actor_id_bb: str = self.get_input("case_actor_id_in")
        self.case_actor_participant_id_bb: str = self.get_input(
            "case_actor_participant_id"
        )

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        participant_id = self.case_actor_participant_id_bb
        case_actor_id = self.case_actor_id_bb
        if not isinstance(participant_id, str) or not isinstance(
            case_actor_id, str
        ):
            self.logger.error(
                "%s: case_actor ids missing in blackboard",
                self.name,
            )
            return Status.FAILURE

        existing_participant = self.datalayer.read(participant_id)
        if existing_participant is None:
            return Status.FAILURE

        authoritative_id = (
            _as_id(getattr(existing_participant, "attributed_to", None))
            or case_actor_id
        )
        self._set_output("case_actor_id", authoritative_id)
        self.logger.info(
            "%s: CaseActor participant already registered; reusing id '%s'",
            self.name,
            authoritative_id,
        )
        return Status.SUCCESS


class CreateCaseActorServiceNode(DataLayerActionWithPorts):
    """Create (or reuse) the CaseActor service object.

    Writes the record **twice**, into two different stores, because it plays two
    different roles:

    1. Into the CaseActor's *own* store, which is what makes this node's output a
       hosted actor rather than just a row.  ``GET``/``POST`` on
       ``/actors/{slug}/…`` resolves the actor from the store that slug names
       (``_resolve_actor_or_404``), so without this write the CaseActor's inbox
       answers ``404 Actor not found`` and nothing addressed to it — including
       the ``Create(VulnerabilityCase)`` that seeds every participant replica —
       is ever delivered.  This is the same rule ``POST /actors/`` follows.
    2. Into the creating actor's store, as an address-book entry for a peer it
       now knows (ADR-0070 decision 5).  Sibling nodes resolve the CaseActor
       from the *executing* actor's store, so this copy is what they read.

    The two writes are not redundant: one publishes an endpoint, the other
    records knowledge.  Under a shared store they were indistinguishable, which
    is why one write used to be enough.
    """

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["case_id"] = PortInformation(data_type=str, required=True)
        ports["case_actor_id"] = PortInformation(data_type=str, required=True)
        return ports

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "case_id": "/case_id",
            "case_actor_id": "/case_actor_id",
        }

    def initialise(self) -> None:
        super().initialise()
        self.case_id_bb: str = self.get_input("case_id")
        self.case_actor_id_bb: str = self.get_input("case_actor_id")

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None
        case_id = self.case_id_bb
        case_actor_id = self.case_actor_id_bb
        if not isinstance(case_id, str) or not isinstance(case_actor_id, str):
            self.logger.error("%s: case_id/case_actor_id missing", self.name)
            return Status.FAILURE

        case_actor = VultronCaseActor(
            id_=case_actor_id,
            name=f"CaseActor for {case_id}",
            attributed_to=self.actor_id,
            context=case_id,
        )
        own_store = self._store_for(case_actor_id)
        if own_store is None:
            self.logger.error(
                "%s: cannot open the CaseActor's own store for %s, so it would"
                " not be a hosted actor and its inbox would 404",
                self.name,
                case_actor_id,
            )
            return Status.FAILURE

        for label, store in (
            ("its own", own_store),
            ("the creating actor's", self.datalayer),
        ):
            try:
                store.create(case_actor)
                self.logger.info(
                    "%s: Created CaseActor %s for case %s in %s store",
                    self.name,
                    case_actor_id,
                    case_id,
                    label,
                )
            except ValueError as e:
                self.logger.warning(
                    "%s: CaseActor %s already exists in %s store: %s",
                    self.name,
                    case_actor_id,
                    label,
                    e,
                )
        return Status.SUCCESS

    def _store_for(self, actor_id: str) -> Any:
        """Return *actor_id*'s own store, or ``None`` when it cannot be opened.

        Named rather than implicit: ``clone_for_actor`` is the only sanctioned
        route to another actor's store (ADR-0070 decision 7), so a cross-actor
        write reads as one.
        """
        assert self.datalayer is not None
        if getattr(self.datalayer, "actor_id", None) == actor_id:
            return self.datalayer
        clone_for_actor = getattr(self.datalayer, "clone_for_actor", None)
        if not callable(clone_for_actor):
            return None
        return clone_for_actor(actor_id)


class RegisterCaseActorParticipantNode(DataLayerActionWithPorts):
    """Attach the CaseActor participant to the case when absent."""

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["case_id"] = PortInformation(data_type=str, required=True)
        ports["case_actor_id"] = PortInformation(data_type=str, required=True)
        ports["case_actor_participant_id"] = PortInformation(
            data_type=str, required=True
        )
        return ports

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "case_id": "/case_id",
            "case_actor_id": "/case_actor_id",
            "case_actor_participant_id": "/case_actor_participant_id",
        }

    def initialise(self) -> None:
        super().initialise()
        self.case_id_bb: str = self.get_input("case_id")
        self.case_actor_id_bb: str = self.get_input("case_actor_id")
        self.case_actor_participant_id_bb: str = self.get_input(
            "case_actor_participant_id"
        )

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case_id = self.case_id_bb
        case_actor_id = self.case_actor_id_bb
        participant_id = self.case_actor_participant_id_bb
        if (
            not isinstance(case_id, str)
            or not isinstance(case_actor_id, str)
            or not isinstance(participant_id, str)
        ):
            self.logger.error("%s: CaseActor context missing", self.name)
            return Status.FAILURE

        case = self.datalayer.read(case_id)
        if not isinstance(case, VulnerabilityCase):
            self.logger.error(
                "%s: Case '%s' not found; cannot register CaseActor participant",
                self.name,
                case_id,
            )
            return Status.FAILURE

        existing = self.datalayer.read(participant_id)
        if existing is not None:
            return Status.SUCCESS

        participant = VultronParticipant(
            id_=participant_id,
            attributed_to=case_actor_id,
            context=case_id,
            name=f"CaseActor for {case_id}",
            case_roles=[CVDRole.COORDINATOR, CVDRole.CASE_MANAGER],
        )
        try:
            self.datalayer.create(participant)
        except ValueError:
            pass
        case.add_participant(participant)
        self.datalayer.save(case)
        self.logger.info(
            "%s: Registered CaseActor participant '%s' for case '%s'",
            self.name,
            participant_id,
            case_id,
        )
        return Status.SUCCESS
