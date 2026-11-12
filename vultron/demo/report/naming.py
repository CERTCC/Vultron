"""Friendly labels and event phrases for the demo report (DRPT-03).

The labels and the phrase lookup this module once held live in
:mod:`vultron.measure.ledger`, which the report tool and the measure layer
share, so both tools name an actor and word an event alike
(``notes/case-event-history.md`` § "Reuse the One JSONL Walker").  The names
are re-exported here for the report tool's callers.
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

from vultron.measure.ledger import (
    event_phrase,
    friendly_target_noun,
)

__all__ = ["event_phrase", "friendly_target_noun"]
