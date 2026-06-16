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

"""Adapter implementing
:class:`~vultron.core.ports.trigger_activity.TriggerActivityPort`.

Reads persisted objects from the DataLayer, calls the appropriate wire-layer
factory functions to construct outbound ActivityStreams activities, persists
the activities, and returns ``(activity_id, activity_dict)`` or
``activity_id`` to callers.

This adapter is the **sole** location where trigger-related domain→wire
translation occurs for activity construction, keeping ``vultron/core/`` free
of wire-layer factory imports (ARCH-01-001).

The adapter is composed from domain-focused mixin classes:

- :mod:`.notes` — Note creation and attachment
- :mod:`.reports` — VulnerabilityReport submission, close, and invalidation
- :mod:`.cases` — VulnerabilityCase creation, engagement, and announcement
- :mod:`.actors` — Actor invitations, recommendations, participant management,
  and CASE_MANAGER delegation
- :mod:`.embargo` — Embargo proposal, acceptance, rejection, and termination

See also:
    - ``vultron/core/ports/trigger_activity.py`` — port Protocol
    - ``vultron/wire/as2/factories/`` — factory functions
    - ``vultron/wire/as2/factories/AGENTS.md``
"""

from ._base import _TriggerAdapterBase
from .actors import _ActorsMixin
from .cases import _CasesMixin
from .embargo import _EmbargoMixin
from .notes import _NotesMixin
from .reports import _ReportsMixin

__all__ = ["TriggerActivityAdapter"]


class TriggerActivityAdapter(
    _NotesMixin,
    _ReportsMixin,
    _CasesMixin,
    _ActorsMixin,
    _EmbargoMixin,
    _TriggerAdapterBase,
):
    """Driven adapter for constructing and persisting outbound wire activities.

    Instantiate once per request with the DataLayer for that request; pass to
    :class:`~vultron.core.use_cases.triggers.service.TriggerService` as
    ``trigger_activity``.

    Args:
        dl: The DataLayer for reading persisted objects and creating activities.
    """
