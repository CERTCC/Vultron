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
"""Call-out bundle for the publication pipeline domain (BT-23-003, BT-23-005).

Provides :class:`PublicationCallOutBundle` and the pre-built core DETERMINISTIC
singleton :data:`PUBLICATION_DETERMINISTIC`.  The matching STOCHASTIC singleton
lives in the simulation layer
(:data:`vultron.demo.fuzzer.bundles.publication.PUBLICATION_STOCHASTIC`).

This bundle covers both
:func:`~vultron.core.behaviors.report.publication_tree.create_publication_tree`
and
:func:`~vultron.core.behaviors.report.publish_artifact_tree.create_publish_artifact_tree`.

Ceiling/floor mapping (BT-23-002):

- ``prioritize_publication_intents_factory`` — PrioritizePublicationIntents (p=1.0) → AlwaysSucceed
- ``prepare_exploit_factory``               — PrepareExploit               (p=0.90) → AlwaysSucceed
- ``prepare_fix_factory``                   — PrepareFix                   (p=0.90) → AlwaysSucceed
- ``prepare_report_factory``                — PrepareReport                (p=0.90) → AlwaysSucceed
- ``draft_advisory_artifact_factory``       — DraftAdvisoryArtifact        (p=0.90) → DraftAdvisoryArtifactByProjection
- ``review_advisory_draft_factory``         — ReviewAdvisoryDraft          (p=1.0) → AlwaysSucceed
- ``revise_advisory_draft_factory``         — ReviseAdvisoryDraft          (p=0.90) → AlwaysSucceed
- ``submit_advisory_artifact_factory``      — SubmitAdvisoryArtifact       (p=0.90) → AlwaysSucceed

Every other default binds to its capability's core declaration
(:func:`~vultron.core.behaviors.call_out.nodes.always_succeed_as`), so its
*yes* writes the declared output ports (BT-23-013).  The draft default,
:class:`DraftAdvisoryArtifactByProjection`, writes a real draft: the CSAF
projection of the case by the public profile (ADR-0219), rendered through
the ``case_projection_port`` the tree's runner places on the blackboard.  For
``prioritize_publication_intents_factory`` that is the default
:class:`~vultron.core.behaviors.report.publication_intent.PublicationIntentDecision`
(publish the fix and the report, withhold the exploit), which the
``ShouldPublish*`` gates read.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import cast

import py_trees
from py_trees.common import Access

from vultron.core.behaviors.call_out.answer import CallOutAnswer
from vultron.core.behaviors.call_out.bundles.base import CallOutBundle
from vultron.core.behaviors.call_out.capabilities.report_management.publication.advisory import (
    DRAFT_CASE_ID_KEY,
    DraftAdvisoryArtifactCapability,
    ReviewAdvisoryDraftCapability,
    ReviseAdvisoryDraftCapability,
    SubmitAdvisoryArtifactCapability,
)
from vultron.core.behaviors.call_out.capabilities.report_management.publication.intents import (
    PrepareExploitCapability,
    PrepareFixCapability,
    PrepareReportCapability,
    PrioritizePublicationIntentsCapability,
)
from vultron.core.behaviors.call_out.nodes import (
    always_succeed_as,
)
from vultron.core.behaviors.call_out.protocol import CallOutBackendFactory
from vultron.core.behaviors.helpers.messages import (
    DATALAYER_OR_ACTOR_UNAVAILABLE,
)
from vultron.core.behaviors.report.advisory_review import DRAFT_ARTIFACT_KEY
from vultron.core.models.case_projection import PublicationStatus
from vultron.core.models.case_projection_profile import PUBLIC_PROFILE
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.case_projection import (
    PROJECTION_FAILURES,
    project_case,
    require_projection_port,
)
from vultron.errors import VultronWiringError

#: The blackboard key the runner places the projection port under.
CASE_PROJECTION_PORT_KEY = "case_projection_port"

#: The run keys the draft backend reads beside its input port.
_RUN_KEYS = ("datalayer", "actor_id", CASE_PROJECTION_PORT_KEY)


class DraftAdvisoryArtifactByProjection(DraftAdvisoryArtifactCapability):
    """DETERMINISTIC DraftAdvisoryArtifact: the case's public projection.

    Reads the case id from its input port, and the store, the executing
    actor and the ``case_projection_port`` from the run's blackboard
    (BTBridge places them).  It cuts the case with the public profile and
    renders it with ``tracking.status`` ``final`` (ADR-0219), through
    :func:`~vultron.core.services.case_projection.project_case`, and answers
    *yes* with the document's JSON text as the draft (BT-23-013).

    A missing port, store or actor is a wiring fault and raises
    :class:`~vultron.errors.VultronWiringError`: no fallback draft is made.
    A replica that cannot be projected, such as one that does not hold the
    case, is *error*: the backend could not draft, it did not decline
    (ADR-0183).
    """

    #: Read-only rate interface parity with the simulation backends.
    success_rate: float = 1.0

    def __init__(self, name: str = "") -> None:
        super().__init__(name)
        self._run = self.attach_blackboard_client(
            name=f"{type(self).__name__}_{self.name}_run"
        )
        for key in _RUN_KEYS:
            self._run.register_key(key, Access.READ)

    def _run_value(self, key: str) -> object | None:
        try:
            value: object = self._run.get(key)
        except KeyError:
            return None
        return value

    def answer(self) -> CallOutAnswer:
        """Answer *yes* with the case's public projection, or *error*."""
        case_id = str(self.get_input(DRAFT_CASE_ID_KEY))
        port = require_projection_port(
            self._run_value(CASE_PROJECTION_PORT_KEY)
        )
        dl = self._run_value("datalayer")
        actor_id = self._run_value("actor_id")
        if dl is None or not isinstance(actor_id, str) or not actor_id:
            raise VultronWiringError(
                f"{self.name}: {DATALAYER_OR_ACTOR_UNAVAILABLE}"
            )
        try:
            document = project_case(
                cast(CasePersistence, dl),
                case_id,
                actor_id,
                PUBLIC_PROFILE,
                PublicationStatus.FINAL,
                port,
            )
        except PROJECTION_FAILURES as exc:
            return CallOutAnswer.error(
                f"drafting the public projection of case '{case_id}'"
                f" failed: {exc}"
            )
        return CallOutAnswer.yes({DRAFT_ARTIFACT_KEY: json.dumps(document)})


