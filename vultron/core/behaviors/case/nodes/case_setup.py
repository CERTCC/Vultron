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

Provides action nodes that set up core case state: persisting the case record,
assigning attribution, recording creation events, and creating the CaseActor
service actor.

Per specs/case-management.yaml CM-02 requirements.
"""

import hashlib
from typing import Any

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models.protocols import is_case_model
from vultron.core.models.vultron_types import (
    VultronCase,
    VultronCaseActor,
    VultronParticipant,
)
from vultron.core.states.roles import CVDRole
from vultron.core.use_cases._helpers import _as_id


def _derive_case_slug(case_id: str) -> str:
    """Derive a short deterministic slug from case_id."""
    if case_id.startswith("urn:uuid:"):
        return case_id[len("urn:uuid:") :]
    return hashlib.sha256(case_id.encode()).hexdigest()[:12]


def _resolve_server_base_url(blackboard: Any) -> str:
    """Read server_base_url from blackboard or fall back to config."""
    try:
        return str(blackboard.get("server_base_url")).rstrip("/")
    except KeyError:
        from vultron.config import get_config

        return get_config().server.base_url.rstrip("/")


class PersistCase(DataLayerAction):
    """
    Persist a VulnerabilityCase to the DataLayer.

    Creates the case record in DataLayer and stores the case_id in the
    blackboard for subsequent nodes.

    Per specs/case-management.yaml CM-02-001.
    """

    def __init__(self, case_obj: VultronCase, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.case_obj = case_obj

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error(f"{self.name}: DataLayer not available")
            return Status.FAILURE

        try:
            self.datalayer.save(self.case_obj)
            self.logger.info(
                f"{self.name}: Persisted VulnerabilityCase"
                f" {self.case_obj.id_}"
            )

            self.blackboard.register_key(
                key="case_id", access=py_trees.common.Access.WRITE
            )
            self.blackboard.case_id = self.case_obj.id_

            return Status.SUCCESS

        except Exception as e:
            self.logger.error(f"{self.name}: Error persisting case: {e}")
            return Status.FAILURE


class SetCaseAttributedTo(DataLayerAction):
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


class RecordCaseCreationEvents(py_trees.composites.Sequence):
    """Composed subtree that records offer_received (optional) and case_created."""

    def __init__(self, case_obj: VultronCase, name: str | None = None):
        self.case_obj = case_obj
        super().__init__(
            name=name or self.__class__.__name__,
            memory=False,
            children=[
                RecordOfferReceivedEventNode(),
                RecordCaseCreatedEventNode(),
            ],
        )


class RecordOfferReceivedEventNode(DataLayerAction):
    """Conditionally record offer_received and stage the case object."""

    def __init__(self, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_id", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="case_for_creation_events",
            access=py_trees.common.Access.WRITE,
        )

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error(f"{self.name}: DataLayer not available")
            return Status.FAILURE

        try:
            case_id = self.blackboard.get("case_id")
        except KeyError:
            self.logger.error(f"{self.name}: case_id not found in blackboard")
            return Status.FAILURE
        if not isinstance(case_id, str):
            self.logger.error(f"{self.name}: case_id not found in blackboard")
            return Status.FAILURE

        case = self.datalayer.read(case_id)
        if not is_case_model(case):
            self.logger.error(
                f"{self.name}: Case {case_id} not found in DataLayer"
            )
            return Status.FAILURE

        try:
            activity = self.blackboard.get("activity")
        except KeyError:
            activity = None

        offer_ref = getattr(activity, "in_reply_to", None)
        if offer_ref is not None:
            offer_id = (
                offer_ref.id_ if hasattr(offer_ref, "id_") else str(offer_ref)
            )
            case.record_event(offer_id, "offer_received")
            self.logger.info(
                f"{self.name}: Recorded offer_received event"
                f" for {offer_id} on case {case_id}"
            )

        self.blackboard.case_for_creation_events = case
        return Status.SUCCESS


class RecordCaseCreatedEventNode(DataLayerAction):
    """Record case_created event and persist updated case."""

    def __init__(self, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_id", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="case_for_creation_events",
            access=py_trees.common.Access.READ,
        )

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error(f"{self.name}: DataLayer not available")
            return Status.FAILURE

        try:
            case_id = self.blackboard.get("case_id")
        except KeyError:
            self.logger.error(f"{self.name}: case_id not found in blackboard")
            return Status.FAILURE
        if not isinstance(case_id, str):
            self.logger.error(f"{self.name}: case_id not found in blackboard")
            return Status.FAILURE

        try:
            case = self.blackboard.get("case_for_creation_events")
        except KeyError:
            self.logger.error(
                f"{self.name}: case_for_creation_events missing or invalid"
            )
            return Status.FAILURE
        if not is_case_model(case):
            self.logger.error(
                f"{self.name}: case_for_creation_events missing or invalid"
            )
            return Status.FAILURE

        case.record_event(case_id, "case_created")
        self.logger.info(
            f"{self.name}: Recorded case_created event on case {case_id}"
        )
        self.datalayer.save(case)
        return Status.SUCCESS


class ResolveCaseActorUrlsNode(DataLayerAction):
    """Resolve case_id + deterministic CaseActor IDs and publish to blackboard."""

    def __init__(self, case_id: str | None = None, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self._case_id_arg = case_id

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        if self._case_id_arg is None:
            self.blackboard.register_key(
                key="case_id", access=py_trees.common.Access.READ
            )
        else:
            self.blackboard.register_key(
                key="case_id", access=py_trees.common.Access.WRITE
            )
        self.blackboard.register_key(
            key="server_base_url", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="case_actor_id", access=py_trees.common.Access.WRITE
        )
        self.blackboard.register_key(
            key="case_actor_participant_id",
            access=py_trees.common.Access.WRITE,
        )

    def update(self) -> Status:
        case_id = self._case_id_arg
        if case_id is None:
            try:
                case_id = self.blackboard.get("case_id")
            except KeyError:
                case_id = None
        if not isinstance(case_id, str) or case_id == "":
            self.logger.error(
                "%s: case_id not available from constructor or blackboard",
                self.name,
            )
            return Status.FAILURE

        case_slug = _derive_case_slug(case_id)
        server_base_url = _resolve_server_base_url(self.blackboard)
        case_actor_id = f"{server_base_url}/actors/case-actor-{case_slug}"
        participant_id = (
            f"{server_base_url}/actors/case-actor-{case_slug}/participant"
        )

        if self._case_id_arg is not None:
            self.blackboard.case_id = case_id
        self.blackboard.case_actor_id = case_actor_id
        self.blackboard.case_actor_participant_id = participant_id
        return Status.SUCCESS


class ReuseExistingCaseActorParticipantNode(DataLayerAction):
    """Idempotency guard: succeed if CaseActor participant already exists."""

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_actor_id", access=py_trees.common.Access.WRITE
        )
        self.blackboard.register_key(
            key="case_actor_participant_id",
            access=py_trees.common.Access.READ,
        )

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error("%s: DataLayer not available", self.name)
            return Status.FAILURE
        participant_id = self.blackboard.get("case_actor_participant_id")
        case_actor_id = self.blackboard.get("case_actor_id")
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
        self.blackboard.case_actor_id = authoritative_id
        self.logger.info(
            "%s: CaseActor participant already registered; reusing id '%s'",
            self.name,
            authoritative_id,
        )
        return Status.SUCCESS


class CreateCaseActorServiceNode(DataLayerAction):
    """Create (or reuse) the CaseActor service object."""

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_id", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="case_actor_id", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                "%s: DataLayer or actor_id not available",
                self.name,
            )
            return Status.FAILURE
        case_id = self.blackboard.get("case_id")
        case_actor_id = self.blackboard.get("case_actor_id")
        if not isinstance(case_id, str) or not isinstance(case_actor_id, str):
            self.logger.error("%s: case_id/case_actor_id missing", self.name)
            return Status.FAILURE

        case_actor = VultronCaseActor(
            id_=case_actor_id,
            name=f"CaseActor for {case_id}",
            attributed_to=self.actor_id,
            context=case_id,
        )
        try:
            self.datalayer.create(case_actor)
            self.logger.info(
                "%s: Created CaseActor %s for case %s",
                self.name,
                case_actor_id,
                case_id,
            )
        except ValueError as e:
            self.logger.warning(
                "%s: CaseActor %s already exists: %s",
                self.name,
                case_actor_id,
                e,
            )
        return Status.SUCCESS


class RegisterCaseActorParticipantNode(DataLayerAction):
    """Attach the CaseActor participant to the case when absent."""

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_id", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="case_actor_id", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="case_actor_participant_id",
            access=py_trees.common.Access.READ,
        )

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error("%s: DataLayer not available", self.name)
            return Status.FAILURE

        case_id = self.blackboard.get("case_id")
        case_actor_id = self.blackboard.get("case_actor_id")
        participant_id = self.blackboard.get("case_actor_participant_id")
        if (
            not isinstance(case_id, str)
            or not isinstance(case_actor_id, str)
            or not isinstance(participant_id, str)
        ):
            self.logger.error("%s: CaseActor context missing", self.name)
            return Status.FAILURE

        case = self.datalayer.read(case_id)
        if not is_case_model(case):
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


class CreateCaseActorNode(py_trees.composites.Sequence):
    """
    Composed subtree that creates and registers the CaseActor for a case.

    Per specs/case-management.yaml CM-02-001 and BTND-07-001.
    """

    def __init__(self, case_id: str | None = None, name: str | None = None):
        super().__init__(
            name=name or self.__class__.__name__,
            memory=False,
            children=[
                ResolveCaseActorUrlsNode(case_id=case_id),
                py_trees.composites.Selector(
                    name="EnsureCaseActorRegistered",
                    memory=False,
                    children=[
                        ReuseExistingCaseActorParticipantNode(),
                        py_trees.composites.Sequence(
                            name="CreateAndRegisterCaseActor",
                            memory=False,
                            children=[
                                CreateCaseActorServiceNode(),
                                RegisterCaseActorParticipantNode(),
                            ],
                        ),
                    ],
                ),
            ],
        )
