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

from vultron.config import get_config
from vultron.core.behaviors.case.nodes.case_setup import _derive_case_slug
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerCondition,
    DataLayerConditionWithPorts,
)

from vultron.config.actor import ActorConfig
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_actor import CaseActor as VultronCaseActor
from vultron.core.models.report_case_link import VultronReportCaseLink
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


class CheckCaseAlreadyExists(DataLayerConditionWithPorts):
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
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
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


class CheckCaseExistsForReport(DataLayerConditionWithPorts):
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
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
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
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

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


class CheckPendingProposalExistsForReport(DataLayerConditionWithPorts):
    """Return SUCCESS when a pending ``VultronReportCaseLink`` exists for the report.

    Used as the idempotency guard in the slimmed vendor tree (ADR-0041).
    A link is "pending" when ``case_id is None`` and
    ``proposal_rejected is False``.

    Per specs/case-proposal.yaml CP-04-001.
    """

    def __init__(self, report_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.report_id = report_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        try:
            link_id = VultronReportCaseLink.build_id(self.report_id)
            link = self.datalayer.read(link_id)
            if not isinstance(link, VultronReportCaseLink):
                self.logger.debug(
                    "%s: no ReportCaseLink found for report '%s'",
                    self.name,
                    self.report_id,
                )
                return Status.FAILURE
            if link.case_id is None and not link.proposal_rejected:
                self.logger.info(
                    "%s: pending proposal already exists for report '%s'"
                    " — skipping (idempotent)",
                    self.name,
                    self.report_id,
                )
                return Status.SUCCESS
            self.logger.debug(
                "%s: ReportCaseLink for report '%s' is not pending"
                " (case_id=%r, proposal_rejected=%r)",
                self.name,
                self.report_id,
                link.case_id,
                link.proposal_rejected,
            )
            return Status.FAILURE
        except Exception as e:
            self.logger.error(
                "%s: error checking pending proposal for report '%s': %s",
                self.name,
                self.report_id,
                e,
            )
            return Status.FAILURE


class WritePendingReportCaseLinkNode(DataLayerActionWithPorts):
    """Write a pending ``VultronReportCaseLink`` for the given report (ADR-0041).

    Creates or updates the link with ``case_id=None`` and sets
    ``trusted_case_creator_id`` to the deterministically derived CaseActor ID
    so that ``_find_report_case_link`` can match the incoming
    ``Create(VulnerabilityCase)`` sender when the CaseActor responds.

    The CaseActor ID is derived as
    ``{case_actor_service_url}/actors/case-actor-{slug}``
    where *slug* is ``_derive_case_slug(report_id)`` — the same formula used
    by ``ResolveCaseActorUrlsNode`` (CP-08-002).  Returns ``FAILURE`` when
    ``case_actor_service_url`` is not configured.

    Always returns ``SUCCESS`` so the enclosing ``Sequence`` continues to
    ``ProposeCaseToActorNode``.

    Per specs/case-proposal.yaml CP-04-001 and ADR-0041.
    """

    def __init__(self, report_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.report_id = report_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        cfg = get_config().actor
        if cfg.case_actor_service_url is None:
            self.feedback_message = (
                f"{self.name}: case_actor_service_url not configured"
                " — cannot derive trusted_case_creator_id"
            )
            self.logger.error(self.feedback_message)
            return Status.FAILURE

        base_url = str(cfg.case_actor_service_url).rstrip("/")
        case_slug = _derive_case_slug(self.report_id)
        case_actor_id = f"{base_url}/actors/case-actor-{case_slug}"

        # Ensure the CaseActor service object exists so its inbox accepts
        # Create(as_CaseProposal) delivery (ADR-0041, CP-04-002).
        self._ensure_case_actor(case_actor_id)

        link_id = VultronReportCaseLink.build_id(self.report_id)
        existing = self.datalayer.read(link_id)
        if isinstance(existing, VultronReportCaseLink):
            if existing.proposal_rejected:
                # Retry path: clear the rejection flag so ProposeReportCaseToActorNode
                # can send a new proposal and downstream uses see a clean pending state.
                existing.proposal_rejected = False
                self.datalayer.save(existing)
                self.logger.info(
                    "%s: cleared proposal_rejected on existing ReportCaseLink"
                    " for report '%s' (retry)",
                    self.name,
                    self.report_id,
                )
            else:
                self.logger.debug(
                    "%s: ReportCaseLink already exists for report '%s'"
                    " — skipping write",
                    self.name,
                    self.report_id,
                )
            return Status.SUCCESS

        link = VultronReportCaseLink(
            report_id=self.report_id,
            trusted_case_creator_id=case_actor_id,
        )
        self.datalayer.create(link)
        self.logger.info(
            "%s: wrote pending ReportCaseLink for report '%s'"
            " (trusted_case_creator_id='%s')",
            self.name,
            self.report_id,
            case_actor_id,
        )
        return Status.SUCCESS

    def _ensure_case_actor(self, case_actor_id: str) -> None:
        """Create the VultronCaseActor service object if it does not exist.

        The actor must exist in the DataLayer before Create(as_CaseProposal) is
        delivered, otherwise the inbox handler returns 404 (CP-04-002).
        """
        assert self.datalayer is not None
        if self.datalayer.read(case_actor_id) is not None:
            return
        case_actor = VultronCaseActor(
            id_=case_actor_id,
            name=f"CaseActor for report {self.report_id}",
        )
        try:
            self.datalayer.create(case_actor)
        except ValueError:
            pass  # already exists (race or duplicate); not an error
