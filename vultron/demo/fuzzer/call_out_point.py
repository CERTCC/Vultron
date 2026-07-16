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
"""Call-out point abstraction layer for the Vultron BT port/adapter seam.

This module provides:

- :data:`CallOutBackendFactory` — the factory callable type used to inject
  swappable backends into tree builder functions (ADR-0025, BT-18-004).
- Five shape mixin classes (one per ADR-0024 agent shape) that document the
  lifecycle pattern and blackboard contract for each call-out point shape.
- Three illustrative Sentinel subclasses (validation, prioritization,
  deployment) that document the shape interface; full Sentinel
  implementation is tracked in issue #1175 (FUZZ-08f).

References
----------
- ADR-0024: ``docs/adr/0024-coordination-agent-taxonomy.md``
- ADR-0025: ``docs/adr/0025-call-out-point-abstraction-layer.md``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-18-001 through BT-18-004
"""

from __future__ import annotations

from py_trees.common import Access, Status

from vultron.core.behaviors.call_out_point import (
    CallOutBackendFactory,
)  # noqa: F401
from vultron.demo.fuzzer.base import WeightedBehavior

__all__ = [
    "CallOutBackendFactory",
    "EvaluatorCallOutPoint",
    "RetrieverCallOutPoint",
    "ComposerCallOutPoint",
    "ActuatorCallOutPoint",
    "SentinelCallOutPoint",
    "NewValidationInfoSentinel",
    "NewPrioritizationInfoSentinel",
    "NewDeploymentInfoSentinel",
]


# ---------------------------------------------------------------------------
# Shape mixin classes
# ---------------------------------------------------------------------------


class EvaluatorCallOutPoint:
    """Mixin for Evaluator-shaped call-out points (ADR-0024).

    An Evaluator receives situation context and writes a structured
    recommendation to a declared output key on SUCCESS.

    Lifecycle:
      - ``setup()``: registers output keys for WRITE access on the blackboard.
      - ``update()``: calls the backend logic (via super()); on SUCCESS writes
        type-conformant synthetic data to all declared output keys (BT-18-002,
        BT-18-003).

    Subclasses must:
      - Declare ``output_keys: dict[str, type]`` with the blackboard keys
        written on SUCCESS and their expected Python types.
      - Document a blackboard contract section in their docstring (BT-18-001).

    Example blackboard contract docstring section::

        Blackboard contract (BT-18-001):
          Input keys:  report_id — str (read from caller's context)
          Output keys: credibility_verdict: str  (SUCCESS only)
    """

    output_keys: dict[str, type] = {}

    def setup(self, **kwargs) -> None:  # type: ignore[override]
        super().setup(**kwargs)  # type: ignore[misc]
        if self.output_keys:
            self._bb_writer = self.attach_blackboard_client(  # type: ignore[attr-defined]
                name=f"{self.__class__.__name__}_writer"
            )
            for key in self.output_keys:
                self._bb_writer.register_key(key, Access.WRITE)

    def update(self) -> Status:
        status = super().update()  # type: ignore[misc]
        if status == Status.SUCCESS and self.output_keys:
            for key, typ in self.output_keys.items():
                setattr(self._bb_writer, key, typ())
        return Status(status)  # type: ignore[arg-type]


class RetrieverCallOutPoint:
    """Mixin for Retriever-shaped call-out points (ADR-0024).

    A Retriever receives an on-demand query and writes structured facts from
    an external source to declared output keys on SUCCESS.  For binary-result
    Retrievers (boolean queries), output_keys is empty and the result is
    expressed as SUCCESS/FAILURE only (BT-18-006).

    Lifecycle identical to :class:`EvaluatorCallOutPoint`; the distinction is
    semantic: a Retriever fetches external facts, an Evaluator produces a
    structured recommendation based on context.

    Subclasses must:
      - Declare ``output_keys: dict[str, type]``.
      - Document a blackboard contract section in their docstring (BT-18-001).
    """

    output_keys: dict[str, type] = {}

    def setup(self, **kwargs) -> None:  # type: ignore[override]
        super().setup(**kwargs)  # type: ignore[misc]
        if self.output_keys:
            self._bb_writer = self.attach_blackboard_client(  # type: ignore[attr-defined]
                name=f"{self.__class__.__name__}_writer"
            )
            for key in self.output_keys:
                self._bb_writer.register_key(key, Access.WRITE)

    def update(self) -> Status:
        status = super().update()  # type: ignore[misc]
        if status == Status.SUCCESS and self.output_keys:
            for key, typ in self.output_keys.items():
                setattr(self._bb_writer, key, typ())
        return Status(status)  # type: ignore[arg-type]


class ComposerCallOutPoint:
    """Mixin for Composer-shaped call-out points (ADR-0024).

    A Composer receives composition context and writes a generated content
    artifact to a declared output key on SUCCESS.

    Lifecycle identical to :class:`EvaluatorCallOutPoint`; the distinction is
    semantic: a Composer generates a *new* content artifact (advisory, patch
    notes, exploit write-up), whereas an Evaluator produces a recommendation.

    Subclasses must:
      - Declare ``output_keys: dict[str, type]`` with the artifact output key.
      - Document a blackboard contract section in their docstring (BT-18-001).
    """

    output_keys: dict[str, type] = {}

    def setup(self, **kwargs) -> None:  # type: ignore[override]
        super().setup(**kwargs)  # type: ignore[misc]
        if self.output_keys:
            self._bb_writer = self.attach_blackboard_client(  # type: ignore[attr-defined]
                name=f"{self.__class__.__name__}_writer"
            )
            for key in self.output_keys:
                self._bb_writer.register_key(key, Access.WRITE)

    def update(self) -> Status:
        status = super().update()  # type: ignore[misc]
        if status == Status.SUCCESS and self.output_keys:
            for key, typ in self.output_keys.items():
                setattr(self._bb_writer, key, typ())
        return Status(status)  # type: ignore[arg-type]


