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

Provides :class:`PublicationCallOutBundle` plus the pre-built singletons
:data:`PUBLICATION_DETERMINISTIC` and :data:`PUBLICATION_STOCHASTIC`.

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
"""

from __future__ import annotations

from dataclasses import dataclass, field

import py_trees

from vultron.core.behaviors.call_out_point import CallOutBackendFactory


def _always_succeed(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.base import AlwaysSucceed

    return AlwaysSucceed(name)


def _stochastic_prioritize_intents(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.publication import (
        PrioritizePublicationIntents,
    )

    return PrioritizePublicationIntents(name)


def _stochastic_prepare_exploit(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.publication import (
        PrepareExploit,
    )

    return PrepareExploit(name)


def _stochastic_prepare_fix(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.publication import PrepareFix

    return PrepareFix(name)


def _stochastic_prepare_report(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.publication import PrepareReport

    return PrepareReport(name)


def _stochastic_draft_advisory(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.publication import (
        DraftAdvisoryArtifact,
    )

    return DraftAdvisoryArtifact(name)


def _stochastic_review_advisory(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.publication import (
        ReviewAdvisoryDraft,
    )

    return ReviewAdvisoryDraft(name)


def _stochastic_revise_advisory(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.publication import (
        ReviseAdvisoryDraft,
    )

    return ReviseAdvisoryDraft(name)


def _stochastic_submit_advisory(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.publication import (
        SubmitAdvisoryArtifact,
    )

    return SubmitAdvisoryArtifact(name)


@dataclass(frozen=True)
class PublicationCallOutBundle:
    """Call-out backend bundle for the publication pipeline domain (BT-23-003).

    Fields map to the corresponding factory parameters on
    :func:`~vultron.core.behaviors.report.publication_tree.create_publication_tree`
    and
    :func:`~vultron.core.behaviors.report.publish_artifact_tree.create_publish_artifact_tree`.
    """

    prioritize_publication_intents_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
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
"""Deterministic bundle: all nodes use AlwaysSucceed (BT-23-001, BT-23-002)."""

PUBLICATION_STOCHASTIC = PublicationCallOutBundle(
    prioritize_publication_intents_factory=_stochastic_prioritize_intents,  # type: ignore[arg-type]
    prepare_exploit_factory=_stochastic_prepare_exploit,  # type: ignore[arg-type]
    prepare_fix_factory=_stochastic_prepare_fix,  # type: ignore[arg-type]
    prepare_report_factory=_stochastic_prepare_report,  # type: ignore[arg-type]
    draft_advisory_artifact_factory=_stochastic_draft_advisory,  # type: ignore[arg-type]
    review_advisory_draft_factory=_stochastic_review_advisory,  # type: ignore[arg-type]
    revise_advisory_draft_factory=_stochastic_revise_advisory,  # type: ignore[arg-type]
    submit_advisory_artifact_factory=_stochastic_submit_advisory,  # type: ignore[arg-type]
)
"""Stochastic bundle: all nodes use probabilistic fuzzer classes."""

__all__ = [
    "PublicationCallOutBundle",
    "PUBLICATION_DETERMINISTIC",
    "PUBLICATION_STOCHASTIC",
]
