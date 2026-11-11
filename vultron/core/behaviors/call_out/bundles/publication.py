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
- ``draft_advisory_artifact_factory``       — DraftAdvisoryArtifact        (p=0.90) → AlwaysSucceed
- ``review_advisory_draft_factory``         — ReviewAdvisoryDraft          (p=1.0) → AlwaysSucceed
- ``revise_advisory_draft_factory``         — ReviseAdvisoryDraft          (p=0.90) → AlwaysSucceed
- ``submit_advisory_artifact_factory``      — SubmitAdvisoryArtifact       (p=0.90) → AlwaysSucceed

Every default binds to its capability's core declaration
(:func:`~vultron.core.behaviors.call_out.nodes.always_succeed_as`), so its
*yes* writes the declared output ports (BT-23-013).  For
``prioritize_publication_intents_factory`` that is the default
:class:`~vultron.core.behaviors.report.publication_intent.PublicationIntentDecision`
(publish the fix and the report, withhold the exploit), which the
``ShouldPublish*`` gates read.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from vultron.core.behaviors.call_out.bundles.base import CallOutBundle
from vultron.core.behaviors.call_out.capabilities.report_management.publication.advisory import (
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
        default=always_succeed_as(DraftAdvisoryArtifactCapability)  # type: ignore[assignment]
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

Every factory is an :class:`~vultron.core.behaviors.call_out.nodes.AlwaysSucceed`
bound to its capability, so each *yes* writes the declared outputs
(BT-23-013); ``prioritize_publication_intents_factory`` writes the standard
CVD :class:`~vultron.core.behaviors.report.publication_intent.PublicationIntentDecision`.
"""

__all__ = [
    "PublicationCallOutBundle",
    "PUBLICATION_DETERMINISTIC",
]