def _draft_by_projection(name: str) -> py_trees.behaviour.Behaviour:
    return DraftAdvisoryArtifactByProjection(name)


@dataclass(frozen=True)
class PublicationCallOutBundle(CallOutBundle):
    """Call-out backend bundle for the publication pipeline domain (BT-23-003).

    Fields map to the corresponding factory parameters on
    :func:`~vultron.core.behaviors.report.publication_tree.create_publication_tree`
    and
    :func:`~vultron.core.behaviors.report.publish_artifact_tree.create_publish_artifact_tree`.
    """

    prioritize_publication_intents_factory: CallOutBackendFactory = field(
        default=always_succeed_as(PrioritizePublicationIntentsCapability)  # type: ignore[assignment]
    )
    prepare_exploit_factory: CallOutBackendFactory = field(
        default=always_succeed_as(PrepareExploitCapability)  # type: ignore[assignment]
    )
    prepare_fix_factory: CallOutBackendFactory = field(
        default=always_succeed_as(PrepareFixCapability)  # type: ignore[assignment]
    )
    prepare_report_factory: CallOutBackendFactory = field(
        default=always_succeed_as(PrepareReportCapability)  # type: ignore[assignment]
    )
    draft_advisory_artifact_factory: CallOutBackendFactory = field(
        default=_draft_by_projection  # type: ignore[assignment]
    )
    review_advisory_draft_factory: CallOutBackendFactory = field(
        default=always_succeed_as(ReviewAdvisoryDraftCapability)  # type: ignore[assignment]
    )
    revise_advisory_draft_factory: CallOutBackendFactory = field(
        default=always_succeed_as(ReviseAdvisoryDraftCapability)  # type: ignore[assignment]
    )
    submit_advisory_artifact_factory: CallOutBackendFactory = field(
        default=always_succeed_as(SubmitAdvisoryArtifactCapability)  # type: ignore[assignment]
    )


PUBLICATION_DETERMINISTIC = PublicationCallOutBundle()
"""Deterministic bundle: happy-path default for production use (BT-23-001, BT-23-002).

Every factory but the draft's is an
:class:`~vultron.core.behaviors.call_out.nodes.AlwaysSucceed` bound to its
capability, so each *yes* writes the declared outputs (BT-23-013); the draft
is :class:`DraftAdvisoryArtifactByProjection`;
``prioritize_publication_intents_factory`` writes the standard
CVD :class:`~vultron.core.behaviors.report.publication_intent.PublicationIntentDecision`.
"""

__all__ = [
    "CASE_PROJECTION_PORT_KEY",
    "DraftAdvisoryArtifactByProjection",
    "PublicationCallOutBundle",
    "PUBLICATION_DETERMINISTIC",
]
