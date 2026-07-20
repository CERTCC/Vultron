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
Condition nodes for case management behavior trees.

Provides idempotency guard conditions for the create_case workflow.
Per specs/idempotency.yaml ID-04-004.

Note: ``ValidateCaseObject`` was removed in issue #716.  ``VultronBase.id_``
is typed ``NonEmptyString`` with a ``default_factory=_new_urn``, so Pydantic
rejects invalid ``id_`` values at construction time (ARCH-10-001 fail-fast
domain objects).  A factory function that calls ``case_obj.id_`` before
constructing the tree would raise ``AttributeError`` before any BT node runs,
making a runtime validation node unreachable and redundant.
"""

import logging
from typing import Any

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerCondition
from vultron.config.actor import ActorConfig
from vultron.core.models.case import VulnerabilityCase
from vultron.core.use_cases._helpers import _resolve_case_manager_id


class CheckAutoCaseCreationEnabledNode(py_trees.behaviour.Behaviour):
    """Gate case creation on the actor's ``auto_create_case`` policy.

    Returns ``SUCCESS`` when the local actor's :class:`ActorConfig` has
    ``auto_create_case`` set (the ADR-0015 Option 4 default), allowing the
    downstream case-creation subtree to run.  Returns ``FAILURE`` when
    ``auto_create_case`` is ``False``, so the enclosing ``Sequence`` exits
    without creating a ``VulnerabilityCase`` — enabling the pre-case ACK
    (``Read(Offer(Report))``) protocol path (CM-15-001, ADR-0015 Option 3).

    The policy is supplied as a constructor argument rather than read from
    the blackboard so it travels with the tree the same way
    ``default_case_roles`` does (see ``CreateCaseOwnerParticipant``).  When no
    ``ActorConfig`` is supplied the node defaults to enabled, preserving the
    historical always-create behavior for callers that predate the flag.

    Per specs/case-management.yaml CM-15-001.
    """

    # Declare the managed logger type so subclass log calls are type-checked
    # against the stdlib logging.Logger API (not py_trees.logging.Logger).
    logger: logging.Logger  # type: ignore[assignment]

    def __init__(
        self,
        actor_config: ActorConfig | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.logger = logging.getLogger(  # type: ignore[assignment]
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )
        self.actor_config = actor_config

    def update(self) -> Status:
        auto_create = (
            self.actor_config.auto_create_case
            if self.actor_config is not None
            else True
        )
        if auto_create:
            self.logger.debug(
                "%s: auto_create_case enabled — proceeding with case creation",
                self.name,
            )
            return Status.SUCCESS

        self.logger.info(
            "%s: auto_create_case disabled — deferring case creation "
            "(pre-case ACK path)",
            self.name,
        )
        return Status.FAILURE


class CheckCaseAlreadyExists(DataLayerCondition):
    """
    Check if a VulnerabilityCase already exists in DataLayer.

    Returns SUCCESS if the case already exists (idempotency early exit).
    Returns FAILURE if the case does not exist (proceed with creation).

    Per specs/idempotency.yaml ID-04-004.
    """

    def __init__(self, case_id: str, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error(f"{self.name}: DataLayer not available")
            return Status.FAILURE

        try:
            existing = self.datalayer.read(self.case_id)
            if existing is None:
                self.logger.debug(
                    f"{self.name}: Case {self.case_id} not found, proceeding"
                )
                return Status.FAILURE

            # A case record that exists but has no participants was
            # pre-stored by the inbox endpoint as a dehydrated reference.
            # It still needs full initialisation (participant creation,
            # CaseActor setup, etc.), so return FAILURE to let the
            # CreateCaseFlow run.
            participants = getattr(existing, "case_participants", None) or []
            if not participants:
                self.logger.debug(
                    f"{self.name}: Case {self.case_id} exists but has no"
                    " participants — proceeding with initialisation"
                )
                return Status.FAILURE

            self.logger.info(
                f"{self.name}: Case {self.case_id} already exists"
                " — skipping creation (idempotent)"
            )
            return Status.SUCCESS

        except Exception as e:
            self.logger.error(
                f"{self.name}: Error checking case existence: {e}"
            )
            return Status.FAILURE


class CheckCaseExistsForReport(DataLayerCondition):
    """
    Check if a VulnerabilityCase already exists for the given report.

    Uses ``find_case_by_report_id`` to check whether a case linked to the
    report already exists with participants. Returns SUCCESS if so (idempotency
    early exit), FAILURE otherwise.

    Per specs/idempotency.yaml ID-04-004.
    """

    def __init__(self, report_id: str, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.report_id = report_id

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error(f"{self.name}: DataLayer not available")
            return Status.FAILURE

        try:
            existing = self.datalayer.find_case_by_report_id(self.report_id)
            if existing is None:
                self.logger.debug(
                    f"{self.name}: No case found for report {self.report_id}"
                )
                return Status.FAILURE

            # A case record that exists but has no participants was
            # pre-stored by the inbox endpoint as a dehydrated reference.
            # It still needs full initialisation, so return FAILURE.
            participants = getattr(existing, "case_participants", None) or []
            if not participants:
                self.logger.debug(
                    f"{self.name}: Case for report {self.report_id} exists"
                    " but has no participants — proceeding with initialisation"
                )
                return Status.FAILURE

            self.logger.info(
                "%s: Case %s already exists for report %s"
                " — skipping (idempotent)",
                self.name,
                existing.id_,
                self.report_id,
            )
            return Status.SUCCESS

        except Exception as e:
            self.logger.error(
                f"{self.name}: Error checking case existence: {e}"
            )
            return Status.FAILURE


class CheckIsCaseManagerNode(DataLayerCondition):
    """Check whether the executing actor is the case's CASE_MANAGER.

    Reads ``case_id`` and ``actor_id`` from the blackboard, resolves the
    case's CASE_MANAGER participant via ``_resolve_case_manager_id``, and
    returns ``SUCCESS`` only when ``actor_id`` matches that participant's
    ``attributed_to`` actor ID.
    """

    def __init__(
        self, case_id: str | None = None, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_id", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                f"{self.name}: DataLayer or actor_id not available"
            )
            return Status.FAILURE

        try:
            case_id = self._case_id or self.blackboard.get("case_id")
        except KeyError:
            case_id = self._case_id

        if not case_id:
            self.logger.debug(
                f"{self.name}: no case_id available — cannot check"
                " CASE_MANAGER role"
            )
            return Status.FAILURE

        case = self.datalayer.read(case_id)
        if case is None:
            self.logger.warning(
                f"{self.name}: case '{case_id}' not found in DataLayer"
            )
            return Status.FAILURE
        if not isinstance(case, VulnerabilityCase):
            self.logger.warning(
                f"{self.name}: object '{case_id}' is not a VulnerabilityCase"
            )
            return Status.FAILURE

        manager_id = _resolve_case_manager_id(case, self.datalayer)
        if manager_id is None:
            self.logger.debug(
                f"{self.name}: no CASE_MANAGER found for case '{case_id}'"
            )
            return Status.FAILURE

        if manager_id == self.actor_id:
            self.logger.debug(
                f"{self.name}: actor '{self.actor_id}' is CASE_MANAGER for"
                f" case '{case_id}'"
            )
            return Status.SUCCESS

        self.logger.debug(
            "%s: actor '%s' is not CASE_MANAGER for case '%s' (manager=%s)",
            self.name,
            self.actor_id,
            case_id,
            manager_id,
        )
        return Status.FAILURE
