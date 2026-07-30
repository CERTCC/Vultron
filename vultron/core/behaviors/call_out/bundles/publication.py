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

- ``prioritize_publication_intents_factory`` — PrioritizePublicationIntents (p=1.0) → _DeterministicPrioritizePublicationIntents
- ``prepare_exploit_factory``               — PrepareExploit               (p=0.90) → AlwaysSucceed
- ``prepare_fix_factory``                   — PrepareFix                   (p=0.90) → AlwaysSucceed
- ``prepare_report_factory``                — PrepareReport                (p=0.90) → AlwaysSucceed
- ``draft_advisory_artifact_factory``       — DraftAdvisoryArtifact        (p=0.90) → AlwaysSucceed
- ``review_advisory_draft_factory``         — ReviewAdvisoryDraft          (p=1.0) → AlwaysSucceed
- ``revise_advisory_draft_factory``         — ReviseAdvisoryDraft          (p=0.90) → AlwaysSucceed
- ``submit_advisory_artifact_factory``      — SubmitAdvisoryArtifact       (p=0.90) → AlwaysSucceed
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import py_trees
from py_trees.common import Access, Status

from vultron.core.behaviors.call_out.nodes import AlwaysSucceed
from vultron.core.behaviors.call_out.protocol import CallOutBackendFactory


def _always_succeed(name: str) -> py_trees.behaviour.Behaviour:
    return AlwaysSucceed(name)


class _DeterministicPrioritizePublicationIntents(AlwaysSucceed):
    """DETERMINISTIC PrioritizePublicationIntents: always succeeds and writes the default intent record.

    Writes :class:`~vultron.core.behaviors.report.publication_tree.PublicationIntentDecision`
    (``publish_fix=True``, ``publish_report=True``, ``publish_exploit=False``) to
    :data:`~vultron.core.behaviors.report.publication_tree.INTENT_DECISION_KEY`
    on SUCCESS so that the ``ShouldPublish*`` gate nodes can read it.

    This is the core-layer DETERMINISTIC backend for the
    ``prioritize_publication_intents_factory`` call-out point (BT-23-002). It
    encodes the standard CVD outcome: publish the fix and advisory, withhold the
    exploit.  A real Evaluator backend overrides these per case policy via
    ``call_out=PUBLICATION_STOCHASTIC`` (or a custom :class:`PublicationCallOutBundle`).

    Uses lazy imports to avoid a circular import with
    ``vultron.core.behaviors.report.publication_tree`` (which imports this
    module's :data:`PUBLICATION_DETERMINISTIC` singleton).
    """

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        from vultron.core.behaviors.report.publication_tree import (
            INTENT_DECISION_KEY,
        )

        self._intent_key = INTENT_DECISION_KEY
        self._intent_bb = self.attach_blackboard_client(
            name=f"{self.__class__.__name__}_writer"
        )
        self._intent_bb.register_key(self._intent_key, Access.WRITE)

    def update(self) -> Status:
        status = super().update()
        if status == Status.SUCCESS and hasattr(self, "_intent_bb"):
            from vultron.core.behaviors.report.publication_tree import (
                PublicationIntentDecision,
            )

            setattr(
                self._intent_bb, self._intent_key, PublicationIntentDecision()
            )
        return status


def _deterministic_prioritize_intents(
    name: str,
) -> py_trees.behaviour.Behaviour:
    return _DeterministicPrioritizePublicationIntents(name)


@dataclass(frozen=True)
class PublicationCallOutBundle:
    """Call-out backend bundle for the publication pipeline domain (BT-23-003).

    Fields map to the corresponding factory parameters on
    :func:`~vultron.core.behaviors.report.publication_tree.create_publication_tree`
    and
    :func:`~vultron.core.behaviors.report.publish_artifact_tree.create_publish_artifact_tree`.
    """

    prioritize_publication_intents_factory: CallOutBackendFactory = field(
        default=_deterministic_prioritize_intents  # type: ignore[assignment]
    )
    prepare_exploit_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    prepare_fix_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    prepare_report_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    draft_advisory_artifact_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    review_advisory_draft_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    revise_advisory_draft_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    submit_advisory_artifact_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )


PUBLICATION_DETERMINISTIC = PublicationCallOutBundle()
"""Deterministic bundle: happy-path default for production use (BT-23-001, BT-23-002).

``prioritize_publication_intents_factory`` uses
:class:`_DeterministicPrioritizePublicationIntents` which returns SUCCESS and
writes the standard CVD default intent record
(:class:`~vultron.core.behaviors.report.publication_tree.PublicationIntentDecision`)
to the blackboard. All other factories use :class:`~vultron.core.behaviors.call_out.nodes.AlwaysSucceed`.
"""

__all__ = [
    "PublicationCallOutBundle",
    "PUBLICATION_DETERMINISTIC",
    "_DeterministicPrioritizePublicationIntents",
]
