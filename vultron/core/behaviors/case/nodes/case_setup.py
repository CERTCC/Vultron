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


class RecordCaseCreationEvents(DataLayerAction):
    """
    Backfill pre-case events into the case event log at case creation.

    Records a trusted-timestamp event for the case creation itself.
    If the triggering activity has an ``in_reply_to`` reference (e.g. an
    originating Offer), that event is also backfilled as an
    ``"offer_received"`` entry.

    Must run after PersistCase so the case exists in the DataLayer.
    Reads ``case_id`` and optionally ``activity`` from the blackboard.

    Per specs/case-management.yaml CM-02-009.
    """

    def __init__(self, case_obj: VultronCase, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.case_obj = case_obj

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_id", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error(f"{self.name}: DataLayer not available")
            return Status.FAILURE

        try:
            case_id = self.blackboard.get("case_id")
            if case_id is None:
                self.logger.error(
                    f"{self.name}: case_id not found in blackboard"
                )
                return Status.FAILURE

            case = self.datalayer.read(case_id)
            if not is_case_model(case):
                self.logger.error(
                    f"{self.name}: Case {case_id} not found in DataLayer"
                )
                return Status.FAILURE

            # Backfill originating offer receipt if available.
            # The activity key is optional — the node handles its absence.
            try:
                activity = self.blackboard.get("activity")
            except KeyError:
                activity = None
            if activity is not None:
                offer_ref = getattr(activity, "in_reply_to", None)
                if offer_ref is not None:
                    offer_id = (
                        offer_ref.id_
                        if hasattr(offer_ref, "id_")
                        else str(offer_ref)
                    )
                    case.record_event(offer_id, "offer_received")
                    self.logger.info(
                        f"{self.name}: Recorded offer_received event"
                        f" for {offer_id} on case {case_id}"
                    )

            # Record the case creation event
            case.record_event(case_id, "case_created")
            self.logger.info(
                f"{self.name}: Recorded case_created event on case {case_id}"
            )

            self.datalayer.save(case)
            return Status.SUCCESS

        except Exception as e:
            self.logger.error(
                f"{self.name}: Error recording case creation events: {e}"
            )
            return Status.FAILURE


class CreateCaseActorNode(DataLayerAction):
    """
    Create a CaseActor (Service) for the new VulnerabilityCase.

    Each VulnerabilityCase MUST have exactly one associated CaseActor.
    The CaseActor is an ActivityStreams Service that manages case
    communications (inbox/outbox).

    When ``case_id`` is not supplied at construction time the node reads
    ``case_id`` from the blackboard (written by a preceding
    ``CreateCaseNode``).  After the CaseActor is created its ID is written
    to the blackboard as ``case_actor_id`` so that subsequent nodes (e.g.
    ``SendOfferCaseManagerRoleNode``) can address it without a DataLayer
    scan.

    Per specs/case-management.yaml CM-02-001.
    """

    def __init__(
        self,
        case_id: str | None = None,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self._case_id_arg = case_id

    def setup(self, **kwargs: Any) -> None:
        """Register blackboard keys including optional case_id read."""
        super().setup(**kwargs)
        if self._case_id_arg is None:
            self.blackboard.register_key(
                key="case_id", access=py_trees.common.Access.READ
            )
        self.blackboard.register_key(
            key="case_actor_id", access=py_trees.common.Access.WRITE
        )
        self.blackboard.register_key(
            key="case_actor_participant_id",
            access=py_trees.common.Access.WRITE,
        )
        self.blackboard.register_key(
            key="server_base_url", access=py_trees.common.Access.READ
        )

    def _derive_case_slug(self, case_id: str) -> str:
        """Derive a short deterministic slug from case_id."""
        import hashlib

        if case_id.startswith("urn:uuid:"):
            return case_id[len("urn:uuid:") :]
        return hashlib.sha256(case_id.encode()).hexdigest()[:12]

    def _resolve_server_base_url(self) -> str:
        """Read server_base_url from blackboard or fall back to config."""
        try:
            return str(self.blackboard.get("server_base_url")).rstrip("/")
        except KeyError:
            from vultron.config import get_config

            return get_config().server.base_url.rstrip("/")

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                f"{self.name}: DataLayer or actor_id not available"
            )
            return Status.FAILURE

        case_id = self._case_id_arg
        if case_id is None:
            case_id = self.blackboard.get("case_id")
        if not case_id:
            self.logger.error(
                f"{self.name}: case_id not available from constructor"
                " or blackboard"
            )
            return Status.FAILURE

        # Use deterministic IDs so re-runs are idempotent.
        # Derive a short slug from the case_id to create a flat,
        # HTTP-routable actor ID.
        case_slug = self._derive_case_slug(case_id)
        server_base_url = self._resolve_server_base_url()

        case_actor_id = f"{server_base_url}/actors/case-actor-{case_slug}"
        participant_id = (
            f"{server_base_url}/actors/case-actor-{case_slug}/participant"
        )

        try:
            # Idempotency: if the participant already exists use its
            # attributed_to as the authoritative actor ID so downstream nodes
            # always get a consistent value regardless of re-execution order.
            existing_participant = self.datalayer.read(participant_id)
            if existing_participant is not None:
                authoritative_id = (
                    _as_id(
                        getattr(existing_participant, "attributed_to", None)
                    )
                    or case_actor_id
                )
                self.blackboard.case_actor_id = authoritative_id
                self.blackboard.case_actor_participant_id = participant_id
                self.logger.info(
                    f"{self.name}: CaseActor participant already registered;"
                    f" reusing id '{authoritative_id}'"
                )
                return Status.SUCCESS

            case_actor = VultronCaseActor(
                id_=case_actor_id,
                name=f"CaseActor for {case_id}",
                attributed_to=self.actor_id,
                context=case_id,
            )
            try:
                self.datalayer.create(case_actor)
                self.logger.info(
                    f"{self.name}: Created CaseActor {case_actor_id}"
                    f" for case {case_id}"
                )
            except ValueError as e:
                self.logger.warning(
                    f"{self.name}: CaseActor {case_actor_id}"
                    f" already exists: {e}"
                )

            # Register the CaseActor as a CaseActorParticipant so receivers
            # can extract trusted_case_actor_id from the case snapshot during
            # bootstrap trust establishment (CBT-01-003).
            self._register_case_actor_participant(
                case_id, case_actor_id, participant_id
            )

            # Publish IDs to the blackboard for downstream nodes.
            self.blackboard.case_actor_id = case_actor_id
            self.blackboard.case_actor_participant_id = participant_id

            return Status.SUCCESS

        except Exception as e:
            self.logger.error(f"{self.name}: Error creating CaseActor: {e}")
            return Status.FAILURE

    def _register_case_actor_participant(
        self, case_id: str, case_actor_id: str, participant_id: str
    ) -> None:
        """Add a VultronParticipant with COORDINATOR+CASE_MANAGER roles to the case.

        Uses core-layer ``VultronParticipant`` with both roles set so the
        bootstrap receiver can identify the CaseActor from the case snapshot
        without requiring a wire-layer import (CBT-01-003).
        """
        if self.datalayer is None:
            return

        case = self.datalayer.read(case_id)
        if not is_case_model(case):
            self.logger.warning(
                f"{self.name}: Case '{case_id}' not found; "
                "cannot register CaseActor participant"
            )
            return

        existing = self.datalayer.read(participant_id)
        if existing is not None:
            # Already registered; participant was checked in update() so this
            # path is only reached on a race condition — safe to skip.
            return

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
            pass  # already exists — idempotent

        case.case_participants.append(participant_id)
        case.actor_participant_index[case_actor_id] = participant_id
        self.datalayer.save(case)
        self.logger.info(
            f"{self.name}: Registered CaseActor participant '{participant_id}'"
            f" (roles: COORDINATOR, CASE_MANAGER) for case '{case_id}'"
        )
