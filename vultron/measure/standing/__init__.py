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

"""Where a case stands: its states, its desiderata, its moves (ADR-0190).

The first level of the shadow's insights reads a case ledger as it stands:
each participant's states, the desiderata each vendor's case has met, broken
or left open, and the moves the state machines allow from here.  It reads a
ledger through the layers below it and adds no rule of its own.

* :mod:`~vultron.measure.standing.moves` — the allowed moves, one typed
  class per machine; a case-state move extends a history a measure can
  score.
* :mod:`~vultron.measure.standing.model` — the standing record, and the gap
  a ledger with a hole yields in its place.
* :mod:`~vultron.measure.standing.joint` — the standing as a point of the
  case's joint walk, and the joint step each move takes there.
* :mod:`~vultron.measure.standing.read` — :func:`case_standing`, each
  allowed move with each vendor's change in expected outcome (#6449).
"""

from vultron.measure.standing.joint import case_prefix, joint_step
from vultron.measure.standing.model import (
    CaseStanding,
    DesideratumChange,
    DesideratumStanding,
    DesideratumStatus,
    ParticipantStanding,
    ScoredMove,
    StandingGap,
    StandingRecord,
    desiderata_standing,
)
from vultron.measure.standing.moves import (
    CSMove,
    EMMove,
    RMMove,
    cs_moves,
    em_moves,
    rm_moves,
)
from vultron.measure.standing.read import case_standing

__all__ = [
    "CSMove",
    "CaseStanding",
    "DesideratumChange",
    "DesideratumStanding",
    "DesideratumStatus",
    "EMMove",
    "ParticipantStanding",
    "RMMove",
    "ScoredMove",
    "StandingGap",
    "StandingRecord",
    "case_prefix",
    "case_standing",
    "cs_moves",
    "desiderata_standing",
    "em_moves",
    "joint_step",
    "rm_moves",
]
