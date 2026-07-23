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

Also provides :class:`EvaluateDefaultRolesNode`, the ADR-0024 Evaluator
call-out point that assigns default roles for a suggested actor (CM-16-003).

Composite subtrees assembling these leaf nodes are defined in the sibling
``actor_trigger_trees.py`` and ``ownership_transfer_tree.py`` modules at
the process-area root per BTND-07-003:

- ``invite_actor_to_case_trigger_bt``
- ``accept_case_invite_trigger_bt``
- ``create_accept_ownership_transfer_tree``
"""

import logging
from typing import Any, cast

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.behaviors.sync.commit_tree import (
    create_commit_log_entry_tree,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.enums.roles import CVDRole, serialize_roles


class EmitInviteActorToCaseNode(DataLayerAction):
    """Create Invite(Actor, Case) and queue in the Case Actor's outbox.

    Uses ``trigger_activity_factory.invite_actor_to_case()`` with
    ``actor=self.actor_id`` (expected to be the Case Actor URI),
    ``to=[invitee_id]``, and ``cc=[case_actor_id]`` when ``case_actor_id``
    is provided so ASGI self-delivery routes the Invite to the CaseActor's
    own inbox for canonical ledger archival (CLP-10-001).  An optional
    ``attributed_to`` carries the original requesting actor when the invite
    is sent from the Case Actor identity (PCR-08-007).

    Reads ``suggested_roles`` from the blackboard (written by
    ``EvaluateDefaultRolesNode`` or the Case Owner's Accept response) and
    embeds the roles in the Invite (CM-17-003).

    Reads the ``VulnerabilityCase`` from the DataLayer and passes it as
    ``target`` to ``TriggerActivityPort.invite_actor_to_case()``.  The adapter
    and factory project it to an enriched ``VulnerabilityCaseStub`` — including
    ``end_time`` when ``em_state == EM.ACTIVE`` — without violating the
    core→wire import boundary (ARCH-01-001, CM-17-002).
    """

    def __init__(
        self,
        invitee_id: str,
        case_id: str,
        case_actor_id: str | None = None,
        attributed_to: str | None = None,
        captured: dict | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.invitee_id = invitee_id
        self.case_id = case_id
        self.case_actor_id = case_actor_id
        self.attributed_to = attributed_to
        self._captured = captured

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="suggested_roles", access=py_trees.common.Access.READ
        )

    def _read_suggested_roles(self) -> list[str] | None:
        try:
            roles = self.blackboard.get("suggested_roles")
            if isinstance(roles, list):
                return serialize_roles(roles)
        except KeyError:
            pass
        return None

    def _emit(self, factory: Any) -> tuple[str, dict]:
        """Build the Invite activity and commit the ledger correlation marker."""
        cc = [self.case_actor_id] if self.case_actor_id else None
        roles = self._read_suggested_roles()
        if roles is not None and not roles:
            raise ValueError(
                f"suggested_roles for actor '{self.invitee_id}' is empty"
                " — cannot emit Invite(Actor, Case) without at least one role"
            )
        # CM-17-002: pass the full case object so the adapter+factory can
        # project it to an enriched stub (with end_time) when em_state==ACTIVE.
        assert self.datalayer is not None and self.actor_id is not None
        case = self.datalayer.read(self.case_id)
        activity_id, activity_dict = factory.invite_actor_to_case(
            invitee_id=self.invitee_id,
            case_id=self.case_id,
            actor=self.actor_id,
            to=[self.invitee_id],
            cc=cc,
            attributed_to=self.attributed_to,
            roles=roles,
            target=case if isinstance(case, VulnerabilityCase) else None,
        )
        # Commit a local correlation marker first so duplicate checks work
        # on retry even if the outbox write below fails (CM-16-009/AC-7a).
        # disposition="rejected" bypasses canonical-payload validation since
        # Invite(Actor, Case) is not a canonical ledger event type.
        commit_tree = create_commit_log_entry_tree(
            case_id=self.case_id,
            object_id=self.invitee_id,
            event_type="invite_actor_to_case",
            disposition="rejected",
        )
        result = BTBridge(
            datalayer=cast(CaseOutboxPersistence, self.datalayer)
        ).execute_with_setup(tree=commit_tree, actor_id=self.actor_id)
        if result.status != Status.SUCCESS:
            raise RuntimeError(
                f"ledger correlation commit failed for"
                f" invite_actor_to_case/{self.invitee_id}"
            )
        return activity_id, activity_dict

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        if (f := self._require_factory()) is not None:
            self.logger.error(self.feedback_message)
            return f

        try:
            activity_id, activity_dict = self._emit(
                self.trigger_activity_factory
            )
            cast(CaseOutboxPersistence, self.datalayer).record_outbox_item(
                self.actor_id, activity_id  # type: ignore[arg-type]
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

    def _emit(self) -> tuple[str, dict]:
        assert self.trigger_activity_factory is not None
        assert self.actor_id is not None
        return self.trigger_activity_factory.accept_case_invite(
            invite_id=self.invite_id,
            actor=self.actor_id,
        )

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        if (f := self._require_factory()) is not None:
            self.logger.error(self.feedback_message)
            return f

        try:
            activity_id, activity_dict = self._emit()
            cast(CaseOutboxPersistence, self.datalayer).record_outbox_item(
                self.actor_id, activity_id  # type: ignore[arg-type]
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


class ProposeCaseToActorNode(DataLayerAction):
    """Send ``Create(as_CaseProposal)`` to the registered case-actor service.

    Reads ``case_id`` and ``case_actor_id`` from the blackboard (written by
    ``CreateCaseActorNode`` / ``ResolveCaseActorUrlsNode``), resolves the
    linked ``VulnerabilityReport`` ID from the case record, and delegates
    activity construction and persistence to
    ``trigger_activity_factory.create_case_proposal()`` so the wire layer
    handles serialization (CP-01-004: report must be embedded inline, not
    as a URI reference).

    This node MUST run AFTER ``CreateCaseActorNode`` succeeds, because the
    case-actor identity must exist in the DataLayer before the proposal can
    be addressed to it (CP-04-002).

    Returns FAILURE when:

    - DataLayer, ``actor_id``, or ``trigger_activity_factory`` is unavailable.
    - ``case_id`` or ``case_actor_id`` is missing from the blackboard.
    - The case is not found in the DataLayer.
    - No ``VulnerabilityReport`` is linked to the case (CP-01-004).
    - ``trigger_activity_factory.create_case_proposal()`` raises an exception.

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

    def _get_report_id(self, case_id: str) -> str | None:
        """Return the first VulnerabilityReport URI linked to *case_id*.

        Returns the report ID string on success, or ``None`` after setting
        ``feedback_message`` on any error.
        """
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            return None

        case = self.datalayer.read(case_id)
        if not isinstance(case, VulnerabilityCase):
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

        raw = case.vulnerability_reports[0]
        # vulnerability_reports entries may be string URIs or ref objects.
        if isinstance(raw, str):
            return raw
        return str(getattr(raw, "id_", raw))

    def _build_proposal(self, case_id: str, case_actor_id: str) -> str | None:
        """Call factory and enqueue outbox item; return activity_id or None."""
        report_id = self._get_report_id(case_id)
        if report_id is None:
            return None
        assert self.trigger_activity_factory is not None
        assert self.actor_id is not None
        try:
            activity_id, _ = (
                self.trigger_activity_factory.create_case_proposal(
                    actor=self.actor_id,
                    report_id=report_id,
                    case_actor_id=case_actor_id,
                )
            )
        except Exception as exc:
            self.feedback_message = f"create_case_proposal failed: {exc}"
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return None
        cast(CaseOutboxPersistence, self.datalayer).record_outbox_item(
            self.actor_id, activity_id
        )
        return activity_id

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        if (f := self._require_factory()) is not None:
            self.logger.error("%s: %s", self.name, self.feedback_message)
            return f

        ids = self._read_blackboard_ids()
        if ids is None:
            return Status.FAILURE
        case_id, case_actor_id = ids

        activity_id = self._build_proposal(case_id, case_actor_id)
        if activity_id is None:
            return Status.FAILURE

        self.logger.info(
            "%s: Queued Create(as_CaseProposal) '%s' to outbox"
            " for case-actor '%s' (case '%s')",
            self.name,
            activity_id,
            case_actor_id,
            case_id,
        )
        return Status.SUCCESS


class EvaluateDefaultRolesNode(py_trees.behaviour.Behaviour):
    """Assign default CVD roles for a suggested actor (CM-16-003).

    ADR-0024 Evaluator shape.  Writes ``suggested_roles_{id_segment}``
    (namespaced by ``recommendation_id``, BTND-03-004) to the blackboard.
    Prototype writes ``[CVDRole.VENDOR]``.  Subclasses may override
    ``_compute_roles()``; an empty return produces ``FAILURE`` (AC-1).
    """

    logger: logging.Logger  # type: ignore[assignment]

    def __init__(
        self,
        suggested_actor_id: str,
        case_id: str,
        recommendation_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.suggested_actor_id = suggested_actor_id
        self.case_id = case_id
        self.recommendation_id = recommendation_id
        self.logger = logging.getLogger(  # type: ignore[assignment]
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard = self.attach_blackboard_client(name=self.name)
        id_segment = self.recommendation_id.split("/")[-1]
        self.blackboard_key = f"suggested_roles_{id_segment}"
        self.blackboard.register_key(
            key=self.blackboard_key, access=py_trees.common.Access.WRITE
        )

    def _compute_roles(self) -> list[CVDRole]:
        """Return roles for the suggested actor; override for custom policy."""
        return [CVDRole.VENDOR]

    def update(self) -> Status:
        roles = self._compute_roles()
        if not roles:
            self.feedback_message = (
                f"{self.name}: _compute_roles() returned an empty list "
                f"for actor '{self.suggested_actor_id}' — cannot assign roles"
            )
            self.logger.error(self.feedback_message)
            return Status.FAILURE
        setattr(self.blackboard, self.blackboard_key, roles)
        self.logger.debug(
            "%s: assigned roles %s for actor '%s' in case '%s'",
            self.name,
            roles,
            self.suggested_actor_id,
            self.case_id,
        )
        return Status.SUCCESS
