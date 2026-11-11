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
"""Per-vendor case-state sequences projected from a case event history (CEH-05).

Read through :mod:`vultron.measure.history`, never beside it:

* :mod:`~vultron.measure.sequences.model` — the per-vendor sequence, which
  refuses anything that is not a valid case-state history prefix, and the
  participant reported with no sequence.
* :mod:`~vultron.measure.sequences.project` — the projection,
  :func:`case_state_sequences`.

The layer stops at the validated sequence: it scores nothing (CEH-05-008).
"""

from vultron.measure.sequences.model import (
    CaseStateSequence,
    CaseStateSequences,
    UnprojectableParticipant,
    UnprojectableReason,
)
from vultron.measure.sequences.project import case_state_sequences

__all__ = [
    "CaseStateSequence",
    "CaseStateSequences",
    "UnprojectableParticipant",
    "UnprojectableReason",
    "case_state_sequences",
]
