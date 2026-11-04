#!/usr/bin/env python
"""FastAPI adapter implementations for inbox orchestration.

Provides concrete adapter classes that implement the
:mod:`vultron.core.behaviors.inbox` protocols using the FastAPI
DataLayer and dispatcher infrastructure:

- :class:`FastAPIIngressAdapter` — parse (wire) + rehydrate (staged)
  (``ingress``)
- :class:`FastAPIDispatchAdapter` — wraps the dispatcher port (``ports``)
- :class:`FastAPIQueuePort` — wraps pending-case queue helpers (``ports``)

The inbox background task that runs them, ``run_inbox_pipeline``, lives in
``pipeline`` with the per-actor lock that serialises it.

The replay of the inbox queue, with its bounded retry and dead letter, and
its ``StoredActivityIngressAdapter`` live in
:mod:`~vultron.adapters.driving.fastapi.inbox_queue_drain` (IE-06-004).

These adapters are constructed in the inbox background task and passed to
:func:`~vultron.core.behaviors.inbox.process_payload` (IO-03-001,
IO-03-003).
"""

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

from vultron.adapters.driving.fastapi.inbox_orchestration.ingress import (
    FastAPIIngressAdapter,
)
from vultron.adapters.driving.fastapi.inbox_orchestration.pipeline import (
    replay_inbox_queue,
    run_inbox_pipeline,
    run_serialised_actor_work,
)
from vultron.adapters.driving.fastapi.inbox_orchestration.ports import (
    FastAPIDispatchAdapter,
    FastAPIQueuePort,
)

__all__ = [
    "FastAPIDispatchAdapter",
    "FastAPIIngressAdapter",
    "FastAPIQueuePort",
    "replay_inbox_queue",
    "run_inbox_pipeline",
    "run_serialised_actor_work",
]
