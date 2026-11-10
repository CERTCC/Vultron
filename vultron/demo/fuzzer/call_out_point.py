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
- Four shape mixin classes, one per capability shape (Evaluator, Retriever,
  Composer, Actuator), that document the lifecycle pattern and blackboard
  contract for each call-out point shape.

There is no Sentinel mixin.  A Sentinel is a call-in integration pattern, not
a capability shape: it watches a condition and calls a trigger endpoint on its
own initiative, so it has no call-out point node, no blackboard contract and no
backend factory (ADR-0097, BT-18-013).

References
----------
- ADR-0024: ``docs/adr/0024-coordination-agent-taxonomy.md``
- ADR-0025: ``docs/adr/0025-call-out-point-abstraction-layer.md``
- ADR-0097: ``docs/adr/0097-capability-layer-four-shapes-and-core-declared-contracts.md``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-18-001 through BT-18-004
"""

from __future__ import annotations

from typing import ClassVar

from py_trees.common import Access, Status

from vultron.core.behaviors.call_out_point import (
    CallOutBackendFactory,
)

__all__ = [
    "CallOutBackendFactory",
    "EvaluatorCallOutPoint",
    "RetrieverCallOutPoint",
    "ComposerCallOutPoint",
    "ActuatorCallOutPoint",
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

    output_keys: ClassVar[dict[str, type]] = {}

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

    output_keys: ClassVar[dict[str, type]] = {}

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

    output_keys: ClassVar[dict[str, type]] = {}

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

    output_keys: ClassVar[dict[str, type]] = {}

    def setup(self, **kwargs) -> None:  # type: ignore[override]
        super().setup(**kwargs)  # type: ignore[misc]

    def update(self) -> Status:
        return Status(super().update())  # type: ignore[misc, arg-type]