class ActuatorCallOutPoint:
    """Mixin for Actuator-shaped call-out points (ADR-0024 amendment 2026-07-07).

    An Actuator receives a trigger and context; it invokes an external system
    to cause a side effect (notification dispatch, state write, queue mutation,
    API call).  It does NOT produce a content artifact on the blackboard.
    SUCCESS means the side effect was confirmed; FAILURE means it could not
    be executed.

    Subclasses must:
      - Declare ``output_keys = {}`` (no blackboard output — see ADR-0024).
      - Document a blackboard contract section in their docstring (BT-18-001).
    """

    output_keys: dict[str, type] = {}

    def setup(self, **kwargs) -> None:  # type: ignore[override]
        super().setup(**kwargs)  # type: ignore[misc]

    def update(self) -> Status:
        return Status(super().update())  # type: ignore[misc, arg-type]


class SentinelCallOutPoint:
    """Mixin for Sentinel-shaped call-out points (ADR-0024).

    A Sentinel monitors a condition independently of the BT tick loop.  When
    the condition is met it calls a trigger endpoint to inject a signal into
    the protocol.  Sentinels do NOT produce a blackboard artifact — their
    output is the trigger call, not a written key.

    Unlike the other four shapes, a Sentinel is NOT placed as a BT node inside
    a tree builder.  It runs as an external agent seam outside the tick loop.
    This mixin documents the shape interface; full implementation is tracked in
    issue #1175 (FUZZ-08f).

    Subclasses must:
      - Declare ``output_keys = {}`` (no blackboard output).
      - Document a blackboard contract section in their docstring (BT-18-001).
    """

    output_keys: dict[str, type] = {}

    def setup(self, **kwargs) -> None:  # type: ignore[override]
        super().setup(**kwargs)  # type: ignore[misc]

    def update(self) -> Status:
        return Status(super().update())  # type: ignore[misc, arg-type]


# ---------------------------------------------------------------------------
# Illustrative Sentinel subclasses
# ---------------------------------------------------------------------------


class NewValidationInfoSentinel(SentinelCallOutPoint, WeightedBehavior):
    """Monitors the case record for new validation-relevant events.

    Semantic function:
        Sentinel — registers with a case-event source and fires a
        change-detection signal into the BT blackboard when new
        validation-relevant information arrives (e.g., reporter follow-up,
        credibility update, new threat intelligence).  The flag is consumed
        by ``NoNewValidationInfo`` at the top of the ``ValidationOrShortcut``
        Selector in ``create_validate_report_tree``.

    Blackboard contract (BT-18-001):
      Input keys:  (monitors external case-event source; no blackboard reads)
      Output keys: (none — fires trigger endpoint; no content artifact)

    Input category: System integration (case management event subscription).

    Success probability: 0.10 (``AlmostAlwaysFail``).

    Automation potential: **High** — event subscription on the case record
    or metadata timestamp comparison; fully automatable.

    Note:
        This is an illustrative subclass that documents the Sentinel interface.
        Full implementation is tracked in issue #1175 (FUZZ-08f).  In
        production a Sentinel runs outside the BT tick loop and calls a trigger
        endpoint when its monitored condition fires; it is not placed inside a
        tree builder function.
    """

    success_rate = 0.10


class NewPrioritizationInfoSentinel(SentinelCallOutPoint, WeightedBehavior):
    """Monitors the case record for new prioritization-relevant events.

    Semantic function:
        Sentinel — registers with a case-event source and fires a
        change-detection signal into the BT blackboard when new
        prioritization-relevant information arrives (e.g., updated SSVC
        scoring data, new threat intelligence, CVSS score update).  The flag
        is consumed by ``NoNewPrioritizationInfo`` at the top of the
        ``PrioritizeBT`` Selector in
        ``create_prioritize_subtree``.

    Blackboard contract (BT-18-001):
      Input keys:  (monitors external case-event source; no blackboard reads)
      Output keys: (none — fires trigger endpoint; no content artifact)

    Input category: System integration (case management event subscription).

    Success probability: 0.10 (``AlmostAlwaysFail``).

    Automation potential: **High** — event subscription on the case record
    or metadata timestamp comparison (SSVC decision-point availability,
    CVSS score updates); fully automatable.

    Note:
        In production a Sentinel runs outside the BT tick loop and calls a
        trigger endpoint when its monitored condition fires; it is not placed
        inside a tree builder function.
    """

    success_rate = 0.10


class NewDeploymentInfoSentinel(SentinelCallOutPoint, WeightedBehavior):
    """Monitors deployment-relevant data sources for new events.

    Semantic function:
        Sentinel — registers with deployment-relevant data sources (e.g.,
        patch management system, CI/CD pipeline, asset inventory) and fires
        a change-detection signal into the BT blackboard when new
        deployment-related events arrive.  The flag is consumed by
        ``NoNewDeploymentInfo`` at the top of the ``Deployment`` Fallback
        Selector in ``create_deploy_fix_tree``.

    Blackboard contract (BT-18-001):
      Input keys:  (monitors external deployment-event source; no blackboard reads)
      Output keys: (none — fires trigger endpoint; no content artifact)

    Input category: System integration (patch management / CI/CD event subscription).

    Success probability: 0.10 (``AlmostAlwaysFail``).

    Automation potential: **High** — event subscription on the patch
    management system or CI/CD pipeline; fully automatable.

    Note:
        In production a Sentinel runs outside the BT tick loop and calls a
        trigger endpoint when its monitored condition fires; it is not placed
        inside a tree builder function.
    """

    success_rate = 0.10
