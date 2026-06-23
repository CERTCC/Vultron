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

"""Actor-participation emit nodes for case behavior trees.

Provides leaf action nodes that emit outbound activities for actor
invitation and invite-acceptance workflows, and for applying received
ownership-transfer decisions to the case record.

Composite subtrees assembling these leaf nodes are defined in the sibling
``actor_trigger_trees.py`` and ``ownership_transfer_tree.py`` modules at
the process-area root per BTND-07-003:

- ``invite_actor_to_case_trigger_bt``
- ``accept_case_invite_trigger_bt``
- ``create_accept_ownership_transfer_tree``
"""

import uuid
from typing import Any, cast

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models.activity import VultronActivity
from vultron.core.models.protocols import is_case_model
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.use_cases._helpers import _as_id


class EmitInviteActorToCaseNode(DataLayerAction):
    """Create Invite(Actor, Case) and queue in the Case Actor's outbox.

    Uses ``trigger_activity_factory.invite_actor_to_case()`` with
    ``actor=self.actor_id`` (expected to be the Case Actor URI) and
    ``to=[invitee_id]``.  An optional ``attributed_to`` carries the
    original requesting actor when the invite is sent from the Case
    Actor identity (PCR-08-007).
    """

    def __init__(
        self,
        invitee_id: str,
        case_id: str,
        attributed_to: str | None = None,
        captured: dict | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.invitee_id = invitee_id
        self.case_id = case_id
        self.attributed_to = attributed_to
        self._captured = captured

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.feedback_message = "DataLayer or actor_id not available"
            return Status.FAILURE

        factory = self.trigger_activity_factory
        if factory is None:
            self.feedback_message = (
                "trigger_activity_factory not in blackboard"
            )
            self.logger.error(self.feedback_message)
            return Status.FAILURE

        try:
            activity_id, activity_dict = factory.invite_actor_to_case(
                invitee_id=self.invitee_id,
                case_id=self.case_id,
                actor=self.actor_id,
                to=[self.invitee_id],
                attributed_to=self.attributed_to,
            )
            cast(CaseOutboxPersistence, self.datalayer).record_outbox_item(
                self.actor_id, activity_id
            )
            if self._captured is not None:
                self._captured["activity"] = activity_dict
            self.logger.info(
                "Actor '%s' emitted Invite(Actor, Case) to '%s' for case '%s'",
                self.actor_id,
                self.invitee_id,
                self.case_id,
            )
            return Status.SUCCESS

        except Exception as e:
            self.feedback_message = f"EmitInviteActorToCase failed: {e}"
            self.logger.error(self.feedback_message)
            return Status.FAILURE


class EmitAcceptCaseInviteNode(DataLayerAction):
    """Create Accept(Invite) and queue in the invitee's outbox.

    Uses ``trigger_activity_factory.accept_case_invite()`` — the factory
    derives the recipient from the persisted invite object.
    """

    def __init__(
        self,
        invite_id: str,
        captured: dict | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.invite_id = invite_id
        self._captured = captured

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.feedback_message = "DataLayer or actor_id not available"
            return Status.FAILURE

        factory = self.trigger_activity_factory
        if factory is None:
            self.feedback_message = (
                "trigger_activity_factory not in blackboard"
            )
            self.logger.error(self.feedback_message)
            return Status.FAILURE

        try:
            activity_id, activity_dict = factory.accept_case_invite(
                invite_id=self.invite_id,
                actor=self.actor_id,
            )
            cast(CaseOutboxPersistence, self.datalayer).record_outbox_item(
                self.actor_id, activity_id
            )
            if self._captured is not None:
                self._captured["activity"] = activity_dict
            self.logger.info(
                "Actor '%s' accepted case invite '%s'",
                self.actor_id,
                self.invite_id,
            )
            return Status.SUCCESS

        except Exception as e:
            self.feedback_message = f"EmitAcceptCaseInvite failed: {e}"
            self.logger.error(self.feedback_message)
            return Status.FAILURE


class AcceptCaseOwnershipTransferNode(DataLayerAction):
    """Apply an ownership-transfer acceptance to the case record.

    Reads the case from the DataLayer, updates ``case.attributed_to`` to
    the new owner, and persists the updated case.  Idempotent: when the
    case is already owned by ``new_owner_id``, returns ``SUCCESS`` without
    mutation.

    Returns ``SUCCESS`` on success or when already idempotent, ``FAILURE``
    when the DataLayer is unavailable or the case is not found.
    """

    def __init__(
        self,
        case_id: str,
        new_owner_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.new_owner_id = new_owner_id

    def update(self) -> Status:
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            self.logger.error("%s: DataLayer not available", self.name)
            return Status.FAILURE

        case = self.datalayer.read(self.case_id)
        if not is_case_model(case):
            self.feedback_message = f"case '{self.case_id}' not found"
            self.logger.warning(
                "%s: case '%s' not found",
                self.name,
                self.case_id,
            )
            return Status.FAILURE

        current_owner_id = _as_id(case.attributed_to)
        if current_owner_id == self.new_owner_id:
            self.logger.info(
                "%s: case '%s' already owned by '%s' — skipping (idempotent)",
                self.name,
                self.case_id,
                self.new_owner_id,
            )
            return Status.SUCCESS

        case.attributed_to = self.new_owner_id  # type: ignore[assignment]
        self.datalayer.save(case)
        self.logger.info(
            "%s: transferred ownership of case '%s' from '%s' to '%s'",
            self.name,
            self.case_id,
            current_owner_id,
            self.new_owner_id,
        )
        return Status.SUCCESS


class ProposeCaseToActorNode(DataLayerAction):
    """Send ``Create(as_CaseProposal)`` to the registered case-actor service.

    Reads ``case_id`` and ``case_actor_id`` from the blackboard (written by
    ``CreateCaseActorNode`` / ``ResolveCaseActorUrlsNode``), reads the
    linked ``VulnerabilityReport`` from the DataLayer, constructs an
    ``as_CaseProposal`` dict, and queues ``Create(as_CaseProposal)`` to the
    actor's outbox so the case-actor service can initialize the case.

    This node MUST run AFTER ``CreateCaseActorNode`` succeeds, because the
    case-actor identity must exist in the DataLayer before the proposal can
    be addressed to it (CP-04-002).

    Returns FAILURE when:

    - DataLayer or ``actor_id`` is unavailable.
    - ``case_id`` or ``case_actor_id`` is missing from the blackboard.
    - The case is not found in the DataLayer.
    - No ``VulnerabilityReport`` is linked to the case (CP-01-004).
    - The linked report is not found in the DataLayer.

    Per ``specs/case-proposal.yaml`` CP-04-001, CP-04-002.
    """

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

    def _read_blackboard_ids(self) -> tuple[str, str] | None:
        """Read case_id and case_actor_id from the blackboard.

        Returns ``(case_id, case_actor_id)`` on success, or ``None`` after
        setting ``feedback_message`` on any error.
        """
        try:
            case_id = self.blackboard.get("case_id")
        except KeyError:
            self.feedback_message = "case_id not found in blackboard"
            return None
        if not isinstance(case_id, str) or not case_id:
            self.feedback_message = "case_id must be a non-empty string"
            return None

        try:
            case_actor_id = self.blackboard.get("case_actor_id")
        except KeyError:
            self.feedback_message = "case_actor_id not found in blackboard"
            return None
        if not isinstance(case_actor_id, str) or not case_actor_id:
            self.feedback_message = "case_actor_id must be a non-empty string"
            return None

        return case_id, case_actor_id

    def _read_report_dict(self, case_id: str) -> dict | None:
        """Read the linked VulnerabilityReport and return its serialized dict.

        Returns the report dict on success, or ``None`` after setting
        ``feedback_message`` on any error.
        """
        case = self.datalayer.read(case_id)  # type: ignore[union-attr]
        if not is_case_model(case):
            self.feedback_message = f"Case '{case_id}' not found"
            self.logger.error("%s: %s", self.name, self.feedback_message)
            return None

        if not case.vulnerability_reports:
            self.feedback_message = (
                f"No VulnerabilityReport linked to case '{case_id}'"
                " — cannot build CaseProposal (CP-01-004)"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return None

        report_id = case.vulnerability_reports[0]
        raw_report = self.datalayer.read(report_id)  # type: ignore[union-attr]
        if raw_report is None:
            self.feedback_message = (
                f"VulnerabilityReport '{report_id}' not found in DataLayer"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return None

        # Serialize the report inline (CP-01-004: object_ must be inline,
        # not a URI reference).  Duck-typed to avoid a core->wire import.
        if hasattr(raw_report, "model_dump"):
            return raw_report.model_dump(by_alias=True)  # type: ignore[no-any-return]
        return {"id": report_id, "type": "VulnerabilityReport"}

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.feedback_message = "DataLayer or actor_id not available"
            return Status.FAILURE

        ids = self._read_blackboard_ids()
        if ids is None:
            return Status.FAILURE
        case_id, case_actor_id = ids

        report_dict = self._read_report_dict(case_id)
        if report_dict is None:
            return Status.FAILURE

        # Build the as_CaseProposal as a plain dict (ARCH-01-001: core must
        # not import wire types).  The vocabulary registry on the receiving
        # side reconstructs the typed as_CaseProposal from this dict.
        proposal_dict = {
            "type": "CaseProposal",
            "id": f"urn:uuid:{uuid.uuid4()}",
            "attributed_to": self.actor_id,
            "object": report_dict,
            "target": case_actor_id,
        }

        # Create(as_CaseProposal) stored as a generic VultronActivity so
        # the core layer stays wire-free.
        activity = VultronActivity(
            type_="Create",
            actor=self.actor_id,
            object_=proposal_dict,
            to=[case_actor_id],
        )

        try:
            self.datalayer.create(activity)
        except ValueError as exc:
            self.feedback_message = (
                f"Create(CaseProposal) activity creation failed: {exc}"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        cast(CaseOutboxPersistence, self.datalayer).record_outbox_item(
            self.actor_id, activity.id_
        )
        self.logger.info(
            "%s: Queued Create(as_CaseProposal) '%s' to outbox"
            " for case-actor '%s' (case '%s')",
            self.name,
            activity.id_,
            case_actor_id,
            case_id,
        )
        return Status.SUCCESS
