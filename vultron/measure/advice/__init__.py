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

"""Move advice: each open move of a case in a band by its outcome shifts (ADR-0200).

:mod:`.shifts` reads each vendor's outcome shift from the walk of ADR-0182;
:mod:`.bands` puts the moves in bands and layers and marks them; and
:mod:`.case` reads a case's standing record into the typed
:class:`CaseAdvice` the case shadow shows (ADR-0190).  The advice ranks no
move by one case score.
"""

from vultron.measure.advice.bands import (
    BAND_ORDER,
    Band,
    Harm,
    MoveAdvice,
    Part,
    advise,
    band,
    deciding_parts,
    dominates,
    harms,
    layers,
)
from vultron.measure.advice.case import (
    BAND_COLOUR_MAPS,
    COORDINATOR_ROLES,
    DOMINATED_BY_HARM_FREE,
    HARM_NOTE,
    HELP_TEXT,
    AdvisedMove,
    BandAdvice,
    CaseAdvice,
    ColourMap,
    UnbandedMove,
    VendorHarm,
    VendorShift,
    case_advice,
)
from vultron.measure.advice.shifts import (
    CHANCE_EVENTS,
    SCOPE_GROUPS,
    ScopeParts,
    ScopeShift,
    chance_values,
    move_shifts,
    open_moves,
    outcome_shift,
    scope_shift,
)

__all__ = [
    "BAND_COLOUR_MAPS",
    "BAND_ORDER",
    "COORDINATOR_ROLES",
    "DOMINATED_BY_HARM_FREE",
    "HARM_NOTE",
    "HELP_TEXT",
    "AdvisedMove",
    "BandAdvice",
    "CaseAdvice",
    "ColourMap",
    "UnbandedMove",
    "VendorHarm",
    "VendorShift",
    "case_advice",
    "CHANCE_EVENTS",
    "SCOPE_GROUPS",
    "Band",
    "Harm",
    "MoveAdvice",
    "Part",
    "ScopeParts",
    "ScopeShift",
    "advise",
    "band",
    "chance_values",
    "deciding_parts",
    "dominates",
    "harms",
    "layers",
    "open_moves",
    "outcome_shift",
    "move_shifts",
    "scope_shift",
]
