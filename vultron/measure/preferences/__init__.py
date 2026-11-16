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
"""The path preferences of a case, counted from its event history (ADR-0182).

A path preference is about the shape of a history rather than the order of
two events, so it is a count or a ratio, never a score against chance
(``docs/topics/measuring_cvd/reward_functions.md``):

* :mod:`~vultron.measure.preferences.model` — the typed counts: one record
  for each participant and one for the case.
* :mod:`~vultron.measure.preferences.count` — :func:`path_preferences`, which
  reads them from a :class:`~vultron.measure.history.CaseEventHistory`.
"""

from vultron.measure.preferences.count import path_preferences
from vultron.measure.preferences.model import (
    CasePathCounts,
    DurationUndefined,
    EmbargoDuration,
    ParticipantPathCounts,
    PathPreferences,
)

__all__ = [
    "CasePathCounts",
    "DurationUndefined",
    "EmbargoDuration",
    "ParticipantPathCounts",
    "PathPreferences",
    "path_preferences",
]
